"""subscriptions, billing_events, organizations.stripe_customer_id

Phase 10 (docs/prompts.md, docs/saas-buildout.md sections 4 & 8).
Constraint names are given explicitly throughout -- autogenerate leaves
them as `None`, which Postgres accepts on create but which then can't be
named in `downgrade()` (see Phase 9's migration, which hit this first).

Revision ID: 744cc09416ce
Revises: 973d9f8b6567
Create Date: 2026-08-13 17:55:39.114252

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '744cc09416ce'
down_revision: str | None = '973d9f8b6567'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "billing_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider_event_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_event_id", name="uq_billing_events_provider_event_id"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(), server_default="stripe", nullable=False),
        sa.Column("provider_customer_id", sa.String(), nullable=False),
        sa.Column("provider_subscription_id", sa.String(), nullable=False),
        sa.Column("plan_code", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], name="fk_subscriptions_org_id_organizations"),
        sa.ForeignKeyConstraint(["plan_code"], ["plans.code"], name="fk_subscriptions_plan_code_plans"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_subscription_id", name="uq_subscriptions_provider_subscription_id"),
    )
    op.add_column("organizations", sa.Column("stripe_customer_id", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_organizations_stripe_customer_id", "organizations", ["stripe_customer_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_organizations_stripe_customer_id", "organizations", type_="unique")
    op.drop_column("organizations", "stripe_customer_id")
    op.drop_table("subscriptions")
    op.drop_table("billing_events")
