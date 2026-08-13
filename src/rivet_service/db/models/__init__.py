"""Import every model module here so Base.metadata is fully populated --
both for Alembic autogenerate (migrations/env.py imports this package)
and so callers can just do ``from rivet_service.db.models import User``.
"""

from .api_key import ApiKey
from .artifact import Artifact
from .candidate import Candidate
from .generation import Generation, GenerationStatus
from .organization import Membership, MembershipRole, Organization
from .plan import Plan
from .project import Project
from .session import Session
from .usage_event import UsageEvent
from .user import User

__all__ = [
    "ApiKey",
    "Artifact",
    "Candidate",
    "Generation",
    "GenerationStatus",
    "Membership",
    "MembershipRole",
    "Organization",
    "Plan",
    "Project",
    "Session",
    "UsageEvent",
    "User",
]
