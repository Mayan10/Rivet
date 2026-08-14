"""One id per request, in every log line for that request and echoed
back on the response (docs/saas-buildout.md section 10: "request id on
every line"). Reuses an inbound ``X-Request-ID`` header when a caller
(a load balancer, or a frontend forwarding its own trace id) already set
one, so a request can be correlated across services -- there's no
security concern in trusting an arbitrary inbound value here, since it
only ever ends up as a log field, never used for authorization.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ..logging_config import request_id_var

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
