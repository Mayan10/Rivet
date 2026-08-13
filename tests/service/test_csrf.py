"""auth/csrf.py: double-submit-cookie CSRF protection. The ``client``
fixture (conftest.py) auto-attaches a matching ``X-CSRF-Token`` header on
every request so the other ~90 tests in this suite don't need to think
about CSRF at all -- these tests explicitly override that header (which
the auto-fill only fills in when *absent*) to exercise rejection.
"""

from __future__ import annotations


def test_csrf_rejects_missing_token(client):
    client.post("/api/v1/auth/register", json={"email": "csrf-missing@example.com", "password": "hunter22222", "accept_tos": True})
    res = client.post("/api/v1/projects", json={"name": "x"}, headers={"X-CSRF-Token": ""})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_failed"


def test_csrf_rejects_mismatched_token(client):
    client.post("/api/v1/auth/register", json={"email": "csrf-mismatch@example.com", "password": "hunter22222", "accept_tos": True})
    res = client.post("/api/v1/projects", json={"name": "x"}, headers={"X-CSRF-Token": "not-the-real-token"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "csrf_failed"


def test_csrf_not_required_for_safe_methods(client):
    client.post("/api/v1/auth/register", json={"email": "csrf-get@example.com", "password": "hunter22222", "accept_tos": True})
    res = client.get("/api/v1/me", headers={"X-CSRF-Token": ""})
    assert res.status_code == 200


def test_csrf_not_required_for_api_key_auth(client):
    res = client.post("/api/v1/auth/register", json={"email": "csrf-apikey@example.com", "password": "hunter22222", "accept_tos": True})
    org_id = res.json()["org"]["id"]

    import uuid

    from rivet_service.db.models import Organization
    from rivet_service.db.session import SessionLocal

    db = SessionLocal()
    try:
        db.get(Organization, uuid.UUID(org_id)).plan_code = "studio"
        db.commit()
    finally:
        db.close()

    key = client.post("/api/v1/api-keys", json={"name": "csrf test key"}).json()

    client.cookies.clear()
    # No X-CSRF-Token at all -- api-key auth (Authorization header) isn't
    # cookie-based, so there's nothing to double-submit against.
    res = client.delete(f"/api/v1/api-keys/{key['id']}", headers={"Authorization": f"Bearer {key['key']}"})
    assert res.status_code == 200


def test_valid_csrf_token_succeeds(client):
    # The baseline every other test in the suite already exercises
    # implicitly (auto-filled by the client fixture) -- asserted directly
    # here so this file also documents the success path, not just failure.
    client.post("/api/v1/auth/register", json={"email": "csrf-valid@example.com", "password": "hunter22222", "accept_tos": True})
    res = client.post("/api/v1/projects", json={"name": "valid csrf project"})
    assert res.status_code == 200
