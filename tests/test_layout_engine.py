import itertools

import pytest

from rivet.core.generator import generate
from rivet.core.models import GenerationRequest, Orientation, PlotSpec, RoomRequirement, RoomType


def test_generate_produces_requested_number_of_candidates(sample_request):
    layouts = generate(sample_request)
    assert 1 <= len(layouts) <= sample_request.num_candidates


def test_candidates_are_sorted_best_first(sample_request):
    layouts = generate(sample_request)
    scores = [layout.score for layout in layouts]
    assert scores == sorted(scores, reverse=True)


def test_rooms_do_not_overlap(sample_request):
    layouts = generate(sample_request)
    for layout in layouts:
        for a, b in itertools.combinations(layout.rooms, 2):
            assert not a.rect.overlaps(b.rect), f"{a.label} overlaps {b.label} in {layout.candidate_id}"


def test_rooms_tile_the_buildable_area_exactly(sample_request):
    layouts = generate(sample_request)
    for layout in layouts:
        total = sum(r.rect.area for r in layout.rooms)
        assert total == pytest.approx(layout.buildable.area, rel=1e-6)


def test_rooms_stay_within_buildable_bounds(sample_request):
    layouts = generate(sample_request)
    for layout in layouts:
        for room in layout.rooms:
            assert layout.buildable.contains(room.rect), f"{room.label} escapes the buildable rect"


def test_top_candidate_has_no_min_width_violations(sample_request):
    # Only the best-ranked candidate needs to be clean for a comfortably-
    # sized request -- the other returned candidates are deliberately
    # diverse alternatives and may trade off a minor violation, which is
    # exactly what their (lower) score should reflect.
    best = generate(sample_request)[0]
    min_width_issues = [v for v in best.violations if "minimum for this room type" in v]
    assert min_width_issues == [], f"{best.candidate_id}: {min_width_issues}"


def test_reasonable_request_scores_well(sample_request):
    layouts = generate(sample_request)
    assert layouts[0].score >= 80.0


def test_same_seed_is_deterministic(sample_request):
    layouts_a = generate(sample_request)
    layouts_b = generate(sample_request)
    assert [layout.score for layout in layouts_a] == [layout.score for layout in layouts_b]
    for a, b in zip(layouts_a, layouts_b):
        for room_a, room_b in zip(a.rooms, b.rooms):
            assert room_a.rect.x == room_b.rect.x
            assert room_a.rect.y == room_b.rect.y


def test_tight_plot_still_produces_valid_non_overlapping_geometry():
    request = GenerationRequest(
        plot=PlotSpec(width_m=8.0, length_m=10.0, entrance=Orientation.SOUTH),
        rooms=[
            RoomRequirement(RoomType.LIVING_ROOM, count=1),
            RoomRequirement(RoomType.BEDROOM, count=3),
            RoomRequirement(RoomType.KITCHEN, count=1),
            RoomRequirement(RoomType.BATHROOM, count=2),
            RoomRequirement(RoomType.CORRIDOR, count=1),
        ],
        num_candidates=2,
        seed=7,
    )
    # Even when the room program doesn't comfortably fit (expect min-width
    # violations to be reported honestly), the tiling itself must still be
    # geometrically valid -- no overlaps, full coverage.
    layouts = generate(request)
    for layout in layouts:
        for a, b in itertools.combinations(layout.rooms, 2):
            assert not a.rect.overlaps(b.rect)
        total = sum(r.rect.area for r in layout.rooms)
        assert total == pytest.approx(layout.buildable.area, rel=1e-6)

