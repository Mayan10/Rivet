"""plans, usage_events, organizations.plan_code

Phase 9 (docs/prompts.md, docs/saas-buildout.md sections 4 & 7). Seeds
the three tiers literally (not imported from billing/plans.py) so this
migration stays correct forever even if that module's definitions change
later -- see billing/plans.py's own docstring. Every org defaults to
"free" (server_default) until Phase 10's real subscription sync exists.

Revision ID: 973d9f8b6567
Revises: 0c23fba685f5
Create Date: 2026-08-13 17:23:38.814049

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '973d9f8b6567'
down_revision: str | None = '0c23fba685f5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ABSOLUTE_MAX_PLOT_AREA_SQM = 2500.0
_ABSOLUTE_MAX_ROOMS = 30

_PLANS = [
    {
        "code": "free",
        "name": "Free",
        "price_cents": 0,
        "currency": "usd",
        "limits": {
            "monthly_generations": 5,
            "max_candidates": 1,
            "max_plot_area_sqm": _ABSOLUTE_MAX_PLOT_AREA_SQM,
            "max_rooms": _ABSOLUTE_MAX_ROOMS,
            "dxf_export": False,
            "watermark_previews": True,
            "multi_storey": False,
            "api_access": False,
            "priority_queue": False,
            "history_retention_days": 7,
        },
    },
    {
        "code": "pro",
        "name": "Pro",
        "price_cents": 2900,
        "currency": "usd",
        "limits": {
            "monthly_generations": 200,
            "max_candidates": 3,
            "max_plot_area_sqm": _ABSOLUTE_MAX_PLOT_AREA_SQM,
            "max_rooms": _ABSOLUTE_MAX_ROOMS,
            "dxf_export": True,
            "watermark_previews": False,
            "multi_storey": False,
            "api_access": False,
            "priority_queue": False,
            "history_retention_days": None,
        },
    },
    {
        "code": "studio",
        "name": "Studio",
        "price_cents": 9900,
        "currency": "usd",
        "limits": {
            "monthly_generations": 1000,
            "max_candidates": 5,
            "max_plot_area_sqm": _ABSOLUTE_MAX_PLOT_AREA_SQM,
            "max_rooms": _ABSOLUTE_MAX_ROOMS,
            "dxf_export": True,
            "watermark_previews": False,
            "multi_storey": False,
            "api_access": True,
            "priority_queue": True,
            "history_retention_days": None,
        },
    },
]

_PLANS_TABLE = sa.table(
    "plans",
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("price_cents", sa.Integer),
    sa.column("currency", sa.String),
    sa.column("limits", postgresql.JSONB),
)


def upgrade() -> None:
    op.create_table(
        "plans",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), server_default="usd", nullable=False),
        sa.Column("provider_price_id", sa.String(), nullable=True),
        sa.Column("limits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "usage_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("generation_id", sa.UUID(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["generation_id"],
            ["generations.id"],
            name="fk_usage_events_generation_id_generations",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.bulk_insert(
        _PLANS_TABLE,
        [
            {
                "code": p["code"],
                "name": p["name"],
                "price_cents": p["price_cents"],
                "currency": p["currency"],
                "limits": p["limits"],  # JSONB column: pass the dict itself, not a pre-serialized string
            }
            for p in _PLANS
        ],
    )

    op.add_column("organizations", sa.Column("plan_code", sa.String(), server_default="free", nullable=False))
    op.create_foreign_key("fk_organizations_plan_code_plans", "organizations", "plans", ["plan_code"], ["code"])


def downgrade() -> None:
    op.drop_constraint("fk_organizations_plan_code_plans", "organizations", type_="foreignkey")
    op.drop_column("organizations", "plan_code")
    op.drop_table("usage_events")
    op.drop_table("plans")
