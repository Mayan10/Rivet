"""Redis-backed fixed-window limiting (rate_limit.py, docs/saas-buildout.md
section 11). Uses ``override_settings`` (conftest.py) to shrink the
window/limits for these tests rather than looping 30-120 real requests
against the production defaults -- faster and the exact threshold is
asserted precisely either way.
"""

from __future__ import annotations


def test_unauthenticated_requests_are_limited_by_ip(client, override_settings):
    override_settings(RATE_LIMIT_UNAUTHENTICATED_MAX=3, RATE_LIMIT_WINDOW_SECONDS=60)
    bad_login = {"email": "nobody@example.com", "password": "wrong-password"}

    for _ in range(3):
        res = client.post("/api/v1/auth/login", json=bad_login)
        assert res.status_code == 401

    res = client.post("/api/v1/auth/login", json=bad_login)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"


def test_authenticated_requests_are_limited_by_org_not_shared_across_orgs(client, override_settings):
    override_settings(RATE_LIMIT_AUTHENTICATED_MAX=3, RATE_LIMIT_WINDOW_SECONDS=60)
    client.post("/api/v1/auth/register", json={"email": "ratelimit-a@example.com", "password": "hunter22222", "accept_tos": True})

    for _ in range(3):
        assert client.get("/api/v1/me").status_code == 200
    res = client.get("/api/v1/me")
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"

    # A second, unrelated org must not be affected by the first org's
    # exhausted quota -- limits are keyed by org id, not shared globally.
    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"email": "ratelimit-b@example.com", "password": "hunter22222", "accept_tos": True})
    res_other_org = client.get("/api/v1/me")
    assert res_other_org.status_code == 200
