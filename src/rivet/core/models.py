"""Data model for floor plan generation.

All spatial quantities are in meters, in a right-handed coordinate system
with the origin at the plot's southwest corner (x -> east, y -> north).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .validator import Violation


class RoomType(str, Enum):
    LIVING_ROOM = "living_room"
    MASTER_BEDROOM = "master_bedroom"
    BEDROOM = "bedroom"
    KITCHEN = "kitchen"
    DINING_ROOM = "dining_room"
    BATHROOM = "bathroom"
    TOILET = "toilet"
    STUDY = "study"
    GARAGE = "garage"
    STORE = "store"
    FOYER = "foyer"
    CORRIDOR = "corridor"
    STAIRCASE = "staircase"
    UTILITY = "utility"
    BALCONY = "balcony"


class Orientation(str, Enum):
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"


class Ruleset(str, Enum):
    """Which building-code ruleset core/rules.py validates and scores
    against. Lives here (not in rules.py) so both PlotSpec/GenerationRequest
    and rules.py can reference it without a circular import.
    """

    TNCDBR_2019 = "tncdbr_2019"
    GENERIC = "generic"


# Rooms that need daylight/ventilation and therefore a plot-boundary wall.
HABITABLE_ROOM_TYPES = frozenset(
    {
        RoomType.LIVING_ROOM,
        RoomType.MASTER_BEDROOM,
        RoomType.BEDROOM,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
        RoomType.STUDY,
    }
)

# Rooms that are purely circulation/service space, excluded from most
# "does this feel like a room" checks (aspect ratio, exterior access).
SERVICE_ROOM_TYPES = frozenset({RoomType.CORRIDOR, RoomType.STAIRCASE})


@dataclass(frozen=True)
class PlotSpec:
    """The buildable land parcel.

    ``abutting_road_width_m`` and ``proposed_height_m`` are optional inputs
    to the TNCDBR_2019 ruleset's setback table (Rule 35, keyed by road
    width and building height, not plot area). When omitted,
    ``core/rules.py`` falls back to documented, non-cited assumptions
    (``ASSUMED_ROAD_WIDTH_M``, ``num_floors * ASSUMED_FLOOR_HEIGHT_M``) --
    supply the real values whenever they're known, since they change which
    setback tier applies.
    """

    width_m: float
    length_m: float
    entrance: Orientation = Orientation.NORTH
    num_floors: int = 1
    abutting_road_width_m: float | None = None
    proposed_height_m: float | None = None

    def __post_init__(self) -> None:
        if self.width_m <= 0 or self.length_m <= 0:
            raise ValueError("Plot dimensions must be positive")
        if self.num_floors < 1:
            raise ValueError("num_floors must be >= 1")
        if self.abutting_road_width_m is not None and self.abutting_road_width_m <= 0:
            raise ValueError("abutting_road_width_m must be positive")
        if self.proposed_height_m is not None and self.proposed_height_m <= 0:
            raise ValueError("proposed_height_m must be positive")

    @property
    def area_sqm(self) -> float:
        return self.width_m * self.length_m


@dataclass(frozen=True)
class RoomRequirement:
    """One requested room (or group of identical rooms)."""

    room_type: RoomType
    count: int = 1
    target_area_sqm: float | None = None
    attached_bathroom: bool = False
    label: str | None = None

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("count must be >= 1")
        if self.target_area_sqm is not None and self.target_area_sqm <= 0:
            raise ValueError("target_area_sqm must be positive")


@dataclass
class GenerationRequest:
    plot: PlotSpec
    rooms: list[RoomRequirement]
    num_candidates: int = 3
    seed: int | None = None
    ruleset: Ruleset = Ruleset.TNCDBR_2019

    def __post_init__(self) -> None:
        if not self.rooms:
            raise ValueError("At least one room requirement is needed")
        if self.num_candidates < 1:
            raise ValueError("num_candidates must be >= 1")


@dataclass
class Rect:
    """An axis-aligned rectangle in plan coordinates (meters)."""

    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def min_side(self) -> float:
        return min(self.w, self.h)

    @property
    def aspect_ratio(self) -> float:
        return max(self.w, self.h) / max(min(self.w, self.h), 1e-9)

    def contains(self, other: Rect, tol: float = 1e-6) -> bool:
        return (
            self.x - tol <= other.x
            and self.y - tol <= other.y
            and self.x2 + tol >= other.x2
            and self.y2 + tol >= other.y2
        )

    def overlaps(self, other: Rect, eps: float = 1e-6) -> bool:
        return not (
            self.x2 <= other.x + eps
            or other.x2 <= self.x + eps
            or self.y2 <= other.y + eps
            or other.y2 <= self.y + eps
        )


@dataclass
class RoomInstance:
    id: str
    room_type: RoomType
    label: str
    rect: Rect
    floor: int = 0


@dataclass
class Opening:
    """A door or window placed on a wall segment."""

    kind: str  # "door" | "main_door" | "window"
    x: float
    y: float
    width: float
    axis: str  # "horizontal" (wall runs along x) | "vertical" (wall runs along y)
    room_id: str
    connects_to: str | None = None  # other room id, for interior doors


@dataclass
class Layout:
    """One fully-formed floor plan candidate."""

    candidate_id: str
    plot: PlotSpec
    buildable: Rect
    rooms: list[RoomInstance] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)

    def room(self, room_id: str) -> RoomInstance:
        for r in self.rooms:
            if r.id == room_id:
                return r
        raise KeyError(room_id)


@dataclass
class InfeasibleResult:
    """Returned by ``core.generator.generate`` instead of layouts when
    every searched candidate fails hard validation (see
    ``core/validator.py``). Callers (CLI, API) must check for this
    explicitly -- ``generate`` never silently returns a code-violating
    layout, and it never raises for this case either, so an infeasible
    request is a real, explainable outcome rather than an exception a
    caller has to remember to catch.
    """

    request: GenerationRequest
    hardest_violations: list[Violation]  # the closest-to-passing candidate's violations
    message: str
