"""No real Stripe account is touched here (Phase 10 was built test-driven
against mocks, real credentials wired in later): checkout/portal session
creation mocks the SDK boundary (billing/stripe_client.py's two
`create_*` functions), while webhook signature verification and
idempotency are tested for real -- ``stripe.WebhookSignature`` builds an
actually-valid signed payload against STRIPE_WEBHOOK_SECRET (set in
conftest.py), the same helper Stripe's own SDK test suite uses, so this
exercises the real verification path end to end without a network call.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import stripe

from rivet_service.config import get_settings
from rivet_service.db.models import Organization, Plan, Subscription
from rivet_service.db.session import SessionLocal

VALID_REGISTER = {"email": "billing-test@example.com", "password": "hunter22222"}


def _register_org(client, *, email: str = VALID_REGISTER["email"]) -> uuid.UUID:
    res = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "hunter22222", "accept_tos": True}
    )
    return uuid.UUID(res.json()["org"]["id"])


def _set_price(plan_code: str, price_id: str) -> None:
    db = SessionLocal()
    try:
        plan = db.get(Plan, plan_code)
        plan.provider_price_id = price_id
        db.commit()
    finally:
        db.close()


def _build_subscription_event(
    *,
    event_id: str,
    event_type: str,
    org_id: uuid.UUID,
    price_id: str,
    status: str,
    subscription_id: str = "sub_test_1",
    customer_id: str = "cus_test_1",
) -> dict:
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": subscription_id,
                "customer": customer_id,
                "status": status,
                "metadata": {"org_id": str(org_id)},
                "items": {"data": [{"price": {"id": price_id}}]},
                "current_period_start": 1_700_000_000,
                "current_period_end": 1_702_592_000,
                "cancel_at_period_end": False,
            }
        },
    }


def _post_signed_webhook(client, event: dict):
    secret = get_settings().stripe_webhook_secret
    payload = json.dumps(event)
    header = stripe.WebhookSignature.generate_signature_header(payload, secret)
    return client.post("/api/v1/webhooks/stripe", content=payload.encode(), headers={"stripe-signature": header})


def _org_plan_code(org_id: uuid.UUID) -> str:
    db = SessionLocal()
    try:
        return db.get(Organization, org_id).plan_code
    finally:
        db.close()


# --- webhooks -----------------------------------------------------------


def test_webhook_rejects_invalid_signature(client):
    res = client.post(
        "/api/v1/webhooks/stripe", content=b'{"id": "evt_x", "type": "customer.subscription.updated"}',
        headers={"stripe-signature": "t=1,v1=not-a-real-signature"},
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_failed"


def test_webhook_subscription_updated_upgrades_org_plan(client):
    org_id = _register_org(client)
    _set_price("pro", "price_test_pro")
    event = _build_subscription_event(
        event_id="evt_upgrade_1",
        event_type="customer.subscription.updated",
        org_id=org_id,
        price_id="price_test_pro",
        status="active",
    )

    res = _post_signed_webhook(client, event)
    assert res.status_code == 200
    assert _org_plan_code(org_id) == "pro"

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter_by(provider_subscription_id="sub_test_1").first()
        assert sub is not None
        assert sub.status == "active"
        assert sub.plan_code == "pro"
    finally:
        db.close()


def test_webhook_is_idempotent_on_duplicate_event_id(client):
    org_id = _register_org(client, email="billing-idempotent@example.com")
    _set_price("pro", "price_test_pro")
    event = _build_subscription_event(
        event_id="evt_dup_1",
        event_type="customer.subscription.updated",
        org_id=org_id,
        price_id="price_test_pro",
        status="active",
        subscription_id="sub_dup_1",
    )

    assert _post_signed_webhook(client, event).status_code == 200
    assert _org_plan_code(org_id) == "pro"

    # Simulate something else changing the org's plan in between, then
    # redeliver the *same* event -- a real processing would flip it back
    # to "pro"; idempotent handling must not touch it a second time.
    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        org.plan_code = "free"
        db.commit()
    finally:
        db.close()

    assert _post_signed_webhook(client, event).status_code == 200
    assert _org_plan_code(org_id) == "free"


def test_webhook_past_due_degrades_org_without_deleting_subscription(client):
    org_id = _register_org(client, email="billing-pastdue@example.com")
    _set_price("pro", "price_test_pro")
    upgrade_event = _build_subscription_event(
        event_id="evt_pd_1",
        event_type="customer.subscription.updated",
        org_id=org_id,
        price_id="price_test_pro",
        status="active",
        subscription_id="sub_pd_1",
    )
    _post_signed_webhook(client, upgrade_event)
    assert _org_plan_code(org_id) == "pro"

    past_due_event = _build_subscription_event(
        event_id="evt_pd_2",
        event_type="customer.subscription.updated",
        org_id=org_id,
        price_id="price_test_pro",
        status="past_due",
        subscription_id="sub_pd_1",
    )
    res = _post_signed_webhook(client, past_due_event)
    assert res.status_code == 200
    assert _org_plan_code(org_id) == "free"  # degraded, not hard-locked

    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter_by(provider_subscription_id="sub_pd_1").first()
        assert sub is not None  # the record survives -- the UI can explain why
        assert sub.status == "past_due"
    finally:
        db.close()


def test_webhook_subscription_deleted_degrades_org_to_free(client):
    org_id = _register_org(client, email="billing-deleted@example.com")
    _set_price("studio", "price_test_studio")
    upgrade_event = _build_subscription_event(
        event_id="evt_del_1",
        event_type="customer.subscription.updated",
        org_id=org_id,
        price_id="price_test_studio",
        status="active",
        subscription_id="sub_del_1",
    )
    _post_signed_webhook(client, upgrade_event)
    assert _org_plan_code(org_id) == "studio"

    deleted_event = _build_subscription_event(
        event_id="evt_del_2",
        event_type="customer.subscription.deleted",
        org_id=org_id,
        price_id="price_test_studio",
        status="canceled",
        subscription_id="sub_del_1",
    )
    res = _post_signed_webhook(client, deleted_event)
    assert res.status_code == 200
    assert _org_plan_code(org_id) == "free"


def test_webhook_unknown_price_leaves_no_trace(client):
    org_id = _register_org(client, email="billing-unknown-price@example.com")
    event = _build_subscription_event(
        event_id="evt_unknown_price",
        event_type="customer.subscription.updated",
        org_id=org_id,
        price_id="price_does_not_exist",
        status="active",
    )
    payload = json.dumps(event)
    header = stripe.WebhookSignature.generate_signature_header(payload, get_settings().stripe_webhook_secret)

    try:
        client.post("/api/v1/webhooks/stripe", content=payload.encode(), headers={"stripe-signature": header})
        raised = False
    except RuntimeError:
        raised = True
    assert raised

    db = SessionLocal()
    try:
        from rivet_service.db.models import BillingEvent

        assert db.query(BillingEvent).filter_by(provider_event_id="evt_unknown_price").first() is None
    finally:
        db.close()


# --- checkout / portal sessions -----------------------------------------


def test_checkout_session_requires_session_auth(client):
    org_id = _register_org(client, email="billing-apikey@example.com")
    # api_access needs the studio plan -- upgrade directly then create a key.
    db = SessionLocal()
    try:
        db.get(Organization, org_id).plan_code = "studio"
        db.commit()
    finally:
        db.close()
    key_res = client.post("/api/v1/api-keys", json={"name": "billing test key"})
    full_key = key_res.json()["key"]

    client.cookies.clear()
    res = client.post(
        "/api/v1/billing/checkout-session",
        json={"plan_code": "pro"},
        headers={"Authorization": f"Bearer {full_key}"},
    )
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_checkout_session_rejects_unpriced_plan(client):
    _register_org(client, email="billing-unpriced@example.com")
    res = client.post("/api/v1/billing/checkout-session", json={"plan_code": "free"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_failed"


def test_checkout_session_returns_url_and_persists_customer_id(client):
    org_id = _register_org(client, email="billing-checkout@example.com")
    _set_price("pro", "price_test_pro")

    fake_session = type("FakeSession", (), {"url": "https://checkout.stripe.com/test", "customer": "cus_new_1"})()
    with patch("rivet_service.api.v1.billing.create_checkout_session", return_value=fake_session) as mocked:
        res = client.post("/api/v1/billing/checkout-session", json={"plan_code": "pro"})

    assert res.status_code == 200
    assert res.json()["checkout_url"] == "https://checkout.stripe.com/test"
    mocked.assert_called_once_with(customer_id=None, price_id="price_test_pro", org_id=str(org_id))

    db = SessionLocal()
    try:
        assert db.get(Organization, org_id).stripe_customer_id == "cus_new_1"
    finally:
        db.close()


def test_portal_session_requires_existing_customer(client):
    _register_org(client, email="billing-no-customer@example.com")
    res = client.post("/api/v1/billing/portal-session")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_failed"


def test_portal_session_returns_url(client):
    org_id = _register_org(client, email="billing-portal@example.com")
    db = SessionLocal()
    try:
        db.get(Organization, org_id).stripe_customer_id = "cus_existing_1"
        db.commit()
    finally:
        db.close()

    fake_session = type("FakeSession", (), {"url": "https://billing.stripe.com/test"})()
    with patch("rivet_service.api.v1.billing.create_portal_session", return_value=fake_session):
        res = client.post("/api/v1/billing/portal-session")

    assert res.status_code == 200
    assert res.json()["portal_url"] == "https://billing.stripe.com/test"
