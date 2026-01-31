"""Unit tests for Provider Cache Service.

Tests the ProviderCacheService and related classes.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from elile.compliance.types import CheckType, Locale
from elile.db.models.cache import CachedDataSource, DataOrigin, FreshnessStatus
from elile.providers import (
    CacheEntry,
    CacheFreshnessConfig,
    CacheLookupResult,
    CacheStats,
    ProviderCacheService,
    ProviderResult,
)


# =============================================================================
# CacheFreshnessConfig Tests
# =============================================================================


class TestCacheFreshnessConfig:
    """Tests for CacheFreshnessConfig model."""

    def test_defaults(self):
        """Test default configuration values."""
        config = CacheFreshnessConfig()
        assert config.fresh_duration == timedelta(days=7)
        assert config.stale_duration == timedelta(days=30)

    def test_custom_values(self):
        """Test custom configuration values."""
        config = CacheFreshnessConfig(
            fresh_duration=timedelta(days=14),
            stale_duration=timedelta(days=60),
        )
        assert config.fresh_duration == timedelta(days=14)
        assert config.stale_duration == timedelta(days=60)

    def test_total_usable_duration(self):
        """Test total_usable_duration property."""
        config = CacheFreshnessConfig(
            fresh_duration=timedelta(days=7),
            stale_duration=timedelta(days=30),
        )
        assert config.total_usable_duration == timedelta(days=37)


# =============================================================================
# CacheEntry Tests
# =============================================================================


class TestCacheEntry:
    """Tests for CacheEntry dataclass."""

    @pytest.fixture
    def fresh_entry(self):
        """Create a fresh cache entry."""
        now = datetime.now(UTC)
        return CacheEntry(
            cache_id=uuid4(),
            entity_id=uuid4(),
            provider_id="sterling",
            check_type="criminal_national",
            freshness=FreshnessStatus.FRESH,
            acquired_at=now - timedelta(hours=1),
            fresh_until=now + timedelta(days=6),
            stale_until=now + timedelta(days=36),
            normalized_data={"records": []},
            cost_incurred=Decimal("5.00"),
            cost_currency="USD",
            data_origin=DataOrigin.PAID_EXTERNAL,
        )

    @pytest.fixture
    def stale_entry(self):
        """Create a stale cache entry."""
        now = datetime.now(UTC)
        return CacheEntry(
            cache_id=uuid4(),
            entity_id=uuid4(),
            provider_id="sterling",
            check_type="criminal_national",
            freshness=FreshnessStatus.STALE,
            acquired_at=now - timedelta(days=10),
            fresh_until=now - timedelta(days=3),
            stale_until=now + timedelta(days=20),
            normalized_data={"records": []},
            cost_incurred=Decimal("5.00"),
            cost_currency="USD",
            data_origin=DataOrigin.PAID_EXTERNAL,
        )

    def test_is_usable_fresh(self, fresh_entry):
        """Test is_usable returns True for fresh entries."""
        assert fresh_entry.is_usable is True

    def test_is_usable_stale(self, stale_entry):
        """Test is_usable returns True for stale entries."""
        assert stale_entry.is_usable is True

    def test_is_usable_expired(self, fresh_entry):
        """Test is_usable returns False for expired entries."""
        fresh_entry.freshness = FreshnessStatus.EXPIRED
        assert fresh_entry.is_usable is False

    def test_is_fresh(self, fresh_entry, stale_entry):
        """Test is_fresh property."""
        assert fresh_entry.is_fresh is True
        assert stale_entry.is_fresh is False

    def test_age(self, fresh_entry):
        """Test age property."""
        # Entry was acquired 1 hour ago
        assert fresh_entry.age.total_seconds() >= 3600 - 10  # Allow 10s tolerance
        assert fresh_entry.age.total_seconds() <= 3610


# =============================================================================
# CacheLookupResult Tests
# =============================================================================


class TestCacheLookupResult:
    """Tests for CacheLookupResult dataclass."""

    def test_miss(self):
        """Test cache miss result."""
        result = CacheLookupResult(hit=False)
        assert result.hit is False
        assert result.entry is None
        assert result.is_fresh_hit is False
        assert result.is_stale_hit is False

    def test_fresh_hit(self):
        """Test fresh cache hit."""
        entry = CacheEntry(
            cache_id=uuid4(),
            entity_id=uuid4(),
            provider_id="test",
            check_type="test",
            freshness=FreshnessStatus.FRESH,
            acquired_at=datetime.now(UTC),
            fresh_until=datetime.now(UTC) + timedelta(days=7),
            stale_until=datetime.now(UTC) + timedelta(days=30),
            normalized_data={},
            cost_incurred=Decimal("0"),
            cost_currency="USD",
            data_origin=DataOrigin.PAID_EXTERNAL,
        )
        result = CacheLookupResult(hit=True, entry=entry, freshness=FreshnessStatus.FRESH)

        assert result.hit is True
        assert result.is_fresh_hit is True
        assert result.is_stale_hit is False

    def test_stale_hit(self):
        """Test stale cache hit."""
        entry = CacheEntry(
            cache_id=uuid4(),
            entity_id=uuid4(),
            provider_id="test",
            check_type="test",
            freshness=FreshnessStatus.STALE,
            acquired_at=datetime.now(UTC) - timedelta(days=10),
            fresh_until=datetime.now(UTC) - timedelta(days=3),
            stale_until=datetime.now(UTC) + timedelta(days=20),
            normalized_data={},
            cost_incurred=Decimal("0"),
            cost_currency="USD",
            data_origin=DataOrigin.PAID_EXTERNAL,
        )
        result = CacheLookupResult(hit=True, entry=entry, freshness=FreshnessStatus.STALE)

        assert result.hit is True
        assert result.is_fresh_hit is False
        assert result.is_stale_hit is True


# =============================================================================
# CacheStats Tests
# =============================================================================


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_initial_values(self):
        """Test initial statistics values."""
        stats = CacheStats()
        assert stats.lookups == 0
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.stores == 0

    def test_hit_rate_empty(self):
        """Test hit_rate with no lookups."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0

    def test_hit_rate(self):
        """Test hit_rate calculation."""
        stats = CacheStats(lookups=100, hits=75)
        assert stats.hit_rate == 0.75

    def test_fresh_hit_rate(self):
        """Test fresh_hit_rate calculation."""
        stats = CacheStats(lookups=100, hits=75, fresh_hits=50)
        assert stats.fresh_hit_rate == 0.50


# =============================================================================
# ProviderCacheService Tests
# =============================================================================


class TestProviderCacheService:
    """Tests for ProviderCacheService class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        return session

    @pytest.fixture
    def mock_encryptor(self):
        """Create mock encryptor."""
        encryptor = MagicMock()
        encryptor.encrypt = MagicMock(return_value=b"encrypted_data")
        encryptor.decrypt = MagicMock(return_value=b"decrypted_data")
        return encryptor

    @pytest.fixture
    def cache_service(self, mock_session, mock_encryptor):
        """Create cache service with mocks."""
        return ProviderCacheService(
            session=mock_session,
            encryptor=mock_encryptor,
        )

    def test_get_freshness_config_criminal(self, cache_service):
        """Test freshness config for criminal checks."""
        config = cache_service._get_freshness_config("criminal_national")
        assert config.fresh_duration == timedelta(days=7)

    def test_get_freshness_config_credit(self, cache_service):
        """Test freshness config for credit checks."""
        config = cache_service._get_freshness_config("credit_report")
        assert config.fresh_duration == timedelta(days=30)

    def test_get_freshness_config_employment(self, cache_service):
        """Test freshness config for employment checks."""
        config = cache_service._get_freshness_config("employment_verification")
        assert config.fresh_duration == timedelta(days=30)

    def test_get_freshness_config_education(self, cache_service):
        """Test freshness config for education checks."""
        config = cache_service._get_freshness_config("education_degree")
        assert config.fresh_duration == timedelta(days=90)

    def test_get_freshness_config_default(self, cache_service):
        """Test default freshness config."""
        config = cache_service._get_freshness_config("unknown_check_type")
        assert config.fresh_duration == timedelta(days=7)

    def test_compute_freshness_status_fresh(self, cache_service):
        """Test computing freshness status - fresh."""
        now = datetime.now(UTC)
        status = cache_service._compute_freshness_status(
            acquired_at=now - timedelta(hours=1),
            fresh_until=now + timedelta(days=6),
            stale_until=now + timedelta(days=30),
        )
        assert status == FreshnessStatus.FRESH

    def test_compute_freshness_status_stale(self, cache_service):
        """Test computing freshness status - stale."""
        now = datetime.now(UTC)
        status = cache_service._compute_freshness_status(
            acquired_at=now - timedelta(days=10),
            fresh_until=now - timedelta(days=3),
            stale_until=now + timedelta(days=20),
        )
        assert status == FreshnessStatus.STALE

    def test_compute_freshness_status_expired(self, cache_service):
        """Test computing freshness status - expired."""
        now = datetime.now(UTC)
        status = cache_service._compute_freshness_status(
            acquired_at=now - timedelta(days=60),
            fresh_until=now - timedelta(days=53),
            stale_until=now - timedelta(days=23),
        )
        assert status == FreshnessStatus.EXPIRED

    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service):
        """Test cache miss."""
        entity_id = uuid4()

        with patch.object(
            cache_service._repository, "get_fresh_entry", new_callable=AsyncMock
        ) as mock_fresh:
            mock_fresh.return_value = None

            with patch.object(
                cache_service._repository, "get_for_entity", new_callable=AsyncMock
            ) as mock_entity:
                mock_entity.return_value = []

                result = await cache_service.get(
                    entity_id=entity_id,
                    provider_id="sterling",
                    check_type="criminal_national",
                )

                assert result.hit is False
                assert result.entry is None
                assert cache_service.stats.misses == 1

    @pytest.mark.asyncio
    async def test_get_fresh_hit(self, cache_service):
        """Test fresh cache hit."""
        entity_id = uuid4()
        now = datetime.now(UTC)

        mock_cached = MagicMock(spec=CachedDataSource)
        mock_cached.cache_id = uuid4()
        mock_cached.entity_id = entity_id
        mock_cached.provider_id = "sterling"
        mock_cached.check_type = "criminal_national"
        mock_cached.data_origin = DataOrigin.PAID_EXTERNAL.value
        mock_cached.customer_id = None
        mock_cached.acquired_at = now - timedelta(hours=1)
        mock_cached.fresh_until = now + timedelta(days=6)
        mock_cached.stale_until = now + timedelta(days=36)
        mock_cached.normalized_data = {"records": []}
        mock_cached.cost_incurred = Decimal("5.00")
        mock_cached.cost_currency = "USD"

        with patch.object(
            cache_service._repository, "get_fresh_entry", new_callable=AsyncMock
        ) as mock_fresh:
            mock_fresh.return_value = mock_cached

            result = await cache_service.get(
                entity_id=entity_id,
                provider_id="sterling",
                check_type="criminal_national",
            )

            assert result.hit is True
            assert result.is_fresh_hit is True
            assert result.entry is not None
            assert result.entry.provider_id == "sterling"
            assert cache_service.stats.hits == 1
            assert cache_service.stats.fresh_hits == 1

    @pytest.mark.asyncio
    async def test_store(self, cache_service, mock_session):
        """Test storing provider result in cache."""
        entity_id = uuid4()
        provider_result = ProviderResult(
            provider_id="sterling",
            check_type=CheckType.CRIMINAL_NATIONAL,
            locale=Locale.US,
            success=True,
            normalized_data={"records": []},
            cost_incurred=Decimal("5.00"),
        )

        entry = await cache_service.store(
            entity_id=entity_id,
            result=provider_result,
        )

        assert entry.provider_id == "sterling"
        assert entry.check_type == "criminal_national"
        assert entry.freshness == FreshnessStatus.FRESH
        assert entry.data_origin == DataOrigin.PAID_EXTERNAL
        assert cache_service.stats.stores == 1
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_with_tenant(self, cache_service, mock_session):
        """Test storing customer-provided data with tenant."""
        entity_id = uuid4()
        tenant_id = uuid4()
        provider_result = ProviderResult(
            provider_id="customer_upload",
            check_type=CheckType.IDENTITY_BASIC,
            locale=Locale.US,
            success=True,
            normalized_data={"name": "John Doe"},
            cost_incurred=Decimal("0.00"),
        )

        entry = await cache_service.store(
            entity_id=entity_id,
            result=provider_result,
            tenant_id=tenant_id,
            data_origin=DataOrigin.CUSTOMER_PROVIDED,
        )

        assert entry.data_origin == DataOrigin.CUSTOMER_PROVIDED
        assert entry.tenant_id == tenant_id

    @pytest.mark.asyncio
    async def test_invalidate(self, cache_service):
        """Test invalidating cache entries."""
        entity_id = uuid4()

        mock_entry = MagicMock()
        mock_entry.cache_id = uuid4()
        mock_entry.check_type = "criminal_national"

        with patch.object(
            cache_service._repository, "get_for_entity", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [mock_entry]

            with patch.object(
                cache_service._repository, "mark_expired", new_callable=AsyncMock
            ) as mock_expire:
                mock_expire.return_value = True

                count = await cache_service.invalidate(
                    entity_id=entity_id,
                    provider_id="sterling",
                )

                assert count == 1
                assert cache_service.stats.invalidations == 1
                mock_expire.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_fetch_cache_hit(self, cache_service):
        """Test get_or_fetch with cache hit."""
        entity_id = uuid4()
        now = datetime.now(UTC)

        mock_cached = MagicMock(spec=CachedDataSource)
        mock_cached.cache_id = uuid4()
        mock_cached.entity_id = entity_id
        mock_cached.provider_id = "sterling"
        mock_cached.check_type = "criminal_national"
        mock_cached.data_origin = DataOrigin.PAID_EXTERNAL.value
        mock_cached.customer_id = None
        mock_cached.acquired_at = now - timedelta(hours=1)
        mock_cached.fresh_until = now + timedelta(days=6)
        mock_cached.stale_until = now + timedelta(days=36)
        mock_cached.normalized_data = {"records": ["record1"]}
        mock_cached.cost_incurred = Decimal("5.00")
        mock_cached.cost_currency = "USD"

        fetch_fn = AsyncMock()  # Should not be called

        with patch.object(
            cache_service._repository, "get_fresh_entry", new_callable=AsyncMock
        ) as mock_fresh:
            mock_fresh.return_value = mock_cached

            result, was_cached = await cache_service.get_or_fetch(
                entity_id=entity_id,
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                fetch_fn=fetch_fn,
            )

            assert was_cached is True
            assert result.normalized_data == {"records": ["record1"]}
            fetch_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_or_fetch_cache_miss(self, cache_service, mock_session):
        """Test get_or_fetch with cache miss."""
        entity_id = uuid4()

        fetch_fn = AsyncMock(
            return_value=ProviderResult(
                provider_id="sterling",
                check_type=CheckType.CRIMINAL_NATIONAL,
                locale=Locale.US,
                success=True,
                normalized_data={"records": ["new_record"]},
                cost_incurred=Decimal("5.00"),
            )
        )

        with patch.object(
            cache_service._repository, "get_fresh_entry", new_callable=AsyncMock
        ) as mock_fresh:
            mock_fresh.return_value = None

            with patch.object(
                cache_service._repository, "get_for_entity", new_callable=AsyncMock
            ) as mock_entity:
                mock_entity.return_value = []

                result, was_cached = await cache_service.get_or_fetch(
                    entity_id=entity_id,
                    provider_id="sterling",
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    locale=Locale.US,
                    fetch_fn=fetch_fn,
                )

                assert was_cached is False
                assert result.normalized_data == {"records": ["new_record"]}
                fetch_fn.assert_called_once()
                mock_session.add.assert_called_once()  # Stored in cache

    @pytest.mark.asyncio
    async def test_update_freshness(self, cache_service):
        """Test updating freshness status."""
        with patch.object(
            cache_service._repository, "update_freshness_batch", new_callable=AsyncMock
        ) as mock_update:
            mock_update.return_value = (5, 3)

            stale_count, expired_count = await cache_service.update_freshness()

            assert stale_count == 5
            assert expired_count == 3
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired(self, cache_service):
        """Test cleaning up expired entries."""
        with patch.object(
            cache_service._repository, "delete_expired", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = 10

            deleted = await cache_service.cleanup_expired(older_than=timedelta(days=90))

            assert deleted == 10
            mock_delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_stats_by_freshness(self, cache_service):
        """Test getting stats by freshness."""
        expected_stats = {
            FreshnessStatus.FRESH: 100,
            FreshnessStatus.STALE: 50,
            FreshnessStatus.EXPIRED: 25,
        }

        with patch.object(
            cache_service._repository, "count_by_freshness", new_callable=AsyncMock
        ) as mock_count:
            mock_count.return_value = expected_stats

            stats = await cache_service.get_stats_by_freshness()

            assert stats == expected_stats

    def test_reset_stats(self, cache_service):
        """Test resetting statistics."""
        cache_service._stats.lookups = 100
        cache_service._stats.hits = 75

        cache_service.reset_stats()

        assert cache_service.stats.lookups == 0
        assert cache_service.stats.hits == 0


# =============================================================================
# Tenant Isolation Tests
# =============================================================================


class TestTenantIsolation:
    """Tests for tenant isolation in caching."""

    @pytest.fixture
    def cache_service(self):
        """Create cache service with mocks."""
        session = AsyncMock()
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.refresh = AsyncMock()
        encryptor = MagicMock()
        encryptor.encrypt = MagicMock(return_value=b"encrypted")
        return ProviderCacheService(session=session, encryptor=encryptor)

    @pytest.mark.asyncio
    async def test_tenant_mismatch_treated_as_miss(self, cache_service):
        """Test that customer-provided data from different tenant is a miss."""
        entity_id = uuid4()
        tenant_a = uuid4()
        tenant_b = uuid4()
        now = datetime.now(UTC)

        # Cache entry belongs to tenant_a
        mock_cached = MagicMock(spec=CachedDataSource)
        mock_cached.cache_id = uuid4()
        mock_cached.entity_id = entity_id
        mock_cached.provider_id = "customer"
        mock_cached.check_type = "identity"
        mock_cached.data_origin = DataOrigin.CUSTOMER_PROVIDED.value
        mock_cached.customer_id = tenant_a  # Belongs to tenant_a
        mock_cached.acquired_at = now - timedelta(hours=1)
        mock_cached.fresh_until = now + timedelta(days=6)
        mock_cached.stale_until = now + timedelta(days=36)
        mock_cached.normalized_data = {"name": "John"}
        mock_cached.cost_incurred = Decimal("0")
        mock_cached.cost_currency = "USD"

        with patch.object(
            cache_service._repository, "get_fresh_entry", new_callable=AsyncMock
        ) as mock_fresh:
            mock_fresh.return_value = mock_cached

            # Request from tenant_b should be treated as miss
            result = await cache_service.get(
                entity_id=entity_id,
                provider_id="customer",
                check_type="identity",
                tenant_id=tenant_b,  # Different tenant!
            )

            assert result.hit is False
            assert cache_service.stats.misses == 1

    @pytest.mark.asyncio
    async def test_paid_external_shared_across_tenants(self, cache_service):
        """Test that paid external data is shared across tenants."""
        entity_id = uuid4()
        tenant_a = uuid4()
        tenant_b = uuid4()
        now = datetime.now(UTC)

        # Cache entry is paid external (shared)
        mock_cached = MagicMock(spec=CachedDataSource)
        mock_cached.cache_id = uuid4()
        mock_cached.entity_id = entity_id
        mock_cached.provider_id = "sterling"
        mock_cached.check_type = "criminal"
        mock_cached.data_origin = DataOrigin.PAID_EXTERNAL.value
        mock_cached.customer_id = None  # Shared data
        mock_cached.acquired_at = now - timedelta(hours=1)
        mock_cached.fresh_until = now + timedelta(days=6)
        mock_cached.stale_until = now + timedelta(days=36)
        mock_cached.normalized_data = {"records": []}
        mock_cached.cost_incurred = Decimal("5.00")
        mock_cached.cost_currency = "USD"

        with patch.object(
            cache_service._repository, "get_fresh_entry", new_callable=AsyncMock
        ) as mock_fresh:
            mock_fresh.return_value = mock_cached

            # Both tenants should get cache hit
            result_a = await cache_service.get(
                entity_id=entity_id,
                provider_id="sterling",
                check_type="criminal",
                tenant_id=tenant_a,
            )

            assert result_a.hit is True

            # Reset stats for second lookup
            cache_service.reset_stats()

            result_b = await cache_service.get(
                entity_id=entity_id,
                provider_id="sterling",
                check_type="criminal",
                tenant_id=tenant_b,
            )

            assert result_b.hit is True
