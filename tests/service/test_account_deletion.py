"""DELETE /api/v1/me (docs/saas-buildout.md section 11). Multi-member org
scenarios are set up by direct DB manipulation, matching how test_api_keys.py
upgrades a plan directly -- there's no invite/add-member endpoint yet to
build a second membership through the API.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

from rivet_service.db.models import (
    Artifact,
    Candidate,
    Generation,
    Membership,
    Organization,
    Project,
    Subscription,
    User,
)
from rivet_service.db.session import SessionLocal

from .test_generations import VALID_GENERATE_PAYLOAD, _run_worker_once


def _register(client, email: str) -> dict:
    res = client.post("/api/v1/auth/register", json={"email": email, "password": "hunter22222", "accept_tos": True})
    return res.json()


def _add_existing_user_to_org_as_member(user_id: str, org_id: str) -> None:
    """Deletes the user's own auto-created solo org (so their only
    remaining membership is the one we're about to add -- resolve_org_for_user
    picks a user's earliest-created membership, so a stray solo org would
    otherwise win instead of the org this test actually cares about), then
    adds them to ``org_id`` as a plain member.
    """
    db = SessionLocal()
    try:
        user_uuid = uuid.UUID(user_id)
        own_membership = db.query(Membership).filter_by(user_id=user_uuid).first()
        own_org_id = own_membership.org_id
        db.delete(own_membership)
        db.flush()  # the membership must actually be gone before the org FK check below runs
        db.query(Organization).filter_by(id=own_org_id).delete()
        db.add(Membership(user_id=user_uuid, org_id=uuid.UUID(org_id), role="member"))
        db.commit()
    finally:
        db.close()


def test_account_deletion_requires_authentication(client):
    res = client.delete("/api/v1/me")
    assert res.status_code == 401


def test_account_deletion_sole_member_cascades_everything(client):
    reg = _register(client, "solo-delete@example.com")
    user_id, org_id = reg["user"]["id"], reg["org"]["id"]

    project_id = client.post("/api/v1/projects", json={"name": "Doomed Project"}).json()["id"]
    gen_id = client.post(f"/api/v1/projects/{project_id}/generations", json=VALID_GENERATE_PAYLOAD).json()[
        "generation_id"
    ]
    _run_worker_once()
    download = client.get(f"/api/v1/generations/{gen_id}/candidates/1/download?format=png").json()
    token = download["download_url"].rsplit("/", 1)[-1]

    res = client.delete("/api/v1/me")
    assert res.status_code == 200
    assert "rivet_session" not in client.cookies
    assert "rivet_csrf" not in client.cookies

    db = SessionLocal()
    try:
        assert db.get(User, uuid.UUID(user_id)) is None
        assert db.get(Organization, uuid.UUID(org_id)) is None
        assert db.query(Project).filter_by(id=uuid.UUID(project_id)).first() is None
        assert db.query(Generation).filter_by(id=uuid.UUID(gen_id)).first() is None
        assert db.query(Candidate).filter_by(generation_id=uuid.UUID(gen_id)).first() is None
        assert db.query(Artifact).count() == 0 or all(
            a.candidate_id != uuid.UUID(gen_id) for a in db.query(Artifact).all()
        )
    finally:
        db.close()

    # The artifact file itself is gone from storage too, not just the DB row.
    assert client.get(f"/api/v1/local-artifacts/{token}").status_code == 404


def test_account_deletion_non_owner_leaves_org_and_teammates_data_intact(client):
    owner = _register(client, "owner-stays@example.com")
    org_id = owner["org"]["id"]
    project_id = client.post("/api/v1/projects", json={"name": "Shared Project"}).json()["id"]

    client.cookies.clear()
    member = _register(client, "member-leaves@example.com")
    _add_existing_user_to_org_as_member(member["user"]["id"], org_id)

    res = client.delete("/api/v1/me")
    assert res.status_code == 200

    db = SessionLocal()
    try:
        assert db.get(User, uuid.UUID(member["user"]["id"])) is None
        assert db.get(Organization, uuid.UUID(org_id)) is not None  # org survives
        assert db.query(Project).filter_by(id=uuid.UUID(project_id)).first() is not None  # teammate's data survives
        assert db.query(Membership).filter_by(org_id=uuid.UUID(org_id)).count() == 1  # only the owner remains
    finally:
        db.close()


def test_account_deletion_blocks_sole_owner_with_other_members(client):
    owner = _register(client, "blocked-owner@example.com")
    user_id, org_id = owner["user"]["id"], owner["org"]["id"]

    client.cookies.clear()
    member = _register(client, "blocking-member@example.com")
    _add_existing_user_to_org_as_member(member["user"]["id"], org_id)

    client.cookies.clear()
    client.post("/api/v1/auth/login", json={"email": "blocked-owner@example.com", "password": "hunter22222"})

    res = client.delete("/api/v1/me")
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "owner_transfer_required"

    db = SessionLocal()
    try:
        assert db.get(User, uuid.UUID(user_id)) is not None
        assert db.get(Organization, uuid.UUID(org_id)) is not None
        assert db.query(Membership).filter_by(org_id=uuid.UUID(org_id)).count() == 2
    finally:
        db.close()


def test_account_deletion_cancels_subscription_and_deletes_stripe_customer(client):
    reg = _register(client, "stripe-cleanup@example.com")
    org_id = uuid.UUID(reg["org"]["id"])

    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        org.stripe_customer_id = "cus_to_delete"
        db.add(
            Subscription(
                org_id=org_id,
                provider="stripe",
                provider_customer_id="cus_to_delete",
                provider_subscription_id="sub_to_cancel",
                plan_code="free",
                status="active",
                current_period_start=org.created_at,
                current_period_end=org.created_at,
            )
        )
        db.commit()
    finally:
        db.close()

    with (
        patch("rivet_service.api.v1.me.cancel_subscription") as mock_cancel,
        patch("rivet_service.api.v1.me.delete_customer") as mock_delete_customer,
    ):
        res = client.delete("/api/v1/me")

    assert res.status_code == 200
    mock_cancel.assert_called_once_with("sub_to_cancel")
    mock_delete_customer.assert_called_once_with("cus_to_delete")
