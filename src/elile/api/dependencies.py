"""FastAPI dependencies for API endpoints."""

from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from elile.core.audit import AuditLogger
from elile.core.context import RequestContext, get_current_context
from elile.db.dependencies import (
    TenantDatabaseSession,
    get_db,
    get_tenant_db,
    get_validated_tenant_id,
)

# Re-export database dependencies for convenience
__all__ = [
    "get_db",
    "get_validated_tenant_id",
    "get_tenant_db",
    "TenantDatabaseSession",
    "get_request_context",
    "get_audit_logger",
    "get_request_id",
]


def get_request_context() -> RequestContext:
    """Get the current request context from ContextVar.

    This dependency requires RequestContextMiddleware to be active.

    Returns:
        The current RequestContext

    Raises:
        ContextNotSetError: If middleware hasn't set the context
    """
    return get_current_context()


def get_audit_logger(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuditLogger:
    """Get an AuditLogger instance with the request's database session.

    Args:
        db: Database session from dependency injection

    Returns:
        AuditLogger configured with the session
    """
    return AuditLogger(db)


def get_request_id(request: Request) -> str:
    """Get the request ID from request state.

    The request ID is set by RequestContextMiddleware.

    Args:
        request: FastAPI request object

    Returns:
        Request ID as string (UUIDv7)
    """
    return str(getattr(request.state, "request_id", "unknown"))
