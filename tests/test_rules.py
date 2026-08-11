import pytest

from rivet.core.models import RoomType
from rivet.core.rules import (
    ROOM_RULES,
    door_width_for,
    is_avoided_adjacency,
    is_preferred_adjacency,
    setbacks_for,
    validate_request,
    window_width_for,
)


def test_every_room_type_has_a_rule():
    for room_type in RoomType:
        assert room_type in ROOM_RULES


@pytest.mark.parametrize("room_type,rule", list(ROOM_RULES.items()))
def test_room_rule_sanity(room_type, rule):
    assert rule.min_area_sqm > 0
    assert rule.default_area_sqm >= rule.min_area_sqm, f"{room_type}: default area below its own minimum"
    assert rule.min_width_m > 0
    # A rectangle at the minimum area and minimum width shouldn't be
    # thinner than a hallway -- min_width^2 should not exceed min_area
    # (i.e. the minimum width is achievable within the minimum area).
    assert rule.min_width_m * rule.min_width_m <= rule.min_area_sqm * 1.01


def test_setbacks_increase_with_plot_size():
    small = setbacks_for(100.0)
    medium = setbacks_for(250.0)
    large = setbacks_for(1000.0)
    assert small.front_m <= medium.front_m <= large.front_m
    assert small.side_m <= medium.side_m <= large.side_m


def test_adjacency_preference_is_symmetric():
    assert is_preferred_adjacency(RoomType.KITCHEN, RoomType.DINING_ROOM)
    assert is_preferred_adjacency(RoomType.DINING_ROOM, RoomType.KITCHEN)


def test_adjacency_avoidance_is_symmetric():
    assert is_avoided_adjacency(RoomType.BATHROOM, RoomType.KITCHEN)
    assert is_avoided_adjacency(RoomType.KITCHEN, RoomType.BATHROOM)


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
        15.0,
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
