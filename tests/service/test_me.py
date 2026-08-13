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
    # Phase 9: freshly-registered orgs default to the free plan.
    assert body["plan"] == "free"
    assert body["entitlements"]["monthly_generations"] == 5
    assert body["entitlements"]["max_candidates"] == 1
    assert body["usage_this_period"] == {"generations": 0}
