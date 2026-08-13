"""Project CRUD (docs/saas-buildout.md section 9)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from ...auth.dependencies import RequestContext, require_context
from ...db.models import Project
from ...db.session import get_db
from ..errors import ApiError
from ._ownership import get_owned_project, require_org

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectIn(BaseModel):
    name: str = Field(min_length=1)


class UpdateProjectIn(BaseModel):
    name: str | None = None
    archived: bool | None = None


def _project_dict(project: Project) -> dict:
    return {
        "id": str(project.id),
        "name": project.name,
        "created_at": project.created_at.isoformat(),
        "archived_at": project.archived_at.isoformat() if project.archived_at else None,
    }


@router.get("")
def list_projects(context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)) -> dict:
    org_id = require_org(context)
    projects = db.query(Project).filter_by(org_id=org_id).order_by(Project.created_at.desc()).all()
    return {"projects": [_project_dict(p) for p in projects]}


@router.post("")
def create_project(
    payload: CreateProjectIn, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    org_id = require_org(context)
    project = Project(org_id=org_id, name=payload.name, created_by=context.user.id if context.user else None)
    db.add(project)
    db.commit()
    return _project_dict(project)


@router.get("/{project_id}")
def get_project(
    project_id: uuid.UUID, context: RequestContext = Depends(require_context), db: DbSession = Depends(get_db)
) -> dict:
    return _project_dict(get_owned_project(db, context, project_id))


@router.patch("/{project_id}")
def update_project(
    project_id: uuid.UUID,
    payload: UpdateProjectIn,
    context: RequestContext = Depends(require_context),
    db: DbSession = Depends(get_db),
) -> dict:
    project = get_owned_project(db, context, project_id)
    if payload.name is not None:
        if not payload.name.strip():
            raise ApiError("validation_failed", "'name' cannot be empty.")
        project.name = payload.name
    if payload.archived is True and project.archived_at is None:
        project.archived_at = datetime.now(timezone.utc)
    elif payload.archived is False:
        project.archived_at = None
    db.commit()
    return _project_dict(project)
