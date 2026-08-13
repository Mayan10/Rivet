"""Regenerate tests/fixtures/dxf_golden_census.json from the current
export/dxf output for the sample_request fixture's plot/room program.

Run only when a DXF structural change is deliberate -- this test exists
to catch *unintended* regressions, so overwriting the golden file should
be a conscious step, not something done to make a failing test pass
without checking why it changed first.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import ezdxf

from rivet.core.generator import generate
from rivet.core.models import GenerationRequest, Orientation, PlotSpec, RoomRequirement, RoomType
from rivet.export.dxf import export_dxf
from rivet.export.dxf.sheet import LAYOUT_NAME

# Mirrors tests/conftest.py::sample_request exactly.
_REQUEST = GenerationRequest(
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

_GOLDEN_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "dxf_golden_census.json"


def main() -> None:
    layouts = generate(_REQUEST)
    assert isinstance(layouts, list), "sample_request must stay feasible for the golden file to mean anything"
    layout = layouts[0]

    out_path = "/tmp/dxf_golden_regen.dxf"
    export_dxf(layout, out_path)
    doc = ezdxf.readfile(out_path)

    counts: Counter[str] = Counter()
    for lay in (doc.modelspace(), doc.layouts.get(LAYOUT_NAME)):
        counts.update(e.dxftype() for e in lay)

    _GOLDEN_PATH.write_text(json.dumps(dict(sorted(counts.items())), indent=2) + "\n")
    print(f"Wrote {_GOLDEN_PATH}")


if __name__ == "__main__":
    main()
