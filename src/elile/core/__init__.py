"""Core services and utilities for Elile."""

from .audit import AuditLogger, audit_operation, audit_operation_v2
from .context import (
    ActorType,
    CacheScope,
    RequestContext,
    create_context,
    get_current_context,
    get_current_context_or_none,
    request_context,
    reset_context,
    set_context,
)
from .exceptions import (
    BudgetExceededError,
    ComplianceError,
    ConsentExpiredError,
    ConsentScopeError,
    ContextNotSetError,
    TenantAccessDeniedError,
    TenantInactiveError,
    TenantNotFoundError,
)
from .tenant import TenantService

__all__ = [
    # Audit
    "AuditLogger",
    "audit_operation",
    "audit_operation_v2",
    # Context
    "ActorType",
    "CacheScope",
    "RequestContext",
    "create_context",
    "get_current_context",
    "get_current_context_or_none",
    "request_context",
    "reset_context",
    "set_context",
    # Exceptions
    "BudgetExceededError",
    "ComplianceError",
    "ConsentExpiredError",
    "ConsentScopeError",
    "ContextNotSetError",
    "TenantAccessDeniedError",
    "TenantInactiveError",
    "TenantNotFoundError",
    # Tenant
    "TenantService",
]
