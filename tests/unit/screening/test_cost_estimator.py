"""Tests for the Screening Cost Estimator (Task 7.10).

Tests cover:
- Single screening cost estimation
- Tier-based pricing
- Degree-based cost scaling
- Check type costs
- Locale adjustments
- Bulk pricing with volume discounts
- Estimated vs actual comparison
- Cache savings estimation
"""

from decimal import Decimal
from uuid import uuid7

import pytest

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.screening.cost_estimator import (
    CostBreakdown,
    CostCategory,
    CostEstimate,
    CostEstimator,
    EstimatorConfig,
    create_cost_estimator,
    get_cost_estimator,
    reset_cost_estimator,
)
from elile.screening.tier_router import DataSourceSpec, DataSourceTier

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def config():
    """Create test configuration."""
    return EstimatorConfig(
        standard_base_fee=Decimal("25.00"),
        enhanced_base_fee=Decimal("75.00"),
        d1_multiplier=1.0,
        d2_multiplier=1.5,
        d3_multiplier=2.5,
    )


@pytest.fixture
def data_sources():
    """Create test data sources."""
    return [
        DataSourceSpec(
            source_id="test-identity",
            provider_id="test-provider",
            name="Test Identity",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.IDENTITY_BASIC],
            locales=[Locale.US, Locale.UK],
            cost_per_query=5.00,
        ),
        DataSourceSpec(
            source_id="test-criminal",
            provider_id="test-provider",
            name="Test Criminal",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.CRIMINAL_NATIONAL],
            locales=[Locale.US],
            cost_per_query=20.00,
        ),
        DataSourceSpec(
            source_id="test-employment",
            provider_id="test-provider",
            name="Test Employment",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.EMPLOYMENT_VERIFICATION],
            locales=[Locale.US, Locale.UK],
            cost_per_query=15.00,
        ),
        DataSourceSpec(
            source_id="test-sanctions",
            provider_id="premium-provider",
            name="Test Sanctions",
            tier=DataSourceTier.PREMIUM,
            check_types=[CheckType.SANCTIONS_OFAC, CheckType.SANCTIONS_PEP],
            locales=[],  # Global
            cost_per_query=35.00,
        ),
        DataSourceSpec(
            source_id="test-adverse",
            provider_id="premium-provider",
            name="Test Adverse Media",
            tier=DataSourceTier.PREMIUM,
            check_types=[CheckType.ADVERSE_MEDIA],
            locales=[],  # Global
            cost_per_query=40.00,
        ),
    ]


@pytest.fixture
def estimator(config, data_sources):
    """Create test estimator."""
    return CostEstimator(config=config, data_sources=data_sources)


# =============================================================================
# CostBreakdown Tests
# =============================================================================


class TestCostBreakdown:
    """Tests for CostBreakdown data class."""

    def test_add_cost_category(self):
        """Test adding cost by category."""
        breakdown = CostBreakdown()
        breakdown.add_cost(Decimal("10.00"), CostCategory.BASE_FEE)
        breakdown.add_cost(Decimal("20.00"), CostCategory.BASE_FEE)

        assert breakdown.by_category[CostCategory.BASE_FEE] == Decimal("30.00")

    def test_add_cost_check_type(self):
        """Test adding cost by check type."""
        breakdown = CostBreakdown()
        breakdown.add_cost(
            Decimal("15.00"),
            CostCategory.DATA_PROVIDER,
            check_type=CheckType.CRIMINAL_NATIONAL,
        )

        assert breakdown.by_check_type[CheckType.CRIMINAL_NATIONAL] == Decimal("15.00")

    def test_add_cost_provider(self):
        """Test adding cost by provider."""
        breakdown = CostBreakdown()
        breakdown.add_cost(
            Decimal("25.00"),
            CostCategory.DATA_PROVIDER,
            provider_id="sterling",
        )

        assert breakdown.by_provider["sterling"] == Decimal("25.00")

    def test_to_dict(self):
        """Test serialization to dict."""
        breakdown = CostBreakdown()
        breakdown.add_cost(
            Decimal("10.00"),
            CostCategory.BASE_FEE,
        )
        breakdown.add_cost(
            Decimal("20.00"),
            CostCategory.DATA_PROVIDER,
            check_type=CheckType.IDENTITY_BASIC,
            provider_id="test",
        )

        data = breakdown.to_dict()

        assert "by_category" in data
        assert "by_check_type" in data
        assert "by_provider" in data
        assert data["by_category"]["base_fee"] == "10.00"


# =============================================================================
# CostEstimate Tests
# =============================================================================


class TestCostEstimate:
    """Tests for CostEstimate data class."""

    def test_default_values(self):
        """Test default values."""
        estimate = CostEstimate()

        assert estimate.tier == ServiceTier.STANDARD
        assert estimate.degree == SearchDegree.D1
        assert estimate.total_estimated == Decimal("0.00")
        assert estimate.confidence == 0.8

    def test_to_dict(self):
        """Test serialization to dict."""
        estimate = CostEstimate(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D2,
            locale=Locale.UK,
            check_types={CheckType.CRIMINAL_NATIONAL},
            total_estimated=Decimal("150.00"),
        )

        data = estimate.to_dict()

        assert data["tier"] == "enhanced"
        assert data["degree"] == "d2"
        assert data["locale"] == "UK"
        assert data["total_estimated"] == "150.00"
        assert "criminal_national" in data["check_types"]


# =============================================================================
# Single Screening Estimation Tests
# =============================================================================


class TestSingleScreeningEstimation:
    """Tests for single screening cost estimation."""

    def test_estimate_standard_d1_basic(self, estimator):
        """Test basic Standard D1 estimate."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        assert estimate.tier == ServiceTier.STANDARD
        assert estimate.degree == SearchDegree.D1
        assert estimate.total_estimated > Decimal("0.00")
        assert CostCategory.BASE_FEE in estimate.breakdown.by_category
        assert CostCategory.DATA_PROVIDER in estimate.breakdown.by_category

    def test_estimate_enhanced_higher_base_fee(self, estimator):
        """Test Enhanced tier has higher base fee."""
        standard = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        enhanced = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        standard_base = standard.breakdown.by_category[CostCategory.BASE_FEE]
        enhanced_base = enhanced.breakdown.by_category[CostCategory.BASE_FEE]

        assert enhanced_base > standard_base

    def test_estimate_d2_higher_than_d1(self, estimator):
        """Test D2 costs more than D1."""
        d1 = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC, CheckType.CRIMINAL_NATIONAL},
            locale=Locale.US,
        )

        d2 = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D2,
            check_types={CheckType.IDENTITY_BASIC, CheckType.CRIMINAL_NATIONAL},
            locale=Locale.US,
        )

        assert d2.total_estimated > d1.total_estimated

    def test_estimate_d3_highest_cost(self, estimator):
        """Test D3 has highest cost."""
        d2 = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D2,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        d3 = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D3,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        assert d3.total_estimated > d2.total_estimated

    def test_estimate_includes_network_costs_d2(self, estimator):
        """Test D2 includes network analysis costs."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D2,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        assert CostCategory.NETWORK_ANALYSIS in estimate.breakdown.by_category
        assert estimate.breakdown.by_category[CostCategory.NETWORK_ANALYSIS] > Decimal("0.00")

    def test_estimate_no_network_costs_d1(self, estimator):
        """Test D1 has no network analysis costs."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        network_cost = estimate.breakdown.by_category.get(
            CostCategory.NETWORK_ANALYSIS, Decimal("0.00")
        )
        assert network_cost == Decimal("0.00")

    def test_estimate_multiple_check_types(self, estimator):
        """Test estimate with multiple check types."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={
                CheckType.IDENTITY_BASIC,
                CheckType.CRIMINAL_NATIONAL,
                CheckType.EMPLOYMENT_VERIFICATION,
            },
            locale=Locale.US,
        )

        assert estimate.estimated_queries == 3
        assert len(estimate.breakdown.by_check_type) == 3

    def test_estimate_min_max_variance(self, estimator):
        """Test estimate includes min/max range."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        assert estimate.minimum_cost < estimate.total_estimated
        assert estimate.maximum_cost > estimate.total_estimated

    def test_estimate_cache_savings(self, estimator):
        """Test cache savings estimate."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
            cache_hit_probability=0.3,
        )

        assert estimate.cache_hit_probability == 0.3
        assert estimate.cache_savings_estimate > Decimal("0.00")


# =============================================================================
# Tier-Based Pricing Tests
# =============================================================================


class TestTierBasedPricing:
    """Tests for tier-based pricing."""

    def test_standard_only_core_sources(self, estimator):
        """Test Standard tier only uses core sources."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.SANCTIONS_OFAC},  # Premium only
            locale=Locale.US,
        )

        # Should have warning about unavailable check type
        assert any("SANCTIONS_OFAC" in w or "sanctions_ofac" in w for w in estimate.warnings)

    def test_enhanced_includes_premium_sources(self, estimator):
        """Test Enhanced tier includes premium sources."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D1,
            check_types={CheckType.SANCTIONS_OFAC},
            locale=Locale.US,
        )

        assert CheckType.SANCTIONS_OFAC in estimate.breakdown.by_check_type

    def test_enhanced_ai_synthesis_cost(self, estimator):
        """Test Enhanced tier includes AI synthesis cost."""
        standard = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        enhanced = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        standard_ai = standard.breakdown.by_category.get(CostCategory.AI_ANALYSIS, Decimal("0.00"))
        enhanced_ai = enhanced.breakdown.by_category.get(CostCategory.AI_ANALYSIS, Decimal("0.00"))

        assert enhanced_ai > standard_ai

    def test_tier_comparison(self, estimator):
        """Test comparing costs across tiers."""
        comparison = estimator.get_tier_comparison(
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC, CheckType.CRIMINAL_NATIONAL},
            locale=Locale.US,
        )

        assert ServiceTier.STANDARD in comparison
        assert ServiceTier.ENHANCED in comparison
        assert (
            comparison[ServiceTier.ENHANCED].total_estimated
            > comparison[ServiceTier.STANDARD].total_estimated
        )

    def test_tier_comparison_d3_only_enhanced(self, estimator):
        """Test D3 only available in Enhanced tier comparison."""
        comparison = estimator.get_tier_comparison(
            degree=SearchDegree.D3,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        assert ServiceTier.STANDARD not in comparison
        assert ServiceTier.ENHANCED in comparison


# =============================================================================
# Locale Adjustment Tests
# =============================================================================


class TestLocaleAdjustments:
    """Tests for locale-based cost adjustments."""

    def test_uk_higher_than_us(self, estimator):
        """Test UK costs more than US."""
        us_estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        uk_estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.UK,
        )

        assert uk_estimate.total_estimated > us_estimate.total_estimated

    def test_missing_check_type_warning(self, estimator):
        """Test warning for check type not available in locale."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.CRIMINAL_NATIONAL},  # US only in test data
            locale=Locale.UK,
        )

        assert any("CRIMINAL_NATIONAL" in w or "criminal_national" in w for w in estimate.warnings)

    def test_unknown_locale_lower_confidence(self, config, data_sources):
        """Test unknown locale has lower confidence."""
        # Create estimator with limited locale data
        estimator = CostEstimator(config=config, data_sources=data_sources)

        us_estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        # BR not in locale_multipliers
        br_estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.BR,
        )

        assert br_estimate.confidence < us_estimate.confidence


# =============================================================================
# Bulk Estimation Tests
# =============================================================================


class TestBulkEstimation:
    """Tests for bulk cost estimation."""

    def test_bulk_estimate_basic(self, estimator):
        """Test basic bulk estimate."""
        screenings = [
            (ServiceTier.STANDARD, SearchDegree.D1, {CheckType.IDENTITY_BASIC}, Locale.US),
            (ServiceTier.STANDARD, SearchDegree.D1, {CheckType.IDENTITY_BASIC}, Locale.US),
        ]

        bulk = estimator.estimate_bulk_cost(screenings)

        assert bulk.screening_count == 2
        assert len(bulk.individual_estimates) == 2
        assert bulk.total_before_discount > Decimal("0.00")

    def test_bulk_volume_discount_small(self, estimator):
        """Test no discount for small volume."""
        screenings = [
            (ServiceTier.STANDARD, SearchDegree.D1, {CheckType.IDENTITY_BASIC}, Locale.US)
            for _ in range(5)
        ]

        bulk = estimator.estimate_bulk_cost(screenings)

        assert bulk.volume_discount == Decimal("0.00")
        assert bulk.discount_percentage == 0.0

    def test_bulk_volume_discount_10plus(self, estimator):
        """Test 5% discount for 10+ screenings."""
        screenings = [
            (ServiceTier.STANDARD, SearchDegree.D1, {CheckType.IDENTITY_BASIC}, Locale.US)
            for _ in range(10)
        ]

        bulk = estimator.estimate_bulk_cost(screenings)

        assert bulk.discount_percentage == 5.0
        assert bulk.volume_discount > Decimal("0.00")
        assert bulk.total_estimated < bulk.total_before_discount

    def test_bulk_volume_discount_100plus(self, estimator):
        """Test 15% discount for 100+ screenings."""
        screenings = [
            (ServiceTier.STANDARD, SearchDegree.D1, {CheckType.IDENTITY_BASIC}, Locale.US)
            for _ in range(100)
        ]

        bulk = estimator.estimate_bulk_cost(screenings)

        assert bulk.discount_percentage == 15.0

    def test_bulk_average_cost(self, estimator):
        """Test average cost calculation."""
        screenings = [
            (ServiceTier.STANDARD, SearchDegree.D1, {CheckType.IDENTITY_BASIC}, Locale.US),
            (
                ServiceTier.ENHANCED,
                SearchDegree.D2,
                {CheckType.IDENTITY_BASIC, CheckType.CRIMINAL_NATIONAL},
                Locale.US,
            ),
        ]

        bulk = estimator.estimate_bulk_cost(screenings)

        assert bulk.average_cost_per_screening > Decimal("0.00")
        # Average should be between the two individual estimates
        min_estimate = min(e.total_estimated for e in bulk.individual_estimates)
        max_estimate = max(e.total_estimated for e in bulk.individual_estimates)
        assert min_estimate <= bulk.average_cost_per_screening <= max_estimate


# =============================================================================
# Cost Comparison Tests
# =============================================================================


class TestCostComparison:
    """Tests for estimated vs actual comparison."""

    def test_compare_exact_match(self, estimator):
        """Test comparison with exact match."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        comparison = estimator.compare_to_actual(
            estimate_id=estimate.estimate_id,
            actual_cost=estimate.total_estimated,
        )

        assert comparison.difference == Decimal("0.00")
        assert comparison.accuracy_percentage == 100.0

    def test_compare_over_estimate(self, estimator):
        """Test comparison when actual is lower."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        actual = estimate.total_estimated - Decimal("5.00")
        comparison = estimator.compare_to_actual(
            estimate_id=estimate.estimate_id,
            actual_cost=actual,
        )

        assert comparison.difference < Decimal("0.00")
        assert comparison.accuracy_percentage > 0

    def test_compare_under_estimate(self, estimator):
        """Test comparison when actual is higher."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        actual = estimate.total_estimated + Decimal("10.00")
        comparison = estimator.compare_to_actual(
            estimate_id=estimate.estimate_id,
            actual_cost=actual,
        )

        assert comparison.difference > Decimal("0.00")

    def test_compare_unknown_estimate(self, estimator):
        """Test comparison with unknown estimate ID."""
        with pytest.raises(ValueError, match="not found"):
            estimator.compare_to_actual(
                estimate_id=uuid7(),
                actual_cost=Decimal("100.00"),
            )


# =============================================================================
# Check Type Cost Tests
# =============================================================================


class TestCheckTypeCost:
    """Tests for individual check type costs."""

    def test_get_check_type_cost(self, estimator):
        """Test getting cost for specific check type."""
        cost = estimator.get_check_type_cost(
            check_type=CheckType.IDENTITY_BASIC,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert cost > Decimal("0.00")

    def test_check_type_unavailable(self, estimator):
        """Test check type not available returns zero."""
        cost = estimator.get_check_type_cost(
            check_type=CheckType.DIGITAL_FOOTPRINT,  # Not in test data
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        assert cost == Decimal("0.00")

    def test_check_type_locale_multiplier(self, estimator):
        """Test check type cost has locale multiplier."""
        us_cost = estimator.get_check_type_cost(
            check_type=CheckType.IDENTITY_BASIC,
            tier=ServiceTier.STANDARD,
            locale=Locale.US,
        )

        uk_cost = estimator.get_check_type_cost(
            check_type=CheckType.IDENTITY_BASIC,
            tier=ServiceTier.STANDARD,
            locale=Locale.UK,
        )

        assert uk_cost > us_cost


# =============================================================================
# Configuration Tests
# =============================================================================


class TestEstimatorConfig:
    """Tests for estimator configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EstimatorConfig()

        assert config.standard_base_fee == Decimal("25.00")
        assert config.enhanced_base_fee == Decimal("75.00")
        assert config.d1_multiplier == 1.0
        assert config.d2_multiplier == 1.5
        assert config.d3_multiplier == 2.5

    def test_custom_config(self):
        """Test custom configuration."""
        config = EstimatorConfig(
            standard_base_fee=Decimal("30.00"),
            enhanced_base_fee=Decimal("100.00"),
            d2_multiplier=2.0,
        )

        assert config.standard_base_fee == Decimal("30.00")
        assert config.enhanced_base_fee == Decimal("100.00")
        assert config.d2_multiplier == 2.0

    def test_config_affects_estimate(self):
        """Test configuration affects estimates."""
        low_config = EstimatorConfig(standard_base_fee=Decimal("10.00"))
        high_config = EstimatorConfig(standard_base_fee=Decimal("50.00"))

        low_estimator = create_cost_estimator(config=low_config)
        high_estimator = create_cost_estimator(config=high_config)

        low_estimate = low_estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        high_estimate = high_estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        assert high_estimate.total_estimated > low_estimate.total_estimated


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_cost_estimator(self):
        """Test creating estimator with factory."""
        estimator = create_cost_estimator()

        assert isinstance(estimator, CostEstimator)

    def test_create_cost_estimator_with_config(self):
        """Test creating estimator with custom config."""
        config = EstimatorConfig(standard_base_fee=Decimal("50.00"))
        estimator = create_cost_estimator(config=config)

        assert estimator.config.standard_base_fee == Decimal("50.00")

    def test_get_global_estimator(self):
        """Test getting global estimator."""
        reset_cost_estimator()

        estimator1 = get_cost_estimator()
        estimator2 = get_cost_estimator()

        assert estimator1 is estimator2

    def test_reset_global_estimator(self):
        """Test resetting global estimator."""
        estimator1 = get_cost_estimator()
        reset_cost_estimator()
        estimator2 = get_cost_estimator()

        assert estimator1 is not estimator2


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_check_types(self, estimator):
        """Test estimate with no check types."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types=set(),
            locale=Locale.US,
        )

        # Should still have base fee
        assert estimate.total_estimated > Decimal("0.00")
        assert estimate.estimated_queries == 0

    def test_reset_clears_estimates(self, estimator):
        """Test reset clears stored estimates."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        estimator.reset()

        with pytest.raises(ValueError):
            estimator.compare_to_actual(
                estimate_id=estimate.estimate_id,
                actual_cost=Decimal("100.00"),
            )

    def test_estimate_stores_for_comparison(self, estimator):
        """Test estimates are stored for later comparison."""
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.STANDARD,
            degree=SearchDegree.D1,
            check_types={CheckType.IDENTITY_BASIC},
            locale=Locale.US,
        )

        # Should be able to compare
        comparison = estimator.compare_to_actual(
            estimate_id=estimate.estimate_id,
            actual_cost=Decimal("50.00"),
        )

        assert comparison.estimated_cost == estimate.total_estimated
