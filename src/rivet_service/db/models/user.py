from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # citext: email lookups (login, uniqueness) must be case-insensitive --
    # Foo@x.com and foo@x.com are the same account. Requires the citext
    # extension, created by this table's migration.
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Phase 11: recorded at registration (required -- see api/v1/auth.py's
    # RegisterIn.accept_tos). tos_version is a free-text snapshot of
    # whatever config.Settings.tos_version was at acceptance time, not a
    # foreign key to a documents table -- there's no such table, and
    # re-prompting existing users when the version bumps isn't built yet
    # (see docs/saas-buildout.md section 12).
    tos_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tos_version: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
