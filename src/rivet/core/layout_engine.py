"""Procedural layout search.

The approach is a classic technique from slicing-floorplan optimization
(common in VLSI/architectural layout literature): a permutation of rooms
fully determines a guillotine-cut ("slicing tree") subdivision of the
buildable rectangle, so simulated annealing can search directly over room
*orderings* rather than raw coordinates. Every permutation is guaranteed to
tile the rectangle exactly (no overlaps, no gaps), so the search never has
to reject invalid geometry — it only has to get *better* geometry.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import networkx as nx

from .graph import RoomNode
from .models import PlotSpec, Rect
from .scoring import ScoreResult, evaluate


@dataclass
class SearchResult:
    order: list[RoomNode]
    rects: dict[str, Rect]
    result: ScoreResult


def slice_tree(rect: Rect, nodes: list[RoomNode]) -> dict[str, Rect]:
    """Recursively subdivide ``rect`` for ``nodes`` in the given order.

    The split point is chosen as the prefix whose cumulative target area is
    closest to half the group's total target area (a balanced binary cut),
    and the cut axis is always the rectangle's longer side, which keeps
    sub-rectangles closer to square as recursion deepens.
    """
    if len(nodes) == 1:
        return {nodes[0].id: rect}

    total = sum(n.target_area_sqm for n in nodes)
    cum = 0.0
    best_k, best_diff = 1, math.inf
    for k in range(1, len(nodes)):
        cum += nodes[k - 1].target_area_sqm
        diff = abs(cum / total - 0.5)
        if diff < best_diff:
            best_diff = diff
            best_k = k

    left, right = nodes[:best_k], nodes[best_k:]
    left_ratio = sum(n.target_area_sqm for n in left) / total

    if rect.w >= rect.h:
        split = rect.x + rect.w * left_ratio
        rect_left = Rect(rect.x, rect.y, split - rect.x, rect.h)
        rect_right = Rect(split, rect.y, rect.x2 - split, rect.h)
    else:
        split = rect.y + rect.h * left_ratio
        rect_left = Rect(rect.x, rect.y, rect.w, split - rect.y)
        rect_right = Rect(rect.x, split, rect.w, rect.y2 - split)

    out = slice_tree(rect_left, left)
    out.update(slice_tree(rect_right, right))
    return out


def _graph_guided_order(nodes: list[RoomNode], graph: nx.Graph, rng: random.Random) -> list[RoomNode]:
    """A DFS-ish traversal that keeps strongly-connected rooms close together
    in the ordering, which the slicing tree tends to keep close in space.
    """
    by_id = {n.id: n for n in nodes}
    # A dict (not a set) so iteration order is insertion order -- fixed and
    # reproducible -- rather than hash-seed dependent. Every loop below
    # draws from ``rng`` while iterating ``remaining``, so a hash-randomized
    # iteration order would make the *same* seed produce different results
    # across separate process runs (a set's order depends on PYTHONHASHSEED,
    # which is randomized per-process by default).
    remaining: dict[str, None] = dict.fromkeys(n.id for n in nodes)
    # Start from the node with the highest total edge weight (a natural hub,
    # e.g. the living room), with randomized tie-breaking for search diversity.
    weighted_degree = {n: sum(d.get("weight", 1.0) for _, _, d in graph.edges(n, data=True)) for n in remaining}
    start = max(remaining, key=lambda n: (weighted_degree.get(n, 0.0), rng.random()))

    order: list[RoomNode] = []
    frontier = [start]
    while remaining:
        if not frontier:
            frontier = [max(remaining, key=lambda n: rng.random())]
        current = frontier.pop()
        if current not in remaining:
            continue
        order.append(by_id[current])
        del remaining[current]

        neighbors = [
            (nbr, graph[current][nbr].get("weight", 1.0))
            for nbr in graph.neighbors(current)
            if nbr in remaining
        ]
        neighbors.sort(key=lambda t: (t[1], rng.random()), reverse=True)
        frontier.extend(nbr for nbr, _ in neighbors)

    return order


def _anneal(
    initial_order: list[RoomNode],
    buildable: Rect,
    graph: nx.Graph,
    nodes: list[RoomNode],
    plot: PlotSpec,
    rng: random.Random,
    iterations: int = 400,
) -> SearchResult:
    order = list(initial_order)
    rects = slice_tree(buildable, order)
    result = evaluate(nodes, rects, buildable, plot, graph)

    best_order, best_rects, best_result = order, rects, result

    temperature = 8.0
    cooling = 0.985

    for _ in range(iterations):
        candidate = list(order)
        move = rng.random()
        if len(candidate) >= 2:
            if move < 0.6:
                i, j = rng.sample(range(len(candidate)), 2)
                candidate[i], candidate[j] = candidate[j], candidate[i]
            else:
                i, j = sorted(rng.sample(range(len(candidate)), 2))
                candidate[i : j + 1] = reversed(candidate[i : j + 1])

        candidate_rects = slice_tree(buildable, candidate)
        candidate_result = evaluate(nodes, candidate_rects, buildable, plot, graph)

        delta = candidate_result.penalty - result.penalty
        if delta < 0 or rng.random() < math.exp(-delta / max(temperature, 1e-6)):
            order, rects, result = candidate, candidate_rects, candidate_result
            if result.penalty < best_result.penalty:
                best_order, best_rects, best_result = order, rects, result

        temperature *= cooling

    return SearchResult(order=best_order, rects=best_rects, result=best_result)


def search_layouts(
    nodes: list[RoomNode],
    graph: nx.Graph,
    buildable: Rect,
    plot: PlotSpec,
    num_candidates: int = 3,
    restarts: int = 8,
    iterations_per_restart: int = 400,
    seed: int | None = None,
) -> list[SearchResult]:
    """Multi-start simulated annealing over room orderings.

    Returns up to ``num_candidates`` distinct results, best score first.
    """
    rng = random.Random(seed)
    results: list[SearchResult] = []

    for restart in range(restarts):
        if restart == 0:
            order = sorted(nodes, key=lambda n: n.target_area_sqm, reverse=True)
        elif restart % 2 == 1:
            order = _graph_guided_order(nodes, graph, rng)
        else:
            order = list(nodes)
            rng.shuffle(order)

        results.append(_anneal(order, buildable, graph, nodes, plot, rng, iterations_per_restart))

    results.sort(key=lambda r: r.result.penalty)

    # De-duplicate near-identical layouts (same rects up to rounding) so the
    # user sees genuinely different options, not the same optimum eight times.
    distinct: list[SearchResult] = []
    seen_signatures: set[tuple] = set()
    for r in results:
        signature = tuple(
            sorted((rid, round(rect.x, 1), round(rect.y, 1), round(rect.w, 1), round(rect.h, 1)) for rid, rect in r.rects.items())
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        distinct.append(r)
        if len(distinct) >= num_candidates:
            break

    return distinct
