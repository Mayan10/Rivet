"""Procedural layout search.

The approach is a classic technique from slicing-floorplan optimization
(common in VLSI/architectural layout literature): a permutation of rooms
fully determines a guillotine-cut ("slicing tree") subdivision of the
buildable rectangle, so simulated annealing can search directly over room
*orderings* rather than raw coordinates. Every permutation is guaranteed to
tile the rectangle exactly (no overlaps, no gaps), so the search never has
to reject invalid geometry — it only has to get *better* geometry.

``build_circulation_layout`` (Phase 3, docs/prompts.md) extends this with
one added rule so the result is a navigable house, not just a valid
tiling: see its docstring and ``docs/architecture.md`` "Circulation" for
the full design. It reuses ``slice_tree`` and the same permutation-driven
determinism guarantee unchanged -- the simulated annealing in ``_anneal``
below needed zero new move types to support it, since the whole corridor
tree is (like the room geometry always was) a pure function of the room
ordering.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import networkx as nx

from .graph import RoomNode
from .models import Orientation, PlotSpec, Rect, VastuOptions
from .rules import (
    CIRCULATION_CORRIDOR_WIDTH_M,
    CIRCULATION_SINGLE_LOAD_THRESHOLD,
    min_door_clear_wall_m,
)
from .scoring import ScoreResult, evaluate


@dataclass
class SearchResult:
    order: list[RoomNode]
    rects: dict[str, Rect]
    corridor_ids: frozenset[str]
    result: ScoreResult


def _balanced_split_index(areas: list[float]) -> int:
    """Index ``k`` (``1 <= k < len(areas)``) splitting a sequence into
    ``areas[:k]`` / ``areas[k:]`` such that the cumulative area up to
    ``k`` is as close as possible to half the total. Shared by
    ``slice_tree`` (per-room) and the circulation splitter (per-slot) so
    both use the same balanced-cut logic.
    """
    total = sum(areas)
    cum = 0.0
    best_k, best_diff = 1, math.inf
    for k in range(1, len(areas)):
        cum += areas[k - 1]
        diff = abs(cum / total - 0.5) if total > 0 else 0.0
        if diff < best_diff:
            best_diff = diff
            best_k = k
    return best_k


def slice_tree(rect: Rect, nodes: list[RoomNode]) -> dict[str, Rect]:
    """Recursively subdivide ``rect`` for ``nodes`` in the given order.

    The split point is chosen as the prefix whose cumulative target area is
    closest to half the group's total target area (a balanced binary cut),
    and the cut axis is always the rectangle's longer side, which keeps
    sub-rectangles closer to square as recursion deepens.
    """
    if len(nodes) == 1:
        return {nodes[0].id: rect}

    areas = [n.target_area_sqm for n in nodes]
    total = sum(areas)
    best_k = _balanced_split_index(areas)

    left, right = nodes[:best_k], nodes[best_k:]
    left_ratio = sum(areas[:best_k]) / total if total > 0 else 0.5

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


def _primary_slots(nodes: list[RoomNode]) -> list[list[RoomNode]]:
    """Group an ordered room list into "slots": a lone room, or a
    [bedroom, its en-suite] pair kept together. Order follows ``nodes``
    (the permutation being searched), so this is a deterministic view of
    it, not a re-sort.
    """
    ensuite_by_parent = {n.ensuite_of: n for n in nodes if n.ensuite_of is not None}
    slots: list[list[RoomNode]] = []
    for n in nodes:
        if n.ensuite_of is not None:
            continue  # placed as part of its bedroom's slot below
        slot = [n]
        ensuite = ensuite_by_parent.get(n.id)
        if ensuite is not None:
            slot.append(ensuite)
        slots.append(slot)
    return slots


def _floor_clamped_ratio(ratio: float, min_first: float, min_second: float, total_extent: float) -> float:
    """Clamp a balanced-split ratio so neither side's absolute extent
    drops below ``min_first``/``min_second`` -- the sum, over every node
    on that side, of the shortest wall *that node's own door* needs (see
    ``rules.min_door_clear_wall_m``). That's the right floor for a group
    that will go on to be divided again beneath this split: each node
    still needs at least its own door-fit minimum once fully subdivided.

    Falls back to the raw (unclamped) ratio when the rect is too small to
    satisfy both floors at once: the resulting leaf will then legitimately
    fail the reachability hard check (or min-width), and the request comes
    back as an honest InfeasibleResult rather than this function lying
    about what fits (see CLAUDE.md: no invented code values, and no hard
    constraint quietly softened).
    """
    if total_extent < min_first + min_second:
        return ratio
    lo = min_first / total_extent
    hi = 1 - (min_second / total_extent)
    if lo > hi:
        return ratio
    return min(max(ratio, lo), hi)


def _slice_tree_forced_axis(rect: Rect, nodes: list[RoomNode], stack_along_y: bool) -> dict[str, Rect]:
    """Like ``slice_tree``, but the cut axis is forced (not adaptive) at
    every level of recursion, not just the first. That means every
    resulting room -- however deeply nested, including an en-suite paired
    with its bedroom -- retains the *full* span of whichever dimension
    isn't being cut, all the way down.

    This is what makes it safe for a leaf cluster bordering a corridor:
    the room needing corridor access (and possibly *also* exterior-wall
    access, both hard requirements that must hold simultaneously) always
    keeps both ends of that dimension, no matter where a split happens to
    place it relative to its en-suite. An earlier version of this function
    split an en-suite pair *along* the corridor-facing dimension,
    specifically to steer the bedroom onto the corridor side -- which
    reliably gave it corridor access but just as reliably cost it exterior
    access (or vice versa), since the two ends of that dimension were now
    split between the bedroom and its en-suite instead of both staying
    with the bedroom.
    """
    if len(nodes) == 1:
        return {nodes[0].id: rect}

    areas = [n.target_area_sqm for n in nodes]
    total = sum(areas)
    best_k = _balanced_split_index(areas)
    first, second = nodes[:best_k], nodes[best_k:]
    first_ratio = sum(areas[:best_k]) / total if total > 0 else 0.5
    min_first = sum(min_door_clear_wall_m(n.room_type) for n in first)
    min_second = sum(min_door_clear_wall_m(n.room_type) for n in second)

    if stack_along_y:
        first_ratio = _floor_clamped_ratio(first_ratio, min_first, min_second, rect.h)
        split = rect.y + rect.h * first_ratio
        rect_a = Rect(rect.x, rect.y, rect.w, split - rect.y)
        rect_b = Rect(rect.x, split, rect.w, rect.y2 - split)
    else:
        first_ratio = _floor_clamped_ratio(first_ratio, min_first, min_second, rect.w)
        split = rect.x + rect.w * first_ratio
        rect_a = Rect(rect.x, rect.y, split - rect.x, rect.h)
        rect_b = Rect(split, rect.y, rect.x2 - split, rect.h)

    out = _slice_tree_forced_axis(rect_a, first, stack_along_y)
    out.update(_slice_tree_forced_axis(rect_b, second, stack_along_y))
    return out


def _slice_tree_bordering(rect: Rect, slots: list[list[RoomNode]], corridor_side: str) -> dict[str, Rect]:
    """Place a small cluster of slots within ``rect``, forcing every split
    (at every depth, including within an en-suite pair) to run parallel to
    the edge bordering the corridor, so every resulting room touches it --
    not just the cluster's outer rect.

    ``corridor_side`` names which edge of ``rect`` the corridor is on:
    "left"/"right" means rooms must be stacked in bands along y (each
    spanning the full width, so each reaches the left/right edge);
    "top"/"bottom" means stacked along x (each spanning the full height).
    """
    nodes = [n for slot in slots for n in slot]
    stack_along_y = corridor_side in ("left", "right")
    return _slice_tree_forced_axis(rect, nodes, stack_along_y)


def build_circulation_layout(
    buildable: Rect, nodes: list[RoomNode], entrance: Orientation
) -> tuple[dict[str, Rect], frozenset[str]]:
    """Circulation-aware counterpart to ``slice_tree``: the same
    permutation-driven guillotine subdivision, plus one added rule.

    At the root (the whole buildable rect), a corridor is always inserted
    -- split perpendicular to the entrance wall, so the corridor starts
    there and the front door opens onto it -- unless the entire request is
    a single room (nothing to connect). Below the root, a corridor is
    inserted again wherever a sub-cluster still holds more than
    ``CIRCULATION_SINGLE_LOAD_THRESHOLD`` primary rooms (en-suites nest
    with their bedroom and don't count); anything at or under the
    threshold is placed directly with ``_slice_tree_bordering`` so every
    room in it touches the corridor immediately bounding it.

    Because a subtree's room count can never exceed its parent's, this
    rule is monotonic top-down: any corridor inserted below the root
    implies every ancestor split up to the root was *also* a corridor
    split. The whole corridor tree is therefore transitively connected
    back to the entrance by construction, and every leaf room touches
    whichever corridor immediately bounds it -- reachability doesn't
    depend on the search finding it, only on this rule always being
    applied the same way for a given room ordering.

    Returns ``(rects, corridor_ids)`` where ``rects`` covers both rooms
    and corridor segments (IDs ``"circulation_1"``, ``"circulation_2"``,
    ... -- distinct from the ``"corridor_1"`` style IDs an explicitly
    *requested* CORRIDOR room gets from
    ``graph.expand_room_requirements``, so the two never collide).
    """
    rects: dict[str, Rect] = {}
    corridor_ids: set[str] = set()
    counter = [0]

    def next_corridor_id() -> str:
        counter[0] += 1
        return f"circulation_{counter[0]}"

    def do_split(rect: Rect, slots: list[list[RoomNode]], axis_vertical: bool):
        areas = [sum(n.target_area_sqm for n in slot) for slot in slots]
        total = sum(areas)
        best_k = _balanced_split_index(areas)
        slots_a, slots_b = slots[:best_k], slots[best_k:]
        ratio_a = sum(areas[:best_k]) / total if total > 0 else 0.5
        width = CIRCULATION_CORRIDOR_WIDTH_M

        # No door-fit floor applied to this split: unlike
        # _slice_tree_forced_axis (which divides a wing's *stacking* axis
        # per room, so each node needs its own floor), this axis becomes
        # every resulting room's shared *depth* -- inherited whole by every
        # node in that wing, not divided per node. The real per-room floor
        # is enforced where the stacking division actually happens, below.
        if axis_vertical:
            available = max(rect.w - width, 0.0)
            w_a = available * ratio_a
            rect_a = Rect(rect.x, rect.y, w_a, rect.h)
            corridor_rect = Rect(rect.x + w_a, rect.y, width, rect.h)
            rect_b = Rect(rect.x + w_a + width, rect.y, available - w_a, rect.h)
            side_a, side_b = "right", "left"
        else:
            available = max(rect.h - width, 0.0)
            h_a = available * ratio_a
            rect_a = Rect(rect.x, rect.y, rect.w, h_a)
            corridor_rect = Rect(rect.x, rect.y + h_a, rect.w, width)
            rect_b = Rect(rect.x, rect.y + h_a + width, rect.w, available - h_a)
            side_a, side_b = "top", "bottom"

        return corridor_rect, rect_a, rect_b, side_a, side_b, slots_a, slots_b

    def recurse(rect: Rect, slots: list[list[RoomNode]], corridor_side: str | None, forced_axis_vertical: bool | None):
        is_root = corridor_side is None

        if len(slots) == 1:
            slot = slots[0]
            if len(slot) == 1:
                rects[slot[0].id] = rect
            elif is_root:
                # No corridor exists at all (the whole request is this one
                # bedroom + its en-suite) -- nothing to orient towards.
                rects.update(slice_tree(rect, slot))
            else:
                rects.update(_slice_tree_forced_axis(rect, slot, corridor_side in ("left", "right")))
            return

        should_split = is_root or len(slots) > CIRCULATION_SINGLE_LOAD_THRESHOLD
        if not should_split:
            rects.update(_slice_tree_bordering(rect, slots, corridor_side))
            return

        if forced_axis_vertical is not None:
            axis_vertical = forced_axis_vertical  # root: tied to entrance orientation
        else:
            # Nested split: `rect` already spans from some ancestor
            # exterior wall to `corridor_side` (its nearest corridor).
            # The new corridor must run parallel to that span -- i.e. its
            # axis is forced by corridor_side, exactly the same rule
            # _slice_tree_bordering uses -- not chosen adaptively by
            # rect's aspect ratio. An adaptive choice can cut *across*
            # that span instead of along it, producing a child that
            # touches neither the exterior wall nor any corridor.
            axis_vertical = corridor_side in ("top", "bottom")
        corridor_rect, rect_a, rect_b, side_a, side_b, slots_a, slots_b = do_split(rect, slots, axis_vertical)
        cid = next_corridor_id()
        rects[cid] = corridor_rect
        corridor_ids.add(cid)
        recurse(rect_a, slots_a, side_a, None)
        recurse(rect_b, slots_b, side_b, None)

    root_axis_vertical = entrance in (Orientation.NORTH, Orientation.SOUTH)
    recurse(buildable, _primary_slots(nodes), corridor_side=None, forced_axis_vertical=root_axis_vertical)

    return rects, frozenset(corridor_ids)


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
    vastu: VastuOptions | None = None,
) -> SearchResult:
    order = list(initial_order)
    rects, corridor_ids = build_circulation_layout(buildable, order, plot.entrance)
    result = evaluate(nodes, rects, buildable, plot, graph, corridor_ids=corridor_ids, vastu=vastu)

    best_order, best_rects, best_corridor_ids, best_result = order, rects, corridor_ids, result

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

        candidate_rects, candidate_corridor_ids = build_circulation_layout(buildable, candidate, plot.entrance)
        candidate_result = evaluate(
            nodes, candidate_rects, buildable, plot, graph, corridor_ids=candidate_corridor_ids, vastu=vastu
        )

        delta = candidate_result.penalty - result.penalty
        if delta < 0 or rng.random() < math.exp(-delta / max(temperature, 1e-6)):
            order, rects, corridor_ids, result = candidate, candidate_rects, candidate_corridor_ids, candidate_result
            if result.penalty < best_result.penalty:
                best_order, best_rects, best_corridor_ids, best_result = order, rects, corridor_ids, result

        temperature *= cooling

    return SearchResult(order=best_order, rects=best_rects, corridor_ids=best_corridor_ids, result=best_result)


def search_layouts(
    nodes: list[RoomNode],
    graph: nx.Graph,
    buildable: Rect,
    plot: PlotSpec,
    num_candidates: int = 3,
    restarts: int = 8,
    iterations_per_restart: int = 400,
    seed: int | None = None,
    vastu: VastuOptions | None = None,
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

        results.append(_anneal(order, buildable, graph, nodes, plot, rng, iterations_per_restart, vastu=vastu))

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
