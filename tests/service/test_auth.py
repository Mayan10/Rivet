from rivet_service.auth.tokens import generate_token
from rivet_service.config import get_settings

VALID_REGISTER = {"email": "auth-test@example.com", "password": "hunter22222"}


def _issue_token(user_id: str, purpose: str, ttl_seconds: int = 3600) -> str:
    return generate_token(get_settings().secret_key, purpose=purpose, subject=user_id, ttl_seconds=ttl_seconds)


def test_register_creates_user_org_membership_and_session(client):
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    assert res.status_code == 200
    body = res.json()
    assert body["user"]["email"] == VALID_REGISTER["email"]
    assert body["user"]["email_verified"] is False
    assert body["org"]["name"]
    assert "rivet_session" in res.cookies


def test_register_email_is_case_insensitive_for_uniqueness(client):
    client.post("/api/v1/auth/register", json={"email": "Case@Example.com", "password": "hunter22222"})
    res = client.post("/api/v1/auth/register", json={"email": "case@example.com", "password": "hunter22222"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "validation_failed"


def test_register_rejects_short_password(client):
    res = client.post("/api/v1/auth/register", json={"email": "short@example.com", "password": "short"})
    assert res.status_code == 400


def test_login_succeeds_with_correct_credentials(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    client.cookies.clear()
    res = client.post("/api/v1/auth/login", json=VALID_REGISTER)
    assert res.status_code == 200
    assert "rivet_session" in res.cookies


def test_login_rejects_wrong_password_with_generic_message(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    res = client.post("/api/v1/auth/login", json={"email": VALID_REGISTER["email"], "password": "wrongpassword"})
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "Invalid email or password."


def test_login_rejects_nonexistent_user_with_same_generic_message(client):
    res = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"})
    assert res.status_code == 401
    assert res.json()["error"]["message"] == "Invalid email or password."


def test_logout_revokes_the_session(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)
    assert client.get("/api/v1/me").status_code == 200

    client.post("/api/v1/auth/logout")
    assert client.get("/api/v1/me").status_code == 401


def test_verify_email_marks_user_verified(client):
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    user_id = res.json()["user"]["id"]

    token = _issue_token(user_id, "email_verify")
    res2 = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert res2.status_code == 200
    assert client.get("/api/v1/me").json()["user"]["email_verified"] is True


def test_verify_email_rejects_wrong_purpose_token(client):
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    user_id = res.json()["user"]["id"]

    token = _issue_token(user_id, "password_reset")  # wrong purpose for this endpoint
    res2 = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert res2.status_code == 400


def test_verify_email_rejects_expired_token(client):
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    user_id = res.json()["user"]["id"]

    token = _issue_token(user_id, "email_verify", ttl_seconds=-1)  # already expired
    res2 = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert res2.status_code == 400


def test_request_password_reset_returns_200_regardless_of_account_existence(client):
    client.post("/api/v1/auth/register", json=VALID_REGISTER)

    res_existing = client.post("/api/v1/auth/request-password-reset", json={"email": VALID_REGISTER["email"]})
    res_missing = client.post("/api/v1/auth/request-password-reset", json={"email": "nobody@example.com"})
    assert res_existing.status_code == 200
    assert res_missing.status_code == 200
    assert res_existing.json() == res_missing.json()  # identical response either way -- no enumeration signal


def test_reset_password_changes_password_and_revokes_existing_sessions(client):
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    user_id = res.json()["user"]["id"]
    assert client.get("/api/v1/me").status_code == 200  # session from registration is live

    token = _issue_token(user_id, "password_reset")
    res2 = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert res2.status_code == 200

    # The old session (still in the cookie jar) must no longer work.
    assert client.get("/api/v1/me").status_code == 401

    client.cookies.clear()
    old_login = client.post("/api/v1/auth/login", json=VALID_REGISTER)
    assert old_login.status_code == 401

    new_login = client.post("/api/v1/auth/login", json={"email": VALID_REGISTER["email"], "password": "newpassword123"})
    assert new_login.status_code == 200


def test_reset_password_rejects_reused_verify_email_token(client):
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    user_id = res.json()["user"]["id"]

    token = _issue_token(user_id, "email_verify")
    res2 = client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "newpassword123"})
    assert res2.status_code == 400
