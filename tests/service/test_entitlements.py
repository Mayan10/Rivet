"""Unit coverage for billing/entitlements.py that doesn't fit naturally
under a route test -- period boundaries and plan-lookup fallback aren't
easily exercised through the API alone.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from rivet_service.billing.entitlements import (
    current_period_start,
    entitlements_for,
    generations_used_this_period,
)
from rivet_service.db.models import Organization, UsageEvent
from rivet_service.db.session import SessionLocal

VALID_REGISTER = {"email": "entitlements-test@example.com", "password": "hunter22222", "accept_tos": True}


def _register_org(client) -> uuid.UUID:
    res = client.post("/api/v1/auth/register", json=VALID_REGISTER)
    return uuid.UUID(res.json()["org"]["id"])


def test_entitlements_for_returns_free_plan_defaults(client):
    org_id = _register_org(client)
    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        entitlements = entitlements_for(db, org)
    finally:
        db.close()

    assert entitlements.monthly_generations == 5
    assert entitlements.max_candidates == 1
    assert entitlements.dxf_export is False
    assert entitlements.watermark_previews is True
    assert entitlements.api_access is False


def test_entitlements_for_reflects_upgraded_plan(client):
    org_id = _register_org(client)
    db = SessionLocal()
    try:
        org = db.get(Organization, org_id)
        org.plan_code = "studio"
        db.commit()
        entitlements = entitlements_for(db, org)
    finally:
        db.close()

    assert entitlements.monthly_generations == 1000
    assert entitlements.max_candidates == 5
    assert entitlements.dxf_export is True
    assert entitlements.watermark_previews is False
    assert entitlements.api_access is True


def test_current_period_start_is_first_of_month_utc():
    period_start = current_period_start()
    assert period_start.day == 1
    assert period_start.hour == 0
    assert period_start.minute == 0
    assert period_start.tzinfo is not None


def test_generations_used_this_period_only_counts_current_period(client):
    org_id = _register_org(client)
    db = SessionLocal()
    try:
        db.add(UsageEvent(org_id=org_id, kind="generation", quantity=1))
        db.add(UsageEvent(org_id=org_id, kind="generation", quantity=1))
        # Predates the current billing period -- shouldn't count.
        stale = UsageEvent(org_id=org_id, kind="generation", quantity=1)
        db.add(stale)
        db.flush()
        stale.occurred_at = current_period_start() - timedelta(days=1)
        # A dxf_export event shouldn't count toward generation quota either.
        db.add(UsageEvent(org_id=org_id, kind="dxf_export", quantity=1))
        db.commit()

        used = generations_used_this_period(db, org_id)
    finally:
        db.close()

    assert used == 2
