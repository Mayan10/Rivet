"""Pydantic request models for the service API.

FastAPI/Pydantic validate the wire format; conversion into the engine's
own ``GenerationRequest`` dataclasses (and back out again for the
response) reuses ``rivet.api.schemas`` -- the JSON shape and behavior for
this endpoint is meant to match the existing Flask app exactly (Phase 6
is a port, not a redesign), just validated by Pydantic instead of the
hand-rolled parsing that module still uses for the Flask app.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from rivet.core.models import (
    GenerationRequest,
    Orientation,
    PlotSpec,
    RoomRequirement,
    RoomType,
    Ruleset,
    VastuOptions,
)

from .errors import ApiError


class PlotIn(BaseModel):
    width_m: float
    length_m: float
    entrance: str = "north"
    num_floors: int = 1
    abutting_road_width_m: float | None = None
    proposed_height_m: float | None = None


class RoomIn(BaseModel):
    room_type: str
    count: int = 1
    target_area_sqm: float | None = None
    attached_bathroom: bool = False
    label: str | None = None


class VastuIn(BaseModel):
    enabled: bool = False
    weight: float = 1.0
    plot_north: str | None = None


class GenerateRequestIn(BaseModel):
    plot: PlotIn
    rooms: list[RoomIn] = Field(min_length=1)
    num_candidates: int = 3
    seed: int | None = None
    ruleset: str = "tncdbr_2019"
    vastu: VastuIn = Field(default_factory=VastuIn)


def _enum_or_400(enum_cls, raw: str, field_name: str):
    try:
        return enum_cls(raw.lower())
    except ValueError as exc:
        valid = ", ".join(v.value for v in enum_cls)
        raise ApiError("validation_failed", f"'{field_name}' must be one of: {valid}", details={"field": field_name}) from exc


def to_generation_request(payload: GenerateRequestIn) -> GenerationRequest:
    entrance = _enum_or_400(Orientation, payload.plot.entrance, "plot.entrance")
    ruleset = _enum_or_400(Ruleset, payload.ruleset, "ruleset")

    try:
        plot = PlotSpec(
            width_m=payload.plot.width_m,
            length_m=payload.plot.length_m,
            entrance=entrance,
            num_floors=payload.plot.num_floors,
            abutting_road_width_m=payload.plot.abutting_road_width_m,
            proposed_height_m=payload.plot.proposed_height_m,
        )
    except ValueError as exc:
        raise ApiError("validation_failed", str(exc)) from exc

    rooms: list[RoomRequirement] = []
    for i, r in enumerate(payload.rooms):
        room_type = _enum_or_400(RoomType, r.room_type, f"rooms[{i}].room_type")
        try:
            rooms.append(
                RoomRequirement(
                    room_type=room_type,
                    count=r.count,
                    target_area_sqm=r.target_area_sqm,
                    attached_bathroom=r.attached_bathroom,
                    label=r.label,
                )
            )
        except ValueError as exc:
            raise ApiError("validation_failed", f"rooms[{i}]: {exc}") from exc

    plot_north = _enum_or_400(Orientation, payload.vastu.plot_north, "vastu.plot_north") if payload.vastu.plot_north else None
    try:
        vastu = VastuOptions(enabled=payload.vastu.enabled, weight=payload.vastu.weight, plot_north=plot_north)
    except ValueError as exc:
        raise ApiError("validation_failed", str(exc), details={"field": "vastu"}) from exc

    try:
        return GenerationRequest(
            plot=plot, rooms=rooms, num_candidates=payload.num_candidates, seed=payload.seed, ruleset=ruleset, vastu=vastu
        )
    except ValueError as exc:
        raise ApiError("validation_failed", str(exc)) from exc
