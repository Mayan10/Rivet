"""Shared "does this resource belong to the caller's org" lookups for
projects.py and generations.py -- 404, not 403, on a mismatch: don't
reveal that a resource exists in an org the caller isn't in.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DbSession

from ...auth.dependencies import RequestContext
from ...db.models import Generation, Project
from ..errors import ApiError


def require_org(context: RequestContext) -> uuid.UUID:
    if context.org is None:
        raise ApiError("unauthorized", "No organization in context.", status_code=401)
    return context.org.id


def get_owned_project(db: DbSession, context: RequestContext, project_id: uuid.UUID) -> Project:
    org_id = require_org(context)
    project = db.query(Project).filter_by(id=project_id, org_id=org_id).first()
    if project is None:
        raise ApiError("not_found", "Project not found.", status_code=404)
    return project


def get_owned_generation(db: DbSession, context: RequestContext, generation_id: uuid.UUID) -> Generation:
    org_id = require_org(context)
    generation = db.query(Generation).filter_by(id=generation_id, org_id=org_id).first()
    if generation is None:
        raise ApiError("not_found", "Generation not found.", status_code=404)
    return generation
