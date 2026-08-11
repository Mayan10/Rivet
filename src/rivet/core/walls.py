"""Derives drawable wall segments from a :class:`Layout`.

Shared by both renderers and the DXF exporter so wall thickness/exterior
classification is computed in exactly one place. Each room contributes its
own four edges as independent segments (rather than trying to merge
coincident edges between neighbors into a single polyline) — where two
rooms share a wall, both draw the same centerline, which overlaps exactly
and renders identically to a single wall. This keeps the geometry trivially
correct even at T-junctions, at the cost of some redundant entities.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Layout, Rect
from .rules import WALL_THICKNESS_EXTERNAL_M, WALL_THICKNESS_INTERNAL_M


@dataclass(frozen=True)
class WallSegment:
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    exterior: bool


def _edge_is_exterior(axis: str, coord: float, buildable: Rect, tol: float = 1e-3) -> bool:
    if axis == "horizontal":
        return abs(coord - buildable.y) <= tol or abs(coord - buildable.y2) <= tol
    return abs(coord - buildable.x) <= tol or abs(coord - buildable.x2) <= tol


def compute_wall_segments(layout: Layout) -> list[WallSegment]:
    buildable = layout.buildable
    segments: list[WallSegment] = []

    for room in layout.rooms:
        r = room.rect
        edges = [
            ("horizontal", r.y, r.x, r.x2),
            ("horizontal", r.y2, r.x, r.x2),
            ("vertical", r.x, r.y, r.y2),
            ("vertical", r.x2, r.y, r.y2),
        ]
        for axis, coord, lo, hi in edges:
            exterior = _edge_is_exterior(axis, coord, buildable)
            thickness = WALL_THICKNESS_EXTERNAL_M if exterior else WALL_THICKNESS_INTERNAL_M
            if axis == "horizontal":
                segments.append(WallSegment(lo, coord, hi, coord, thickness, exterior))
            else:
                segments.append(WallSegment(coord, lo, coord, hi, thickness, exterior))

    return segments
