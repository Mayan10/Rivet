"""Phase 3 reachability (docs/prompts.md "Approach A" -- belt-and-suspenders).

The Phase 0 audit's single most severe finding was that a generated layout
could place a room with no route back to the entrance: nothing enforced
that the door graph formed one connected component rooted at the main
door. core/layout_engine.py's circulation-aware splitter now guarantees
this by construction (see its module docstring), and
core/validator.py's reachability check is the defensive confirmation of
it, catching anything construction alone doesn't (see the real door-fit
bugs it caught during Phase 3 -- geometry.py's shared_wall float
tolerance, openings.py's corridor-junction opening, and
layout_engine.py's per-room-type door-fit floor).

These tests stress both across many room programs, plot sizes, entrance
orientations and seeds, with no explicit CORRIDOR room ever requested --
exactly the scenario the original bug was found in: circulation must be
entirely automatic, never something the caller has to ask for.
"""

from __future__ import annotations

import itertools
from collections import deque

import pytest

from conftest import assert_feasible
from rivet.core.generator import generate
from rivet.core.models import (
    GenerationRequest,
    InfeasibleResult,
    Layout,
    Orientation,
    PlotSpec,
    RoomRequirement,
    RoomType,
)
from rivet.core.validator import validate_layout

_PROGRAMS = {
    "small": [
        RoomRequirement(RoomType.LIVING_ROOM, count=1),
        RoomRequirement(RoomType.BEDROOM, count=1),
        RoomRequirement(RoomType.KITCHEN, count=1),
        RoomRequirement(RoomType.BATHROOM, count=1),
    ],
    "typical": [
        RoomRequirement(RoomType.LIVING_ROOM, count=1),
        RoomRequirement(RoomType.MASTER_BEDROOM, count=1, attached_bathroom=True),
        RoomRequirement(RoomType.BEDROOM, count=2, attached_bathroom=True),
        RoomRequirement(RoomType.KITCHEN, count=1),
        RoomRequirement(RoomType.DINING_ROOM, count=1),
        RoomRequirement(RoomType.BATHROOM, count=1),
    ],
    # Deliberately over CIRCULATION_SINGLE_LOAD_THRESHOLD -- forces the
    # branching corridor tree, not just a single spine.
    "large_branching": [
        RoomRequirement(RoomType.LIVING_ROOM, count=1),
        RoomRequirement(RoomType.MASTER_BEDROOM, count=1, attached_bathroom=True),
        RoomRequirement(RoomType.BEDROOM, count=3, attached_bathroom=True),
        RoomRequirement(RoomType.KITCHEN, count=1),
        RoomRequirement(RoomType.DINING_ROOM, count=1),
        RoomRequirement(RoomType.BATHROOM, count=2),
        RoomRequirement(RoomType.STUDY, count=1),
    ],
}

_PLOTS = {
    "tight": (12.0, 11.0),
    "comfortable": (18.0, 15.0),
}

_ORIENTATIONS = [Orientation.NORTH, Orientation.SOUTH, Orientation.EAST, Orientation.WEST]
_SEEDS = [1, 42, 123]


def _reachable_ids(layout: Layout) -> set[str]:
    """BFS over the door graph from the main entrance -- an independent
    re-implementation of core/validator.py's own reachability walk, kept
    deliberately separate so this test isn't just re-running the same code
    it's meant to check.
    """
    adjacency: dict[str, set[str]] = {room.id: set() for room in layout.rooms}
    for opening in layout.openings:
        if opening.connects_to is None:
            continue
        adjacency.setdefault(opening.room_id, set()).add(opening.connects_to)
        adjacency.setdefault(opening.connects_to, set()).add(opening.room_id)

    main_doors = [o for o in layout.openings if o.kind == "main_door"]
    if not main_doors:
        return set()

    start = main_doors[0].room_id
    reachable = {start}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, ()):
            if neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)
    return reachable


@pytest.mark.parametrize(
    "program_name,plot_name,entrance,seed",
    list(itertools.product(_PROGRAMS, _PLOTS, _ORIENTATIONS, _SEEDS)),
)
def test_every_candidate_room_is_reachable_from_entrance(program_name, plot_name, entrance, seed):
    width, length = _PLOTS[plot_name]
    request = GenerationRequest(
        plot=PlotSpec(
            width_m=width,
            length_m=length,
            entrance=entrance,
            abutting_road_width_m=9.0,
            proposed_height_m=6.0,
        ),
        rooms=_PROGRAMS[program_name],
        num_candidates=2,
        seed=seed,
    )
    result = generate(request)

    if isinstance(result, InfeasibleResult):
        # A tight plot legitimately having no valid layout (e.g. "tight" +
        # "large_branching") is expected and not what this test is
        # checking -- generate() already never returns a layout that
        # fails validate_layout, reachability included.
        return

    for layout in result:
        validation = validate_layout(layout, request.ruleset)
        assert validation.is_valid, [(v.constraint_id, v.room_id, v.message) for v in validation.violations]

        room_ids = {room.id for room in layout.rooms}
        reachable = _reachable_ids(layout)
        assert room_ids <= reachable, f"unreachable from entrance: {room_ids - reachable}"


def test_typical_program_on_a_comfortable_plot_is_feasible_and_reachable(sample_request):
    # A concrete, always-feasible positive case (unlike the parametrized
    # sweep above, which allows legitimate infeasibility) -- so this test
    # fails loudly, not silently, if a future change breaks the common
    # path rather than just an edge case.
    layouts = assert_feasible(generate(sample_request))
    for layout in layouts:
        validation = validate_layout(layout, sample_request.ruleset)
        assert validation.is_valid

        room_ids = {room.id for room in layout.rooms}
        reachable = _reachable_ids(layout)
        assert room_ids <= reachable
