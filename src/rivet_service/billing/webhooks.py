"""Webhook dispatch (saas-buildout.md section 8). The one place that
writes ``subscriptions``/``billing_events`` and syncs
``organizations.plan_code`` -- ``entitlements_for`` still reads
``organizations.plan_code`` directly (unchanged since Phase 9), so this
module's job is keeping that column in sync with what Stripe says is
true, never handing out access based on anything else (the post-checkout
redirect isn't trusted at all).

Listens to ``customer.subscription.{created,updated,deleted}`` only, not
``checkout.session.completed``. Stripe fires a `customer.subscription.*`
event immediately after a subscription-mode Checkout completes, and that
event already carries the full Subscription object (status, price,
period bounds) -- ``checkout.session.completed`` doesn't include those
without an extra API call to re-fetch the subscription, which is
avoidable complexity for no benefit here. `.deleted` reuses the same
upsert as `.created`/`.updated`: Stripe already sets ``status="canceled"``
on the object in a `.deleted` event, so there is nothing delete-specific
to do beyond that.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from ..db.models import BillingEvent, Organization, Plan, Subscription
from .plans import DEFAULT_PLAN_CODE

logger = logging.getLogger(__name__)

# Any other status (past_due, canceled, unpaid, incomplete,
# incomplete_expired, paused, ...) degrades to the free plan's limits
# rather than hard-locking the account (section 8) -- the subscription
# row itself keeps the real status for the UI to explain why.
_ENTITLED_STATUSES = frozenset({"trialing", "active"})


def _upsert_subscription(db: DbSession, sub: stripe.Subscription) -> None:
    # StripeObject only implements __getitem__, not Mapping's .get() --
    # converting once up front lets the rest of this function use plain
    # dict semantics instead of indexing everywhere.
    sub = sub.to_dict()
    org_id_raw = sub.get("metadata", {}).get("org_id")
    if not org_id_raw:
        logger.warning("subscription %s has no org_id in metadata, skipping", sub.get("id"))
        return

    org = db.get(Organization, uuid.UUID(org_id_raw))
    if org is None:
        logger.warning("subscription %s references unknown org %s, skipping", sub.get("id"), org_id_raw)
        return

    price_id = sub["items"]["data"][0]["price"]["id"]
    plan = db.query(Plan).filter_by(provider_price_id=price_id).first()
    if plan is None:
        # A genuine misconfiguration (a Stripe price with no matching
        # Plan.provider_price_id) -- raise rather than silently drop the
        # event. The BillingEvent insert that guards idempotency hasn't
        # been committed yet (see handle_webhook_event), so this rolls
        # back cleanly and Stripe's automatic webhook retry re-processes
        # it once the plan is fixed.
        raise RuntimeError(f"No plan configured for Stripe price {price_id!r} (Plan.provider_price_id).")

    record = db.query(Subscription).filter_by(provider_subscription_id=sub["id"]).first()
    if record is None:
        record = Subscription(
            org_id=org.id, provider="stripe", provider_subscription_id=sub["id"], provider_customer_id=sub["customer"]
        )
        db.add(record)

    record.provider_customer_id = sub["customer"]
    record.plan_code = plan.code
    record.status = sub["status"]
    record.current_period_start = datetime.fromtimestamp(sub["current_period_start"], tz=timezone.utc)
    record.current_period_end = datetime.fromtimestamp(sub["current_period_end"], tz=timezone.utc)
    record.cancel_at_period_end = sub["cancel_at_period_end"]

    org.stripe_customer_id = sub["customer"]
    org.plan_code = plan.code if sub["status"] in _ENTITLED_STATUSES else DEFAULT_PLAN_CODE


_HANDLERS: dict[str, Callable[[DbSession, stripe.StripeObject], None]] = {
    "customer.subscription.created": lambda db, event: _upsert_subscription(db, event["data"]["object"]),
    "customer.subscription.updated": lambda db, event: _upsert_subscription(db, event["data"]["object"]),
    "customer.subscription.deleted": lambda db, event: _upsert_subscription(db, event["data"]["object"]),
}


def handle_webhook_event(db: DbSession, event: stripe.Event) -> None:
    billing_event = BillingEvent(provider_event_id=event["id"], type=event["type"], payload=event.to_dict())
    db.add(billing_event)
    try:
        db.flush()
    except IntegrityError:
        # provider_event_id already recorded -- Stripe retried or
        # redelivered this event. Already processed; 200 and stop.
        db.rollback()
        return

    handler = _HANDLERS.get(event["type"])
    if handler is not None:
        handler(db, event)
    db.commit()
