from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR

logger = logging.getLogger(__name__)


def _error_payload(
    *,
    error: str,
    type_: str,
    code: str | None = None,
    details: Any | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": error, "code": code, "type": type_}
    if details is not None:
        payload["details"] = details
    return payload


class AlfredException(Exception):
    """Base exception for Alfred.

    Note: these exceptions are meant to be raised from inside request handlers or
    service functions invoked by request handlers, so FastAPI can translate them
    via registered exception handlers.
    """

    status_code: int = 400
    default_code: str | None = None

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: Any | None = None,
    ) -> None:
        self.message = message
        self.code = code if code is not None else self.default_code
        self.status_code = status_code if status_code is not None else self.status_code
        self.details = details
        super().__init__(message)


class ConfigurationError(AlfredException):
    """Raised when configuration is invalid (server-side)."""

    status_code = 500
    default_code = "configuration_error"


class ServiceUnavailableError(AlfredException):
    """Raised when an upstream dependency is unavailable."""

    status_code = 503
    default_code = "service_unavailable"


class RateLimitError(AlfredException):
    """Raised when a rate limit is exceeded."""

    status_code = 429
    default_code = "rate_limited"


def register_exception_handlers(app: FastAPI) -> None:
    """Register Alfred's exception handlers on a FastAPI app."""

    @app.exception_handler(AlfredException)
    async def _alfred_exception_handler(_request: Request, exc: AlfredException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                error=exc.message,
                code=exc.code,
                type_=exc.__class__.__name__,
                details=exc.details,
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_payload(
                error="Validation error",
                code="validation_error",
                type_=exc.__class__.__name__,
                details=exc.errors(),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        detail = getattr(exc, "detail", None)
        if isinstance(detail, str):
            error = detail
            details = None
        else:
            error = "Request failed"
            details = detail
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(
                error=error,
                code="http_exception",
                type_=exc.__class__.__name__,
                details=details,
            ),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_payload(
                error="Internal server error",
                code="internal_error",
                type_="InternalServerError",
            ),
        )
