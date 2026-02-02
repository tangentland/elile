"""Screening Cost Estimation System.

Task 7.10: Implements pre-execution cost estimation for screening operations,
helping organizations budget and make informed tier selection decisions.

Features:
- Tier-based pricing with base fees and multipliers
- Degree-based cost scaling (D1 < D2 < D3)
- Check type-specific costs from provider data
- Locale-specific pricing adjustments
- Bulk pricing with volume discounts
- Estimated vs actual cost tracking
- Cache hit probability for cost optimization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger
from elile.screening.tier_router import (
    DataSourceSpec,
    DataSourceTier,
    TierRouter,
    create_default_data_sources,
)

logger = get_logger(__name__)


# =============================================================================
# Cost Types
# =============================================================================


class CostCategory(str, Enum):
    """Categories of costs in a screening."""

    BASE_FEE = "base_fee"  # Tier-based base fee
    DATA_PROVIDER = "data_provider"  # Provider query costs
    AI_ANALYSIS = "ai_analysis"  # AI model costs
    STORAGE = "storage"  # Data storage costs
    REPORT_GENERATION = "report_generation"  # Report costs
    NETWORK_ANALYSIS = "network_analysis"  # D2/D3 connection analysis


@dataclass
class CostBreakdown:
    """Detailed breakdown of estimated costs."""

    by_category: dict[CostCategory, Decimal] = field(default_factory=dict)
    by_check_type: dict[CheckType, Decimal] = field(default_factory=dict)
    by_provider: dict[str, Decimal] = field(default_factory=dict)

    def add_cost(
        self,
        amount: Decimal,
        category: CostCategory,
        *,
        check_type: CheckType | None = None,
        provider_id: str | None = None,
    ) -> None:
        """Add a cost to the breakdown."""
        # Category
        if category not in self.by_category:
            self.by_category[category] = Decimal("0.00")
        self.by_category[category] += amount

        # Check type
        if check_type:
            if check_type not in self.by_check_type:
                self.by_check_type[check_type] = Decimal("0.00")
            self.by_check_type[check_type] += amount

        # Provider
        if provider_id:
            if provider_id not in self.by_provider:
                self.by_provider[provider_id] = Decimal("0.00")
            self.by_provider[provider_id] += amount

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "by_category": {k.value: str(v) for k, v in self.by_category.items()},
            "by_check_type": {k.value: str(v) for k, v in self.by_check_type.items()},
            "by_provider": {k: str(v) for k, v in self.by_provider.items()},
        }


@dataclass
class CostEstimate:
    """Pre-execution cost estimate for a screening."""

    estimate_id: UUID = field(default_factory=uuid7)

    # Request parameters
    tier: ServiceTier = ServiceTier.STANDARD
    degree: SearchDegree = SearchDegree.D1
    locale: Locale = Locale.US
    check_types: set[CheckType] = field(default_factory=set)

    # Cost totals
    total_estimated: Decimal = Decimal("0.00")
    minimum_cost: Decimal = Decimal("0.00")
    maximum_cost: Decimal = Decimal("0.00")

    # Breakdown
    breakdown: CostBreakdown = field(default_factory=CostBreakdown)

    # Estimate metadata
    confidence: float = 0.8  # Estimate confidence (0.0-1.0)
    currency: str = "USD"
    estimated_queries: int = 0
    cache_hit_probability: float = 0.0

    # Potential savings
    cache_savings_estimate: Decimal = Decimal("0.00")
    volume_discount: Decimal = Decimal("0.00")

    # Notes
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimate_id": str(self.estimate_id),
            "tier": self.tier.value,
            "degree": self.degree.value,
            "locale": self.locale.value,
            "check_types": [ct.value for ct in self.check_types],
            "total_estimated": str(self.total_estimated),
            "minimum_cost": str(self.minimum_cost),
            "maximum_cost": str(self.maximum_cost),
            "breakdown": self.breakdown.to_dict(),
            "confidence": self.confidence,
            "currency": self.currency,
            "estimated_queries": self.estimated_queries,
            "cache_hit_probability": self.cache_hit_probability,
            "cache_savings_estimate": str(self.cache_savings_estimate),
            "volume_discount": str(self.volume_discount),
            "notes": self.notes,
            "warnings": self.warnings,
        }


@dataclass
class BulkCostEstimate:
    """Cost estimate for multiple screenings."""

    estimate_id: UUID = field(default_factory=uuid7)
    screening_count: int = 0

    # Per-screening average
    average_cost_per_screening: Decimal = Decimal("0.00")

    # Totals
    total_estimated: Decimal = Decimal("0.00")
    total_before_discount: Decimal = Decimal("0.00")
    volume_discount: Decimal = Decimal("0.00")
    discount_percentage: float = 0.0

    # Individual estimates
    individual_estimates: list[CostEstimate] = field(default_factory=list)

    # Summary
    currency: str = "USD"
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimate_id": str(self.estimate_id),
            "screening_count": self.screening_count,
            "average_cost_per_screening": str(self.average_cost_per_screening),
            "total_estimated": str(self.total_estimated),
            "total_before_discount": str(self.total_before_discount),
            "volume_discount": str(self.volume_discount),
            "discount_percentage": self.discount_percentage,
            "currency": self.currency,
            "notes": self.notes,
        }


@dataclass
class CostComparison:
    """Comparison between estimated and actual costs."""

    estimate_id: UUID
    screening_id: UUID | None = None

    estimated_cost: Decimal = Decimal("0.00")
    actual_cost: Decimal = Decimal("0.00")
    difference: Decimal = Decimal("0.00")
    accuracy_percentage: float = 0.0

    # Breakdown comparison
    by_category: dict[CostCategory, tuple[Decimal, Decimal]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "estimate_id": str(self.estimate_id),
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "estimated_cost": str(self.estimated_cost),
            "actual_cost": str(self.actual_cost),
            "difference": str(self.difference),
            "accuracy_percentage": self.accuracy_percentage,
        }


# =============================================================================
# Configuration
# =============================================================================


class EstimatorConfig(BaseModel):
    """Configuration for cost estimation."""

    # Base fees by tier
    standard_base_fee: Decimal = Field(
        default=Decimal("25.00"),
        description="Base fee for Standard tier",
    )
    enhanced_base_fee: Decimal = Field(
        default=Decimal("75.00"),
        description="Base fee for Enhanced tier",
    )

    # Degree multipliers (applied to provider costs)
    d1_multiplier: float = Field(default=1.0, ge=1.0, description="D1 cost multiplier")
    d2_multiplier: float = Field(default=1.5, ge=1.0, description="D2 cost multiplier")
    d3_multiplier: float = Field(default=2.5, ge=1.0, description="D3 cost multiplier")

    # AI analysis costs
    ai_cost_per_finding: Decimal = Field(
        default=Decimal("0.50"),
        description="AI analysis cost per finding",
    )
    ai_base_cost: Decimal = Field(
        default=Decimal("5.00"),
        description="Base AI analysis cost",
    )
    ai_synthesis_cost: Decimal = Field(
        default=Decimal("10.00"),
        description="AI synthesis cost for Enhanced tier",
    )

    # Storage costs
    storage_cost_per_mb: Decimal = Field(
        default=Decimal("0.10"),
        description="Storage cost per MB",
    )
    average_screening_size_mb: float = Field(
        default=2.0,
        description="Average screening data size in MB",
    )

    # Report costs
    basic_report_cost: Decimal = Field(
        default=Decimal("5.00"),
        description="Basic report generation cost",
    )
    detailed_report_cost: Decimal = Field(
        default=Decimal("15.00"),
        description="Detailed report generation cost",
    )

    # Network analysis costs (D2/D3)
    network_analysis_per_entity: Decimal = Field(
        default=Decimal("5.00"),
        description="Cost per entity in network analysis",
    )
    max_network_entities_d2: int = Field(default=10, description="Max entities for D2")
    max_network_entities_d3: int = Field(default=50, description="Max entities for D3")

    # Locale adjustments (multipliers relative to US)
    locale_multipliers: dict[str, float] = Field(
        default={
            "US": 1.0,
            "UK": 1.2,
            "EU": 1.3,
            "CA": 1.1,
            "AU": 1.15,
        },
        description="Cost multipliers by locale",
    )

    # Volume discount tiers
    volume_discount_tiers: list[tuple[int, float]] = Field(
        default=[
            (10, 0.05),  # 5% off for 10+
            (50, 0.10),  # 10% off for 50+
            (100, 0.15),  # 15% off for 100+
            (500, 0.20),  # 20% off for 500+
            (1000, 0.25),  # 25% off for 1000+
        ],
        description="Volume discount tiers (count, discount)",
    )

    # Cache assumptions
    default_cache_hit_rate: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Default cache hit probability",
    )

    # Variance for min/max estimates
    estimate_variance: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description="Variance for min/max cost estimates",
    )


# =============================================================================
# Cost Estimator
# =============================================================================


class CostEstimator:
    """Pre-execution cost estimation for screenings.

    Provides cost estimates based on service tier, search degree,
    check types, and locale to help organizations budget effectively.

    Usage:
        estimator = CostEstimator()

        # Get estimate before execution
        estimate = estimator.estimate_screening_cost(
            tier=ServiceTier.ENHANCED,
            degree=SearchDegree.D2,
            check_types={CheckType.CRIMINAL_NATIONAL, CheckType.EMPLOYMENT_VERIFICATION},
            locale=Locale.US,
        )
        print(f"Estimated cost: ${estimate.total_estimated}")

        # Compare with actual after execution
        comparison = estimator.compare_to_actual(
            estimate_id=estimate.estimate_id,
            actual_cost=Decimal("127.50"),
        )
        print(f"Accuracy: {comparison.accuracy_percentage:.1f}%")
    """

    def __init__(
        self,
        config: EstimatorConfig | None = None,
        data_sources: list[DataSourceSpec] | None = None,
        tier_router: TierRouter | None = None,
    ):
        """Initialize cost estimator.

        Args:
            config: Estimator configuration.
            data_sources: Data source specifications with costs.
            tier_router: Tier router for capability checks.
        """
        self.config = config or EstimatorConfig()
        self._data_sources = data_sources or create_default_data_sources()
        self._tier_router = tier_router

        # Build lookup maps
        self._source_by_check_type: dict[CheckType, list[DataSourceSpec]] = {}
        for source in self._data_sources:
            for check_type in source.check_types:
                if check_type not in self._source_by_check_type:
                    self._source_by_check_type[check_type] = []
                self._source_by_check_type[check_type].append(source)

        # Track estimates for comparison
        self._estimates: dict[UUID, CostEstimate] = {}

    def estimate_screening_cost(
        self,
        tier: ServiceTier,
        degree: SearchDegree,
        check_types: set[CheckType],
        locale: Locale,
        *,
        cache_hit_probability: float | None = None,
        include_reports: bool = True,
    ) -> CostEstimate:
        """Estimate cost for a single screening.

        Args:
            tier: Service tier (Standard/Enhanced).
            degree: Search degree (D1/D2/D3).
            check_types: Set of check types to perform.
            locale: Screening locale.
            cache_hit_probability: Override default cache hit rate.
            include_reports: Include report generation costs.

        Returns:
            CostEstimate with detailed breakdown.
        """
        estimate = CostEstimate(
            tier=tier,
            degree=degree,
            locale=locale,
            check_types=check_types,
            cache_hit_probability=cache_hit_probability or self.config.default_cache_hit_rate,
        )

        # Get locale multiplier
        locale_key = locale.value.split("_")[0] if "_" in locale.value else locale.value
        locale_multiplier = Decimal(str(self.config.locale_multipliers.get(locale_key, 1.0)))

        # Get degree multiplier
        degree_multiplier = self._get_degree_multiplier(degree)

        # 1. Base fee
        base_fee = (
            self.config.enhanced_base_fee
            if tier == ServiceTier.ENHANCED
            else self.config.standard_base_fee
        )
        base_fee = base_fee * locale_multiplier
        estimate.breakdown.add_cost(base_fee, CostCategory.BASE_FEE)

        # 2. Data provider costs
        provider_costs = self._estimate_provider_costs(
            check_types=check_types,
            tier=tier,
            locale=locale,
            degree_multiplier=degree_multiplier,
            locale_multiplier=locale_multiplier,
            estimate=estimate,
        )

        # 3. AI analysis costs
        ai_cost = self._estimate_ai_costs(tier, degree, len(check_types))
        estimate.breakdown.add_cost(ai_cost, CostCategory.AI_ANALYSIS)

        # 4. Storage costs
        storage_cost = (
            Decimal(str(self.config.average_screening_size_mb)) * self.config.storage_cost_per_mb
        )
        estimate.breakdown.add_cost(storage_cost, CostCategory.STORAGE)

        # 5. Report costs
        if include_reports:
            report_cost = (
                self.config.detailed_report_cost
                if tier == ServiceTier.ENHANCED
                else self.config.basic_report_cost
            )
            estimate.breakdown.add_cost(report_cost, CostCategory.REPORT_GENERATION)

        # 6. Network analysis costs (D2/D3)
        if degree in (SearchDegree.D2, SearchDegree.D3):
            network_cost = self._estimate_network_costs(degree)
            estimate.breakdown.add_cost(network_cost, CostCategory.NETWORK_ANALYSIS)

        # Calculate totals
        estimate.total_estimated = sum(
            estimate.breakdown.by_category.values(),
            Decimal("0.00"),
        )

        # Calculate cache savings estimate
        estimate.cache_savings_estimate = provider_costs * Decimal(
            str(estimate.cache_hit_probability)
        )

        # Calculate min/max with variance
        variance = Decimal(str(self.config.estimate_variance))
        estimate.minimum_cost = estimate.total_estimated * (Decimal("1.0") - variance)
        estimate.maximum_cost = estimate.total_estimated * (Decimal("1.0") + variance)

        # Set confidence based on data availability
        estimate.confidence = self._calculate_confidence(check_types, locale)

        # Add notes
        if estimate.cache_hit_probability > 0:
            estimate.notes.append(
                f"Estimated ${estimate.cache_savings_estimate:.2f} potential savings from cache hits"
            )

        if degree == SearchDegree.D3 and tier != ServiceTier.ENHANCED:
            estimate.warnings.append("D3 degree requires Enhanced tier")

        # Store for later comparison
        self._estimates[estimate.estimate_id] = estimate

        logger.info(
            "cost_estimated",
            estimate_id=str(estimate.estimate_id),
            tier=tier.value,
            degree=degree.value,
            locale=locale.value,
            check_count=len(check_types),
            total_estimated=float(estimate.total_estimated),
        )

        return estimate

    def estimate_bulk_cost(
        self,
        screenings: list[tuple[ServiceTier, SearchDegree, set[CheckType], Locale]],
    ) -> BulkCostEstimate:
        """Estimate cost for multiple screenings.

        Args:
            screenings: List of (tier, degree, check_types, locale) tuples.

        Returns:
            BulkCostEstimate with volume discounts.
        """
        bulk = BulkCostEstimate(
            screening_count=len(screenings),
        )

        # Calculate individual estimates
        for tier, degree, check_types, locale in screenings:
            estimate = self.estimate_screening_cost(
                tier=tier,
                degree=degree,
                check_types=check_types,
                locale=locale,
            )
            bulk.individual_estimates.append(estimate)
            bulk.total_before_discount += estimate.total_estimated

        # Apply volume discount
        discount_rate = self._get_volume_discount(len(screenings))
        bulk.discount_percentage = discount_rate * 100
        bulk.volume_discount = bulk.total_before_discount * Decimal(str(discount_rate))
        bulk.total_estimated = bulk.total_before_discount - bulk.volume_discount

        # Calculate average
        if len(screenings) > 0:
            bulk.average_cost_per_screening = bulk.total_estimated / Decimal(len(screenings))

        # Add notes
        if discount_rate > 0:
            bulk.notes.append(
                f"Volume discount of {bulk.discount_percentage:.1f}% applied for {len(screenings)} screenings"
            )

        logger.info(
            "bulk_cost_estimated",
            estimate_id=str(bulk.estimate_id),
            screening_count=len(screenings),
            total_before_discount=float(bulk.total_before_discount),
            volume_discount=float(bulk.volume_discount),
            total_estimated=float(bulk.total_estimated),
        )

        return bulk

    def compare_to_actual(
        self,
        estimate_id: UUID,
        actual_cost: Decimal,
        *,
        actual_breakdown: dict[CostCategory, Decimal] | None = None,
    ) -> CostComparison:
        """Compare estimate to actual costs.

        Args:
            estimate_id: ID of the original estimate.
            actual_cost: Actual cost incurred.
            actual_breakdown: Optional breakdown by category.

        Returns:
            CostComparison with accuracy metrics.
        """
        estimate = self._estimates.get(estimate_id)
        if not estimate:
            raise ValueError(f"Estimate {estimate_id} not found")

        comparison = CostComparison(
            estimate_id=estimate_id,
            estimated_cost=estimate.total_estimated,
            actual_cost=actual_cost,
        )

        # Calculate difference
        comparison.difference = actual_cost - estimate.total_estimated

        # Calculate accuracy
        if estimate.total_estimated > 0:
            error_ratio = abs(comparison.difference) / estimate.total_estimated
            comparison.accuracy_percentage = max(0, (1 - float(error_ratio))) * 100

        # Category comparison
        if actual_breakdown:
            for category in CostCategory:
                estimated = estimate.breakdown.by_category.get(category, Decimal("0.00"))
                actual = actual_breakdown.get(category, Decimal("0.00"))
                if estimated > 0 or actual > 0:
                    comparison.by_category[category] = (estimated, actual)

        logger.info(
            "cost_comparison",
            estimate_id=str(estimate_id),
            estimated=float(estimate.total_estimated),
            actual=float(actual_cost),
            difference=float(comparison.difference),
            accuracy=comparison.accuracy_percentage,
        )

        return comparison

    def get_check_type_cost(
        self,
        check_type: CheckType,
        tier: ServiceTier,
        locale: Locale,
    ) -> Decimal:
        """Get estimated cost for a specific check type.

        Args:
            check_type: The check type.
            tier: Service tier.
            locale: Locale for pricing.

        Returns:
            Estimated cost for the check type.
        """
        sources = self._get_available_sources(check_type, tier, locale)
        if not sources:
            return Decimal("0.00")

        # Use cheapest available source
        min_cost = min(Decimal(str(s.cost_per_query)) for s in sources)

        # Apply locale multiplier
        locale_key = locale.value.split("_")[0] if "_" in locale.value else locale.value
        locale_multiplier = Decimal(str(self.config.locale_multipliers.get(locale_key, 1.0)))

        return min_cost * locale_multiplier

    def get_tier_comparison(
        self,
        degree: SearchDegree,
        check_types: set[CheckType],
        locale: Locale,
    ) -> dict[ServiceTier, CostEstimate]:
        """Get cost estimates for both tiers for comparison.

        Args:
            degree: Search degree.
            check_types: Check types to perform.
            locale: Locale.

        Returns:
            Dict mapping tier to cost estimate.
        """
        result = {}
        for tier in ServiceTier:
            # Skip if tier doesn't support degree
            if tier == ServiceTier.STANDARD and degree == SearchDegree.D3:
                continue

            result[tier] = self.estimate_screening_cost(
                tier=tier,
                degree=degree,
                check_types=check_types,
                locale=locale,
            )

        return result

    def _estimate_provider_costs(
        self,
        check_types: set[CheckType],
        tier: ServiceTier,
        locale: Locale,
        degree_multiplier: Decimal,
        locale_multiplier: Decimal,
        estimate: CostEstimate,
    ) -> Decimal:
        """Estimate data provider costs."""
        total = Decimal("0.00")

        for check_type in check_types:
            sources = self._get_available_sources(check_type, tier, locale)
            if not sources:
                estimate.warnings.append(
                    f"No data source available for {check_type.value} in {locale.value}"
                )
                continue

            # Use cheapest available source
            source = min(sources, key=lambda s: s.cost_per_query)
            cost = Decimal(str(source.cost_per_query)) * degree_multiplier * locale_multiplier

            estimate.breakdown.add_cost(
                cost,
                CostCategory.DATA_PROVIDER,
                check_type=check_type,
                provider_id=source.provider_id,
            )
            estimate.estimated_queries += 1
            total += cost

        return total

    def _estimate_ai_costs(
        self,
        tier: ServiceTier,
        degree: SearchDegree,
        check_count: int,
    ) -> Decimal:
        """Estimate AI analysis costs."""
        cost = self.config.ai_base_cost

        # Add per-finding estimate
        estimated_findings = check_count * 2  # Rough estimate
        cost += self.config.ai_cost_per_finding * Decimal(str(estimated_findings))

        # Add synthesis cost for Enhanced
        if tier == ServiceTier.ENHANCED:
            cost += self.config.ai_synthesis_cost

        # Higher degrees need more analysis
        if degree == SearchDegree.D2:
            cost *= Decimal("1.3")
        elif degree == SearchDegree.D3:
            cost *= Decimal("1.8")

        return cost

    def _estimate_network_costs(self, degree: SearchDegree) -> Decimal:
        """Estimate network analysis costs for D2/D3."""
        if degree == SearchDegree.D2:
            max_entities = self.config.max_network_entities_d2
        elif degree == SearchDegree.D3:
            max_entities = self.config.max_network_entities_d3
        else:
            return Decimal("0.00")

        # Estimate 50% of max entities
        estimated_entities = max_entities // 2
        return self.config.network_analysis_per_entity * Decimal(str(estimated_entities))

    def _get_available_sources(
        self,
        check_type: CheckType,
        tier: ServiceTier,
        locale: Locale,
    ) -> list[DataSourceSpec]:
        """Get available data sources for a check type."""
        sources = self._source_by_check_type.get(check_type, [])

        # Filter by tier
        if tier == ServiceTier.STANDARD:
            sources = [s for s in sources if s.tier == DataSourceTier.CORE]

        # Filter by locale
        sources = [s for s in sources if s.available_in_locale(locale)]

        return sources

    def _get_degree_multiplier(self, degree: SearchDegree) -> Decimal:
        """Get cost multiplier for search degree."""
        multipliers = {
            SearchDegree.D1: self.config.d1_multiplier,
            SearchDegree.D2: self.config.d2_multiplier,
            SearchDegree.D3: self.config.d3_multiplier,
        }
        return Decimal(str(multipliers.get(degree, 1.0)))

    def _get_volume_discount(self, count: int) -> float:
        """Get volume discount rate for screening count."""
        discount = 0.0
        for threshold, rate in sorted(self.config.volume_discount_tiers, reverse=True):
            if count >= threshold:
                discount = rate
                break
        return discount

    def _calculate_confidence(
        self,
        check_types: set[CheckType],
        locale: Locale,
    ) -> float:
        """Calculate estimate confidence based on data availability."""
        if not check_types:
            return 0.5

        available_count = 0
        for check_type in check_types:
            sources = self._source_by_check_type.get(check_type, [])
            if any(s.available_in_locale(locale) for s in sources):
                available_count += 1

        # Base confidence from coverage
        coverage = available_count / len(check_types)

        # Locale affects confidence
        locale_key = locale.value.split("_")[0] if "_" in locale.value else locale.value
        locale_known = locale_key in self.config.locale_multipliers

        if locale_known:
            return min(0.95, coverage * 0.9 + 0.1)
        else:
            return min(0.75, coverage * 0.7)

    def reset(self) -> None:
        """Reset stored estimates (for testing)."""
        self._estimates.clear()


# =============================================================================
# Factory Functions
# =============================================================================


def create_cost_estimator(
    config: EstimatorConfig | None = None,
    data_sources: list[DataSourceSpec] | None = None,
) -> CostEstimator:
    """Create a cost estimator.

    Args:
        config: Optional estimator configuration.
        data_sources: Optional data source specifications.

    Returns:
        Configured CostEstimator.
    """
    return CostEstimator(
        config=config,
        data_sources=data_sources,
    )


# Global estimator instance
_estimator: CostEstimator | None = None


def get_cost_estimator() -> CostEstimator:
    """Get the global cost estimator.

    Returns:
        Shared CostEstimator instance.
    """
    global _estimator
    if _estimator is None:
        _estimator = CostEstimator()
    return _estimator


def reset_cost_estimator() -> None:
    """Reset the global cost estimator.

    Primarily for testing purposes.
    """
    global _estimator
    _estimator = None
