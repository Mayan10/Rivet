"""Plan tier definitions -- the canonical reference for what each plan
means. The `plans` table's own migration inlines a literal copy of this
data as its seed (not an import of this module), since a migration
should stay correct forever even if this file changes later; edit both
together when tiers actually change, with a new migration.

max_plot_area_sqm/max_rooms aren't broken out per-tier in
docs/saas-buildout.md section 7's pricing table (only monthly
generations, candidates/request, PNG/SVG, DXF export, history, API keys,
seats are) -- all three tiers get the same absolute safety-ceiling
values (below) until real per-plan figures are decided. Those same
constants are also the universal, plan-independent ceilings
api/validation.py rejects at (section 7: "someone will POST a 500m x
500m plot ... should be rejected at validation, not discovered when your
worker OOMs") -- every plan's limit already equals the absolute ceiling
today, so there's currently no daylight between "exceeds your plan" and
"exceeds what's allowed at all" for plot size/room count, only for
candidates.
"""

from __future__ import annotations

DEFAULT_PLAN_CODE = "free"

ABSOLUTE_MAX_PLOT_AREA_SQM = 2500.0  # e.g. 50m x 50m -- generous for any real residential plot
ABSOLUTE_MAX_ROOMS = 30
ABSOLUTE_MAX_CANDIDATES = 10

PLAN_DEFINITIONS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "price_cents": 0,
        "currency": "usd",
        "limits": {
            "monthly_generations": 5,
            "max_candidates": 1,
            "max_plot_area_sqm": ABSOLUTE_MAX_PLOT_AREA_SQM,
            "max_rooms": ABSOLUTE_MAX_ROOMS,
            "dxf_export": False,
            "watermark_previews": True,
            "multi_storey": False,
            "api_access": False,
            "priority_queue": False,
            "history_retention_days": 7,
        },
    },
    "pro": {
        "name": "Pro",
        "price_cents": 2900,
        "currency": "usd",
        "limits": {
            "monthly_generations": 200,
            "max_candidates": 3,
            "max_plot_area_sqm": ABSOLUTE_MAX_PLOT_AREA_SQM,
            "max_rooms": ABSOLUTE_MAX_ROOMS,
            "dxf_export": True,
            "watermark_previews": False,
            "multi_storey": False,
            "api_access": False,
            "priority_queue": False,
            "history_retention_days": None,
        },
    },
    "studio": {
        "name": "Studio",
        "price_cents": 9900,
        "currency": "usd",
        "limits": {
            "monthly_generations": 1000,
            "max_candidates": 5,
            "max_plot_area_sqm": ABSOLUTE_MAX_PLOT_AREA_SQM,
            "max_rooms": ABSOLUTE_MAX_ROOMS,
            "dxf_export": True,
            "watermark_previews": False,
            "multi_storey": False,
            "api_access": True,
            "priority_queue": True,
            "history_retention_days": None,
        },
    },
}
