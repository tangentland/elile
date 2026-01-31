"""Error handling utilities with audit event generation.

Provides decorators and utilities for structured error handling with
automatic audit logging for compliance tracking.

Usage:
    from elile.core.error_handling import handle_errors, ErrorHandler

    # Decorator for automatic error handling and audit logging
    @handle_errors(audit=True)
    async def my_operation(db: AsyncSession, ctx: RequestContext):
        # ... operation that may raise exceptions
        pass

    # Manual error handling with audit
    async with ErrorHandler(db, ctx) as handler:
        result = await risky_operation()
        if not result:
            handler.record_error("operation_failed", {"reason": "no result"})
"""

import functools
import logging
import traceback
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any, Callable, ParamSpec, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.context import RequestContext, get_current_context_or_none
from elile.db.models.audit import AuditEventType, AuditSeverity
from elile.utils.exceptions import ElileError


logger = logging.getLogger("elile.errors")

P = ParamSpec("P")
T = TypeVar("T")


class ErrorRecord:
    """Record of an error that occurred during an operation.

    Captures error details for audit logging and debugging.

    Attributes:
        error_code: Machine-readable error code
        message: Human-readable error message
        exception: The original exception (if any)
        details: Additional error context
        severity: Error severity level
        timestamp: When the error occurred
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        exception: Exception | None = None,
        details: dict | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ):
        self.error_code = error_code
        self.message = message
        self.exception = exception
        self.details = details or {}
        self.severity = severity
        self.timestamp = datetime.now(UTC)

        # Capture stack trace if exception provided
        if exception:
            self.details["exception_type"] = type(exception).__name__
            self.details["exception_message"] = str(exception)
            self.details["traceback"] = traceback.format_exc()

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
        }


class ErrorHandler:
    """Context manager for collecting and logging errors during operations.

    Provides a structured way to handle multiple errors within an operation,
    with automatic audit logging when exiting the context.

    Example:
        async with ErrorHandler(db, ctx, resource_type="screening") as handler:
            try:
                await risky_operation()
            except SomeError as e:
                handler.record_error("operation_failed", str(e), exception=e)

            # Continue processing other items
            for item in items:
                try:
                    await process_item(item)
                except ItemError as e:
                    handler.record_error("item_failed", str(e), details={"item_id": item.id})

        # All errors are logged as audit events on exit
    """

    def __init__(
        self,
        db: AsyncSession | None = None,
        ctx: RequestContext | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        log_to_audit: bool = True,
    ):
        """Initialize error handler.

        Args:
            db: Database session for audit logging (optional)
            ctx: Request context (optional, will try to get from ContextVar)
            resource_type: Type of resource being operated on
            resource_id: ID of specific resource
            log_to_audit: Whether to log errors to audit system
        """
        self.db = db
        self.ctx = ctx or get_current_context_or_none()
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.log_to_audit = log_to_audit
        self.errors: list[ErrorRecord] = []

    async def __aenter__(self) -> "ErrorHandler":
        """Enter context."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        """Exit context and log any recorded errors."""
        # If an unhandled exception occurred, record it
        if exc_val is not None:
            error_code = self._get_error_code(exc_val)
            self.record_error(error_code, str(exc_val), exception=exc_val)

        # Log all errors to audit system
        if self.errors and self.log_to_audit and self.db:
            await self._log_errors_to_audit()

        # Log to Python logging regardless
        for error in self.errors:
            self._log_error(error)

        # Don't suppress exceptions
        return False

    def record_error(
        self,
        error_code: str,
        message: str,
        exception: Exception | None = None,
        details: dict | None = None,
        severity: AuditSeverity = AuditSeverity.ERROR,
    ) -> ErrorRecord:
        """Record an error.

        Args:
            error_code: Machine-readable error code
            message: Human-readable message
            exception: The exception that caused the error
            details: Additional context
            severity: Error severity level

        Returns:
            The created ErrorRecord
        """
        record = ErrorRecord(
            error_code=error_code,
            message=message,
            exception=exception,
            details=details,
            severity=severity,
        )
        self.errors.append(record)
        return record

    def has_errors(self) -> bool:
        """Check if any errors were recorded."""
        return len(self.errors) > 0

    def get_errors(self) -> list[ErrorRecord]:
        """Get all recorded errors."""
        return self.errors.copy()

    def clear_errors(self) -> None:
        """Clear recorded errors."""
        self.errors.clear()

    def _get_error_code(self, exc: Exception) -> str:
        """Derive error code from exception type."""
        if isinstance(exc, ElileError):
            # Use class name in snake_case
            name = type(exc).__name__
            # Convert CamelCase to snake_case
            import re
            return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
        return "internal_error"

    def _log_error(self, error: ErrorRecord) -> None:
        """Log error to Python logging."""
        log_method = logger.error if error.severity == AuditSeverity.ERROR else logger.warning
        if error.severity == AuditSeverity.CRITICAL:
            log_method = logger.critical

        ctx_info = ""
        if self.ctx:
            ctx_info = f"[tenant={self.ctx.tenant_id}] [request={self.ctx.request_id}] "

        log_method(
            f"{ctx_info}{error.error_code}: {error.message}",
            extra={
                "error_code": error.error_code,
                "details": error.details,
                "resource_type": self.resource_type,
                "resource_id": self.resource_id,
            },
        )

    async def _log_errors_to_audit(self) -> None:
        """Log errors to audit system."""
        if not self.db or not self.errors:
            return

        try:
            from elile.core.audit import AuditLogger

            audit_logger = AuditLogger(self.db)

            for error in self.errors:
                await audit_logger.log_event(
                    event_type=AuditEventType.API_ERROR,
                    event_data=error.to_dict(),
                    severity=error.severity,
                    tenant_id=self.ctx.tenant_id if self.ctx else None,
                    user_id=self.ctx.actor_id if self.ctx else None,
                    correlation_id=self.ctx.correlation_id if self.ctx else None,
                    resource_type=self.resource_type,
                    resource_id=self.resource_id,
                )

            await self.db.commit()
        except Exception as e:
            # Don't fail the main operation if audit logging fails
            logger.warning(f"Failed to log error to audit: {e}")


def handle_errors(
    audit: bool = True,
    resource_type: str | None = None,
    reraise: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorator for automatic error handling with audit logging.

    Wraps an async function to catch exceptions, log them to the audit system,
    and optionally re-raise them.

    Args:
        audit: Whether to log errors to audit system
        resource_type: Type of resource being operated on
        reraise: Whether to re-raise exceptions after logging

    Returns:
        Decorated function

    Example:
        @handle_errors(audit=True, resource_type="screening")
        async def perform_screening(db: AsyncSession, subject_id: UUID):
            # ... screening logic
            pass
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Try to extract db session and context from arguments
            db = None
            ctx = get_current_context_or_none()

            for arg in args:
                if isinstance(arg, AsyncSession):
                    db = arg
                    break

            for value in kwargs.values():
                if isinstance(value, AsyncSession):
                    db = value
                    break

            async with ErrorHandler(
                db=db,
                ctx=ctx,
                resource_type=resource_type or func.__name__,
                log_to_audit=audit,
            ) as handler:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if reraise:
                        raise
                    # If not reraising, error is still recorded by __aexit__
                    return None  # type: ignore

        return wrapper  # type: ignore

    return decorator


@asynccontextmanager
async def error_context(
    db: AsyncSession | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    log_to_audit: bool = True,
):
    """Async context manager for error handling.

    Simpler alternative to ErrorHandler class.

    Example:
        async with error_context(db, resource_type="user") as handler:
            await risky_operation()
    """
    handler = ErrorHandler(
        db=db,
        resource_type=resource_type,
        resource_id=resource_id,
        log_to_audit=log_to_audit,
    )
    async with handler:
        yield handler
