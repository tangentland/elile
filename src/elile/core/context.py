"""Request context for async-safe multi-tenant operations.

This module provides request context propagation using Python's contextvars
for multi-tenant isolation, compliance enforcement, and audit trail integrity.

Usage:
    from elile.core.context import RequestContext, request_context, get_current_context

    # Create a context for a request
    ctx = create_context(
        tenant_id=tenant_uuid,
        actor_id=user_uuid,
        locale="US",
        permitted_checks={"identity", "employment", "education"},
    )

    # Use as context manager (sync or async)
    with request_context(ctx):
        # Context is automatically available
        current = get_current_context()
        current.assert_check_permitted("employment")

    # Or in async code
    async with request_context(ctx):
        await do_screening_work()
"""

from contextlib import contextmanager
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Self
from uuid import UUID, uuid7

from pydantic import BaseModel, Field, model_validator

from elile.agent.state import SearchDegree, ServiceTier
from elile.core.exceptions import (
    BudgetExceededError,
    ComplianceError,
    ConsentExpiredError,
    ConsentScopeError,
    ContextNotSetError,
)


class ActorType(str, Enum):
    """Type of actor performing the operation."""

    HUMAN = "human"  # Human user via UI or API
    SERVICE = "service"  # Internal service call
    SYSTEM = "system"  # System-initiated operation (e.g., scheduled job)


class CacheScope(str, Enum):
    """Scope for cache isolation."""

    SHARED = "shared"  # Cache can be shared across tenants (rare, for public data)
    TENANT_ISOLATED = "tenant_isolated"  # Cache is isolated per tenant (default)


class RequestContext(BaseModel):
    """Context for a single request/operation.

    This model carries all information needed for:
    - Multi-tenant isolation
    - Compliance enforcement (locale, permitted checks)
    - Consent validation
    - Audit trail correlation
    - Cost tracking
    - Cache scoping
    """

    # Identity
    request_id: UUID = Field(default_factory=uuid7)
    tenant_id: UUID
    actor_id: UUID
    actor_type: ActorType = ActorType.HUMAN

    # Compliance
    locale: str = "US"
    permitted_checks: set[str] = Field(default_factory=set)
    permitted_sources: set[str] = Field(default_factory=set)

    # Consent
    consent_token: UUID | None = None
    consent_scope: set[str] = Field(default_factory=set)
    consent_expiry: datetime | None = None

    # Service configuration
    service_tier: ServiceTier = ServiceTier.STANDARD
    investigation_degree: SearchDegree = SearchDegree.D1

    # Audit
    correlation_id: UUID = Field(default_factory=uuid7)
    initiated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Cost tracking (mutable)
    budget_limit: float | None = None
    cost_accumulated: float = 0.0

    # Cache
    cache_scope: CacheScope = CacheScope.TENANT_ISOLATED

    model_config = {"frozen": False}  # Allow cost_accumulated to be mutable

    @model_validator(mode="after")
    def validate_consent_consistency(self) -> Self:
        """Validate that consent fields are consistent."""
        if self.consent_token is not None:
            if not self.consent_scope:
                raise ValueError("consent_scope required when consent_token is set")
            if self.consent_expiry is None:
                raise ValueError("consent_expiry required when consent_token is set")
        return self

    def assert_check_permitted(self, check_type: str) -> None:
        """Assert that a check type is permitted for this request.

        Args:
            check_type: The type of check to verify (e.g., "criminal_records")

        Raises:
            ComplianceError: If the check is not permitted for this locale/configuration
        """
        if self.permitted_checks and check_type not in self.permitted_checks:
            raise ComplianceError(
                f"Check type '{check_type}' is not permitted for locale '{self.locale}'",
                check_type=check_type,
                locale=self.locale,
            )

    def assert_source_permitted(self, provider_id: str) -> None:
        """Assert that a data source is permitted for this request.

        Args:
            provider_id: The identifier of the data provider

        Raises:
            ComplianceError: If the source is not permitted for this locale/configuration
        """
        if self.permitted_sources and provider_id not in self.permitted_sources:
            raise ComplianceError(
                f"Data source '{provider_id}' is not permitted for locale '{self.locale}'",
                check_type=provider_id,
                locale=self.locale,
            )

    def assert_budget_available(self, cost: float) -> None:
        """Assert that the budget allows for an operation of the given cost.

        Args:
            cost: The cost of the proposed operation

        Raises:
            BudgetExceededError: If the operation would exceed the budget
        """
        if self.budget_limit is not None:
            new_total = self.cost_accumulated + cost
            if new_total > self.budget_limit:
                raise BudgetExceededError(
                    f"Operation cost {cost} would exceed budget (accumulated: {self.cost_accumulated}, limit: {self.budget_limit})",
                    cost=cost,
                    budget_limit=self.budget_limit,
                    accumulated=self.cost_accumulated,
                )

    def assert_consent_valid(self) -> None:
        """Assert that consent is currently valid.

        Raises:
            ConsentExpiredError: If consent has expired
        """
        if self.consent_token is not None and self.consent_expiry is not None:
            now = datetime.now(UTC)
            if now > self.consent_expiry:
                raise ConsentExpiredError(
                    "Consent has expired",
                    consent_token=self.consent_token,
                    expiry=self.consent_expiry,
                )

    def assert_consent_scope(self, data_type: str) -> None:
        """Assert that the granted consent covers the requested data type.

        Args:
            data_type: The type of data being accessed (e.g., "criminal_records")

        Raises:
            ConsentScopeError: If the data type is not in the granted scope
        """
        if self.consent_scope and data_type not in self.consent_scope:
            raise ConsentScopeError(
                f"Data type '{data_type}' is not in the granted consent scope",
                required_scope=data_type,
                granted_scope=self.consent_scope,
            )

    def record_cost(self, cost: float) -> None:
        """Record a cost against this request's budget.

        Call assert_budget_available() first if you need to fail before
        committing to an operation. This method unconditionally records
        the cost even if it exceeds the budget.

        Args:
            cost: The cost to record
        """
        self.cost_accumulated += cost

    def to_audit_dict(self) -> dict[str, Any]:
        """Convert context to a dictionary for audit logging.

        Returns:
            Dictionary with context fields suitable for audit event_data
        """
        return {
            "request_id": str(self.request_id),
            "tenant_id": str(self.tenant_id),
            "actor_id": str(self.actor_id),
            "actor_type": self.actor_type.value,
            "locale": self.locale,
            "service_tier": self.service_tier.value,
            "investigation_degree": self.investigation_degree.value,
            "correlation_id": str(self.correlation_id),
            "initiated_at": self.initiated_at.isoformat(),
            "consent_token": str(self.consent_token) if self.consent_token else None,
            "budget_limit": self.budget_limit,
            "cost_accumulated": self.cost_accumulated,
            "cache_scope": self.cache_scope.value,
        }


# =============================================================================
# Context Variable Management
# =============================================================================

_request_context: ContextVar[RequestContext | None] = ContextVar("request_context", default=None)


def get_current_context() -> RequestContext:
    """Get the current request context.

    Returns:
        The current RequestContext

    Raises:
        ContextNotSetError: If no context is set in the current execution context
    """
    ctx = _request_context.get()
    if ctx is None:
        raise ContextNotSetError(
            "No request context is set. Use request_context() context manager."
        )
    return ctx


def get_current_context_or_none() -> RequestContext | None:
    """Get the current request context, or None if not set.

    Use this when context is optional (e.g., system operations that may
    or may not have a request context).

    Returns:
        The current RequestContext, or None if not set
    """
    return _request_context.get()


def set_context(ctx: RequestContext) -> Token[RequestContext | None]:
    """Set the request context and return a token for restoration.

    This is a low-level API. Prefer using the request_context() context manager.

    Args:
        ctx: The context to set

    Returns:
        Token that can be used to restore the previous context
    """
    return _request_context.set(ctx)


def reset_context(token: Token[RequestContext | None]) -> None:
    """Reset the context to its previous value using a token.

    This is a low-level API. Prefer using the request_context() context manager.

    Args:
        token: Token returned from set_context()
    """
    _request_context.reset(token)


@contextmanager
def request_context(ctx: RequestContext):
    """Context manager for setting request context.

    This works for both sync and async code because contextvars are
    automatically propagated to async tasks.

    Args:
        ctx: The context to set for the duration of the block

    Yields:
        The context that was set

    Example:
        with request_context(ctx):
            # Context is available here
            current = get_current_context()
            current.assert_check_permitted("employment")

        # Context is restored after the block
    """
    token = set_context(ctx)
    try:
        yield ctx
    finally:
        reset_context(token)


def create_context(
    *,
    tenant_id: UUID,
    actor_id: UUID,
    actor_type: ActorType = ActorType.HUMAN,
    locale: str = "US",
    permitted_checks: set[str] | None = None,
    permitted_sources: set[str] | None = None,
    consent_token: UUID | None = None,
    consent_scope: set[str] | None = None,
    consent_expiry: datetime | None = None,
    service_tier: ServiceTier = ServiceTier.STANDARD,
    investigation_degree: SearchDegree = SearchDegree.D1,
    correlation_id: UUID | None = None,
    budget_limit: float | None = None,
    cache_scope: CacheScope = CacheScope.TENANT_ISOLATED,
) -> RequestContext:
    """Factory function to create a RequestContext with defaults.

    This is the preferred way to create a RequestContext as it handles
    default values and optional parameters cleanly.

    Args:
        tenant_id: Required tenant identifier
        actor_id: Required actor (user/service) identifier
        actor_type: Type of actor (default: HUMAN)
        locale: Jurisdiction for compliance (default: "US")
        permitted_checks: Set of allowed check types (empty = all allowed)
        permitted_sources: Set of allowed data sources (empty = all allowed)
        consent_token: Optional consent identifier
        consent_scope: Required if consent_token is set
        consent_expiry: Required if consent_token is set
        service_tier: Service tier level (default: STANDARD)
        investigation_degree: Search depth (default: D1)
        correlation_id: Optional correlation ID (auto-generated if not provided)
        budget_limit: Optional cost budget
        cache_scope: Cache isolation scope (default: TENANT_ISOLATED)

    Returns:
        A new RequestContext instance
    """
    return RequestContext(
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_type=actor_type,
        locale=locale,
        permitted_checks=permitted_checks or set(),
        permitted_sources=permitted_sources or set(),
        consent_token=consent_token,
        consent_scope=consent_scope or set(),
        consent_expiry=consent_expiry,
        service_tier=service_tier,
        investigation_degree=investigation_degree,
        correlation_id=correlation_id or uuid7(),
        budget_limit=budget_limit,
        cache_scope=cache_scope,
    )
