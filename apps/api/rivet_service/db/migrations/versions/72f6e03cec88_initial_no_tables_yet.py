"""initial (no tables yet)

Phase 6 (docs/prompts.md, docs/saas-buildout.md) is a FastAPI skeleton
only -- no auth or persistence functionality exists yet, so there is
nothing to create. This revision exists purely to prove the Alembic
harness works end to end (env.py connects, `alembic upgrade head`
succeeds, alembic_version gets stamped) and to give Phase 7 (users/orgs)
a real `down_revision` to chain onto, rather than every future phase's
first migration having to special-case `down_revision = None`.

Revision ID: 72f6e03cec88
Revises:
Create Date: 2026-08-13 11:06:06.454104

"""
from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = '72f6e03cec88'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
