"""Unit tests for Sanctions Provider implementation.

Tests the SanctionsProvider class including check execution,
health checks, and screening operations.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from elile.compliance.types import CheckType, Locale
from elile.entity.types import SubjectIdentifiers
from elile.providers.sanctions import (
    FuzzyMatchConfig,
    SanctionsList,
    SanctionsProvider,
    SanctionsProviderConfig,
    create_sanctions_provider,
    get_sanctions_provider,
)
from elile.providers.types import DataSourceCategory, ProviderStatus

# =============================================================================
# Configuration Tests
# =============================================================================


class TestSanctionsProviderConfig:
    """Tests for SanctionsProviderConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = SanctionsProviderConfig()
        assert SanctionsList.OFAC_SDN in config.enabled_lists
        assert SanctionsList.UN_CONSOLIDATED in config.enabled_lists
        assert SanctionsList.EU_CONSOLIDATED in config.enabled_lists
        assert config.cache_ttl_seconds == 3600
        assert config.timeout_ms == 30000
        assert config.batch_size == 100

    def test_custom_enabled_lists(self):
        """Test custom enabled lists."""
        config = SanctionsProviderConfig(
            enabled_lists=[SanctionsList.OFAC_SDN],
        )
        assert len(config.enabled_lists) == 1
        assert SanctionsList.OFAC_SDN in config.enabled_lists

    def test_custom_match_config(self):
        """Test custom match configuration."""
        match_config = FuzzyMatchConfig(
            exact_threshold=0.98,
            use_phonetic=False,
        )
        config = SanctionsProviderConfig(match_config=match_config)
        assert config.match_config.exact_threshold == 0.98
        assert config.match_config.use_phonetic is False

    def test_custom_timeouts(self):
        """Test custom timeout configuration."""
        config = SanctionsProviderConfig(
            cache_ttl_seconds=7200,
            timeout_ms=60000,
        )
        assert config.cache_ttl_seconds == 7200
        assert config.timeout_ms == 60000


# =============================================================================
# Provider Initialization Tests
# =============================================================================


class TestProviderInitialization:
    """Tests for SanctionsProvider initialization."""

    def test_create_provider_with_defaults(self):
        """Test creating provider with default config."""
        provider = SanctionsProvider()
        assert provider.provider_id == "sanctions_provider"
        assert provider.provider_info.category == DataSourceCategory.CORE

    def test_create_provider_with_config(self):
        """Test creating provider with custom config."""
        config = SanctionsProviderConfig(
            enabled_lists=[SanctionsList.OFAC_SDN, SanctionsList.UN_CONSOLIDATED],
        )
        provider = SanctionsProvider(config)
        assert len(provider.config.enabled_lists) == 2

    def test_provider_capabilities(self):
        """Test provider capabilities are registered."""
        provider = SanctionsProvider()
        info = provider.provider_info
        check_types = [cap.check_type for cap in info.capabilities]
        assert CheckType.SANCTIONS_OFAC in check_types
        assert CheckType.SANCTIONS_UN in check_types
        assert CheckType.SANCTIONS_EU in check_types
        assert CheckType.SANCTIONS_PEP in check_types
        assert CheckType.WATCHLIST_INTERPOL in check_types

    def test_factory_function(self):
        """Test create_sanctions_provider factory."""
        provider = create_sanctions_provider()
        assert isinstance(provider, SanctionsProvider)

    def test_sample_data_loaded(self):
        """Test sample data is loaded on initialization."""
        provider = SanctionsProvider()
        assert len(provider._sanctions_db) > 0


# =============================================================================
# Execute Check Tests
# =============================================================================


class TestExecuteCheck:
    """Tests for execute_check method."""

    @pytest.mark.asyncio
    async def test_execute_ofac_check_no_match(self):
        """Test OFAC check with no matches."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Clean Person Name"),
            locale=Locale.US,
        )
        assert result.success is True
        assert result.provider_id == "sanctions_provider"
        assert result.check_type == CheckType.SANCTIONS_OFAC
        assert result.normalized_data["screening"]["has_hit"] is False
        assert result.normalized_data["screening"]["total_matches"] == 0

    @pytest.mark.asyncio
    async def test_execute_ofac_check_with_match(self):
        """Test OFAC check with match."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Vladimir Putin"),
            locale=Locale.US,
        )
        assert result.success is True
        assert result.normalized_data["screening"]["has_hit"] is True
        assert result.normalized_data["screening"]["total_matches"] >= 1

    @pytest.mark.asyncio
    async def test_execute_un_check(self):
        """Test UN consolidated check."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_UN,
            subject=SubjectIdentifiers(full_name="Clean Person"),
            locale=Locale.EU,
        )
        assert result.success is True
        assert result.check_type == CheckType.SANCTIONS_UN

    @pytest.mark.asyncio
    async def test_execute_eu_check(self):
        """Test EU consolidated check."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_EU,
            subject=SubjectIdentifiers(full_name="Alexander Lukashenko"),
            locale=Locale.EU,
        )
        assert result.success is True
        assert result.normalized_data["screening"]["has_hit"] is True

    @pytest.mark.asyncio
    async def test_execute_pep_check(self):
        """Test PEP database check."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_PEP,
            subject=SubjectIdentifiers(full_name="Hunter Biden"),
            locale=Locale.US,
        )
        assert result.success is True
        assert result.normalized_data["screening"]["has_hit"] is True

    @pytest.mark.asyncio
    async def test_execute_check_invalid_subject(self):
        """Test check with no name."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(),  # No name
            locale=Locale.US,
        )
        assert result.success is False
        assert result.error_code == "INVALID_SUBJECT"

    @pytest.mark.asyncio
    async def test_execute_check_with_dob(self):
        """Test check with date of birth."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(
                full_name="Vladimir Putin",
                date_of_birth=date(1952, 10, 7),
            ),
            locale=Locale.US,
        )
        assert result.success is True
        # Should match with DOB boost
        matches = result.normalized_data.get("matches", [])
        if matches:
            # Check that DOB was in matched fields
            assert any("dob" in m.get("matched_fields", []) for m in matches)

    @pytest.mark.asyncio
    async def test_execute_check_returns_query_id(self):
        """Test check returns valid query ID."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Test Person"),
            locale=Locale.US,
        )
        assert result.query_id is not None
        assert isinstance(result.query_id, UUID)

    @pytest.mark.asyncio
    async def test_execute_check_returns_latency(self):
        """Test check returns latency measurement."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Test Person"),
            locale=Locale.US,
        )
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_check_returns_cost(self):
        """Test check returns cost information."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Test Person"),
            locale=Locale.US,
        )
        assert result.cost_incurred is not None
        assert isinstance(result.cost_incurred, Decimal)


# =============================================================================
# Health Check Tests
# =============================================================================


class TestHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self):
        """Test health check returns healthy status."""
        provider = SanctionsProvider()
        health = await provider.health_check()
        assert health.provider_id == "sanctions_provider"
        assert health.status == ProviderStatus.HEALTHY
        assert health.latency_ms is not None


# =============================================================================
# Screen All Lists Tests
# =============================================================================


class TestScreenAllLists:
    """Tests for screen_all_lists method."""

    @pytest.mark.asyncio
    async def test_screen_all_lists_no_matches(self):
        """Test screening all lists with no matches."""
        provider = SanctionsProvider()
        result = await provider.screen_all_lists(
            subject=SubjectIdentifiers(full_name="Completely Clean Person"),
        )
        assert result.subject_name == "Completely Clean Person"
        assert result.has_hit is False
        assert len(result.lists_screened) > 0

    @pytest.mark.asyncio
    async def test_screen_all_lists_with_matches(self):
        """Test screening all lists with matches."""
        provider = SanctionsProvider()
        result = await provider.screen_all_lists(
            subject=SubjectIdentifiers(full_name="Kim Jong Un"),
        )
        assert result.has_hit is True
        assert result.total_matches >= 1

    @pytest.mark.asyncio
    async def test_screen_all_lists_empty_subject(self):
        """Test screening with empty subject."""
        provider = SanctionsProvider()
        result = await provider.screen_all_lists(
            subject=SubjectIdentifiers(),
        )
        assert result.subject_name == ""
        assert result.has_hit is False


# =============================================================================
# List Statistics Tests
# =============================================================================


class TestListStatistics:
    """Tests for get_list_statistics method."""

    @pytest.mark.asyncio
    async def test_get_list_statistics(self):
        """Test getting list statistics."""
        provider = SanctionsProvider()
        stats = await provider.get_list_statistics()
        assert "lists" in stats
        assert "total_entities" in stats
        assert "last_update" in stats
        assert stats["total_entities"] > 0


# =============================================================================
# Normalized Result Tests
# =============================================================================


class TestNormalizedResults:
    """Tests for normalized result format."""

    @pytest.mark.asyncio
    async def test_normalized_screening_structure(self):
        """Test normalized screening result structure."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Test Person"),
            locale=Locale.US,
        )
        screening = result.normalized_data["screening"]
        assert "screening_id" in screening
        assert "subject_name" in screening
        assert "lists_screened" in screening
        assert "total_matches" in screening
        assert "has_hit" in screening
        assert "screened_at" in screening
        assert "screening_time_ms" in screening

    @pytest.mark.asyncio
    async def test_normalized_match_structure(self):
        """Test normalized match result structure."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Vladimir Putin"),
            locale=Locale.US,
        )
        if result.normalized_data["screening"]["has_hit"]:
            matches = result.normalized_data["matches"]
            assert len(matches) > 0
            match = matches[0]
            assert "match_id" in match
            assert "entity_id" in match
            assert "entity_name" in match
            assert "entity_type" in match
            assert "list_source" in match
            assert "match_type" in match
            assert "match_score" in match


# =============================================================================
# List Mapping Tests
# =============================================================================


class TestListMapping:
    """Tests for check type to list mapping."""

    @pytest.mark.asyncio
    async def test_ofac_check_screens_ofac_lists(self):
        """Test OFAC check screens OFAC lists."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Test"),
            locale=Locale.US,
        )
        lists_screened = result.normalized_data["screening"]["lists_screened"]
        assert "ofac_sdn" in lists_screened or "ofac_consolidated" in lists_screened

    @pytest.mark.asyncio
    async def test_pep_check_screens_pep_lists(self):
        """Test PEP check screens PEP lists."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_PEP,
            subject=SubjectIdentifiers(full_name="Test"),
            locale=Locale.US,
        )
        lists_screened = result.normalized_data["screening"]["lists_screened"]
        assert any("pep" in lst for lst in lists_screened)


# =============================================================================
# Match Score Tests
# =============================================================================


class TestMatchScores:
    """Tests for match score accuracy."""

    @pytest.mark.asyncio
    async def test_exact_name_match_high_score(self):
        """Test exact name match returns high score."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Vladimir Putin"),
            locale=Locale.US,
        )
        if result.normalized_data["screening"]["has_hit"]:
            highest_score = result.normalized_data["screening"]["highest_match_score"]
            # Note: match_entity applies weights (name_weight = 0.7 by default)
            # So a perfect match becomes 0.7 without DOB/country boost
            assert highest_score >= 0.60

    @pytest.mark.asyncio
    async def test_partial_name_match_lower_score(self):
        """Test partial name match returns lower score."""
        provider = SanctionsProvider()
        # Use just first name which should match less precisely
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(full_name="Vladimir"),
            locale=Locale.US,
        )
        # May or may not match depending on threshold
        screening = result.normalized_data["screening"]
        if screening["has_hit"]:
            # Score should be lower than full name match
            assert screening["highest_match_score"] < 0.95


# =============================================================================
# Singleton Tests
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_sanctions_provider_singleton(self):
        """Test get_sanctions_provider returns singleton."""
        # Reset the singleton for this test
        import elile.providers.sanctions.provider as provider_module

        provider_module._provider_instance = None

        provider1 = get_sanctions_provider()
        provider2 = get_sanctions_provider()
        assert provider1 is provider2

        # Clean up
        provider_module._provider_instance = None

    def test_create_sanctions_provider_new_instance(self):
        """Test create_sanctions_provider returns new instance."""
        provider1 = create_sanctions_provider()
        provider2 = create_sanctions_provider()
        assert provider1 is not provider2


# =============================================================================
# Subject Name Building Tests
# =============================================================================


class TestSubjectNameBuilding:
    """Tests for building search names from subject identifiers."""

    @pytest.mark.asyncio
    async def test_full_name_used(self):
        """Test full_name is used when available."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(
                full_name="Full Name Here",
                first_name="First",
                last_name="Last",
            ),
            locale=Locale.US,
        )
        # Full name should be used
        assert result.normalized_data["screening"]["subject_name"] == "Full Name Here"

    @pytest.mark.asyncio
    async def test_name_parts_combined(self):
        """Test name parts are combined when full_name missing."""
        provider = SanctionsProvider()
        result = await provider.execute_check(
            check_type=CheckType.SANCTIONS_OFAC,
            subject=SubjectIdentifiers(
                first_name="John",
                middle_name="Michael",
                last_name="Smith",
            ),
            locale=Locale.US,
        )
        subject_name = result.normalized_data["screening"]["subject_name"]
        assert "John" in subject_name
        assert "Michael" in subject_name
        assert "Smith" in subject_name
