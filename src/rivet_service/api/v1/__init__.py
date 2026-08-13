from fastapi import APIRouter, Depends

from ...auth.csrf import enforce_csrf
from ...rate_limit import enforce_rate_limit
from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .billing import router as billing_router
from .generate import router as generate_router
from .generations import router as generations_router
from .local_artifacts import router as local_artifacts_router
from .me import router as me_router
from .projects import router as projects_router

router = APIRouter(prefix="/api/v1")

# Rate-limited by IP (unauthenticated) or org (authenticated), and
# CSRF-checked on cookie-authenticated state-changing requests --
# enforce_rate_limit/enforce_csrf each read context themselves, so these
# two dependencies cover every route in every included router uniformly
# (enforce_csrf is a no-op for GET/HEAD/OPTIONS and for non-session auth,
# so applying it broadly is safe -- no route-by-route judgment call).
# billing_router is deliberately excluded here: it's wired route-by-route
# inside api/v1/billing.py instead, so the webhook receiver (Stripe's
# shared infrastructure, not a single caller to throttle, and never
# session-authenticated) can be excluded from both.
_guarded = [Depends(enforce_rate_limit), Depends(enforce_csrf)]
router.include_router(generate_router, dependencies=_guarded)
router.include_router(auth_router, dependencies=_guarded)
router.include_router(me_router, dependencies=_guarded)
router.include_router(api_keys_router, dependencies=_guarded)
router.include_router(projects_router, dependencies=_guarded)
router.include_router(generations_router, dependencies=_guarded)
router.include_router(local_artifacts_router, dependencies=_guarded)
router.include_router(billing_router)
