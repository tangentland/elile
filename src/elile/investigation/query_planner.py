"""Query Planner for SAR (Search-Assess-Refine) investigations.

This module implements intelligent query planning that generates search queries
for each information type using accumulated facts from the knowledge base.
It performs cross-type query enrichment to improve search accuracy.

Key features:
- Type-specific query templates
- Cross-type enrichment (e.g., use confirmed addresses for criminal searches)
- Gap-based refinement queries
- Jurisdiction-aware query generation
- Query deduplication
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from elile.agent.state import (
    Address,
    InformationType,
    KnowledgeBase,
    ServiceTier,
)
from elile.compliance.types import CheckType, Locale


class QueryType(str, Enum):
    """Types of search queries."""

    INITIAL = "initial"  # First iteration, basic subject info
    ENRICHED = "enriched"  # Uses facts from completed types
    GAP_FILL = "gap_fill"  # Targets specific missing information
    REFINEMENT = "refinement"  # Alternative search for low-confidence results


@dataclass
class SearchQuery:
    """A search query to execute against a data provider.

    Represents a single query that will be sent to a provider, including
    the search parameters and context about how it was generated.
    """

    query_id: UUID
    info_type: InformationType
    query_type: QueryType

    # Query specification
    provider_id: str
    check_type: CheckType
    search_params: dict[str, Any]

    # Context
    iteration_number: int
    targeting_gap: str | None = None  # If gap-filling query
    enriched_from: list[InformationType] = field(default_factory=list)

    # Metadata
    priority: int = 0  # Higher = more important
    estimated_cost: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query_id": str(self.query_id),
            "info_type": self.info_type.value,
            "query_type": self.query_type.value,
            "provider_id": self.provider_id,
            "check_type": self.check_type.value,
            "search_params": self.search_params,
            "iteration_number": self.iteration_number,
            "targeting_gap": self.targeting_gap,
            "enriched_from": [t.value for t in self.enriched_from],
            "priority": self.priority,
            "estimated_cost": self.estimated_cost,
        }


# Mapping from InformationType to primary CheckType(s)
INFO_TYPE_TO_CHECK_TYPES: dict[InformationType, list[CheckType]] = {
    InformationType.IDENTITY: [
        CheckType.IDENTITY_BASIC,
        CheckType.SSN_TRACE,
    ],
    InformationType.EMPLOYMENT: [
        CheckType.EMPLOYMENT_VERIFICATION,
    ],
    InformationType.EDUCATION: [
        CheckType.EDUCATION_VERIFICATION,
        CheckType.EDUCATION_DEGREE,
    ],
    InformationType.CRIMINAL: [
        CheckType.CRIMINAL_NATIONAL,
        CheckType.CRIMINAL_COUNTY,
        CheckType.CRIMINAL_FEDERAL,
    ],
    InformationType.CIVIL: [
        CheckType.CIVIL_LITIGATION,
        CheckType.CIVIL_JUDGMENTS,
        CheckType.BANKRUPTCY,
        CheckType.LIENS,
    ],
    InformationType.FINANCIAL: [
        CheckType.CREDIT_REPORT,
    ],
    InformationType.LICENSES: [
        CheckType.LICENSE_VERIFICATION,
        CheckType.PROFESSIONAL_SANCTIONS,
    ],
    InformationType.REGULATORY: [
        CheckType.REGULATORY_ENFORCEMENT,
    ],
    InformationType.SANCTIONS: [
        CheckType.SANCTIONS_OFAC,
        CheckType.SANCTIONS_UN,
        CheckType.SANCTIONS_EU,
        CheckType.SANCTIONS_PEP,
        CheckType.WATCHLIST_INTERPOL,
    ],
    InformationType.ADVERSE_MEDIA: [
        CheckType.ADVERSE_MEDIA,
    ],
    InformationType.DIGITAL_FOOTPRINT: [
        CheckType.DIGITAL_FOOTPRINT,
        CheckType.SOCIAL_MEDIA,
    ],
    InformationType.NETWORK_D2: [
        CheckType.BUSINESS_AFFILIATIONS,
        CheckType.NETWORK_D2,
    ],
    InformationType.NETWORK_D3: [
        CheckType.NETWORK_D3,
    ],
    InformationType.RECONCILIATION: [],  # No direct queries, cross-type analysis
}


@dataclass
class QueryPlanResult:
    """Result of query planning for a single info type iteration."""

    info_type: InformationType
    iteration_number: int
    queries: list[SearchQuery]
    enrichment_sources: list[InformationType]  # Types used for enrichment

    @property
    def query_count(self) -> int:
        """Number of queries planned."""
        return len(self.queries)

    @property
    def has_queries(self) -> bool:
        """Whether any queries were planned."""
        return len(self.queries) > 0


class QueryPlanner:
    """Generates search queries using knowledge base for enrichment.

    The QueryPlanner is responsible for creating search queries that will be
    executed against data providers. It uses the accumulated KnowledgeBase
    to enrich queries with confirmed facts from previous searches.

    Example:
        ```python
        planner = QueryPlanner()

        # First iteration - basic identity queries
        result = planner.plan_queries(
            info_type=InformationType.IDENTITY,
            knowledge_base=kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "checkr"],
        )

        # Later - criminal queries enriched with identity facts
        result = planner.plan_queries(
            info_type=InformationType.CRIMINAL,
            knowledge_base=kb,  # Now has confirmed addresses
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )
        # Criminal queries will include known counties for targeted searches
        ```
    """

    def __init__(self, max_queries_per_iteration: int = 20):
        """Initialize the query planner.

        Args:
            max_queries_per_iteration: Maximum queries to generate per iteration.
        """
        self.max_queries_per_iteration = max_queries_per_iteration
        self._query_hashes: set[str] = set()  # For deduplication

    def plan_queries(
        self,
        info_type: InformationType,
        knowledge_base: KnowledgeBase,
        iteration_number: int,
        gaps: list[str],
        locale: Locale,
        tier: ServiceTier,
        available_providers: list[str],
        subject_name: str | None = None,
        subject_dob: date | None = None,
    ) -> QueryPlanResult:
        """Plan queries for an information type iteration.

        Args:
            info_type: Information type to query.
            knowledge_base: Accumulated facts for enrichment.
            iteration_number: Current iteration (1-indexed).
            gaps: Identified gaps from previous iteration.
            locale: Subject locale for jurisdiction.
            tier: Service tier (affects available check types).
            available_providers: List of provider IDs that can handle this type.
            subject_name: Fallback name if knowledge base is empty.
            subject_dob: Fallback DOB if knowledge base is empty.

        Returns:
            QueryPlanResult with planned queries.
        """
        queries: list[SearchQuery] = []
        enrichment_sources: list[InformationType] = []

        # Get check types for this info type
        check_types = self._get_check_types_for_info_type(info_type, tier)

        if not check_types:
            # No check types for this info type (e.g., RECONCILIATION)
            return QueryPlanResult(
                info_type=info_type,
                iteration_number=iteration_number,
                queries=[],
                enrichment_sources=[],
            )

        if iteration_number == 1:
            # Initial queries - use basic subject info + any prior knowledge
            queries, enrichment_sources = self._generate_initial_queries(
                info_type=info_type,
                check_types=check_types,
                knowledge_base=knowledge_base,
                locale=locale,
                _tier=tier,
                available_providers=available_providers,
                subject_name=subject_name,
                subject_dob=subject_dob,
            )
        else:
            # Refinement queries - target gaps
            queries, enrichment_sources = self._generate_refinement_queries(
                info_type=info_type,
                check_types=check_types,
                knowledge_base=knowledge_base,
                gaps=gaps,
                iteration_number=iteration_number,
                _locale=locale,
                _tier=tier,
                available_providers=available_providers,
            )

        # Deduplicate queries
        queries = self._deduplicate_queries(queries)

        # Limit query count
        queries = queries[: self.max_queries_per_iteration]

        # Sort by priority (higher first)
        queries.sort(key=lambda q: q.priority, reverse=True)

        return QueryPlanResult(
            info_type=info_type,
            iteration_number=iteration_number,
            queries=queries,
            enrichment_sources=enrichment_sources,
        )

    def _get_check_types_for_info_type(
        self, info_type: InformationType, tier: ServiceTier
    ) -> list[CheckType]:
        """Get applicable check types for an info type and tier."""
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

    def _generate_initial_queries(
        self,
        info_type: InformationType,
        check_types: list[CheckType],
        knowledge_base: KnowledgeBase,
        locale: Locale,
        _tier: ServiceTier,  # Reserved for future tier-specific query logic
        available_providers: list[str],
        subject_name: str | None,
        subject_dob: date | None,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate initial queries for first iteration."""
        queries: list[SearchQuery] = []
        enrichment_sources: list[InformationType] = []

        # Get base search params from knowledge base or fallbacks
        primary_name = (
            knowledge_base.confirmed_names[0] if knowledge_base.confirmed_names else subject_name
        )
        dob = knowledge_base.confirmed_dob or subject_dob

        if not primary_name:
            # Can't generate queries without a name
            return queries, enrichment_sources

        # Generate type-specific queries
        if info_type == InformationType.IDENTITY:
            queries = self._generate_identity_queries(
                check_types, knowledge_base, available_providers, primary_name, dob
            )

        elif info_type == InformationType.EMPLOYMENT:
            queries, enrichment_sources = self._generate_employment_queries(
                check_types, knowledge_base, available_providers, primary_name, dob
            )

        elif info_type == InformationType.EDUCATION:
            queries, enrichment_sources = self._generate_education_queries(
                check_types, knowledge_base, available_providers, primary_name, dob
            )

        elif info_type == InformationType.CRIMINAL:
            queries, enrichment_sources = self._generate_criminal_queries(
                check_types, knowledge_base, available_providers, primary_name, dob, locale
            )

        elif info_type == InformationType.CIVIL:
            queries, enrichment_sources = self._generate_civil_queries(
                check_types, knowledge_base, available_providers, primary_name, dob
            )

        elif info_type == InformationType.FINANCIAL:
            queries, enrichment_sources = self._generate_financial_queries(
                check_types, knowledge_base, available_providers, primary_name, dob
            )

        elif info_type == InformationType.LICENSES:
            queries, enrichment_sources = self._generate_license_queries(
                check_types, knowledge_base, available_providers, primary_name
            )

        elif info_type == InformationType.REGULATORY:
            queries, enrichment_sources = self._generate_regulatory_queries(
                check_types, knowledge_base, available_providers, primary_name
            )

        elif info_type == InformationType.SANCTIONS:
            queries = self._generate_sanctions_queries(
                check_types, knowledge_base, available_providers, primary_name, dob
            )

        elif info_type == InformationType.ADVERSE_MEDIA:
            queries, enrichment_sources = self._generate_adverse_media_queries(
                check_types, knowledge_base, available_providers, primary_name
            )

        elif info_type == InformationType.DIGITAL_FOOTPRINT:
            queries, enrichment_sources = self._generate_digital_queries(
                check_types, knowledge_base, available_providers, primary_name
            )

        elif info_type in (InformationType.NETWORK_D2, InformationType.NETWORK_D3):
            queries, enrichment_sources = self._generate_network_queries(
                info_type, check_types, knowledge_base, available_providers
            )

        return queries, enrichment_sources

    def _generate_identity_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
    ) -> list[SearchQuery]:
        """Generate identity verification queries."""
        queries = []

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names[1:] if len(kb.confirmed_names) > 1 else [],
                }

                if dob:
                    search_params["dob"] = dob.isoformat()

                if kb.confirmed_addresses:
                    search_params["addresses"] = [
                        self._address_to_dict(addr) for addr in kb.confirmed_addresses
                    ]

                if kb.confirmed_ssn_last4:
                    search_params["ssn_last4"] = kb.confirmed_ssn_last4

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.IDENTITY,
                        query_type=QueryType.INITIAL,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        priority=10,  # Identity is highest priority
                    )
                )

        return queries

    def _generate_employment_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate employment verification queries."""
        queries = []
        enrichment_sources = []

        # Employment can be enriched with identity facts
        if kb.confirmed_names or kb.confirmed_addresses:
            enrichment_sources.append(InformationType.IDENTITY)

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names[1:] if len(kb.confirmed_names) > 1 else [],
                }

                if dob:
                    search_params["dob"] = dob.isoformat()

                # Include any provided employers for verification
                if kb.employers:
                    search_params["employers_to_verify"] = [
                        {
                            "name": emp.employer_name,
                            "title": emp.title,
                            "start_date": emp.start_date,
                            "end_date": emp.end_date,
                        }
                        for emp in kb.employers
                    ]

                query_type = QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.EMPLOYMENT,
                        query_type=query_type,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=9,
                    )
                )

        return queries, enrichment_sources

    def _generate_education_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate education verification queries."""
        queries = []
        enrichment_sources = []

        if kb.confirmed_names:
            enrichment_sources.append(InformationType.IDENTITY)

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names[1:] if len(kb.confirmed_names) > 1 else [],
                }

                if dob:
                    search_params["dob"] = dob.isoformat()

                # Include any provided schools for verification
                if kb.schools:
                    search_params["schools_to_verify"] = [
                        {
                            "name": school.institution_name,
                            "degree_type": school.degree_type,
                            "field_of_study": school.field_of_study,
                            "end_date": school.end_date,
                        }
                        for school in kb.schools
                    ]

                query_type = QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.EDUCATION,
                        query_type=query_type,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=8,
                    )
                )

        return queries, enrichment_sources

    def _generate_criminal_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
        locale: Locale,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate criminal record queries with jurisdiction targeting."""
        queries = []
        enrichment_sources = []

        # Criminal queries are heavily enriched with identity facts
        if kb.confirmed_addresses or kb.known_counties or kb.known_states:
            enrichment_sources.append(InformationType.IDENTITY)

        for check_type in check_types:
            for provider_id in providers:
                if check_type == CheckType.CRIMINAL_COUNTY:
                    # Generate county-specific queries using known counties
                    counties = kb.known_counties[:5] if kb.known_counties else ["*"]
                    for county in counties:
                        search_params: dict[str, Any] = {
                            "name": name,
                            "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                            "county": county,
                            "locale": locale.value,
                        }
                        if dob:
                            search_params["dob"] = dob.isoformat()

                        queries.append(
                            SearchQuery(
                                query_id=uuid7(),
                                info_type=InformationType.CRIMINAL,
                                query_type=(
                                    QueryType.ENRICHED if county != "*" else QueryType.INITIAL
                                ),
                                provider_id=provider_id,
                                check_type=check_type,
                                search_params=search_params,
                                iteration_number=1,
                                enriched_from=enrichment_sources.copy() if county != "*" else [],
                                priority=7,
                            )
                        )
                else:
                    # National/federal/state queries
                    search_params = {
                        "name": name,
                        "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                        "locale": locale.value,
                    }
                    if dob:
                        search_params["dob"] = dob.isoformat()
                    if kb.known_states:
                        search_params["states"] = kb.known_states

                    queries.append(
                        SearchQuery(
                            query_id=uuid7(),
                            info_type=InformationType.CRIMINAL,
                            query_type=(
                                QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL
                            ),
                            provider_id=provider_id,
                            check_type=check_type,
                            search_params=search_params,
                            iteration_number=1,
                            enriched_from=enrichment_sources.copy(),
                            priority=7,
                        )
                    )

        return queries, enrichment_sources

    def _generate_civil_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate civil record queries."""
        queries = []
        enrichment_sources = []

        if kb.confirmed_names or kb.known_states:
            enrichment_sources.append(InformationType.IDENTITY)

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                }
                if dob:
                    search_params["dob"] = dob.isoformat()
                if kb.known_states:
                    search_params["states"] = kb.known_states

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.CIVIL,
                        query_type=QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=6,
                    )
                )

        return queries, enrichment_sources

    def _generate_financial_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate financial/credit queries."""
        queries = []
        enrichment_sources = []

        if kb.confirmed_addresses or kb.confirmed_ssn_last4:
            enrichment_sources.append(InformationType.IDENTITY)

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                }
                if dob:
                    search_params["dob"] = dob.isoformat()
                if kb.confirmed_ssn_last4:
                    search_params["ssn_last4"] = kb.confirmed_ssn_last4
                if kb.confirmed_addresses:
                    search_params["current_address"] = self._address_to_dict(
                        kb.confirmed_addresses[0]
                    )

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.FINANCIAL,
                        query_type=QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=5,
                    )
                )

        return queries, enrichment_sources

    def _generate_license_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate professional license queries."""
        queries = []
        enrichment_sources = []

        if kb.confirmed_names:
            enrichment_sources.append(InformationType.IDENTITY)
        if kb.licenses:
            # Can verify specific licenses
            pass

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                }

                # Include known licenses for verification
                if kb.licenses:
                    search_params["licenses_to_verify"] = [
                        {
                            "type": lic.license_type,
                            "number": lic.license_number,
                            "jurisdiction": lic.jurisdiction,
                        }
                        for lic in kb.licenses
                    ]

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.LICENSES,
                        query_type=QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=5,
                    )
                )

        return queries, enrichment_sources

    def _generate_regulatory_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate regulatory enforcement queries."""
        queries = []
        enrichment_sources = []

        if kb.confirmed_names:
            enrichment_sources.append(InformationType.IDENTITY)
        if kb.employers:
            enrichment_sources.append(InformationType.EMPLOYMENT)

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                }

                # Include employers for industry-specific searches
                if kb.employers:
                    search_params["employers"] = [emp.employer_name for emp in kb.employers]

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.REGULATORY,
                        query_type=QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=5,
                    )
                )

        return queries, enrichment_sources

    def _generate_sanctions_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
        dob: date | None,
    ) -> list[SearchQuery]:
        """Generate sanctions/watchlist queries."""
        queries = []

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                }
                if dob:
                    search_params["dob"] = dob.isoformat()

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.SANCTIONS,
                        query_type=QueryType.INITIAL,  # Sanctions don't need enrichment
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        priority=10,  # Sanctions are high priority
                    )
                )

        return queries

    def _generate_adverse_media_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate adverse media queries with full enrichment."""
        queries = []
        enrichment_sources = []

        # Adverse media benefits from all prior knowledge
        if kb.confirmed_names:
            enrichment_sources.append(InformationType.IDENTITY)
        if kb.employers:
            enrichment_sources.append(InformationType.EMPLOYMENT)
        if kb.schools:
            enrichment_sources.append(InformationType.EDUCATION)

        for check_type in check_types:
            for provider_id in providers:
                # Build comprehensive search terms
                search_terms = [name]
                search_terms.extend(kb.confirmed_names)
                search_terms.extend([emp.employer_name for emp in kb.employers])
                search_terms.extend([school.institution_name for school in kb.schools])

                # Deduplicate search terms
                search_terms = list(dict.fromkeys(search_terms))

                search_params: dict[str, Any] = {
                    "search_terms": search_terms,
                    "date_range_years": 7,
                }

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.ADVERSE_MEDIA,
                        query_type=QueryType.ENRICHED,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=6,
                    )
                )

        return queries, enrichment_sources

    def _generate_digital_queries(
        self,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
        name: str,
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate digital footprint queries."""
        queries = []
        enrichment_sources = []

        if kb.confirmed_names:
            enrichment_sources.append(InformationType.IDENTITY)

        for check_type in check_types:
            for provider_id in providers:
                search_params: dict[str, Any] = {
                    "name": name,
                    "name_variants": kb.confirmed_names if kb.confirmed_names else [],
                }

                # Include any known email handles or usernames
                # (would be added to KB from earlier searches)

                queries.append(
                    SearchQuery(
                        query_id=uuid7(),
                        info_type=InformationType.DIGITAL_FOOTPRINT,
                        query_type=QueryType.ENRICHED if enrichment_sources else QueryType.INITIAL,
                        provider_id=provider_id,
                        check_type=check_type,
                        search_params=search_params,
                        iteration_number=1,
                        enriched_from=enrichment_sources.copy(),
                        priority=4,
                    )
                )

        return queries, enrichment_sources

    def _generate_network_queries(
        self,
        info_type: InformationType,
        check_types: list[CheckType],
        kb: KnowledgeBase,
        providers: list[str],
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate network expansion queries."""
        queries = []
        enrichment_sources = [InformationType.IDENTITY]

        # Network queries use discovered entities
        if kb.employers:
            enrichment_sources.append(InformationType.EMPLOYMENT)

        for check_type in check_types:
            for provider_id in providers:
                # Query for each discovered person
                for person in kb.discovered_people[:10]:  # Limit to top 10
                    search_params: dict[str, Any] = {
                        "entity_name": person.name,
                        "entity_type": "person",
                        "relationship_to_subject": person.relationship_to_subject,
                    }

                    queries.append(
                        SearchQuery(
                            query_id=uuid7(),
                            info_type=info_type,
                            query_type=QueryType.ENRICHED,
                            provider_id=provider_id,
                            check_type=check_type,
                            search_params=search_params,
                            iteration_number=1,
                            enriched_from=enrichment_sources.copy(),
                            priority=3,
                        )
                    )

                # Query for each discovered org
                for org in kb.discovered_orgs[:10]:  # Limit to top 10
                    search_params = {
                        "entity_name": org.name,
                        "entity_type": "organization",
                        "relationship_to_subject": org.relationship_to_subject,
                    }

                    queries.append(
                        SearchQuery(
                            query_id=uuid7(),
                            info_type=info_type,
                            query_type=QueryType.ENRICHED,
                            provider_id=provider_id,
                            check_type=check_type,
                            search_params=search_params,
                            iteration_number=1,
                            enriched_from=enrichment_sources.copy(),
                            priority=3,
                        )
                    )

        return queries, enrichment_sources

    def _generate_refinement_queries(
        self,
        info_type: InformationType,
        check_types: list[CheckType],
        knowledge_base: KnowledgeBase,
        gaps: list[str],
        iteration_number: int,
        _locale: Locale,  # Reserved for jurisdiction-specific gap queries
        _tier: ServiceTier,  # Reserved for tier-specific refinement logic
        available_providers: list[str],
    ) -> tuple[list[SearchQuery], list[InformationType]]:
        """Generate gap-filling refinement queries."""
        queries = []
        enrichment_sources = [InformationType.IDENTITY]  # Always use identity for refinement

        primary_name = knowledge_base.confirmed_names[0] if knowledge_base.confirmed_names else None
        if not primary_name:
            return queries, enrichment_sources

        for gap in gaps:
            for provider_id in available_providers:
                query = self._create_gap_query(
                    info_type=info_type,
                    gap=gap,
                    provider_id=provider_id,
                    kb=knowledge_base,
                    check_types=check_types,
                    iteration_number=iteration_number,
                )
                if query:
                    queries.append(query)

        return queries, enrichment_sources

    def _create_gap_query(
        self,
        info_type: InformationType,
        gap: str,
        provider_id: str,
        kb: KnowledgeBase,
        check_types: list[CheckType],
        iteration_number: int,
    ) -> SearchQuery | None:
        """Create a query targeting a specific gap."""
        primary_name = kb.confirmed_names[0] if kb.confirmed_names else None
        if not primary_name or not check_types:
            return None

        search_params: dict[str, Any] = {
            "name": primary_name,
            "gap_focus": gap,
        }

        # Gap-specific query logic
        if "employment_dates" in gap.lower():
            search_params["focus"] = "employment_dates"
            if kb.employers:
                search_params["employers"] = [emp.employer_name for emp in kb.employers]

        elif "education_verification" in gap.lower():
            search_params["focus"] = "education_verification"
            if kb.schools:
                search_params["schools"] = [school.institution_name for school in kb.schools]

        elif "address_history" in gap.lower():
            search_params["focus"] = "address_history"

        elif "name_variants" in gap.lower():
            search_params["focus"] = "name_variants"
            search_params["expand_variants"] = True

        elif "county" in gap.lower():
            # Target specific county for criminal records
            search_params["focus"] = "county_records"
            search_params["expand_counties"] = True

        return SearchQuery(
            query_id=uuid7(),
            info_type=info_type,
            query_type=QueryType.GAP_FILL,
            provider_id=provider_id,
            check_type=check_types[0],  # Use primary check type
            search_params=search_params,
            iteration_number=iteration_number,
            targeting_gap=gap,
            enriched_from=[InformationType.IDENTITY],
            priority=8,  # Gap-fill queries are high priority
        )

    def _deduplicate_queries(self, queries: list[SearchQuery]) -> list[SearchQuery]:
        """Remove duplicate queries based on key parameters."""
        seen: set[str] = set()
        deduped: list[SearchQuery] = []

        for query in queries:
            # Create a hash key from essential query parameters
            key_parts = [
                query.provider_id,
                query.check_type.value,
                str(sorted(query.search_params.items())),
            ]
            key = "|".join(key_parts)

            if key not in seen:
                seen.add(key)
                deduped.append(query)

        return deduped

    def _address_to_dict(self, address: Address) -> dict[str, str | None]:
        """Convert Address to dictionary."""
        return {
            "street": address.street,
            "city": address.city,
            "state": address.state,
            "county": address.county,
            "postal_code": address.postal_code,
            "country": address.country,
        }

    def clear_deduplication_cache(self) -> None:
        """Clear the query deduplication cache."""
        self._query_hashes.clear()
