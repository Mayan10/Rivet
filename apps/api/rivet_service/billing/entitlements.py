"""One function, one dataclass (docs/saas-buildout.md section 7).
Entitlements are read from the ``plans`` table (``Organization.plan_code``
-> ``Plan.limits``), never branched on in application code -- "limits
live here, not scattered through if plan == 'pro' branches."
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session as DbSession

from ..db.models import Organization, Plan, UsageEvent
from .plans import DEFAULT_PLAN_CODE


@dataclass(frozen=True)
class Entitlements:
    monthly_generations: int
    max_candidates: int
    max_plot_area_sqm: float
    max_rooms: int
    dxf_export: bool
    watermark_previews: bool
    multi_storey: bool
    api_access: bool
    priority_queue: bool
    history_retention_days: int | None  # None = unlimited


def entitlements_for(db: DbSession, org: Organization) -> Entitlements:
    plan = db.get(Plan, org.plan_code) or db.get(Plan, DEFAULT_PLAN_CODE)
    return Entitlements(**plan.limits)


def current_period_start() -> datetime:
    """No subscriptions table yet (Phase 10), so there's no real billing
    cycle to anchor to -- calendar month (UTC) until then.
    """
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def generations_used_this_period(db: DbSession, org_id: uuid.UUID) -> int:
    total = (
        db.query(func.coalesce(func.sum(UsageEvent.quantity), 0))
        .filter(
            UsageEvent.org_id == org_id,
            UsageEvent.kind == "generation",
            UsageEvent.occurred_at >= current_period_start(),
        )
        .scalar()
    )
    return int(total)
