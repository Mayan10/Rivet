"""Dimension styling and placement (Phase 4 items 1 & 4).

Coordinates are millimetres now (see units.py), so the pre-Phase-4
dimstyle hack (``dimlfac`` compensating for meter-as-centimeter
misreading) is gone -- raw mm values are exactly what should display.
What's added: DIMSCALE tied to the fixed 1:100 print scale, so dimension
text/arrows print at a legible, consistent size regardless of plot size,
and per-room dimension chains (previously only the two overall
width/length dimensions existed).
"""

from __future__ import annotations

from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace

from ...core.models import Layout
from .layers import DIMENSIONS, LayerMap
from .units import PRINT_SCALE, mm

DIMSTYLE_NAME = "RIVET"

# Nominal (paper-mm) sizes -- DIMSCALE multiplies these for their actual
# model-space size, so they stay legible at 1:100 regardless of plot size.
_DIMTXT_MM = 2.5
_DIMASZ_MM = 2.5
_DIMEXE_MM = 1.25
_DIMEXO_MM = 1.5

# How far outside each room's own edge its dimension line sits, and how
# far outside the plot the two overall dimensions sit -- both in metres,
# converted at the call site.
_ROOM_DIM_OFFSET_M = 0.3
_OVERALL_DIM_OFFSET_M = 1.0


def _setup_dimstyle(doc: Drawing) -> None:
    dimstyle = doc.dimstyles.new(DIMSTYLE_NAME, dxfattribs={})
    dimstyle.dxf.dimlfac = 1.0
    dimstyle.dxf.dimdec = 0
    dimstyle.dxf.dimtxt = _DIMTXT_MM
    dimstyle.dxf.dimasz = _DIMASZ_MM
    dimstyle.dxf.dimexe = _DIMEXE_MM
    dimstyle.dxf.dimexo = _DIMEXO_MM
    dimstyle.dxf.dimscale = float(PRINT_SCALE)


def _linear_dim(msp: Modelspace, layers: LayerMap, base, p1, p2, angle: float = 0):
    dim = msp.add_linear_dim(
        base=base, p1=p1, p2=p2, angle=angle, dimstyle=DIMSTYLE_NAME, dxfattribs={"layer": layers[DIMENSIONS]}
    )
    dim.render()
    return dim


def draw_overall_dimensions(msp: Modelspace, layers: LayerMap, layout: Layout) -> None:
    plot = layout.plot
    offset = mm(_OVERALL_DIM_OFFSET_M)
    _linear_dim(msp, layers, base=(0, -offset), p1=(0, 0), p2=(mm(plot.width_m), 0))
    _linear_dim(msp, layers, base=(-offset, 0), p1=(0, 0), p2=(0, mm(plot.length_m)), angle=90)


def draw_room_dimensions(msp: Modelspace, layers: LayerMap, layout: Layout) -> int:
    """One width dimension along each room's bottom edge and one depth
    dimension along its left edge, offset outward from the room. Rooms
    sharing a bottom/left baseline (a row/column) naturally line up along
    the same dimension line, matching how a real chain reads even though
    each is its own DIMENSION entity rather than one continued string.
    Returns the number of dimensions drawn (for tests).
    """
    offset = mm(_ROOM_DIM_OFFSET_M)
    count = 0
    for room in layout.rooms:
        r = room.rect
        x, y, x2, y2 = mm(r.x), mm(r.y), mm(r.x2), mm(r.y2)
        _linear_dim(msp, layers, base=(x, y - offset), p1=(x, y), p2=(x2, y))
        count += 1
        _linear_dim(msp, layers, base=(x - offset, y), p1=(x, y), p2=(x, y2), angle=90)
        count += 1
    return count


def setup_and_configure(doc: Drawing) -> None:
    _setup_dimstyle(doc)
