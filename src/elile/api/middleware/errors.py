"""Error handling middleware for mapping exceptions to HTTP responses."""

from datetime import UTC, datetime
from typing import Callable
from uuid import UUID

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from elile.api.schemas.errors import APIError, ErrorCode
from elile.core.exceptions import (
    AuthenticationError,
    BudgetExceededError,
    ComplianceError,
    ConsentExpiredError,
    ConsentScopeError,
    ContextNotSetError,
    TenantAccessDeniedError,
    TenantInactiveError,
    TenantNotFoundError,
)


# Exception to HTTP status/error code mapping
# Format: Exception -> (status_code, error_code)
EXCEPTION_MAP: dict[type[Exception], tuple[int, str]] = {
    AuthenticationError: (401, ErrorCode.UNAUTHORIZED.value),
    TenantNotFoundError: (404, ErrorCode.TENANT_NOT_FOUND.value),
    TenantInactiveError: (403, ErrorCode.TENANT_INACTIVE.value),
    TenantAccessDeniedError: (403, ErrorCode.TENANT_ACCESS_DENIED.value),
    ComplianceError: (403, ErrorCode.COMPLIANCE_BLOCKED.value),
    BudgetExceededError: (402, ErrorCode.BUDGET_EXCEEDED.value),
    ConsentExpiredError: (403, ErrorCode.CONSENT_EXPIRED.value),
    ConsentScopeError: (403, ErrorCode.CONSENT_SCOPE_ERROR.value),
    ContextNotSetError: (500, ErrorCode.INTERNAL_ERROR.value),
    ValidationError: (422, ErrorCode.VALIDATION_ERROR.value),
}


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware that catches exceptions and returns standardized error responses.

    Maps domain exceptions to appropriate HTTP status codes and formats
    all errors using the APIError schema.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and handle any exceptions."""
        try:
            return await call_next(request)
        except Exception as exc:
            return self._handle_exception(request, exc)

    def _handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Convert exception to JSON error response."""
        request_id = self._get_request_id(request)
        status_code, error_code, message, details = self._map_exception(exc)

        error = APIError(
            error_code=error_code,
            message=message,
            details=details,
            request_id=request_id,
            timestamp=datetime.now(UTC),
        )

        return JSONResponse(
            status_code=status_code,
            content=error.model_dump(mode="json"),
            headers={"X-Request-ID": request_id},
        )

    def _get_request_id(self, request: Request) -> str:
        """Extract request ID from state or generate placeholder."""
        if hasattr(request.state, "request_id"):
            rid = request.state.request_id
            return str(rid) if isinstance(rid, UUID) else rid
        return "unknown"

    def _map_exception(
        self, exc: Exception
    ) -> tuple[int, str, str, dict | None]:
        """Map exception to (status_code, error_code, message, details)."""
        # Authentication errors
        if isinstance(exc, AuthenticationError):
            return (
                401,
                ErrorCode.UNAUTHORIZED.value,
                str(exc),
                None,
            )

        # Tenant errors
        if isinstance(exc, TenantNotFoundError):
            return (
                404,
                ErrorCode.TENANT_NOT_FOUND.value,
                str(exc),
                {"tenant_id": str(exc.tenant_id)},
            )

        if isinstance(exc, TenantInactiveError):
            return (
                403,
                ErrorCode.TENANT_INACTIVE.value,
                str(exc),
                {"tenant_id": str(exc.tenant_id)},
            )

        if isinstance(exc, TenantAccessDeniedError):
            return (
                403,
                ErrorCode.TENANT_ACCESS_DENIED.value,
                str(exc),
                {"tenant_id": str(exc.tenant_id), "resource": exc.resource},
            )

        # Compliance errors
        if isinstance(exc, ComplianceError):
            return (
                403,
                ErrorCode.COMPLIANCE_BLOCKED.value,
                str(exc),
                {"check_type": exc.check_type, "locale": exc.locale},
            )

        if isinstance(exc, ConsentExpiredError):
            return (
                403,
                ErrorCode.CONSENT_EXPIRED.value,
                str(exc),
                {"consent_token": str(exc.consent_token)},
            )

        if isinstance(exc, ConsentScopeError):
            return (
                403,
                ErrorCode.CONSENT_SCOPE_ERROR.value,
                str(exc),
                {
                    "required_scope": exc.required_scope,
                    "granted_scope": list(exc.granted_scope),
                },
            )

        # Budget errors
        if isinstance(exc, BudgetExceededError):
            return (
                402,
                ErrorCode.BUDGET_EXCEEDED.value,
                str(exc),
                {
                    "cost": exc.cost,
                    "budget_limit": exc.budget_limit,
                    "accumulated": exc.accumulated,
                },
            )

        # Validation errors (Pydantic)
        if isinstance(exc, ValidationError):
            return (
                422,
                ErrorCode.VALIDATION_ERROR.value,
                "Request validation failed",
                {"errors": exc.errors()},
            )

        # Context errors (internal)
        if isinstance(exc, ContextNotSetError):
            return (
                500,
                ErrorCode.INTERNAL_ERROR.value,
                "Internal server error: context not initialized",
                None,
            )

        # Generic exceptions
        return (
            500,
            ErrorCode.INTERNAL_ERROR.value,
            "Internal server error",
            {"type": type(exc).__name__} if self._is_debug() else None,
        )

    def _is_debug(self) -> bool:
        """Check if debug mode is enabled."""
        try:
            from elile.config.settings import get_settings
            return get_settings().DEBUG
        except Exception:
            return False
