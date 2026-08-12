"""High-level entry point: a :class:`GenerationRequest` in, either ranked
:class:`Layout` candidates or an :class:`InfeasibleResult` out.

This is the only function most callers (the CLI, the API) need to know
about — it wires together the graph builder, the layout search, the
opening placer, and (as of Phase 1) hard-constraint validation. The layout
search (``core/layout_engine.py``) only optimizes the soft score and has no
concept of a hard rejection, so this module over-generates candidates and
filters them through ``core/validator.py`` itself, rather than teaching the
search algorithm about validity.
"""

from __future__ import annotations

from .graph import build_adjacency_graph, expand_room_requirements
from .layout_engine import search_layouts
from .models import GenerationRequest, InfeasibleResult, Layout, Rect, RoomInstance
from .openings import place_openings
from .rules import setbacks_for
from .validator import ValidationResult, validate_layout


def compute_buildable_rect(request: GenerationRequest) -> Rect:
    plot = request.plot
    setbacks = setbacks_for(
        plot.width_m,
        plot.area_sqm,
        ruleset=request.ruleset,
        road_width_m=plot.abutting_road_width_m,
        height_m=plot.proposed_height_m,
        num_floors=plot.num_floors,
    )
    w = plot.width_m - 2 * setbacks.side_m
    h = plot.length_m - setbacks.front_m - setbacks.rear_m
    if w <= 0 or h <= 0:
        raise ValueError(
            f"Plot {plot.width_m}m x {plot.length_m}m leaves no buildable area once "
            f"setbacks (side {setbacks.side_m}m, front {setbacks.front_m}m, "
            f"rear {setbacks.rear_m}m) are applied."
        )
    return Rect(x=setbacks.side_m, y=setbacks.rear_m, w=w, h=h)


def _build_layout(candidate_id, sr, nodes, buildable, request, graph) -> Layout:
    rooms = [
        RoomInstance(id=n.id, room_type=n.room_type, label=n.label, rect=sr.rects[n.id])
        for n in nodes
    ]
    openings = place_openings(nodes, sr.rects, buildable, request.plot, graph)
    return Layout(
        candidate_id=candidate_id,
        plot=request.plot,
        buildable=buildable,
        rooms=rooms,
        openings=openings,
        score=sr.result.score,
        score_breakdown=sr.result.breakdown,
        violations=sr.result.violations,
        ruleset=request.ruleset,
    )


def generate(request: GenerationRequest) -> list[Layout] | InfeasibleResult:
    buildable = compute_buildable_rect(request)

    nodes = expand_room_requirements(request.rooms, ruleset=request.ruleset)
    if not nodes:
        raise ValueError("The request produced no rooms to place")

    graph = build_adjacency_graph(nodes)

    # Over-generate: the search only optimizes the soft score and has no
    # idea what "hard-valid" means, so its top-N-by-score candidates aren't
    # necessarily the top-N-by-score-among-valid-ones. Ask for a larger
    # pool and filter here instead of teaching the search about validity.
    pool_size = max(request.num_candidates * 3, 9)
    restarts = max(pool_size * 2, 16)
    search_results = search_layouts(
        nodes=nodes,
        graph=graph,
        buildable=buildable,
        plot=request.plot,
        num_candidates=pool_size,
        restarts=restarts,
        seed=request.seed,
    )

    valid: list[Layout] = []
    best_invalid: tuple[Layout, ValidationResult] | None = None

    for i, sr in enumerate(search_results):
        layout = _build_layout(f"candidate-{i + 1}", sr, nodes, buildable, request, graph)
        result = validate_layout(layout, request.ruleset)

        if result.is_valid:
            valid.append(layout)
            if len(valid) >= request.num_candidates:
                break
        elif best_invalid is None or len(result.violations) < len(best_invalid[1].violations):
            best_invalid = (layout, result)

    if not valid:
        assert best_invalid is not None  # search_results is non-empty since nodes is non-empty
        _, result = best_invalid
        return InfeasibleResult(
            request=request,
            hardest_violations=result.violations,
            message=(
                f"No candidate layout satisfied every hard constraint out of "
                f"{len(search_results)} searched. Closest attempt had "
                f"{len(result.violations)} violation(s) -- see hardest_violations."
            ),
        )

    # Re-sequence IDs so they're contiguous among the *valid* set (a layout
    # that was internally candidate-4 because 1-3 failed validation should
    # still present to the user as candidate-1 if it's their best option).
    for i, layout in enumerate(valid):
        layout.candidate_id = f"candidate-{i + 1}"

    return valid
