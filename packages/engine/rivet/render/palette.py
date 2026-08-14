"""Shared visual language for both renderers (and the DXF layer colors)."""

from __future__ import annotations

from ..core.models import RoomType

# Soft, desaturated fills — legible on white, printer-friendly.
ROOM_FILL_RGB: dict[RoomType, tuple[int, int, int]] = {
    RoomType.LIVING_ROOM: (255, 236, 210),
    RoomType.MASTER_BEDROOM: (214, 232, 255),
    RoomType.BEDROOM: (223, 240, 255),
    RoomType.KITCHEN: (255, 220, 210),
    RoomType.DINING_ROOM: (255, 245, 200),
    RoomType.BATHROOM: (206, 244, 235),
    RoomType.TOILET: (206, 244, 235),
    RoomType.STUDY: (232, 223, 255),
    RoomType.GARAGE: (222, 222, 222),
    RoomType.STORE: (230, 225, 215),
    RoomType.FOYER: (255, 229, 235),
    RoomType.CORRIDOR: (240, 240, 240),
    RoomType.STAIRCASE: (235, 225, 245),
    RoomType.UTILITY: (225, 235, 225),
    RoomType.BALCONY: (225, 245, 250),
}

DEFAULT_FILL_RGB = (235, 235, 235)

WALL_RGB = (35, 35, 40)
TEXT_RGB = (30, 30, 35)
DIMENSION_RGB = (110, 110, 120)
PLOT_BOUNDARY_RGB = (170, 170, 180)


def fill_for(room_type: RoomType) -> tuple[int, int, int]:
    return ROOM_FILL_RGB.get(room_type, DEFAULT_FILL_RGB)


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)
