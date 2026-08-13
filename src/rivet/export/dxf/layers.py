"""Layer schemes.

Two named schemes map the same logical layer keys to different DXF layer
names: ``"aia"`` (default, AIA CAD Layer Guidelines-style names, per Phase
4 item 6) and ``"legacy"`` (the plain names Rivet used before Phase 4,
kept for anyone already depending on them). Every other module in this
package refers to layers only by their logical key, never a literal
string, so the scheme is genuinely swappable in one place.
"""

from __future__ import annotations

from ezdxf.document import Drawing
from ezdxf.lldxf.const import DXFValueError

# Logical layer keys used throughout this package.
WALLS_EXT = "walls_ext"
WALLS_INT = "walls_int"
WALLS_HATCH = "walls_hatch"
DOORS = "doors"
WINDOWS = "windows"
FIXTURES = "fixtures"
ROOMS = "rooms"
TEXT = "text"
DIMENSIONS = "dimensions"
PLOT_BOUNDARY = "plot_boundary"
TITLE_BLOCK = "title_block"
SCHEDULE = "schedule"
NON_PLOT = "non_plot"

AIA_LAYER_NAMES: dict[str, str] = {
    WALLS_EXT: "A-WALL-EXTR",
    WALLS_INT: "A-WALL-PART",
    WALLS_HATCH: "A-WALL-PATT",
    DOORS: "A-DOOR",
    WINDOWS: "A-GLAZ",
    FIXTURES: "A-FLOR-FIXT",
    ROOMS: "A-FLOR-IDEN",
    TEXT: "A-ANNO-TEXT",
    DIMENSIONS: "A-ANNO-DIMS",
    PLOT_BOUNDARY: "A-SITE-PROP",
    TITLE_BLOCK: "A-ANNO-TTLB",
    SCHEDULE: "A-ANNO-SCHD",
    NON_PLOT: "A-ANNO-NPLT",
}

# Rivet's original (pre-Phase-4) layer names -- selectable via
# layer_scheme="legacy" for backward compatibility.
LEGACY_LAYER_NAMES: dict[str, str] = {
    WALLS_EXT: "WALLS-EXTERIOR",
    WALLS_INT: "WALLS-INTERIOR",
    WALLS_HATCH: "WALLS-PATTERN",
    DOORS: "DOORS",
    WINDOWS: "WINDOWS",
    FIXTURES: "FIXTURES",
    ROOMS: "ROOMS",
    TEXT: "TEXT",
    DIMENSIONS: "DIMENSIONS",
    PLOT_BOUNDARY: "PLOT-BOUNDARY",
    TITLE_BLOCK: "TITLEBLOCK",
    SCHEDULE: "SCHEDULES",
    NON_PLOT: "VIEWPORT",
}

LAYER_SCHEMES: dict[str, dict[str, str]] = {
    "aia": AIA_LAYER_NAMES,
    "legacy": LEGACY_LAYER_NAMES,
}

DEFAULT_LAYER_SCHEME = "aia"

# AutoCAD Color Index per logical layer -- same across both schemes, since
# color is a drawing convention, not a naming one.
_LAYER_COLORS: dict[str, int] = {
    WALLS_EXT: 7,  # black/white
    WALLS_INT: 8,  # gray
    WALLS_HATCH: 8,
    DOORS: 5,  # blue
    WINDOWS: 4,  # cyan
    FIXTURES: 6,  # magenta
    ROOMS: 9,  # light gray
    TEXT: 7,
    DIMENSIONS: 3,  # green
    PLOT_BOUNDARY: 9,
    TITLE_BLOCK: 7,
    SCHEDULE: 7,
    NON_PLOT: 251,  # light gray, and non-plotting regardless of color
}

# Lineweight in hundredths of a millimetre (ezdxf's native unit for this
# DXF group code) -- heaviest on cut walls, lightest on annotation, per
# Phase 4 item 5.
_LAYER_LINEWEIGHTS: dict[str, int] = {
    WALLS_EXT: 50,
    WALLS_INT: 35,
    WALLS_HATCH: 9,
    DOORS: 25,
    WINDOWS: 18,
    FIXTURES: 18,
    ROOMS: 9,
    TEXT: 13,
    DIMENSIONS: 13,
    PLOT_BOUNDARY: 9,
    TITLE_BLOCK: 25,
    SCHEDULE: 13,
    NON_PLOT: 0,
}


class LayerMap:
    """Resolves a logical layer key to this document's actual layer name,
    for the scheme it was built with.
    """

    def __init__(self, scheme: str) -> None:
        if scheme not in LAYER_SCHEMES:
            raise ValueError(f"Unknown layer_scheme {scheme!r}; choose one of {sorted(LAYER_SCHEMES)}")
        self.scheme = scheme
        self._names = LAYER_SCHEMES[scheme]

    def __getitem__(self, key: str) -> str:
        return self._names[key]


def setup_layers(doc: Drawing, scheme: str = DEFAULT_LAYER_SCHEME) -> LayerMap:
    """Create every logical layer in ``doc`` under the given scheme's
    names, with its color and lineweight, and return the LayerMap to
    resolve logical keys to those names.
    """
    layer_map = LayerMap(scheme)
    for key, name in layer_map._names.items():
        try:
            layer = doc.layers.add(name=name, color=_LAYER_COLORS[key])
        except DXFValueError:
            layer = doc.layers.get(name)
        layer.dxf.lineweight = _LAYER_LINEWEIGHTS[key]
        if key == NON_PLOT:
            layer.dxf.plot = 0
    return layer_map
