"""PNG rendering of a :class:`Layout`, drawn entirely from its geometry —
no dataset imagery involved anywhere in this path.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

from ..core.metrics import LayoutMetrics, compute_metrics
from ..core.models import Layout
from ..core.rules import WALL_THICKNESS_EXTERNAL_M, WALL_THICKNESS_INTERNAL_M
from ..core.walls import compute_wall_segments
from .opening_geometry import door_symbol, window_symbol
from .palette import DIMENSION_RGB, PLOT_BOUNDARY_RGB, TEXT_RGB, WALL_RGB, fill_for

PX_PER_M = 60
MARGIN_PX = 110
TITLE_BLOCK_PX = 84


def _load_font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class _Transform:
    def __init__(self, height_px: int, px_per_m: float):
        self.height_px = height_px
        self.px_per_m = px_per_m

    def pt(self, x_m: float, y_m: float) -> tuple[float, float]:
        return (MARGIN_PX + x_m * self.px_per_m, self.height_px - MARGIN_PX - y_m * self.px_per_m)

    def length(self, meters: float) -> float:
        return meters * self.px_per_m


def _dashed_rect(draw: ImageDraw.ImageDraw, tr: _Transform, x0, y0, x1, y1, color, dash=6, gap=5):
    for (ax, ay, bx, by) in [(x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)]:
        p0, p1 = tr.pt(ax, ay), tr.pt(bx, by)
        length = ((p1[0] - p0[0]) ** 2 + (p1[1] - p0[1]) ** 2) ** 0.5
        if length == 0:
            continue
        ux, uy = (p1[0] - p0[0]) / length, (p1[1] - p0[1]) / length
        d = 0.0
        while d < length:
            seg_end = min(d + dash, length)
            draw.line(
                [(p0[0] + ux * d, p0[1] + uy * d), (p0[0] + ux * seg_end, p0[1] + uy * seg_end)],
                fill=color,
                width=1,
            )
            d += dash + gap


def _draw_dimensions(draw: ImageDraw.ImageDraw, tr: _Transform, layout: Layout, font):
    plot = layout.plot
    # Bottom: overall width. Left: overall length.
    y_dim = -0.55
    p0, p1 = tr.pt(0, y_dim), tr.pt(plot.width_m, y_dim)
    draw.line([p0, p1], fill=DIMENSION_RGB, width=1)
    label = f"{plot.width_m:.2f} m"
    draw.text(((p0[0] + p1[0]) / 2, p0[1] + 4), label, fill=DIMENSION_RGB, font=font, anchor="ma")

    x_dim = -0.55
    p0, p1 = tr.pt(x_dim, 0), tr.pt(x_dim, plot.length_m)
    draw.line([p0, p1], fill=DIMENSION_RGB, width=1)
    label = f"{plot.length_m:.2f} m"
    draw.text((p0[0] - 6, (p0[1] + p1[1]) / 2), label, fill=DIMENSION_RGB, font=font, anchor="rm")


def _draw_north_arrow(draw: ImageDraw.ImageDraw, tr: _Transform, layout: Layout, font):
    cx, cy = tr.pt(layout.plot.width_m + 1.1, layout.plot.length_m - 0.3)
    r = 22
    draw.line([(cx, cy + r), (cx, cy - r)], fill=TEXT_RGB, width=2)
    draw.polygon([(cx, cy - r), (cx - 6, cy - r + 12), (cx + 6, cy - r + 12)], fill=TEXT_RGB)
    draw.text((cx, cy + r + 6), "N", fill=TEXT_RGB, font=font, anchor="ma")


def _draw_title_block(
    draw: ImageDraw.ImageDraw, plan_height_px: int, layout: Layout, metrics: LayoutMetrics, font, font_small
):
    x0, y0 = 20, plan_height_px + 10
    x1, y1 = 20 + 320, plan_height_px + TITLE_BLOCK_PX - 10
    draw.rectangle([x0, y0, x1, y1], outline=TEXT_RGB, width=1)
    draw.text((x0 + 10, y0 + 8), "Rivet — Generated Floor Plan", fill=TEXT_RGB, font=font)
    draw.text(
        (x0 + 10, y0 + 30),
        f"{layout.candidate_id}  |  score {layout.score}/100  |  {metrics.gross_area_sqm:.1f} m² gross",
        fill=DIMENSION_RGB,
        font=font_small,
    )
    draw.text((x0 + 10, y0 + 48), "Scale not guaranteed — see printed dimensions", fill=DIMENSION_RGB, font=font_small)


def render_png(layout: Layout, px_per_m: float = PX_PER_M) -> Image.Image:
    metrics = compute_metrics(layout, layout.ruleset)
    plot = layout.plot
    width_px = int(plot.width_m * px_per_m) + 2 * MARGIN_PX
    plan_height_px = int(plot.length_m * px_per_m) + 2 * MARGIN_PX
    height_px = plan_height_px + TITLE_BLOCK_PX

    img = Image.new("RGB", (width_px, height_px), "white")
    draw = ImageDraw.Draw(img)
    tr = _Transform(plan_height_px, px_per_m)

    font_label = _load_font(13)
    font_small_label = _load_font(11)
    font_title = _load_font(15)
    font_dim = _load_font(12)

    _dashed_rect(draw, tr, 0, 0, plot.width_m, plot.length_m, PLOT_BOUNDARY_RGB)

    for room in layout.rooms:
        r = room.rect
        p0 = tr.pt(r.x, r.y2)
        p1 = tr.pt(r.x2, r.y)
        draw.rectangle([p0[0], p0[1], p1[0], p1[1]], fill=fill_for(room.room_type))

    for seg in compute_wall_segments(layout):
        p0, p1 = tr.pt(seg.x1, seg.y1), tr.pt(seg.x2, seg.y2)
        draw.line([p0, p1], fill=WALL_RGB, width=max(2, round(tr.length(seg.thickness))))

    for op in layout.openings:
        thickness = WALL_THICKNESS_EXTERNAL_M if op.kind in ("main_door", "window") else WALL_THICKNESS_INTERNAL_M
        gap_w = max(2, round(tr.length(thickness))) + 2

        if op.kind == "window":
            sym = window_symbol(op, thickness)
            p0, p1 = tr.pt(*sym.span[0]), tr.pt(*sym.span[1])
            draw.line([p0, p1], fill="white", width=gap_w)
            draw.line([p0, p1], fill=WALL_RGB, width=1)
            for tick in (sym.tick_a, sym.tick_b):
                t0, t1 = tr.pt(*tick[0]), tr.pt(*tick[1])
                draw.line([t0, t1], fill=WALL_RGB, width=1)
        else:
            sym = door_symbol(op, layout, thickness)
            g0, g1 = tr.pt(*sym.wall_gap[0]), tr.pt(*sym.wall_gap[1])
            draw.line([g0, g1], fill="white", width=gap_w)
            leaf0, leaf1 = tr.pt(*sym.hinge), tr.pt(*sym.leaf_end)
            draw.line([leaf0, leaf1], fill=WALL_RGB, width=1)
            arc_px = [tr.pt(*p) for p in sym.arc_points]
            draw.line(arc_px, fill=WALL_RGB, width=1)

    font_tiny_label = _load_font(9)
    for room in layout.rooms:
        r = room.rect
        cx, cy = tr.pt(r.cx, r.cy)
        room_w_px = tr.length(r.w) - 8
        label_font = font_label
        if draw.textlength(room.label, font=label_font) > room_w_px:
            label_font = font_small_label
        if draw.textlength(room.label, font=label_font) > room_w_px:
            label_font = font_tiny_label
        draw.text((cx, cy - 7), room.label, fill=TEXT_RGB, font=label_font, anchor="mm")
        draw.text((cx, cy + 9), f"{r.area:.1f} m²", fill=DIMENSION_RGB, font=font_small_label, anchor="mm")

    _draw_dimensions(draw, tr, layout, font_dim)
    _draw_north_arrow(draw, tr, layout, font_dim)
    _draw_title_block(draw, plan_height_px, layout, metrics, font_title, font_small_label)

    return img


def render_png_bytes(layout: Layout, px_per_m: float = PX_PER_M) -> bytes:
    buf = io.BytesIO()
    render_png(layout, px_per_m).save(buf, format="PNG")
    return buf.getvalue()
