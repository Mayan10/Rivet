"""Single source of truth for every geometry-derived number Rivet reports.

Before this module, `sum(r.rect.area for r in layout.rooms)` (and similar
one-liners) were duplicated independently across the PNG renderer, the SVG
renderer, the DXF exporter, and the API schema layer -- harmless while it
was just a total-area sum, but Phase 2 adds real quantity-takeoff math
(wall running length, plaster area, block counts) that is not a one-liner
and would silently drift if left duplicated four ways. Every consumer now
calls :func:`compute_metrics` once and reads the result.

Two categories of number live here, and they must not be presented as the
same kind of fact:

- **Cited**: room minimums, corridor width, the ventilation *ratio*
  (1/8 of floor area), FSI cap -- all traceable to a TNCDBR 2019 rule
  (see ``core/rules.py`` and ``docs/regulatory_sources.md``).
- **Uncited assumption**: wall height, block dimensions, mortar joint,
  wastage factor, window/door height -- standard-practice placeholders
  needed to turn cited geometry into a quantity estimate, flagged as such
  in ``core/rules.py``. Nothing derived from these is used to reject a
  layout (see ``core/validator.py`` -- Phase 2 intentionally leaves its
  exterior-access check as the Phase 1 proxy rather than hinging a hard
  rejection on an invented window height).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import (
    HABITABLE_ROOM_TYPES,
    SERVICE_ROOM_TYPES,
    Layout,
    Rect,
    RoomInstance,
    RoomType,
    Ruleset,
)
from .rules import (
    BLOCK_COUNT_WASTAGE_FACTOR,
    BLOCK_HEIGHT_M,
    BLOCK_LENGTH_M,
    DOOR_HEIGHT_M,
    MORTAR_JOINT_M,
    PLASTER_FACES_EXTERNAL,
    PLASTER_FACES_INTERNAL,
    TNCDBR_MAX_FSI_CITATION,
    VENTILATION_CITATION,
    VENTILATION_OPENING_RATIO,
    VENTILATION_OPENING_RATIO_KITCHEN_MULTIPLIER,
    WALL_HEIGHT_M,
    WALL_THICKNESS_EXTERNAL_M,
    WALL_THICKNESS_INTERNAL_M,
    WINDOW_HEIGHT_M,
    setbacks_for,
)
from .rules import fsi_permitted as _fsi_permitted
from .walls import compute_wall_segments, edge_is_exterior, total_wall_length_by_class

# Circulation, for the purposes of this metric, is SERVICE_ROOM_TYPES
# (corridor, staircase) plus the foyer/entrance lobby -- a real transition
# space even though core/models.py doesn't classify it as "service".
_CIRCULATION_ROOM_TYPES = SERVICE_ROOM_TYPES | {RoomType.FOYER}

_BLOCK_FACE_AREA_SQM = (BLOCK_LENGTH_M + MORTAR_JOINT_M) * (BLOCK_HEIGHT_M + MORTAR_JOINT_M)


@dataclass(frozen=True)
class RoomMetric:
    room_id: str
    label: str
    room_type: RoomType
    gross_area_sqm: float  # room rect area, to wall centerline (Rivet's existing room geometry)
    carpet_area_sqm: float  # net clear area, inset by half the thickness of each bounding wall
    is_habitable: bool
    window_opening_area_sqm: float | None  # None if not habitable
    required_ventilation_area_sqm: float | None  # None if not habitable
    ventilation_ratio_actual: float | None  # window_opening_area / carpet_area; None if not habitable
    ventilation_passes: bool | None  # None if not habitable


@dataclass(frozen=True)
class SetbackFace:
    face: str  # "front" | "rear" | "left" | "right"
    required_m: float
    provided_m: float

    @property
    def compliant(self) -> bool:
        return self.provided_m >= self.required_m - 1e-6


@dataclass(frozen=True)
class OpeningScheduleRow:
    tag: str
    kind: str  # "door" | "main_door" | "window"
    width_m: float
    height_m: float
    count: int

    @property
    def unit_area_sqm(self) -> float:
        return self.width_m * self.height_m

    @property
    def total_area_sqm(self) -> float:
        return self.unit_area_sqm * self.count


@dataclass(frozen=True)
class QuantityTakeoff:
    exterior_wall_length_m: float
    interior_wall_length_m: float
    plaster_area_sqm: float  # gross both-faces estimate; does not deduct openings, see module docstring
    block_count_estimate: int  # deducts total opening area once from gross wall face area
    floor_finish_area_by_room_sqm: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class LayoutMetrics:
    rooms: list[RoomMetric]
    total_carpet_area_sqm: float
    total_built_up_area_sqm: float
    total_plinth_area_sqm: float
    circulation_area_sqm: float
    circulation_pct_of_built_up: float
    ground_coverage_pct: float
    fsi_consumed: float
    fsi_permitted: float | None
    fsi_permitted_citation: str | None
    setbacks: list[SetbackFace]
    door_schedule: list[OpeningScheduleRow]
    window_schedule: list[OpeningScheduleRow]
    quantity_takeoff: QuantityTakeoff

    @property
    def gross_area_sqm(self) -> float:
        """Sum of room rects to wall centerline -- what every consumer used
        to compute itself as ``sum(r.rect.area for r in layout.rooms)``
        before Phase 2. Kept as a derived property, not a stored field, so
        there's exactly one place that expression is allowed to appear.
        """
        return sum(r.gross_area_sqm for r in self.rooms)


def _carpet_rect(rect: Rect, buildable: Rect) -> Rect:
    left = (WALL_THICKNESS_EXTERNAL_M if edge_is_exterior("vertical", rect.x, buildable) else WALL_THICKNESS_INTERNAL_M) / 2
    right = (WALL_THICKNESS_EXTERNAL_M if edge_is_exterior("vertical", rect.x2, buildable) else WALL_THICKNESS_INTERNAL_M) / 2
    bottom = (WALL_THICKNESS_EXTERNAL_M if edge_is_exterior("horizontal", rect.y, buildable) else WALL_THICKNESS_INTERNAL_M) / 2
    top = (WALL_THICKNESS_EXTERNAL_M if edge_is_exterior("horizontal", rect.y2, buildable) else WALL_THICKNESS_INTERNAL_M) / 2

    w = max(rect.w - left - right, 0.0)
    h = max(rect.h - bottom - top, 0.0)
    return Rect(x=rect.x + left, y=rect.y + bottom, w=w, h=h)


def _room_metric(room: RoomInstance, layout: Layout) -> RoomMetric:
    carpet_rect = _carpet_rect(room.rect, layout.buildable)
    carpet_area = carpet_rect.area
    is_habitable = room.room_type in HABITABLE_ROOM_TYPES

    if not is_habitable:
        return RoomMetric(
            room_id=room.id,
            label=room.label,
            room_type=room.room_type,
            gross_area_sqm=room.rect.area,
            carpet_area_sqm=carpet_area,
            is_habitable=False,
            window_opening_area_sqm=None,
            required_ventilation_area_sqm=None,
            ventilation_ratio_actual=None,
            ventilation_passes=None,
        )

    window_width_total = sum(
        o.width for o in layout.openings if o.kind == "window" and o.room_id == room.id
    )
    window_area = window_width_total * WINDOW_HEIGHT_M

    ratio = VENTILATION_OPENING_RATIO
    if room.room_type == RoomType.KITCHEN:
        ratio *= VENTILATION_OPENING_RATIO_KITCHEN_MULTIPLIER
    required_area = carpet_area * ratio

    return RoomMetric(
        room_id=room.id,
        label=room.label,
        room_type=room.room_type,
        gross_area_sqm=room.rect.area,
        carpet_area_sqm=carpet_area,
        is_habitable=True,
        window_opening_area_sqm=window_area,
        required_ventilation_area_sqm=required_area,
        ventilation_ratio_actual=window_area / max(carpet_area, 1e-9),
        ventilation_passes=window_area >= required_area - 1e-6,
    )


def _setback_faces(layout: Layout, ruleset: Ruleset) -> list[SetbackFace]:
    plot = layout.plot
    required = setbacks_for(
        plot.width_m,
        plot.area_sqm,
        ruleset=ruleset,
        road_width_m=plot.abutting_road_width_m,
        height_m=plot.proposed_height_m,
        num_floors=plot.num_floors,
    )
    b = layout.buildable
    return [
        SetbackFace("front", required.front_m, plot.length_m - b.y2),
        SetbackFace("rear", required.rear_m, b.y),
        SetbackFace("left", required.side_m, b.x),
        SetbackFace("right", required.side_m, plot.width_m - b.x2),
    ]


def _opening_schedule(layout: Layout, kinds: tuple[str, ...], height_m: float) -> list[OpeningScheduleRow]:
    counts: dict[tuple[str, float], int] = {}
    for o in layout.openings:
        if o.kind not in kinds:
            continue
        key = (o.kind, round(o.width, 3))
        counts[key] = counts.get(key, 0) + 1

    rows = []
    for i, ((kind, width), count) in enumerate(sorted(counts.items(), key=lambda kv: (kv[0][0], kv[0][1])), start=1):
        prefix = "MD" if kind == "main_door" else ("D" if kind == "door" else "W")
        rows.append(OpeningScheduleRow(tag=f"{prefix}{i}", kind=kind, width_m=width, height_m=height_m, count=count))
    return rows


def _quantity_takeoff(layout: Layout, rooms: list[RoomMetric], total_opening_area_sqm: float) -> QuantityTakeoff:
    segments = compute_wall_segments(layout)
    exterior_len, interior_len = total_wall_length_by_class(segments)

    plaster_area = (
        exterior_len * WALL_HEIGHT_M * PLASTER_FACES_EXTERNAL + interior_len * WALL_HEIGHT_M * PLASTER_FACES_INTERNAL
    )

    gross_wall_face_area = (exterior_len + interior_len) * WALL_HEIGHT_M
    net_wall_face_area = max(gross_wall_face_area - total_opening_area_sqm, 0.0)
    block_count = math.ceil(net_wall_face_area / _BLOCK_FACE_AREA_SQM * BLOCK_COUNT_WASTAGE_FACTOR)

    floor_finish = {r.room_id: r.carpet_area_sqm for r in rooms}

    return QuantityTakeoff(
        exterior_wall_length_m=exterior_len,
        interior_wall_length_m=interior_len,
        plaster_area_sqm=plaster_area,
        block_count_estimate=block_count,
        floor_finish_area_by_room_sqm=floor_finish,
    )


def compute_metrics(layout: Layout, ruleset: Ruleset = Ruleset.TNCDBR_2019) -> LayoutMetrics:
    plot = layout.plot
    buildable = layout.buildable

    rooms = [_room_metric(room, layout) for room in layout.rooms]
    total_carpet = sum(r.carpet_area_sqm for r in rooms)

    # Built-up area = area within the OUTER face of the external wall, i.e.
    # the buildable rect (bounded at the external wall CENTERLINE) expanded
    # by half the external wall thickness on every side.
    built_up_w = buildable.w + WALL_THICKNESS_EXTERNAL_M
    built_up_h = buildable.h + WALL_THICKNESS_EXTERNAL_M
    total_built_up = built_up_w * built_up_h

    # Plinth area: built-up plus any plinth-only elements (porch, verandah
    # projections beyond the building line). Rivet doesn't model those
    # separately yet, so plinth == built-up for now -- not an approximation
    # so much as "there is nothing else to add" given current scope.
    total_plinth = total_built_up

    circulation_area = sum(r.gross_area_sqm for r in rooms if r.room_type in _CIRCULATION_ROOM_TYPES)
    circulation_pct = (circulation_area / total_built_up * 100) if total_built_up > 0 else 0.0

    ground_coverage_pct = (total_built_up / plot.area_sqm * 100) if plot.area_sqm > 0 else 0.0
    # FSI consumed assumes each floor repeats this ground floor's footprint
    # -- Rivet doesn't yet generate distinct per-floor layouts (see
    # docs/prompts.md Phase 3/multi-storey scope note).
    fsi_consumed = (total_built_up * plot.num_floors) / plot.area_sqm if plot.area_sqm > 0 else 0.0
    fsi_cap = _fsi_permitted(ruleset)

    door_schedule = _opening_schedule(layout, ("door", "main_door"), DOOR_HEIGHT_M)
    window_schedule = _opening_schedule(layout, ("window",), WINDOW_HEIGHT_M)
    total_opening_area = sum(r.total_area_sqm for r in door_schedule) + sum(r.total_area_sqm for r in window_schedule)

    return LayoutMetrics(
        rooms=rooms,
        total_carpet_area_sqm=total_carpet,
        total_built_up_area_sqm=total_built_up,
        total_plinth_area_sqm=total_plinth,
        circulation_area_sqm=circulation_area,
        circulation_pct_of_built_up=circulation_pct,
        ground_coverage_pct=ground_coverage_pct,
        fsi_consumed=fsi_consumed,
        fsi_permitted=fsi_cap,
        fsi_permitted_citation=(TNCDBR_MAX_FSI_CITATION if fsi_cap is not None else None),
        setbacks=_setback_faces(layout, ruleset),
        door_schedule=door_schedule,
        window_schedule=window_schedule,
        quantity_takeoff=_quantity_takeoff(layout, rooms, total_opening_area),
    )


__all__ = [
    "VENTILATION_CITATION",
    "LayoutMetrics",
    "OpeningScheduleRow",
    "QuantityTakeoff",
    "RoomMetric",
    "SetbackFace",
    "compute_metrics",
]
