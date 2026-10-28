"""Access token: the check on every API request and the regenerate endpoint."""

import re
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from phemius.api.errors import error_body
from phemius.services import access as access_service

router = APIRouter(prefix="/api/access", tags=["access"])

# Docker and uptime checks probe health without a secret, and it reveals no
# library data.
OPEN_PATHS = {"/api/health"}
# An <audio> element cannot send headers, so audio files also accept ?token=.
AUDIO_FILE_PATH = re.compile(r"/api/audio/\d+/file")


class AccessToken(BaseModel):
    token: str


@router.post("/token")
def regenerate_token(response: Response) -> AccessToken:
    """Replace the access token and return the new one. It is shown only here."""
    response.headers["Cache-Control"] = "no-store"
    return AccessToken(token=access_service.regenerate_token())


async def require_access_token(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if not _is_protected(request):
        return await call_next(request)
    token = _presented_token(request)
    if await run_in_threadpool(access_service.is_valid_token, token):
        return await call_next(request)
    return JSONResponse(
        error_body(
            "Access token required",
            "unauthorized",
            hint="Enter the access token shown when the server first started.",
        ),
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _is_protected(request: Request) -> bool:
    path = request.url.path
    is_api = path == "/api" or path.startswith("/api/")
    # Fail closed: the flag is set at startup, so a missing one means "required".
    is_required: bool = getattr(request.app.state, "is_token_required", True)
    return is_required and is_api and path not in OPEN_PATHS


def _presented_token(request: Request) -> str | None:
    scheme, _, credentials = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    if request.method in {"GET", "HEAD"} and AUDIO_FILE_PATH.fullmatch(
        request.url.path
    ):
        return request.query_params.get("token")
    return None
