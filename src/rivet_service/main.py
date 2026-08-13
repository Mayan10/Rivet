"""FastAPI app factory (Phase 6, docs/saas-buildout.md).

``/healthz`` is liveness only (the process is up, nothing else checked).
``/readyz`` is readiness: it actually pings the database, since that's
the one real dependency this phase introduces. Kubernetes/ECS-style
distinction on purpose -- a process that's up but can't reach its DB
should fail readiness (get taken out of a load balancer) without being
killed and restarted for no reason.
"""

from __future__ import annotations

from fastapi import FastAPI, Response

from .api.errors import register_error_handlers
from .api.v1 import router as v1_router
from .config import get_settings
from .db.session import database_is_reachable


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

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
