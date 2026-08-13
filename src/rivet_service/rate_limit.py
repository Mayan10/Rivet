"""Redis-backed fixed-window rate limiting (docs/saas-buildout.md section
11: "unauthenticated endpoints by IP, authenticated by org"). Reuses the
same Redis connection Phase 8's job queue already depends on -- no new
infrastructure, no new dependency.

Fixed window (INCR + EXPIRE), not a sliding window or token bucket:
simple enough to read in one function and debug without a library, which
matters more here than smoothing bursts at a window boundary -- this is
abuse mitigation, not a precision SLA.

Client IP is read from the ASGI connection directly (``request.client.host``),
not ``X-Forwarded-For`` -- there's no reverse proxy in front of this
service in any environment that exists today. Whoever adds one (Phase
12, deploy) needs to revisit this alongside picking a trusted-proxy
header, since trusting an arbitrary inbound X-Forwarded-For today would
let any caller claim any IP and dodge the limit entirely.

Fails open (allows the request) if Redis itself is unreachable, logging
a warning -- a Redis blip degrading abuse mitigation is an acceptable
trade against a Redis blip taking down the entire API.
"""

from __future__ import annotations

import logging
import time

from fastapi import Depends, Request

from .api.errors import ApiError
from .auth.dependencies import RequestContext, current_context
from .config import get_settings
from .jobs.queue import get_redis_connection

logger = logging.getLogger(__name__)


def enforce_rate_limit(request: Request, context: RequestContext = Depends(current_context)) -> None:
    settings = get_settings()
    if context.org is not None:
        scope, key, limit = "org", str(context.org.id), settings.rate_limit_authenticated_max
    else:
        client_host = request.client.host if request.client else "unknown"
        scope, key, limit = "ip", client_host, settings.rate_limit_unauthenticated_max

    window = settings.rate_limit_window_seconds
    window_start = int(time.time()) // window
    redis_key = f"ratelimit:{scope}:{key}:{window_start}"

    try:
        redis = get_redis_connection()
        count = redis.incr(redis_key)
        if count == 1:
            redis.expire(redis_key, window)
    except Exception:
        logger.warning("rate limiter: Redis unreachable, failing open for this request", exc_info=True)
        return

    if count > limit:
        raise ApiError(
            "rate_limited",
            "Too many requests. Try again shortly.",
            status_code=429,
            details={"retry_after_seconds": window},
        )
