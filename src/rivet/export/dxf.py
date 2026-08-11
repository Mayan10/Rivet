"""DXF export.

Unlike the legacy ``trace_to_dxf.py`` (which turned a raster image into a
soup of unlabeled LINE segments via contour tracing), this writes real CAD
structure: layered wall polylines with true thickness, wall segments
correctly split around door/window openings, door swing arcs, window
breaks, room text, and dimension entities.
"""

from __future__ import annotations

import io

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from ..core.models import Layout, Opening
from ..core.rules import WALL_THICKNESS_EXTERNAL_M, WALL_THICKNESS_INTERNAL_M
from ..core.walls import WallSegment, compute_wall_segments
from ..render.opening_geometry import door_symbol, window_symbol

LAYER_WALLS_EXT = "WALLS-EXTERIOR"
LAYER_WALLS_INT = "WALLS-INTERIOR"
LAYER_DOORS = "DOORS"
LAYER_WINDOWS = "WINDOWS"
LAYER_TEXT = "TEXT"
LAYER_DIMENSIONS = "DIMENSIONS"
LAYER_ROOMS = "ROOMS"
LAYER_PLOT_BOUNDARY = "PLOT-BOUNDARY"

# AutoCAD Color Index per layer.
_LAYER_COLORS = {
    LAYER_WALLS_EXT: 7,  # black/white
    LAYER_WALLS_INT: 8,  # gray
    LAYER_DOORS: 5,  # blue
    LAYER_WINDOWS: 4,  # cyan
    LAYER_TEXT: 7,
    LAYER_DIMENSIONS: 3,  # green
    LAYER_ROOMS: 9,  # light gray
    LAYER_PLOT_BOUNDARY: 9,
}


def _split_segment_by_openings(seg: WallSegment, openings: list[Opening]) -> list[WallSegment]:
    """Cut a wall segment into pieces that exclude any door/window spans
    lying on it, so the exported walls don't run straight through openings.
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


def _configure_dimstyle(doc: Drawing) -> None:
    """The built-in 'EZDXF' dimstyle defaults assume a unit-scale factor
    that misreads our meter-based coordinates as centimeters (a 12m wall
    would be labeled "1200" instead of "12.00"). Force a 1:1 scale with
    two decimal places so dimension text matches the actual drawing units.
    """
    dimstyle = doc.dimstyles.get("EZDXF")
    dimstyle.dxf.dimlfac = 1.0
    dimstyle.dxf.dimdec = 2
    dimstyle.dxf.dimtxt = 0.25
    dimstyle.dxf.dimasz = 0.15
    dimstyle.dxf.dimexe = 0.1
    dimstyle.dxf.dimexo = 0.05


def build_document(layout: Layout) -> Drawing:
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # meters
    _configure_dimstyle(doc)
    for name, color in _LAYER_COLORS.items():
        doc.layers.add(name=name, color=color)
    msp = doc.modelspace()

    plot = layout.plot
    msp.add_lwpolyline(
        [(0, 0), (plot.width_m, 0), (plot.width_m, plot.length_m), (0, plot.length_m), (0, 0)],
        dxfattribs={"layer": LAYER_PLOT_BOUNDARY, "linetype": "DASHED"},
    )

    for seg in compute_wall_segments(layout):
        layer = LAYER_WALLS_EXT if seg.exterior else LAYER_WALLS_INT
        for piece in _split_segment_by_openings(seg, layout.openings):
            msp.add_lwpolyline(
                [(piece.x1, piece.y1), (piece.x2, piece.y2)],
                dxfattribs={"layer": layer, "const_width": piece.thickness},
            )

    for room in layout.rooms:
        r = room.rect
        msp.add_lwpolyline(
            [(r.x, r.y), (r.x2, r.y), (r.x2, r.y2), (r.x, r.y2), (r.x, r.y)],
            dxfattribs={"layer": LAYER_ROOMS},
        )
        msp.add_text(room.label, dxfattribs={"layer": LAYER_TEXT, "height": 0.28}).set_placement(
            (r.cx, r.cy + 0.18), align=TextEntityAlignment.MIDDLE_CENTER
        )
        msp.add_text(
            f"{r.area:.1f} m2", dxfattribs={"layer": LAYER_TEXT, "height": 0.18}
        ).set_placement((r.cx, r.cy - 0.2), align=TextEntityAlignment.MIDDLE_CENTER)

    for op in layout.openings:
        thickness = (
            WALL_THICKNESS_EXTERNAL_M if op.kind in ("main_door", "window") else WALL_THICKNESS_INTERNAL_M
        )
        if op.kind == "window":
            sym = window_symbol(op, thickness)
            msp.add_line(sym.span[0], sym.span[1], dxfattribs={"layer": LAYER_WINDOWS})
            msp.add_line(sym.tick_a[0], sym.tick_a[1], dxfattribs={"layer": LAYER_WINDOWS})
            msp.add_line(sym.tick_b[0], sym.tick_b[1], dxfattribs={"layer": LAYER_WINDOWS})
        else:
            sym = door_symbol(op, layout, thickness)
            msp.add_line(sym.hinge, sym.leaf_end, dxfattribs={"layer": LAYER_DOORS})
            msp.add_lwpolyline(sym.arc_points, dxfattribs={"layer": LAYER_DOORS})

    dim_w = msp.add_linear_dim(
        base=(0, -1.0), p1=(0, 0), p2=(plot.width_m, 0), dimstyle="EZDXF", dxfattribs={"layer": LAYER_DIMENSIONS}
    )
    dim_w.render()
    dim_l = msp.add_linear_dim(
        base=(-1.0, 0),
        p1=(0, 0),
        p2=(0, plot.length_m),
        angle=90,
        dimstyle="EZDXF",
        dxfattribs={"layer": LAYER_DIMENSIONS},
    )
    dim_l.render()

    total_area = sum(r.rect.area for r in layout.rooms)
    msp.add_text(
        f"Rivet generated floor plan | {layout.candidate_id} | "
        f"score {layout.score}/100 | {total_area:.1f} m2 gross",
        dxfattribs={"layer": LAYER_TEXT, "height": 0.35},
    ).set_placement((0, plot.length_m + 1.2), align=TextEntityAlignment.LEFT)

    return doc


def export_dxf(layout: Layout, path: str) -> str:
    """Write the layout to ``path`` and return it."""
    build_document(layout).saveas(path)
    return path


def export_dxf_bytes(layout: Layout) -> bytes:
    """Serialize the layout to DXF text bytes (for HTTP responses)."""
    stream = io.StringIO()
    build_document(layout).write(stream)
    return stream.getvalue().encode("utf-8")
