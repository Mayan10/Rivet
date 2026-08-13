"""Checkout/portal session creation and the Stripe webhook receiver
(docs/saas-buildout.md sections 8 & 9). Checkout/portal require session
auth specifically, same reasoning as api_keys.py's key-creation route:
these are account-level actions on behalf of a real signed-in person, not
something an org-scoped API key alone should be able to trigger.

The webhook route is deliberately outside ``require_context`` -- Stripe
isn't a signed-in user, and its own signature check (in
billing/stripe_client.py) is the only authentication that route has or
needs.
"""

from __future__ import annotations

import stripe as stripe_sdk
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from ...auth.csrf import enforce_csrf
from ...auth.dependencies import RequestContext, require_context
from ...billing.stripe_client import (
    StripeNotConfigured,
    construct_webhook_event,
    create_checkout_session,
    create_portal_session,
)
from ...billing.webhooks import handle_webhook_event
from ...db.models import Plan
from ...db.session import get_db
from ...rate_limit import enforce_rate_limit
from ..errors import ApiError

router = APIRouter(tags=["billing"])
_guarded = [Depends(enforce_rate_limit), Depends(enforce_csrf)]


class CheckoutSessionIn(BaseModel):
    plan_code: str


def _require_user_org(context: RequestContext) -> None:
    if context.user is None or context.org is None:
        raise ApiError("unauthorized", "Billing actions require a signed-in user.", status_code=401)


@router.post("/billing/checkout-session", dependencies=_guarded)
def checkout_session(
    payload: CheckoutSessionIn, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    _require_user_org(context)

    plan = db.get(Plan, payload.plan_code)
    if plan is None or plan.provider_price_id is None:
        raise ApiError("validation_failed", f"Plan '{payload.plan_code}' is not available for purchase.")

    try:
        session = create_checkout_session(
            customer_id=context.org.stripe_customer_id, price_id=plan.provider_price_id, org_id=str(context.org.id)
        )
    except StripeNotConfigured as exc:
        raise ApiError("service_unavailable", "Billing is not configured.", status_code=503) from exc

    if context.org.stripe_customer_id is None:
        # Persisted immediately (not left to wait for a subscription
        # webhook), so an abandoned-then-retried checkout reuses the same
        # Stripe customer instead of creating a new one each time.
        context.org.stripe_customer_id = session.customer
        db.commit()

    return {"checkout_url": session.url}


@router.post("/billing/portal-session", dependencies=_guarded)
def portal_session(context: RequestContext = Depends(require_context)) -> dict:
    _require_user_org(context)

    if context.org.stripe_customer_id is None:
        raise ApiError("validation_failed", "No billing account exists for this organization yet.")

    try:
        session = create_portal_session(customer_id=context.org.stripe_customer_id)
    except StripeNotConfigured as exc:
        raise ApiError("service_unavailable", "Billing is not configured.", status_code=503) from exc

    return {"portal_url": session.url}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: DbSession = Depends(get_db)) -> dict:
    payload = await request.body()
    signature_header = request.headers.get("stripe-signature", "")

    try:
        event = construct_webhook_event(payload=payload, signature_header=signature_header)
    except StripeNotConfigured as exc:
        raise ApiError("service_unavailable", "Billing is not configured.", status_code=503) from exc
    except stripe_sdk.SignatureVerificationError as exc:
        raise ApiError("validation_failed", "Invalid webhook signature.") from exc

    handle_webhook_event(db, event)
    return {"status": "ok"}
