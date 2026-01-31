"""Provider types and enums for Elile data provider abstraction.

This module defines the core types used throughout the provider system:
- Enums for categorizing providers and costs
- Result models for provider responses
- Health status models for availability tracking
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from elile.compliance.types import CheckType, Locale


class DataSourceCategory(str, Enum):
    """Category of data source provider.

    Determines availability by service tier:
    - CORE: Available in both Standard and Enhanced tiers
    - PREMIUM: Available only in Enhanced tier
    """

    CORE = "core"
    PREMIUM = "premium"


class CostTier(str, Enum):
    """Cost tier for billing and optimization.

    Used to select between providers when multiple
    can satisfy the same check type.
    """

    FREE = "free"  # No per-query cost (e.g., public registries)
    LOW = "low"  # < $1 per query
    MEDIUM = "medium"  # $1-10 per query
    HIGH = "high"  # $10-50 per query
    PREMIUM = "premium"  # > $50 per query (e.g., comprehensive reports)


class ProviderStatus(str, Enum):
    """Health status of a provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"  # Partially available (e.g., high latency)
    UNHEALTHY = "unhealthy"  # Not responding
    MAINTENANCE = "maintenance"  # Planned downtime


class ProviderHealth(BaseModel):
    """Health status of a data provider.

    Reported by periodic health checks and individual request failures.
    """

    provider_id: str
    status: ProviderStatus
    last_check: datetime
    latency_ms: int | None = None
    error_message: str | None = None
    consecutive_failures: int = 0
    success_rate_24h: float = Field(default=1.0, ge=0.0, le=1.0)

    @property
    def is_available(self) -> bool:
        """Check if provider is available for requests."""
        return self.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)


class ProviderResult(BaseModel):
    """Result from a provider check execution.

    Contains both the normalized data and metadata about the query.
    """

    provider_id: str
    check_type: CheckType
    locale: Locale
    success: bool

    # Data (if successful)
    normalized_data: dict = Field(default_factory=dict)
    raw_response: bytes | None = None

    # Error info (if failed)
    error_code: str | None = None
    error_message: str | None = None
    retryable: bool = False

    # Metadata
    query_id: UUID | None = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: int = 0

    # Cost
    cost_incurred: Decimal = Field(default=Decimal("0.00"))
    cost_currency: str = "USD"

    @property
    def is_success(self) -> bool:
        """Check if the result is successful."""
        return self.success and self.error_code is None


class ProviderCapability(BaseModel):
    """Capability of a provider for a specific check type.

    Describes what a provider can do for a particular check type.
    """

    check_type: CheckType
    supported_locales: list[Locale] = Field(default_factory=list)
    cost_tier: CostTier = CostTier.MEDIUM
    average_latency_ms: int = 5000
    reliability_score: float = Field(default=0.99, ge=0.0, le=1.0)

    def supports_locale(self, locale: Locale) -> bool:
        """Check if this capability supports a locale."""
        if not self.supported_locales:
            return True  # Empty list means all locales supported
        return locale in self.supported_locales


class ProviderInfo(BaseModel):
    """Static information about a provider.

    Used for provider registration and discovery.
    """

    provider_id: str
    name: str
    description: str = ""
    category: DataSourceCategory
    capabilities: list[ProviderCapability] = Field(default_factory=list)
    base_url: str | None = None
    rate_limit_per_minute: int = 60
    rate_limit_per_day: int | None = None
    requires_api_key: bool = True
    supports_batch: bool = False

    @property
    def supported_checks(self) -> list[CheckType]:
        """Get list of all supported check types."""
        return [cap.check_type for cap in self.capabilities]

    @property
    def supported_locales(self) -> list[Locale]:
        """Get list of all supported locales (union across capabilities)."""
        all_locales = set()
        for cap in self.capabilities:
            all_locales.update(cap.supported_locales)
        return list(all_locales) if all_locales else list(Locale)

    def get_capability(self, check_type: CheckType) -> ProviderCapability | None:
        """Get capability for a specific check type."""
        for cap in self.capabilities:
            if cap.check_type == check_type:
                return cap
        return None

    def supports_check(self, check_type: CheckType, locale: Locale | None = None) -> bool:
        """Check if provider supports a check type, optionally for a specific locale."""
        cap = self.get_capability(check_type)
        if cap is None:
            return False
        if locale is None:
            return True
        return cap.supports_locale(locale)


class ProviderQuery(BaseModel):
    """Query to be executed against a provider.

    Contains all information needed to execute a check.
    """

    query_id: UUID
    provider_id: str
    check_type: CheckType
    locale: Locale

    # Subject identifiers (will be passed to provider)
    subject_data: dict = Field(default_factory=dict)

    # Context
    tenant_id: UUID | None = None
    correlation_id: UUID | None = None
    screening_id: UUID | None = None

    # Options
    timeout_ms: int = 30000
    retry_count: int = 0
    max_retries: int = 3


class ProviderQueryCost(BaseModel):
    """Cost tracking for a provider query.

    Used for billing and optimization.
    """

    query_id: UUID
    provider_id: str
    check_type: CheckType

    # Cost breakdown
    base_cost: Decimal = Field(default=Decimal("0.00"))
    volume_discount: Decimal = Field(default=Decimal("0.00"))
    final_cost: Decimal = Field(default=Decimal("0.00"))
    currency: str = "USD"

    # Attribution
    screening_id: UUID | None = None
    tenant_id: UUID | None = None

    # Cache impact
    cache_hit: bool = False
    cache_saved: Decimal | None = None  # Cost that would have been incurred

    # Timestamps
    incurred_at: datetime = Field(default_factory=datetime.utcnow)
