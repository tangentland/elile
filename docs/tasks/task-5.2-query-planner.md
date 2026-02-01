# Task 5.2: Query Planner

## Overview

Implement intelligent query planner that generates search queries for each information type using accumulated knowledge base. Performs cross-type query enrichment using facts from completed types.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 5.1: SAR State Machine (state tracking)
- Task 2.8: Data Source Resolver (provider capabilities)
- Task 1.2: Audit Logging (query audit trail)

## Implementation Checklist

- [ ] Create KnowledgeBase for fact accumulation
- [ ] Implement query template system per type
- [ ] Build cross-type enrichment logic
- [ ] Add gap-based refinement queries
- [ ] Create jurisdiction-aware query generation
- [ ] Implement query deduplication
- [ ] Write comprehensive query planner tests

## Key Implementation

```python
# src/elile/investigation/query_planner.py
from dataclasses import dataclass, field
from datetime import date

@dataclass
class KnowledgeBase:
    """Accumulated facts for query enrichment."""

    # Identity facts
    confirmed_names: list[str] = field(default_factory=list)
    name_variants: list[str] = field(default_factory=list)
    confirmed_dob: date | None = None
    confirmed_ssn: str | None = None
    confirmed_addresses: list[Address] = field(default_factory=list)

    # Employment facts
    employers: list[EmployerRecord] = field(default_factory=list)
    job_titles: list[str] = field(default_factory=list)

    # Education facts
    schools: list[EducationRecord] = field(default_factory=list)
    degrees: list[str] = field(default_factory=list)

    # Professional facts
    licenses: list[LicenseRecord] = field(default_factory=list)

    # Discovered entities (for network expansion)
    discovered_people: list[PersonEntity] = field(default_factory=list)
    discovered_orgs: list[OrgEntity] = field(default_factory=list)

    # Jurisdictions for targeted searches
    known_counties: list[str] = field(default_factory=list)
    known_states: list[str] = field(default_factory=list)

    def add_identity_facts(
        self,
        names: list[str],
        dob: date | None,
        addresses: list[Address]
    ) -> None:
        """Add identity facts to knowledge base."""
        self.confirmed_names.extend(names)
        if dob:
            self.confirmed_dob = dob
        self.confirmed_addresses.extend(addresses)

        # Extract jurisdictions
        for addr in addresses:
            if addr.county and addr.county not in self.known_counties:
                self.known_counties.append(addr.county)
            if addr.state and addr.state not in self.known_states:
                self.known_states.append(addr.state)

    def add_employment_facts(self, employers: list[EmployerRecord]) -> None:
        """Add employment facts."""
        self.employers.extend(employers)
        for emp in employers:
            if emp.title and emp.title not in self.job_titles:
                self.job_titles.append(emp.title)
            # Extract employer jurisdictions
            if emp.location:
                if emp.location.county and emp.location.county not in self.known_counties:
                    self.known_counties.append(emp.location.county)

    def get_primary_name(self) -> str | None:
        """Get primary confirmed name."""
        return self.confirmed_names[0] if self.confirmed_names else None

@dataclass
class SearchQuery:
    """A search query to execute."""
    query_id: UUID
    info_type: InformationType
    query_type: str  # "initial" | "enriched" | "gap_fill" | "refinement"

    # Query specification
    provider_id: str
    search_params: dict[str, Any]

    # Context
    iteration_number: int
    targeting_gap: str | None = None  # If gap-filling query
    enriched_from: list[InformationType] = field(default_factory=list)

class QueryPlanner:
    """Generates search queries using knowledge base."""

    def __init__(
        self,
        data_source_resolver: DataSourceResolver,
        audit_logger: AuditLogger
    ):
        self.resolver = data_source_resolver
        self.audit = audit_logger

    def plan_queries(
        self,
        info_type: InformationType,
        knowledge_base: KnowledgeBase,
        iteration_number: int,
        gaps: list[str],
        locale: Locale,
        tier: ServiceTier
    ) -> list[SearchQuery]:
        """
        Plan queries for information type.

        Args:
            info_type: Information type to query
            knowledge_base: Accumulated facts
            iteration_number: Current iteration (1-indexed)
            gaps: Identified gaps from previous iteration
            locale: Subject locale for jurisdiction
            tier: Service tier (affects available providers)

        Returns:
            List of search queries to execute
        """
        queries = []

        if iteration_number == 1:
            # Initial queries - use basic subject info
            queries.extend(
                self._generate_initial_queries(
                    info_type, knowledge_base, locale, tier
                )
            )
        else:
            # Refinement queries - target gaps
            queries.extend(
                self._generate_refinement_queries(
                    info_type, knowledge_base, gaps, locale, tier
                )
            )

        # Audit
        self.audit.log_event(
            AuditEventType.QUERIES_PLANNED,
            {
                "info_type": info_type,
                "iteration": iteration_number,
                "queries_generated": len(queries),
                "query_types": [q.query_type for q in queries]
            }
        )

        return queries

    def _generate_initial_queries(
        self,
        info_type: InformationType,
        kb: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier
    ) -> list[SearchQuery]:
        """Generate initial queries for information type."""
        queries = []

        # Get providers for this check type
        check_type = self._map_info_type_to_check_type(info_type)
        providers = self.resolver.resolve_providers(check_type, locale, tier)

        if info_type == InformationType.IDENTITY:
            # Identity verification queries
            for provider in providers:
                queries.append(SearchQuery(
                    query_id=uuid4(),
                    info_type=info_type,
                    query_type="initial",
                    provider_id=provider.provider_id,
                    search_params={
                        "name": kb.get_primary_name(),
                        "dob": kb.confirmed_dob,
                        "addresses": [addr.to_dict() for addr in kb.confirmed_addresses]
                    },
                    iteration_number=1
                ))

        elif info_type == InformationType.CRIMINAL:
            # Criminal record queries - enriched with confirmed addresses
            for provider in providers:
                # Use confirmed addresses for jurisdiction targeting
                for county in kb.known_counties[:5]:  # Top 5 counties
                    queries.append(SearchQuery(
                        query_id=uuid4(),
                        info_type=info_type,
                        query_type="enriched",
                        provider_id=provider.provider_id,
                        search_params={
                            "name": kb.get_primary_name(),
                            "name_variants": kb.confirmed_names,
                            "dob": kb.confirmed_dob,
                            "county": county
                        },
                        iteration_number=1,
                        enriched_from=[InformationType.IDENTITY]
                    ))

        elif info_type == InformationType.EMPLOYMENT:
            # Employment verification
            for provider in providers:
                queries.append(SearchQuery(
                    query_id=uuid4(),
                    info_type=info_type,
                    query_type="enriched",
                    provider_id=provider.provider_id,
                    search_params={
                        "name": kb.get_primary_name(),
                        "name_variants": kb.confirmed_names,
                        "dob": kb.confirmed_dob,
                        "addresses": [addr.to_dict() for addr in kb.confirmed_addresses]
                    },
                    iteration_number=1,
                    enriched_from=[InformationType.IDENTITY]
                ))

        elif info_type == InformationType.ADVERSE_MEDIA:
            # Adverse media - use all known entities
            for provider in providers:
                search_terms = []
                # Add confirmed names
                search_terms.extend(kb.confirmed_names)
                # Add employers
                search_terms.extend([emp.name for emp in kb.employers])
                # Add schools
                search_terms.extend([school.name for school in kb.schools])

                queries.append(SearchQuery(
                    query_id=uuid4(),
                    info_type=info_type,
                    query_type="enriched",
                    provider_id=provider.provider_id,
                    search_params={
                        "search_terms": search_terms,
                        "date_range": "7_years"
                    },
                    iteration_number=1,
                    enriched_from=[
                        InformationType.IDENTITY,
                        InformationType.EMPLOYMENT,
                        InformationType.EDUCATION
                    ]
                ))

        return queries

    def _generate_refinement_queries(
        self,
        info_type: InformationType,
        kb: KnowledgeBase,
        gaps: list[str],
        locale: Locale,
        tier: ServiceTier
    ) -> list[SearchQuery]:
        """Generate gap-filling refinement queries."""
        queries = []
        check_type = self._map_info_type_to_check_type(info_type)
        providers = self.resolver.resolve_providers(check_type, locale, tier)

        # Generate targeted queries for each gap
        for gap in gaps:
            for provider in providers:
                query = self._create_gap_query(
                    info_type, gap, provider.provider_id, kb
                )
                if query:
                    queries.append(query)

        return queries

    def _create_gap_query(
        self,
        info_type: InformationType,
        gap: str,
        provider_id: str,
        kb: KnowledgeBase
    ) -> SearchQuery | None:
        """Create query targeting specific gap."""
        # Gap-specific query logic
        if "employment_dates" in gap:
            # Target specific employer for dates
            return SearchQuery(
                query_id=uuid4(),
                info_type=info_type,
                query_type="gap_fill",
                provider_id=provider_id,
                search_params={
                    "name": kb.get_primary_name(),
                    "focus": "employment_dates",
                    "employers": [emp.name for emp in kb.employers]
                },
                iteration_number=2,
                targeting_gap=gap
            )

        return None

    def _map_info_type_to_check_type(self, info_type: InformationType) -> CheckType:
        """Map information type to check type."""
        mapping = {
            InformationType.IDENTITY: CheckType.IDENTITY_VERIFICATION,
            InformationType.CRIMINAL: CheckType.CRIMINAL_RECORDS,
            InformationType.EMPLOYMENT: CheckType.EMPLOYMENT_VERIFICATION,
            InformationType.EDUCATION: CheckType.EDUCATION_VERIFICATION,
            InformationType.FINANCIAL: CheckType.CREDIT_CHECK,
            InformationType.CIVIL: CheckType.CIVIL_LITIGATION,
            InformationType.LICENSES: CheckType.PROFESSIONAL_LICENSE,
            InformationType.REGULATORY: CheckType.REGULATORY_ACTIONS,
            InformationType.SANCTIONS: CheckType.SANCTIONS_PEP,
            InformationType.ADVERSE_MEDIA: CheckType.ADVERSE_MEDIA,
            InformationType.DIGITAL_FOOTPRINT: CheckType.DIGITAL_FOOTPRINT,
        }
        return mapping[info_type]
```

## Testing Requirements

### Unit Tests
- Knowledge base fact accumulation
- Query generation for each information type
- Cross-type enrichment logic
- Gap-based query creation
- Jurisdiction extraction
- Query deduplication

### Integration Tests
- Complete query planning cycle
- Multi-iteration refinement
- Knowledge base growth across types
- Provider resolution integration

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] QueryPlanner generates type-specific queries
- [ ] Knowledge base accumulates facts across types
- [ ] Criminal queries enriched with addresses/counties
- [ ] Adverse media queries use all known entities
- [ ] Gap-filling queries target specific missing info
- [ ] Jurisdictions automatically extracted
- [ ] Query audit trail complete

## Deliverables

- `src/elile/investigation/query_planner.py`
- `src/elile/investigation/knowledge_base.py`
- `tests/unit/test_query_planner.py`
- `tests/integration/test_query_enrichment.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - Cross-Type Enrichment
- Dependencies: Task 5.1 (SAR state), Task 2.8 (data sources)

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
