import pytest

from conftest import assert_feasible
from rivet.core.generator import compute_buildable_rect, generate
from rivet.core.metrics import compute_metrics
from rivet.core.models import (
    GenerationRequest,
    Layout,
    Orientation,
    PlotSpec,
    Rect,
    RoomInstance,
    RoomRequirement,
    RoomType,
    Ruleset,
)
from rivet.core.rules import TNCDBR_MAX_FSI, WALL_THICKNESS_EXTERNAL_M, WALL_THICKNESS_INTERNAL_M
from rivet.core.walls import compute_wall_segments, total_wall_length_by_class


def _single_room_layout():
    """A fully hand-computable case: one room, no interior walls, filling
    the buildable rect exactly, so every metric can be checked with a
    calculator, not just re-derived by other code.
    """
    plot = PlotSpec(width_m=10.0, length_m=10.0, entrance=Orientation.NORTH, abutting_road_width_m=9.0, proposed_height_m=3.0)
    request = GenerationRequest(plot=plot, rooms=[RoomRequirement(RoomType.LIVING_ROOM)])
    buildable = compute_buildable_rect(request)
    room = RoomInstance(
        id="living_room_1",
        room_type=RoomType.LIVING_ROOM,
        label="Living Room",
        rect=Rect(buildable.x, buildable.y, buildable.w, buildable.h),
    )
    layout = Layout(candidate_id="c", plot=plot, buildable=buildable, rooms=[room], openings=[])
    return layout, request


def test_hand_checked_single_room_metrics():
    # Road width 9.0 -> front setback 1.5m (Rule 35, <=9m tier).
    # Height 3.0 -> side 1.0m, rear 0.0m (Rule 35, <=7m tier).
    # buildable = x=1.0, y=0.0, w=10-2*1.0=8.0, h=10-1.5-0=8.5
    layout, request = _single_room_layout()
    assert layout.buildable == Rect(x=1.0, y=0.0, w=8.0, h=8.5)

    metrics = compute_metrics(layout, request.ruleset)

    # Gross area: the room fills buildable exactly.
    assert metrics.gross_area_sqm == pytest.approx(8.0 * 8.5)

    # Carpet area: every edge of the only room touches the buildable
    # boundary (all 4 edges exterior), inset by half the external wall
    # thickness (0.23/2 = 0.115) on each side.
    d = WALL_THICKNESS_EXTERNAL_M / 2
    expected_carpet = (8.0 - 2 * d) * (8.5 - 2 * d)
    assert metrics.total_carpet_area_sqm == pytest.approx(expected_carpet)
    assert metrics.rooms[0].carpet_area_sqm == pytest.approx(expected_carpet)

    # Built-up area: buildable expanded outward by half the external wall
    # thickness on every side (full thickness added to each dimension).
    expected_built_up = (8.0 + WALL_THICKNESS_EXTERNAL_M) * (8.5 + WALL_THICKNESS_EXTERNAL_M)
    assert metrics.total_built_up_area_sqm == pytest.approx(expected_built_up)
    assert metrics.total_plinth_area_sqm == pytest.approx(expected_built_up)  # no verandah modeled yet

    # No interior walls at all in a single-room layout.
    assert metrics.quantity_takeoff.interior_wall_length_m == pytest.approx(0.0)
    # Exterior wall length is exactly the buildable rect's perimeter.
    assert metrics.quantity_takeoff.exterior_wall_length_m == pytest.approx(2 * (8.0 + 8.5))

    # Exact area conservation for this corner-simple case (see
    # test_area_conservation_within_tolerance below for why multi-room
    # layouts only conserve approximately).
    ext_footprint = metrics.quantity_takeoff.exterior_wall_length_m * WALL_THICKNESS_EXTERNAL_M
    assert metrics.total_carpet_area_sqm + ext_footprint == pytest.approx(metrics.total_built_up_area_sqm, rel=1e-9)

    # Ground coverage and FSI.
    assert metrics.ground_coverage_pct == pytest.approx(expected_built_up / 100.0 * 100)  # plot is 10x10=100sqm
    assert metrics.fsi_consumed == pytest.approx(expected_built_up / 100.0)
    assert metrics.fsi_permitted == TNCDBR_MAX_FSI
    assert metrics.fsi_permitted_citation is not None and "Rule 35" in metrics.fsi_permitted_citation

    # Setbacks: provided always matches required, since buildable is
    # derived from setbacks_for() by construction.
    by_face = {s.face: s for s in metrics.setbacks}
    assert by_face["front"].required_m == pytest.approx(1.5)
    assert by_face["front"].provided_m == pytest.approx(1.5)
    assert by_face["rear"].required_m == pytest.approx(0.0)
    assert by_face["left"].required_m == pytest.approx(1.0)
    assert by_face["right"].required_m == pytest.approx(1.0)
    assert all(s.compliant for s in metrics.setbacks)


def test_generic_ruleset_has_no_fsi_cap():
    layout, _request = _single_room_layout()
    metrics = compute_metrics(layout, Ruleset.GENERIC)
    assert metrics.fsi_permitted is None
    assert metrics.fsi_permitted_citation is None


def test_area_conservation_within_tolerance(sample_request):
    # carpet_area + (deduplicated) wall footprints should reconstruct
    # built-up area, but only approximately for a real multi-room layout:
    # each interior T-junction/corner double-counts a thickness-squared
    # sliver differently in the per-room carpet inset than in the
    # length x thickness wall footprint approximation. This was measured
    # empirically at ~0.2% of built-up area for a 10-room layout; 1% is a
    # deliberately generous bound, not a tuned-to-pass number.
    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)

    ext_len, int_len = total_wall_length_by_class(compute_wall_segments(layout))
    wall_footprint = ext_len * WALL_THICKNESS_EXTERNAL_M + int_len * WALL_THICKNESS_INTERNAL_M
    reconstructed = metrics.total_carpet_area_sqm + wall_footprint

    assert reconstructed == pytest.approx(metrics.total_built_up_area_sqm, rel=0.01)


def test_room_gross_areas_sum_matches_buildable(sample_request):
    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)
    assert metrics.gross_area_sqm == pytest.approx(layout.buildable.area, rel=1e-6)


def test_carpet_area_never_exceeds_gross_area(sample_request):
    layouts = assert_feasible(generate(sample_request))
    for layout in layouts:
        metrics = compute_metrics(layout, sample_request.ruleset)
        for room in metrics.rooms:
            assert room.carpet_area_sqm <= room.gross_area_sqm + 1e-9


def test_built_up_area_exceeds_gross_area(sample_request):
    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)
    assert metrics.total_built_up_area_sqm > metrics.gross_area_sqm


def test_door_schedule_counts_match_openings(sample_request):
    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)

    door_opening_count = sum(1 for o in layout.openings if o.kind in ("door", "main_door"))
    window_opening_count = sum(1 for o in layout.openings if o.kind == "window")

    assert sum(row.count for row in metrics.door_schedule) == door_opening_count
    assert sum(row.count for row in metrics.window_schedule) == window_opening_count


def test_ventilation_metrics_only_populated_for_habitable_rooms(sample_request):
    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)

    for room in metrics.rooms:
        if room.is_habitable:
            assert room.window_opening_area_sqm is not None
            assert room.required_ventilation_area_sqm is not None
            assert room.ventilation_passes is not None
        else:
            assert room.window_opening_area_sqm is None
            assert room.required_ventilation_area_sqm is None
            assert room.ventilation_ratio_actual is None
            assert room.ventilation_passes is None


def test_ventilation_does_not_affect_validator_hard_check(sample_request):
    # Regression guard for the Phase 2 design decision: computing the real
    # ventilation ratio must never change whether generate() considers a
    # request feasible -- core/validator.py keeps the Phase 1
    # has-exterior-wall proxy as its actual hard check.
    from rivet.core.validator import validate_layout

    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    result = validate_layout(layout, sample_request.ruleset)
    assert result.is_valid  # unaffected by whether individual rooms pass the informational ratio


def test_quantity_takeoff_block_count_is_positive(sample_request):
    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)
    assert metrics.quantity_takeoff.block_count_estimate > 0
    assert metrics.quantity_takeoff.plaster_area_sqm > 0
    assert set(metrics.quantity_takeoff.floor_finish_area_by_room_sqm) == {r.id for r in layout.rooms}


def test_renderers_exporter_and_api_report_identical_gross_area(sample_request):
    # The whole point of Phase 2: PNG, SVG, DXF, and the API used to each
    # compute sum(r.rect.area for r in layout.rooms) independently. Now
    # they all read core.metrics.compute_metrics -- assert that's actually
    # true by checking the same formatted figure appears everywhere,
    # rather than just trusting the refactor.
    from rivet.api.schemas import layout_to_dict
    from rivet.export.dxf import build_document
    from rivet.render.svg import render_svg

    layouts = assert_feasible(generate(sample_request))
    layout = layouts[0]
    metrics = compute_metrics(layout, sample_request.ruleset)
    expected = f"{metrics.gross_area_sqm:.1f}"

    assert f"{expected} m² gross" in render_svg(layout)

    doc = build_document(layout)
    dxf_text = "\n".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert f"{expected} m2 gross" in dxf_text

    api_payload = layout_to_dict(layout)
    assert api_payload["gross_area_sqm"] == pytest.approx(metrics.gross_area_sqm, abs=0.01)
    assert api_payload["metrics"]["gross_area_sqm"] == pytest.approx(metrics.gross_area_sqm, abs=0.01)
