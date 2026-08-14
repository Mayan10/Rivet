"""Structured JSON logs with a request id on every line (docs/saas-
buildout.md section 10). The formatter itself can't stop a call site from
logging a secret or a full request body -- that's a discipline enforced
by never writing that code, same as this codebase already avoids logging
password/session-token values anywhere. What this module *can* guarantee
mechanically is that every line carries the request id, without every
log call needing to pass it explicitly -- middleware/request_id.py sets
``request_id_var`` once per request, and this formatter reads it back.
"""

from __future__ import annotations

import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)
