"""Rectangle adjacency helpers shared by the layout engine, scorer, and
opening placer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Orientation, Rect

# Below this, two rects "touching" isn't a usable doorway -- shared by the
# scorer (soft: penalizes a missed preferred adjacency) and the validator
# (hard: rejects a cited avoided adjacency that's nonetheless realized).
MIN_USABLE_SHARED_WALL_M = 1.0


@dataclass(frozen=True)
class SharedWall:
    """A segment of wall shared by two rectangles."""

    axis: str  # "horizontal" -> rects stacked in y, wall runs along x
    coord: float  # the shared x (if axis=="vertical") or y (if "horizontal")
    lo: float  # overlap range start along the wall
    hi: float  # overlap range end along the wall

    @property
    def length(self) -> float:
        return self.hi - self.lo

    @property
    def mid(self) -> float:
        return (self.lo + self.hi) / 2


def shared_wall(a: Rect, b: Rect, tol: float = 1e-3, min_length: float = 0.5) -> SharedWall | None:
    """Return the wall segment shared by two rectangles, or None.

    Two rects share a *vertical* wall when one's right edge touches the
    other's left edge (or vice versa) and their y-ranges overlap by at
    least ``min_length``. Symmetric for a *horizontal* wall on x/y edges.
    """
    # Vertical wall: a.x2 touches b.x, or b.x2 touches a.x
    if abs(a.x2 - b.x) <= tol or abs(b.x2 - a.x) <= tol:
        coord = a.x2 if abs(a.x2 - b.x) <= tol else a.x
        lo = max(a.y, b.y)
        hi = min(a.y2, b.y2)
        if hi - lo >= min_length:
            return SharedWall(axis="vertical", coord=coord, lo=lo, hi=hi)

    # Horizontal wall: a.y2 touches b.y, or b.y2 touches a.y
    if abs(a.y2 - b.y) <= tol or abs(b.y2 - a.y) <= tol:
        coord = a.y2 if abs(a.y2 - b.y) <= tol else a.y
        lo = max(a.x, b.x)
        hi = min(a.x2, b.x2)
        if hi - lo >= min_length:
            return SharedWall(axis="horizontal", coord=coord, lo=lo, hi=hi)

    return None


def on_boundary(rect: Rect, boundary: Rect, tol: float = 1e-3) -> bool:
    """Whether ``rect`` has at least one edge flush with ``boundary``'s edge."""
    return (
        abs(rect.x - boundary.x) <= tol
        or abs(rect.x2 - boundary.x2) <= tol
        or abs(rect.y - boundary.y) <= tol
        or abs(rect.y2 - boundary.y2) <= tol
    )


def boundary_edges(rect: Rect, boundary: Rect, tol: float = 1e-3) -> list[SharedWall]:
    """Edges of ``rect`` that lie flush on ``boundary`` (candidate window walls)."""
    edges: list[SharedWall] = []
    if abs(rect.x - boundary.x) <= tol:
        edges.append(SharedWall(axis="vertical", coord=rect.x, lo=rect.y, hi=rect.y2))
    if abs(rect.x2 - boundary.x2) <= tol:
        edges.append(SharedWall(axis="vertical", coord=rect.x2, lo=rect.y, hi=rect.y2))
    if abs(rect.y - boundary.y) <= tol:
        edges.append(SharedWall(axis="horizontal", coord=rect.y, lo=rect.x, hi=rect.x2))
    if abs(rect.y2 - boundary.y2) <= tol:
        edges.append(SharedWall(axis="horizontal", coord=rect.y2, lo=rect.x, hi=rect.x2))
    return edges


_ENTRANCE_EDGE_MAP = {
    Orientation.NORTH: "y2",
    Orientation.SOUTH: "y",
    Orientation.EAST: "x2",
    Orientation.WEST: "x",
}


def entrance_edge(entrance: Orientation) -> str:
    """Which side of the buildable rect the front door sits on."""
    return _ENTRANCE_EDGE_MAP[entrance]


def room_touches_edge(rect: Rect, boundary: Rect, edge: str, tol: float = 1e-3) -> bool:
    if edge == "y2":
        return abs(rect.y2 - boundary.y2) <= tol
    if edge == "y":
        return abs(rect.y - boundary.y) <= tol
    if edge == "x2":
        return abs(rect.x2 - boundary.x2) <= tol
    return abs(rect.x - boundary.x) <= tol
