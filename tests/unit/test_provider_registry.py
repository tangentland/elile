"""Unit tests for Provider Interface and Registry.

Tests the DataProvider protocol, ProviderRegistry, and related types.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers
from elile.providers import (
    BaseDataProvider,
    CostTier,
    DataProvider,
    DataSourceCategory,
    NoProviderAvailableError,
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
    ProviderNotFoundError,
    ProviderQuery,
    ProviderQueryCost,
    ProviderRegistry,
    ProviderResult,
    ProviderStatus,
    get_provider_registry,
    reset_provider_registry,
)


# =============================================================================
# Type Tests
# =============================================================================


class TestDataSourceCategory:
    """Tests for DataSourceCategory enum."""

    def test_core_value(self):
        """Test CORE category value."""
        assert DataSourceCategory.CORE.value == "core"

    def test_premium_value(self):
        """Test PREMIUM category value."""
        assert DataSourceCategory.PREMIUM.value == "premium"


class TestCostTier:
    """Tests for CostTier enum."""

    def test_all_tiers(self):
        """Test all cost tier values."""
        assert CostTier.FREE.value == "free"
        assert CostTier.LOW.value == "low"
        assert CostTier.MEDIUM.value == "medium"
        assert CostTier.HIGH.value == "high"
        assert CostTier.PREMIUM.value == "premium"


class TestProviderStatus:
    """Tests for ProviderStatus enum."""

    def test_all_statuses(self):
        """Test all status values."""
        assert ProviderStatus.HEALTHY.value == "healthy"
        assert ProviderStatus.DEGRADED.value == "degraded"
        assert ProviderStatus.UNHEALTHY.value == "unhealthy"
        assert ProviderStatus.MAINTENANCE.value == "maintenance"


class TestProviderHealth:
    """Tests for ProviderHealth model."""

    def test_create_healthy(self):
        """Test creating healthy status."""
        health = ProviderHealth(
            provider_id="test",
            status=ProviderStatus.HEALTHY,
            last_check=datetime.utcnow(),
            latency_ms=100,
        )
        assert health.is_available is True
        assert health.consecutive_failures == 0

    def test_create_degraded(self):
        """Test degraded is still available."""
        health = ProviderHealth(
            provider_id="test",
            status=ProviderStatus.DEGRADED,
            last_check=datetime.utcnow(),
        )
        assert health.is_available is True

    def test_create_unhealthy(self):
        """Test unhealthy is not available."""
        health = ProviderHealth(
            provider_id="test",
            status=ProviderStatus.UNHEALTHY,
            last_check=datetime.utcnow(),
            error_message="Connection refused",
        )
        assert health.is_available is False

    def test_maintenance_not_available(self):
        """Test maintenance is not available."""
        health = ProviderHealth(
            provider_id="test",
            status=ProviderStatus.MAINTENANCE,
            last_check=datetime.utcnow(),
        )
        assert health.is_available is False


class TestProviderResult:
    """Tests for ProviderResult model."""

    def test_create_success(self):
        """Test creating successful result."""
        result = ProviderResult(
            provider_id="test",
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            success=True,
            normalized_data={"records": []},
            latency_ms=500,
        )
        assert result.is_success is True
        assert result.error_code is None

    def test_create_failure(self):
        """Test creating failed result."""
        result = ProviderResult(
            provider_id="test",
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            success=False,
            error_code="API_ERROR",
            error_message="Service unavailable",
            retryable=True,
        )
        assert result.is_success is False
        assert result.retryable is True

    def test_cost_defaults(self):
        """Test cost default values."""
        result = ProviderResult(
            provider_id="test",
            check_type=CheckType.CREDIT_REPORT,
            locale=Locale.US,
            success=True,
        )
        assert result.cost_incurred == Decimal("0.00")
        assert result.cost_currency == "USD"


class TestProviderCapability:
    """Tests for ProviderCapability model."""

    def test_supports_locale_empty(self):
        """Test empty supported_locales means all locales."""
        cap = ProviderCapability(
            check_type=CheckType.CRIMINAL_NATIONAL,
            supported_locales=[],
        )
        assert cap.supports_locale(Locale.US) is True
        assert cap.supports_locale(Locale.UK) is True

    def test_supports_locale_specific(self):
        """Test specific locale support."""
        cap = ProviderCapability(
            check_type=CheckType.CRIMINAL_NATIONAL,
            supported_locales=[Locale.US, Locale.CA],
        )
        assert cap.supports_locale(Locale.US) is True
        assert cap.supports_locale(Locale.CA) is True
        assert cap.supports_locale(Locale.UK) is False


class TestProviderInfo:
    """Tests for ProviderInfo model."""

    @pytest.fixture
    def provider_info(self):
        """Create test provider info."""
        return ProviderInfo(
            provider_id="test_provider",
            name="Test Provider",
            description="A test provider",
            category=DataSourceCategory.CORE,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    supported_locales=[Locale.US],
                    cost_tier=CostTier.LOW,
                ),
                ProviderCapability(
                    check_type=CheckType.CREDIT_REPORT,
                    supported_locales=[Locale.US, Locale.CA],
                    cost_tier=CostTier.MEDIUM,
                ),
            ],
        )

    def test_supported_checks(self, provider_info):
        """Test supported_checks property."""
        checks = provider_info.supported_checks
        assert CheckType.CRIMINAL_NATIONAL in checks
        assert CheckType.CREDIT_REPORT in checks
        assert len(checks) == 2

    def test_supported_locales(self, provider_info):
        """Test supported_locales property."""
        locales = provider_info.supported_locales
        assert Locale.US in locales
        assert Locale.CA in locales

    def test_get_capability(self, provider_info):
        """Test get_capability method."""
        cap = provider_info.get_capability(CheckType.CRIMINAL_NATIONAL)
        assert cap is not None
        assert cap.cost_tier == CostTier.LOW

        cap = provider_info.get_capability(CheckType.EMPLOYMENT_VERIFICATION)
        assert cap is None

    def test_supports_check(self, provider_info):
        """Test supports_check method."""
        assert provider_info.supports_check(CheckType.CRIMINAL_NATIONAL) is True
        assert provider_info.supports_check(CheckType.CRIMINAL_NATIONAL, Locale.US) is True
        assert provider_info.supports_check(CheckType.CRIMINAL_NATIONAL, Locale.UK) is False
        assert provider_info.supports_check(CheckType.EMPLOYMENT_VERIFICATION) is False


class TestProviderQuery:
    """Tests for ProviderQuery model."""

    def test_create(self):
        """Test creating provider query."""
        query = ProviderQuery(
            query_id=uuid7(),
            provider_id="test",
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            subject_data={"name": "John Smith"},
        )
        assert query.timeout_ms == 30000
        assert query.retry_count == 0
        assert query.max_retries == 3


class TestProviderQueryCost:
    """Tests for ProviderQueryCost model."""

    def test_create(self):
        """Test creating query cost."""
        cost = ProviderQueryCost(
            query_id=uuid7(),
            provider_id="test",
            check_type=CheckType.CREDIT_REPORT,
            base_cost=Decimal("5.00"),
            volume_discount=Decimal("0.50"),
            final_cost=Decimal("4.50"),
        )
        assert cost.final_cost == Decimal("4.50")
        assert cost.cache_hit is False


# =============================================================================
# BaseDataProvider Tests
# =============================================================================


class TestBaseDataProvider:
    """Tests for BaseDataProvider class."""

    @pytest.fixture
    def provider_info(self):
        """Create test provider info."""
        return ProviderInfo(
            provider_id="test_base",
            name="Test Base Provider",
            category=DataSourceCategory.CORE,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    supported_locales=[Locale.US],
                ),
            ],
        )

    @pytest.fixture
    def base_provider(self, provider_info):
        """Create base provider instance."""
        return BaseDataProvider(provider_info)

    def test_provider_id(self, base_provider):
        """Test provider_id property."""
        assert base_provider.provider_id == "test_base"

    def test_category(self, base_provider):
        """Test category property."""
        assert base_provider.category == DataSourceCategory.CORE

    def test_supported_checks(self, base_provider):
        """Test supported_checks property."""
        assert CheckType.CRIMINAL_NATIONAL in base_provider.supported_checks

    def test_supports_check(self, base_provider):
        """Test supports_check method."""
        assert base_provider.supports_check(CheckType.CRIMINAL_NATIONAL) is True
        assert base_provider.supports_check(CheckType.CREDIT_REPORT) is False

    @pytest.mark.asyncio
    async def test_execute_check_not_implemented(self, base_provider):
        """Test execute_check raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await base_provider.execute_check(
                CheckType.CRIMINAL_NATIONAL,
                SubjectIdentifiers(full_name="Test"),
                Locale.US,
            )

    @pytest.mark.asyncio
    async def test_health_check_not_implemented(self, base_provider):
        """Test health_check raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            await base_provider.health_check()


# =============================================================================
# ProviderRegistry Tests
# =============================================================================


class MockProvider(BaseDataProvider):
    """Mock provider for testing."""

    def __init__(
        self,
        provider_id: str,
        category: DataSourceCategory = DataSourceCategory.CORE,
        checks: list[CheckType] | None = None,
        locales: list[Locale] | None = None,
        cost_tier: CostTier = CostTier.MEDIUM,
    ):
        checks = checks or [CheckType.CRIMINAL_NATIONAL]
        locales = locales or [Locale.US]

        super().__init__(
            ProviderInfo(
                provider_id=provider_id,
                name=f"Mock {provider_id}",
                category=category,
                capabilities=[
                    ProviderCapability(
                        check_type=check,
                        supported_locales=locales,
                        cost_tier=cost_tier,
                    )
                    for check in checks
                ],
            )
        )

    async def execute_check(
        self,
        check_type: CheckType,
        subject: SubjectIdentifiers,
        locale: Locale,
        **kwargs,
    ) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            check_type=check_type,
            locale=locale,
            success=True,
            normalized_data={"mock": True},
        )

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            last_check=datetime.utcnow(),
        )


class TestProviderRegistry:
    """Tests for ProviderRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create a fresh registry."""
        return ProviderRegistry()

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider."""
        return MockProvider("mock_provider")

    def test_register(self, registry, mock_provider):
        """Test registering a provider."""
        registry.register(mock_provider)
        assert registry.get_provider("mock_provider") is mock_provider

    def test_register_duplicate(self, registry, mock_provider):
        """Test registering duplicate provider raises error."""
        registry.register(mock_provider)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(mock_provider)

    def test_unregister(self, registry, mock_provider):
        """Test unregistering a provider."""
        registry.register(mock_provider)
        assert registry.unregister("mock_provider") is True
        assert registry.unregister("mock_provider") is False

    def test_get_provider_not_found(self, registry):
        """Test getting non-existent provider raises error."""
        with pytest.raises(ProviderNotFoundError):
            registry.get_provider("nonexistent")

    def test_get_provider_info(self, registry, mock_provider):
        """Test getting provider info."""
        registry.register(mock_provider)
        info = registry.get_provider_info("mock_provider")
        assert info.provider_id == "mock_provider"

    def test_get_provider_health(self, registry, mock_provider):
        """Test getting provider health."""
        registry.register(mock_provider)
        health = registry.get_provider_health("mock_provider")
        assert health.provider_id == "mock_provider"

    def test_update_provider_health(self, registry, mock_provider):
        """Test updating provider health."""
        registry.register(mock_provider)
        new_health = ProviderHealth(
            provider_id="mock_provider",
            status=ProviderStatus.DEGRADED,
            last_check=datetime.utcnow(),
        )
        registry.update_provider_health(new_health)
        health = registry.get_provider_health("mock_provider")
        assert health.status == ProviderStatus.DEGRADED

    def test_list_providers_all(self, registry):
        """Test listing all providers."""
        registry.register(MockProvider("p1"))
        registry.register(MockProvider("p2"))
        providers = registry.list_providers()
        assert len(providers) == 2

    def test_list_providers_by_category(self, registry):
        """Test listing providers by category."""
        registry.register(MockProvider("core1", DataSourceCategory.CORE))
        registry.register(MockProvider("premium1", DataSourceCategory.PREMIUM))

        core = registry.list_providers(category=DataSourceCategory.CORE)
        assert len(core) == 1
        assert core[0].provider_id == "core1"

    def test_list_providers_by_check_type(self, registry):
        """Test listing providers by check type."""
        registry.register(MockProvider("criminal", checks=[CheckType.CRIMINAL_NATIONAL]))
        registry.register(MockProvider("credit", checks=[CheckType.CREDIT_REPORT]))

        criminal = registry.list_providers(check_type=CheckType.CRIMINAL_NATIONAL)
        assert len(criminal) == 1
        assert criminal[0].provider_id == "criminal"

    def test_list_providers_healthy_only(self, registry):
        """Test listing only healthy providers."""
        registry.register(MockProvider("healthy"))
        registry.register(MockProvider("unhealthy"))

        # Mark one as unhealthy
        registry.update_provider_health(ProviderHealth(
            provider_id="unhealthy",
            status=ProviderStatus.UNHEALTHY,
            last_check=datetime.utcnow(),
        ))

        healthy = registry.list_providers(healthy_only=True)
        assert len(healthy) == 1
        assert healthy[0].provider_id == "healthy"

    def test_get_providers_for_check_standard_tier(self, registry):
        """Test getting providers for standard tier."""
        registry.register(MockProvider("core", DataSourceCategory.CORE))
        registry.register(MockProvider("premium", DataSourceCategory.PREMIUM))

        providers = registry.get_providers_for_check(
            check_type=CheckType.CRIMINAL_NATIONAL,
            service_tier=ServiceTier.STANDARD,
        )
        assert len(providers) == 1
        assert providers[0].provider_id == "core"

    def test_get_providers_for_check_enhanced_tier(self, registry):
        """Test getting providers for enhanced tier."""
        registry.register(MockProvider("core", DataSourceCategory.CORE))
        registry.register(MockProvider("premium", DataSourceCategory.PREMIUM))

        providers = registry.get_providers_for_check(
            check_type=CheckType.CRIMINAL_NATIONAL,
            service_tier=ServiceTier.ENHANCED,
        )
        assert len(providers) == 2

    def test_get_providers_for_check_sorted_by_cost(self, registry):
        """Test providers are sorted by cost tier."""
        registry.register(MockProvider("expensive", cost_tier=CostTier.HIGH))
        registry.register(MockProvider("cheap", cost_tier=CostTier.FREE))
        registry.register(MockProvider("medium", cost_tier=CostTier.MEDIUM))

        providers = registry.get_providers_for_check(
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert providers[0].provider_id == "cheap"
        assert providers[1].provider_id == "medium"
        assert providers[2].provider_id == "expensive"

    def test_get_provider_for_check(self, registry):
        """Test getting single best provider."""
        registry.register(MockProvider("best", cost_tier=CostTier.LOW))
        registry.register(MockProvider("expensive", cost_tier=CostTier.HIGH))

        provider = registry.get_provider_for_check(CheckType.CRIMINAL_NATIONAL)
        assert provider.provider_id == "best"

    def test_get_provider_for_check_no_available(self, registry):
        """Test error when no provider available."""
        with pytest.raises(NoProviderAvailableError):
            registry.get_provider_for_check(CheckType.CRIMINAL_NATIONAL)

    def test_get_fallback_providers(self, registry):
        """Test getting fallback providers."""
        registry.register(MockProvider("primary"))
        registry.register(MockProvider("fallback1"))
        registry.register(MockProvider("fallback2"))

        fallbacks = registry.get_fallback_providers(
            primary_provider_id="primary",
            check_type=CheckType.CRIMINAL_NATIONAL,
        )
        assert len(fallbacks) == 2
        assert all(p.provider_id != "primary" for p in fallbacks)

    @pytest.mark.asyncio
    async def test_check_all_health(self, registry):
        """Test checking health of all providers."""
        registry.register(MockProvider("p1"))
        registry.register(MockProvider("p2"))

        results = await registry.check_all_health()
        assert len(results) == 2
        assert all(h.status == ProviderStatus.HEALTHY for h in results.values())

    def test_get_statistics(self, registry):
        """Test getting registry statistics."""
        registry.register(MockProvider("core1", DataSourceCategory.CORE))
        registry.register(MockProvider("core2", DataSourceCategory.CORE))
        registry.register(MockProvider("premium1", DataSourceCategory.PREMIUM))

        stats = registry.get_statistics()
        assert stats["total_providers"] == 3
        assert stats["by_category"]["core"] == 2
        assert stats["by_category"]["premium"] == 1


class TestGlobalRegistry:
    """Tests for global registry functions."""

    def teardown_method(self):
        """Reset global registry after each test."""
        reset_provider_registry()

    def test_get_provider_registry(self):
        """Test getting global registry."""
        reg1 = get_provider_registry()
        reg2 = get_provider_registry()
        assert reg1 is reg2

    def test_reset_provider_registry(self):
        """Test resetting global registry."""
        reg1 = get_provider_registry()
        reg1.register(MockProvider("test"))

        reset_provider_registry()

        reg2 = get_provider_registry()
        assert reg2 is not reg1
        with pytest.raises(ProviderNotFoundError):
            reg2.get_provider("test")


# =============================================================================
# Protocol Compliance Tests
# =============================================================================


class TestProtocolCompliance:
    """Tests for DataProvider protocol compliance."""

    def test_mock_provider_is_data_provider(self):
        """Test MockProvider implements DataProvider protocol."""
        provider = MockProvider("test")
        assert isinstance(provider, DataProvider)

    def test_base_provider_is_data_provider(self):
        """Test BaseDataProvider implements DataProvider protocol."""
        info = ProviderInfo(
            provider_id="test",
            name="Test",
            category=DataSourceCategory.CORE,
        )
        provider = BaseDataProvider(info)
        assert isinstance(provider, DataProvider)
