"""DXF export orchestration.

Builds a real CAD deliverable (Phase 4, docs/prompts.md): millimetre
coordinates, BLOCK/INSERT/ATTDEF for doors/windows/fixtures/north-arrow/
title-block, per-room dimension chains, masonry hatch with proper
boundary paths and per-layer lineweights, AIA-style layers (legacy names
still selectable), and a paper-space sheet with a locked-scale viewport
and door/window/room schedules. Replaces the earlier version, which drew
everything as bare LWPOLYLINE/TEXT/LINE in metre coordinates on a fixed
legacy layer set -- a valid DXF, but not something an Indian CAD/
construction workflow could use directly (see this module's docstring
history in git for the Phase 0 audit finding that prompted the rewrite).
"""

from __future__ import annotations

import io

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from ...core.metrics import compute_metrics
from ...core.models import Layout
from ...core.walls import compute_wall_segments
from .blocks import (
    define_all_blocks,
    insert_door,
    insert_fixtures,
    insert_north_arrow,
    insert_window,
)
from .dimensions import draw_overall_dimensions, draw_room_dimensions, setup_and_configure
from .layers import DEFAULT_LAYER_SCHEME, PLOT_BOUNDARY, ROOMS, TEXT, setup_layers
from .sheet import TitleBlockInfo, build_sheet, draw_schedules
from .units import ROOM_AREA_MM, ROOM_LABEL_MM, SHEET_TITLE_TEXT_MM, mm, paper_mm_to_model
from .walls_geometry import draw_walls


def _schedule_tag_lookup(door_rows, window_rows) -> dict[tuple[str, float], str]:
    lookup: dict[tuple[str, float], str] = {}
    for row in (*door_rows, *window_rows):
        lookup[(row.kind, round(row.width_m, 3))] = row.tag
    return lookup


def build_document(
    layout: Layout,
    *,
    layer_scheme: str = DEFAULT_LAYER_SCHEME,
    title_block_info: TitleBlockInfo | None = None,
) -> Drawing:
    metrics = compute_metrics(layout, layout.ruleset)
    title_block_info = title_block_info or TitleBlockInfo()

    doc = ezdxf.new(dxfversion="R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimeters
    layers = setup_layers(doc, layer_scheme)
    setup_and_configure(doc)
    define_all_blocks(doc)
    msp = doc.modelspace()

    plot = layout.plot
    msp.add_lwpolyline(
        [
            (0, 0),
            (mm(plot.width_m), 0),
            (mm(plot.width_m), mm(plot.length_m)),
            (0, mm(plot.length_m)),
            (0, 0),
        ],
        dxfattribs={"layer": layers[PLOT_BOUNDARY], "linetype": "DASHED"},
    )

    draw_walls(msp, layers, compute_wall_segments(layout), layout.openings)

    for room in layout.rooms:
        r = room.rect
        msp.add_lwpolyline(
            [(mm(r.x), mm(r.y)), (mm(r.x2), mm(r.y)), (mm(r.x2), mm(r.y2)), (mm(r.x), mm(r.y2)), (mm(r.x), mm(r.y))],
            dxfattribs={"layer": layers[ROOMS]},
        )
        msp.add_text(
            room.label, dxfattribs={"layer": layers[TEXT], "height": paper_mm_to_model(ROOM_LABEL_MM)}
        ).set_placement((mm(r.cx), mm(r.cy) + mm(0.18)), align=TextEntityAlignment.MIDDLE_CENTER)
        msp.add_text(
            f"{r.area:.1f} m2", dxfattribs={"layer": layers[TEXT], "height": paper_mm_to_model(ROOM_AREA_MM)}
        ).set_placement((mm(r.cx), mm(r.cy) - mm(0.2)), align=TextEntityAlignment.MIDDLE_CENTER)

    tag_for = _schedule_tag_lookup(metrics.door_schedule, metrics.window_schedule)
    for op in layout.openings:
        key = (op.kind, round(op.width, 3))
        if op.kind == "window":
            insert_window(msp, layers, op, layout, tag_for.get(key, "W?"))
        else:
            insert_door(msp, layers, op, layout, tag_for.get(key, "D?"))

    insert_fixtures(msp, layers, layout)
    insert_north_arrow(msp, layers, (mm(plot.width_m) + mm(1.0), mm(plot.length_m)))

    draw_overall_dimensions(msp, layers, layout)
    draw_room_dimensions(msp, layers, layout)

    msp.add_text(
        f"Rivet generated floor plan | {layout.candidate_id} | "
        f"score {layout.score}/100 | {metrics.gross_area_sqm:.1f} m2 gross",
        dxfattribs={"layer": layers[TEXT], "height": paper_mm_to_model(SHEET_TITLE_TEXT_MM)},
    ).set_placement((0, mm(plot.length_m) + mm(1.6)), align=TextEntityAlignment.LEFT)

    geometry = build_sheet(doc, layers, layout, title_block_info)
    draw_schedules(doc, layers, geometry, metrics)

    return doc


def export_dxf(
    layout: Layout,
    path: str,
    *,
    layer_scheme: str = DEFAULT_LAYER_SCHEME,
    title_block_info: TitleBlockInfo | None = None,
) -> str:
    """Write the layout to ``path`` and return it."""
    build_document(layout, layer_scheme=layer_scheme, title_block_info=title_block_info).saveas(path)
    return path


def export_dxf_bytes(
    layout: Layout,
    *,
    layer_scheme: str = DEFAULT_LAYER_SCHEME,
    title_block_info: TitleBlockInfo | None = None,
) -> bytes:
    """Serialize the layout to DXF text bytes (for HTTP responses)."""
    stream = io.StringIO()
    build_document(layout, layer_scheme=layer_scheme, title_block_info=title_block_info).write(stream)
    return stream.getvalue().encode("utf-8")
