"""DB-backed sessions (see docs/prompts.md Phase 7 status for why: a
signed stateless cookie can't be truly revoked, which POST /auth/logout
and password-reset-invalidates-existing-sessions both need).

The cookie value is a high-entropy opaque token (``secrets.token_urlsafe``),
never signed -- only its SHA-256 hash is stored, mirroring how
``auth/api_keys.py`` handles API keys.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session as DbSession

from ..db.models import Session as SessionModel
from ..db.models import User

SESSION_COOKIE_NAME = "rivet_session"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: DbSession, user_id: uuid.UUID, *, ttl_days: int) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        SessionModel(
            user_id=user_id,
            token_hash=_hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=ttl_days),
        )
    )
    db.commit()
    return token


def resolve_session(db: DbSession, token: str) -> User | None:
    row = db.query(SessionModel).filter_by(token_hash=_hash_token(token)).first()
    if row is None or row.revoked_at is not None or row.expires_at < datetime.now(timezone.utc):
        return None
    return db.get(User, row.user_id)


def revoke_session(db: DbSession, token: str) -> None:
    row = db.query(SessionModel).filter_by(token_hash=_hash_token(token)).first()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()


def revoke_all_sessions_for_user(db: DbSession, user_id: uuid.UUID) -> None:
    """Called on password reset -- a reset should invalidate every
    existing session, not just the one that requested it.
    """
    now = datetime.now(timezone.utc)
    db.query(SessionModel).filter(
        SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None)
    ).update({"revoked_at": now})
    db.commit()
