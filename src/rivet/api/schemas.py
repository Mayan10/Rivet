"""JSON <-> core model translation and request validation for the API."""

from __future__ import annotations

import base64

from ..core.metrics import LayoutMetrics, compute_metrics
from ..core.models import (
    GenerationRequest,
    InfeasibleResult,
    Layout,
    Orientation,
    PlotSpec,
    RoomRequirement,
    RoomType,
    Ruleset,
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
        num_floors = int(plot_payload.get("num_floors", 1))
        road_width_raw = plot_payload.get("abutting_road_width_m")
        road_width_m = float(road_width_raw) if road_width_raw is not None else None
        height_raw = plot_payload.get("proposed_height_m")
        height_m = float(height_raw) if height_raw is not None else None
    except (TypeError, ValueError) as exc:
        raise RequestValidationError(
            "'plot.num_floors', 'plot.abutting_road_width_m', and 'plot.proposed_height_m' must be numbers"
        ) from exc

    try:
        plot = PlotSpec(
            width_m=width_m,
            length_m=length_m,
            entrance=entrance,
            num_floors=num_floors,
            abutting_road_width_m=road_width_m,
            proposed_height_m=height_m,
        )
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

    ruleset_str = payload.get("ruleset", Ruleset.TNCDBR_2019.value)
    try:
        ruleset = Ruleset(str(ruleset_str).lower())
    except ValueError as exc:
        valid = ", ".join(r.value for r in Ruleset)
        raise RequestValidationError(f"'ruleset' must be one of: {valid}") from exc

    try:
        return GenerationRequest(
            plot=plot, rooms=rooms, num_candidates=num_candidates, seed=seed, ruleset=ruleset
        )
    except ValueError as exc:
        raise RequestValidationError(str(exc)) from exc


def _setback_to_dict(s) -> dict:
    return {"face": s.face, "required_m": round(s.required_m, 3), "provided_m": round(s.provided_m, 3), "compliant": s.compliant}


def _opening_row_to_dict(row) -> dict:
    return {
        "tag": row.tag,
        "kind": row.kind,
        "width_m": row.width_m,
        "height_m": row.height_m,
        "count": row.count,
        "total_area_sqm": round(row.total_area_sqm, 2),
    }


def metrics_to_dict(metrics: LayoutMetrics) -> dict:
    return {
        "gross_area_sqm": round(metrics.gross_area_sqm, 2),
        "total_carpet_area_sqm": round(metrics.total_carpet_area_sqm, 2),
        "total_built_up_area_sqm": round(metrics.total_built_up_area_sqm, 2),
        "total_plinth_area_sqm": round(metrics.total_plinth_area_sqm, 2),
        "circulation_area_sqm": round(metrics.circulation_area_sqm, 2),
        "circulation_pct_of_built_up": round(metrics.circulation_pct_of_built_up, 1),
        "ground_coverage_pct": round(metrics.ground_coverage_pct, 1),
        "fsi_consumed": round(metrics.fsi_consumed, 3),
        "fsi_permitted": metrics.fsi_permitted,
        "fsi_permitted_citation": metrics.fsi_permitted_citation,
        "setbacks": [_setback_to_dict(s) for s in metrics.setbacks],
        "door_schedule": [_opening_row_to_dict(r) for r in metrics.door_schedule],
        "window_schedule": [_opening_row_to_dict(r) for r in metrics.window_schedule],
        "quantity_takeoff": {
            "exterior_wall_length_m": round(metrics.quantity_takeoff.exterior_wall_length_m, 2),
            "interior_wall_length_m": round(metrics.quantity_takeoff.interior_wall_length_m, 2),
            "plaster_area_sqm": round(metrics.quantity_takeoff.plaster_area_sqm, 2),
            "block_count_estimate": metrics.quantity_takeoff.block_count_estimate,
            "floor_finish_area_by_room_sqm": {
                k: round(v, 2) for k, v in metrics.quantity_takeoff.floor_finish_area_by_room_sqm.items()
            },
        },
        "rooms": [
            {
                "room_id": r.room_id,
                "is_habitable": r.is_habitable,
                "carpet_area_sqm": round(r.carpet_area_sqm, 2),
                "window_opening_area_sqm": (
                    round(r.window_opening_area_sqm, 2) if r.window_opening_area_sqm is not None else None
                ),
                "required_ventilation_area_sqm": (
                    round(r.required_ventilation_area_sqm, 2) if r.required_ventilation_area_sqm is not None else None
                ),
                "ventilation_ratio_actual": (
                    round(r.ventilation_ratio_actual, 3) if r.ventilation_ratio_actual is not None else None
                ),
                "ventilation_passes": r.ventilation_passes,
            }
            for r in metrics.rooms
        ],
    }


def layout_to_dict(layout: Layout, *, dxf_url: str | None = None) -> dict:
    metrics = compute_metrics(layout, layout.ruleset)
    carpet_by_room = {r.room_id: r.carpet_area_sqm for r in metrics.rooms}

    return {
        "candidate_id": layout.candidate_id,
        "score": layout.score,
        "score_breakdown": layout.score_breakdown,
        "violations": layout.violations,
        "gross_area_sqm": round(metrics.gross_area_sqm, 2),
        "metrics": metrics_to_dict(metrics),
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
                "carpet_area_sqm": round(carpet_by_room[r.id], 2),
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


def infeasible_to_dict(result: InfeasibleResult) -> dict:
    return {
        "message": result.message,
        "violations": [
            {
                "constraint_id": v.constraint_id,
                "severity": v.severity,
                "room_id": v.room_id,
                "message": v.message,
                "actual": v.actual,
                "required": v.required,
                "source": v.source,
            }
            for v in result.hardest_violations
        ],
    }
