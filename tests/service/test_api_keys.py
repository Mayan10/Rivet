VALID_REGISTER = {"email": "keys-test@example.com", "password": "hunter22222"}


def test_create_api_key_returns_full_key_once(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    res = client.post("/api/v1/api-keys", json={"name": "CI key"})
    assert res.status_code == 200
    body = res.json()
    assert body["key"].startswith("rvt_live_")
    assert body["prefix"] == body["key"][:12]


def test_list_api_keys_never_exposes_the_full_key(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    client.post("/api/v1/api-keys", json={"name": "CI key"})

    res = client.get("/api/v1/api-keys")
    assert res.status_code == 200
    keys = res.json()["api_keys"]
    assert len(keys) == 1
    assert "key" not in keys[0]
    assert "key_hash" not in keys[0]


def test_create_api_key_requires_session_auth_not_just_api_key_auth(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    created = client.post("/api/v1/api-keys", json={"name": "CI key"}).json()
    full_key = created["key"]

    client.cookies.clear()
    res = client.post(
        "/api/v1/api-keys", json={"name": "second key"}, headers={"Authorization": f"Bearer {full_key}"}
    )
    assert res.status_code == 401


def test_api_key_authenticates_requests_without_a_session(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    full_key = client.post("/api/v1/api-keys", json={"name": "CI key"}).json()["key"]

    client.cookies.clear()
    res = client.get("/api/v1/me", headers={"Authorization": f"Bearer {full_key}"})
    assert res.status_code == 200
    body = res.json()
    assert body["auth_method"] == "api_key"
    assert body["user"] is None
    assert body["org"] is not None


def test_revoked_api_key_no_longer_authenticates(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    key_data = client.post("/api/v1/api-keys", json={"name": "CI key"}).json()
    full_key = key_data["key"]

    res = client.delete(f"/api/v1/api-keys/{key_data['id']}")
    assert res.status_code == 200

    client.cookies.clear()
    res2 = client.get("/api/v1/me", headers={"Authorization": f"Bearer {full_key}"})
    assert res2.status_code == 401


def test_revoke_unknown_api_key_returns_404(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    res = client.delete("/api/v1/api-keys/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404
