"""Millimetre coordinate conversion and print-scale sizing.

Every geometric figure on ``Layout`` (rooms, walls, openings) is in
metres -- that's core/render's native unit and stays untouched here (see
CLAUDE.md: this module is the one place that converts, nobody upstream
does). DXF output for Indian CAD/construction practice needs millimetre
coordinates instead (Phase 4's highest-priority item -- metre-unit output
is unusable for every Indian practice), so every coordinate is scaled by
``MM_PER_M`` exactly once, at the point it's written into an ezdxf call.

The drawing is sized for a fixed print scale (``PRINT_SCALE`` = 1:100,
per docs/prompts.md Phase 4 item 1's own instruction) -- DIMSCALE and
every annotation height below are nominal "paper" sizes in mm that ezdxf/
AutoCAD multiply by DIMSCALE (dimensions) or that this module multiplies
by PRINT_SCALE directly (plain TEXT, which DIMSCALE doesn't reach) to get
their actual model-space size.
"""

from __future__ import annotations

MM_PER_M = 1000.0
PRINT_SCALE = 100  # 1:100

Point = tuple[float, float]


def mm(value_m: float) -> float:
    """Convert a single metre value to millimetres."""
    return value_m * MM_PER_M


def pt(x_m: float, y_m: float) -> Point:
    """Convert a metre-space (x, y) point to millimetres."""
    return (x_m * MM_PER_M, y_m * MM_PER_M)


def paper_mm_to_model(paper_mm: float) -> float:
    """Nominal size on the printed sheet (mm) -> actual model-space size
    (mm), given the fixed 1:100 print scale. Used for plain TEXT/HATCH
    pattern scale, which DIMSCALE doesn't touch.
    """
    return paper_mm * PRINT_SCALE


# Nominal (paper-mm) annotation sizes -- converted via paper_mm_to_model()
# wherever they're used. Kept in one place so the sheet reads consistently
# at 1:100 regardless of plot size.
TITLE_TEXT_MM = 3.5
ROOM_LABEL_MM = 3.0
ROOM_AREA_MM = 2.2
SCHEDULE_TEXT_MM = 2.2
SHEET_TITLE_TEXT_MM = 5.0
