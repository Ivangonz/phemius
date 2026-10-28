"""FastAPI app: routes, error handlers, startup and the static UI.

Run with `make run` (uvicorn phemius.app:app).
"""

import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles

from phemius import __version__
from phemius.api import audio, docs, health, library_config
from phemius.api.errors import register_exception_handlers
from phemius.config import load_config
from phemius.logs import configure_logging
from phemius.services.voices import check_engine
from phemius.sources.folder import start_watcher
from phemius.store.database import init_database

STATIC_DIR = Path(__file__).parent / "static"

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config()
    configure_logging(config.log_level)
    init_database(config.db_path)
    config.audio_dir.mkdir(parents=True, exist_ok=True)
    observer = start_watcher(config.watch_dir) if config.watch_dir else None
    log.info("phemius_started", version=__version__, data_dir=str(config.data_dir))
    _warn_if_voice_engine_not_ready()
    yield
    if observer:
        observer.stop()
        observer.join()


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


def create_app() -> FastAPI:
    app = FastAPI(title="Phemius", version=__version__, lifespan=lifespan)
    register_exception_handlers(app)
    app.middleware("http")(log_requests)
    for module in (health, library_config, docs, audio):
        app.include_router(module.router)
    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
