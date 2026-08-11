import io

import ezdxf
import pytest

from rivet.core.generator import generate
from rivet.export.dxf import export_dxf, export_dxf_bytes

EXPECTED_LAYERS = {
    "WALLS-EXTERIOR",
    "WALLS-INTERIOR",
    "DOORS",
    "WINDOWS",
    "TEXT",
    "DIMENSIONS",
    "ROOMS",
    "PLOT-BOUNDARY",
}


def test_export_dxf_is_structurally_valid(sample_request, tmp_path):
    layout = generate(sample_request)[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))

    doc = ezdxf.readfile(str(path))
    auditor = doc.audit()
    assert auditor.errors == []


def test_export_dxf_has_expected_layers_and_entity_counts(sample_request, tmp_path):
    layout = generate(sample_request)[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()

    layers_present = {e.dxf.layer for e in msp}
    assert EXPECTED_LAYERS.issubset(layers_present)

    room_polylines = [e for e in msp if e.dxf.layer == "ROOMS"]
    assert len(room_polylines) == len(layout.rooms)

    doors = [e for e in msp if e.dxf.layer == "DOORS"]
    windows = [e for e in msp if e.dxf.layer == "WINDOWS"]
    door_count = sum(1 for o in layout.openings if o.kind in ("door", "main_door"))
    window_count = sum(1 for o in layout.openings if o.kind == "window")
    # Each door draws 2 entities (leaf line + arc polyline); each window
    # draws 3 (span + two jamb ticks).
    assert len(doors) == door_count * 2
    assert len(windows) == window_count * 3


def test_export_dxf_bytes_round_trips(sample_request):
    layout = generate(sample_request)[0]
    data = export_dxf_bytes(layout)
    assert data.startswith((b"  0\r\nSECTION", b"0\nSECTION")) or b"SECTION" in data[:50]

    doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
    assert doc.audit().errors == []


def test_dimension_values_match_plot_size(sample_request, tmp_path):
    layout = generate(sample_request)[0]
    path = tmp_path / "plan.dxf"
    export_dxf(layout, str(path))

    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    dims = [e for e in msp if e.dxftype() == "DIMENSION"]
    assert len(dims) == 2

    measurements = sorted(d.get_measurement() for d in dims)
    expected = sorted([layout.plot.width_m, layout.plot.length_m])
    for actual, want in zip(measurements, expected):
        assert actual == pytest.approx(want, rel=1e-3)
