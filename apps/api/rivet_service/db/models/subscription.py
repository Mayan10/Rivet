from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Subscription(Base):
    """One row per org's billing relationship with the provider (Stripe).
    Written only from billing/webhooks.py -- webhooks are the source of
    truth (saas-buildout.md section 8), never the post-checkout redirect.

    ``status`` mirrors Stripe's subscription status strings verbatim
    (trialing/active/past_due/canceled/unpaid/...) rather than a narrower
    enum, since new statuses Stripe adds later should still be recorded
    faithfully instead of raising on an unrecognized value.
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    provider: Mapped[str] = mapped_column(nullable=False, server_default="stripe")
    provider_customer_id: Mapped[str] = mapped_column(nullable=False)
    provider_subscription_id: Mapped[str] = mapped_column(nullable=False, unique=True)
    plan_code: Mapped[str] = mapped_column(ForeignKey("plans.code"), nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
