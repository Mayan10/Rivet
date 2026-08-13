"""GET /me (docs/saas-buildout.md section 9)."""

from __future__ import annotations

import dataclasses

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from ...auth.dependencies import RequestContext, require_context
from ...billing.entitlements import entitlements_for, generations_used_this_period
from ...db.session import get_db

router = APIRouter(tags=["me"])


@router.get("/me")
def me(context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)) -> dict:
    entitlements = entitlements_for(db, context.org) if context.org is not None else None
    return {
        "user": (
            {"id": str(context.user.id), "email": context.user.email, "email_verified": context.user.email_verified_at is not None}
            if context.user is not None
            else None
        ),
        "org": ({"id": str(context.org.id), "name": context.org.name} if context.org is not None else None),
        "role": context.role,
        "auth_method": context.auth_method,
        "plan": context.org.plan_code if context.org is not None else None,
        "entitlements": dataclasses.asdict(entitlements) if entitlements is not None else None,
        "usage_this_period": (
            {"generations": generations_used_this_period(db, context.org.id)} if context.org is not None else None
        ),
    }
