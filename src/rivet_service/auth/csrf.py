"""Double-submit-cookie CSRF protection for cookie-authenticated,
state-changing routes (docs/saas-buildout.md section 11). API-key auth
(``Authorization: Bearer ...``) is exempt -- a cross-site request can
make a browser attach a cookie automatically, but it can't make a
browser attach a custom Authorization header, so there's nothing for
CSRF to exploit on that path.

The cookie's value carries no meaning beyond "a value only same-origin
JS could have read out of a cookie and echoed back in a header" -- it
isn't looked up against anything server-side, unlike the session token
itself (auth/sessions.py). A cross-site attacker can trigger the cookie
to be *sent*, but can't *read* its value to also put it in the header,
which is exactly the asymmetry this defends.
"""

from __future__ import annotations

import hmac
import secrets

from fastapi import Depends, Request, Response

from ..api.errors import ApiError
from ..config import get_settings
from .dependencies import RequestContext, current_context

CSRF_COOKIE_NAME = "rivet_csrf"
CSRF_HEADER_NAME = "X-CSRF-Token"

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def issue_csrf_cookie(response: Response) -> None:
    """Called alongside every session-cookie issuance (register, login)."""
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=False,  # must be JS-readable -- that's the whole mechanism
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_ttl_days * 86400,
    )


def enforce_csrf(request: Request, context: RequestContext = Depends(current_context)) -> None:
    if request.method in _SAFE_METHODS or context.auth_method != "session":
        return

    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value or not hmac.compare_digest(cookie_value, header_value):
        raise ApiError("csrf_failed", "Missing or invalid CSRF token.", status_code=403)
