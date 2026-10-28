"""Exception handlers so every error uses `{detail, code, hint, errors}`."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from phemius.errors import PhemiusError

log = structlog.get_logger(__name__)

HTTP_ERROR_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
}


def error_body(
    detail: str,
    code: str,
    hint: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"detail": detail, "code": code}
    if hint:
        body["hint"] = hint
    if errors:
        body["errors"] = errors
    return body


async def _handle_phemius_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, PhemiusError)
    errors = [
        {"field": field, "message": message}
        for field, message in error.field_errors.items()
    ]
    log.info("request_failed", path=request.url.path, code=error.code)
    return JSONResponse(
        error_body(error.message, error.code, error.hint, errors),
        status_code=error.status_code,
    )


async def _handle_validation_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, RequestValidationError)
    errors = [
        {
            "field": ".".join(str(part) for part in item["loc"][1:]) or "body",
            "message": item["msg"],
        }
        for item in error.errors()
    ]
    return JSONResponse(
        error_body("Invalid request", "validation_error", errors=errors),
        status_code=422,
    )


async def _handle_http_error(request: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, HTTPException)
    code = HTTP_ERROR_CODES.get(error.status_code, "http_error")
    return JSONResponse(
        error_body(str(error.detail), code),
        status_code=error.status_code,
        headers=error.headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(PhemiusError, _handle_phemius_error)
    app.add_exception_handler(RequestValidationError, _handle_validation_error)
    app.add_exception_handler(HTTPException, _handle_http_error)
