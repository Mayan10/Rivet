"""SVG rendering of a :class:`Layout` — the scalable counterpart to
``render/raster.py``, sharing the same wall/opening geometry and palette.
"""

from __future__ import annotations

import svgwrite

from ..core.metrics import compute_metrics
from ..core.models import Layout
from ..core.rules import WALL_THICKNESS_EXTERNAL_M, WALL_THICKNESS_INTERNAL_M
from ..core.walls import compute_wall_segments
from .opening_geometry import door_symbol, window_symbol
from .palette import DIMENSION_RGB, PLOT_BOUNDARY_RGB, TEXT_RGB, WALL_RGB, fill_for, rgb_to_hex

PX_PER_M = 60
MARGIN_PX = 110
TITLE_BLOCK_PX = 84


class _Transform:
    def __init__(self, height_px: float, px_per_m: float):
        self.height_px = height_px
        self.px_per_m = px_per_m

    def pt(self, x_m: float, y_m: float) -> tuple[float, float]:
        return (MARGIN_PX + x_m * self.px_per_m, self.height_px - MARGIN_PX - y_m * self.px_per_m)

    def length(self, meters: float) -> float:
        return meters * self.px_per_m


def render_svg(layout: Layout, px_per_m: float = PX_PER_M) -> str:
    metrics = compute_metrics(layout, layout.ruleset)
    plot = layout.plot
    width_px = plot.width_m * px_per_m + 2 * MARGIN_PX
    plan_height_px = plot.length_m * px_per_m + 2 * MARGIN_PX
    height_px = plan_height_px + TITLE_BLOCK_PX

    dwg = svgwrite.Drawing(size=(f"{width_px}px", f"{height_px}px"), viewBox=f"0 0 {width_px} {height_px}")
    dwg.add(dwg.rect((0, 0), (width_px, height_px), fill="white"))
    tr = _Transform(plan_height_px, px_per_m)

    plot_boundary = dwg.add(dwg.g(stroke=rgb_to_hex(PLOT_BOUNDARY_RGB), stroke_dasharray="6,5", fill="none"))
    p0, p1 = tr.pt(0, plot.length_m), tr.pt(plot.width_m, 0)
    plot_boundary.add(dwg.rect((p0[0], p0[1]), (p1[0] - p0[0], p1[1] - p0[1])))

    rooms_g = dwg.add(dwg.g())
    for room in layout.rooms:
        r = room.rect
        top_left = tr.pt(r.x, r.y2)
        rooms_g.add(
            dwg.rect(
                (top_left[0], top_left[1]),
                (tr.length(r.w), tr.length(r.h)),
                fill=rgb_to_hex(fill_for(room.room_type)),
            )
        )

    walls_g = dwg.add(dwg.g(stroke=rgb_to_hex(WALL_RGB), stroke_linecap="square"))
    for seg in compute_wall_segments(layout):
        p0, p1 = tr.pt(seg.x1, seg.y1), tr.pt(seg.x2, seg.y2)
        walls_g.add(dwg.line(p0, p1, stroke_width=max(1.5, tr.length(seg.thickness))))

    openings_g = dwg.add(dwg.g())
    for op in layout.openings:
        thickness = WALL_THICKNESS_EXTERNAL_M if op.kind in ("main_door", "window") else WALL_THICKNESS_INTERNAL_M
        gap_w = max(2.0, tr.length(thickness)) + 2

        if op.kind == "window":
            sym = window_symbol(op, thickness)
            p0, p1 = tr.pt(*sym.span[0]), tr.pt(*sym.span[1])
            openings_g.add(dwg.line(p0, p1, stroke="white", stroke_width=gap_w))
            openings_g.add(dwg.line(p0, p1, stroke=rgb_to_hex(WALL_RGB), stroke_width=1))
            for tick in (sym.tick_a, sym.tick_b):
                t0, t1 = tr.pt(*tick[0]), tr.pt(*tick[1])
                openings_g.add(dwg.line(t0, t1, stroke=rgb_to_hex(WALL_RGB), stroke_width=1))
        else:
            sym = door_symbol(op, layout, thickness)
            g0, g1 = tr.pt(*sym.wall_gap[0]), tr.pt(*sym.wall_gap[1])
            openings_g.add(dwg.line(g0, g1, stroke="white", stroke_width=gap_w))
            leaf0, leaf1 = tr.pt(*sym.hinge), tr.pt(*sym.leaf_end)
            openings_g.add(dwg.line(leaf0, leaf1, stroke=rgb_to_hex(WALL_RGB), stroke_width=1))
            arc_px = [tr.pt(*p) for p in sym.arc_points]
            openings_g.add(dwg.polyline(arc_px, stroke=rgb_to_hex(WALL_RGB), fill="none", stroke_width=1))

    labels_g = dwg.add(dwg.g(text_anchor="middle", font_family="Helvetica, Arial, sans-serif"))
    for room in layout.rooms:
        r = room.rect
        cx, cy = tr.pt(r.cx, r.cy)
        room_w_px = tr.length(r.w) - 8
        # Rough average-glyph-width heuristic (no real text metrics available
        # without a renderer) — good enough to keep long en-suite labels
        # from spilling out of narrow rooms.
        font_size = 13
        if len(room.label) * font_size * 0.55 > room_w_px:
            font_size = 10
        if len(room.label) * font_size * 0.55 > room_w_px:
            font_size = 8
        labels_g.add(
            dwg.text(room.label, insert=(cx, cy - 4), fill=rgb_to_hex(TEXT_RGB), font_size=f"{font_size}px")
        )
        labels_g.add(
            dwg.text(
                f"{r.area:.1f} m²",
                insert=(cx, cy + 13),
                fill=rgb_to_hex(DIMENSION_RGB),
                font_size="11px",
            )
        )

    dim_g = dwg.add(dwg.g(stroke=rgb_to_hex(DIMENSION_RGB), font_family="Helvetica, Arial, sans-serif"))
    p0, p1 = tr.pt(0, -0.55), tr.pt(plot.width_m, -0.55)
    dim_g.add(dwg.line(p0, p1, stroke_width=1))
    dim_g.add(
        dwg.text(
            f"{plot.width_m:.2f} m",
            insert=((p0[0] + p1[0]) / 2, p0[1] + 16),
            fill=rgb_to_hex(DIMENSION_RGB),
            font_size="12px",
            text_anchor="middle",
            stroke="none",
        )
    )
    p0, p1 = tr.pt(-0.55, 0), tr.pt(-0.55, plot.length_m)
    dim_g.add(dwg.line(p0, p1, stroke_width=1))
    dim_g.add(
        dwg.text(
            f"{plot.length_m:.2f} m",
            insert=(p0[0] - 8, (p0[1] + p1[1]) / 2),
            fill=rgb_to_hex(DIMENSION_RGB),
            font_size="12px",
            text_anchor="end",
            stroke="none",
        )
    )

    # North arrow
    ncx, ncy = tr.pt(plot.width_m + 1.1, plot.length_m - 0.3)
    north_g = dwg.add(dwg.g(stroke=rgb_to_hex(TEXT_RGB)))
    north_g.add(dwg.line((ncx, ncy + 22), (ncx, ncy - 22), stroke_width=2))
    north_g.add(dwg.polygon([(ncx, ncy - 22), (ncx - 6, ncy - 10), (ncx + 6, ncy - 10)], fill=rgb_to_hex(TEXT_RGB)))
    north_g.add(
        dwg.text(
            "N",
            insert=(ncx, ncy + 34),
            fill=rgb_to_hex(TEXT_RGB),
            font_size="12px",
            text_anchor="middle",
            stroke="none",
            font_family="Helvetica, Arial, sans-serif",
        )
    )

    # Title block
    tb_x, tb_y = 20, plan_height_px + 10
    title_g = dwg.add(dwg.g(font_family="Helvetica, Arial, sans-serif"))
    title_g.add(
        dwg.rect((tb_x, tb_y), (320, TITLE_BLOCK_PX - 20), fill="none", stroke=rgb_to_hex(TEXT_RGB), stroke_width=1)
    )
    title_g.add(
        dwg.text(
            "Rivet — Generated Floor Plan",
            insert=(tb_x + 10, tb_y + 20),
            fill=rgb_to_hex(TEXT_RGB),
            font_size="15px",
        )
    )
    title_g.add(
        dwg.text(
            f"{layout.candidate_id} | score {layout.score}/100 | {metrics.gross_area_sqm:.1f} m² gross",
            insert=(tb_x + 10, tb_y + 38),
            fill=rgb_to_hex(DIMENSION_RGB),
            font_size="11px",
        )
    )

    return dwg.tostring()
