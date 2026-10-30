"""Access token: the check on every API request and the regenerate endpoint."""

import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from phemius.api.errors import error_body
from phemius.config import AccessMode
from phemius.services import access as access_service

router = APIRouter(prefix="/api/access", tags=["access"])

# Docker and uptime checks probe health without a secret, and it reveals no
# library data.
OPEN_PATHS = {"/api/health"}
# An <audio> element cannot send headers, so audio files and voice previews also
# accept a signed, short-lived URL (GET /api/audio/{id}/url, POST .../preview).
AUDIO_FILE_PATH = re.compile(r"/api/audio/(\d+)/file")
PREVIEW_FILE_PATH = re.compile(r"/api/voices/([^/]+)/preview/file")


class AccessToken(BaseModel):
    token: str


class AccessStatus(BaseModel):
    active_mode: AccessMode
    is_token_required: bool
    has_token: bool
    is_token_from_env: bool
    # The port this server listens on; None when the server does not report one.
    port: int | None


@router.get("")
def get_access_status(request: Request) -> AccessStatus:
    """How the server is reached. The token and its hash are never included."""
    status = access_service.describe_access(_active_mode(request))
    return AccessStatus(**asdict(status), port=_listening_port(request))


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
    token = _bearer_token(request)
    if await run_in_threadpool(access_service.is_valid_token, token):
        return await call_next(request)
    if await run_in_threadpool(_has_valid_file_signature, request):
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


def _active_mode(request: Request) -> AccessMode:
    mode: AccessMode = request.app.state.access_mode
    return mode


def _listening_port(request: Request) -> int | None:
    server = request.scope.get("server")
    return int(server[1]) if server and server[1] is not None else None


def _bearer_token(request: Request) -> str | None:
    scheme, _, credentials = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    return None


def _has_valid_file_signature(request: Request) -> bool:
    if request.method not in {"GET", "HEAD"}:
        return False
    path = request.url.path
    expires = request.query_params.get("expires")
    signature = request.query_params.get("sig")
    if audio := AUDIO_FILE_PATH.fullmatch(path):
        audio_id = int(audio.group(1))
        return access_service.is_valid_audio_signature(audio_id, expires, signature)
    if preview := PREVIEW_FILE_PATH.fullmatch(path):
        voice_id = preview.group(1)
        return access_service.is_valid_preview_signature(voice_id, expires, signature)
    return False
