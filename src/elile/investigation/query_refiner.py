"""Query Refiner for SAR loop REFINE phase.

This module implements the REFINE phase of the SAR loop, generating targeted
queries to fill gaps identified during assessment. It prioritizes gaps and
creates focused follow-up queries to improve confidence.

Key features:
- Gap-based query generation
- Priority-based gap ordering
- Query deduplication
- Type-specific refinement strategies
- Knowledge base enrichment for better targeting
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType, KnowledgeBase, ServiceTier
from elile.compliance.types import CheckType, Locale
from elile.core.logging import get_logger
from elile.investigation.query_planner import INFO_TYPE_TO_CHECK_TYPES, QueryType, SearchQuery
from elile.investigation.result_assessor import AssessmentResult, Gap

logger = get_logger(__name__)


class RefinerConfig(BaseModel):
    """Configuration for query refinement."""

    max_queries_per_gap: int = Field(default=3, ge=1, le=10)
    max_total_queries: int = Field(default=15, ge=1, le=50)
    include_alternative_providers: bool = Field(default=True)
    min_gap_priority: int = Field(default=3, ge=1, le=3)  # Include gaps up to this priority


@dataclass
class RefinementResult:
    """Result of query refinement for a single assessment."""

    info_type: InformationType
    iteration_number: int
    gaps_addressed: int
    queries: list[SearchQuery]
    skipped_gaps: list[Gap] = field(default_factory=list)

    @property
    def query_count(self) -> int:
        """Number of queries generated."""
        return len(self.queries)

    @property
    def has_queries(self) -> bool:
        """Whether any queries were generated."""
        return len(self.queries) > 0


# Gap-specific strategies for query generation
GAP_STRATEGIES: dict[str, dict[str, Any]] = {
    # Identity gaps
    "missing_address": {
        "check_types": [CheckType.SSN_TRACE, CheckType.IDENTITY_BASIC],
        "focus": "address_history",
        "priority_boost": 2,
    },
    "missing_dob": {
        "check_types": [CheckType.IDENTITY_BASIC],
        "focus": "identity_verification",
        "priority_boost": 3,
    },
    "missing_name_variant": {
        "check_types": [CheckType.SSN_TRACE, CheckType.IDENTITY_BASIC],
        "focus": "name_variants",
        "priority_boost": 1,
    },
    "no_address_found": {
        "check_types": [CheckType.SSN_TRACE],
        "focus": "full_address_search",
        "priority_boost": 2,
    },
    # Employment gaps
    "no_employment_found": {
        "check_types": [CheckType.EMPLOYMENT_VERIFICATION],
        "focus": "employment_discovery",
        "priority_boost": 3,
    },
    "missing_end_date": {
        "check_types": [CheckType.EMPLOYMENT_VERIFICATION],
        "focus": "employment_dates",
        "priority_boost": 1,
    },
    "missing_employer": {
        "check_types": [CheckType.EMPLOYMENT_VERIFICATION],
        "focus": "employment_verification",
        "priority_boost": 2,
    },
    # Education gaps
    "no_education_found": {
        "check_types": [CheckType.EDUCATION_VERIFICATION, CheckType.EDUCATION_DEGREE],
        "focus": "education_discovery",
        "priority_boost": 3,
    },
    "missing_school": {
        "check_types": [CheckType.EDUCATION_VERIFICATION],
        "focus": "school_verification",
        "priority_boost": 2,
    },
    # Criminal gaps
    "missing_criminal_record": {
        "check_types": [CheckType.CRIMINAL_NATIONAL, CheckType.CRIMINAL_COUNTY],
        "focus": "criminal_search",
        "priority_boost": 2,
    },
    "missing_criminal_clear": {
        "check_types": [CheckType.CRIMINAL_NATIONAL],
        "focus": "criminal_clearance",
        "priority_boost": 1,
    },
    # Credit gaps
    "missing_credit_score": {
        "check_types": [CheckType.CREDIT_REPORT],
        "focus": "credit_inquiry",
        "priority_boost": 2,
    },
    "missing_credit_status": {
        "check_types": [CheckType.CREDIT_REPORT],
        "focus": "credit_status",
        "priority_boost": 1,
    },
    # License gaps
    "missing_license": {
        "check_types": [CheckType.LICENSE_VERIFICATION],
        "focus": "license_search",
        "priority_boost": 2,
    },
}


class QueryRefiner:
    """Refines queries to target identified gaps.

    The QueryRefiner generates targeted follow-up queries based on gaps
    identified during the ASSESS phase. It prioritizes gaps by criticality
    and uses type-specific strategies to generate effective queries.

    Example:
        ```python
        refiner = QueryRefiner()
        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=kb,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "checkr"],
        )

        # Execute refined queries
        for query in result.queries:
            execute(query)
        ```
    """

    def __init__(self, config: RefinerConfig | None = None):
        """Initialize the query refiner.

        Args:
            config: Optional refinement configuration.
        """
        self.config = config or RefinerConfig()
        self._query_signatures: set[str] = set()

    def refine_queries(
        self,
        assessment: AssessmentResult,
        knowledge_base: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier,
        available_providers: list[str],
    ) -> RefinementResult:
        """Generate refinement queries targeting assessment gaps.

        Args:
            assessment: Assessment with identified gaps.
            knowledge_base: Current knowledge base for enrichment.
            locale: Subject locale for jurisdiction.
            tier: Service tier for available check types.
            available_providers: List of provider IDs.

        Returns:
            RefinementResult with targeted queries.
        """
        # Reset deduplication for this refinement
        self._query_signatures.clear()

        queries: list[SearchQuery] = []
        skipped_gaps: list[Gap] = []

        # Get queryable gaps and prioritize them
        queryable_gaps = [g for g in assessment.gaps_identified if g.can_query]
        prioritized_gaps = self._prioritize_gaps(queryable_gaps, assessment.info_type)

        # Filter by minimum priority
        eligible_gaps = [g for g in prioritized_gaps if g.priority <= self.config.min_gap_priority]

        logger.debug(
            "Refining queries",
            info_type=assessment.info_type.value,
            total_gaps=len(assessment.gaps_identified),
            queryable_gaps=len(queryable_gaps),
            eligible_gaps=len(eligible_gaps),
        )

        # Generate queries for each gap
        for gap in eligible_gaps:
            gap_queries = self._generate_gap_queries(
                gap=gap,
                info_type=assessment.info_type,
                knowledge_base=knowledge_base,
                locale=locale,
                tier=tier,
                available_providers=available_providers,
                iteration_number=assessment.iteration_number + 1,
            )

            if gap_queries:
                queries.extend(gap_queries)
            else:
                skipped_gaps.append(gap)

            # Check if we've reached the max total queries
            if len(queries) >= self.config.max_total_queries:
                break

        # Final deduplication
        queries = self._deduplicate_queries(queries)

        # Trim to max if needed
        queries = queries[: self.config.max_total_queries]

        # Sort by priority (higher first)
        queries.sort(key=lambda q: q.priority, reverse=True)

        logger.info(
            "Query refinement complete",
            info_type=assessment.info_type.value,
            gaps_addressed=len(eligible_gaps) - len(skipped_gaps),
            queries_generated=len(queries),
        )

        return RefinementResult(
            info_type=assessment.info_type,
            iteration_number=assessment.iteration_number + 1,
            gaps_addressed=len(eligible_gaps) - len(skipped_gaps),
            queries=queries,
            skipped_gaps=skipped_gaps,
        )

    def _prioritize_gaps(
        self,
        gaps: list[Gap],
        _info_type: InformationType,  # Reserved for type-specific prioritization
    ) -> list[Gap]:
        """Prioritize gaps by criticality.

        Critical gaps (fundamental missing data) are processed first.
        Priority is determined by:
        1. Gap's own priority (lower number = higher priority)
        2. Whether it's a "no_*" or "missing_*" gap type
        3. Relationship to the information type

        Args:
            gaps: List of gaps to prioritize.
            info_type: Information type context.

        Returns:
            Sorted list of gaps (highest priority first).
        """

        def gap_sort_key(gap: Gap) -> tuple[int, int, str]:
            """Generate sort key for gap prioritization.

            Returns tuple of (category, priority, gap_type) where lower is higher priority.
            """
            # Category 1: Complete missing data (highest priority)
            if gap.gap_type.startswith("no_"):
                category = 1
            # Category 2: Missing specific field
            elif gap.gap_type.startswith("missing_"):
                category = 2
            # Category 3: Other gaps
            else:
                category = 3

            return (category, gap.priority, gap.gap_type)

        return sorted(gaps, key=gap_sort_key)

    def _generate_gap_queries(
        self,
        gap: Gap,
        info_type: InformationType,
        knowledge_base: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier,
        available_providers: list[str],
        iteration_number: int,
    ) -> list[SearchQuery]:
        """Generate queries targeting a specific gap.

        Uses gap-specific strategies when available, otherwise falls back
        to default query generation based on information type.

        Args:
            gap: Gap to address.
            info_type: Information type.
            knowledge_base: Knowledge base for enrichment.
            locale: Subject locale.
            tier: Service tier.
            available_providers: Available provider IDs.
            iteration_number: Target iteration number.

        Returns:
            List of queries targeting this gap.
        """
        queries: list[SearchQuery] = []

        # Get primary name for queries
        primary_name = (
            knowledge_base.confirmed_names[0] if knowledge_base.confirmed_names else None
        )
        if not primary_name:
            logger.debug("Cannot generate gap queries without primary name", gap_type=gap.gap_type)
            return queries

        # Get gap-specific strategy
        strategy = GAP_STRATEGIES.get(gap.gap_type)

        # Determine check types to use
        if strategy:
            check_types = strategy["check_types"]
            focus = strategy.get("focus", gap.gap_type)
            priority_boost = strategy.get("priority_boost", 0)
        else:
            # Fall back to info type's check types
            check_types = self._get_check_types_for_info_type(info_type, tier)
            focus = gap.gap_type
            priority_boost = 0

        if not check_types:
            logger.debug("No check types available for gap", gap_type=gap.gap_type)
            return queries

        # Build search params
        search_params = self._build_search_params(
            gap=gap,
            knowledge_base=knowledge_base,
            primary_name=primary_name,
            focus=focus,
            locale=locale,
        )

        # Generate queries for each provider/check_type combination
        queries_for_gap = 0
        for check_type in check_types:
            if queries_for_gap >= self.config.max_queries_per_gap:
                break

            for provider_id in available_providers:
                if queries_for_gap >= self.config.max_queries_per_gap:
                    break

                # Create the query
                query = SearchQuery(
                    query_id=uuid7(),
                    info_type=info_type,
                    query_type=QueryType.GAP_FILL,
                    provider_id=provider_id,
                    check_type=check_type,
                    search_params=search_params.copy(),
                    iteration_number=iteration_number,
                    targeting_gap=gap.gap_type,
                    enriched_from=[InformationType.IDENTITY],
                    priority=8 + priority_boost,
                )

                # Check for duplicates
                signature = self._get_query_signature(query)
                if signature not in self._query_signatures:
                    self._query_signatures.add(signature)
                    queries.append(query)
                    queries_for_gap += 1

        return queries

    def _build_search_params(
        self,
        gap: Gap,
        knowledge_base: KnowledgeBase,
        primary_name: str,
        focus: str,
        locale: Locale,
    ) -> dict[str, Any]:
        """Build search parameters for a gap query.

        Enriches search params with all available knowledge base data
        relevant to the gap being targeted.

        Args:
            gap: Gap being targeted.
            knowledge_base: Knowledge base for enrichment.
            primary_name: Subject's primary name.
            focus: Query focus area.
            locale: Subject locale.

        Returns:
            Dictionary of search parameters.
        """
        params: dict[str, Any] = {
            "name": primary_name,
            "gap_focus": gap.gap_type,
            "focus": focus,
        }

        # Add name variants
        if len(knowledge_base.confirmed_names) > 1:
            params["name_variants"] = knowledge_base.confirmed_names[1:]

        # Add DOB if known
        if knowledge_base.confirmed_dob:
            params["dob"] = knowledge_base.confirmed_dob.isoformat()

        # Add SSN last 4 if known
        if knowledge_base.confirmed_ssn_last4:
            params["ssn_last4"] = knowledge_base.confirmed_ssn_last4

        # Add locale
        params["locale"] = locale.value

        # Gap-type specific enrichment
        if "employment" in gap.gap_type.lower():
            if knowledge_base.employers:
                params["known_employers"] = [emp.employer_name for emp in knowledge_base.employers]

        elif "education" in gap.gap_type.lower():
            if knowledge_base.schools:
                params["known_schools"] = [s.institution_name for s in knowledge_base.schools]

        elif "address" in gap.gap_type.lower():
            if knowledge_base.confirmed_addresses:
                params["known_addresses"] = [
                    {
                        "city": addr.city,
                        "state": addr.state,
                        "county": addr.county,
                    }
                    for addr in knowledge_base.confirmed_addresses
                ]
            if knowledge_base.known_states:
                params["known_states"] = knowledge_base.known_states
            if knowledge_base.known_counties:
                params["known_counties"] = knowledge_base.known_counties

        elif "criminal" in gap.gap_type.lower():
            if knowledge_base.known_counties:
                params["counties"] = knowledge_base.known_counties
            if knowledge_base.known_states:
                params["states"] = knowledge_base.known_states

        elif "license" in gap.gap_type.lower() and knowledge_base.licenses:
            params["license_types"] = list(
                {lic.license_type for lic in knowledge_base.licenses}
            )

        return params

    def _get_check_types_for_info_type(
        self,
        info_type: InformationType,
        tier: ServiceTier,
    ) -> list[CheckType]:
        """Get applicable check types for an info type and tier.

        Args:
            info_type: Information type.
            tier: Service tier.

        Returns:
            List of applicable check types.
        """
        check_types = INFO_TYPE_TO_CHECK_TYPES.get(info_type, [])

        # Filter out Enhanced-only check types for Standard tier
        if tier == ServiceTier.STANDARD:
            enhanced_only = {
                CheckType.IDENTITY_BIOMETRIC,
                CheckType.ADVERSE_MEDIA_AI,
                CheckType.DIGITAL_FOOTPRINT,
                CheckType.SOCIAL_MEDIA,
                CheckType.NETWORK_D3,
                CheckType.DARK_WEB_MONITORING,
            }
            check_types = [ct for ct in check_types if ct not in enhanced_only]

        return check_types

    def _get_query_signature(self, query: SearchQuery) -> str:
        """Generate a signature for query deduplication.

        Args:
            query: Query to generate signature for.

        Returns:
            Unique string signature.
        """
        key_parts = [
            query.provider_id,
            query.check_type.value,
            query.targeting_gap or "",
            str(sorted(query.search_params.items())),
        ]
        return "|".join(key_parts)

    def _deduplicate_queries(self, queries: list[SearchQuery]) -> list[SearchQuery]:
        """Remove duplicate queries from the list.

        Args:
            queries: List of queries to deduplicate.

        Returns:
            Deduplicated list of queries.
        """
        seen: set[str] = set()
        deduped: list[SearchQuery] = []

        for query in queries:
            signature = self._get_query_signature(query)
            if signature not in seen:
                seen.add(signature)
                deduped.append(query)

        return deduped


def create_query_refiner(config: RefinerConfig | None = None) -> QueryRefiner:
    """Factory function to create a QueryRefiner.

    Args:
        config: Optional refinement configuration.

    Returns:
        Configured QueryRefiner instance.
    """
    return QueryRefiner(config=config)
