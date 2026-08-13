from __future__ import annotations

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Plan(Base):
    """Tier definitions (free/pro/studio), seeded by this table's own
    migration -- not by billing/plans.py at import time, so the DB stays
    the single source of truth an admin could edit without a deploy.
    ``limits`` mirrors billing.entitlements.Entitlements' fields; kept as
    jsonb (not a column per field) since the shape may grow before it's
    worth a migration for each new entitlement.
    """

    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(primary_key=True)  # "free" | "pro" | "studio"
    name: Mapped[str] = mapped_column(nullable=False)
    price_cents: Mapped[int] = mapped_column(nullable=False)
    currency: Mapped[str] = mapped_column(nullable=False, server_default="usd")
    provider_price_id: Mapped[str | None] = mapped_column()  # Stripe price id -- filled in Phase 10
    limits: Mapped[dict] = mapped_column(JSONB, nullable=False)
