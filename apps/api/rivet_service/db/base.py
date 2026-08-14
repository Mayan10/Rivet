"""SQLAlchemy declarative base.

Empty of real tables in Phase 6 on purpose -- see docs/prompts.md's Phase
6 status block. Each later phase (7: users/orgs, 8: projects/generations,
9: plans, 10: subscriptions/billing_events) imports this ``Base`` and
adds its own models in its own migration, when that phase's code first
needs them.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
