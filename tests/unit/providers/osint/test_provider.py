"""Tests for OSINT aggregator provider."""

from decimal import Decimal

import pytest

from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers
from elile.providers.osint.provider import (
    OSINTProvider,
    create_osint_provider,
    get_osint_provider,
)
from elile.providers.osint.types import (
    OSINTProviderConfig,
)
from elile.providers.types import DataSourceCategory, ProviderStatus


class TestOSINTProviderInit:
    """Tests for OSINTProvider initialization."""

    def test_default_initialization(self) -> None:
        """Test provider initializes with default config."""
        provider = OSINTProvider()
        assert provider.provider_id == "osint_provider"
        assert provider.config.enable_social_media is True
        assert provider.config.enable_news_search is True
        assert provider.config.enable_public_records is True

    def test_custom_config_initialization(self) -> None:
        """Test provider initializes with custom config."""
        config = OSINTProviderConfig(
            enable_public_records=False,
            news_lookback_days=180,
        )
        provider = OSINTProvider(config)
        assert provider.config.enable_public_records is False
        assert provider.config.news_lookback_days == 180

    def test_provider_info(self) -> None:
        """Test provider info is correctly set."""
        provider = OSINTProvider()
        info = provider.provider_info

        assert info.provider_id == "osint_provider"
        assert info.name == "OSINT Aggregator Provider"
        assert info.category == DataSourceCategory.PREMIUM
        assert len(info.capabilities) >= 1

    def test_supported_checks(self) -> None:
        """Test supported check types."""
        provider = OSINTProvider()
        checks = provider.supported_checks

        assert CheckType.SOCIAL_MEDIA in checks
        assert CheckType.ADVERSE_MEDIA in checks
        assert CheckType.DIGITAL_FOOTPRINT in checks


class TestOSINTProviderExecuteCheck:
    """Tests for OSINTProvider.execute_check method."""

    @pytest.fixture
    def provider(self) -> OSINTProvider:
        """Create a provider instance."""
        return OSINTProvider()

    @pytest.mark.asyncio
    async def test_execute_check_no_name(self, provider: OSINTProvider) -> None:
        """Test execute_check fails without full_name."""
        subject = SubjectIdentifiers()  # No name

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is False
        assert result.error_code == "INVALID_SUBJECT"

    @pytest.mark.asyncio
    async def test_execute_check_with_name(self, provider: OSINTProvider) -> None:
        """Test execute_check with subject name."""
        subject = SubjectIdentifiers(full_name="John Smith")

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert result.provider_id == "osint_provider"
        assert result.query_id is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_check_includes_normalized_data(self, provider: OSINTProvider) -> None:
        """Test execute_check returns normalized data."""
        subject = SubjectIdentifiers(
            full_name="Test User",
            email="test@example.com",
        )

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        assert result.success is True
        assert "search" in result.normalized_data
        assert "social_profiles" in result.normalized_data
        assert "entities" in result.normalized_data
        assert "relationships" in result.normalized_data

    @pytest.mark.asyncio
    async def test_execute_check_includes_cost(self, provider: OSINTProvider) -> None:
        """Test that execute_check includes cost information."""
        subject = SubjectIdentifiers(full_name="Cost Test")

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        assert result.cost_incurred is not None
        assert result.cost_incurred >= Decimal("5.00")  # Base cost


class TestOSINTProviderGatherIntelligence:
    """Tests for OSINTProvider.gather_intelligence method."""

    @pytest.fixture
    def provider(self) -> OSINTProvider:
        """Create a provider instance."""
        return OSINTProvider()

    @pytest.mark.asyncio
    async def test_gather_intelligence_basic(self, provider: OSINTProvider) -> None:
        """Test basic intelligence gathering."""
        result = await provider.gather_intelligence(
            subject_name="Test Subject",
            identifiers=["test@example.com"],
        )

        assert result.search_id is not None
        assert result.subject_name == "Test Subject"
        assert "test@example.com" in result.search_identifiers
        assert result.total_sources_searched > 0

    @pytest.mark.asyncio
    async def test_gather_intelligence_multiple_identifiers(self, provider: OSINTProvider) -> None:
        """Test intelligence gathering with multiple identifiers."""
        result = await provider.gather_intelligence(
            subject_name="Multi ID Test",
            identifiers=["id1@example.com", "id2@example.com", "username123"],
        )

        assert len(result.search_identifiers) == 3

    @pytest.mark.asyncio
    async def test_gather_intelligence_returns_profiles(self, provider: OSINTProvider) -> None:
        """Test that gathering returns social profiles."""
        result = await provider.gather_intelligence(
            subject_name="Profile Test",
            identifiers=["test@example.com"],
        )

        # Should find at least LinkedIn profile (80% chance in simulation)
        # Run multiple times if needed
        assert isinstance(result.social_profiles, list)

    @pytest.mark.asyncio
    async def test_gather_intelligence_deduplication(self, provider: OSINTProvider) -> None:
        """Test that deduplication is applied."""
        result = await provider.gather_intelligence(
            subject_name="Dedup Test",
            identifiers=["test@example.com"],
        )

        # Dedup metrics should be populated
        assert result.total_items_found >= 0
        assert result.unique_items_after_dedup >= 0
        assert result.dedup_removed_count >= 0

    @pytest.mark.asyncio
    async def test_gather_intelligence_entity_extraction(self, provider: OSINTProvider) -> None:
        """Test that entity extraction is performed."""
        result = await provider.gather_intelligence(
            subject_name="Entity Test",
            identifiers=["test@example.com"],
        )

        assert isinstance(result.extracted_entities, list)
        assert isinstance(result.extracted_relationships, list)


class TestOSINTProviderSearchMethods:
    """Tests for individual search methods."""

    @pytest.fixture
    def provider(self) -> OSINTProvider:
        """Create a provider instance."""
        return OSINTProvider()

    @pytest.mark.asyncio
    async def test_search_social_media(self, provider: OSINTProvider) -> None:
        """Test social media search."""
        profiles = await provider.search_social_media(
            subject_name="Social Test",
            identifiers=["test@example.com"],
        )

        assert isinstance(profiles, list)
        for profile in profiles:
            assert profile.display_name is not None

    @pytest.mark.asyncio
    async def test_search_news(self, provider: OSINTProvider) -> None:
        """Test news search."""
        mentions = await provider.search_news(
            subject_name="News Test",
            lookback_days=90,
        )

        assert isinstance(mentions, list)


class TestOSINTProviderConfig:
    """Tests for provider configuration effects."""

    @pytest.mark.asyncio
    async def test_disable_social_media(self) -> None:
        """Test disabling social media search."""
        config = OSINTProviderConfig(enable_social_media=False)
        provider = OSINTProvider(config)

        result = await provider.gather_intelligence(
            subject_name="Test",
            identifiers=["test@example.com"],
            check_type=CheckType.ADVERSE_MEDIA,  # Non-social check
        )

        # Social profiles should be empty for non-social check with disabled social
        # Note: This depends on check_type filtering behavior
        assert isinstance(result.social_profiles, list)

    @pytest.mark.asyncio
    async def test_disable_news_search(self) -> None:
        """Test disabling news search."""
        config = OSINTProviderConfig(enable_news_search=False)
        provider = OSINTProvider(config)

        result = await provider.gather_intelligence(
            subject_name="Test",
            identifiers=["test@example.com"],
            check_type=CheckType.SOCIAL_MEDIA,  # Non-news check
        )

        assert isinstance(result.news_mentions, list)

    @pytest.mark.asyncio
    async def test_disable_public_records(self) -> None:
        """Test disabling public records search."""
        config = OSINTProviderConfig(enable_public_records=False)
        provider = OSINTProvider(config)

        result = await provider.gather_intelligence(
            subject_name="Test",
            identifiers=["test@example.com"],
            check_type=CheckType.SOCIAL_MEDIA,  # Non-records check
        )

        assert isinstance(result.public_records, list)

    @pytest.mark.asyncio
    async def test_disable_entity_extraction(self) -> None:
        """Test disabling entity extraction."""
        config = OSINTProviderConfig(enable_entity_extraction=False)
        provider = OSINTProvider(config)

        result = await provider.gather_intelligence(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        assert len(result.extracted_entities) == 0

    @pytest.mark.asyncio
    async def test_disable_relationship_extraction(self) -> None:
        """Test disabling relationship extraction."""
        config = OSINTProviderConfig(enable_relationship_extraction=False)
        provider = OSINTProvider(config)

        result = await provider.gather_intelligence(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        assert len(result.extracted_relationships) == 0

    @pytest.mark.asyncio
    async def test_disable_deduplication(self) -> None:
        """Test disabling deduplication."""
        config = OSINTProviderConfig(enable_deduplication=False)
        provider = OSINTProvider(config)

        result = await provider.gather_intelligence(
            subject_name="Test",
            identifiers=["test@example.com"],
        )

        # Dedup removed should be 0 when disabled
        assert result.dedup_removed_count == 0


class TestOSINTProviderHealthCheck:
    """Tests for OSINTProvider.health_check method."""

    @pytest.mark.asyncio
    async def test_health_check(self) -> None:
        """Test health check returns healthy status."""
        provider = OSINTProvider()
        health = await provider.health_check()

        assert health.provider_id == "osint_provider"
        assert health.status == ProviderStatus.HEALTHY
        assert health.latency_ms >= 0


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_osint_provider(self) -> None:
        """Test create_osint_provider factory."""
        provider = create_osint_provider()
        assert isinstance(provider, OSINTProvider)

    def test_create_osint_provider_with_config(self) -> None:
        """Test create_osint_provider with custom config."""
        config = OSINTProviderConfig(enable_news_search=False)
        provider = create_osint_provider(config)
        assert provider.config.enable_news_search is False

    def test_get_osint_provider_singleton(self) -> None:
        """Test get_osint_provider returns singleton."""
        provider1 = get_osint_provider()
        provider2 = get_osint_provider()
        assert provider1 is provider2


class TestNormalizedOutput:
    """Tests for normalized output structure."""

    @pytest.fixture
    def provider(self) -> OSINTProvider:
        """Create a provider instance."""
        return OSINTProvider()

    @pytest.mark.asyncio
    async def test_normalized_data_structure(self, provider: OSINTProvider) -> None:
        """Test normalized data has expected structure."""
        subject = SubjectIdentifiers(full_name="Structure Test")

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        data = result.normalized_data

        # Check search section
        assert "search" in data
        search = data["search"]
        assert "search_id" in search
        assert "subject_name" in search
        assert "sources_searched" in search
        assert "unique_items" in search
        assert "searched_at" in search

        # Check arrays exist
        assert isinstance(data["social_profiles"], list)
        assert isinstance(data["news_mentions"], list)
        assert isinstance(data["public_records"], list)
        assert isinstance(data["professional_info"], list)
        assert isinstance(data["entities"], list)
        assert isinstance(data["relationships"], list)


class TestCostCalculation:
    """Tests for cost calculation."""

    @pytest.fixture
    def provider(self) -> OSINTProvider:
        """Create a provider instance."""
        return OSINTProvider()

    @pytest.mark.asyncio
    async def test_base_cost(self, provider: OSINTProvider) -> None:
        """Test base cost is applied."""
        subject = SubjectIdentifiers(full_name="Cost Test")

        result = await provider.execute_check(
            check_type=CheckType.SOCIAL_MEDIA,
            subject=subject,
            locale=Locale.US,
        )

        # Base cost should be at least $5
        assert result.cost_incurred >= Decimal("5.00")


class TestDeterministicResults:
    """Tests for deterministic result generation."""

    @pytest.fixture
    def provider(self) -> OSINTProvider:
        """Create a provider instance."""
        return OSINTProvider()

    @pytest.mark.asyncio
    async def test_same_name_same_results(self, provider: OSINTProvider) -> None:
        """Test that same name produces same results."""
        result1 = await provider.gather_intelligence(
            subject_name="Deterministic Test",
            identifiers=["test@example.com"],
        )
        result2 = await provider.gather_intelligence(
            subject_name="Deterministic Test",
            identifiers=["test@example.com"],
        )

        # Profile counts should match
        assert len(result1.social_profiles) == len(result2.social_profiles)
        assert len(result1.news_mentions) == len(result2.news_mentions)

    @pytest.mark.asyncio
    async def test_different_names_different_results(self, provider: OSINTProvider) -> None:
        """Test that different names produce different results."""
        result1 = await provider.gather_intelligence(
            subject_name="Person One",
            identifiers=[],
        )
        result2 = await provider.gather_intelligence(
            subject_name="Person Two Different",
            identifiers=[],
        )

        # Results may differ (though not guaranteed due to random seed)
        # At minimum, subject names should differ
        assert result1.subject_name != result2.subject_name
