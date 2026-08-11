"""API routes.

``/api/v1/generate`` is the only endpoint that does real work; the rest
(``/rules``, ``/room-types``, ``/health``) exist so a client (or the web
UI) can introspect what the engine will accept before submitting a request.
"""

from __future__ import annotations

import dataclasses
import re
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, send_file

from .. import __version__
from ..core.generator import generate
from ..core.models import RoomType
from ..core.rules import ROOM_RULES
from ..core.rules import validate_request as validate_rulebook
from ..export.dxf import export_dxf
from .schemas import RequestValidationError, layout_to_dict, parse_generation_request

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
download_bp = Blueprint("download", __name__)

_TOKEN_RE = re.compile(r"^[a-f0-9]{32}\.dxf$")


@api_bp.get("/health")
def health():
    return jsonify({"status": "ok", "version": __version__})


@api_bp.get("/room-types")
def room_types():
    return jsonify(sorted(t.value for t in RoomType))


@api_bp.get("/rules")
def rules():
    return jsonify({room_type.value: dataclasses.asdict(rule) for room_type, rule in ROOM_RULES.items()})


@api_bp.post("/generate")
def generate_endpoint():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    try:
        gen_request = parse_generation_request(payload)
    except RequestValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    warnings = validate_rulebook(
        gen_request.plot.width_m,
        gen_request.plot.length_m,
        [(r.room_type, r.count, r.target_area_sqm) for r in gen_request.rooms],
    )

    try:
        layouts = generate(gen_request)
    except ValueError as exc:
        return jsonify({"error": str(exc), "warnings": warnings}), 422

    output_dir = Path(current_app.config["RIVET_OUTPUT_DIR"])
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = []
    for layout in layouts:
        token = uuid.uuid4().hex
        export_dxf(layout, str(output_dir / f"{token}.dxf"))
        candidates.append(layout_to_dict(layout, dxf_url=f"/download/{token}.dxf"))

    return jsonify({"warnings": warnings, "candidates": candidates})


@download_bp.get("/download/<token>")
def download(token: str):
    if not _TOKEN_RE.match(token):
        return jsonify({"error": "Not found"}), 404

    path = Path(current_app.config["RIVET_OUTPUT_DIR"]) / token
    if not path.is_file():
        return jsonify({"error": "Not found"}), 404

    return send_file(path, as_attachment=True, download_name="rivet-floorplan.dxf")
