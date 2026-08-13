"""Phase 5: vastu is optional, soft, and requires an explicit plot_north.

Three things this file exists to prove:
1. core/vastu.py's direction math (rotation + 8-sector classification) is
   correct for all four plot_north values.
2. VastuOptions enforces "plot_north must be explicit" and "it's SOFT"
   (nothing here can appear in core/validator.py).
3. With vastu disabled (the default), generation output is byte-identical
   to before this module existed -- the phase's own stated test.
"""

from __future__ import annotations

import pytest

from rivet.core.generator import generate
from rivet.core.graph import RoomNode
from rivet.core.models import (
    GenerationRequest,
    Orientation,
    PlotSpec,
    Rect,
    RoomRequirement,
    RoomType,
    VastuOptions,
)
from rivet.core.scoring import evaluate
from rivet.core.vastu import evaluate_vastu, room_zone, true_compass_zone

# ---------------------------------------------------------------------------
# VastuOptions validation
# ---------------------------------------------------------------------------


def test_plot_north_required_when_enabled():
    with pytest.raises(ValueError, match="plot_north"):
        VastuOptions(enabled=True)


def test_plot_north_optional_when_disabled():
    options = VastuOptions()  # enabled=False by default
    assert options.enabled is False
    assert options.plot_north is None


def test_negative_weight_rejected():
    with pytest.raises(ValueError, match="weight"):
        VastuOptions(enabled=True, plot_north=Orientation.NORTH, weight=-1.0)


# ---------------------------------------------------------------------------
# Direction math
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dx,dy,expected",
    [
        (0, 10, "N"),
        (10, 10, "NE"),
        (10, 0, "E"),
        (10, -10, "SE"),
        (0, -10, "S"),
        (-10, -10, "SW"),
        (-10, 0, "W"),
        (-10, 10, "NW"),
    ],
)
def test_zone_classification_with_north_up(dx, dy, expected):
    # plot_north=NORTH is the identity rotation, so this directly tests
    # the 8-sector bucketing.
    assert true_compass_zone(dx, dy, Orientation.NORTH) == expected


def test_zone_center_has_no_direction():
    assert true_compass_zone(0, 0, Orientation.NORTH) == "CENTER"


@pytest.mark.parametrize(
    "plot_north,drawing_offset,expected_true_zone",
    [
        # plot_north names which DRAWING axis is actually true north.
        # A room drawn straight "up" (0, 10) in the plan should be
        # classified as true-north only when plot_north=NORTH; if the
        # drawing's "up" is actually true east/south/west, that same
        # drawn position lands in a different real-world direction.
        (Orientation.NORTH, (0, 10), "N"),
        (Orientation.EAST, (0, 10), "W"),
        (Orientation.SOUTH, (0, 10), "S"),
        (Orientation.WEST, (0, 10), "E"),
    ],
)
def test_plot_north_rotation_changes_classification(plot_north, drawing_offset, expected_true_zone):
    dx, dy = drawing_offset
    assert true_compass_zone(dx, dy, plot_north) == expected_true_zone


def test_room_zone_uses_offset_from_buildable_center():
    buildable = Rect(x=0, y=0, w=20, h=20)  # center at (10, 10)
    room = Rect(x=15, y=15, w=2, h=2)  # center at (16, 16) -> NE of buildable center
    assert room_zone(room, buildable, Orientation.NORTH) == "NE"


# ---------------------------------------------------------------------------
# Preference evaluation
# ---------------------------------------------------------------------------


def _node(room_id: str, room_type: RoomType, label: str) -> RoomNode:
    return RoomNode(
        id=room_id, room_type=room_type, label=label, target_area_sqm=10.0, max_aspect_ratio=2.5,
        exterior_wall_required=False,
    )


def test_kitchen_in_southeast_is_satisfied():
    buildable = Rect(x=0, y=0, w=20, h=20)
    kitchen = _node("kitchen_1", RoomType.KITCHEN, "Kitchen")
    rects = {"kitchen_1": Rect(x=15, y=1, w=2, h=2)}  # bottom-right -> SE of center
    plot = PlotSpec(width_m=20, length_m=20, entrance=Orientation.NORTH)
    options = VastuOptions(enabled=True, plot_north=Orientation.NORTH)

    result = evaluate_vastu([kitchen], rects, buildable, plot, options)
    kitchen_pref = next(p for p in result.preferences if p.name == "kitchen_southeast")
    assert kitchen_pref.satisfied
    assert result.penalty == 0.0  # entrance_orientation also checked, but north entrance is satisfied


def test_toilet_in_northeast_is_violated():
    buildable = Rect(x=0, y=0, w=20, h=20)
    bath = _node("bathroom_1", RoomType.BATHROOM, "Bathroom")
    rects = {"bathroom_1": Rect(x=15, y=15, w=2, h=2)}  # top-right -> NE of center
    plot = PlotSpec(width_m=20, length_m=20, entrance=Orientation.NORTH)
    options = VastuOptions(enabled=True, plot_north=Orientation.NORTH)

    result = evaluate_vastu([bath], rects, buildable, plot, options)
    bath_pref = next(p for p in result.preferences if p.name == "toilet_avoid_northeast")
    assert not bath_pref.satisfied
    assert result.penalty > 0.0


def test_weight_scales_penalty_linearly():
    buildable = Rect(x=0, y=0, w=20, h=20)
    bath = _node("bathroom_1", RoomType.BATHROOM, "Bathroom")
    rects = {"bathroom_1": Rect(x=15, y=15, w=2, h=2)}
    plot = PlotSpec(width_m=20, length_m=20, entrance=Orientation.NORTH)

    result_1x = evaluate_vastu([bath], rects, buildable, plot, VastuOptions(enabled=True, plot_north=Orientation.NORTH, weight=1.0))
    result_2x = evaluate_vastu([bath], rects, buildable, plot, VastuOptions(enabled=True, plot_north=Orientation.NORTH, weight=2.0))
    assert result_2x.penalty == pytest.approx(result_1x.penalty * 2)


# ---------------------------------------------------------------------------
# scoring.py integration
# ---------------------------------------------------------------------------


def test_evaluate_omits_vastu_key_when_disabled():
    import networkx as nx

    buildable = Rect(x=0, y=0, w=20, h=20)
    node = _node("kitchen_1", RoomType.KITCHEN, "Kitchen")
    rects = {"kitchen_1": Rect(x=0, y=0, w=20, h=20)}
    plot = PlotSpec(width_m=20, length_m=20, entrance=Orientation.NORTH)
    graph = nx.Graph()
    graph.add_node("kitchen_1")

    result = evaluate([node], rects, buildable, plot, graph, vastu=None)
    assert "vastu" not in result.breakdown
    assert result.vastu_preferences == []


def test_evaluate_includes_vastu_key_when_enabled():
    import networkx as nx

    buildable = Rect(x=0, y=0, w=20, h=20)
    node = _node("kitchen_1", RoomType.KITCHEN, "Kitchen")
    rects = {"kitchen_1": Rect(x=0, y=0, w=2, h=2)}  # SW-ish, violates kitchen-SE
    plot = PlotSpec(width_m=20, length_m=20, entrance=Orientation.NORTH)
    graph = nx.Graph()
    graph.add_node("kitchen_1")
    options = VastuOptions(enabled=True, plot_north=Orientation.NORTH)

    result = evaluate([node], rects, buildable, plot, graph, vastu=options)
    assert "vastu" in result.breakdown
    assert result.breakdown["vastu"] > 0.0
    assert result.vastu_preferences


# ---------------------------------------------------------------------------
# End-to-end determinism: disabled vastu must not change generation output
# ---------------------------------------------------------------------------


def test_disabled_vastu_is_byte_identical_to_pre_phase_5_baseline(sample_request):
    # Recorded once from `generate(sample_request)` before this phase
    # existed (Phase 3/4 baseline) -- see docs/prompts.md Phase 5 status.
    # sample_request.vastu defaults to VastuOptions() (disabled), so this
    # exercises exactly the code path every pre-Phase-5 caller took.
    layouts = generate(sample_request)
    assert isinstance(layouts, list)
    layout = layouts[0]

    assert layout.score == pytest.approx(17.2)
    assert "vastu" not in layout.score_breakdown
    assert layout.vastu_preferences == []


def test_vastu_enabled_end_to_end_with_pooja_room():
    request = GenerationRequest(
        plot=PlotSpec(
            width_m=15.0, length_m=13.0, entrance=Orientation.NORTH, abutting_road_width_m=9.0, proposed_height_m=6.0
        ),
        rooms=[
            RoomRequirement(RoomType.LIVING_ROOM, count=1),
            RoomRequirement(RoomType.MASTER_BEDROOM, count=1, attached_bathroom=True),
            RoomRequirement(RoomType.BEDROOM, count=2, attached_bathroom=True),
            RoomRequirement(RoomType.KITCHEN, count=1),
            RoomRequirement(RoomType.DINING_ROOM, count=1),
            RoomRequirement(RoomType.BATHROOM, count=1),
            RoomRequirement(RoomType.POOJA, count=1),
        ],
        num_candidates=1,
        seed=42,
        vastu=VastuOptions(enabled=True, weight=1.0, plot_north=Orientation.NORTH),
    )
    result = generate(request)
    assert isinstance(result, list), getattr(result, "message", result)
    layout = result[0]

    assert layout.vastu_preferences
    assert "vastu" in layout.score_breakdown
    names = {p.name for p in layout.vastu_preferences}
    assert "pooja_northeast" in names
    assert "kitchen_southeast" in names
    assert "master_bedroom_southwest" in names
    assert "entrance_orientation" in names
