"""users.tos_accepted_at, users.tos_version

Phase 11 (docs/prompts.md, docs/saas-buildout.md section 12). Nullable --
existing rows (there are none in production yet, but the column can't
retroactively know when a pre-Phase-11 user "accepted" anything) predate
acceptance tracking entirely. New registrations always populate both
(see api/v1/auth.py's RegisterIn.accept_tos).

Revision ID: 2babde093fcb
Revises: 744cc09416ce
Create Date: 2026-08-13 20:15:47.536134

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2babde093fcb'
down_revision: str | None = '744cc09416ce'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tos_accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("tos_version", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "tos_version")
    op.drop_column("users", "tos_accepted_at")
