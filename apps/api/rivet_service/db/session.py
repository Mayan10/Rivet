"""Sync SQLAlchemy engine/session -- one style used identically by the
API and the (Phase 8) RQ workers, since RQ is inherently sync. See
docs/prompts.md's Phase 6 status block for why sync was chosen over
async SQLAlchemy.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings


def build_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or get_settings().database_url, pool_pre_ping=True)


_engine = build_engine()
SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, always closed after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def database_is_reachable(engine: Engine | None = None) -> bool:
    """Used by /readyz -- a real connectivity check, not just "the process
    is up" (that's /healthz).
    """
    try:
        with (engine or _engine).connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 -- a readiness probe must never itself crash on a driver/network error
        return False
