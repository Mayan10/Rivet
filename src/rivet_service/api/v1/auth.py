"""Auth endpoints (docs/saas-buildout.md section 9).

Email verification and password reset only log the token/link for now --
no email-sending provider is named anywhere in the 7-phase plan, and
picking one (SES, SendGrid, ...) is a distinct decision that doesn't
belong bundled into an auth-schema phase. See docs/prompts.md Phase 7
status. Tokens are deliberately never included in the HTTP response body
(only server-side logs) -- an API response is a worse leak surface than
an actual email would be.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ...auth.dependencies import resolve_org_for_user
from ...auth.passwords import hash_password, verify_password
from ...auth.sessions import (
    SESSION_COOKIE_NAME,
    create_session,
    revoke_all_sessions_for_user,
    revoke_session,
)
from ...auth.tokens import TokenError, generate_token, verify_token
from ...config import get_settings
from ...db.models import Membership, MembershipRole, Organization, User
from ...db.session import get_db
from ..errors import ApiError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: str
    password: str = Field(min_length=8)
    org_name: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


class VerifyEmailIn(BaseModel):
    token: str


class RequestPasswordResetIn(BaseModel):
    email: str


class ResetPasswordIn(BaseModel):
    token: str
    new_password: str = Field(min_length=8)


def _normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if "@" not in email or " " in email:
        raise ApiError("validation_failed", "Invalid email address.", details={"field": "email"})
    return email


def _user_dict(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "email_verified": user.email_verified_at is not None}


def _org_dict(org: Organization | None) -> dict | None:
    if org is None:
        return None
    return {"id": str(org.id), "name": org.name}


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 86400,
    )


@router.post("/register")
def register(payload: RegisterIn, response: Response, db: DbSession = Depends(get_db)) -> dict:
    email = _normalize_email(payload.email)
    if db.query(User).filter_by(email=email).first() is not None:
        raise ApiError("validation_failed", "An account with this email already exists.")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.flush()  # assign user.id before the org/membership rows reference it

    org = Organization(name=payload.org_name or f"{email}'s Organization")
    db.add(org)
    db.flush()

    db.add(Membership(user_id=user.id, org_id=org.id, role=MembershipRole.OWNER.value))
    db.commit()

    settings = get_settings()
    verify_token_value = generate_token(
        settings.secret_key,
        purpose="email_verify",
        user_id=str(user.id),
        ttl_seconds=settings.email_verification_token_ttl_hours * 3600,
    )
    logger.info("Email verification token for %s (no email provider configured): %s", email, verify_token_value)

    session_token = create_session(db, user.id, ttl_days=settings.session_ttl_days)
    _set_session_cookie(response, session_token)

    return {"user": _user_dict(user), "org": _org_dict(org)}


@router.post("/login")
def login(payload: LoginIn, response: Response, db: DbSession = Depends(get_db)) -> dict:
    email = _normalize_email(payload.email)
    user = db.query(User).filter_by(email=email).first()

    # Same error for "no such user" and "wrong password" -- section 5.
    if user is None or user.deleted_at is not None or not verify_password(payload.password, user.password_hash):
        raise ApiError("unauthorized", "Invalid email or password.", status_code=401)

    settings = get_settings()
    session_token = create_session(db, user.id, ttl_days=settings.session_ttl_days)
    _set_session_cookie(response, session_token)

    org, _role = resolve_org_for_user(db, user)
    return {"user": _user_dict(user), "org": _org_dict(org)}


@router.post("/logout")
def logout(request: Request, response: Response, db: DbSession = Depends(get_db)) -> dict:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        revoke_session(db, token)
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"status": "ok"}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailIn, db: DbSession = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        user_id = verify_token(settings.secret_key, payload.token, expected_purpose="email_verify")
        user = db.get(User, uuid.UUID(user_id))
    except (TokenError, ValueError) as exc:
        raise ApiError("validation_failed", "Invalid or expired token.") from exc
    if user is None:
        raise ApiError("validation_failed", "Invalid or expired token.")

    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"status": "ok"}


@router.post("/request-password-reset")
def request_password_reset(payload: RequestPasswordResetIn, db: DbSession = Depends(get_db)) -> dict:
    email = _normalize_email(payload.email)
    user = db.query(User).filter_by(email=email).first()
    if user is not None:
        settings = get_settings()
        reset_token = generate_token(
            settings.secret_key,
            purpose="password_reset",
            user_id=str(user.id),
            ttl_seconds=settings.password_reset_token_ttl_hours * 3600,
        )
        logger.info("Password reset token for %s (no email provider configured): %s", email, reset_token)

    # Always 200, regardless of whether the account exists -- section 5's
    # "do not distinguish no-such-user from wrong-password" logic applies
    # here too, otherwise this endpoint becomes an email-enumeration oracle.
    return {"status": "ok"}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordIn, db: DbSession = Depends(get_db)) -> dict:
    settings = get_settings()
    try:
        user_id = verify_token(settings.secret_key, payload.token, expected_purpose="password_reset")
        user = db.get(User, uuid.UUID(user_id))
    except (TokenError, ValueError) as exc:
        raise ApiError("validation_failed", "Invalid or expired token.") from exc
    if user is None:
        raise ApiError("validation_failed", "Invalid or expired token.")

    user.password_hash = hash_password(payload.new_password)
    db.commit()
    revoke_all_sessions_for_user(db, user.id)  # a reset invalidates every existing session, not just this request's
    return {"status": "ok"}
