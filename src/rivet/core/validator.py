"""Hard-constraint validation.

Everything here either rejects a layout or it doesn't -- there is no
weighted penalty in this module. That's the point: building-code minimums
must never be traded off against how nice the rest of a layout looks (that
was the bug this module fixes -- see ``docs/prompts.md`` Phase 1 and the
Phase 0 audit). Soft preferences (adjacency desirability, aspect ratio,
area-error-from-target, entrance placement) stay in ``core/scoring.py``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from .geometry import MIN_USABLE_SHARED_WALL_M, on_boundary, shared_wall
from .models import Layout, Rect, RoomType
from .rules import (
    ADJACENCY_AVOID_HARD_CITATION,
    Ruleset,
    is_hard_avoided_adjacency,
    kitchen_minimum,
    rule_for,
    setbacks_for,
)

_REACHABILITY_CITATION = (
    "Phase 3 design (docs/prompts.md 'Approach A'): construction already "
    "guarantees every room connects to circulation (core/layout_engine.py's "
    "forced-axis splitting), so this is a belt-and-suspenders check against "
    "the actual door graph rather than trusting geometry alone."
)
_EXTERIOR_ACCESS_CITATION = (
    "TNCDBR 2019, Rule 52(16)(a) [ventilation opening required; this check is a "
    "has-exterior-wall proxy -- the real 1/8-of-floor-area opening ratio is "
    "computed in core/metrics.py per the Phase 2 plan, not here]"
)
_SETBACK_CITATION = "TNCDBR 2019, Rule 35"


@dataclass(frozen=True)
class Violation:
    constraint_id: str
    severity: str  # "error" -- everything in this module is a hard rejection
    room_id: str | None
    message: str
    actual: float | None
    required: float | None
    source: str


@dataclass(frozen=True)
class ValidationResult:
    violations: list[Violation] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.violations) == 0


def _room_min_dimensions(
    room_type: RoomType, ruleset: Ruleset, has_dining_room: bool
) -> tuple[float, float, str]:
    rule = rule_for(room_type, ruleset)
    if room_type == RoomType.KITCHEN:
        min_area, min_width = kitchen_minimum(has_dining_room)
        return min_area, min_width, rule.citation
    return rule.min_area_sqm, rule.min_width_m, rule.citation


def _dimension_violations(layout: Layout, ruleset: Ruleset) -> list[Violation]:
    violations: list[Violation] = []
    has_dining_room = any(r.room_type == RoomType.DINING_ROOM for r in layout.rooms)

    for room in layout.rooms:
        rule = rule_for(room.room_type, ruleset)
        min_area, min_width, citation = _room_min_dimensions(room.room_type, ruleset, has_dining_room)

        if room.rect.area < min_area - 1e-6:
            violations.append(
                Violation(
                    constraint_id="min_area",
                    severity="error",
                    room_id=room.id,
                    message=(
                        f"{room.label}: {room.rect.area:.2f} sqm is below the legal "
                        f"minimum of {min_area:.2f} sqm."
                    ),
                    actual=room.rect.area,
                    required=min_area,
                    source=citation,
                )
            )

        if room.rect.min_side < min_width - 1e-6:
            violations.append(
                Violation(
                    constraint_id="min_width",
                    severity="error",
                    room_id=room.id,
                    message=(
                        f"{room.label}: narrowest side {room.rect.min_side:.2f}m is "
                        f"below the legal minimum of {min_width:.2f}m."
                    ),
                    actual=room.rect.min_side,
                    required=min_width,
                    source=citation,
                )
            )

        if rule.exterior_wall_required and not on_boundary(room.rect, layout.buildable):
            violations.append(
                Violation(
                    constraint_id="exterior_access",
                    severity="error",
                    room_id=room.id,
                    message=f"{room.label} has no exterior wall for daylight/ventilation.",
                    actual=None,
                    required=None,
                    source=_EXTERIOR_ACCESS_CITATION,
                )
            )

    return violations


def _hard_adjacency_violations(layout: Layout) -> list[Violation]:
    violations: list[Violation] = []
    rooms = layout.rooms
    for i, a in enumerate(rooms):
        for b in rooms[i + 1 :]:
            if not is_hard_avoided_adjacency(a.room_type, b.room_type):
                continue
            if shared_wall(a.rect, b.rect, min_length=MIN_USABLE_SHARED_WALL_M):
                violations.append(
                    Violation(
                        constraint_id="adjacency_avoided_hard",
                        severity="error",
                        room_id=a.id,
                        message=f"{a.label} and {b.label} share a wall, which is not permitted.",
                        actual=None,
                        required=None,
                        source=ADJACENCY_AVOID_HARD_CITATION,
                    )
                )
    return violations


def _setback_violations(layout: Layout, ruleset: Ruleset) -> list[Violation]:
    """Defensive check: layout.buildable should always already match the
    ruleset's setbacks, since it's derived from setbacks_for() at generation
    time -- but this catches a mismatch if a layout is ever validated
    against a different ruleset than it was generated with.
    """
    plot = layout.plot
    expected = setbacks_for(
        plot.width_m,
        plot.area_sqm,
        ruleset=ruleset,
        road_width_m=plot.abutting_road_width_m,
        height_m=plot.proposed_height_m,
        num_floors=plot.num_floors,
    )
    expected_buildable = Rect(
        x=expected.side_m,
        y=expected.rear_m,
        w=plot.width_m - 2 * expected.side_m,
        h=plot.length_m - expected.front_m - expected.rear_m,
    )

    tol = 1e-3
    b = layout.buildable
    mismatched = (
        abs(b.x - expected_buildable.x) > tol
        or abs(b.y - expected_buildable.y) > tol
        or abs(b.w - expected_buildable.w) > tol
        or abs(b.h - expected_buildable.h) > tol
    )
    if not mismatched:
        return []

    return [
        Violation(
            constraint_id="setback_compliance",
            severity="error",
            room_id=None,
            message=(
                f"Buildable area {b.w:.2f}x{b.h:.2f} at ({b.x:.2f},{b.y:.2f}) does not "
                f"match the setbacks required for this ruleset "
                f"(expected {expected_buildable.w:.2f}x{expected_buildable.h:.2f} at "
                f"({expected_buildable.x:.2f},{expected_buildable.y:.2f}))."
            ),
            actual=None,
            required=None,
            source=_SETBACK_CITATION,
        )
    ]


def _reachability_violations(layout: Layout) -> list[Violation]:
    """Every room must be reachable from the entrance by walking through
    doors -- never trapped behind another room with no door of its own.

    This walks the *actual* door graph (``layout.openings``), not the
    desired-adjacency graph used to seed generation, so it catches any
    discrepancy between what the layout engine intended and what
    ``openings.py`` actually placed.
    """
    adjacency: dict[str, set[str]] = {room.id: set() for room in layout.rooms}
    for opening in layout.openings:
        if opening.connects_to is None:
            continue
        if opening.room_id in adjacency:
            adjacency[opening.room_id].add(opening.connects_to)
        if opening.connects_to in adjacency:
            adjacency[opening.connects_to].add(opening.room_id)

    main_doors = [o for o in layout.openings if o.kind == "main_door"]
    if not main_doors:
        return [
            Violation(
                constraint_id="reachability",
                severity="error",
                room_id=None,
                message="No main entrance door was placed; the layout has no connection to the outside.",
                actual=None,
                required=None,
                source=_REACHABILITY_CITATION,
            )
        ]

    entry_id = main_doors[0].room_id
    reachable = {entry_id}
    queue = deque([entry_id])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, ()):
            if neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)

    return [
        Violation(
            constraint_id="reachability",
            severity="error",
            room_id=room.id,
            message=f"{room.label} is not reachable from the entrance through any door.",
            actual=None,
            required=None,
            source=_REACHABILITY_CITATION,
        )
        for room in layout.rooms
        if room.id not in reachable
    ]


def validate_layout(layout: Layout, ruleset: Ruleset = Ruleset.TNCDBR_2019) -> ValidationResult:
    """Run every hard constraint against a fully-formed layout.

    Door widths are deliberately NOT checked here: TNCDBR 2019's general
    residential provisions don't specify one (see
    docs/regulatory_sources.md "Gaps"), and CLAUDE.md's rule against
    inventing code values applies just as much to what the validator
    rejects as to what core/rules.py hardcodes.
    """
    violations: list[Violation] = []
    violations.extend(_dimension_violations(layout, ruleset))
    violations.extend(_hard_adjacency_violations(layout))
    violations.extend(_setback_violations(layout, ruleset))
    violations.extend(_reachability_violations(layout))
    return ValidationResult(violations=violations)
