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
    # Plot sized so its TNCDBR_2019 buildable area (~95 sqm under the
    # default road-width/height assumptions) roughly matches the room
    # program's target areas (~86 sqm) -- a 12x15 plot leaves ~135 sqm
    # buildable, which is legitimately larger than this program under the
    # real Rule 35 setbacks (a smaller front/side setback than the old
    # plot-area-tiered heuristic assumed), and the layout engine always
    # tiles 100% of buildable area (see docs/architecture.md), so an
    # oversized plot for the program produces artificially low soft scores
    # by inflating every room above its target -- not a bug, but not what
    # this fixture is for either. Circulation (docs/prompts.md Phase 3)
    # will let a layout leave buildable area unassigned instead.
    return GenerationRequest(
        plot=PlotSpec(width_m=12.0, length_m=11.0, entrance=Orientation.NORTH),
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
