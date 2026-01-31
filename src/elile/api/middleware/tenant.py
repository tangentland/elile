"""Tenant validation middleware."""

from typing import Callable
from uuid import UUID

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from elile.core.exceptions import TenantInactiveError, TenantNotFoundError


# Paths that don't require tenant validation
SKIP_TENANT_PATHS = {
    "/health",
    "/health/db",
    "/health/ready",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class TenantValidationMiddleware(BaseHTTPMiddleware):
    """Middleware that validates X-Tenant-ID header.

    Extracts and validates the tenant ID, ensuring the tenant exists
    and is active before allowing the request to proceed.

    Sets:
        request.state.tenant_id: UUID of the validated tenant
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """Process request and validate tenant."""
        # Skip tenant validation for allowed paths
        if self._should_skip_validation(request.url.path):
            return await call_next(request)

        # Extract tenant ID header
        tenant_header = request.headers.get("X-Tenant-ID")
        if not tenant_header:
            return self._bad_request("Missing X-Tenant-ID header")

        # Parse UUID
        try:
            tenant_id = UUID(tenant_header)
        except ValueError:
            return self._bad_request(f"Invalid X-Tenant-ID format: must be a valid UUID")

        # Validate tenant exists and is active
        try:
            await self._validate_tenant(tenant_id)
        except TenantNotFoundError as e:
            return self._not_found(str(e), tenant_id)
        except TenantInactiveError as e:
            return self._forbidden(str(e), tenant_id)

        # Set tenant ID on request state
        request.state.tenant_id = tenant_id

        return await call_next(request)

    def _should_skip_validation(self, path: str) -> bool:
        """Check if path should skip tenant validation."""
        return path in SKIP_TENANT_PATHS or path.startswith(("/docs", "/redoc"))

    async def _validate_tenant(self, tenant_id: UUID) -> None:
        """Validate tenant exists and is active.

        Args:
            tenant_id: The tenant ID to validate

        Raises:
            TenantNotFoundError: If tenant doesn't exist
            TenantInactiveError: If tenant is deactivated
        """
        from elile.core.tenant import TenantService
        from elile.db.config import get_async_session

        # Get a database session for validation
        async with get_async_session() as session:
            service = TenantService(session)
            await service.validate_tenant_active(tenant_id)

    def _bad_request(self, message: str) -> JSONResponse:
        """Create a 400 bad request response."""
        from datetime import UTC, datetime
        from elile.api.schemas.errors import APIError, ErrorCode

        error = APIError(
            error_code=ErrorCode.INVALID_REQUEST.value,
            message=message,
            details=None,
            request_id=self._get_request_id_or_default(),
            timestamp=datetime.now(UTC),
        )

        return JSONResponse(
            status_code=400,
            content=error.model_dump(mode="json"),
        )

    def _not_found(self, message: str, tenant_id: UUID) -> JSONResponse:
        """Create a 404 not found response."""
        from datetime import UTC, datetime
        from elile.api.schemas.errors import APIError, ErrorCode

        error = APIError(
            error_code=ErrorCode.TENANT_NOT_FOUND.value,
            message=message,
            details={"tenant_id": str(tenant_id)},
            request_id=self._get_request_id_or_default(),
            timestamp=datetime.now(UTC),
        )

        return JSONResponse(
            status_code=404,
            content=error.model_dump(mode="json"),
        )

    def _forbidden(self, message: str, tenant_id: UUID) -> JSONResponse:
        """Create a 403 forbidden response."""
        from datetime import UTC, datetime
        from elile.api.schemas.errors import APIError, ErrorCode

        error = APIError(
            error_code=ErrorCode.TENANT_INACTIVE.value,
            message=message,
            details={"tenant_id": str(tenant_id)},
            request_id=self._get_request_id_or_default(),
            timestamp=datetime.now(UTC),
        )

        return JSONResponse(
            status_code=403,
            content=error.model_dump(mode="json"),
        )

    def _get_request_id_or_default(self) -> str:
        """Get request ID or return default."""
        return "unknown"
