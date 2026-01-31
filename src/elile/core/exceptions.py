"""Core exceptions for Elile compliance and request context."""

from datetime import datetime
from uuid import UUID

from elile.utils.exceptions import ElileError


class ContextNotSetError(ElileError):
    """Raised when attempting to access request context that is not set.

    This error indicates a programming error - operations requiring context
    are being called outside of a request_context() context manager.
    """

    def __init__(self, message: str = "Request context is not set"):
        super().__init__(message)


class ComplianceError(ElileError):
    """Raised when an operation violates compliance rules.

    Attributes:
        check_type: The type of check that was attempted (e.g., "criminal_records")
        locale: The jurisdiction where compliance rules apply (e.g., "US", "EU")
    """

    def __init__(
        self,
        message: str,
        check_type: str,
        locale: str,
    ):
        super().__init__(message)
        self.check_type = check_type
        self.locale = locale

    def __str__(self) -> str:
        return f"ComplianceError({self.locale}, {self.check_type}): {self.args[0]}"


class BudgetExceededError(ElileError):
    """Raised when an operation would exceed the request's cost budget.

    Attributes:
        cost: The cost of the attempted operation
        budget_limit: The maximum budget allowed for this request
        accumulated: The total cost already accumulated before this operation
    """

    def __init__(
        self,
        message: str,
        cost: float,
        budget_limit: float,
        accumulated: float,
    ):
        super().__init__(message)
        self.cost = cost
        self.budget_limit = budget_limit
        self.accumulated = accumulated

    def __str__(self) -> str:
        return (
            f"BudgetExceededError: {self.args[0]} "
            f"(cost={self.cost}, limit={self.budget_limit}, accumulated={self.accumulated})"
        )


class ConsentExpiredError(ElileError):
    """Raised when consent has expired for a data access operation.

    Attributes:
        consent_token: The identifier of the expired consent
        expiry: When the consent expired
    """

    def __init__(
        self,
        message: str,
        consent_token: UUID | str,
        expiry: datetime,
    ):
        super().__init__(message)
        self.consent_token = consent_token
        self.expiry = expiry

    def __str__(self) -> str:
        return f"ConsentExpiredError: {self.args[0]} (token={self.consent_token}, expired={self.expiry})"


class ConsentScopeError(ElileError):
    """Raised when attempting to access data outside the granted consent scope.

    Attributes:
        required_scope: The scope required for the operation (e.g., "criminal_records")
        granted_scope: The scopes that were granted in the consent
    """

    def __init__(
        self,
        message: str,
        required_scope: str,
        granted_scope: set[str],
    ):
        super().__init__(message)
        self.required_scope = required_scope
        self.granted_scope = granted_scope

    def __str__(self) -> str:
        return (
            f"ConsentScopeError: {self.args[0]} "
            f"(required={self.required_scope}, granted={sorted(self.granted_scope)})"
        )


class TenantNotFoundError(ElileError):
    """Raised when a tenant does not exist.

    Attributes:
        tenant_id: The identifier of the tenant that was not found
    """

    def __init__(self, tenant_id: UUID | str):
        super().__init__(f"Tenant not found: {tenant_id}")
        self.tenant_id = tenant_id

    def __str__(self) -> str:
        return f"TenantNotFoundError: {self.args[0]}"


class TenantInactiveError(ElileError):
    """Raised when attempting to use a deactivated tenant.

    Attributes:
        tenant_id: The identifier of the inactive tenant
    """

    def __init__(self, tenant_id: UUID | str):
        super().__init__(f"Tenant is inactive: {tenant_id}")
        self.tenant_id = tenant_id

    def __str__(self) -> str:
        return f"TenantInactiveError: {self.args[0]}"


class TenantAccessDeniedError(ElileError):
    """Raised when access to a tenant resource is denied.

    Attributes:
        tenant_id: The identifier of the tenant
        resource: The resource that access was denied to
    """

    def __init__(self, tenant_id: UUID | str, resource: str):
        super().__init__(f"Access denied to {resource} for tenant {tenant_id}")
        self.tenant_id = tenant_id
        self.resource = resource

    def __str__(self) -> str:
        return f"TenantAccessDeniedError: {self.args[0]}"


class AuthenticationError(ElileError):
    """Raised when authentication fails.

    This exception is used for API authentication failures such as
    missing or invalid API keys, expired tokens, or invalid credentials.

    Attributes:
        reason: The specific reason authentication failed
    """

    def __init__(self, reason: str = "Authentication failed"):
        super().__init__(reason)
        self.reason = reason

    def __str__(self) -> str:
        return f"AuthenticationError: {self.args[0]}"
