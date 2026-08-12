from rivet.core.models import Layout, Opening, PlotSpec, Rect, RoomInstance, RoomType, Ruleset
from rivet.core.validator import validate_layout


def _plot(width=12.0, length=11.0):
    return PlotSpec(width_m=width, length_m=length)


def _buildable(plot: PlotSpec, ruleset=Ruleset.TNCDBR_2019):
    from rivet.core.rules import setbacks_for

    s = setbacks_for(plot.width_m, plot.area_sqm, ruleset=ruleset)
    return Rect(x=s.side_m, y=s.rear_m, w=plot.width_m - 2 * s.side_m, h=plot.length_m - s.front_m - s.rear_m)


def _layout(rooms: list[RoomInstance], plot: PlotSpec | None = None) -> Layout:
    plot = plot or _plot()
    return Layout(candidate_id="c", plot=plot, buildable=_buildable(plot), rooms=rooms, openings=[])


def test_valid_layout_has_no_violations():
    plot = _plot()
    buildable = _buildable(plot)
    rooms = [
        RoomInstance(
            id="living_room_1",
            room_type=RoomType.LIVING_ROOM,
            label="Living Room",
            rect=Rect(buildable.x, buildable.y, buildable.w, buildable.h),
        )
    ]
    layout = _layout(rooms, plot)
    # A hand-built fixture has no doors by construction (the real generator
    # always places one) -- give it a main door so this test exercises the
    # dimension/adjacency/setback checks it's meant to, not reachability.
    layout.openings = [
        Opening(kind="main_door", x=buildable.x, y=buildable.y, width=1.0, axis="horizontal", room_id="living_room_1")
    ]
    result = validate_layout(layout, Ruleset.TNCDBR_2019)
    assert result.is_valid
    assert result.violations == []


def test_room_below_legal_min_area_is_rejected():
    plot = _plot()
    rooms = [
        RoomInstance(
            id="bedroom_1",
            room_type=RoomType.BEDROOM,
            label="Bedroom",
            rect=Rect(0, 0, 2.5, 2.5),  # 6.25 sqm, below TNCDBR's 7.5 sqm habitable minimum
        )
    ]
    result = validate_layout(_layout(rooms, plot), Ruleset.TNCDBR_2019)
    assert not result.is_valid
    ids = {v.constraint_id for v in result.violations}
    assert "min_area" in ids
    assert any(v.source.startswith("TNCDBR 2019") for v in result.violations)


def test_room_below_legal_min_width_is_rejected():
    plot = _plot()
    rooms = [
        RoomInstance(
            id="bedroom_1",
            room_type=RoomType.BEDROOM,
            label="Bedroom",
            rect=Rect(0, 0, 1.0, 10.0),  # 10 sqm (plenty), but only 1.0m wide < 2.4m minimum
        )
    ]
    result = validate_layout(_layout(rooms, plot), Ruleset.TNCDBR_2019)
    assert not result.is_valid
    assert any(v.constraint_id == "min_width" for v in result.violations)


def test_kitchen_minimum_is_context_dependent_on_dining_room():
    plot = _plot()
    # 6 sqm, 2.0m wide: below the 7.5/2.1 "doubles as dining" minimum, but
    # above the 5.0/1.8 "separate dining room provided" minimum.
    kitchen = RoomInstance(id="kitchen_1", room_type=RoomType.KITCHEN, label="Kitchen", rect=Rect(0, 0, 2.0, 3.0))

    without_dining = validate_layout(_layout([kitchen], plot), Ruleset.TNCDBR_2019)
    assert not without_dining.is_valid
    assert any(v.room_id == "kitchen_1" for v in without_dining.violations)

    dining = RoomInstance(
        id="dining_1", room_type=RoomType.DINING_ROOM, label="Dining Room", rect=Rect(2.0, 0, 3.0, 3.0)
    )
    with_dining = validate_layout(_layout([kitchen, dining], plot), Ruleset.TNCDBR_2019)
    kitchen_violations = [v for v in with_dining.violations if v.room_id == "kitchen_1"]
    assert kitchen_violations == []


def test_hard_avoided_adjacency_is_rejected():
    plot = _plot()
    kitchen = RoomInstance(id="kitchen_1", room_type=RoomType.KITCHEN, label="Kitchen", rect=Rect(0, 0, 3.0, 3.0))
    bathroom = RoomInstance(
        id="bathroom_1", room_type=RoomType.BATHROOM, label="Bathroom", rect=Rect(3.0, 0, 2.0, 2.0)
    )
    result = validate_layout(_layout([kitchen, bathroom], plot), Ruleset.TNCDBR_2019)
    assert not result.is_valid
    assert any(v.constraint_id == "adjacency_avoided_hard" for v in result.violations)
    assert any("Rule 52(7)(c)(vi)" in v.source for v in result.violations)


def test_soft_avoided_adjacency_is_not_rejected():
    # BATHROOM/DINING_ROOM is in ADJACENCY_AVOID but not the cited hard
    # subset -- the validator must not reject it (that's scoring.py's job).
    plot = _plot()
    dining = RoomInstance(id="dining_1", room_type=RoomType.DINING_ROOM, label="Dining", rect=Rect(0, 0, 3.0, 3.0))
    bathroom = RoomInstance(
        id="bathroom_1", room_type=RoomType.BATHROOM, label="Bathroom", rect=Rect(3.0, 0, 2.0, 2.0)
    )
    result = validate_layout(_layout([dining, bathroom], plot), Ruleset.TNCDBR_2019)
    assert not any(v.constraint_id == "adjacency_avoided_hard" for v in result.violations)


def test_exterior_access_required_for_habitable_room():
    plot = _plot()
    buildable = _buildable(plot)
    # Placed away from every buildable edge.
    interior_rect = Rect(buildable.x + 2, buildable.y + 2, 3.0, 3.0)
    room = RoomInstance(id="living_room_1", room_type=RoomType.LIVING_ROOM, label="Living Room", rect=interior_rect)
    result = validate_layout(_layout([room], plot), Ruleset.TNCDBR_2019)
    assert any(v.constraint_id == "exterior_access" for v in result.violations)


def test_generic_ruleset_uses_its_own_uncited_minimums():
    # GENERIC's bedroom minimum (9.5/2.4) differs from TNCDBR's (7.5/2.4) --
    # a room valid under one can be invalid under the other.
    plot = _plot()
    rooms = [RoomInstance(id="bedroom_1", room_type=RoomType.BEDROOM, label="Bedroom", rect=Rect(0, 0, 2.5, 3.0))]
    layout = _layout(rooms, plot)  # 7.5 sqm
    # See test_valid_layout_has_no_violations: a fully-valid assertion needs
    # a main door, since a hand-built fixture has none by default.
    layout.openings = [Opening(kind="main_door", x=0, y=0, width=1.0, axis="horizontal", room_id="bedroom_1")]

    tncdbr_result = validate_layout(layout, Ruleset.TNCDBR_2019)
    generic_result = validate_layout(layout, Ruleset.GENERIC)
    assert tncdbr_result.is_valid
    assert not generic_result.is_valid


def test_door_widths_are_not_hard_checked():
    # Explicit regression guard: door widths are uncited (see
    # docs/regulatory_sources.md "Gaps") and must never appear as a
    # validator constraint until a citation exists.
    plot = _plot()
    buildable = _buildable(plot)
    room = RoomInstance(
        id="living_room_1",
        room_type=RoomType.LIVING_ROOM,
        label="Living Room",
        rect=Rect(buildable.x, buildable.y, buildable.w, buildable.h),
    )
    layout = _layout([room], plot)
    layout.openings = [
        Opening(kind="main_door", x=buildable.x, y=buildable.y, width=0.1, axis="horizontal", room_id="living_room_1")
    ]
    result = validate_layout(layout, Ruleset.TNCDBR_2019)
    assert not any(v.constraint_id == "door_width" for v in result.violations)
