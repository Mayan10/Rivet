"""FastAPI app factory (Phase 6, docs/saas-buildout.md).

``/healthz`` is liveness only (the process is up, nothing else checked).
``/readyz`` is readiness: it actually pings the database, since that's
the one real dependency this phase introduces. Kubernetes/ECS-style
distinction on purpose -- a process that's up but can't reach its DB
should fail readiness (get taken out of a load balancer) without being
killed and restarted for no reason.
"""

from __future__ import annotations

import sentry_sdk
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from .api.errors import register_error_handlers
from .api.v1 import router as v1_router
from .config import get_settings
from .db.session import database_is_reachable
from .logging_config import configure_logging
from .middleware.request_id import RequestIdMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    if settings.sentry_dsn:
        # No-op (not even imported meaningfully) when unset -- no real
        # Sentry project is required for the rest of the service to work.
        sentry_sdk.init(dsn=settings.sentry_dsn, environment=settings.env, send_default_pii=False)

    app = FastAPI(title=settings.app_name)

    # Order matters: Starlette runs middleware in reverse of add order,
    # so RequestIdMiddleware (added last) is outermost and sees every
    # request first -- CORS's own preflight handling and every log line
    # from here down get a request id.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins_list,  # no wildcard (section 11) -- explicit origins only
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    register_error_handlers(app)
    app.include_router(v1_router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz(response: Response) -> dict:
        db_ok = database_is_reachable()
        if not db_ok:
            response.status_code = 503
        return {"status": "ok" if db_ok else "not_ready", "database": db_ok}

    return app


app = create_app()
