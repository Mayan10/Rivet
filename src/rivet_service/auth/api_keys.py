"""API key generation and lookup (docs/saas-buildout.md section 5:
``Authorization: Bearer rvt_live_...``, hashed lookup). Not yet gated to
a paid tier -- entitlements don't exist until Phase 9; see
api/v1/api_keys.py.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from ..db.models import ApiKey

KEY_PREFIX = "rvt_live_"
_DISPLAY_PREFIX_LEN = 12  # e.g. "rvt_live_ab1" -- enough to tell keys apart, not enough to guess


def _hash_key(full_key: str) -> str:
    return hashlib.sha256(full_key.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class GeneratedApiKey:
    full_key: str  # shown to the caller exactly once
    prefix: str
    key_hash: str


def generate_api_key() -> GeneratedApiKey:
    full_key = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    return GeneratedApiKey(full_key=full_key, prefix=full_key[:_DISPLAY_PREFIX_LEN], key_hash=_hash_key(full_key))


def resolve_api_key(db: DbSession, full_key: str) -> ApiKey | None:
    row = db.query(ApiKey).filter_by(key_hash=_hash_key(full_key)).first()
    if row is None or row.revoked_at is not None:
        return None
    return row
