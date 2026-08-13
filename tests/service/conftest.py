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
    "generations",
    "projects",
    "sessions",
    "api_keys",
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


@pytest.fixture
def client():
    return TestClient(create_app())


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
