"""Wall boundary polylines and masonry hatch (Phase 4 item 5).

Replaces the pre-Phase-4 approach (a zero-width centerline LWPOLYLINE
with ``const_width`` set to the wall thickness -- a rendering trick that
approximates a filled band in some viewers but isn't a real boundary).
Each wall segment now gets its true rectangular footprint traced as a
closed polyline (for the cut-wall lineweight) and a HATCH entity filling
that same boundary (masonry pattern) -- the two things item 5 actually
asks for.
"""

from __future__ import annotations

from ezdxf.layouts import Modelspace

from ...core.models import Opening
from ...core.walls import WallSegment
from .layers import WALLS_EXT, WALLS_HATCH, WALLS_INT, LayerMap
from .units import mm

# ANSI31 is a general-purpose diagonal hatch; ezdxf ships it as a built-in
# pattern (no external .pat file to load). It's the conventional stand-in
# for masonry/concrete fill in architectural sections when a true brick
# pattern isn't available. Scale tuned for legibility on a wall this thin
# once geometry is in millimetres.
_HATCH_PATTERN = "ANSI31"
_HATCH_SCALE = 40.0


def _boundary(seg: WallSegment) -> list[tuple[float, float]]:
    half_t = mm(seg.thickness) / 2
    x1, y1, x2, y2 = mm(seg.x1), mm(seg.y1), mm(seg.x2), mm(seg.y2)
    if abs(y1 - y2) < 1e-6:  # horizontal run
        lo, hi = sorted((x1, x2))
        return [(lo, y1 - half_t), (hi, y1 - half_t), (hi, y1 + half_t), (lo, y1 + half_t)]
    lo, hi = sorted((y1, y2))  # vertical run
    return [(x1 - half_t, lo), (x1 + half_t, lo), (x1 + half_t, hi), (x1 - half_t, hi)]


def _split_segment_by_openings(seg: WallSegment, openings: list[Opening]) -> list[WallSegment]:
    """Cut a wall segment into pieces that exclude any door/window spans
    lying on it, so exported walls don't run straight through openings.
    """
    is_horizontal = abs(seg.y1 - seg.y2) < 1e-6
    if is_horizontal:
        axis, coord = "horizontal", seg.y1
        lo, hi = sorted((seg.x1, seg.x2))
    else:
        axis, coord = "vertical", seg.x1
        lo, hi = sorted((seg.y1, seg.y2))

    cuts: list[tuple[float, float]] = []
    for op in openings:
        if op.axis != axis:
            continue
        op_coord = op.y if axis == "horizontal" else op.x
        if abs(op_coord - coord) > 1e-3:
            continue
        op_lo = op.x if axis == "horizontal" else op.y
        op_hi = op_lo + op.width
        c_lo, c_hi = max(op_lo, lo), min(op_hi, hi)
        if c_hi > c_lo:
            cuts.append((c_lo, c_hi))

    if not cuts:
        return [seg]

    cuts.sort()
    merged: list[list[float]] = []
    for c in cuts:
        if merged and c[0] <= merged[-1][1] + 1e-6:
            merged[-1][1] = max(merged[-1][1], c[1])
        else:
            merged.append([c[0], c[1]])

    pieces: list[tuple[float, float]] = []
    cursor = lo
    for c_lo, c_hi in merged:
        if c_lo > cursor:
            pieces.append((cursor, c_lo))
        cursor = max(cursor, c_hi)
    if cursor < hi:
        pieces.append((cursor, hi))

    out = []
    for a, b in pieces:
        if axis == "horizontal":
            out.append(WallSegment(a, coord, b, coord, seg.thickness, seg.exterior))
        else:
            out.append(WallSegment(coord, a, coord, b, seg.thickness, seg.exterior))
    return out


def draw_walls(msp: Modelspace, layers: LayerMap, segments: list[WallSegment], openings: list[Opening]) -> int:
    """Draw every wall segment's true boundary + masonry hatch, split
    around door/window openings. Returns the count of boundary polylines
    drawn (for tests).
    """
    count = 0
    for seg in segments:
        layer_key = WALLS_EXT if seg.exterior else WALLS_INT
        for piece in _split_segment_by_openings(seg, openings):
            boundary = _boundary(piece)
            msp.add_lwpolyline(boundary, close=True, dxfattribs={"layer": layers[layer_key]})
            count += 1

            hatch = msp.add_hatch(dxfattribs={"layer": layers[WALLS_HATCH]})
            hatch.set_pattern_fill(_HATCH_PATTERN, scale=_HATCH_SCALE)
            hatch.paths.add_polyline_path(boundary, is_closed=True)
    return count
