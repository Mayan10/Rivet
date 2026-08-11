"""High-level entry point: a :class:`GenerationRequest` in, ranked
:class:`Layout` candidates out.

This is the only function most callers (the CLI, the API) need to know
about — it wires together the graph builder, the layout search, and the
opening placer.
"""

from __future__ import annotations

from .graph import build_adjacency_graph, expand_room_requirements
from .layout_engine import search_layouts
from .models import GenerationRequest, Layout, Rect, RoomInstance
from .openings import place_openings
from .rules import setbacks_for


def compute_buildable_rect(request: GenerationRequest) -> Rect:
    plot = request.plot
    setbacks = setbacks_for(plot.area_sqm)
    w = plot.width_m - 2 * setbacks.side_m
    h = plot.length_m - setbacks.front_m - setbacks.rear_m
    if w <= 0 or h <= 0:
        raise ValueError(
            f"Plot {plot.width_m}m x {plot.length_m}m leaves no buildable area once "
            f"setbacks (side {setbacks.side_m}m, front {setbacks.front_m}m, "
            f"rear {setbacks.rear_m}m) are applied."
        )
    return Rect(x=setbacks.side_m, y=setbacks.rear_m, w=w, h=h)


def generate(request: GenerationRequest) -> list[Layout]:
    buildable = compute_buildable_rect(request)

    nodes = expand_room_requirements(request.rooms)
    if not nodes:
        raise ValueError("The request produced no rooms to place")

    graph = build_adjacency_graph(nodes)

    search_results = search_layouts(
        nodes=nodes,
        graph=graph,
        buildable=buildable,
        plot=request.plot,
        num_candidates=request.num_candidates,
        seed=request.seed,
    )

    layouts: list[Layout] = []
    for i, sr in enumerate(search_results):
        rooms = [
            RoomInstance(id=n.id, room_type=n.room_type, label=n.label, rect=sr.rects[n.id])
            for n in nodes
        ]
        openings = place_openings(nodes, sr.rects, buildable, request.plot, graph)
        layouts.append(
            Layout(
                candidate_id=f"candidate-{i + 1}",
                plot=request.plot,
                buildable=buildable,
                rooms=rooms,
                openings=openings,
                score=sr.result.score,
                score_breakdown=sr.result.breakdown,
                violations=sr.result.violations,
            )
        )

    return layouts
