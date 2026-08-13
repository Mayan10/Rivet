"""BLOCK definitions and INSERT placement (Phase 4 items 2-3).

One definition per symbol type, placed with INSERT and scaled/rotated per
instance -- not inline geometry repeated at every occurrence. Door and
window blocks carry ATTDEF (TAG/TYPE/WIDTH_MM/HEIGHT_MM/ROOM), so an
INSERT's ATTRIB values are extractable into a schedule by AutoCAD's
DATAEXTRACTION (or by ``core/metrics.py``'s own schedule, which this
package also draws directly -- see sheet.py -- since DATAEXTRACTION only
works inside AutoCAD itself).

Sanitary/kitchen fixture blocks are deliberately schematic: one
representative symbol per relevant room, placed at a fixed anchor point
inside the room rect. There's no wall-adjacency-aware fixture-layout
algorithm in this codebase (nothing upstream models fixture placement at
all) -- building one is a substantially larger feature than the block/
attribute plumbing this phase is about. These exist to demonstrate that
plumbing, not to be construction-ready fixture layouts.

Every block is defined with its geometry on layer "0" (ezdxf/AutoCAD's
standard "inherit the INSERT's layer" convention), so a single definition
correctly colors/lineweights itself per the layer each INSERT is placed
on -- no per-entity layer bookkeeping needed here.
"""

from __future__ import annotations

import math

from ezdxf.document import Drawing
from ezdxf.layouts import Modelspace

from ...core.models import Layout, Opening, Rect, RoomType
from ...core.rules import DOOR_HEIGHT_M, WALL_THICKNESS_EXTERNAL_M, WINDOW_HEIGHT_M
from ...render.opening_geometry import along_into
from .layers import DOORS, FIXTURES, TEXT, WINDOWS, LayerMap
from .units import mm

BLOCK_DOOR = "RIVET_DOOR"
BLOCK_WINDOW = "RIVET_WINDOW"
BLOCK_NORTH_ARROW = "RIVET_NORTH_ARROW"
BLOCK_WC = "RIVET_FIXTURE_WC"
BLOCK_WASHBASIN = "RIVET_FIXTURE_WASHBASIN"
BLOCK_KITCHEN_COUNTER = "RIVET_FIXTURE_KITCHEN_COUNTER"

# Nominal size (mm) every door/window block is drawn at; INSERT scales
# from this to each opening's actual width.
_NOMINAL_DOOR_WIDTH_MM = mm(1.0)
_NOMINAL_WINDOW_WIDTH_MM = mm(1.0)

_ATTR_TAGS = ("TAG", "TYPE", "WIDTH_MM", "HEIGHT_MM", "ROOM")

# (along, into) -> (rotation degrees, mirror y). Only four combinations
# are possible -- both vectors are always axis-aligned, see
# render/opening_geometry.py::along_into. Derived once by hand: the
# canonical block is drawn for along=(1, 0), into=(0, 1); every other case
# is that same quarter-circle rotated and/or mirrored about its hinge.
_DOOR_ORIENTATION: dict[tuple[tuple[float, float], tuple[float, float]], tuple[float, bool]] = {
    ((1.0, 0.0), (0.0, 1.0)): (0.0, False),
    ((1.0, 0.0), (0.0, -1.0)): (0.0, True),
    ((0.0, 1.0), (1.0, 0.0)): (90.0, True),
    ((0.0, 1.0), (-1.0, 0.0)): (90.0, False),
}


def _add_attdefs(block, label_y: float, line_gap: float) -> None:
    for i, tag in enumerate(_ATTR_TAGS):
        block.add_attdef(
            tag=tag,
            insert=(0, label_y - i * line_gap),
            text=tag,
            height=mm(0.12),
            dxfattribs={"invisible": True},
        )


def _define_door_block(doc: Drawing) -> None:
    """Canonical unit door: hinge at origin, leaf swinging from (1, 0) to
    (0, 1) -- along=(1, 0), into=(0, 1). Every instance reaches its actual
    orientation via INSERT rotation/mirroring (see _DOOR_ORIENTATION) and
    its actual width via uniform INSERT scale (preserves the quarter-arc).
    """
    block = doc.blocks.new(name=BLOCK_DOOR)
    n = 10
    arc = [
        (
            _NOMINAL_DOOR_WIDTH_MM * math.cos(math.pi / 2 * i / n),
            _NOMINAL_DOOR_WIDTH_MM * math.sin(math.pi / 2 * i / n),
        )
        for i in range(n + 1)
    ]
    block.add_lwpolyline(arc)
    block.add_line((0, 0), (0, _NOMINAL_DOOR_WIDTH_MM))
    _add_attdefs(block, label_y=-mm(0.25), line_gap=mm(0.16))


def _define_window_block(doc: Drawing) -> None:
    """Canonical unit window: span from (0, 0) to (1, 0), jamb ticks
    perpendicular by half the external wall thickness. Thickness is
    constant (every window sits on an exterior wall), so only the x-scale
    varies per instance; rotation handles horizontal vs. vertical walls.
    """
    block = doc.blocks.new(name=BLOCK_WINDOW)
    half_t = mm(WALL_THICKNESS_EXTERNAL_M) / 2
    block.add_line((0, 0), (_NOMINAL_WINDOW_WIDTH_MM, 0))
    block.add_line((0, -half_t), (0, half_t))
    block.add_line((_NOMINAL_WINDOW_WIDTH_MM, -half_t), (_NOMINAL_WINDOW_WIDTH_MM, half_t))
    _add_attdefs(block, label_y=-mm(0.4), line_gap=mm(0.16))


def _define_north_arrow_block(doc: Drawing) -> None:
    size = mm(1.0)
    block = doc.blocks.new(name=BLOCK_NORTH_ARROW)
    block.add_lwpolyline(
        [(0, 0), (size * 0.18, -size * 0.55), (0, -size * 0.38), (-size * 0.18, -size * 0.55)],
        close=True,
    )
    block.add_text("N", dxfattribs={"height": mm(0.22)}).set_placement((0, size * 0.08))


def _define_fixture_blocks(doc: Drawing) -> None:
    """Schematic-only symbols -- see module docstring."""
    wc = doc.blocks.new(name=BLOCK_WC)
    wc.add_lwpolyline([(0, 0), (mm(0.4), 0), (mm(0.4), mm(0.55)), (0, mm(0.55))], close=True)
    wc.add_ellipse(center=(mm(0.2), mm(0.9)), major_axis=(mm(0.22), 0), ratio=0.75, start_param=0, end_param=math.pi)

    basin = doc.blocks.new(name=BLOCK_WASHBASIN)
    basin.add_lwpolyline([(0, 0), (mm(0.5), 0), (mm(0.5), mm(0.35)), (0, mm(0.35))], close=True)
    basin.add_arc(center=(mm(0.25), mm(0.02)), radius=mm(0.16), start_angle=10, end_angle=170)

    counter = doc.blocks.new(name=BLOCK_KITCHEN_COUNTER)
    counter.add_lwpolyline([(0, 0), (mm(1.5), 0), (mm(1.5), mm(0.6)), (0, mm(0.6))], close=True)
    counter.add_lwpolyline(
        [(mm(1.0), mm(0.15)), (mm(1.35), mm(0.15)), (mm(1.35), mm(0.45)), (mm(1.0), mm(0.45))],
        close=True,
    )


def define_all_blocks(doc: Drawing) -> None:
    _define_door_block(doc)
    _define_window_block(doc)
    _define_north_arrow_block(doc)
    _define_fixture_blocks(doc)


def insert_door(msp: Modelspace, layers: LayerMap, op: Opening, layout: Layout, tag: str) -> None:
    room = layout.room(op.room_id)
    along, into = along_into(op, layout)
    rotation, mirror = _DOOR_ORIENTATION[(along, into)]
    scale = mm(op.width) / _NOMINAL_DOOR_WIDTH_MM

    insert = msp.add_blockref(
        BLOCK_DOOR,
        (mm(op.x), mm(op.y)),
        dxfattribs={
            "layer": layers[DOORS],
            "xscale": scale,
            "yscale": -scale if mirror else scale,
            "rotation": rotation,
        },
    )
    insert.add_auto_attribs(
        {
            "TAG": tag,
            "TYPE": op.kind,
            "WIDTH_MM": f"{mm(op.width):.0f}",
            "HEIGHT_MM": f"{mm(DOOR_HEIGHT_M):.0f}",
            "ROOM": room.label,
        }
    )


def insert_window(msp: Modelspace, layers: LayerMap, op: Opening, layout: Layout, tag: str) -> None:
    room = layout.room(op.room_id)
    rotation = 0.0 if op.axis == "horizontal" else 90.0
    scale = mm(op.width) / _NOMINAL_WINDOW_WIDTH_MM

    insert = msp.add_blockref(
        BLOCK_WINDOW,
        (mm(op.x), mm(op.y)),
        dxfattribs={"layer": layers[WINDOWS], "xscale": scale, "yscale": 1.0, "rotation": rotation},
    )
    insert.add_auto_attribs(
        {
            "TAG": tag,
            "TYPE": "window",
            "WIDTH_MM": f"{mm(op.width):.0f}",
            "HEIGHT_MM": f"{mm(WINDOW_HEIGHT_M):.0f}",
            "ROOM": room.label,
        }
    )


def insert_north_arrow(msp: Modelspace, layers: LayerMap, position: tuple[float, float]) -> None:
    msp.add_blockref(BLOCK_NORTH_ARROW, position, dxfattribs={"layer": layers[TEXT]})


def _fixture_anchor(rect: Rect, corner: str, margin: float = 0.15) -> tuple[float, float]:
    if corner == "top_left":
        return (rect.x + margin, rect.y2 - margin)
    if corner == "bottom_right":
        return (rect.x2 - margin, rect.y + margin)
    return (rect.x + margin, rect.y + margin)  # bottom_left


def insert_fixtures(msp: Modelspace, layers: LayerMap, layout: Layout) -> int:
    """Insert schematic fixture blocks for bathroom/toilet/kitchen rooms.
    Returns the number of fixture blocks inserted (for tests).
    """
    count = 0
    for room in layout.rooms:
        rect = room.rect
        if room.room_type in (RoomType.BATHROOM, RoomType.TOILET):
            if rect.w < 0.6 or rect.h < 0.9:
                continue
            x, y = _fixture_anchor(rect, "top_left")
            msp.add_blockref(BLOCK_WC, (mm(x), mm(y)), dxfattribs={"layer": layers[FIXTURES]})
            count += 1
            if rect.area > 2.0:
                bx, by = _fixture_anchor(rect, "bottom_right")
                msp.add_blockref(
                    BLOCK_WASHBASIN, (mm(bx) - mm(0.5), mm(by)), dxfattribs={"layer": layers[FIXTURES]}
                )
                count += 1
        elif room.room_type == RoomType.KITCHEN:
            if rect.w < 1.6 or rect.h < 0.7:
                continue
            x, y = _fixture_anchor(rect, "bottom_left", margin=0.1)
            msp.add_blockref(BLOCK_KITCHEN_COUNTER, (mm(x), mm(y)), dxfattribs={"layer": layers[FIXTURES]})
            count += 1
    return count
