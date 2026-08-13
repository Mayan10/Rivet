from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Session(Base):
    """Not in docs/saas-buildout.md section 4's table list -- added in
    Phase 7 because section 5's session-cookie requirement needs
    somewhere to revoke against (POST /auth/logout, and password reset
    invalidating existing sessions). See docs/prompts.md Phase 7 status
    for the full reasoning.

    token_hash, not the raw token: the cookie carries the only copy of
    the actual bearer value (opaque, high-entropy, not signed -- see
    config.py's secret_key comment); this table only ever sees its hash,
    the same pattern api_keys already uses.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
