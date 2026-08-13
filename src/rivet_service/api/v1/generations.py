"""Async generate flow (docs/saas-buildout.md sections 6 & 9): validate,
write a queued row, enqueue, return 202. No quota/entitlement check yet
(Phase 9) -- any authenticated org can enqueue as many generations as it
wants, same deferral pattern Phase 7 used for API-key paid-tier gating.

Downloads return a JSON ``{"download_url": ...}`` rather than redirecting
-- lets a frontend decide whether to open it, embed it, etc., and matches
every other response on this API already being a JSON envelope.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from rivet.core.version import ENGINE_VERSION, RULEBOOK_VERSION

from ...auth.dependencies import RequestContext, require_context
from ...config import get_settings
from ...db.models import Artifact, Candidate, Generation, GenerationStatus
from ...db.session import get_db
from ...jobs.queue import get_queue
from ...jobs.tasks import run_generation_job
from ...storage import get_storage_adapter
from ..errors import ApiError
from ..schemas import GenerateRequestIn, to_generation_request
from ._ownership import get_owned_generation, get_owned_project

router = APIRouter(tags=["generations"])


def _candidate_dict(candidate: Candidate) -> dict:
    return {"index": candidate.index, "score": candidate.score, "score_breakdown": candidate.score_breakdown_json}


def _generation_dict(generation: Generation, db: DbSession) -> dict:
    candidates = db.query(Candidate).filter_by(generation_id=generation.id).order_by(Candidate.index).all()
    return {
        "id": str(generation.id),
        "project_id": str(generation.project_id),
        "status": generation.status,
        "error_message": generation.error_message,
        "engine_version": generation.engine_version,
        "rulebook_version": generation.rulebook_version,
        "queued_at": generation.queued_at.isoformat(),
        "started_at": generation.started_at.isoformat() if generation.started_at else None,
        "finished_at": generation.finished_at.isoformat() if generation.finished_at else None,
        "candidates": [_candidate_dict(c) for c in candidates],
    }


@router.post("/projects/{project_id}/generations", status_code=202)
def create_generation(
    project_id: uuid.UUID,
    payload: GenerateRequestIn,
    context: RequestContext = Depends(require_context),
    db: DbSession = Depends(get_db),
) -> dict:
    project = get_owned_project(db, context, project_id)
    to_generation_request(payload)  # validates early, raises ApiError on bad input -- same checks /generate does

    generation = Generation(
        project_id=project.id,
        org_id=context.org.id,
        created_by=context.user.id if context.user else None,
        status=GenerationStatus.QUEUED.value,
        request_json=payload.model_dump(),
        seed=payload.seed,
        engine_version=ENGINE_VERSION,
        rulebook_version=RULEBOOK_VERSION,
        queued_at=datetime.now(timezone.utc),
    )
    db.add(generation)
    db.commit()

    settings = get_settings()
    get_queue().enqueue(run_generation_job, str(generation.id), job_timeout=settings.job_timeout_seconds)

    return {"generation_id": str(generation.id), "status": generation.status}


@router.get("/generations/{generation_id}")
def get_generation(
    generation_id: uuid.UUID, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    generation = get_owned_generation(db, context, generation_id)
    return _generation_dict(generation, db)


@router.delete("/generations/{generation_id}")
def delete_generation(
    generation_id: uuid.UUID, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    generation = get_owned_generation(db, context, generation_id)

    storage = get_storage_adapter()
    candidates = db.query(Candidate).filter_by(generation_id=generation.id).all()
    for candidate in candidates:
        for artifact in db.query(Artifact).filter_by(candidate_id=candidate.id).all():
            storage.delete(artifact.storage_key)

    db.delete(generation)  # cascades to candidates/artifacts rows (ondelete="CASCADE")
    db.commit()
    return {"status": "ok"}


@router.get("/generations/{generation_id}/candidates/{index}/download")
def download_candidate_artifact(
    generation_id: uuid.UUID,
    index: int,
    format: str,
    context: RequestContext = Depends(require_context),
    db: DbSession = Depends(get_db),
) -> dict:
    generation = get_owned_generation(db, context, generation_id)
    candidate = db.query(Candidate).filter_by(generation_id=generation.id, index=index).first()
    if candidate is None:
        raise ApiError("not_found", "Candidate not found.", status_code=404)

    artifact = db.query(Artifact).filter_by(candidate_id=candidate.id, kind=format).first()
    if artifact is None:
        raise ApiError("not_found", f"No '{format}' artifact for this candidate.", status_code=404)

    settings = get_settings()
    storage = get_storage_adapter()
    url = storage.presigned_download_url(artifact.storage_key, expires_in=settings.artifact_url_ttl_seconds)
    return {"download_url": url, "expires_in": settings.artifact_url_ttl_seconds, "watermarked": artifact.watermarked}
