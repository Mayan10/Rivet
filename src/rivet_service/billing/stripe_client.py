"""Thin wrapper around the `stripe` SDK -- the only module in this
service that imports it. Everything else (routes, webhook dispatch)
talks to this module's functions, not to `stripe` directly, so a future
provider swap (Razorpay, if the entity/currency decision ever changes --
see docs/saas-buildout.md section 8) touches one file.

Uses the SDK's instance-based `StripeClient` (not the legacy global
`stripe.api_key = ...`), and the `.v1.` namespace specifically -- the
un-namespaced `client.checkout`/`client.billing_portal` accessors emit a
`DeprecationWarning` on every call in this SDK version.
"""

from __future__ import annotations

import stripe

from ..config import get_settings


class StripeNotConfigured(Exception):
    """Raised when a Stripe-backed route is hit without STRIPE_SECRET_KEY
    set -- lets the route translate this into a clear 503 rather than the
    SDK's own less-obvious error further down the call stack.
    """


def get_stripe_client() -> stripe.StripeClient:
    # Not cached, matching storage/get_storage_adapter() and
    # jobs/get_queue() -- rebuilt per call from current settings (cheap:
    # no connection is opened here) so tests can override env vars
    # without a stale client surviving across them.
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise StripeNotConfigured("STRIPE_SECRET_KEY is not set.")
    return stripe.StripeClient(api_key=settings.stripe_secret_key)


def create_checkout_session(*, customer_id: str | None, price_id: str, org_id: str) -> stripe.checkout.Session:
    """``customer_id`` is None on an org's very first checkout -- Stripe
    creates the customer implicitly in that case (and the caller reads it
    back off the returned session to persist as
    ``organizations.stripe_customer_id``, so every later call passes it).
    ``org_id`` goes in ``client_reference_id`` and subscription metadata
    so the webhook handler (which only sees the Stripe event, not this
    request) can find the org unambiguously even before a `subscriptions`
    row exists.
    """
    settings = get_settings()
    client = get_stripe_client()
    params: stripe.checkout.SessionCreateParams = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": settings.billing_checkout_success_url,
        "cancel_url": settings.billing_checkout_cancel_url,
        "client_reference_id": org_id,
        "subscription_data": {"metadata": {"org_id": org_id}},
    }
    if customer_id:
        params["customer"] = customer_id
    else:
        params["customer_creation"] = "always"
    return client.v1.checkout.sessions.create(params)


def create_portal_session(*, customer_id: str) -> stripe.billing_portal.Session:
    settings = get_settings()
    client = get_stripe_client()
    return client.v1.billing_portal.sessions.create(
        {"customer": customer_id, "return_url": settings.billing_portal_return_url}
    )


def cancel_subscription(subscription_id: str) -> None:
    get_stripe_client().v1.subscriptions.cancel(subscription_id)


def delete_customer(customer_id: str) -> None:
    get_stripe_client().v1.customers.delete(customer_id)


def construct_webhook_event(*, payload: bytes, signature_header: str) -> stripe.Event:
    """Raises ``stripe.SignatureVerificationError`` on a bad/missing
    signature -- the caller (api/v1/billing.py) turns that into a 400, not
    a 500, since it's a hostile/misconfigured request, not a bug.
    """
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise StripeNotConfigured("STRIPE_WEBHOOK_SECRET is not set.")
    return stripe.Webhook.construct_event(payload, signature_header, settings.stripe_webhook_secret)
