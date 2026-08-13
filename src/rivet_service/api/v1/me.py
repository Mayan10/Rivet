"""GET /me (docs/saas-buildout.md section 9) and DELETE /me (section 11:
"account deletion actually deletes: rows, artifacts in object storage,
and the provider customer record").

DELETE /me does explicit, ordered deletion in one function -- not
DB-level ON DELETE CASCADE rules spread across migrations -- same
reasoning as generations.py's delete_generation: this needs to be
legible and debuggable in one place (CLAUDE.md), not implicit in schema.

Two shapes, decided up front, not guessed: if the requesting user is the
org's only member, the whole org cascades -- projects, generations (and
their storage artifacts), usage history, any Stripe subscription and
customer record, gone. If other members remain, only the requesting
user's own data is removed (their membership, sessions, API keys;
project/generation ``created_by`` attribution set to NULL) and the org
and teammates' data survive untouched. A sole owner with other members
still in the org is blocked (409) until ownership is transferred --
there's no transfer-ownership endpoint yet, so that edge case is
human-resolved for now, not a silent org deletion one teammate can
trigger for everyone else.
"""

from __future__ import annotations

import contextlib
import dataclasses

import stripe as stripe_sdk
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session as DbSession

from ...auth.csrf import CSRF_COOKIE_NAME
from ...auth.dependencies import RequestContext, require_context
from ...auth.sessions import SESSION_COOKIE_NAME
from ...billing.entitlements import entitlements_for, generations_used_this_period
from ...billing.stripe_client import cancel_subscription, delete_customer
from ...db.models import (
    ApiKey,
    Artifact,
    Candidate,
    Generation,
    Membership,
    MembershipRole,
    Project,
    Subscription,
    UsageEvent,
)
from ...db.models import Session as SessionModel
from ...db.session import get_db
from ...storage import get_storage_adapter
from ..errors import ApiError

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


def _delete_org_artifacts(db: DbSession, org_id) -> None:
    storage = get_storage_adapter()
    for generation in db.query(Generation).filter_by(org_id=org_id).all():
        for candidate in db.query(Candidate).filter_by(generation_id=generation.id).all():
            for artifact in db.query(Artifact).filter_by(candidate_id=candidate.id).all():
                storage.delete(artifact.storage_key)


@router.delete("/me")
def delete_account(
    response: Response, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    if context.user is None or context.org is None:
        raise ApiError("unauthorized", "Account deletion requires a signed-in user.", status_code=401)

    user, org = context.user, context.org
    memberships = db.query(Membership).filter_by(org_id=org.id).all()
    my_membership = next(m for m in memberships if m.user_id == user.id)
    other_members = [m for m in memberships if m.user_id != user.id]

    if other_members:
        if context.role == MembershipRole.OWNER.value and not any(
            m.role == MembershipRole.OWNER.value for m in other_members
        ):
            raise ApiError(
                "owner_transfer_required",
                "Transfer ownership to another member before deleting your account.",
                status_code=409,
            )

        db.query(ApiKey).filter_by(org_id=org.id, created_by=user.id).delete()
        db.query(Project).filter_by(org_id=org.id, created_by=user.id).update({"created_by": None})
        db.query(Generation).filter_by(org_id=org.id, created_by=user.id).update({"created_by": None})
        db.delete(my_membership)
        db.query(SessionModel).filter_by(user_id=user.id).delete()
        db.delete(user)
        db.commit()
    else:
        # Sole member -- the whole org goes. Stripe cleanup runs first,
        # before any DB row is touched, so a Stripe-side failure leaves
        # the database completely unchanged rather than half-deleted.
        for subscription in db.query(Subscription).filter_by(org_id=org.id).all():
            if subscription.status != "canceled":
                with contextlib.suppress(stripe_sdk.InvalidRequestError):
                    cancel_subscription(subscription.provider_subscription_id)
        if org.stripe_customer_id:
            delete_customer(org.stripe_customer_id)

        _delete_org_artifacts(db, org.id)

        db.query(Generation).filter_by(org_id=org.id).delete()  # cascades candidates/artifacts (ondelete=CASCADE)
        db.query(UsageEvent).filter_by(org_id=org.id).delete()
        db.query(Subscription).filter_by(org_id=org.id).delete()
        db.query(ApiKey).filter_by(org_id=org.id).delete()
        db.query(Project).filter_by(org_id=org.id).delete()
        db.delete(my_membership)
        db.query(SessionModel).filter_by(user_id=user.id).delete()
        db.delete(user)
        db.delete(org)
        db.commit()

    response.delete_cookie(SESSION_COOKIE_NAME)
    response.delete_cookie(CSRF_COOKIE_NAME)
    return {"status": "ok"}
