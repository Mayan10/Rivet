import pytest

from rivet.core.models import RoomType, Ruleset
from rivet.core.rules import (
    ROOM_RULES,
    door_width_for,
    is_avoided_adjacency,
    is_hard_avoided_adjacency,
    is_preferred_adjacency,
    kitchen_minimum,
    room_rules_for,
    setbacks_for,
    validate_request,
    window_width_for,
)


def test_every_room_type_has_a_rule():
    for room_type in RoomType:
        assert room_type in ROOM_RULES


@pytest.mark.parametrize("ruleset", list(Ruleset))
@pytest.mark.parametrize("room_type", list(RoomType))
def test_room_rule_sanity(ruleset, room_type):
    rule = room_rules_for(ruleset)[room_type]
    assert rule.min_area_sqm > 0
    assert rule.default_area_sqm >= rule.min_area_sqm, f"{room_type}: default area below its own minimum"
    assert rule.min_width_m > 0
    assert rule.citation, f"{room_type} ({ruleset}): every RoomRule must state a citation, even if it's an explicit 'uncited placeholder'"
    # A rectangle at the minimum area and minimum width shouldn't be
    # thinner than a hallway -- min_width^2 should not exceed min_area
    # (i.e. the minimum width is achievable within the minimum area).
    assert rule.min_width_m * rule.min_width_m <= rule.min_area_sqm * 1.01


def test_tncdbr_room_minimums_are_cited_not_placeholder():
    # The room types Phase 1 explicitly promotes to hard constraints
    # (docs/prompts.md Phase 1 point 2) must carry a real TNCDBR citation,
    # not fall back to "uncited placeholder" under the default ruleset.
    cited_types = [
        RoomType.LIVING_ROOM,
        RoomType.MASTER_BEDROOM,
        RoomType.BEDROOM,
        RoomType.STUDY,
        RoomType.KITCHEN,
        RoomType.DINING_ROOM,
        RoomType.BATHROOM,
        RoomType.TOILET,
    ]
    for room_type in cited_types:
        rule = room_rules_for(Ruleset.TNCDBR_2019)[room_type]
        assert rule.citation.startswith("TNCDBR 2019"), f"{room_type} should be cited, got: {rule.citation!r}"


def test_kitchen_minimum_depends_on_dining_room_presence():
    # TNCDBR 2019, Rule 52(6)(b): a kitchen with a separate dining area has
    # a smaller legal minimum than one that also serves as the dining space.
    with_dining_area, with_dining_width = kitchen_minimum(has_separate_dining_room=True)
    as_dining_area, as_dining_width = kitchen_minimum(has_separate_dining_room=False)
    assert with_dining_area < as_dining_area
    assert with_dining_width < as_dining_width


def test_setbacks_tncdbr_front_increases_with_road_width():
    narrow = setbacks_for(12.0, 132.0, ruleset=Ruleset.TNCDBR_2019, road_width_m=6.0, height_m=6.0)
    wide = setbacks_for(12.0, 132.0, ruleset=Ruleset.TNCDBR_2019, road_width_m=20.0, height_m=6.0)
    assert narrow.front_m < wide.front_m


def test_setbacks_tncdbr_side_and_rear_increase_with_height():
    low = setbacks_for(12.0, 132.0, ruleset=Ruleset.TNCDBR_2019, road_width_m=9.0, height_m=5.0)
    high = setbacks_for(12.0, 132.0, ruleset=Ruleset.TNCDBR_2019, road_width_m=9.0, height_m=15.0)
    assert low.side_m <= high.side_m
    assert low.rear_m <= high.rear_m


def test_setbacks_generic_increases_with_plot_size():
    small = setbacks_for(10.0, 100.0, ruleset=Ruleset.GENERIC)
    medium = setbacks_for(15.0, 250.0, ruleset=Ruleset.GENERIC)
    large = setbacks_for(30.0, 1000.0, ruleset=Ruleset.GENERIC)
    assert small.front_m <= medium.front_m <= large.front_m
    assert small.side_m <= medium.side_m <= large.side_m


def test_adjacency_preference_is_symmetric():
    assert is_preferred_adjacency(RoomType.KITCHEN, RoomType.DINING_ROOM)
    assert is_preferred_adjacency(RoomType.DINING_ROOM, RoomType.KITCHEN)


def test_adjacency_avoidance_is_symmetric():
    assert is_avoided_adjacency(RoomType.BATHROOM, RoomType.KITCHEN)
    assert is_avoided_adjacency(RoomType.KITCHEN, RoomType.BATHROOM)


def test_hard_avoided_adjacency_is_a_subset_of_avoided_adjacency():
    # Only the cited pair (TNCDBR 2019, Rule 52(7)(c)(vi)) is hard; the
    # uncited DINING_ROOM pairs stay soft-only.
    assert is_hard_avoided_adjacency(RoomType.BATHROOM, RoomType.KITCHEN)
    assert is_hard_avoided_adjacency(RoomType.TOILET, RoomType.KITCHEN)
    assert not is_hard_avoided_adjacency(RoomType.BATHROOM, RoomType.DINING_ROOM)
    assert is_avoided_adjacency(RoomType.BATHROOM, RoomType.DINING_ROOM)


def test_no_generic_bedroom_bathroom_preference():
    # Regression guard: a generic (BEDROOM, BATHROOM) preference combined
    # with per-instance en-suite pairing creates an edge count no
    # single-wall-per-room geometry could satisfy (every bedroom "wants"
    # every bathroom). See core/rules.py and core/graph.py for the fix.
    assert not is_preferred_adjacency(RoomType.BEDROOM, RoomType.BATHROOM)
    assert not is_preferred_adjacency(RoomType.MASTER_BEDROOM, RoomType.BATHROOM)


def test_door_and_window_width_specializations():
    assert door_width_for(RoomType.BATHROOM) < door_width_for(RoomType.BEDROOM)
    assert window_width_for(RoomType.KITCHEN) < window_width_for(RoomType.LIVING_ROOM)


def test_validate_request_flags_undersized_plot():
    issues = validate_request(
        4.0,
        4.0,
        [(RoomType.LIVING_ROOM, 1, None), (RoomType.BEDROOM, 2, None), (RoomType.KITCHEN, 1, None)],
    )
    assert issues


def test_validate_request_accepts_reasonable_plot():
    issues = validate_request(
        12.0,
        11.0,
        [
            (RoomType.LIVING_ROOM, 1, None),
            (RoomType.MASTER_BEDROOM, 1, None),
            (RoomType.BEDROOM, 2, None),
            (RoomType.KITCHEN, 1, None),
            (RoomType.DINING_ROOM, 1, None),
            (RoomType.BATHROOM, 1, None),
        ],
    )
    assert issues == []
