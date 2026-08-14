from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class GenerationStatus(str, PyEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class Generation(Base):
    __tablename__ = "generations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(nullable=False)
    # The exact validated request payload -- combined with `seed` (also in
    # here, pulled out as its own column for queryability) and the two
    # version columns below, this is what "make determinism a product
    # feature" (saas-buildout.md section 4) means: any historical
    # generation can be regenerated on demand from these four fields.
    request_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer)
    engine_version: Mapped[int] = mapped_column(Integer, nullable=False)
    rulebook_version: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None]
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
