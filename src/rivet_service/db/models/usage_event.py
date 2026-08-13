from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class UsageEvent(Base):
    """Append-only (saas-buildout.md section 4: "compute quota by summing
    over the current billing period rather than keeping a mutable
    counter"). One row per generation *request* (recorded at enqueue
    time, whether or not it goes on to succeed -- compute was consumed
    either way), plus one row per DXF download (kind="dxf_export",
    tracked for analytics parity with this schema; the actual DXF gate
    is Entitlements.dxf_export, a plan boolean, not a second quota).
    """

    __tablename__ = "usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    kind: Mapped[str] = mapped_column(nullable=False)  # "generation" | "dxf_export"
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    # SET NULL, not CASCADE: the ledger entry (and the quota it already
    # consumed) must survive a user deleting the generation it refers to.
    generation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generations.id", ondelete="SET NULL")
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
