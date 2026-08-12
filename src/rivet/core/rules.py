"""The design rulebook.

Two rulesets are shipped, selected via :class:`Ruleset`:

- ``TNCDBR_2019``: cited values from the Tamil Nadu Combined Development
  and Building Rules, 2019 (base text, February 2019 edition). Source and
  full extraction notes: ``docs/regulatory_sources.md``. This is the
  default.
- ``GENERIC``: uncited placeholder values (the values this module shipped
  with before this rulebook rewrite), kept as a fallback for jurisdictions
  without a cited ruleset yet. Every value in it is explicitly flagged as
  uncited — do not treat it as code-compliant.

Every :class:`RoomRule` splits its area/width into two different kinds of
number, and they must not be confused:

- ``min_area_sqm`` / ``min_width_m`` are the **hard legal minimum** per the
  ruleset's citation. ``core/validator.py`` rejects a layout that falls
  below these — they are never just a scoring penalty.
- ``default_area_sqm`` is a **soft generation target**: how big the layout
  search *aims* to make a room absent a user-specified target. It is a
  design choice, not a code minimum, and is not required to carry a
  citation (it never rejects anything).

See ``docs/design_rules.md`` for the human-readable summary of what's
shipped, and ``docs/regulatory_sources.md`` for the raw source extraction
this module is built from, including what's still uncited (door widths;
the NBC 2016 GENERIC room-minimum values; whether any of TNCDBR's
amendment G.O.s post-2019 touch these clauses).
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import RoomType, Ruleset

# ---------------------------------------------------------------------------
# Ruleset selection
# ---------------------------------------------------------------------------

DEFAULT_RULESET = Ruleset.TNCDBR_2019

# Used when PlotSpec doesn't specify abutting_road_width_m / proposed_height_m.
# These are assumptions of convenience, not code values -- callers should
# supply the real figures whenever they're known, since they change which
# TNCDBR 2019 Rule 35 setback tier applies.
ASSUMED_ROAD_WIDTH_M = 9.0
ASSUMED_FLOOR_HEIGHT_M = 3.0  # per floor, for estimating height from num_floors


# ---------------------------------------------------------------------------
# Per-room-type space standards
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoomRule:
    min_area_sqm: float  # HARD legal minimum -- see `citation`
    min_width_m: float  # HARD legal minimum -- see `citation`
    default_area_sqm: float  # SOFT generation target, not a code value
    max_aspect_ratio: float = 2.2  # long-side : short-side comfort ceiling (soft)
    exterior_wall_required: bool = False
    citation: str = ""


# TNCDBR 2019, Rule 52(5)(b): "The area of habitable room shall not be less
# than 7.5 sqm with a minimum width of 2.4m. Pooja room, or store room shall
# not be taken as a habitable room." Applies uniformly to any room "occupied
# or designed for occupancy ... for study, living or sleeping purposes"
# (Rule 2(56)) -- so the same hard floor covers living room, bedrooms, and
# study. default_area_sqm below is a soft design target, not part of the
# citation.
_HABITABLE_ROOM_CITATION = "TNCDBR 2019, Rule 52(5)(b)"

_TNCDBR_2019_ROOM_RULES: dict[RoomType, RoomRule] = {
    RoomType.LIVING_ROOM: RoomRule(7.5, 2.4, 18.0, 2.2, True, _HABITABLE_ROOM_CITATION),
    RoomType.MASTER_BEDROOM: RoomRule(7.5, 2.4, 14.0, 2.0, True, _HABITABLE_ROOM_CITATION),
    RoomType.BEDROOM: RoomRule(7.5, 2.4, 11.0, 2.0, True, _HABITABLE_ROOM_CITATION),
    RoomType.STUDY: RoomRule(7.5, 2.4, 9.0, 2.0, True, _HABITABLE_ROOM_CITATION),
    # Rule 52(6)(b): kitchen minimum is context-dependent on whether a
    # separate dining area exists in the same dwelling -- 5.0sqm/1.8m if so,
    # 7.5sqm/2.1m if the kitchen also serves as the dining space. The
    # smaller (more permissive) figure is used here as the table default;
    # core/validator.py applies the correct context-dependent minimum by
    # checking whether the layout also has a DINING_ROOM.
    RoomType.KITCHEN: RoomRule(5.0, 1.8, 8.0, 2.4, True, "TNCDBR 2019, Rule 52(6)(b)"),
    RoomType.DINING_ROOM: RoomRule(7.5, 2.4, 10.0, 2.0, False, _HABITABLE_ROOM_CITATION),
    RoomType.BATHROOM: RoomRule(1.4, 1.0, 3.5, 2.2, False, "TNCDBR 2019, Rule 52(7)(b)"),
    RoomType.TOILET: RoomRule(1.0, 0.9, 1.8, 2.2, False, "TNCDBR 2019, Rule 52(7)(b)"),
    RoomType.GARAGE: RoomRule(18.0, 3.0, 18.0, 2.2, False, "TNCDBR 2019, Rule 52(10)(a) [private garage, 3.0m x 6.0m min]"),
    RoomType.STORE: RoomRule(3.0, 1.2, 3.0, 2.2, False, "TNCDBR 2019, Rule 52(9) [store room, no cited min width]"),
    # Not covered by a specific TNCDBR Rule 52 sub-clause found so far --
    # kept as soft-only design targets with min == default so the validator
    # never rejects on these until a citation is found. See
    # docs/regulatory_sources.md "Gaps".
    RoomType.FOYER: RoomRule(2.5, 1.2, 4.0, 2.5, False, "uncited placeholder"),
    RoomType.CORRIDOR: RoomRule(1.0, 1.0, 2.5, 6.0, False, "TNCDBR 2019, Rule 42(i) [residential corridor/verandah min width 1.0m; area is not separately specified]"),
    RoomType.STAIRCASE: RoomRule(4.0, 0.75, 5.0, 3.0, False, "TNCDBR 2019, Rule 52(17)(a)(i) [staircase min width 0.75m ordinary residential; area not separately specified]"),
    RoomType.UTILITY: RoomRule(2.5, 1.2, 3.5, 2.4, False, "uncited placeholder"),
    RoomType.BALCONY: RoomRule(2.0, 1.0, 3.5, 3.0, True, "uncited placeholder"),
}

# GENERIC fallback: the original uncited placeholder values this module
# shipped with before the TNCDBR rewrite. Explicitly not code-cited --
# only use this ruleset when no jurisdiction-specific ruleset is available,
# and don't present its output as compliant with any particular code.
_GENERIC_ROOM_RULES: dict[RoomType, RoomRule] = {
    RoomType.LIVING_ROOM: RoomRule(11.0, 2.7, 18.0, 2.2, True, "uncited placeholder"),
    RoomType.MASTER_BEDROOM: RoomRule(11.0, 2.7, 14.0, 2.0, True, "uncited placeholder"),
    RoomType.BEDROOM: RoomRule(9.5, 2.4, 11.0, 2.0, True, "uncited placeholder"),
    RoomType.KITCHEN: RoomRule(5.0, 1.8, 8.0, 2.4, True, "uncited placeholder"),
    RoomType.DINING_ROOM: RoomRule(7.5, 2.4, 10.0, 2.0, False, "uncited placeholder"),
    RoomType.BATHROOM: RoomRule(2.2, 1.2, 3.5, 2.2, False, "uncited placeholder"),
    RoomType.TOILET: RoomRule(1.5, 0.9, 1.8, 2.2, False, "uncited placeholder"),
    RoomType.STUDY: RoomRule(6.5, 2.1, 9.0, 2.0, True, "uncited placeholder"),
    RoomType.GARAGE: RoomRule(15.0, 2.7, 18.0, 2.2, False, "uncited placeholder"),
    RoomType.STORE: RoomRule(2.0, 1.2, 3.0, 2.2, False, "uncited placeholder"),
    RoomType.FOYER: RoomRule(2.5, 1.2, 4.0, 2.5, False, "uncited placeholder"),
    RoomType.CORRIDOR: RoomRule(1.5, 1.0, 2.5, 6.0, False, "uncited placeholder"),
    RoomType.STAIRCASE: RoomRule(4.0, 1.0, 5.0, 3.0, False, "uncited placeholder"),
    RoomType.UTILITY: RoomRule(2.5, 1.2, 3.5, 2.4, False, "uncited placeholder"),
    RoomType.BALCONY: RoomRule(2.0, 1.0, 3.5, 3.0, True, "uncited placeholder"),
}

_ROOM_RULES_BY_RULESET: dict[Ruleset, dict[RoomType, RoomRule]] = {
    Ruleset.TNCDBR_2019: _TNCDBR_2019_ROOM_RULES,
    Ruleset.GENERIC: _GENERIC_ROOM_RULES,
}

# Backward-compatible alias: the default ruleset's table, for callers that
# don't (yet) select a ruleset explicitly (e.g. `rivet rules` CLI output).
ROOM_RULES: dict[RoomType, RoomRule] = _ROOM_RULES_BY_RULESET[DEFAULT_RULESET]


def room_rules_for(ruleset: Ruleset = DEFAULT_RULESET) -> dict[RoomType, RoomRule]:
    return _ROOM_RULES_BY_RULESET[ruleset]


def rule_for(room_type: RoomType, ruleset: Ruleset = DEFAULT_RULESET) -> RoomRule:
    try:
        return _ROOM_RULES_BY_RULESET[ruleset][room_type]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f"No design rule registered for room type {room_type!r}") from exc


# ---------------------------------------------------------------------------
# Kitchen's context-dependent legal minimum (TNCDBR 2019, Rule 52(6)(b))
# ---------------------------------------------------------------------------

# "The area of a kitchen where separate dining area is provided shall be
# not less than 5.0 sqm with a minimum width of 1.8m ... A kitchen, which
# is intended for use as a dining area also, shall have a floor area of
# not less than 7.5 sqm with a minimum width of 2.1m."
KITCHEN_WITH_DINING_MIN_AREA_SQM = 5.0
KITCHEN_WITH_DINING_MIN_WIDTH_M = 1.8
KITCHEN_AS_DINING_MIN_AREA_SQM = 7.5
KITCHEN_AS_DINING_MIN_WIDTH_M = 2.1
KITCHEN_MIN_CITATION = "TNCDBR 2019, Rule 52(6)(b)"


def kitchen_minimum(has_separate_dining_room: bool) -> tuple[float, float]:
    """Return (min_area_sqm, min_width_m) for a kitchen, per Rule 52(6)(b)."""
    if has_separate_dining_room:
        return KITCHEN_WITH_DINING_MIN_AREA_SQM, KITCHEN_WITH_DINING_MIN_WIDTH_M
    return KITCHEN_AS_DINING_MIN_AREA_SQM, KITCHEN_AS_DINING_MIN_WIDTH_M


# ---------------------------------------------------------------------------
# Construction standards
# ---------------------------------------------------------------------------

WALL_THICKNESS_EXTERNAL_M = 0.23  # ~9in masonry, load-bearing perimeter wall
WALL_THICKNESS_INTERNAL_M = 0.115  # ~4.5in half-brick partition

# Door widths: NOT found in TNCDBR 2019's general residential provisions.
# The only door widths in the source text (900mm clear opening) are under
# Rule 43, differently-abled accessibility -- not a general dwelling-door
# requirement. These remain uncited placeholders; core/validator.py does
# NOT hard-reject on door width until a citation is found. See
# docs/regulatory_sources.md "Gaps".
DOOR_WIDTH_MAIN_M = 1.00  # uncited placeholder
DOOR_WIDTH_INTERNAL_M = 0.90  # uncited placeholder
DOOR_WIDTH_BATH_M = 0.75  # uncited placeholder
DOOR_HEIGHT_M = 2.10  # not drawn in plan view, kept for DXF text/metadata

WINDOW_WIDTH_HABITABLE_M = 1.20  # uncited placeholder
WINDOW_WIDTH_KITCHEN_M = 0.90  # uncited placeholder
WINDOW_SILL_HEIGHT_M = 0.90  # not drawn in plan view, kept for metadata

# TNCDBR 2019, Rule 42(i): minimum width of corridor/verandah within
# residential buildings is 1.0m.
CORRIDOR_MIN_WIDTH_M = 1.00
MIN_OPENING_EDGE_CLEARANCE_M = 0.30  # keep door/window off the exact corner

# TNCDBR 2019, Rule 52(16)(a): minimum aggregate opening area (windows/
# ventilators, excluding doors) shall not be less than one-eighth of the
# floor area, increased by 25% for kitchens. Not yet enforced anywhere
# (Phase 1 keeps the existing has-exterior-wall boolean check) -- recorded
# here for Phase 2 (core/metrics.py), which computes it as a real ratio.
VENTILATION_OPENING_RATIO = 1.0 / 8.0
VENTILATION_OPENING_RATIO_KITCHEN_MULTIPLIER = 1.25
VENTILATION_CITATION = "TNCDBR 2019, Rule 52(16)(a)"


def door_width_for(room_type: RoomType) -> float:
    if room_type in (RoomType.BATHROOM, RoomType.TOILET):
        return DOOR_WIDTH_BATH_M
    return DOOR_WIDTH_INTERNAL_M


def window_width_for(room_type: RoomType) -> float:
    if room_type == RoomType.KITCHEN:
        return WINDOW_WIDTH_KITCHEN_M
    return WINDOW_WIDTH_HABITABLE_M


# ---------------------------------------------------------------------------
# Setbacks
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Setbacks:
    front_m: float
    rear_m: float
    side_m: float


# --- TNCDBR 2019, Rule 35(1)(a): Non High Rise buildings, <=16 dwellings,
# height <=18.30m, "Other areas" column (the applicable column for an
# individual residential building -- CBA/EWS are area classifications a
# single house doesn't fall under). A single house is never a ">16
# dwelling unit" development, so Rule 35(1)(b) (which uses the same side/
# rear-by-height shape for its 12-18.30m tiers) is folded in below rather
# than implemented as a separate path.
#
# Side and rear setback are simplified to apply symmetrically on both
# sides/rear even where the cited table would allow a single-side-only
# setback for some height/plot-width combinations -- i.e. this is never
# less space than TNCDBR requires, only possibly more conservative than
# strictly necessary.


def _tncdbr_front_setback_m(road_width_m: float) -> float:
    """Rule 35(1)(a)(E)(i), "Other areas": front setback by abutting road width."""
    if road_width_m <= 9.0:
        return 1.5
    if road_width_m <= 18.0:
        return 3.0
    if road_width_m <= 30.5:
        return 4.5
    return 6.0


def _tncdbr_side_setback_m(height_m: float, plot_width_m: float) -> float:
    """Rule 35(1)(a)(E)(ii) for height <=12m; Rule 35(1)(b)(D)(ii) for 12-18.30m."""
    if height_m <= 7.0:
        return 1.0
    if height_m <= 12.0:
        return 1.0 if plot_width_m <= 6.0 else 1.5
    if height_m <= 16.0:
        return 2.5
    return 3.0  # up to 18.30m; TNCDBR High Rise rules (>18.30m) not implemented


def _tncdbr_rear_setback_m(height_m: float) -> float:
    """Rule 35(1)(a)(E)(iii) for height <=12m; Rule 35(1)(b)(D)(ii) for 12-18.30m."""
    if height_m <= 7.0:
        return 0.0
    if height_m <= 12.0:
        return 1.5
    if height_m <= 16.0:
        return 2.5
    return 3.0  # up to 18.30m; TNCDBR High Rise rules (>18.30m) not implemented


# GENERIC fallback: the original uncited plot-area-tiered heuristic. Kept
# only for the GENERIC ruleset -- do not treat this as code-compliant.
_GENERIC_SETBACK_TIERS: list[tuple[float, Setbacks]] = [
    (150.0, Setbacks(front_m=1.5, rear_m=1.0, side_m=0.9)),
    (300.0, Setbacks(front_m=3.0, rear_m=2.0, side_m=1.5)),
    (500.0, Setbacks(front_m=4.5, rear_m=3.0, side_m=2.0)),
    (float("inf"), Setbacks(front_m=6.0, rear_m=4.0, side_m=3.0)),
]


def setbacks_for(
    plot_width_m: float,
    plot_area_sqm: float,
    *,
    ruleset: Ruleset = DEFAULT_RULESET,
    road_width_m: float | None = None,
    height_m: float | None = None,
    num_floors: int = 1,
) -> Setbacks:
    """Setbacks for a plot under ``ruleset``.

    ``road_width_m`` and ``height_m`` are TNCDBR_2019 inputs (Rule 35); if
    omitted, ``ASSUMED_ROAD_WIDTH_M`` and ``num_floors * ASSUMED_FLOOR_HEIGHT_M``
    are used as documented, non-cited assumptions. GENERIC ignores both and
    uses the plot-area-tiered heuristic instead.
    """
    if ruleset == Ruleset.TNCDBR_2019:
        road = road_width_m if road_width_m is not None else ASSUMED_ROAD_WIDTH_M
        height = height_m if height_m is not None else num_floors * ASSUMED_FLOOR_HEIGHT_M
        return Setbacks(
            front_m=_tncdbr_front_setback_m(road),
            rear_m=_tncdbr_rear_setback_m(height),
            side_m=_tncdbr_side_setback_m(height, plot_width_m),
        )

    for ceiling, setbacks in _GENERIC_SETBACK_TIERS:
        if plot_area_sqm <= ceiling:
            return setbacks
    return _GENERIC_SETBACK_TIERS[-1][1]  # pragma: no cover - unreachable, inf ceiling above


# ---------------------------------------------------------------------------
# Adjacency preferences and hard avoidances
# ---------------------------------------------------------------------------

# Soft preferences: rooms that should share a wall when possible. Symmetric.
#
# Note: there is deliberately no generic (BEDROOM, BATHROOM) style pair here.
# That relationship is handled per-instance by ``RoomRequirement.attached_bathroom``
# in core/graph.py, which creates one dedicated *required* edge per en-suite.
# A generic type-level preference would instead make *every* bedroom prefer
# *every* bathroom in the request — an edge count that grows with
# bedrooms x bathrooms and that no single-wall-per-room geometry could ever
# satisfy, which would push every candidate's adjacency score toward zero
# regardless of actual layout quality. Bedrooms reach a shared/family
# bathroom via the corridor pairs below instead.
ADJACENCY_PREFERRED: list[tuple[RoomType, RoomType]] = [
    (RoomType.KITCHEN, RoomType.DINING_ROOM),
    (RoomType.DINING_ROOM, RoomType.LIVING_ROOM),
    (RoomType.LIVING_ROOM, RoomType.FOYER),
    (RoomType.FOYER, RoomType.CORRIDOR),
    (RoomType.CORRIDOR, RoomType.BEDROOM),
    (RoomType.CORRIDOR, RoomType.MASTER_BEDROOM),
    (RoomType.CORRIDOR, RoomType.BATHROOM),
    (RoomType.KITCHEN, RoomType.UTILITY),
    (RoomType.GARAGE, RoomType.FOYER),
    (RoomType.STAIRCASE, RoomType.CORRIDOR),
    (RoomType.STAIRCASE, RoomType.FOYER),
]

# Hard avoidances: rooms that should *not* share a wall/door. Symmetric.
# The BATHROOM/TOILET <-> KITCHEN pairs are cited: TNCDBR 2019, Rule
# 52(7)(c)(vi) -- "the door of the water closet or bath not to be directly
# opened to a kitchen." core/validator.py treats this pair as a hard
# rejection, not just a scoring penalty, on the strength of that citation.
# The DINING_ROOM pairs are not separately cited and remain soft-only.
ADJACENCY_AVOID: list[tuple[RoomType, RoomType]] = [
    (RoomType.BATHROOM, RoomType.KITCHEN),
    (RoomType.TOILET, RoomType.KITCHEN),
    (RoomType.BATHROOM, RoomType.DINING_ROOM),
    (RoomType.TOILET, RoomType.DINING_ROOM),
]

# The subset of ADJACENCY_AVOID that's cited and therefore hard (see above).
ADJACENCY_AVOID_HARD: list[tuple[RoomType, RoomType]] = [
    (RoomType.BATHROOM, RoomType.KITCHEN),
    (RoomType.TOILET, RoomType.KITCHEN),
]
ADJACENCY_AVOID_HARD_CITATION = "TNCDBR 2019, Rule 52(7)(c)(vi)"

# Rooms a main entrance is allowed to open directly into.
ENTRANCE_COMPATIBLE_ROOMS = frozenset(
    {RoomType.FOYER, RoomType.LIVING_ROOM, RoomType.CORRIDOR, RoomType.GARAGE}
)


def _pair_in(pairs: list[tuple[RoomType, RoomType]], a: RoomType, b: RoomType) -> bool:
    return (a, b) in pairs or (b, a) in pairs


def is_preferred_adjacency(a: RoomType, b: RoomType) -> bool:
    return _pair_in(ADJACENCY_PREFERRED, a, b)


def is_avoided_adjacency(a: RoomType, b: RoomType) -> bool:
    return _pair_in(ADJACENCY_AVOID, a, b)


def is_hard_avoided_adjacency(a: RoomType, b: RoomType) -> bool:
    return _pair_in(ADJACENCY_AVOID_HARD, a, b)


# ---------------------------------------------------------------------------
# Request-level validation
# ---------------------------------------------------------------------------


def validate_request(
    plot_width_m: float,
    plot_length_m: float,
    room_specs: list[tuple[RoomType, int, float | None]],
    *,
    ruleset: Ruleset = DEFAULT_RULESET,
    road_width_m: float | None = None,
    height_m: float | None = None,
    num_floors: int = 1,
) -> list[str]:
    """Sanity-check a request before spending time generating layouts.

    ``room_specs`` is a list of (room_type, count, target_area_sqm_or_None).
    Returns a list of human-readable warning/error strings; an empty list
    means the request looks feasible. This is a fast pre-flight heuristic,
    not the authoritative hard-constraint check -- that's
    ``core/validator.py``, which runs against actual generated geometry.
    """
    issues: list[str] = []
    plot_area = plot_width_m * plot_length_m
    setbacks = setbacks_for(
        plot_width_m,
        plot_area,
        ruleset=ruleset,
        road_width_m=road_width_m,
        height_m=height_m,
        num_floors=num_floors,
    )
    buildable_w = plot_width_m - 2 * setbacks.side_m
    buildable_l = plot_length_m - setbacks.front_m - setbacks.rear_m

    if buildable_w <= 1.0 or buildable_l <= 1.0:
        issues.append(
            f"Plot {plot_width_m}m x {plot_length_m}m is too small once setbacks "
            f"(side {setbacks.side_m}m, front {setbacks.front_m}m, rear {setbacks.rear_m}m) "
            "are applied — there is little to no buildable area left."
        )
        return issues

    buildable_area = buildable_w * buildable_l

    has_dining_room = any(room_type == RoomType.DINING_ROOM for room_type, _, _ in room_specs)

    required_area = 0.0
    for room_type, count, target_area in room_specs:
        rule = rule_for(room_type, ruleset)
        min_area = rule.min_area_sqm
        if room_type == RoomType.KITCHEN:
            min_area, _min_width = kitchen_minimum(has_dining_room)
        per_room = target_area if target_area is not None else rule.default_area_sqm
        if per_room < min_area:
            issues.append(
                f"{room_type.value}: requested {per_room:.1f} sqm is below the "
                f"legal minimum of {min_area:.1f} sqm ({rule.citation})."
            )
        required_area += per_room * count

    # Circulation allowance: real plans lose ~12-18% of buildable area to
    # walls and corridors that aren't "rooms" themselves.
    required_with_circulation = required_area * 1.15
    if required_with_circulation > buildable_area:
        issues.append(
            f"Requested rooms need roughly {required_with_circulation:.1f} sqm "
            f"(including circulation) but the buildable area is only "
            f"{buildable_area:.1f} sqm. Reduce room count/areas or use a larger plot."
        )

    return issues
