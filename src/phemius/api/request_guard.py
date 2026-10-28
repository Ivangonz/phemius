"""Refuses DNS-rebinding hosts in local mode and cross-site changes in every mode.

Local mode has no token, so a page on another site must neither reach the API
under its own domain (rebinding) nor send it forms (CSRF).
"""

from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from phemius.api.access import OPEN_PATHS
from phemius.api.errors import error_body
from phemius.config import ENV_PREFIX
from phemius.services.access import is_loopback_host

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Fetch metadata values a browser sends for the page's own requests ("none" is
# the user typing the URL or following a bookmark).
TRUSTED_FETCH_SITES = {"same-origin", "none"}

log = structlog.get_logger(__name__)


async def guard_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if _is_untrusted_host(request):
        return _reject(
            request,
            400,
            "Unexpected Host header",
            "untrusted_host",
            hint="Open Phemius at http://localhost or http://127.0.0.1 with its"
            f" port. To use another address, set {ENV_PREFIX}ACCESS_MODE=network.",
        )
    if _is_cross_site_change(request):
        return _reject(
            request,
            403,
            "Cross-site request refused",
            "cross_site_request",
            hint="Changes are accepted only from the Phemius page itself or from"
            " clients that send no Origin header, such as curl.",
        )
    return await call_next(request)


def _is_untrusted_host(request: Request) -> bool:
    is_token_required: bool = getattr(request.app.state, "is_token_required", True)
    if is_token_required or request.url.path in OPEN_PATHS:
        return False
    return not is_loopback_host(_host_name(request.headers.get("Host", "")))


def _host_name(host: str) -> str:
    if host.startswith("["):
        return host[1:].partition("]")[0]
    return host.rpartition(":")[0] if ":" in host else host


def _is_cross_site_change(request: Request) -> bool:
    if request.method not in STATE_CHANGING_METHODS:
        return False
    # The browser computes Sec-Fetch-Site itself and pages cannot forge it, so it
    # is trusted over Origin: a reverse proxy may rewrite Host, and then Origin
    # would no longer match it on a same-origin request.
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site is not None:
        return fetch_site not in TRUSTED_FETCH_SITES
    origin = request.headers.get("Origin")
    if origin is None:
        return False
    return urlsplit(origin).netloc.lower() != request.headers.get("Host", "").lower()


def _reject(
    request: Request, status_code: int, detail: str, code: str, hint: str
) -> JSONResponse:
    log.warning(
        "request_refused", code=code, method=request.method, path=request.url.path
    )
    return JSONResponse(error_body(detail, code, hint=hint), status_code=status_code)
