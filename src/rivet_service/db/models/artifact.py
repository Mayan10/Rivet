from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("candidate_id", "kind", name="uq_artifact_candidate_kind"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(nullable=False)  # "png" | "svg" | "dxf"
    storage_key: Mapped[str] = mapped_column(nullable=False)  # uuid-based, never guessable/sequential
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(nullable=False)
    # Always False until Phase 9 (watermarking is a render parameter set
    # by the entitlement check, which doesn't exist yet).
    watermarked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
