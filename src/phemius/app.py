"""FastAPI app: routes, error handlers, startup and the static UI.

Run with `phemius serve` or `make run backend`. The UI in `static/` is
built from `frontend/` with `make build frontend`.
"""

import sys
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope

from phemius import __version__
from phemius.api import (
    access,
    audio,
    checks,
    docs,
    health,
    library,
    library_config,
    queue,
    request_guard,
    settings,
    stats,
)
from phemius.api.errors import register_exception_handlers
from phemius.config import Config, load_config
from phemius.logs import configure_logging
from phemius.services import access as access_service
from phemius.services import backup
from phemius.services.runner import start_runner
from phemius.services.voices import check_engine
from phemius.sources.folder import start_watcher
from phemius.store.database import init_database
from phemius.store.permissions import (
    create_private_dir,
    tighten_library_permissions,
)

STATIC_DIR = Path(__file__).parent / "static"

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    environment_config = load_config()
    configure_logging(environment_config.log_level)
    _tighten_library_permissions(
        environment_config.data_dir, environment_config.db_path
    )
    init_database(environment_config.db_path)
    config = load_config()
    create_private_dir(config.audio_dir)
    backup.remove_leftovers(config.data_dir)
    _prepare_access(app, config)
    runner = start_runner()
    observer = start_watcher(config.watch_dir) if config.watch_dir else None
    log.info(
        "phemius_started",
        version=__version__,
        data_dir=str(config.data_dir),
        access_mode=config.access_mode,
    )
    _warn_if_voice_engine_not_ready()
    yield
    if observer:
        observer.stop()
        observer.join()
    runner.stop()


def _prepare_access(app: FastAPI, config: Config) -> None:
    app.state.access_mode = config.access_mode
    app.state.is_token_required = access_service.is_token_required(config.access_mode)
    _show_new_token(access_service.prepare_access_token(config.access_mode))


def _show_new_token(token: str | None) -> None:
    # Printed, never logged: this is the one time the token is shown, so it
    # must reach the console even when the log level hides info messages.
    if token:
        print(
            f"Phemius access token (shown once, save it now): {token}",
            file=sys.stderr,
            flush=True,
        )


def _tighten_library_permissions(data_dir: Path, db_path: Path) -> None:
    tightened = tighten_library_permissions(data_dir, db_path)
    if tightened:
        log.warning(
            "library_permissions_tightened",
            paths=[str(path) for path in tightened],
            hint="Group and other access to the library was removed.",
        )


def _warn_if_voice_engine_not_ready() -> None:
    status = check_engine()
    if not status.is_ready:
        log.warning("voice_engine_not_ready", message=status.message, hint=status.hint)


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
    return response


class SinglePageApp(StaticFiles):
    """Serves the built UI, falling back to index.html for client-side routes."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # Unmatched /api paths must keep the JSON error shape instead of HTML.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404:
                raise
            return await super().get_response("index.html", scope)


def create_app(static_dir: Path = STATIC_DIR) -> FastAPI:
    app = FastAPI(title="Phemius", version=__version__, lifespan=lifespan)
    register_exception_handlers(app)
    # The last middleware added runs first, so rejected requests are logged too,
    # and a rebinding or cross-site request is refused before any token lookup.
    app.middleware("http")(access.require_access_token)
    app.middleware("http")(request_guard.guard_request)
    app.middleware("http")(log_requests)
    for module in (
        health,
        library_config,
        settings,
        docs,
        audio,
        queue,
        checks,
        stats,
        library,
        access,
    ):
        app.include_router(module.router)
    if static_dir.is_dir():
        app.mount("/", SinglePageApp(directory=static_dir), name="static")
    return app


app = create_app()
