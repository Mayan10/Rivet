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

from dataclasses import dataclass, field

import networkx as nx

from .geometry import MIN_USABLE_SHARED_WALL_M, entrance_edge, room_touches_edge, shared_wall
from .graph import RoomNode
from .models import PlotSpec, Rect, VastuOptions
from .rules import (
    ADJACENCY_AVOID,
    CIRCULATION_TARGET_PCT_MAX,
    CIRCULATION_TARGET_PCT_MIN,
    ENTRANCE_COMPATIBLE_ROOMS,
    is_avoided_adjacency,
)
from .vastu import VastuPreferenceResult, evaluate_vastu

# Penalty weights. These are tuned so that a single serious soft issue
# dominates many small ones, while still letting simulated annealing find
# smooth gradients toward better layouts. Hard constraints have no weight
# here at all -- see core/validator.py.
W_AREA_ERROR = 12.0
W_ASPECT_RATIO = 18.0
W_ADJACENCY_MISSED = 10.0
W_ADJACENCY_AVOIDED = 55.0
W_ENTRANCE = 14.0
W_CIRCULATION = 6.0


@dataclass
class ScoreResult:
    penalty: float
    score: float  # 0-100, higher is better
    breakdown: dict[str, float]
    violations: list[str]
    # Empty unless vastu was enabled -- kept separate from `breakdown`
    # (never merged into that plain float dict) so a consumer can never
    # confuse a vastu preference with a code-compliance figure. See
    # core/vastu.py and docs/design_rules.md "Vastu".
    vastu_preferences: list[VastuPreferenceResult] = field(default_factory=list)


def evaluate(
    nodes: list[RoomNode],
    rects: dict[str, Rect],
    buildable: Rect,
    plot: PlotSpec,
    graph: nx.Graph,
    corridor_ids: frozenset[str] = frozenset(),
    vastu: VastuOptions | None = None,
) -> ScoreResult:
    breakdown = {
        "area_error": 0.0,
        "aspect_ratio": 0.0,
        "adjacency_missed": 0.0,
        "adjacency_avoided": 0.0,
        "entrance": 0.0,
        "circulation": 0.0,
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
    # Only real rooms participate -- `rects` also carries circulation
    # segments (Phase 3), which aren't in `nodes` and have no room_type to
    # check an avoided-adjacency rule against.
    node_by_id = {n.id: n for n in nodes}
    ids = [n.id for n in nodes]
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
    # Since Phase 3, the entrance edge is usually the root circulation
    # segment itself (the whole point of tying its axis to plot.entrance) --
    # `edge_rooms` only inspects real rooms, so a corridor-only entrance
    # wall leaves it empty and this check is silently satisfied, which is
    # the best case, not a gap: a corridor at the door is strictly better
    # than a foyer/living room there.
    edge = entrance_edge(plot.entrance)
    edge_rooms = [n for n in nodes if room_touches_edge(rects[n.id], buildable, edge)]
    if edge_rooms and not any(n.room_type in ENTRANCE_COMPATIBLE_ROOMS for n in edge_rooms):
        breakdown["entrance"] += W_ENTRANCE
        violations.append(
            f"The {plot.entrance.value} entrance wall opens directly into "
            f"{', '.join(n.label for n in edge_rooms)} instead of a foyer/living space."
        )

    # Circulation: soft target band as a % of buildable area -- a proxy for
    # built-up area that's good enough to guide the search; core/metrics.py
    # computes the real built-up-area-based figure for reporting (Phase 2).
    if corridor_ids:
        circulation_area = sum(rects[cid].area for cid in corridor_ids if cid in rects)
        circulation_pct = (circulation_area / buildable.area * 100) if buildable.area > 0 else 0.0
        if circulation_pct < CIRCULATION_TARGET_PCT_MIN:
            deficit = (CIRCULATION_TARGET_PCT_MIN - circulation_pct) / CIRCULATION_TARGET_PCT_MIN
            breakdown["circulation"] += W_CIRCULATION * deficit
        elif circulation_pct > CIRCULATION_TARGET_PCT_MAX:
            excess = (circulation_pct - CIRCULATION_TARGET_PCT_MAX) / CIRCULATION_TARGET_PCT_MAX
            breakdown["circulation"] += W_CIRCULATION * excess

    vastu_preferences: list[VastuPreferenceResult] = []
    if vastu is not None and vastu.enabled:
        vastu_result = evaluate_vastu(nodes, rects, buildable, plot, vastu)
        breakdown["vastu"] = vastu_result.penalty
        vastu_preferences = vastu_result.preferences

    penalty = sum(breakdown.values())
    score = round(max(0.0, 100.0 - penalty), 1)
    return ScoreResult(
        penalty=penalty, score=score, breakdown=breakdown, violations=violations, vastu_preferences=vastu_preferences
    )


__all__ = [
    "ADJACENCY_AVOID",
    "ScoreResult",
    "evaluate",
]
