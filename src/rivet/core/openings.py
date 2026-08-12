"""Places doors on shared walls between adjacent rooms and windows on
exterior-facing walls of habitable rooms.

Since Phase 3 (docs/prompts.md), every layout also carries one or more
auto-generated circulation segments (see core/layout_engine.py's
``build_circulation_layout``) that this module treats as door hosts too:
every non-en-suite room gets a door onto whichever corridor immediately
borders it, and the main entrance door opens onto the corridor whenever
one occupies the entrance wall (the common case, since the root corridor
is specifically oriented to touch it).
"""

from __future__ import annotations

import networkx as nx

from .geometry import boundary_edges, entrance_edge, room_touches_edge, shared_wall
from .graph import RoomNode
from .models import Opening, PlotSpec, Rect
from .rules import (
    DOOR_WIDTH_MAIN_M,
    ENTRANCE_COMPATIBLE_ROOMS,
    MIN_DOOR_CLEAR_WALL_M,
    MIN_OPENING_EDGE_CLEARANCE_M,
    door_width_for,
    window_width_for,
)


def _clamp_position(desired_mid: float, width: float, lo: float, hi: float) -> float:
    """Center an opening of ``width`` on ``desired_mid``, kept within
    [lo, hi] and clear of the wall's corners.
    """
    start = desired_mid - width / 2
    max_start = max(lo, hi - width)
    return min(max(start, lo), max_start)


def _door_on_shared_wall(room_id: str, other_id: str, wall, width: float, kind: str = "door") -> Opening | None:
    lo, hi = wall.lo + MIN_OPENING_EDGE_CLEARANCE_M, wall.hi - MIN_OPENING_EDGE_CLEARANCE_M
    if hi - lo < width:
        return None
    pos = _clamp_position(wall.mid, width, lo, hi)
    if wall.axis == "vertical":
        x, y = wall.coord, pos
    else:
        x, y = pos, wall.coord
    return Opening(kind=kind, x=x, y=y, width=width, axis=wall.axis, room_id=room_id, connects_to=other_id)


def _junction_opening(a_id: str, b_id: str, wall, width: float) -> Opening:
    """An open connection between two circulation segments, centered on
    their shared wall with no corner clearance subtracted.

    Unlike a room door (``_door_on_shared_wall``), a junction is
    deliberately sized to the *full* width of the narrower corridor (see
    caller) -- subtracting MIN_OPENING_EDGE_CLEARANCE_M from both ends
    would always fail to fit a width that's already the whole wall.
    """
    pos = _clamp_position(wall.mid, width, wall.lo, wall.hi)
    if wall.axis == "vertical":
        x, y = wall.coord, pos
    else:
        x, y = pos, wall.coord
    return Opening(kind="door", x=x, y=y, width=width, axis=wall.axis, room_id=a_id, connects_to=b_id)


def _door_on_boundary_edge(rect: Rect, room_id: str, edge: str, width: float, kind: str) -> Opening | None:
    if edge in ("y2", "y"):
        coord = rect.y2 if edge == "y2" else rect.y
        lo, hi = rect.x + MIN_OPENING_EDGE_CLEARANCE_M, rect.x2 - MIN_OPENING_EDGE_CLEARANCE_M
        if hi - lo < width:
            return None
        x = _clamp_position(rect.cx, width, lo, hi)
        return Opening(kind=kind, x=x, y=coord, width=width, axis="horizontal", room_id=room_id)

    coord = rect.x2 if edge == "x2" else rect.x
    lo, hi = rect.y + MIN_OPENING_EDGE_CLEARANCE_M, rect.y2 - MIN_OPENING_EDGE_CLEARANCE_M
    if hi - lo < width:
        return None
    y = _clamp_position(rect.cy, width, lo, hi)
    return Opening(kind=kind, x=coord, y=y, width=width, axis="vertical", room_id=room_id)


def _place_interior_doors(
    nodes: list[RoomNode], rects: dict[str, Rect], graph: nx.Graph
) -> list[Opening]:
    by_id = {n.id: n for n in nodes}
    openings: list[Opening] = []

    for u, v, _data in graph.edges(data=True):
        wall = shared_wall(rects[u], rects[v], min_length=MIN_DOOR_CLEAR_WALL_M)
        if wall is None:
            continue
        width = min(door_width_for(by_id[u].room_type), door_width_for(by_id[v].room_type))
        opening = _door_on_shared_wall(u, v, wall, width)
        if opening is not None:
            openings.append(opening)

    return openings


def _place_corridor_doors(
    nodes: list[RoomNode], rects: dict[str, Rect], corridor_ids: frozenset[str]
) -> list[Opening]:
    """A door between every non-en-suite room and whichever corridor
    segment(s) it touches, plus between corridor segments that meet each
    other (a branch corridor joining its parent).

    En-suite bathrooms are deliberately excluded: they connect only via
    their own bedroom's door, never directly to circulation, the same
    reachability exception ``core/validator.py`` honors.
    """
    openings: list[Opening] = []
    ensuite_ids = {n.id for n in nodes if n.ensuite_of is not None}

    for node in nodes:
        if node.id in ensuite_ids:
            continue
        for cid in corridor_ids:
            if cid not in rects:
                continue
            wall = shared_wall(rects[node.id], rects[cid], min_length=MIN_DOOR_CLEAR_WALL_M)
            if wall is None:
                continue
            width = door_width_for(node.room_type)
            opening = _door_on_shared_wall(node.id, cid, wall, width)
            if opening is not None:
                openings.append(opening)
                break  # one corridor connection is enough per room

    corridor_list = sorted(corridor_ids)
    for i, a in enumerate(corridor_list):
        if a not in rects:
            continue
        for b in corridor_list[i + 1 :]:
            if b not in rects:
                continue
            wall = shared_wall(rects[a], rects[b], min_length=MIN_DOOR_CLEAR_WALL_M)
            if wall is None:
                continue
            # A junction between two circulation segments is an open
            # connection, not a room door -- as wide as the narrower
            # corridor rather than a fixed door width.
            width = min(wall.length, rects[a].min_side, rects[b].min_side)
            openings.append(_junction_opening(a, b, wall, width))

    return openings


def _place_main_door(
    nodes: list[RoomNode],
    rects: dict[str, Rect],
    buildable: Rect,
    plot: PlotSpec,
    corridor_ids: frozenset[str],
) -> Opening | None:
    edge = entrance_edge(plot.entrance)

    # Corridors first: the root circulation segment is specifically
    # oriented (core/layout_engine.py) to touch the entrance wall, so this
    # is the common case since Phase 3.
    for cid in sorted(corridor_ids):
        if cid in rects and room_touches_edge(rects[cid], buildable, edge):
            opening = _door_on_boundary_edge(rects[cid], cid, edge, DOOR_WIDTH_MAIN_M, kind="main_door")
            if opening is not None:
                return opening

    on_edge = [n for n in nodes if room_touches_edge(rects[n.id], buildable, edge)]
    if not on_edge:
        return None

    preferred = [n for n in on_edge if n.room_type in ENTRANCE_COMPATIBLE_ROOMS]
    host = preferred[0] if preferred else on_edge[0]
    return _door_on_boundary_edge(rects[host.id], host.id, edge, DOOR_WIDTH_MAIN_M, kind="main_door")


def _place_windows(nodes: list[RoomNode], rects: dict[str, Rect], buildable: Rect) -> list[Opening]:
    openings: list[Opening] = []
    for node in nodes:
        if not node.exterior_wall_required:
            continue
        edges = boundary_edges(rects[node.id], buildable)
        if not edges:
            continue

        edge = max(edges, key=lambda e: e.length)
        width = window_width_for(node.room_type)
        if edge.length < width + 2 * MIN_OPENING_EDGE_CLEARANCE_M:
            width = edge.length - 2 * MIN_OPENING_EDGE_CLEARANCE_M
            if width < 0.5:
                continue

        lo, hi = edge.lo + MIN_OPENING_EDGE_CLEARANCE_M, edge.hi - MIN_OPENING_EDGE_CLEARANCE_M
        pos = _clamp_position(edge.mid, width, lo, hi)

        if edge.axis == "horizontal":
            openings.append(
                Opening(kind="window", x=pos, y=edge.coord, width=width, axis="horizontal", room_id=node.id)
            )
        else:
            openings.append(
                Opening(kind="window", x=edge.coord, y=pos, width=width, axis="vertical", room_id=node.id)
            )
    return openings


def place_openings(
    nodes: list[RoomNode],
    rects: dict[str, Rect],
    buildable: Rect,
    plot: PlotSpec,
    graph: nx.Graph,
    corridor_ids: frozenset[str] = frozenset(),
) -> list[Opening]:
    openings = _place_interior_doors(nodes, rects, graph)
    openings.extend(_place_corridor_doors(nodes, rects, corridor_ids))

    main_door = _place_main_door(nodes, rects, buildable, plot, corridor_ids)
    if main_door is not None:
        openings.append(main_door)

    openings.extend(_place_windows(nodes, rects, buildable))
    return openings
