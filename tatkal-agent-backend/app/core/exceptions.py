"""
Centralized exception definitions and FastAPI exception handlers.

All public-facing error responses follow a consistent structure.
Internal details (stack traces, file paths, secrets) are never exposed to clients.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# ── Custom Exception Hierarchy ───────────────────────────────────

class AppException(Exception):
    """Base exception for application-specific errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ResourceNotFoundError(AppException):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", identifier: str | None = None) -> None:
        msg = f"{resource} not found"
        if identifier:
            msg += f": {identifier}"
        super().__init__(
            message=msg,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ResourceConflictError(AppException):
    """Raised on duplicate or conflicting resource creation."""

    def __init__(self, message: str = "Resource conflict") -> None:
        super().__init__(
            message=message,
            code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class ServiceUnavailableError(AppException):
    """Raised when a required service or integration is unavailable."""

    def __init__(self, service: str = "Service") -> None:
        super().__init__(
            message=f"{service} is currently unavailable",
            code="SERVICE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class IntegrationNotRegisteredError(AppException):
    """Raised when a required integration adapter has not been registered."""

    def __init__(self, integration_name: str) -> None:
        super().__init__(
            message=f"Integration '{integration_name}' is not registered",
            code="INTEGRATION_NOT_REGISTERED",
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
        )


# ── Error response builder ──────────────────────────────────────

def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    error_dict: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        error_dict.update(details)
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": error_dict,
        },
    )


# ── Exception handler registration ──────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers to the FastAPI application."""

    from app.agent.recovery.circuit_breaker import CircuitBreakerOpenError
    from app.agent.recovery.errors import BaseRecoveryError, ErrorCategory

    @app.exception_handler(BaseRecoveryError)
    async def handle_recovery_exception(_request: Request, exc: BaseRecoveryError) -> JSONResponse:
        logger.warning("RecoveryException [%s]: %s", exc.error_code, exc.message)
        details: dict[str, Any] = {
            "category": exc.category.value,
            "recoverable": exc.recoverable,
            "requires_human": exc.requires_human,
            "is_uncertain_outcome": exc.is_uncertain_outcome,
        }
        if exc.retry_after_seconds is not None:
            details["retry_after_seconds"] = exc.retry_after_seconds
        if exc.retry_guidance:
            details["retry_guidance"] = exc.retry_guidance

        if isinstance(exc, CircuitBreakerOpenError):
            details["circuit_breaker_open"] = True
            details["breaker_name"] = exc.breaker_name
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif exc.category == ErrorCategory.VALIDATION:
            status_code = status.HTTP_400_BAD_REQUEST
        elif exc.category == ErrorCategory.AUTHENTICATION:
            status_code = status.HTTP_401_UNAUTHORIZED
        elif exc.category == ErrorCategory.RATE_LIMIT:
            status_code = status.HTTP_429_TOO_MANY_REQUESTS
        elif exc.category == ErrorCategory.TIMEOUT:
            status_code = status.HTTP_504_GATEWAY_TIMEOUT
        elif exc.category == ErrorCategory.SERVICE_UNAVAILABLE:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return _error_response(status_code, exc.error_code, exc.message, details=details)

    @app.exception_handler(AppException)
    async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        logger.warning("AppException [%s]: %s", exc.code, exc.message)
        return _error_response(exc.status_code, exc.code, exc.message, details=exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Summarise validation issues without leaking internal schema details
        error_count = len(exc.errors())
        logger.info("Validation error with %d issue(s)", error_count)
        status_422 = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        return _error_response(
            status_422,
            "VALIDATION_ERROR",
            f"Request validation failed with {error_count} error(s). "
            "Check the request body and query parameters.",
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(
        _request: Request, exc: Exception
    ) -> JSONResponse:
        # Log the full traceback internally but return a safe message to the client
        logger.exception("Unhandled exception: %s", exc)
        return _error_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected internal error occurred. Please try again later.",
        )
