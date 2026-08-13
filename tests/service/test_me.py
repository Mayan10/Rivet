def test_me_requires_authentication(client):
    res = client.get("/api/v1/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_me_reflects_session_auth(client):
    client.post("/api/v1/auth/register", json={"email": "me-test@example.com", "password": "hunter22222"})
    res = client.get("/api/v1/me")
    assert res.status_code == 200
    body = res.json()
    assert body["auth_method"] == "session"
    assert body["role"] == "owner"
    assert body["user"]["email"] == "me-test@example.com"
    # Not built until Phase 9 -- explicitly null, not omitted, so the
    # response shape doesn't change once they land.
    assert body["plan"] is None
    assert body["entitlements"] is None
    assert body["usage_this_period"] is None
