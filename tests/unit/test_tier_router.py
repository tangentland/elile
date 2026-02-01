"""Unit tests for tier router.

Tests service tier routing and data source management.
"""

import pytest
from uuid_utils import uuid7

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import Locale
from elile.providers.types import CheckType
from elile.screening.tier_router import (
    DataSourceSpec,
    DataSourceTier,
    TierCapabilities,
    TierRouter,
    TierRouterConfig,
    RoutingResult,
    create_tier_router,
    create_default_data_sources,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return TierRouterConfig(
        standard_max_queries=50,
        standard_max_degree=SearchDegree.D1,
        standard_budget_limit=100.0,
        enhanced_max_queries=200,
        enhanced_max_degree=SearchDegree.D3,
        enhanced_budget_limit=1000.0,
    )


@pytest.fixture
def core_source():
    """Create core data source."""
    return DataSourceSpec(
        source_id="core-identity",
        provider_id="provider1",
        name="Core Identity Check",
        tier=DataSourceTier.CORE,
        check_types=[CheckType.IDENTITY_BASIC],
        locales=[Locale.US],
        cost_per_query=5.0,
    )


@pytest.fixture
def premium_source():
    """Create premium data source."""
    return DataSourceSpec(
        source_id="premium-sanctions",
        provider_id="provider2",
        name="Premium Sanctions Check",
        tier=DataSourceTier.PREMIUM,
        check_types=[CheckType.SANCTIONS_OFAC],
        locales=[],  # Global
        cost_per_query=25.0,
    )


@pytest.fixture
def router(config, core_source, premium_source):
    """Create tier router with data sources."""
    router = TierRouter(config=config)
    router.add_data_source(core_source)
    router.add_data_source(premium_source)
    return router


# =============================================================================
# DataSourceSpec Tests
# =============================================================================


class TestDataSourceSpec:
    """Tests for DataSourceSpec."""

    def test_supports_check_type(self, core_source):
        """Test check type support."""
        assert core_source.supports_check(CheckType.IDENTITY_BASIC)
        assert not core_source.supports_check(CheckType.CRIMINAL_NATIONAL)

    def test_available_in_locale(self, core_source):
        """Test locale availability."""
        assert core_source.available_in_locale(Locale.US)
        assert not core_source.available_in_locale(Locale.UK)

    def test_available_in_locale_global(self, premium_source):
        """Test global source availability."""
        # Empty locales means global availability
        assert premium_source.available_in_locale(Locale.US)
        assert premium_source.available_in_locale(Locale.UK)
        assert premium_source.available_in_locale(Locale.EU)


# =============================================================================
# TierCapabilities Tests
# =============================================================================


class TestTierCapabilities:
    """Tests for TierCapabilities."""

    def test_allows_degree_standard(self):
        """Test degree checking for Standard tier."""
        capabilities = TierCapabilities(
            tier=ServiceTier.STANDARD,
            max_degree=SearchDegree.D1,
        )

        assert capabilities.allows_degree(SearchDegree.D1)
        assert not capabilities.allows_degree(SearchDegree.D2)
        assert not capabilities.allows_degree(SearchDegree.D3)

    def test_allows_degree_enhanced(self):
        """Test degree checking for Enhanced tier."""
        capabilities = TierCapabilities(
            tier=ServiceTier.ENHANCED,
            max_degree=SearchDegree.D3,
        )

        assert capabilities.allows_degree(SearchDegree.D1)
        assert capabilities.allows_degree(SearchDegree.D2)
        assert capabilities.allows_degree(SearchDegree.D3)

    def test_allows_check_type_unrestricted(self):
        """Test check type when unrestricted."""
        capabilities = TierCapabilities(
            tier=ServiceTier.ENHANCED,
            available_check_types=[],  # Empty = all allowed
        )

        assert capabilities.allows_check_type(CheckType.IDENTITY_BASIC)
        assert capabilities.allows_check_type(CheckType.SANCTIONS_OFAC)

    def test_allows_check_type_restricted(self):
        """Test check type when restricted."""
        capabilities = TierCapabilities(
            tier=ServiceTier.STANDARD,
            available_check_types=[CheckType.IDENTITY_BASIC],
        )

        assert capabilities.allows_check_type(CheckType.IDENTITY_BASIC)
        assert not capabilities.allows_check_type(CheckType.SANCTIONS_OFAC)

    def test_to_dict(self):
        """Test serialization."""
        capabilities = TierCapabilities(
            tier=ServiceTier.STANDARD,
            max_queries=50,
            max_degree=SearchDegree.D1,
        )

        result = capabilities.to_dict()

        assert result["tier"] == "standard"
        assert result["max_queries"] == 50
        assert result["max_degree"] == "d1"


# =============================================================================
# TierRouter Tests
# =============================================================================


class TestTierRouter:
    """Tests for TierRouter."""

    def test_create_router(self, config):
        """Test router creation."""
        router = create_tier_router(config=config)

        assert router is not None
        assert router.config == config

    def test_add_data_source(self, config, core_source):
        """Test adding data source."""
        router = TierRouter(config=config)
        router.add_data_source(core_source)

        sources = router.get_all_sources()
        assert len(sources) == 1
        assert sources[0].source_id == "core-identity"

    def test_get_capabilities_standard(self, router):
        """Test getting Standard tier capabilities."""
        capabilities = router.get_capabilities(ServiceTier.STANDARD)

        assert capabilities.tier == ServiceTier.STANDARD
        assert capabilities.max_degree == SearchDegree.D1
        assert capabilities.budget_limit == 100.0
        assert not capabilities.network_analysis

    def test_get_capabilities_enhanced(self, router):
        """Test getting Enhanced tier capabilities."""
        capabilities = router.get_capabilities(ServiceTier.ENHANCED)

        assert capabilities.tier == ServiceTier.ENHANCED
        assert capabilities.max_degree == SearchDegree.D3
        assert capabilities.budget_limit == 1000.0
        assert capabilities.network_analysis

    def test_get_available_sources_standard(self, router):
        """Test getting sources for Standard tier."""
        sources = router.get_available_sources(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        # Standard tier only gets core sources
        assert len(sources) == 1
        assert sources[0].tier == DataSourceTier.CORE

    def test_get_available_sources_enhanced(self, router):
        """Test getting sources for Enhanced tier."""
        sources = router.get_available_sources(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
        )

        # Enhanced tier gets all sources
        assert len(sources) == 2

    def test_get_available_sources_locale_filter(self, router):
        """Test locale filtering."""
        sources = router.get_available_sources(
            tier=ServiceTier.ENHANCED,
            locale=Locale.UK,  # Core source only available in US
        )

        # Only premium source is global
        assert len(sources) == 1
        assert sources[0].tier == DataSourceTier.PREMIUM

    def test_get_available_sources_check_type_filter(self, router):
        """Test check type filtering."""
        sources = router.get_available_sources(
            tier=ServiceTier.ENHANCED,
            check_types=[CheckType.SANCTIONS_OFAC],
        )

        # Only premium source supports sanctions check
        assert len(sources) == 1
        assert sources[0].source_id == "premium-sanctions"

    def test_get_core_sources(self, router):
        """Test getting only core sources."""
        sources = router.get_core_sources()

        assert len(sources) == 1
        assert all(s.tier == DataSourceTier.CORE for s in sources)

    def test_get_premium_sources(self, router):
        """Test getting only premium sources."""
        sources = router.get_premium_sources()

        assert len(sources) == 1
        assert all(s.tier == DataSourceTier.PREMIUM for s in sources)

    def test_route_request_standard(self, router):
        """Test routing Standard tier request."""
        result = router.route_request(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        assert isinstance(result, RoutingResult)
        assert result.tier == ServiceTier.STANDARD
        assert result.handler_type == "standard"
        assert len(result.available_sources) == 1

    def test_route_request_enhanced(self, router):
        """Test routing Enhanced tier request."""
        result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
            degree=SearchDegree.D2,
        )

        assert result.tier == ServiceTier.ENHANCED
        assert result.handler_type == "enhanced"
        assert len(result.available_sources) == 2

    def test_route_request_degree_warning(self, router):
        """Test warning for degree exceeding tier limit."""
        result = router.route_request(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            degree=SearchDegree.D3,  # Exceeds Standard limit
        )

        assert len(result.warnings) > 0
        assert "d3" in result.warnings[0]

    def test_route_request_filtered_sources(self, router):
        """Test tracking filtered sources."""
        result = router.route_request(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        # Premium source should be filtered
        assert "premium-sanctions" in result.filtered_sources

    def test_route_request_cost_estimate(self, router):
        """Test cost estimation."""
        result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        # Should estimate based on source costs
        assert result.estimated_cost > 0

    def test_validate_request_valid(self, router):
        """Test validating a valid request."""
        is_valid, errors = router.validate_request(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
        )

        assert is_valid
        assert len(errors) == 0

    def test_validate_request_invalid_degree(self, router):
        """Test validating request with invalid degree."""
        is_valid, errors = router.validate_request(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D3,  # Not allowed for Standard
        )

        assert not is_valid
        assert len(errors) > 0
        assert "d3" in errors[0]

    def test_validate_request_budget_exceeded(self, router):
        """Test validating request with budget exceeded."""
        is_valid, errors = router.validate_request(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            estimated_cost=500.0,  # Exceeds $100 limit
        )

        assert not is_valid
        assert len(errors) > 0
        assert "budget" in errors[0].lower() or "cost" in errors[0].lower()

    def test_register_handler(self, router):
        """Test registering handlers."""
        class MockHandler:
            async def execute(self, request, available_sources):
                return None

        handler = MockHandler()
        router.register_handler(ServiceTier.STANDARD, handler)

        assert router.get_handler(ServiceTier.STANDARD) == handler

    def test_get_handler_not_registered(self, router):
        """Test getting unregistered handler."""
        handler = router.get_handler(ServiceTier.STANDARD)
        assert handler is None


# =============================================================================
# Configuration Tests
# =============================================================================


class TestTierRouterConfig:
    """Tests for TierRouterConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = TierRouterConfig()

        assert config.standard_max_queries == 50
        assert config.enhanced_max_queries == 200
        assert config.standard_max_degree == SearchDegree.D1
        assert config.enhanced_max_degree == SearchDegree.D3

    def test_custom_config(self):
        """Test custom configuration."""
        config = TierRouterConfig(
            standard_max_queries=25,
            standard_budget_limit=50.0,
        )

        assert config.standard_max_queries == 25
        assert config.standard_budget_limit == 50.0


# =============================================================================
# Default Data Sources Tests
# =============================================================================


class TestDefaultDataSources:
    """Tests for default data sources."""

    def test_create_default_sources(self):
        """Test creating default data sources."""
        sources = create_default_data_sources()

        assert len(sources) > 0
        assert any(s.tier == DataSourceTier.CORE for s in sources)
        assert any(s.tier == DataSourceTier.PREMIUM for s in sources)

    def test_default_sources_have_check_types(self):
        """Test that default sources have check types."""
        sources = create_default_data_sources()

        for source in sources:
            assert len(source.check_types) > 0

    def test_default_sources_coverage(self):
        """Test that default sources cover key check types."""
        sources = create_default_data_sources()
        all_check_types = set()

        for source in sources:
            all_check_types.update(source.check_types)

        # Should cover essential check types
        assert CheckType.IDENTITY_BASIC in all_check_types
        assert CheckType.EMPLOYMENT_VERIFICATION in all_check_types
        assert CheckType.CRIMINAL_NATIONAL in all_check_types
        assert CheckType.SANCTIONS_OFAC in all_check_types


# =============================================================================
# Integration Tests
# =============================================================================


class TestTierRouterIntegration:
    """Integration tests for tier router."""

    def test_full_routing_flow(self):
        """Test complete routing flow."""
        # Create router with default sources
        router = create_tier_router()
        for source in create_default_data_sources():
            router.add_data_source(source)

        # Route Standard tier request
        standard_result = router.route_request(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        # Route Enhanced tier request
        enhanced_result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
            degree=SearchDegree.D2,
        )

        # Enhanced should have more sources
        assert len(enhanced_result.available_sources) > len(standard_result.available_sources)

        # Enhanced should have higher cost estimate
        assert enhanced_result.estimated_cost > standard_result.estimated_cost

    def test_tier_upgrade_path(self):
        """Test that Enhanced includes all Standard capabilities."""
        router = create_tier_router()
        for source in create_default_data_sources():
            router.add_data_source(source)

        standard_caps = router.get_capabilities(ServiceTier.STANDARD)
        enhanced_caps = router.get_capabilities(ServiceTier.ENHANCED)

        # Enhanced should have >= Standard capabilities
        assert enhanced_caps.max_queries >= standard_caps.max_queries
        assert enhanced_caps.max_sources >= standard_caps.max_sources
        assert enhanced_caps.budget_limit >= standard_caps.budget_limit

    def test_locale_specific_routing(self):
        """Test routing for different locales."""
        router = create_tier_router()
        for source in create_default_data_sources():
            router.add_data_source(source)

        us_result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        uk_result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.UK,
            degree=SearchDegree.D1,
        )

        # US should have more sources (locale-specific + global)
        # UK only gets global sources
        assert len(us_result.available_sources) >= len(uk_result.available_sources)


# =============================================================================
# Edge Cases
# =============================================================================


class TestTierRouterEdgeCases:
    """Edge case tests for tier router."""

    def test_empty_sources(self):
        """Test router with no data sources."""
        router = create_tier_router()

        result = router.route_request(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        assert len(result.available_sources) == 0
        assert result.estimated_cost == 0

    def test_all_sources_filtered(self, config, core_source):
        """Test when all sources are filtered out."""
        router = TierRouter(config=config)
        router.add_data_source(core_source)

        # Request with check type not supported by any source
        result = router.route_request(
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
            degree=SearchDegree.D1,
            check_types=[CheckType.SANCTIONS_OFAC],  # Not supported by core source
        )

        assert len(result.available_sources) == 0

    def test_cost_estimation_with_degree_multiplier(self, router):
        """Test cost estimation includes degree multiplier."""
        d1_result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
            degree=SearchDegree.D1,
        )

        d3_result = router.route_request(
            tier=ServiceTier.ENHANCED,
            locale=Locale.US,
            degree=SearchDegree.D3,
        )

        # D3 should cost more than D1
        assert d3_result.estimated_cost > d1_result.estimated_cost
