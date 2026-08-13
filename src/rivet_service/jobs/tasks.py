"""The actual RQ job (docs/saas-buildout.md section 6): run the engine,
render PNG/SVG, export DXF, upload each to storage, write candidate and
artifact rows, mark the generation succeeded or failed.

A plain importable function, not a method on some job-runner class --
that's what RQ expects (``queue.enqueue(run_generation_job, ...)``), and
it means tests can call it directly without a live worker process.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from rivet.core.generator import generate
from rivet.core.models import InfeasibleResult
from rivet.export.dxf import export_dxf_bytes
from rivet.render.raster import render_png_bytes
from rivet.render.svg import render_svg

from ..api.schemas import GenerateRequestIn, to_generation_request
from ..db.models import Artifact, Candidate, Generation, GenerationStatus
from ..db.session import SessionLocal
from ..storage import get_storage_adapter

logger = logging.getLogger(__name__)

_CONTENT_TYPES = {"png": "image/png", "svg": "image/svg+xml", "dxf": "application/dxf"}


def _render_artifacts(layout) -> list[tuple[str, bytes]]:
    return [
        ("png", render_png_bytes(layout)),
        ("svg", render_svg(layout).encode("utf-8")),
        ("dxf", export_dxf_bytes(layout)),
    ]


def run_generation_job(generation_id: str) -> None:
    db = SessionLocal()
    try:
        generation = db.get(Generation, uuid.UUID(generation_id))
        if generation is None:
            logger.warning("run_generation_job: generation %s no longer exists, skipping", generation_id)
            return

        generation.status = GenerationStatus.RUNNING.value
        generation.started_at = datetime.now(timezone.utc)
        db.commit()

        try:
            request = to_generation_request(GenerateRequestIn.model_validate(generation.request_json))
            # engine_version/rulebook_version were already recorded at
            # enqueue time (api/v1/generations.py) from the same
            # rivet.core.version constants -- re-checking here would only
            # ever say "yes, still true," since nothing in this process
            # changes them mid-flight.
            result = generate(request)

            if isinstance(result, InfeasibleResult):
                generation.status = GenerationStatus.FAILED.value
                generation.error_message = result.message
                generation.finished_at = datetime.now(timezone.utc)
                db.commit()
                return

            storage = get_storage_adapter()
            for i, layout in enumerate(result, start=1):
                candidate = Candidate(
                    generation_id=generation.id, index=i, score=layout.score, score_breakdown_json=layout.score_breakdown
                )
                db.add(candidate)
                db.flush()

                for kind, data in _render_artifacts(layout):
                    # Never guessable/sequential (section 6) -- the path
                    # prefix is only for a human skimming a bucket
                    # listing, the actual key component is a fresh uuid.
                    key = f"generations/{generation.id}/{uuid.uuid4()}.{kind}"
                    storage.put(key, data, content_type=_CONTENT_TYPES[kind])
                    db.add(
                        Artifact(
                            candidate_id=candidate.id,
                            kind=kind,
                            storage_key=key,
                            size_bytes=len(data),
                            sha256=hashlib.sha256(data).hexdigest(),
                            watermarked=False,
                        )
                    )

            generation.status = GenerationStatus.SUCCEEDED.value
            generation.finished_at = datetime.now(timezone.utc)
            db.commit()
        except Exception as exc:
            db.rollback()
            generation = db.get(Generation, uuid.UUID(generation_id))
            generation.status = GenerationStatus.FAILED.value
            generation.error_message = str(exc)
            generation.finished_at = datetime.now(timezone.utc)
            db.commit()
            raise
    finally:
        db.close()
