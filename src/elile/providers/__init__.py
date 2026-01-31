"""Data provider abstraction package for Elile.

This package provides the interface and infrastructure for integrating
external data sources (background check providers, court systems,
credit bureaus, etc.) into the Elile platform.

Usage:
    from elile.providers import (
        DataProvider,
        BaseDataProvider,
        ProviderRegistry,
        get_provider_registry,
    )

    # Register a provider
    registry = get_provider_registry()
    registry.register(my_provider)

    # Get provider for a check
    provider = registry.get_provider_for_check(
        check_type=CheckType.CRIMINAL_NATIONAL,
        locale=Locale.US,
    )

    # Execute check
    result = await provider.execute_check(
        check_type=CheckType.CRIMINAL_NATIONAL,
        subject=identifiers,
        locale=Locale.US,
    )

Provider Implementation:
    from elile.providers import BaseDataProvider, ProviderInfo, ProviderCapability

    class MyProvider(BaseDataProvider):
        def __init__(self):
            super().__init__(ProviderInfo(
                provider_id="my_provider",
                name="My Provider",
                category=DataSourceCategory.CORE,
                capabilities=[
                    ProviderCapability(
                        check_type=CheckType.CRIMINAL_NATIONAL,
                        supported_locales=[Locale.US],
                        cost_tier=CostTier.LOW,
                    ),
                ],
            ))

        async def execute_check(self, check_type, subject, locale, **kwargs):
            # Implement provider-specific logic
            ...

        async def health_check(self):
            # Implement health check
            ...
"""

from elile.providers.cache import (
    CacheEntry,
    CacheFreshnessConfig,
    CacheLookupResult,
    CacheStats,
    ProviderCacheService,
)
from elile.providers.cost import (
    BudgetConfig,
    BudgetExceededError,
    BudgetStatus,
    CostRecord,
    CostSummary,
    ProviderCostService,
    get_cost_service,
    reset_cost_service,
)
from elile.providers.health import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
    HealthMonitor,
    HealthMonitorConfig,
    ProviderMetrics,
)
from elile.providers.protocol import BaseDataProvider, DataProvider
from elile.providers.rate_limit import (
    ProviderRateLimitRegistry,
    RateLimitConfig,
    RateLimitExceededError,
    RateLimitResult,
    RateLimitStatus,
    RateLimitStrategy,
    TokenBucket,
    get_rate_limit_registry,
    reset_rate_limit_registry,
)
from elile.providers.registry import (
    NoProviderAvailableError,
    ProviderNotFoundError,
    ProviderRegistry,
    get_provider_registry,
    reset_provider_registry,
)
from elile.providers.types import (
    CostTier,
    DataSourceCategory,
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
    ProviderQuery,
    ProviderQueryCost,
    ProviderResult,
    ProviderStatus,
)

__all__ = [
    # Protocol
    "DataProvider",
    "BaseDataProvider",
    # Registry
    "ProviderRegistry",
    "get_provider_registry",
    "reset_provider_registry",
    "ProviderNotFoundError",
    "NoProviderAvailableError",
    # Health & Circuit Breaker
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerRegistry",
    "CircuitOpenError",
    "CircuitState",
    "HealthMonitor",
    "HealthMonitorConfig",
    "ProviderMetrics",
    # Rate Limiting
    "RateLimitConfig",
    "RateLimitResult",
    "RateLimitStatus",
    "RateLimitStrategy",
    "RateLimitExceededError",
    "TokenBucket",
    "ProviderRateLimitRegistry",
    "get_rate_limit_registry",
    "reset_rate_limit_registry",
    # Response Caching
    "CacheEntry",
    "CacheFreshnessConfig",
    "CacheLookupResult",
    "CacheStats",
    "ProviderCacheService",
    # Cost Tracking
    "BudgetConfig",
    "BudgetExceededError",
    "BudgetStatus",
    "CostRecord",
    "CostSummary",
    "ProviderCostService",
    "get_cost_service",
    "reset_cost_service",
    # Types
    "CostTier",
    "DataSourceCategory",
    "ProviderCapability",
    "ProviderHealth",
    "ProviderInfo",
    "ProviderQuery",
    "ProviderQueryCost",
    "ProviderResult",
    "ProviderStatus",
]
