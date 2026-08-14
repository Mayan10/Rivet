"""Free-tier watermarking, applied by the worker (jobs/tasks.py) to
already-rendered PNG/SVG bytes -- post-processing in the service layer,
not a parameter on the engine's renderers. See docs/prompts.md Phase 9
status for why: ``packages/engine/rivet/render/`` is a protected pure-library
directory for these service phases, and a business-model watermark is a
service-layer concern layered on a finished drawing, not something the
renderer needs geometry-aware knowledge to draw -- it never needs to know
plans exist, matching CLAUDE.md's own layer-separation rule.

DXF isn't watermarked: free tier doesn't get DXF at all
(Entitlements.dxf_export gates the whole format, not a watermarked
version of it -- see api/v1/generations.py's download handler).
"""

from __future__ import annotations

import io
import re

from PIL import Image, ImageDraw, ImageFont

WATERMARK_TEXT = "RIVET · FREE PREVIEW"


def watermark_png(data: bytes) -> bytes:
    base = Image.open(io.BytesIO(data)).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=22)

    text_w = draw.textlength(WATERMARK_TEXT, font=font)
    step_x, step_y = int(text_w) + 80, 90
    tile = Image.new("RGBA", (step_x, step_y), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    tile_draw.text((0, step_y // 2 - 11), WATERMARK_TEXT, font=font, fill=(120, 120, 130, 90))
    tile = tile.rotate(-30, expand=True)

    for y in range(-tile.height, base.height + tile.height, step_y):
        for x in range(-tile.width, base.width + tile.width, step_x):
            overlay.alpha_composite(tile, (x, y))

    watermarked = Image.alpha_composite(base, overlay)
    out = io.BytesIO()
    watermarked.convert("RGB").save(out, format="PNG")
    return out.getvalue()


_SVG_SIZE_RE = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')


def watermark_svg(svg: str) -> str:
    match = _SVG_SIZE_RE.search(svg)
    width, height = (float(match.group(1)), float(match.group(2))) if match else (1000.0, 1000.0)

    tiles = []
    step = 220
    for y in range(0, int(height) + step, step):
        for x in range(0, int(width) + step, step):
            tiles.append(
                f'<text x="{x}" y="{y}" font-size="16" fill="#787882" fill-opacity="0.35" '
                f'transform="rotate(-30 {x} {y})">{WATERMARK_TEXT}</text>'
            )
    watermark_group = f'<g>{"".join(tiles)}</g></svg>'
    return svg[: svg.rindex("</svg>")] + watermark_group
