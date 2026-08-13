"""Signed, expiring tokens.

Originally built for email verification and password reset
(docs/saas-buildout.md section 5) and reused as-is in Phase 8 for
signed local-storage download links (storage/local.py) -- both are the
same shape: "prove you're allowed to act on this subject, before this
expiry, without a server-side record backing the token itself." Hand-
rolled HMAC rather than a new dependency (itsdangerous does the same
thing, but this is a small, well-understood pattern -- see
docs/prompts.md Phase 7 status).

Stateless by design: no DB row backs these, unlike sessions
(auth/sessions.py) or API keys. Anyone holding a valid token can act
without a pre-existing server-side record -- that's the whole point of
"signed, expiring" rather than "looked up."
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time


class TokenError(ValueError):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


def generate_token(secret_key: str, *, purpose: str, subject: str, ttl_seconds: int) -> str:
    payload = {"purpose": purpose, "subject": subject, "exp": int(time.time()) + ttl_seconds}
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return f"{_b64encode(payload_bytes)}.{_b64encode(signature)}"


def verify_token(secret_key: str, token: str, *, expected_purpose: str) -> str:
    """Returns the subject encoded in the token, or raises TokenError."""
    try:
        payload_b64, signature_b64 = token.split(".", 1)
        payload_bytes = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
    except Exception as exc:
        raise TokenError("Malformed token") from exc

    expected_signature = hmac.new(secret_key.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected_signature):
        raise TokenError("Invalid token signature")

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise TokenError("Malformed token payload") from exc

    if payload.get("purpose") != expected_purpose:
        raise TokenError("Token is not valid for this purpose")
    if payload.get("exp", 0) < time.time():
        raise TokenError("Token has expired")

    subject = payload.get("subject")
    if not subject:
        raise TokenError("Malformed token payload")
    return subject
