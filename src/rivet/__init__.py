"""Rivet — a generative floor plan engine.

Given a plot and a set of room requirements, Rivet designs a new floor plan
from scratch (no dataset lookup), scores it against a documented set of
residential design rules, renders it, and exports it to DXF.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("rivet-floorplan")
except PackageNotFoundError:  # pragma: no cover - local/editable checkout
    __version__ = "0.0.0+dev"

__all__ = ["__version__"]
