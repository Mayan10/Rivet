import pytest

from rivet.core.models import GenerationRequest, Orientation, PlotSpec, RoomRequirement, RoomType


@pytest.fixture
def sample_request() -> GenerationRequest:
    return GenerationRequest(
        plot=PlotSpec(width_m=12.0, length_m=15.0, entrance=Orientation.NORTH),
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
