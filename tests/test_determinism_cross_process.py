"""CLAUDE.md's determinism contract: the same GenerationRequest + seed must
produce byte-identical output across *separate process* invocations, not
just within one Python session.

This matters because Python randomizes string-hash seeding per process by
default (PYTHONHASHSEED). A prior real bug in this codebase
(``layout_engine._graph_guided_order`` iterating a bare ``set()``) was
reproducible within a single pytest process but produced different output
across separate ``python3`` invocations, because the set's iteration order
-- and therefore which room got which ``rng.random()`` draw -- depended on
the process's hash seed. It was caught by manually running the same seeded
request in three separate shell invocations and diffing the output, not by
any automated test, because nothing spanned a process boundary. This test
is that check, automated, so a future regression of the same class fails
CI instead of needing to be rediscovered by hand.

See docs/architecture.md "Determinism" for the full story.
"""

from __future__ import annotations

import json
import subprocess
import sys

_SCRIPT = """
import json
from rivet.core.models import GenerationRequest, Orientation, PlotSpec, RoomRequirement, RoomType
from rivet.core.generator import generate

request = GenerationRequest(
    plot=PlotSpec(
        width_m=15.0, length_m=13.0, entrance=Orientation.NORTH,
        abutting_road_width_m=9.0, proposed_height_m=6.0,
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
result = generate(request)
payload = [
    {
        "candidate_id": layout.candidate_id,
        "score": layout.score,
        "rooms": sorted(
            (
                {
                    "id": r.id,
                    "x": round(r.rect.x, 6),
                    "y": round(r.rect.y, 6),
                    "w": round(r.rect.w, 6),
                    "h": round(r.rect.h, 6),
                }
                for r in layout.rooms
            ),
            key=lambda d: d["id"],
        ),
    }
    for layout in result
]
print(json.dumps(payload, sort_keys=True))
"""


def _generate_in_fresh_process() -> str:
    # No PYTHONHASHSEED override in env -- each subprocess gets Python's
    # default per-process-random hash seed, which is exactly the axis the
    # original bug varied on.
    proc = subprocess.run(
        [sys.executable, "-c", _SCRIPT],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    return proc.stdout.strip()


def test_generation_is_deterministic_across_separate_processes():
    outputs = [_generate_in_fresh_process() for _ in range(3)]

    assert outputs[0], "generate() produced no output"
    for output in outputs[1:]:
        assert output == outputs[0]

    # Parse to confirm it's real, non-trivial content, not e.g. all-empty
    # candidate lists trivially matching each other.
    parsed = json.loads(outputs[0])
    assert len(parsed) >= 1
    assert len(parsed[0]["rooms"]) >= 1
