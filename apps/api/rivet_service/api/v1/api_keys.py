"""API key management (docs/saas-buildout.md sections 5 & 9).

Creation requires session auth specifically (not just any org-scoped
api-key auth): ``api_keys.created_by`` is a real user reference, and an
API key isn't itself tied to one. Listing/revoking only need an org, so
either auth method works for those. Creation is also gated to
Entitlements.api_access (Phase 9 -- carried forward from Phase 7, which
implemented the mechanism before entitlements existed to gate it with).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ...auth.api_keys import generate_api_key
from ...auth.dependencies import RequestContext, require_context
from ...billing.entitlements import entitlements_for
from ...db.models import ApiKey
from ...db.session import get_db
from ..errors import ApiError

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateApiKeyIn(BaseModel):
    name: str = Field(min_length=1)


def _key_dict(key: ApiKey) -> dict:
    return {
        "id": str(key.id),
        "name": key.name,
        "prefix": key.prefix,
        "created_at": key.created_at.isoformat(),
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "revoked_at": key.revoked_at.isoformat() if key.revoked_at else None,
    }


@router.get("")
def list_api_keys(context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)) -> dict:
    if context.org is None:
        raise ApiError("unauthorized", "No organization in context.", status_code=401)
    keys = db.query(ApiKey).filter_by(org_id=context.org.id).order_by(ApiKey.created_at).all()
    return {"api_keys": [_key_dict(k) for k in keys]}


@router.post("")
def create_api_key(
    payload: CreateApiKeyIn, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    if context.user is None or context.org is None:
        raise ApiError("unauthorized", "API keys can only be created by a signed-in user.", status_code=401)

    if not entitlements_for(db, context.org).api_access:
        raise ApiError("plan_required", "API keys are not included in your plan.", status_code=403)

    generated = generate_api_key()
    key = ApiKey(
        org_id=context.org.id,
        name=payload.name,
        prefix=generated.prefix,
        key_hash=generated.key_hash,
        created_by=context.user.id,
    )
    db.add(key)
    db.commit()

    # The only time the full key is ever available -- not retrievable again.
    return {**_key_dict(key), "key": generated.full_key}


@router.delete("/{key_id}")
def revoke_api_key(
    key_id: uuid.UUID, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    if context.org is None:
        raise ApiError("unauthorized", "No organization in context.", status_code=401)

    key = db.query(ApiKey).filter_by(id=key_id, org_id=context.org.id).first()
    if key is None:
        raise ApiError("not_found", "API key not found.", status_code=404)

    if key.revoked_at is None:
        key.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return {"status": "ok"}
