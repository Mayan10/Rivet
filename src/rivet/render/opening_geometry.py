"""Real-world (meter-space) geometry for door swings and window symbols,
shared by the raster and SVG renderers so both draw identical symbols.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.models import Layout, Opening

Point = tuple[float, float]


@dataclass(frozen=True)
class DoorSymbol:
    hinge: Point
    leaf_end: Point
    arc_points: list[Point]
    wall_gap: tuple[Point, Point]
    thickness: float


@dataclass(frozen=True)
class WindowSymbol:
    span: tuple[Point, Point]
    tick_a: tuple[Point, Point]
    tick_b: tuple[Point, Point]
    thickness: float


def _along_into(op: Opening, layout: Layout) -> tuple[Point, Point]:
    room = layout.room(op.room_id)
    rect = room.rect

    if op.axis == "horizontal":
        along: Point = (1.0, 0.0)
        if abs(rect.y - op.y) <= 1e-3:
            into: Point = (0.0, 1.0)
        else:
            into = (0.0, -1.0)
    else:
        along = (0.0, 1.0)
        if abs(rect.x - op.x) <= 1e-3:
            into = (1.0, 0.0)
        else:
            into = (-1.0, 0.0)

    return along, into


def door_symbol(op: Opening, layout: Layout, thickness: float, n_arc: int = 10) -> DoorSymbol:
    along, into = _along_into(op, layout)
    hinge: Point = (op.x, op.y)
    hinge_end: Point = (op.x + along[0] * op.width, op.y + along[1] * op.width)
    leaf_end: Point = (hinge[0] + into[0] * op.width, hinge[1] + into[1] * op.width)

    arc_points: list[Point] = []
    for i in range(n_arc + 1):
        t = (math.pi / 2) * (i / n_arc)
        x = hinge[0] + op.width * (math.cos(t) * along[0] + math.sin(t) * into[0])
        y = hinge[1] + op.width * (math.cos(t) * along[1] + math.sin(t) * into[1])
        arc_points.append((x, y))

    return DoorSymbol(
        hinge=hinge,
        leaf_end=leaf_end,
        arc_points=arc_points,
        wall_gap=(hinge, hinge_end),
        thickness=thickness,
    )


def window_symbol(op: Opening, thickness: float) -> WindowSymbol:
    if op.axis == "horizontal":
        p1: Point = (op.x, op.y)
        p2: Point = (op.x + op.width, op.y)
        perp: Point = (0.0, thickness / 2)
    else:
        p1 = (op.x, op.y)
        p2 = (op.x, op.y + op.width)
        perp = (thickness / 2, 0.0)

    tick_a = ((p1[0] - perp[0], p1[1] - perp[1]), (p1[0] + perp[0], p1[1] + perp[1]))
    tick_b = ((p2[0] - perp[0], p2[1] - perp[1]), (p2[0] + perp[0], p2[1] + perp[1]))

    return WindowSymbol(span=(p1, p2), tick_a=tick_a, tick_b=tick_b, thickness=thickness)
