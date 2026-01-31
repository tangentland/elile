"""Provider registry for Elile data provider management.

This module provides centralized registration and lookup of data providers,
enabling tier-aware routing and provider selection.
"""

from datetime import datetime, timedelta

from elile.agent.state import ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger

from .protocol import DataProvider
from .types import (
    CostTier,
    DataSourceCategory,
    ProviderHealth,
    ProviderInfo,
    ProviderStatus,
)

logger = get_logger(__name__)


class ProviderNotFoundError(Exception):
    """Raised when a provider is not found in the registry."""

    def __init__(self, provider_id: str):
        super().__init__(f"Provider not found: {provider_id}")
        self.provider_id = provider_id


class NoProviderAvailableError(Exception):
    """Raised when no provider is available for a check type."""

    def __init__(self, check_type: CheckType, locale: Locale | None = None):
        msg = f"No provider available for check type: {check_type.value}"
        if locale:
            msg += f" in locale: {locale.value}"
        super().__init__(msg)
        self.check_type = check_type
        self.locale = locale


class ProviderRegistry:
    """Registry for managing data providers.

    Provides centralized registration, lookup, and selection of providers
    based on check type, locale, service tier, and availability.

    Usage:
        registry = ProviderRegistry()
        registry.register(sterling_provider)
        registry.register(checkr_provider)

        # Get provider for a check
        provider = registry.get_provider_for_check(
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            service_tier=ServiceTier.STANDARD,
        )

        # Get all providers for a check (for fallback)
        providers = registry.get_providers_for_check(
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
        )
    """

    def __init__(self):
        """Initialize the provider registry."""
        self._providers: dict[str, DataProvider] = {}
        self._health_cache: dict[str, ProviderHealth] = {}
        self._health_check_interval = timedelta(minutes=5)

    def register(self, provider: DataProvider) -> None:
        """Register a provider with the registry.

        Args:
            provider: Provider instance to register.

        Raises:
            ValueError: If a provider with the same ID is already registered.
        """
        provider_id = provider.provider_id

        if provider_id in self._providers:
            raise ValueError(f"Provider already registered: {provider_id}")

        self._providers[provider_id] = provider

        # Initialize health cache with unknown status
        self._health_cache[provider_id] = ProviderHealth(
            provider_id=provider_id,
            status=ProviderStatus.HEALTHY,  # Assume healthy until first check
            last_check=datetime.utcnow() - self._health_check_interval * 2,
        )

        logger.info(
            "provider_registered",
            provider_id=provider_id,
            category=provider.category.value,
            supported_checks=[c.value for c in provider.supported_checks],
        )

    def unregister(self, provider_id: str) -> bool:
        """Unregister a provider from the registry.

        Args:
            provider_id: ID of provider to unregister.

        Returns:
            True if provider was unregistered, False if not found.
        """
        if provider_id not in self._providers:
            return False

        del self._providers[provider_id]
        self._health_cache.pop(provider_id, None)

        logger.info("provider_unregistered", provider_id=provider_id)
        return True

    def get_provider(self, provider_id: str) -> DataProvider:
        """Get a provider by ID.

        Args:
            provider_id: Unique provider identifier.

        Returns:
            The provider instance.

        Raises:
            ProviderNotFoundError: If provider is not registered.
        """
        if provider_id not in self._providers:
            raise ProviderNotFoundError(provider_id)
        return self._providers[provider_id]

    def get_provider_info(self, provider_id: str) -> ProviderInfo:
        """Get provider info by ID.

        Args:
            provider_id: Unique provider identifier.

        Returns:
            The provider info.

        Raises:
            ProviderNotFoundError: If provider is not registered.
        """
        return self.get_provider(provider_id).provider_info

    def get_provider_health(self, provider_id: str) -> ProviderHealth:
        """Get cached health status for a provider.

        Args:
            provider_id: Unique provider identifier.

        Returns:
            Cached health status.

        Raises:
            ProviderNotFoundError: If provider is not registered.
        """
        if provider_id not in self._providers:
            raise ProviderNotFoundError(provider_id)
        return self._health_cache.get(
            provider_id,
            ProviderHealth(
                provider_id=provider_id,
                status=ProviderStatus.HEALTHY,
                last_check=datetime.utcnow(),
            ),
        )

    def update_provider_health(self, health: ProviderHealth) -> None:
        """Update cached health status for a provider.

        Args:
            health: New health status.
        """
        self._health_cache[health.provider_id] = health

        if health.status != ProviderStatus.HEALTHY:
            logger.warning(
                "provider_health_changed",
                provider_id=health.provider_id,
                status=health.status.value,
                error_message=health.error_message,
            )

    def list_providers(
        self,
        category: DataSourceCategory | None = None,
        check_type: CheckType | None = None,
        locale: Locale | None = None,
        healthy_only: bool = False,
    ) -> list[DataProvider]:
        """List providers matching criteria.

        Args:
            category: Optional filter by category.
            check_type: Optional filter by supported check type.
            locale: Optional filter by supported locale.
            healthy_only: Only include healthy providers.

        Returns:
            List of matching providers.
        """
        result = []

        for provider in self._providers.values():
            # Filter by category
            if category is not None and provider.category != category:
                continue

            # Filter by check type
            if check_type is not None and check_type not in provider.supported_checks:
                continue

            # Filter by locale
            if locale is not None:
                info = provider.provider_info
                if info.supported_locales and locale not in info.supported_locales:
                    # Check if any capability supports this locale
                    if not any(
                        cap.supports_locale(locale)
                        for cap in info.capabilities
                        if check_type is None or cap.check_type == check_type
                    ):
                        continue

            # Filter by health
            if healthy_only:
                health = self._health_cache.get(provider.provider_id)
                if health and not health.is_available:
                    continue

            result.append(provider)

        return result

    def get_providers_for_check(
        self,
        check_type: CheckType,
        locale: Locale | None = None,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        healthy_only: bool = True,
    ) -> list[DataProvider]:
        """Get all providers that can handle a check type.

        Filters by service tier:
        - STANDARD: Only CORE category providers
        - ENHANCED: Both CORE and PREMIUM category providers

        Args:
            check_type: Type of check to find providers for.
            locale: Optional locale filter.
            service_tier: Service tier (affects available categories).
            healthy_only: Only include healthy providers.

        Returns:
            List of providers, sorted by preference (cost tier, reliability).
        """
        # Determine allowed categories based on service tier
        allowed_categories = {DataSourceCategory.CORE}
        if service_tier == ServiceTier.ENHANCED:
            allowed_categories.add(DataSourceCategory.PREMIUM)

        providers = []
        for provider in self._providers.values():
            # Check category is allowed for tier
            if provider.category not in allowed_categories:
                continue

            # Check supports the check type
            if check_type not in provider.supported_checks:
                continue

            # Check locale support
            if locale is not None:
                info = provider.provider_info
                cap = info.get_capability(check_type)
                if cap and not cap.supports_locale(locale):
                    continue

            # Check health
            if healthy_only:
                health = self._health_cache.get(provider.provider_id)
                if health and not health.is_available:
                    continue

            providers.append(provider)

        # Sort by preference (lower cost first, then higher reliability)
        def sort_key(p: DataProvider) -> tuple:
            info = p.provider_info
            cap = info.get_capability(check_type)
            cost_order = {
                CostTier.FREE: 0,
                CostTier.LOW: 1,
                CostTier.MEDIUM: 2,
                CostTier.HIGH: 3,
                CostTier.PREMIUM: 4,
            }
            cost = cost_order.get(cap.cost_tier, 2) if cap else 2
            reliability = 1.0 - (cap.reliability_score if cap else 0.9)
            return (cost, reliability)

        return sorted(providers, key=sort_key)

    def get_provider_for_check(
        self,
        check_type: CheckType,
        locale: Locale | None = None,
        service_tier: ServiceTier = ServiceTier.STANDARD,
    ) -> DataProvider:
        """Get the best provider for a check type.

        Args:
            check_type: Type of check to find provider for.
            locale: Optional locale filter.
            service_tier: Service tier (affects available categories).

        Returns:
            Best available provider.

        Raises:
            NoProviderAvailableError: If no provider can handle the check.
        """
        providers = self.get_providers_for_check(
            check_type=check_type,
            locale=locale,
            service_tier=service_tier,
            healthy_only=True,
        )

        if not providers:
            raise NoProviderAvailableError(check_type, locale)

        return providers[0]

    def get_fallback_providers(
        self,
        primary_provider_id: str,
        check_type: CheckType,
        locale: Locale | None = None,
        service_tier: ServiceTier = ServiceTier.STANDARD,
    ) -> list[DataProvider]:
        """Get fallback providers if primary fails.

        Args:
            primary_provider_id: ID of the primary provider to exclude.
            check_type: Type of check.
            locale: Optional locale filter.
            service_tier: Service tier.

        Returns:
            List of fallback providers, excluding the primary.
        """
        providers = self.get_providers_for_check(
            check_type=check_type,
            locale=locale,
            service_tier=service_tier,
            healthy_only=True,
        )

        return [p for p in providers if p.provider_id != primary_provider_id]

    async def check_all_health(self) -> dict[str, ProviderHealth]:
        """Run health checks on all registered providers.

        Returns:
            Dict mapping provider_id to health status.
        """
        results = {}

        for provider_id, provider in self._providers.items():
            try:
                health = await provider.health_check()
                self._health_cache[provider_id] = health
                results[provider_id] = health
            except Exception as e:
                health = ProviderHealth(
                    provider_id=provider_id,
                    status=ProviderStatus.UNHEALTHY,
                    last_check=datetime.utcnow(),
                    error_message=str(e),
                )
                self._health_cache[provider_id] = health
                results[provider_id] = health

                logger.error(
                    "provider_health_check_failed",
                    provider_id=provider_id,
                    error=str(e),
                )

        return results

    def get_statistics(self) -> dict:
        """Get registry statistics.

        Returns:
            Dict with provider counts and health summary.
        """
        total = len(self._providers)
        by_category = {}
        by_status = {}

        for provider_id, provider in self._providers.items():
            # Count by category
            cat = provider.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

            # Count by status
            health = self._health_cache.get(provider_id)
            status = health.status.value if health else "unknown"
            by_status[status] = by_status.get(status, 0) + 1

        return {
            "total_providers": total,
            "by_category": by_category,
            "by_status": by_status,
            "healthy_count": by_status.get(ProviderStatus.HEALTHY.value, 0),
        }


# Global registry instance
_global_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance.

    Returns:
        The global ProviderRegistry singleton.
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ProviderRegistry()
    return _global_registry


def reset_provider_registry() -> None:
    """Reset the global provider registry.

    Primarily used for testing.
    """
    global _global_registry
    _global_registry = None
