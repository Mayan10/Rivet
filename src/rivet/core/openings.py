"""Places doors on shared walls between adjacent rooms and windows on
exterior-facing walls of habitable rooms.
"""

from __future__ import annotations

import networkx as nx

from .geometry import boundary_edges, entrance_edge, room_touches_edge, shared_wall
from .graph import RoomNode
from .models import Opening, PlotSpec, Rect
from .rules import (
    DOOR_WIDTH_MAIN_M,
    ENTRANCE_COMPATIBLE_ROOMS,
    MIN_OPENING_EDGE_CLEARANCE_M,
    door_width_for,
    window_width_for,
)

_MIN_DOOR_WALL_M = 1.2  # a shared wall shorter than this can't fit a door + clearances


def _clamp_position(desired_mid: float, width: float, lo: float, hi: float) -> float:
    """Center an opening of ``width`` on ``desired_mid``, kept within
    [lo, hi] and clear of the wall's corners.
    """
    start = desired_mid - width / 2
    max_start = max(lo, hi - width)
    return min(max(start, lo), max_start)


def _place_interior_doors(
    nodes: list[RoomNode], rects: dict[str, Rect], graph: nx.Graph
) -> list[Opening]:
    by_id = {n.id: n for n in nodes}
    openings: list[Opening] = []

    for u, v, _data in graph.edges(data=True):
        wall = shared_wall(rects[u], rects[v], min_length=_MIN_DOOR_WALL_M)
        if wall is None:
            continue

        width = min(door_width_for(by_id[u].room_type), door_width_for(by_id[v].room_type))
        lo, hi = wall.lo + MIN_OPENING_EDGE_CLEARANCE_M, wall.hi - MIN_OPENING_EDGE_CLEARANCE_M
        if hi - lo < width:
            continue
        pos = _clamp_position(wall.mid, width, lo, hi)

        if wall.axis == "vertical":
            x, y = wall.coord, pos
        else:
            x, y = pos, wall.coord

        openings.append(
            Opening(kind="door", x=x, y=y, width=width, axis=wall.axis, room_id=u, connects_to=v)
        )

    return openings


def _place_main_door(
    nodes: list[RoomNode], rects: dict[str, Rect], buildable: Rect, plot: PlotSpec
) -> Opening | None:
    edge = entrance_edge(plot.entrance)
    on_edge = [n for n in nodes if room_touches_edge(rects[n.id], buildable, edge)]
    if not on_edge:
        return None

    preferred = [n for n in on_edge if n.room_type in ENTRANCE_COMPATIBLE_ROOMS]
    host = preferred[0] if preferred else on_edge[0]
    rect = rects[host.id]
    width = DOOR_WIDTH_MAIN_M

    if edge in ("y2", "y"):
        coord = rect.y2 if edge == "y2" else rect.y
        lo, hi = rect.x + MIN_OPENING_EDGE_CLEARANCE_M, rect.x2 - MIN_OPENING_EDGE_CLEARANCE_M
        if hi - lo < width:
            return None
        x = _clamp_position(rect.cx, width, lo, hi)
        return Opening(kind="main_door", x=x, y=coord, width=width, axis="horizontal", room_id=host.id)

    coord = rect.x2 if edge == "x2" else rect.x
    lo, hi = rect.y + MIN_OPENING_EDGE_CLEARANCE_M, rect.y2 - MIN_OPENING_EDGE_CLEARANCE_M
    if hi - lo < width:
        return None
    y = _clamp_position(rect.cy, width, lo, hi)
    return Opening(kind="main_door", x=coord, y=y, width=width, axis="vertical", room_id=host.id)


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
) -> list[Opening]:
    openings = _place_interior_doors(nodes, rects, graph)

    main_door = _place_main_door(nodes, rects, buildable, plot)
    if main_door is not None:
        openings.append(main_door)

    openings.extend(_place_windows(nodes, rects, buildable))
    return openings
