"""The single shared auth resolution point (docs/saas-buildout.md section
5: "Both resolve through one dependency ... Every route depends on that
and nothing else reads plan codes directly").

Returns ``(user_or_none, org_or_none, entitlements)`` per the spec --
except Entitlements doesn't exist until Phase 9, so ``RequestContext``
carries ``role`` (this request's membership role, if session-authenticated)
in its place for now. Phase 9 adds an `entitlements` field alongside it;
every route already goes through this one dependency, so that phase's
diff is additive here, not a call-site rewrite everywhere.

An unauthenticated request resolves to an all-None context rather than
raising -- routes that work anonymously (like /api/v1/generate) don't pay
an auth cost, and ``require_context`` below is the explicit opt-in for
routes that need a real user or org.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy.orm import Session as DbSession

from ..api.errors import ApiError
from ..db.models import Membership, Organization, User
from ..db.session import get_db
from .api_keys import resolve_api_key
from .sessions import SESSION_COOKIE_NAME, resolve_session


@dataclass(frozen=True)
class RequestContext:
    user: User | None
    org: Organization | None
    role: str | None  # membership role for session auth; None for api-key auth (org-scoped, not user-scoped)
    auth_method: str  # "session" | "api_key" | "none"


def resolve_org_for_user(db: DbSession, user: User) -> tuple[Organization | None, str | None]:
    # Every user starts solo (docs/saas-buildout.md section 4) and there's
    # no org-switching/invite flow anywhere in the phase plan yet, so the
    # first membership *is* the user's context for now.
    membership = db.query(Membership).filter_by(user_id=user.id).order_by(Membership.created_at).first()
    if membership is None:
        return None, None
    org = db.get(Organization, membership.org_id)
    return org, membership.role


def current_context(request: Request, db: DbSession = Depends(get_db)) -> RequestContext:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        api_key = resolve_api_key(db, auth_header.removeprefix("Bearer ").strip())
        if api_key is not None:
            api_key.last_used_at = datetime.now(timezone.utc)
            db.commit()
            org = db.get(Organization, api_key.org_id)
            return RequestContext(user=None, org=org, role=None, auth_method="api_key")

    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        user = resolve_session(db, token)
        if user is not None:
            org, role = resolve_org_for_user(db, user)
            return RequestContext(user=user, org=org, role=role, auth_method="session")

    return RequestContext(user=None, org=None, role=None, auth_method="none")


def require_context(context: RequestContext = Depends(current_context)) -> RequestContext:
    if context.auth_method == "none":
        raise ApiError("unauthorized", "Authentication required.", status_code=401)
    return context
