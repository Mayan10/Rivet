"""Optional vastu-shastra directional-placement scoring (Phase 5,
docs/prompts.md).

This module is entirely SOFT: nothing here computes a hard rejection or
feeds ``core/validator.py``, and it's never even called unless
``GenerationRequest.vastu.enabled`` is True (default False) -- see
``core/scoring.py``. With vastu disabled, search output is byte-identical
to before this module existed (see ``tests/test_vastu.py``).

Vastu directional analysis needs to know which way TRUE north actually
is. ``core/models.py``'s coordinate convention ("x -> east, y -> north")
is only ever a drawing-space assumption -- a real plot's surveyed
orientation may not match it -- so ``VastuOptions.plot_north`` is a
required input whenever vastu is enabled, naming which *drawing* axis
actually points at true north for this specific plot. Every direction
check in this module rotates into a true-north-aligned frame first (see
``true_compass_zone``) before classifying a room.

Zones are the standard simplified 8-direction (Ashtadikpalaka) division
used by most practical vastu tools: the buildable rectangle is treated as
centered on its own center point, and each room is classified by the
compass bearing from that center to the room's own center, in 45-degree
sectors.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .graph import RoomNode
from .models import Orientation, PlotSpec, Rect, RoomType, VastuOptions

_ZONES = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

# Rotation applied to a (dx, dy) drawing-space offset to get a
# (dx', dy') true-north-aligned offset, keyed by VastuOptions.plot_north
# -- chosen so the drawing axis plot_north names ends up pointing at true
# north (0, 1) in the rotated frame. NORTH is the identity: the common
# case where the drawing's own "y -> north" convention already matches
# the plot's real survey orientation.
_ROTATIONS = {
    Orientation.NORTH: lambda dx, dy: (dx, dy),
    Orientation.EAST: lambda dx, dy: (-dy, dx),
    Orientation.SOUTH: lambda dx, dy: (-dx, -dy),
    Orientation.WEST: lambda dx, dy: (dy, -dx),
}

_ENTRANCE_OFFSET = {
    Orientation.NORTH: (0.0, 1.0),
    Orientation.SOUTH: (0.0, -1.0),
    Orientation.EAST: (1.0, 0.0),
    Orientation.WEST: (-1.0, 0.0),
}

# Base penalty per violated preference; scaled by VastuOptions.weight.
# Uncited (there is no code basis for vastu -- see docs/design_rules.md),
# tuned only so a vastu-enabled search has a real gradient to climb.
W_VASTU_VIOLATION = 10.0

_PREFERRED_ZONE: dict[RoomType, tuple[str, str, str]] = {
    RoomType.KITCHEN: ("kitchen_southeast", "Kitchen should be in the southeast (Agni) zone.", "SE"),
    RoomType.MASTER_BEDROOM: (
        "master_bedroom_southwest",
        "Master bedroom should be in the southwest (Nairutya) zone.",
        "SW",
    ),
    RoomType.POOJA: ("pooja_northeast", "Pooja/prayer room should be in the northeast (Ishanya) zone.", "NE"),
}

_AVOIDED_ZONE: dict[RoomType, tuple[str, str, str]] = {
    RoomType.BATHROOM: ("toilet_avoid_northeast", "Bathroom should avoid the northeast (Ishanya) zone.", "NE"),
    RoomType.TOILET: ("toilet_avoid_northeast", "Toilet should avoid the northeast (Ishanya) zone.", "NE"),
}


@dataclass(frozen=True)
class VastuPreferenceResult:
    name: str
    description: str
    room_id: str | None
    room_label: str
    satisfied: bool


@dataclass(frozen=True)
class VastuResult:
    penalty: float
    preferences: list[VastuPreferenceResult]


def true_compass_zone(dx: float, dy: float, plot_north: Orientation) -> str:
    """Classify a (dx, dy) drawing-space offset into one of 8 true-compass
    sectors, after rotating for ``plot_north``.
    """
    tdx, tdy = _ROTATIONS[plot_north](dx, dy)
    if tdx == 0.0 and tdy == 0.0:
        return "CENTER"
    # Compass bearing (0 = north, clockwise-positive): atan2(easting,
    # northing), not the usual atan2(y, x) -- north is the reference axis
    # here, not east.
    bearing = math.degrees(math.atan2(tdx, tdy)) % 360
    index = int((bearing + 22.5) // 45) % 8
    return _ZONES[index]


def room_zone(rect: Rect, buildable: Rect, plot_north: Orientation) -> str:
    return true_compass_zone(rect.cx - buildable.cx, rect.cy - buildable.cy, plot_north)


def evaluate_vastu(
    nodes: list[RoomNode],
    rects: dict[str, Rect],
    buildable: Rect,
    plot: PlotSpec,
    options: VastuOptions,
) -> VastuResult:
    assert options.plot_north is not None  # enforced by VastuOptions.__post_init__ when enabled
    plot_north = options.plot_north
    preferences: list[VastuPreferenceResult] = []
    violated = 0

    def record(name: str, description: str, room_id: str | None, room_label: str, satisfied: bool) -> None:
        nonlocal violated
        preferences.append(VastuPreferenceResult(name, description, room_id, room_label, satisfied))
        if not satisfied:
            violated += 1

    for node in nodes:
        rect = rects.get(node.id)
        if rect is None:
            continue
        zone = room_zone(rect, buildable, plot_north)

        preferred = _PREFERRED_ZONE.get(node.room_type)
        if preferred is not None:
            name, description, target_zone = preferred
            record(name, description, node.id, node.label, zone == target_zone)

        avoided = _AVOIDED_ZONE.get(node.room_type)
        if avoided is not None:
            name, description, avoid_zone = avoided
            record(name, description, node.id, node.label, zone != avoid_zone)

    entrance_dx, entrance_dy = _ENTRANCE_OFFSET[plot.entrance]
    entrance_zone = true_compass_zone(entrance_dx, entrance_dy, plot_north)
    record(
        "entrance_orientation",
        "Main entrance should face north or east.",
        None,
        "Entrance",
        entrance_zone in ("N", "NE", "E"),
    )

    penalty = options.weight * W_VASTU_VIOLATION * violated
    return VastuResult(penalty=penalty, preferences=preferences)
