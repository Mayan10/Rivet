import pytest

from rivet.core.models import (
    GenerationRequest,
    InfeasibleResult,
    Layout,
    Orientation,
    PlotSpec,
    RoomRequirement,
    RoomType,
)


def assert_feasible(result: list[Layout] | InfeasibleResult) -> list[Layout]:
    """Assert generate() returned layouts (not InfeasibleResult) and return
    them, with a useful failure message if it didn't -- for tests whose
    fixture is expected to be comfortably feasible.
    """
    if isinstance(result, InfeasibleResult):
        details = "\n".join(f"  - [{v.constraint_id}] {v.message}" for v in result.hardest_violations)
        pytest.fail(f"Expected a feasible result but got InfeasibleResult: {result.message}\n{details}")
    return result


@pytest.fixture
def sample_request() -> GenerationRequest:
    # Plot sized for this room program *with* circulation (Phase 3):
    # auto-generated corridors now consume real buildable area (and, for
    # a program this size, branch into two segments -- see
    # docs/architecture.md "Circulation"), so the 12x11 plot that worked
    # before Phase 3 is now genuinely too tight (en-suites and the dining
    # room can no longer clear their legal minimum width once corridors
    # take their share). This is a real consequence of adding circulation,
    # not a bug -- same category of resizing Phase 1 and Phase 2 each
    # needed. The soft score at this size is still modest (~20s) because
    # of the separate, pre-existing "buildable bigger than target sum"
    # effect (Phase 0/1/2) -- not re-tuned away here, just not compounded
    # by an aspect-ratio problem anymore (see rules.py BATHROOM/TOILET
    # max_aspect_ratio, bumped 2.2 -> 4.0 as part of this phase: a narrow
    # en-suite alongside its bedroom is normal, not a quality defect, and
    # forcing every corridor-bordering room onto one axis -- required for
    # the reachability guarantee -- exposed that the old 2.2 target never
    # accounted for that).
    return GenerationRequest(
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
        ],
        num_candidates=3,
        seed=42,
    )
