"""Service-layer tests need the ``service`` extra installed and a real
Postgres to connect to (Phase 6 has no DB tables yet, but /readyz and the
session factory do real connections).

Both are optional and skip this whole directory cleanly (not a
collection error) when missing -- so a contributor who only ran
``pip install -e ".[dev]"`` (no ``service`` extra) or who simply has no
Postgres running still sees a fully green ``pytest -q`` at the repo root.
CI installs the ``service`` extra and sets DATABASE_URL against a real
Postgres service container, running ``alembic upgrade head`` before
pytest (an explicit release step, not done by these tests -- see
docs/saas-buildout.md "Ops"), so there this whole directory actually
runs.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://mayan@localhost:5432/rivet_test")

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


@pytest.fixture(autouse=True)
def _clean_auth_tables():
    """Phase 7 tables persist across test runs in the shared dev/CI
    Postgres (no per-test transaction rollback -- routes commit their own
    sessions), so wipe them before every test rather than relying on
    unique-per-test data to avoid collisions.
    """
    from rivet_service.db.session import SessionLocal

    db = SessionLocal()
    try:
        for table in ("sessions", "api_keys", "memberships", "organizations", "users"):
            db.execute(text(f"DELETE FROM {table}"))
        db.commit()
    finally:
        db.close()
    yield


@pytest.fixture
def client():
    return TestClient(create_app())
