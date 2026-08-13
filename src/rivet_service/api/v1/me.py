"""GET /me (docs/saas-buildout.md section 9).

``plan``, ``entitlements``, and ``usage`` are explicitly null for now --
plans/entitlements don't exist until Phase 9 and usage tracking until
Phase 9 too. Every field the eventual response needs is already named
here (as null) so the frontend's shape doesn't change later, only the
values fill in.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.dependencies import RequestContext, require_context

router = APIRouter(tags=["me"])


@router.get("/me")
def me(context: RequestContext = Depends(require_context)) -> dict:
    return {
        "user": (
            {"id": str(context.user.id), "email": context.user.email, "email_verified": context.user.email_verified_at is not None}
            if context.user is not None
            else None
        ),
        "org": ({"id": str(context.org.id), "name": context.org.name} if context.org is not None else None),
        "role": context.role,
        "auth_method": context.auth_method,
        "plan": None,
        "entitlements": None,
        "usage_this_period": None,
    }
