"""Data provider protocol for Elile provider abstraction.

This module defines the interface that all data providers must implement.
Providers can be background check aggregators, court record systems,
credit bureaus, or any other data source.
"""

from typing import Protocol, runtime_checkable

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers

from .types import (
    DataSourceCategory,
    ProviderHealth,
    ProviderInfo,
    ProviderResult,
)


@runtime_checkable
class DataProvider(Protocol):
    """Interface all data providers must implement.

    This protocol defines the contract for integrating external data sources
    into the Elile platform. Implementations handle the specifics of
    communicating with each provider's API.

    Example implementation:
        class SterlingProvider:
            @property
            def provider_info(self) -> ProviderInfo:
                return ProviderInfo(
                    provider_id="sterling",
                    name="Sterling",
                    category=DataSourceCategory.CORE,
                    capabilities=[...],
                )

            async def execute_check(
                self,
                check_type: CheckType,
                subject: SubjectIdentifiers,
                locale: Locale,
                **kwargs,
            ) -> ProviderResult:
                # Call Sterling API and return normalized result
                ...
    """

    @property
    def provider_info(self) -> ProviderInfo:
        """Get static provider information.

        Returns:
            ProviderInfo with provider ID, capabilities, and metadata.
        """
        ...

    @property
    def provider_id(self) -> str:
        """Get the unique provider identifier.

        Returns:
            String identifier (e.g., "sterling", "checkr", "ofac").
        """
        ...

    @property
    def category(self) -> DataSourceCategory:
        """Get the provider's data source category.

        Returns:
            CORE for Standard tier, PREMIUM for Enhanced-only.
        """
        ...

    @property
    def supported_checks(self) -> list[CheckType]:
        """Get list of check types this provider supports.

        Returns:
            List of CheckType values this provider can execute.
        """
        ...

    @property
    def supported_locales(self) -> list[Locale]:
        """Get list of locales this provider supports.

        Returns:
            List of Locale values. Empty means all locales.
        """
        ...

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        degree: SearchDegree = SearchDegree.D1,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        timeout_ms: int = 30000,
    ) -> ProviderResult:
        """Execute a check against this provider.

        Args:
            check_type: Type of check to perform.
            subject: Subject identifiers to search for.
            locale: Jurisdiction for compliance filtering.
            degree: Search depth (D1=subject only, D2=connections, D3=extended).
            service_tier: Service tier affecting available options.
            timeout_ms: Request timeout in milliseconds.

        Returns:
            ProviderResult with normalized data or error information.

        Raises:
            ProviderError: If the request fails in an unrecoverable way.
        """
        ...

    async def health_check(self) -> ProviderHealth:
        """Check provider availability and health.

        Should be called periodically to update provider status.

        Returns:
            ProviderHealth with current status and metrics.
        """
        ...


class BaseDataProvider:
    """Base class for data provider implementations.

    Provides common functionality for provider implementations.
    Subclasses should override the abstract methods and provide
    their own ProviderInfo.
    """

    def __init__(self, provider_info: ProviderInfo):
        """Initialize the provider.

        Args:
            provider_info: Static provider information.
        """
        self._provider_info = provider_info

    @property
    def provider_info(self) -> ProviderInfo:
        """Get static provider information."""
        return self._provider_info

    @property
    def provider_id(self) -> str:
        """Get the unique provider identifier."""
        return self._provider_info.provider_id

    @property
    def category(self) -> DataSourceCategory:
        """Get the provider's data source category."""
        return self._provider_info.category

    @property
    def supported_checks(self) -> list[CheckType]:
        """Get list of check types this provider supports."""
        return self._provider_info.supported_checks

    @property
    def supported_locales(self) -> list[Locale]:
        """Get list of locales this provider supports."""
        return self._provider_info.supported_locales

    def supports_check(self, check_type: CheckType, locale: Locale | None = None) -> bool:
        """Check if this provider supports a check type.

        Args:
            check_type: Check type to verify.
            locale: Optional locale to filter by.

        Returns:
            True if the provider supports this check.
        """
        return self._provider_info.supports_check(check_type, locale)

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        *,
        degree: SearchDegree = SearchDegree.D1,
        service_tier: ServiceTier = ServiceTier.STANDARD,
        timeout_ms: int = 30000,
    ) -> ProviderResult:
        """Execute a check against this provider.

        Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement execute_check")

    async def health_check(self) -> ProviderHealth:
        """Check provider availability and health.

        Subclasses must implement this method.
        """
        raise NotImplementedError("Subclasses must implement health_check")
