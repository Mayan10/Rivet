"""Phase 4: DXF export is a real CAD deliverable, not layered polylines.

Every assertion here round-trips through ``ezdxf.readfile``/``ezdxf.read``
(export, then re-open) rather than inspecting the in-memory ``Drawing``
directly, per the phase's own testing requirement -- a document that
looks right in memory but fails to reload correctly is exactly the kind
of bug this guards against.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import ezdxf
import pytest
from conftest import assert_feasible

from rivet.core.generator import generate
from rivet.export.dxf import export_dxf, export_dxf_bytes
from rivet.export.dxf.blocks import (
    BLOCK_DOOR,
    BLOCK_KITCHEN_COUNTER,
    BLOCK_NORTH_ARROW,
    BLOCK_WASHBASIN,
    BLOCK_WC,
    BLOCK_WINDOW,
)
from rivet.export.dxf.layers import AIA_LAYER_NAMES, LEGACY_LAYER_NAMES
from rivet.export.dxf.sheet import BLOCK_TITLE_BLOCK, LAYOUT_NAME

_GOLDEN_PATH = Path(__file__).parent / "fixtures" / "dxf_golden_census.json"


def _entity_census(doc) -> dict[str, int]:
    from collections import Counter

    counts: Counter[str] = Counter()
    for layout in (doc.modelspace(), doc.layouts.get(LAYOUT_NAME)):
        counts.update(e.dxftype() for e in layout)
    return dict(counts)


def test_export_dxf_is_structurally_valid(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))

    doc = ezdxf.readfile(str(path))
    auditor = doc.audit()
    assert auditor.errors == []


def test_export_dxf_bytes_round_trips(sample_request):
    layout = assert_feasible(generate(sample_request))[0]
    data = export_dxf_bytes(layout)
    assert data.startswith((b"  0\r\nSECTION", b"0\nSECTION")) or b"SECTION" in data[:50]

    doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
    assert doc.audit().errors == []


def test_units_are_millimeters(sample_request, tmp_path):
    # Phase 4 item 1's highest-priority finding: metre-unit output is
    # unusable for Indian CAD/construction practice.
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    assert doc.header["$INSUNITS"] == 4  # millimeters

    msp = doc.modelspace()
    boundary = next(e for e in msp if e.dxf.layer == AIA_LAYER_NAMES["plot_boundary"])
    xs = [p[0] for p in boundary.get_points()]
    assert max(xs) == pytest.approx(layout.plot.width_m * 1000, rel=1e-6)


def test_aia_layer_scheme_is_default(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))

    layers_present = {layer.dxf.name for layer in doc.layers}
    assert set(AIA_LAYER_NAMES.values()).issubset(layers_present)
    assert not set(LEGACY_LAYER_NAMES.values()) & layers_present


def test_legacy_layer_scheme_is_selectable(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path), layer_scheme="legacy")
    doc = ezdxf.readfile(str(path))

    layers_present = {layer.dxf.name for layer in doc.layers}
    assert set(LEGACY_LAYER_NAMES.values()).issubset(layers_present)
    assert not set(AIA_LAYER_NAMES.values()) & layers_present


def test_layer_colors_and_lineweights_are_set(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))

    ext = doc.layers.get(AIA_LAYER_NAMES["walls_ext"])
    interior = doc.layers.get(AIA_LAYER_NAMES["walls_int"])
    anno = doc.layers.get(AIA_LAYER_NAMES["dimensions"])
    assert ext.dxf.color != 0
    # Cut (exterior) walls get the heaviest lineweight, annotation the
    # lightest -- item 5's explicit ordering.
    assert ext.dxf.lineweight > interior.dxf.lineweight > anno.dxf.lineweight


def test_block_definitions_exist(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))

    for name in (BLOCK_DOOR, BLOCK_WINDOW, BLOCK_NORTH_ARROW, BLOCK_WC, BLOCK_WASHBASIN, BLOCK_KITCHEN_COUNTER, BLOCK_TITLE_BLOCK):
        assert name in doc.blocks, f"missing block definition {name}"


def test_insert_count_equals_doors_and_windows_plus_fixed_symbols(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    door_count = sum(1 for o in layout.openings if o.kind in ("door", "main_door"))
    window_count = sum(1 for o in layout.openings if o.kind == "window")
    inserts = list(msp.query("INSERT"))
    door_window_inserts = [i for i in inserts if i.dxf.name in (BLOCK_DOOR, BLOCK_WINDOW)]
    assert len(door_window_inserts) == door_count + window_count

    # North arrow is inserted exactly once.
    assert sum(1 for i in inserts if i.dxf.name == BLOCK_NORTH_ARROW) == 1

    # Title block is inserted exactly once, in paper space.
    psp = doc.layouts.get(LAYOUT_NAME)
    title_inserts = [i for i in psp.query("INSERT") if i.dxf.name == BLOCK_TITLE_BLOCK]
    assert len(title_inserts) == 1


def test_door_and_window_attributes_carry_schedule_data(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    for insert in msp.query("INSERT"):
        if insert.dxf.name not in (BLOCK_DOOR, BLOCK_WINDOW):
            continue
        tags = {a.dxf.tag: a.dxf.text for a in insert.attribs}
        assert tags["TAG"]  # non-empty schedule tag
        assert tags["ROOM"]  # host room label
        assert float(tags["WIDTH_MM"]) > 0
        assert float(tags["HEIGHT_MM"]) > 0


def test_every_wall_boundary_polyline_is_closed(sample_request, tmp_path):
    from rivet.export.dxf.layers import AIA_LAYER_NAMES as L

    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    wall_layers = {L["walls_ext"], L["walls_int"]}
    wall_polylines = [e for e in msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer in wall_layers]
    assert wall_polylines
    for poly in wall_polylines:
        assert poly.closed


def test_masonry_hatch_exists_with_boundary_paths(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    hatches = list(msp.query("HATCH"))
    assert hatches
    for hatch in hatches:
        assert len(hatch.paths) > 0
        assert hatch.dxf.pattern_name == "ANSI31"


def test_overall_and_per_room_dimensions_exist(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    dims = list(msp.query("DIMENSION"))
    # 2 overall (width, length) + 2 per room (width, depth).
    assert len(dims) == 2 + 2 * len(layout.rooms)

    measurements = sorted(d.get_measurement() for d in dims)
    expected_overall = sorted([layout.plot.width_m * 1000, layout.plot.length_m * 1000])
    for actual, want in zip(measurements[-2:], expected_overall):
        assert actual == pytest.approx(want, rel=1e-3)


def test_paper_space_layout_and_locked_viewport_exist(sample_request, tmp_path):
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))

    assert LAYOUT_NAME in doc.layouts.names()
    psp = doc.layouts.get(LAYOUT_NAME)
    viewports = [v for v in psp.query("VIEWPORT") if v.dxf.id != 1]  # id 1 is the implicit paper-space viewport
    assert len(viewports) == 1
    from ezdxf.lldxf import const

    assert viewports[0].dxf.flags & const.VSF_LOCK_ZOOM


def test_schedules_reflect_layout_metrics(sample_request, tmp_path):
    from rivet.core.metrics import compute_metrics

    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))
    psp = doc.layouts.get(LAYOUT_NAME)

    metrics = compute_metrics(layout, layout.ruleset)
    schedule_text = "\n".join(e.dxf.text for e in psp.query("TEXT"))
    for row in metrics.door_schedule:
        assert row.tag in schedule_text
    for room in metrics.rooms:
        assert room.label in schedule_text


def test_title_block_attributes_carry_provided_metadata(sample_request, tmp_path):
    from rivet.export.dxf import TitleBlockInfo

    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(
        layout,
        str(path),
        title_block_info=TitleBlockInfo(project="Test Project", client="Test Client", sheet="A-102", revision="2"),
    )
    doc = ezdxf.readfile(str(path))
    psp = doc.layouts.get(LAYOUT_NAME)
    insert = next(i for i in psp.query("INSERT") if i.dxf.name == BLOCK_TITLE_BLOCK)
    values = {a.dxf.tag: a.dxf.text for a in insert.attribs}

    assert values["PROJECT"] == "Test Project"
    assert values["CLIENT"] == "Test Client"
    assert values["SHEET"] == "A-102"
    assert values["REVISION"] == "2"


def test_entity_type_census_matches_golden_file(sample_request, tmp_path):
    # Golden-file regression guard: fails if the entity-type census of a
    # fixed reference plan changes, catching any unintended structural
    # regression a purely behavioral test might miss. Regenerate
    # deliberately (not silently) with:
    #   python scripts/regenerate_dxf_golden.py
    layout = assert_feasible(generate(sample_request))[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))
    doc = ezdxf.readfile(str(path))

    census = _entity_census(doc)
    golden = json.loads(_GOLDEN_PATH.read_text())
    assert census == golden, (
        "Entity-type census changed from the committed golden file. If this is an "
        "intentional structural change, regenerate tests/fixtures/dxf_golden_census.json."
    )
