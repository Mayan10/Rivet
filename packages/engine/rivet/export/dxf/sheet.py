"""Paper space sheet: a locked-scale viewport onto the plan, a title block
with attributes, and door/window/room schedules as plain annotation
(Phase 4 items 7-8).

Layout of the sheet (all paper-space mm, independent of plot size):

    +----------------------------------------+----------------+
    |                                         |   schedules    |
    |                viewport                 |  (door/window/ |
    |             (locked at 1:100)           |   room area)   |
    |                                         |                |
    +----------------------------------------+----------------+
    |                     title block                          |
    +------------------------------------------------------------+

The sheet is sized to exactly fit the plot at 1:100 plus fixed margins,
rather than a named ISO paper size -- since every sheet is generated
per-request, there's no fixed physical sheet to target, and sizing it
this way keeps the 1:100 scale genuinely exact rather than "fit to page."

The title block is built at the exact size this sheet needs (one INSERT
per document, not reused at varying sizes like the door/window blocks),
so it's simpler to size correctly than stretching a nominal block would
be -- it's still a real BLOCK definition + ATTDEF/ATTRIB, satisfying item
7's "title block as a block with attributes."
"""

from __future__ import annotations

from dataclasses import dataclass

from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment
from ezdxf.lldxf import const

from ...core.metrics import LayoutMetrics
from ...core.models import Layout
from .layers import SCHEDULE, TITLE_BLOCK, LayerMap
from .units import PRINT_SCALE, SCHEDULE_TEXT_MM, SHEET_TITLE_TEXT_MM, TITLE_TEXT_MM, mm

BLOCK_TITLE_BLOCK = "RIVET_TITLE_BLOCK"
LAYOUT_NAME = "Sheet"

_VIEWPORT_MARGIN_MM = 15.0
_SCHEDULE_PANEL_WIDTH_MM = 95.0
_TITLE_BLOCK_HEIGHT_MM = 45.0
_ROW_HEIGHT_MM = 5.5
_SCHEDULE_ROW_HEIGHT_MM = 4.5
_DISCLAIMER_BAND_MM = 9.0

DISCLAIMER_TEXT = (
    "Design guidance, not a stamped drawing. Have construction-intent "
    "drawings reviewed by a licensed engineer/architect."
)

_TITLE_BLOCK_ATTRS = ("PROJECT", "CLIENT", "DATE", "SHEET", "REVISION", "SCALE")


@dataclass(frozen=True)
class TitleBlockInfo:
    project: str | None = None
    client: str | None = None
    date: str | None = None
    sheet: str = "A-101"
    revision: str = "0"


@dataclass(frozen=True)
class SheetGeometry:
    """Everything downstream drawing needs to know about this sheet's
    fixed layout, computed once from the plot size.
    """

    sheet_width_mm: float
    sheet_height_mm: float
    viewport_w_paper_mm: float
    viewport_h_paper_mm: float
    schedule_x_mm: float
    schedule_top_y_mm: float


def compute_sheet_geometry(layout: Layout) -> SheetGeometry:
    plot = layout.plot
    viewport_w = mm(plot.width_m) / PRINT_SCALE
    viewport_h = mm(plot.length_m) / PRINT_SCALE

    sheet_width = viewport_w + 2 * _VIEWPORT_MARGIN_MM + _SCHEDULE_PANEL_WIDTH_MM
    sheet_height = viewport_h + 2 * _VIEWPORT_MARGIN_MM + _TITLE_BLOCK_HEIGHT_MM

    return SheetGeometry(
        sheet_width_mm=sheet_width,
        sheet_height_mm=sheet_height,
        viewport_w_paper_mm=viewport_w,
        viewport_h_paper_mm=viewport_h,
        schedule_x_mm=viewport_w + 2 * _VIEWPORT_MARGIN_MM,
        schedule_top_y_mm=sheet_height,
    )


def _define_title_block(doc: Drawing, geometry: SheetGeometry) -> None:
    width, height = geometry.sheet_width_mm, _TITLE_BLOCK_HEIGHT_MM
    block = doc.blocks.new(name=BLOCK_TITLE_BLOCK)
    block.add_lwpolyline([(0, 0), (width, 0), (width, height), (0, height)], close=True)
    block.add_line((0, height * 0.62), (width, height * 0.62))
    block.add_line((width * 0.42, 0), (width * 0.42, height * 0.62))

    block.add_text(
        "RIVET — GENERATED FLOOR PLAN", dxfattribs={"height": SHEET_TITLE_TEXT_MM}
    ).set_placement((mm(0.003), height * 0.72), align=TextEntityAlignment.LEFT)

    # Fields occupy the band between the disclaimer strip (bottom
    # _DISCLAIMER_BAND_MM) and the sheet-title divider at height*0.62.
    fields_top = height * 0.62
    field_h = (fields_top - _DISCLAIMER_BAND_MM) / 3
    left_fields = ("PROJECT", "CLIENT", "DATE")
    right_fields = ("SHEET", "REVISION", "SCALE")
    for i, tag in enumerate(left_fields):
        y = fields_top - field_h * (i + 1) + field_h * 0.25
        block.add_text(f"{tag}:", dxfattribs={"height": TITLE_TEXT_MM * 0.8}).set_placement(
            (width * 0.01, y), align=TextEntityAlignment.LEFT
        )
        block.add_attdef(tag=tag, insert=(width * 0.13, y), text="", height=TITLE_TEXT_MM)
    for i, tag in enumerate(right_fields):
        y = fields_top - field_h * (i + 1) + field_h * 0.25
        block.add_text(f"{tag}:", dxfattribs={"height": TITLE_TEXT_MM * 0.8}).set_placement(
            (width * 0.44, y), align=TextEntityAlignment.LEFT
        )
        default = "1:100" if tag == "SCALE" else ""
        block.add_attdef(tag=tag, insert=(width * 0.56, y), text=default, height=TITLE_TEXT_MM)

    block.add_mtext(
        DISCLAIMER_TEXT,
        dxfattribs={"char_height": TITLE_TEXT_MM * 0.7, "width": width * 0.98},
    ).set_location((width * 0.01, _DISCLAIMER_BAND_MM * 0.35))


def _title_block_values(info: TitleBlockInfo) -> dict[str, str]:
    return {
        "PROJECT": info.project or "",
        "CLIENT": info.client or "",
        "DATE": info.date or "",
        "SHEET": info.sheet,
        "REVISION": info.revision,
        "SCALE": f"1:{PRINT_SCALE}",
    }


def build_sheet(doc: Drawing, layers: LayerMap, layout: Layout, title_block_info: TitleBlockInfo) -> SheetGeometry:
    geometry = compute_sheet_geometry(layout)
    _define_title_block(doc, geometry)

    psp = doc.layouts.new(LAYOUT_NAME)
    psp.page_setup(size=(geometry.sheet_width_mm, geometry.sheet_height_mm), margins=(0, 0, 0, 0), units="mm")

    view_center = (mm(layout.plot.width_m) / 2, mm(layout.plot.length_m) / 2)
    viewport_center = (
        _VIEWPORT_MARGIN_MM + geometry.viewport_w_paper_mm / 2,
        _TITLE_BLOCK_HEIGHT_MM + _VIEWPORT_MARGIN_MM + geometry.viewport_h_paper_mm / 2,
    )
    vp = psp.add_viewport(
        center=viewport_center,
        size=(geometry.viewport_w_paper_mm, geometry.viewport_h_paper_mm),
        view_center_point=view_center,
        view_height=mm(layout.plot.length_m),
    )
    vp.dxf.flags = const.VSF_LOCK_ZOOM

    insert = psp.add_blockref(BLOCK_TITLE_BLOCK, (0, 0), dxfattribs={"layer": layers[TITLE_BLOCK]})
    insert.add_auto_attribs(_title_block_values(title_block_info))

    return geometry


def _schedule_header(psp, x: float, y: float, title: str) -> float:
    psp.add_text(title, dxfattribs={"height": SCHEDULE_TEXT_MM * 1.2}).set_placement(
        (x, y), align=TextEntityAlignment.LEFT
    )
    return y - _SCHEDULE_ROW_HEIGHT_MM


def _draw_opening_schedule(psp, layers: LayerMap, x: float, y: float, title: str, rows) -> float:
    y = _schedule_header(psp, x, y, title)
    if not rows:
        psp.add_text("(none)", dxfattribs={"height": SCHEDULE_TEXT_MM, "layer": layers[SCHEDULE]}).set_placement(
            (x, y), align=TextEntityAlignment.LEFT
        )
        return y - _SCHEDULE_ROW_HEIGHT_MM
    for row in rows:
        text = f"{row.tag}  {row.width_m * 1000:.0f}x{row.height_m * 1000:.0f}mm  qty {row.count}"
        psp.add_text(text, dxfattribs={"height": SCHEDULE_TEXT_MM, "layer": layers[SCHEDULE]}).set_placement(
            (x, y), align=TextEntityAlignment.LEFT
        )
        y -= _SCHEDULE_ROW_HEIGHT_MM
    return y


def draw_schedules(doc: Drawing, layers: LayerMap, geometry: SheetGeometry, metrics: LayoutMetrics) -> int:
    """Room area + door + window schedules, drawn directly as TEXT rows
    (not FIELD entities -- item 8 is explicit that FIELDs don't
    recalculate outside AutoCAD, so this reads LayoutMetrics once at
    export time instead). Returns the number of schedule text rows drawn
    (for tests).
    """
    psp = doc.layouts.get(LAYOUT_NAME)
    x = geometry.schedule_x_mm + 3.0
    y = geometry.schedule_top_y_mm - 8.0
    count = 0

    y = _schedule_header(psp, x, y, "ROOM SCHEDULE")
    count += 1
    for room in metrics.rooms:
        text = f"{room.label}  {room.gross_area_sqm:.1f} m2"
        psp.add_text(text, dxfattribs={"height": SCHEDULE_TEXT_MM, "layer": layers[SCHEDULE]}).set_placement(
            (x, y), align=TextEntityAlignment.LEFT
        )
        y -= _SCHEDULE_ROW_HEIGHT_MM
        count += 1
    y -= _SCHEDULE_ROW_HEIGHT_MM * 0.5

    y = _draw_opening_schedule(psp, layers, x, y, "DOOR SCHEDULE", metrics.door_schedule)
    count += 1 + max(len(metrics.door_schedule), 1)
    y -= _SCHEDULE_ROW_HEIGHT_MM * 0.5

    y = _draw_opening_schedule(psp, layers, x, y, "WINDOW SCHEDULE", metrics.window_schedule)
    count += 1 + max(len(metrics.window_schedule), 1)

    return count
