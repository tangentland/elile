"""Unit tests for provider request routing."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid7

import pytest

from elile.agent.state import ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.db.models.cache import FreshnessStatus
from elile.entity.types import SubjectIdentifiers
from elile.db.models.cache import DataOrigin
from elile.providers.cache import CacheEntry, CacheLookupResult, ProviderCacheService
from elile.providers.cost import ProviderCostService
from elile.providers.health import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerRegistry,
    CircuitOpenError,
    CircuitState,
)
from elile.providers.protocol import BaseDataProvider
from elile.providers.rate_limit import (
    ProviderRateLimitRegistry,
    RateLimitExceededError,
    RateLimitResult,
    RateLimitStatus,
)
from elile.providers.registry import ProviderRegistry
from elile.providers.router import (
    FailureReason,
    RequestRouter,
    RouteFailure,
    RoutedRequest,
    RoutedResult,
    RoutingConfig,
)
from elile.providers.types import (
    CostTier,
    DataSourceCategory,
    ProviderCapability,
    ProviderHealth,
    ProviderInfo,
    ProviderResult,
    ProviderStatus,
)


class TestRoutedRequest:
    """Tests for RoutedRequest dataclass."""

    def test_create_generates_request_id(self):
        """Test that create() generates a UUIDv7 request ID."""
        subject = SubjectIdentifiers(full_name="John Smith")
        request = RoutedRequest.create(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=uuid7(),
            tenant_id=uuid7(),
        )

        assert request.request_id is not None
        assert request.check_type == CheckType.CRIMINAL_NATIONAL
        assert request.locale == Locale.US
        assert request.service_tier == ServiceTier.STANDARD

    def test_create_with_service_tier(self):
        """Test create() with custom service tier."""
        subject = SubjectIdentifiers(full_name="John Smith")
        request = RoutedRequest.create(
            check_type=CheckType.CREDIT_REPORT,
            subject=subject,
            locale=Locale.US,
            entity_id=uuid7(),
            tenant_id=uuid7(),
            service_tier=ServiceTier.ENHANCED,
        )

        assert request.service_tier == ServiceTier.ENHANCED


class TestRouteFailure:
    """Tests for RouteFailure dataclass."""

    def test_add_error(self):
        """Test adding provider errors to failure."""
        failure = RouteFailure(
            reason=FailureReason.ALL_PROVIDERS_FAILED,
            message="All providers failed",
        )

        failure.add_error("provider1", "Connection timeout")
        failure.add_error("provider2", "Rate limited")

        assert len(failure.provider_errors) == 2
        assert ("provider1", "Connection timeout") in failure.provider_errors
        assert ("provider2", "Rate limited") in failure.provider_errors


class TestRoutingConfig:
    """Tests for RoutingConfig model."""

    def test_default_values(self):
        """Test default configuration values."""
        config = RoutingConfig()

        assert config.max_retries == 3
        assert config.base_retry_delay == 0.5
        assert config.max_retry_delay == 10.0
        assert config.retry_jitter == 0.1
        assert config.timeout == 30.0
        assert config.parallel_batch is True
        assert config.include_stale_cache is False

    def test_custom_values(self):
        """Test custom configuration values."""
        config = RoutingConfig(
            max_retries=5,
            base_retry_delay=1.0,
            timeout=60.0,
        )

        assert config.max_retries == 5
        assert config.base_retry_delay == 1.0
        assert config.timeout == 60.0


class MockProvider(BaseDataProvider):
    """Mock provider for testing."""

    def __init__(
        self,
        provider_id: str,
        category: DataSourceCategory = DataSourceCategory.CORE,
        check_types: list[CheckType] | None = None,
        locales: list[Locale] | None = None,
    ):
        super().__init__(
            ProviderInfo(
                provider_id=provider_id,
                name=f"Mock {provider_id}",
                category=category,
                capabilities=[
                    ProviderCapability(
                        check_type=ct,
                        supported_locales=locales or [Locale.US],
                        cost_tier=CostTier.LOW,
                    )
                    for ct in (check_types or [CheckType.CRIMINAL_NATIONAL])
                ],
            )
        )
        self.execute_check = AsyncMock(
            return_value=ProviderResult(
                provider_id=provider_id,
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
                normalized_data={"records": []},
                cost_incurred=Decimal("5.00"),
            )
        )
        self.health_check = AsyncMock(
            return_value=ProviderHealth(
                provider_id=provider_id,
                status=ProviderStatus.HEALTHY,
                last_check=datetime.now(UTC),
            )
        )


@pytest.fixture
def registry():
    """Create a test provider registry."""
    reg = ProviderRegistry()
    return reg


@pytest.fixture
def mock_provider():
    """Create a mock provider."""
    return MockProvider("test_provider")


@pytest.fixture
def subject():
    """Create test subject identifiers."""
    return SubjectIdentifiers(
        full_name="John Smith",
        date_of_birth="1980-01-15",
    )


@pytest.fixture
def entity_id():
    """Create test entity ID."""
    return uuid7()


@pytest.fixture
def tenant_id():
    """Create test tenant ID."""
    return uuid7()


class TestRequestRouter:
    """Tests for RequestRouter class."""

    @pytest.mark.asyncio
    async def test_route_request_success(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test successful request routing."""
        registry.register(mock_provider)
        router = RequestRouter(registry=registry)

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.provider_id == "test_provider"
        assert result.result is not None
        assert result.result.success is True
        assert result.attempts >= 1
        assert result.failure is None

    @pytest.mark.asyncio
    async def test_route_request_no_provider(self, registry, subject, entity_id, tenant_id):
        """Test routing when no provider available."""
        router = RequestRouter(registry=registry)

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is False
        assert result.failure is not None
        assert result.failure.reason == FailureReason.NO_PROVIDER

    @pytest.mark.asyncio
    async def test_route_request_with_cache_hit(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test routing with cache hit."""
        registry.register(mock_provider)

        now = datetime.now(UTC)
        # Create mock cache service
        mock_cache = MagicMock(spec=ProviderCacheService)
        mock_cache.get = AsyncMock(
            return_value=CacheLookupResult(
                hit=True,
                freshness=FreshnessStatus.FRESH,
                entry=CacheEntry(
                    cache_id=uuid7(),
                    entity_id=entity_id,
                    provider_id="test_provider",
                    check_type=CheckType.CRIMINAL_NATIONAL.value,
                    freshness=FreshnessStatus.FRESH,
                    acquired_at=now,
                    fresh_until=now + timedelta(days=7),
                    stale_until=now + timedelta(days=30),
                    normalized_data={"records": []},
                    cost_incurred=Decimal("5.00"),
                    cost_currency="USD",
                    data_origin=DataOrigin.PAID_EXTERNAL,
                ),
            )
        )

        router = RequestRouter(registry=registry, cache=mock_cache)

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.cache_hit is True
        assert result.attempts == 0
        # Provider should not be called
        mock_provider.execute_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_request_circuit_open(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test routing when circuit breaker is open."""
        registry.register(mock_provider)

        # Create circuit registry with open circuit
        circuit_registry = CircuitBreakerRegistry()
        breaker = circuit_registry.get_breaker("test_provider")
        breaker.force_open()

        router = RequestRouter(
            registry=registry,
            circuit_registry=circuit_registry,
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is False
        assert result.failure is not None
        assert result.failure.reason == FailureReason.ALL_CIRCUITS_OPEN
        mock_provider.execute_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_request_rate_limited(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test routing when rate limited."""
        registry.register(mock_provider)

        # Create rate limiter that denies
        rate_limiter = MagicMock(spec=ProviderRateLimitRegistry)
        rate_limiter.check = AsyncMock(
            return_value=RateLimitResult(
                allowed=False,
                tokens_remaining=0.0,
                retry_after_seconds=5.0,
            )
        )

        router = RequestRouter(
            registry=registry,
            rate_limiter=rate_limiter,
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is False
        assert result.failure is not None
        assert result.failure.reason == FailureReason.ALL_RATE_LIMITED
        mock_provider.execute_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_request_provider_failure_fallback(
        self, registry, subject, entity_id, tenant_id
    ):
        """Test fallback to alternate provider on failure."""
        # Create two providers, first fails, second succeeds
        provider1 = MockProvider("provider1")
        provider1.execute_check = AsyncMock(
            return_value=ProviderResult(
                provider_id="provider1",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=False,
                error_code="CONNECTION_ERROR",
                error_message="Connection failed",
                retryable=False,
            )
        )

        provider2 = MockProvider("provider2")
        provider2.execute_check = AsyncMock(
            return_value=ProviderResult(
                provider_id="provider2",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
                normalized_data={"records": []},
                cost_incurred=Decimal("5.00"),
            )
        )

        registry.register(provider1)
        registry.register(provider2)

        router = RequestRouter(
            registry=registry,
            config=RoutingConfig(max_retries=1),  # No retries
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.provider_id == "provider2"

    @pytest.mark.asyncio
    async def test_route_request_retry_on_failure(
        self, registry, subject, entity_id, tenant_id
    ):
        """Test retry logic on transient failure."""
        provider = MockProvider("test_provider")
        # First call fails with retryable error, second succeeds
        provider.execute_check = AsyncMock(
            side_effect=[
                ProviderResult(
                    provider_id="test_provider",
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    locale=Locale.US,
                    success=False,
                    error_code="TIMEOUT",
                    error_message="Request timed out",
                    retryable=True,
                ),
                ProviderResult(
                    provider_id="test_provider",
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    locale=Locale.US,
                    success=True,
                    normalized_data={"records": []},
                ),
            ]
        )

        registry.register(provider)
        router = RequestRouter(
            registry=registry,
            config=RoutingConfig(base_retry_delay=0.01),  # Fast retries for testing
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.attempts == 2
        assert provider.execute_check.call_count == 2

    @pytest.mark.asyncio
    async def test_route_request_timeout(
        self, registry, subject, entity_id, tenant_id
    ):
        """Test request timeout handling."""
        provider = MockProvider("test_provider")
        # Simulate a slow provider
        async def slow_execute(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than timeout
            return ProviderResult(
                provider_id="test_provider",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
            )

        provider.execute_check = AsyncMock(side_effect=slow_execute)

        registry.register(provider)
        router = RequestRouter(
            registry=registry,
            config=RoutingConfig(
                timeout=0.05,  # 50ms timeout
                max_retries=1,
                base_retry_delay=0.01,
            ),
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is False
        assert result.failure is not None
        assert "Timeout" in str(result.failure.provider_errors)

    @pytest.mark.asyncio
    async def test_route_request_cost_tracking(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test cost tracking integration."""
        registry.register(mock_provider)

        cost_service = MagicMock(spec=ProviderCostService)
        cost_service.record_cost = AsyncMock()

        router = RequestRouter(
            registry=registry,
            cost_service=cost_service,
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        cost_service.record_cost.assert_called_once()


class TestRequestRouterBatch:
    """Tests for batch routing."""

    @pytest.mark.asyncio
    async def test_route_batch_parallel(self, registry, subject, entity_id, tenant_id):
        """Test parallel batch routing."""
        provider = MockProvider(
            "test_provider",
            check_types=[CheckType.CRIMINAL_NATIONAL, CheckType.CREDIT_REPORT],
        )
        registry.register(provider)

        router = RequestRouter(registry=registry)

        requests = [
            RoutedRequest.create(
                check_type=CheckType.CRIMINAL_NATIONAL,
                subject=subject,
                locale=Locale.US,
                entity_id=entity_id,
                tenant_id=tenant_id,
            ),
            RoutedRequest.create(
                check_type=CheckType.CREDIT_REPORT,
                subject=subject,
                locale=Locale.US,
                entity_id=entity_id,
                tenant_id=tenant_id,
            ),
        ]

        results = await router.route_batch(requests, parallel=True)

        assert len(results) == 2
        # All should succeed
        for result in results:
            assert result.success is True

    @pytest.mark.asyncio
    async def test_route_batch_sequential(self, registry, subject, entity_id, tenant_id):
        """Test sequential batch routing."""
        provider = MockProvider(
            "test_provider",
            check_types=[CheckType.CRIMINAL_NATIONAL, CheckType.CREDIT_REPORT],
        )
        registry.register(provider)

        router = RequestRouter(registry=registry)

        requests = [
            RoutedRequest.create(
                check_type=CheckType.CRIMINAL_NATIONAL,
                subject=subject,
                locale=Locale.US,
                entity_id=entity_id,
                tenant_id=tenant_id,
            ),
            RoutedRequest.create(
                check_type=CheckType.CREDIT_REPORT,
                subject=subject,
                locale=Locale.US,
                entity_id=entity_id,
                tenant_id=tenant_id,
            ),
        ]

        results = await router.route_batch(requests, parallel=False)

        assert len(results) == 2
        for result in results:
            assert result.success is True

    @pytest.mark.asyncio
    async def test_route_batch_empty(self, registry):
        """Test empty batch routing."""
        router = RequestRouter(registry=registry)

        results = await router.route_batch([])

        assert results == []

    @pytest.mark.asyncio
    async def test_route_batch_partial_failure(self, registry, subject, entity_id, tenant_id):
        """Test batch with partial failures."""
        # Provider only supports criminal check
        provider = MockProvider(
            "test_provider",
            check_types=[CheckType.CRIMINAL_NATIONAL],
        )
        registry.register(provider)

        router = RequestRouter(registry=registry)

        requests = [
            RoutedRequest.create(
                check_type=CheckType.CRIMINAL_NATIONAL,
                subject=subject,
                locale=Locale.US,
                entity_id=entity_id,
                tenant_id=tenant_id,
            ),
            RoutedRequest.create(
                check_type=CheckType.CREDIT_REPORT,  # No provider for this
                subject=subject,
                locale=Locale.US,
                entity_id=entity_id,
                tenant_id=tenant_id,
            ),
        ]

        results = await router.route_batch(requests)

        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert results[1].failure.reason == FailureReason.NO_PROVIDER


class TestRequestRouterCircuitBreaker:
    """Tests for circuit breaker integration."""

    @pytest.mark.asyncio
    async def test_circuit_records_success(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test that success is recorded to circuit breaker."""
        registry.register(mock_provider)

        circuit_registry = CircuitBreakerRegistry()
        router = RequestRouter(
            registry=registry,
            circuit_registry=circuit_registry,
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        breaker = circuit_registry.get_breaker("test_provider")
        assert breaker.is_closed

    @pytest.mark.asyncio
    async def test_circuit_records_failure(
        self, registry, subject, entity_id, tenant_id
    ):
        """Test that failure is recorded to circuit breaker."""
        provider = MockProvider("test_provider")
        provider.execute_check = AsyncMock(
            return_value=ProviderResult(
                provider_id="test_provider",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=False,
                error_code="ERROR",
                error_message="Failed",
                retryable=False,
            )
        )
        registry.register(provider)

        circuit_registry = CircuitBreakerRegistry(
            default_config=CircuitBreakerConfig(failure_threshold=1)
        )
        router = RequestRouter(
            registry=registry,
            circuit_registry=circuit_registry,
            config=RoutingConfig(max_retries=1),
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is False
        breaker = circuit_registry.get_breaker("test_provider")
        # Circuit should be open after failure threshold reached
        assert breaker.is_open


class TestRequestRouterCacheIntegration:
    """Tests for cache integration."""

    @pytest.mark.asyncio
    async def test_cache_miss_stores_result(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test that cache miss stores the result."""
        registry.register(mock_provider)

        mock_cache = MagicMock(spec=ProviderCacheService)
        mock_cache.get = AsyncMock(
            return_value=CacheLookupResult(
                hit=False,
                freshness=FreshnessStatus.EXPIRED,
                entry=None,
            )
        )
        mock_cache.store = AsyncMock()

        router = RequestRouter(
            registry=registry,
            cache=mock_cache,
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.cache_hit is False
        mock_cache.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_stale_cache_used_when_configured(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test that stale cache is used when configured."""
        registry.register(mock_provider)

        now = datetime.now(UTC)
        mock_cache = MagicMock(spec=ProviderCacheService)
        mock_cache.get = AsyncMock(
            return_value=CacheLookupResult(
                hit=True,
                freshness=FreshnessStatus.STALE,
                entry=CacheEntry(
                    cache_id=uuid7(),
                    entity_id=entity_id,
                    provider_id="test_provider",
                    check_type=CheckType.CRIMINAL_NATIONAL.value,
                    freshness=FreshnessStatus.STALE,
                    acquired_at=now - timedelta(days=30),
                    fresh_until=now - timedelta(days=23),
                    stale_until=now + timedelta(days=7),
                    normalized_data={"records": ["old"]},
                    cost_incurred=Decimal("5.00"),
                    cost_currency="USD",
                    data_origin=DataOrigin.PAID_EXTERNAL,
                ),
            )
        )

        router = RequestRouter(
            registry=registry,
            cache=mock_cache,
            config=RoutingConfig(include_stale_cache=True),
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.cache_hit is True
        # Provider should not be called
        mock_provider.execute_check.assert_not_called()


class TestRequestRouterCostTracking:
    """Tests for cost tracking integration."""

    @pytest.mark.asyncio
    async def test_cache_hit_records_savings(
        self, registry, mock_provider, subject, entity_id, tenant_id
    ):
        """Test that cache hit records cost savings."""
        registry.register(mock_provider)

        now = datetime.now(UTC)
        mock_cache = MagicMock(spec=ProviderCacheService)
        mock_cache.get = AsyncMock(
            return_value=CacheLookupResult(
                hit=True,
                freshness=FreshnessStatus.FRESH,
                entry=CacheEntry(
                    cache_id=uuid7(),
                    entity_id=entity_id,
                    provider_id="test_provider",
                    check_type=CheckType.CRIMINAL_NATIONAL.value,
                    freshness=FreshnessStatus.FRESH,
                    acquired_at=now,
                    fresh_until=now + timedelta(days=7),
                    stale_until=now + timedelta(days=30),
                    normalized_data={"records": []},
                    cost_incurred=Decimal("5.00"),
                    cost_currency="USD",
                    data_origin=DataOrigin.PAID_EXTERNAL,
                ),
            )
        )

        cost_service = MagicMock(spec=ProviderCostService)
        cost_service.record_cache_savings = AsyncMock()

        router = RequestRouter(
            registry=registry,
            cache=mock_cache,
            cost_service=cost_service,
        )

        result = await router.route_request(
            check_type=CheckType.CRIMINAL_NATIONAL,
            subject=subject,
            locale=Locale.US,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )

        assert result.success is True
        assert result.cache_hit is True
        cost_service.record_cache_savings.assert_called_once()


class TestRoutedResult:
    """Tests for RoutedResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=True,
            provider_id="test_provider",
            attempts=1,
        )

        assert result.success is True
        assert result.failure is None

    def test_failed_result(self):
        """Test creating a failed result."""
        result = RoutedResult(
            request_id=uuid7(),
            check_type=CheckType.CRIMINAL_NATIONAL,
            success=False,
            failure=RouteFailure(
                reason=FailureReason.ALL_PROVIDERS_FAILED,
                message="All providers failed",
            ),
        )

        assert result.success is False
        assert result.failure is not None
        assert result.failure.reason == FailureReason.ALL_PROVIDERS_FAILED


class TestFailureReason:
    """Tests for FailureReason enum."""

    def test_all_values(self):
        """Test all failure reason values."""
        assert FailureReason.NO_PROVIDER.value == "no_provider"
        assert FailureReason.ALL_PROVIDERS_FAILED.value == "all_providers_failed"
        assert FailureReason.ALL_CIRCUITS_OPEN.value == "all_circuits_open"
        assert FailureReason.ALL_RATE_LIMITED.value == "all_rate_limited"
        assert FailureReason.TIMEOUT.value == "timeout"
        assert FailureReason.CANCELLED.value == "cancelled"
