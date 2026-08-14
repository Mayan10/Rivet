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


def edge_is_exterior(axis: str, coord: float, buildable: Rect, tol: float = 1e-3) -> bool:
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
            exterior = edge_is_exterior(axis, coord, buildable)
            thickness = WALL_THICKNESS_EXTERNAL_M if exterior else WALL_THICKNESS_INTERNAL_M
            if axis == "horizontal":
                segments.append(WallSegment(lo, coord, hi, coord, thickness, exterior))
            else:
                segments.append(WallSegment(coord, lo, coord, hi, thickness, exterior))

    return segments


def deduplicate_wall_segments(segments: list[WallSegment], precision: int = 4) -> list[WallSegment]:
    """Merge coincident/overlapping per-room segments into their true unique
    runs -- one entry per physical wall, not one per room that touches it.

    ``compute_wall_segments`` deliberately double-counts a shared interior
    wall (once per room) because that's harmless, even convenient, for
    rendering: two overlapping lines draw identically to one. It's wrong
    for quantity takeoff (running wall length, plaster area, block count in
    ``core/metrics.py``), which needs each physical wall counted exactly
    once. Used only for that -- renderers and the DXF exporter keep using
    ``compute_wall_segments`` directly.
    """
    groups: dict[tuple[str, float, float, bool], list[tuple[float, float]]] = {}

    for seg in segments:
        if abs(seg.y1 - seg.y2) < 10**-precision:
            axis, coord = "horizontal", round(seg.y1, precision)
            lo, hi = sorted((seg.x1, seg.x2))
        else:
            axis, coord = "vertical", round(seg.x1, precision)
            lo, hi = sorted((seg.y1, seg.y2))
        key = (axis, coord, seg.thickness, seg.exterior)
        groups.setdefault(key, []).append((lo, hi))

    merged: list[WallSegment] = []
    for (axis, coord, thickness, exterior), intervals in groups.items():
        intervals.sort()
        run_lo, run_hi = intervals[0]
        for lo, hi in intervals[1:]:
            if lo <= run_hi + 10**-precision:
                run_hi = max(run_hi, hi)
                continue
            merged.append(_segment_from_run(axis, coord, run_lo, run_hi, thickness, exterior))
            run_lo, run_hi = lo, hi
        merged.append(_segment_from_run(axis, coord, run_lo, run_hi, thickness, exterior))

    return merged


def _segment_from_run(
    axis: str, coord: float, lo: float, hi: float, thickness: float, exterior: bool
) -> WallSegment:
    if axis == "horizontal":
        return WallSegment(lo, coord, hi, coord, thickness, exterior)
    return WallSegment(coord, lo, coord, hi, thickness, exterior)


def total_wall_length_by_class(segments: list[WallSegment]) -> tuple[float, float]:
    """(exterior_length_m, interior_length_m) of deduplicated wall runs."""
    deduped = deduplicate_wall_segments(segments)
    exterior_len = sum(abs(s.x2 - s.x1) + abs(s.y2 - s.y1) for s in deduped if s.exterior)
    interior_len = sum(abs(s.x2 - s.x1) + abs(s.y2 - s.y1) for s in deduped if not s.exterior)
    return exterior_len, interior_len
