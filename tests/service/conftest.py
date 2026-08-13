"""Service-layer tests need the ``service`` extra installed and a real
Postgres to connect to (Phase 6 has no DB tables yet, but /readyz and the
session factory do real connections). Phase 8 tests additionally touch
Redis (jobs) and local disk (storage) -- both get dedicated, isolated
locations (a separate Redis DB index, a fresh temp directory) rather than
the shared dev instances, so running the suite never pollutes a
developer's own `docker compose up` state.

All three infra requirements are optional and skip this whole directory
cleanly (not a collection error) when missing -- so a contributor who
only ran ``pip install -e ".[dev]"`` (no ``service`` extra) or who
simply has no Postgres running still sees a fully green ``pytest -q`` at
the repo root. CI installs the ``service`` extra and sets DATABASE_URL
against a real Postgres service container, running ``alembic upgrade
head`` before pytest (an explicit release step, not done by these tests
-- see docs/saas-buildout.md "Ops"), so there this whole directory
actually runs.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://mayan@localhost:5432/rivet_test")
# A distinct DB index from the dev default (.../0) so `pytest -q` never
# shares queue state with a developer's own `docker compose up` / local
# worker.
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

_TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="rivet-test-storage-")
os.environ.setdefault("STORAGE_LOCAL_DIR", _TEST_STORAGE_DIR)

# Phase 10: fake but well-formed test-mode-shaped values -- no real
# Stripe account is ever contacted in tests (checkout/portal session
# creation is mocked at the SDK boundary; webhook tests build real
# locally-signed payloads against this same secret instead of hitting
# the network). See tests/service/test_billing.py's module docstring.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake_for_tests")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_fake_for_tests")

try:
    from fastapi.testclient import TestClient

    from rivet_service.db.session import database_is_reachable
    from rivet_service.main import create_app
except ImportError:
    pytest.skip(
        "rivet_service dependencies not installed -- run `pip install -e \".[service]\"` "
        "to include tests/service in the run.",
        allow_module_level=True,
    )

if not database_is_reachable():
    pytest.skip("No reachable DATABASE_URL configured -- skipping service tests.", allow_module_level=True)

from sqlalchemy import text  # only importable once the try/except above has succeeded

_DB_TABLES = (
    "artifacts",
    "candidates",
    "usage_events",
    "generations",
    "projects",
    "sessions",
    "api_keys",
    "billing_events",
    "subscriptions",
    "memberships",
    "organizations",
    "users",
)


@pytest.fixture(autouse=True)
def _clean_service_state():
    """Every Phase 6-8 table/queue/storage-dir persists across test runs
    in the shared dev/CI Postgres+Redis (no per-test transaction rollback
    -- routes commit their own sessions), so wipe them before every test
    rather than relying on unique-per-test data to avoid collisions.
    """
    from rivet_service.db.session import SessionLocal

    db = SessionLocal()
    try:
        for table in _DB_TABLES:
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
    finally:
        db.close()

    with contextlib.suppress(Exception):  # Redis may simply not be running; jobs-touching tests skip themselves
        from rivet_service.jobs.queue import get_redis_connection

        get_redis_connection().flushdb()

    shutil.rmtree(_TEST_STORAGE_DIR, ignore_errors=True)
    os.makedirs(_TEST_STORAGE_DIR, exist_ok=True)

    yield


class _AutoCsrfTestClient(TestClient):
    """Phase 11 added CSRF enforcement (auth/csrf.py) on cookie-authenticated
    state-changing requests -- a real security check, not something tests
    should bypass. But ~90 pre-existing call sites across this suite
    predate it and were never written to attach the header. Rather than
    hand-edit every one, this auto-attaches ``X-CSRF-Token`` from the
    ``rivet_csrf`` cookie (set by register/login) whenever the caller
    hasn't already set that header -- the real production check still
    runs on every request, comparing a real cookie against a real header,
    it's just populated automatically here instead of by hand.
    ``test_csrf.py`` overrides or omits the header explicitly to test
    rejection, which this only fills in when absent.
    """

    def request(self, method, url, *, headers=None, **kwargs):
        headers = dict(headers or {})
        if not any(k.lower() == "x-csrf-token" for k in headers) and "rivet_csrf" in self.cookies:
            headers["X-CSRF-Token"] = self.cookies["rivet_csrf"]
        return super().request(method, url, headers=headers, **kwargs)


@pytest.fixture
def client():
    return _AutoCsrfTestClient(create_app())


@pytest.fixture
def override_settings(monkeypatch):
    """Yields a function(**env_vars) that sets env vars and clears
    get_settings()'s LRU cache so the change is visible immediately.
    Clears the cache again on teardown (after monkeypatch has already
    restored the original env vars) so a later test re-reads real
    defaults instead of inheriting this test's cached Settings object --
    get_settings() is process-wide, not per-test.
    """
    from rivet_service.config import get_settings

    def _apply(**env_vars) -> None:
        for key, value in env_vars.items():
            monkeypatch.setenv(key, str(value))
        get_settings.cache_clear()

    yield _apply
    get_settings.cache_clear()


def redis_is_reachable() -> bool:
    try:
        from rivet_service.jobs.queue import get_redis_connection

        get_redis_connection().ping()
        return True
    except Exception:  # noqa: BLE001 -- any failure means "not reachable"
        return False


def minio_is_reachable() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:9000/minio/health/live", timeout=1) as resp:
            return resp.status == 200
    except Exception:  # noqa: BLE001 -- any failure means "not reachable"
        return False
