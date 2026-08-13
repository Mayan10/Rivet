from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Candidate(Base):
    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("generation_id", "index", name="uq_candidate_generation_index"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    generation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False
    )
    # 1-based, matching the engine's own "candidate-1", "candidate-2", ...
    # Layout.candidate_id numbering.
    index: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    score_breakdown_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
