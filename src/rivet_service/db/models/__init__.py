"""Import every model module here so Base.metadata is fully populated --
both for Alembic autogenerate (migrations/env.py imports this package)
and so callers can just do ``from rivet_service.db.models import User``.
"""

from .api_key import ApiKey
from .organization import Membership, MembershipRole, Organization
from .session import Session
from .user import User

__all__ = ["ApiKey", "Membership", "MembershipRole", "Organization", "Session", "User"]
