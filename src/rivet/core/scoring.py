"""Fitness function used to rank candidate layouts -- soft preferences only.

Everything in this module is advisory: it guides the simulated-annealing
search toward nicer layouts, but nothing here ever rejects one. Hard
building-code minimums (room area/width, exterior window access, cited
avoided adjacencies, setback compliance) are enforced by
``core/validator.py`` against the final geometry, not scored here -- see
Phase 1 in ``docs/prompts.md`` for why that split matters. The scorer keeps
a *soft* nudge against the full ``ADJACENCY_AVOID`` set (including the
cited pairs the validator hard-rejects) purely as a search-efficiency
aid -- steering the search away from a violation before validation ever
runs doesn't change what gets rejected, it just means fewer candidates get
discarded after the fact.

The layout engine treats this as the objective to minimize (as a penalty)
during simulated annealing, and the generator uses the derived 0-100
``score`` to rank and present the final candidates.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from .geometry import MIN_USABLE_SHARED_WALL_M, entrance_edge, room_touches_edge, shared_wall
from .graph import RoomNode
from .models import PlotSpec, Rect
from .rules import ADJACENCY_AVOID, ENTRANCE_COMPATIBLE_ROOMS, is_avoided_adjacency

# Penalty weights. These are tuned so that a single serious soft issue
# dominates many small ones, while still letting simulated annealing find
# smooth gradients toward better layouts. Hard constraints have no weight
# here at all -- see core/validator.py.
W_AREA_ERROR = 12.0
W_ASPECT_RATIO = 18.0
W_ADJACENCY_MISSED = 10.0
W_ADJACENCY_AVOIDED = 55.0
W_ENTRANCE = 14.0


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
        "aspect_ratio": 0.0,
        "adjacency_missed": 0.0,
        "adjacency_avoided": 0.0,
        "entrance": 0.0,
    }
    violations: list[str] = []

    for node in nodes:
        rect = rects[node.id]

        area_err = abs(rect.area - node.target_area_sqm) / max(node.target_area_sqm, 1e-6)
        breakdown["area_error"] += W_AREA_ERROR * area_err

        if rect.aspect_ratio > node.max_aspect_ratio:
            excess = (rect.aspect_ratio - node.max_aspect_ratio) / node.max_aspect_ratio
            breakdown["aspect_ratio"] += W_ASPECT_RATIO * excess

    # Adjacency: graph edges we want realized as a shared wall.
    for u, v, data in graph.edges(data=True):
        wall = shared_wall(rects[u], rects[v], min_length=MIN_USABLE_SHARED_WALL_M)
        if wall is None:
            breakdown["adjacency_missed"] += W_ADJACENCY_MISSED * data.get("weight", 1.0)

    # Avoided adjacencies: penalize even though we never add a graph edge for
    # them, since the slicing search could still place them side by side by
    # chance. Includes the cited (hard) pairs too -- see module docstring.
    node_by_id = {n.id: n for n in nodes}
    ids = list(rects.keys())
    for i, a_id in enumerate(ids):
        for b_id in ids[i + 1 :]:
            a, b = node_by_id[a_id], node_by_id[b_id]
            if is_avoided_adjacency(a.room_type, b.room_type) and shared_wall(
                rects[a_id], rects[b_id], min_length=MIN_USABLE_SHARED_WALL_M
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
