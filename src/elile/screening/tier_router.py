"""Tier router for service tier-based request routing.

This module implements routing logic based on service tier (Standard vs Enhanced),
determining which data sources, handlers, and capabilities are available.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.agent.state import SearchDegree, ServiceTier
from elile.compliance.types import Locale
from elile.providers.types import CheckType


# =============================================================================
# Data Source Types
# =============================================================================


class DataSourceTier(str, Enum):
    """Tier classification for data sources."""

    CORE = "core"  # Available in Standard tier
    PREMIUM = "premium"  # Only available in Enhanced tier


@dataclass
class DataSourceSpec:
    """Specification for a data source.

    Attributes:
        source_id: Unique identifier for the data source.
        provider_id: ID of the provider offering this source.
        name: Human-readable name.
        tier: Whether this is a core or premium source.
        check_types: Check types this source supports.
        locales: Locales where this source is available.
        cost_per_query: Estimated cost per query.
        avg_response_time_ms: Average response time in milliseconds.
        reliability_score: Reliability score (0.0-1.0).
        requires_consent: Whether explicit consent is required.
    """

    source_id: str
    provider_id: str
    name: str
    tier: DataSourceTier = DataSourceTier.CORE
    check_types: list[CheckType] = field(default_factory=list)
    locales: list[Locale] = field(default_factory=list)
    cost_per_query: float = 0.0
    avg_response_time_ms: int = 1000
    reliability_score: float = 0.9
    requires_consent: bool = True

    def supports_check(self, check_type: CheckType) -> bool:
        """Check if source supports a check type."""
        return check_type in self.check_types

    def available_in_locale(self, locale: Locale) -> bool:
        """Check if source is available in locale."""
        return len(self.locales) == 0 or locale in self.locales


# =============================================================================
# Handler Protocol
# =============================================================================


class ScreeningHandler(Protocol):
    """Protocol for screening handlers."""

    async def execute(
        self,
        request: Any,
        available_sources: list[DataSourceSpec],
    ) -> Any:
        """Execute screening with available sources."""
        ...


# =============================================================================
# Configuration
# =============================================================================


class TierRouterConfig(BaseModel):
    """Configuration for tier router."""

    # Standard tier limits
    standard_max_queries: int = Field(default=50, description="Max queries for Standard")
    standard_max_sources: int = Field(default=10, description="Max sources for Standard")
    standard_max_degree: SearchDegree = Field(
        default=SearchDegree.D1,
        description="Max search degree for Standard",
    )

    # Enhanced tier limits
    enhanced_max_queries: int = Field(default=200, description="Max queries for Enhanced")
    enhanced_max_sources: int = Field(default=50, description="Max sources for Enhanced")
    enhanced_max_degree: SearchDegree = Field(
        default=SearchDegree.D3,
        description="Max search degree for Enhanced",
    )

    # Cost limits
    standard_budget_limit: float = Field(default=50.0, description="Budget limit for Standard")
    enhanced_budget_limit: float = Field(default=500.0, description="Budget limit for Enhanced")

    # Feature flags
    standard_network_analysis: bool = Field(
        default=False,
        description="Enable network analysis for Standard",
    )
    enhanced_network_analysis: bool = Field(
        default=True,
        description="Enable network analysis for Enhanced",
    )


# =============================================================================
# Tier Capabilities
# =============================================================================


@dataclass
class TierCapabilities:
    """Capabilities available for a service tier.

    Attributes:
        tier: The service tier.
        max_queries: Maximum queries allowed.
        max_sources: Maximum data sources allowed.
        max_degree: Maximum search degree allowed.
        budget_limit: Maximum budget allowed.
        network_analysis: Whether network analysis is enabled.
        available_check_types: Check types available in this tier.
        restrictions: List of restrictions applied.
    """

    tier: ServiceTier
    max_queries: int = 50
    max_sources: int = 10
    max_degree: SearchDegree = SearchDegree.D1
    budget_limit: float = 50.0
    network_analysis: bool = False
    available_check_types: list[CheckType] = field(default_factory=list)
    restrictions: list[str] = field(default_factory=list)

    def allows_degree(self, degree: SearchDegree) -> bool:
        """Check if degree is allowed."""
        degree_order = {SearchDegree.D1: 1, SearchDegree.D2: 2, SearchDegree.D3: 3}
        return degree_order.get(degree, 0) <= degree_order.get(self.max_degree, 1)

    def allows_check_type(self, check_type: CheckType) -> bool:
        """Check if check type is allowed."""
        return len(self.available_check_types) == 0 or check_type in self.available_check_types

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tier": self.tier.value,
            "max_queries": self.max_queries,
            "max_sources": self.max_sources,
            "max_degree": self.max_degree.value,
            "budget_limit": self.budget_limit,
            "network_analysis": self.network_analysis,
            "available_check_types": [ct.value for ct in self.available_check_types],
            "restrictions": self.restrictions,
        }


# =============================================================================
# Routing Result
# =============================================================================


@dataclass
class RoutingResult:
    """Result of routing a request to appropriate resources.

    Attributes:
        routing_id: Unique identifier for this routing decision.
        tier: Service tier of the request.
        capabilities: Capabilities for this tier.
        available_sources: Data sources available for this request.
        filtered_sources: Sources filtered out due to tier/locale restrictions.
        handler_type: Type of handler to use.
        estimated_cost: Estimated cost for this request.
        warnings: Any warnings about the routing.
    """

    routing_id: UUID = field(default_factory=uuid7)
    tier: ServiceTier = ServiceTier.STANDARD
    capabilities: TierCapabilities | None = None
    available_sources: list[DataSourceSpec] = field(default_factory=list)
    filtered_sources: list[str] = field(default_factory=list)
    handler_type: str = "standard"
    estimated_cost: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "routing_id": str(self.routing_id),
            "tier": self.tier.value,
            "capabilities": self.capabilities.to_dict() if self.capabilities else None,
            "available_sources_count": len(self.available_sources),
            "filtered_sources": self.filtered_sources,
            "handler_type": self.handler_type,
            "estimated_cost": self.estimated_cost,
            "warnings": self.warnings,
        }


# =============================================================================
# Tier Router
# =============================================================================


class TierRouter:
    """Routes requests based on service tier.

    Determines which data sources, handlers, and capabilities are available
    based on the service tier (Standard vs Enhanced).
    """

    def __init__(
        self,
        config: TierRouterConfig | None = None,
        data_sources: list[DataSourceSpec] | None = None,
    ) -> None:
        """Initialize tier router.

        Args:
            config: Router configuration.
            data_sources: Available data sources.
        """
        self.config = config or TierRouterConfig()
        self._data_sources = data_sources or []
        self._handlers: dict[ServiceTier, ScreeningHandler] = {}

    def register_handler(self, tier: ServiceTier, handler: ScreeningHandler) -> None:
        """Register a handler for a service tier.

        Args:
            tier: Service tier.
            handler: Handler to register.
        """
        self._handlers[tier] = handler

    def add_data_source(self, source: DataSourceSpec) -> None:
        """Add a data source.

        Args:
            source: Data source specification.
        """
        self._data_sources.append(source)

    def get_capabilities(self, tier: ServiceTier) -> TierCapabilities:
        """Get capabilities for a service tier.

        Args:
            tier: Service tier.

        Returns:
            Capabilities for the tier.
        """
        if tier == ServiceTier.STANDARD:
            return TierCapabilities(
                tier=tier,
                max_queries=self.config.standard_max_queries,
                max_sources=self.config.standard_max_sources,
                max_degree=self.config.standard_max_degree,
                budget_limit=self.config.standard_budget_limit,
                network_analysis=self.config.standard_network_analysis,
                available_check_types=self._get_standard_check_types(),
                restrictions=["D2/D3 search requires Enhanced tier"],
            )
        else:  # ENHANCED
            return TierCapabilities(
                tier=tier,
                max_queries=self.config.enhanced_max_queries,
                max_sources=self.config.enhanced_max_sources,
                max_degree=self.config.enhanced_max_degree,
                budget_limit=self.config.enhanced_budget_limit,
                network_analysis=self.config.enhanced_network_analysis,
                available_check_types=self._get_all_check_types(),
                restrictions=[],
            )

    def _get_standard_check_types(self) -> list[CheckType]:
        """Get check types available for Standard tier."""
        return [
            CheckType.IDENTITY_BASIC,
            CheckType.EMPLOYMENT_VERIFICATION,
            CheckType.EDUCATION_VERIFICATION,
            CheckType.CRIMINAL_NATIONAL,
            CheckType.CREDIT_REPORT,
            CheckType.SSN_TRACE,
        ]

    def _get_all_check_types(self) -> list[CheckType]:
        """Get all check types (Enhanced tier)."""
        return list(CheckType)

    def get_available_sources(
        self,
        tier: ServiceTier,
        locale: Locale | None = None,
        check_types: list[CheckType] | None = None,
    ) -> list[DataSourceSpec]:
        """Get data sources available for a tier.

        Args:
            tier: Service tier.
            locale: Optional locale to filter by.
            check_types: Optional check types to filter by.

        Returns:
            List of available data sources.
        """
        sources: list[DataSourceSpec] = []

        for source in self._data_sources:
            # Filter by tier
            if tier == ServiceTier.STANDARD and source.tier == DataSourceTier.PREMIUM:
                continue

            # Filter by locale
            if locale and not source.available_in_locale(locale):
                continue

            # Filter by check type
            if check_types:
                if not any(source.supports_check(ct) for ct in check_types):
                    continue

            sources.append(source)

        return sources

    def get_core_sources(self) -> list[DataSourceSpec]:
        """Get core data sources (available in all tiers).

        Returns:
            List of core data sources.
        """
        return [s for s in self._data_sources if s.tier == DataSourceTier.CORE]

    def get_premium_sources(self) -> list[DataSourceSpec]:
        """Get premium data sources (Enhanced tier only).

        Returns:
            List of premium data sources.
        """
        return [s for s in self._data_sources if s.tier == DataSourceTier.PREMIUM]

    def get_all_sources(self) -> list[DataSourceSpec]:
        """Get all data sources.

        Returns:
            All data sources.
        """
        return list(self._data_sources)

    def route_request(
        self,
        tier: ServiceTier,
        locale: Locale,
        degree: SearchDegree,
        check_types: list[CheckType] | None = None,
    ) -> RoutingResult:
        """Route a request to appropriate resources.

        Args:
            tier: Service tier.
            locale: Geographic locale.
            degree: Search degree.
            check_types: Optional check types to include.

        Returns:
            RoutingResult with available resources.
        """
        result = RoutingResult(tier=tier)
        capabilities = self.get_capabilities(tier)
        result.capabilities = capabilities

        # Check degree restrictions
        if not capabilities.allows_degree(degree):
            result.warnings.append(
                f"Requested degree {degree.value} exceeds tier limit {capabilities.max_degree.value}"
            )

        # Get available sources
        result.available_sources = self.get_available_sources(
            tier=tier,
            locale=locale,
            check_types=check_types,
        )

        # Track filtered sources
        all_sources = set(s.source_id for s in self._data_sources)
        available_ids = set(s.source_id for s in result.available_sources)
        result.filtered_sources = list(all_sources - available_ids)

        # Set handler type
        result.handler_type = "enhanced" if tier == ServiceTier.ENHANCED else "standard"

        # Estimate cost
        result.estimated_cost = self._estimate_cost(
            sources=result.available_sources,
            degree=degree,
        )

        return result

    def _estimate_cost(
        self,
        sources: list[DataSourceSpec],
        degree: SearchDegree,
    ) -> float:
        """Estimate cost for a request.

        Args:
            sources: Available data sources.
            degree: Search degree.

        Returns:
            Estimated cost.
        """
        base_cost = sum(s.cost_per_query for s in sources)

        # Multiply by degree factor
        degree_multiplier = {
            SearchDegree.D1: 1.0,
            SearchDegree.D2: 2.5,
            SearchDegree.D3: 5.0,
        }
        return base_cost * degree_multiplier.get(degree, 1.0)

    def validate_request(
        self,
        tier: ServiceTier,
        degree: SearchDegree,
        estimated_cost: float | None = None,
    ) -> tuple[bool, list[str]]:
        """Validate a request against tier restrictions.

        Args:
            tier: Service tier.
            degree: Search degree.
            estimated_cost: Optional estimated cost.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors: list[str] = []
        capabilities = self.get_capabilities(tier)

        # Check degree
        if not capabilities.allows_degree(degree):
            errors.append(
                f"Search degree {degree.value} not allowed for {tier.value} tier. "
                f"Maximum allowed: {capabilities.max_degree.value}"
            )

        # Check budget
        if estimated_cost is not None and estimated_cost > capabilities.budget_limit:
            errors.append(
                f"Estimated cost ${estimated_cost:.2f} exceeds "
                f"{tier.value} tier limit ${capabilities.budget_limit:.2f}"
            )

        return len(errors) == 0, errors

    def get_handler(self, tier: ServiceTier) -> ScreeningHandler | None:
        """Get registered handler for a tier.

        Args:
            tier: Service tier.

        Returns:
            Registered handler or None.
        """
        return self._handlers.get(tier)


# =============================================================================
# Factory Functions
# =============================================================================


def create_tier_router(
    config: TierRouterConfig | None = None,
) -> TierRouter:
    """Create a tier router with default configuration.

    Args:
        config: Optional router configuration.

    Returns:
        Configured TierRouter.
    """
    return TierRouter(config=config or TierRouterConfig())


def create_default_data_sources() -> list[DataSourceSpec]:
    """Create default set of data sources.

    Returns:
        List of default data sources.
    """
    return [
        # Core sources (Standard tier)
        DataSourceSpec(
            source_id="sterling-identity",
            provider_id="sterling",
            name="Sterling Identity Verification",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.IDENTITY_BASIC, CheckType.SSN_TRACE],
            locales=[Locale.US],
            cost_per_query=2.50,
            avg_response_time_ms=500,
            reliability_score=0.95,
        ),
        DataSourceSpec(
            source_id="sterling-employment",
            provider_id="sterling",
            name="Sterling Employment Verification",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.EMPLOYMENT_VERIFICATION],
            locales=[Locale.US],
            cost_per_query=15.00,
            avg_response_time_ms=2000,
            reliability_score=0.90,
        ),
        DataSourceSpec(
            source_id="sterling-education",
            provider_id="sterling",
            name="Sterling Education Verification",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.EDUCATION_VERIFICATION],
            locales=[Locale.US],
            cost_per_query=10.00,
            avg_response_time_ms=1500,
            reliability_score=0.85,
        ),
        DataSourceSpec(
            source_id="ncrc-criminal",
            provider_id="ncrc",
            name="National Criminal Records Check",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.CRIMINAL_NATIONAL],
            locales=[Locale.US],
            cost_per_query=20.00,
            avg_response_time_ms=3000,
            reliability_score=0.92,
        ),
        DataSourceSpec(
            source_id="experian-credit",
            provider_id="experian",
            name="Experian Credit Report",
            tier=DataSourceTier.CORE,
            check_types=[CheckType.CREDIT_REPORT],
            locales=[Locale.US],
            cost_per_query=25.00,
            avg_response_time_ms=1000,
            reliability_score=0.98,
        ),
        # Premium sources (Enhanced tier only)
        DataSourceSpec(
            source_id="worldcheck-sanctions",
            provider_id="worldcheck",
            name="World-Check Sanctions & PEP",
            tier=DataSourceTier.PREMIUM,
            check_types=[CheckType.SANCTIONS_OFAC, CheckType.SANCTIONS_PEP],
            locales=[],  # Global
            cost_per_query=35.00,
            avg_response_time_ms=800,
            reliability_score=0.99,
        ),
        DataSourceSpec(
            source_id="lexis-civil",
            provider_id="lexisnexis",
            name="LexisNexis Civil Litigation",
            tier=DataSourceTier.PREMIUM,
            check_types=[CheckType.CIVIL_LITIGATION],
            locales=[Locale.US],
            cost_per_query=30.00,
            avg_response_time_ms=2500,
            reliability_score=0.88,
        ),
        DataSourceSpec(
            source_id="dowjones-adverse",
            provider_id="dowjones",
            name="Dow Jones Adverse Media",
            tier=DataSourceTier.PREMIUM,
            check_types=[CheckType.ADVERSE_MEDIA],
            locales=[],  # Global
            cost_per_query=40.00,
            avg_response_time_ms=1200,
            reliability_score=0.90,
        ),
        DataSourceSpec(
            source_id="interpol-global",
            provider_id="interpol",
            name="Interpol Red Notice Check",
            tier=DataSourceTier.PREMIUM,
            check_types=[CheckType.CRIMINAL_INTERNATIONAL],
            locales=[],  # Global
            cost_per_query=50.00,
            avg_response_time_ms=3500,
            reliability_score=0.95,
        ),
    ]
