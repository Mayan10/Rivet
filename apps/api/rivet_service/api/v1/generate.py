"""POST /api/v1/generate -- Phase 6's one ported endpoint.

Unauthenticated, synchronous, behaves like the existing Flask endpoint
(``rivet.api.routes``): no persistence, no quota, no job queue. Those
land in Phases 7-9; this is intentionally still the old shape, just
served by FastAPI. Reuses ``rivet.api.schemas.layout_to_dict`` for the
response body so the JSON shape doesn't drift between the two apps while
both are running (see docs/prompts.md Phase 6 status: Flask stays up
until FastAPI reaches parity).

No DXF download URL yet -- Phase 6 has no object storage or download
token concept (that's Phase 8), so ``dxf_url`` is always null here for
now; the candidate's SVG/PNG are still returned inline as before.

Phase 9: still unauthenticated, so no plan/quota to check against -- but
it does get the same universal, plan-independent safety ceilings
(api/validation.py) every generation request gets, authenticated or not.
"""

from __future__ import annotations

from fastapi import APIRouter

from rivet.api.schemas import infeasible_to_dict, layout_to_dict
from rivet.core.generator import generate
from rivet.core.models import InfeasibleResult

from ..errors import ApiError
from ..schemas import GenerateRequestIn, to_generation_request
from ..validation import enforce_absolute_ceilings

router = APIRouter(tags=["generate"])


@router.post("/generate")
def generate_endpoint(payload: GenerateRequestIn) -> dict:
    request = to_generation_request(payload)
    enforce_absolute_ceilings(request)
    result = generate(request)

    if isinstance(result, InfeasibleResult):
        raise ApiError(
            "infeasible_program",
            result.message,
            status_code=422,
            details=infeasible_to_dict(result),
        )

    return {"candidates": [layout_to_dict(layout, dxf_url=None) for layout in result]}
