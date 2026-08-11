"""JSON <-> core model translation and request validation for the API."""

from __future__ import annotations

import base64

from ..core.models import (
    GenerationRequest,
    Layout,
    Orientation,
    PlotSpec,
    RoomRequirement,
    RoomType,
)
from ..render.raster import render_png_bytes
from ..render.svg import render_svg


class RequestValidationError(ValueError):
    """Raised when an incoming JSON payload can't be turned into a GenerationRequest."""


def parse_generation_request(payload: object) -> GenerationRequest:
    if not isinstance(payload, dict):
        raise RequestValidationError("Request body must be a JSON object")

    plot_payload = payload.get("plot")
    if not isinstance(plot_payload, dict):
        raise RequestValidationError("'plot' is required and must be an object")

    try:
        width_m = float(plot_payload["width_m"])
        length_m = float(plot_payload["length_m"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RequestValidationError("'plot.width_m' and 'plot.length_m' are required numbers") from exc

    entrance_str = plot_payload.get("entrance", "north")
    try:
        entrance = Orientation(str(entrance_str).lower())
    except ValueError as exc:
        valid = ", ".join(o.value for o in Orientation)
        raise RequestValidationError(f"'plot.entrance' must be one of: {valid}") from exc

    try:
        plot = PlotSpec(width_m=width_m, length_m=length_m, entrance=entrance)
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc

    rooms_payload = payload.get("rooms")
    if not isinstance(rooms_payload, list) or not rooms_payload:
        raise RequestValidationError("'rooms' is required and must be a non-empty array")

    rooms: list[RoomRequirement] = []
    for i, item in enumerate(rooms_payload):
        if not isinstance(item, dict):
            raise RequestValidationError(f"rooms[{i}] must be an object")

        type_str = item.get("room_type")
        try:
            room_type = RoomType(str(type_str).lower())
        except ValueError as exc:
            valid = ", ".join(t.value for t in RoomType)
            raise RequestValidationError(f"rooms[{i}].room_type '{type_str}' is invalid. Valid: {valid}") from exc

        try:
            target_area = item.get("target_area_sqm")
            rooms.append(
                RoomRequirement(
                    room_type=room_type,
                    count=int(item.get("count", 1)),
                    target_area_sqm=(float(target_area) if target_area is not None else None),
                    attached_bathroom=bool(item.get("attached_bathroom", False)),
                    label=item.get("label"),
                )
            )
        except (TypeError, ValueError) as exc:
            raise RequestValidationError(f"rooms[{i}] has an invalid field: {exc}") from exc

    try:
        num_candidates = int(payload.get("num_candidates", 3))
    except (TypeError, ValueError) as exc:
        raise RequestValidationError("'num_candidates' must be an integer") from exc

    seed_raw = payload.get("seed")
    try:
        seed = int(seed_raw) if seed_raw is not None else None
    except (TypeError, ValueError) as exc:
        raise RequestValidationError("'seed' must be an integer") from exc

    try:
        return GenerationRequest(plot=plot, rooms=rooms, num_candidates=num_candidates, seed=seed)
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc


def layout_to_dict(layout: Layout, *, dxf_url: str | None = None) -> dict:
    return {
        "candidate_id": layout.candidate_id,
        "score": layout.score,
        "score_breakdown": layout.score_breakdown,
        "violations": layout.violations,
        "gross_area_sqm": round(sum(r.rect.area for r in layout.rooms), 2),
        "rooms": [
            {
                "id": r.id,
                "room_type": r.room_type.value,
                "label": r.label,
                "x": round(r.rect.x, 3),
                "y": round(r.rect.y, 3),
                "width": round(r.rect.w, 3),
                "height": round(r.rect.h, 3),
                "area_sqm": round(r.rect.area, 2),
            }
            for r in layout.rooms
        ],
        "openings": [
            {
                "kind": o.kind,
                "x": round(o.x, 3),
                "y": round(o.y, 3),
                "width": round(o.width, 3),
                "axis": o.axis,
                "room_id": o.room_id,
                "connects_to": o.connects_to,
            }
            for o in layout.openings
        ],
        "svg": render_svg(layout),
        "png_base64": base64.b64encode(render_png_bytes(layout)).decode("ascii"),
        "dxf_url": dxf_url,
    }
