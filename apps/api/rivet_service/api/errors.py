"""Consistent error envelope for every 4xx/5xx response (saas-buildout.md
section 9): ``{"error": {"code": "...", "message": "...", "details": {}}}``.
Every route in this service raises :class:`ApiError` (or lets FastAPI's
own request-validation error through, translated by the handler below)
rather than returning an ad hoc error shape.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 400, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def _envelope(code: str, message: str, details: dict) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error_handler(_request: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=_envelope(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # 400, not FastAPI's default 422 -- 422 is reserved here for
        # "well-formed request, but the room program is infeasible"
        # (ApiError("infeasible_program", ...)), matching the pre-existing
        # Flask app's convention (rivet/api/routes.py) that this endpoint
        # is a same-behavior port of.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=_envelope("validation_failed", "Request failed validation.", {"errors": exc.errors()}),
        )
