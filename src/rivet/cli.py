"""Command-line entry point.

Also doubles as a fast, dependency-light smoke test of the whole
pipeline (graph -> layout search -> openings -> render -> DXF) without
needing to stand up the Flask API.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import pathlib
import sys

from .core.generator import generate
from .core.models import GenerationRequest, Orientation, PlotSpec, RoomRequirement, RoomType
from .core.rules import ROOM_RULES, validate_request
from .export.dxf import export_dxf
from .render.raster import render_png
from .render.svg import render_svg


def _parse_room_spec(spec: str) -> RoomRequirement:
    """Parse ``type[:count][=area_sqm][+ensuite]``, e.g. ``bedroom:2=12.5+ensuite``."""
    ensuite = False
    if spec.endswith("+ensuite"):
        ensuite = True
        spec = spec[: -len("+ensuite")]

    area = None
    if "=" in spec:
        spec, area_str = spec.split("=", 1)
        try:
            area = float(area_str)
        except ValueError as exc:
            raise SystemExit(f"Invalid area in room spec '{spec}={area_str}': not a number") from exc

    if ":" in spec:
        type_str, count_str = spec.split(":", 1)
        try:
            count = int(count_str)
        except ValueError as exc:
            raise SystemExit(f"Invalid count in room spec '{spec}': '{count_str}' is not an integer") from exc
    else:
        type_str, count = spec, 1

    try:
        room_type = RoomType(type_str.strip().lower())
    except ValueError as exc:
        valid = ", ".join(t.value for t in RoomType)
        raise SystemExit(f"Unknown room type '{type_str}'. Valid types: {valid}") from exc

    return RoomRequirement(room_type=room_type, count=count, target_area_sqm=area, attached_bathroom=ensuite)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rivet", description="Rivet -- generative floor plan engine")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="Generate ranked floor plan candidates from a room program")
    gen.add_argument("--width", type=float, required=True, help="Plot width in meters (east-west)")
    gen.add_argument("--length", type=float, required=True, help="Plot length in meters (north-south)")
    gen.add_argument(
        "--entrance", choices=[o.value for o in Orientation], default="north", help="Which side the front door is on"
    )
    gen.add_argument(
        "--room",
        action="append",
        required=True,
        dest="rooms",
        metavar="SPEC",
        help="Room spec 'type[:count][=area_sqm][+ensuite]', repeatable. "
        "e.g. --room bedroom:2+ensuite --room kitchen --room bathroom:1",
    )
    gen.add_argument("--candidates", type=int, default=3, help="Number of ranked candidates to produce")
    gen.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
    gen.add_argument("--out-dir", default="output", help="Directory to write rendered files into")
    gen.add_argument("--formats", default="png,svg,dxf", help="Comma-separated: png,svg,dxf")

    sub.add_parser("rules", help="Print the design rulebook as JSON")
    sub.add_parser("room-types", help="List valid room type identifiers")

    return parser


def _run_generate(args: argparse.Namespace) -> int:
    room_reqs = [_parse_room_spec(s) for s in args.rooms]
    plot = PlotSpec(width_m=args.width, length_m=args.length, entrance=Orientation(args.entrance))

    issues = validate_request(
        plot.width_m, plot.length_m, [(r.room_type, r.count, r.target_area_sqm) for r in room_reqs]
    )
    for issue in issues:
        print(f"[warning] {issue}", file=sys.stderr)

    request = GenerationRequest(plot=plot, rooms=room_reqs, num_candidates=args.candidates, seed=args.seed)
    layouts = generate(request)

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    formats = {f.strip().lower() for f in args.formats.split(",") if f.strip()}

    for layout in layouts:
        base = out_dir / layout.candidate_id
        status = f"{layout.candidate_id}: score {layout.score}/100"
        if layout.violations:
            status += f" -- {len(layout.violations)} issue(s)"
        print(status)
        for v in layout.violations:
            print(f"   - {v}")

        if "png" in formats:
            render_png(layout).save(f"{base}.png")
        if "svg" in formats:
            (out_dir / f"{layout.candidate_id}.svg").write_text(render_svg(layout))
        if "dxf" in formats:
            export_dxf(layout, f"{base}.dxf")

    print(f"Wrote {len(layouts)} candidate(s) to {out_dir}/")
    return 0


def _run_rules() -> int:
    payload = {
        room_type.value: dataclasses.asdict(rule)
        for room_type, rule in ROOM_RULES.items()
    }
    print(json.dumps(payload, indent=2))
    return 0


def _run_room_types() -> int:
    for t in RoomType:
        print(t.value)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "generate":
        return _run_generate(args)
    if args.command == "rules":
        return _run_rules()
    if args.command == "room-types":
        return _run_room_types()
    return 1  # pragma: no cover - argparse enforces valid subcommands


if __name__ == "__main__":
    raise SystemExit(main())
