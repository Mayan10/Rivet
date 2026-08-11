"""The design rulebook.

These constants encode commonly-referenced residential space-planning
guidance (dimensions found across national building codes and standard
architectural handbooks for single-family residential design). They are
defaults for an automated design *assistant* — not a substitute for a
licensed engineer's stamped drawings or the locally-applicable building
code, which always takes precedence.

See ``docs/design_rules.md`` for the human-readable version of this file.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RoomType

# ---------------------------------------------------------------------------
# Per-room-type space standards
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomRule:
    min_area_sqm: float
    default_area_sqm: float
    min_width_m: float
    max_aspect_ratio: float = 2.2  # long-side : short-side comfort ceiling
    exterior_wall_required: bool = False


ROOM_RULES: dict[RoomType, RoomRule] = {
    RoomType.LIVING_ROOM: RoomRule(11.0, 18.0, 2.7, 2.2, True),
    RoomType.MASTER_BEDROOM: RoomRule(11.0, 14.0, 2.7, 2.0, True),
    RoomType.BEDROOM: RoomRule(9.5, 11.0, 2.4, 2.0, True),
    RoomType.KITCHEN: RoomRule(5.0, 8.0, 1.8, 2.4, True),
    RoomType.DINING_ROOM: RoomRule(7.5, 10.0, 2.4, 2.0, False),
    RoomType.BATHROOM: RoomRule(2.2, 3.5, 1.2, 2.2, False),
    RoomType.TOILET: RoomRule(1.5, 1.8, 0.9, 2.2, False),
    RoomType.STUDY: RoomRule(6.5, 9.0, 2.1, 2.0, True),
    RoomType.GARAGE: RoomRule(15.0, 18.0, 2.7, 2.2, False),
    RoomType.STORE: RoomRule(2.0, 3.0, 1.2, 2.2, False),
    RoomType.FOYER: RoomRule(2.5, 4.0, 1.2, 2.5, False),
    RoomType.CORRIDOR: RoomRule(1.5, 2.5, 1.0, 6.0, False),
    RoomType.STAIRCASE: RoomRule(4.0, 5.0, 1.0, 3.0, False),
    RoomType.UTILITY: RoomRule(2.5, 3.5, 1.2, 2.4, False),
    RoomType.BALCONY: RoomRule(2.0, 3.5, 1.0, 3.0, True),
}


def rule_for(room_type: RoomType) -> RoomRule:
    try:
        return ROOM_RULES[room_type]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"No design rule registered for room type {room_type!r}") from exc


# ---------------------------------------------------------------------------
# Construction standards
# ---------------------------------------------------------------------------

WALL_THICKNESS_EXTERNAL_M = 0.23  # ~9in masonry, load-bearing perimeter wall
WALL_THICKNESS_INTERNAL_M = 0.115  # ~4.5in half-brick partition

DOOR_WIDTH_MAIN_M = 1.00
DOOR_WIDTH_INTERNAL_M = 0.90
DOOR_WIDTH_BATH_M = 0.75
DOOR_HEIGHT_M = 2.10  # not drawn in plan view, kept for DXF text/metadata

WINDOW_WIDTH_HABITABLE_M = 1.20
WINDOW_WIDTH_KITCHEN_M = 0.90
WINDOW_SILL_HEIGHT_M = 0.90  # not drawn in plan view, kept for metadata

CORRIDOR_MIN_WIDTH_M = 1.00
MIN_OPENING_EDGE_CLEARANCE_M = 0.30  # keep door/window off the exact corner


def door_width_for(room_type: RoomType) -> float:
    if room_type in (RoomType.BATHROOM, RoomType.TOILET):
        return DOOR_WIDTH_BATH_M
    return DOOR_WIDTH_INTERNAL_M


def window_width_for(room_type: RoomType) -> float:
    if room_type == RoomType.KITCHEN:
        return WINDOW_WIDTH_KITCHEN_M
    return WINDOW_WIDTH_HABITABLE_M


# ---------------------------------------------------------------------------
# Setbacks (simplified tiered rule as a function of plot area)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Setbacks:
    front_m: float
    rear_m: float
    side_m: float


_SETBACK_TIERS: list[tuple[float, Setbacks]] = [
    (150.0, Setbacks(front_m=1.5, rear_m=1.0, side_m=0.9)),
    (300.0, Setbacks(front_m=3.0, rear_m=2.0, side_m=1.5)),
    (500.0, Setbacks(front_m=4.5, rear_m=3.0, side_m=2.0)),
    (float("inf"), Setbacks(front_m=6.0, rear_m=4.0, side_m=3.0)),
]


def setbacks_for(plot_area_sqm: float) -> Setbacks:
    for ceiling, setbacks in _SETBACK_TIERS:
        if plot_area_sqm <= ceiling:
            return setbacks
    return _SETBACK_TIERS[-1][1]  # pragma: no cover - unreachable, inf ceiling above


# ---------------------------------------------------------------------------
# Adjacency preferences and hard avoidances
# ---------------------------------------------------------------------------

# Soft preferences: rooms that should share a wall when possible. Symmetric.
#
# Note: there is deliberately no generic (BEDROOM, BATHROOM) style pair here.
# That relationship is handled per-instance by ``RoomRequirement.attached_bathroom``
# in core/graph.py, which creates one dedicated *required* edge per en-suite.
# A generic type-level preference would instead make *every* bedroom prefer
# *every* bathroom in the request — an edge count that grows with
# bedrooms x bathrooms and that no single-wall-per-room geometry could ever
# satisfy, which would push every candidate's adjacency score toward zero
# regardless of actual layout quality. Bedrooms reach a shared/family
# bathroom via the corridor pairs below instead.
ADJACENCY_PREFERRED: list[tuple[RoomType, RoomType]] = [
    (RoomType.KITCHEN, RoomType.DINING_ROOM),
    (RoomType.DINING_ROOM, RoomType.LIVING_ROOM),
    (RoomType.LIVING_ROOM, RoomType.FOYER),
    (RoomType.FOYER, RoomType.CORRIDOR),
    (RoomType.CORRIDOR, RoomType.BEDROOM),
    (RoomType.CORRIDOR, RoomType.MASTER_BEDROOM),
    (RoomType.CORRIDOR, RoomType.BATHROOM),
    (RoomType.KITCHEN, RoomType.UTILITY),
    (RoomType.GARAGE, RoomType.FOYER),
    (RoomType.STAIRCASE, RoomType.CORRIDOR),
    (RoomType.STAIRCASE, RoomType.FOYER),
]

# Hard avoidances: rooms that should *not* share a wall/door. Symmetric.
ADJACENCY_AVOID: list[tuple[RoomType, RoomType]] = [
    (RoomType.BATHROOM, RoomType.KITCHEN),
    (RoomType.TOILET, RoomType.KITCHEN),
    (RoomType.BATHROOM, RoomType.DINING_ROOM),
    (RoomType.TOILET, RoomType.DINING_ROOM),
]

# Rooms a main entrance is allowed to open directly into.
ENTRANCE_COMPATIBLE_ROOMS = frozenset(
    {RoomType.FOYER, RoomType.LIVING_ROOM, RoomType.CORRIDOR, RoomType.GARAGE}
)


def _pair_in(pairs: list[tuple[RoomType, RoomType]], a: RoomType, b: RoomType) -> bool:
    return (a, b) in pairs or (b, a) in pairs


def is_preferred_adjacency(a: RoomType, b: RoomType) -> bool:
    return _pair_in(ADJACENCY_PREFERRED, a, b)


def is_avoided_adjacency(a: RoomType, b: RoomType) -> bool:
    return _pair_in(ADJACENCY_AVOID, a, b)


# ---------------------------------------------------------------------------
# Request-level validation
# ---------------------------------------------------------------------------


def validate_request(plot_width_m: float, plot_length_m: float, room_specs: list[tuple[RoomType, int, float | None]]) -> list[str]:
    """Sanity-check a request before spending time generating layouts.

    ``room_specs`` is a list of (room_type, count, target_area_sqm_or_None).
    Returns a list of human-readable warning/error strings; an empty list
    means the request looks feasible.
    """
    issues: list[str] = []
    plot_area = plot_width_m * plot_length_m
    setbacks = setbacks_for(plot_area)
    buildable_w = plot_width_m - 2 * setbacks.side_m
    buildable_l = plot_length_m - setbacks.front_m - setbacks.rear_m

    if buildable_w <= 1.0 or buildable_l <= 1.0:
        issues.append(
            f"Plot {plot_width_m}m x {plot_length_m}m is too small once setbacks "
            f"(side {setbacks.side_m}m, front {setbacks.front_m}m, rear {setbacks.rear_m}m) "
            "are applied — there is little to no buildable area left."
        )
        return issues

    buildable_area = buildable_w * buildable_l

    required_area = 0.0
    for room_type, count, target_area in room_specs:
        rule = rule_for(room_type)
        per_room = target_area if target_area is not None else rule.default_area_sqm
        if per_room < rule.min_area_sqm:
            issues.append(
                f"{room_type.value}: requested {per_room:.1f} sqm is below the "
                f"recommended minimum of {rule.min_area_sqm:.1f} sqm."
            )
        required_area += per_room * count

    # Circulation allowance: real plans lose ~12-18% of buildable area to
    # walls and corridors that aren't "rooms" themselves.
    required_with_circulation = required_area * 1.15
    if required_with_circulation > buildable_area:
        issues.append(
            f"Requested rooms need roughly {required_with_circulation:.1f} sqm "
            f"(including circulation) but the buildable area is only "
            f"{buildable_area:.1f} sqm. Reduce room count/areas or use a larger plot."
        )

    return issues
