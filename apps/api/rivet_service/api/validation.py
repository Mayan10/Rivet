"""Two of the three enforcement points section 7 names (the third, the
download handler's DXF gate, lives in api/v1/generations.py since it has
nothing to do with request validation).

- ``enforce_absolute_ceilings``: universal, plan-independent limits.
  Applies to *every* generation request, authenticated or not (used by
  both /api/v1/generate and /projects/{id}/generations) -- protects the
  worker from a pathological request regardless of who's asking.
- ``clamp_to_entitlements``: plan-specific, only for the authenticated
  flow. ``num_candidates`` is silently reduced to the plan's limit (a
  graceful degradation -- fewer results, not a rejection); plot area and
  room count over the plan's limit are rejected instead, since silently
  shrinking someone's plot would change their request into something
  they didn't ask for, not just reduce it.
"""

from __future__ import annotations

import dataclasses

from rivet.core.models import GenerationRequest

from ..billing.entitlements import Entitlements
from ..billing.plans import ABSOLUTE_MAX_CANDIDATES, ABSOLUTE_MAX_PLOT_AREA_SQM, ABSOLUTE_MAX_ROOMS
from .errors import ApiError


def enforce_absolute_ceilings(request: GenerationRequest) -> None:
    if request.plot.area_sqm > ABSOLUTE_MAX_PLOT_AREA_SQM:
        raise ApiError(
            "validation_failed", f"Plot area exceeds the maximum of {ABSOLUTE_MAX_PLOT_AREA_SQM:.0f} sqm."
        )
    total_rooms = sum(r.count for r in request.rooms)
    if total_rooms > ABSOLUTE_MAX_ROOMS:
        raise ApiError("validation_failed", f"Total room count exceeds the maximum of {ABSOLUTE_MAX_ROOMS}.")
    if request.num_candidates > ABSOLUTE_MAX_CANDIDATES:
        raise ApiError("validation_failed", f"'num_candidates' exceeds the maximum of {ABSOLUTE_MAX_CANDIDATES}.")


def clamp_to_entitlements(request: GenerationRequest, entitlements: Entitlements) -> GenerationRequest:
    if request.plot.area_sqm > entitlements.max_plot_area_sqm:
        raise ApiError("plan_required", "Your plan doesn't allow a plot this large.", status_code=403)

    total_rooms = sum(r.count for r in request.rooms)
    if total_rooms > entitlements.max_rooms:
        raise ApiError("plan_required", "Your plan doesn't allow this many rooms.", status_code=403)

    if request.num_candidates <= entitlements.max_candidates:
        return request
    return dataclasses.replace(request, num_candidates=entitlements.max_candidates)
