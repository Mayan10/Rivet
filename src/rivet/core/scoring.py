"""Fitness function used to rank candidate layouts.

The layout engine treats this as the objective to minimize (as a penalty)
during simulated annealing, and the generator uses the derived 0-100
``score`` to rank and present the final candidates.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .geometry import entrance_edge, on_boundary, room_touches_edge, shared_wall
from .graph import RoomNode
from .models import PlotSpec, Rect
from .rules import ADJACENCY_AVOID, ENTRANCE_COMPATIBLE_ROOMS, is_avoided_adjacency

# Penalty weights. Larger = "more of a hard constraint". These are tuned so
# that a single serious violation (a room below minimum width, two avoided
# room types sharing a wall) dominates many small ones, while still letting
# simulated annealing find smooth gradients toward better layouts.
W_AREA_ERROR = 12.0
W_MIN_WIDTH = 45.0
W_ASPECT_RATIO = 18.0
W_ADJACENCY_MISSED = 10.0
W_ADJACENCY_AVOIDED = 55.0
W_EXTERIOR_ACCESS = 28.0
W_ENTRANCE = 14.0

MIN_SHARED_WALL_M = 1.0  # below this, two rects "touching" isn't a usable doorway


@dataclass
class ScoreResult:
    penalty: float
    score: float  # 0-100, higher is better
    breakdown: dict[str, float]
    violations: list[str]


def evaluate(
    nodes: list[RoomNode],
    rects: dict[str, Rect],
    buildable: Rect,
    plot: PlotSpec,
    graph: nx.Graph,
) -> ScoreResult:
    breakdown = {
        "area_error": 0.0,
        "min_width": 0.0,
        "aspect_ratio": 0.0,
        "adjacency_missed": 0.0,
        "adjacency_avoided": 0.0,
        "exterior_access": 0.0,
        "entrance": 0.0,
    }
    violations: list[str] = []

    for node in nodes:
        rect = rects[node.id]

        area_err = abs(rect.area - node.target_area_sqm) / max(node.target_area_sqm, 1e-6)
        breakdown["area_error"] += W_AREA_ERROR * area_err

        if rect.min_side < node.min_width_m:
            deficit = (node.min_width_m - rect.min_side) / node.min_width_m
            breakdown["min_width"] += W_MIN_WIDTH * deficit
            violations.append(
                f"{node.label}: narrowest side {rect.min_side:.2f}m is below the "
                f"{node.min_width_m:.2f}m minimum for this room type."
            )

        if rect.aspect_ratio > node.max_aspect_ratio:
            excess = (rect.aspect_ratio - node.max_aspect_ratio) / node.max_aspect_ratio
            breakdown["aspect_ratio"] += W_ASPECT_RATIO * excess

        if node.exterior_wall_required and not on_boundary(rect, buildable):
            breakdown["exterior_access"] += W_EXTERIOR_ACCESS
            violations.append(f"{node.label} has no exterior wall for daylight/ventilation.")

    # Adjacency: graph edges we want realized as a shared wall.
    for u, v, data in graph.edges(data=True):
        wall = shared_wall(rects[u], rects[v], min_length=MIN_SHARED_WALL_M)
        if wall is None:
            breakdown["adjacency_missed"] += W_ADJACENCY_MISSED * data.get("weight", 1.0)

    # Hard avoidances: penalize even though we never add a graph edge for them,
    # since the slicing search could still place them side by side by chance.
    node_by_id = {n.id: n for n in nodes}
    ids = list(rects.keys())
    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1 :]:
            a, b = node_by_id[a_id], node_by_id[b_id]
            if is_avoided_adjacency(a.room_type, b.room_type) and shared_wall(
                rects[a_id], rects[b_id], min_length=MIN_SHARED_WALL_M
            ):
                breakdown["adjacency_avoided"] += W_ADJACENCY_AVOIDED
                violations.append(
                    f"{a.label} and {b.label} share a wall but shouldn't (avoided adjacency)."
                )

    # Entrance: the plot-boundary edge the front door sits on should be
    # reachable from an entrance-compatible room (foyer/living/corridor/garage).
    edge = entrance_edge(plot.entrance)
    edge_rooms = [n for n in nodes if room_touches_edge(rects[n.id], buildable, edge)]
    if edge_rooms and not any(n.room_type in ENTRANCE_COMPATIBLE_ROOMS for n in edge_rooms):
        breakdown["entrance"] += W_ENTRANCE
        violations.append(
            f"The {plot.entrance.value} entrance wall opens directly into "
            f"{', '.join(n.label for n in edge_rooms)} instead of a foyer/living space."
        )

    penalty = sum(breakdown.values())
    score = round(max(0.0, 100.0 - penalty), 1)
    return ScoreResult(penalty=penalty, score=score, breakdown=breakdown, violations=violations)


__all__ = [
    "ADJACENCY_AVOID",
    "ScoreResult",
    "evaluate",
]
