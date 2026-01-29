"""Query enrichment using accumulated knowledge base."""

from __future__ import annotations

import structlog

from elile.agent.state import (
    InformationType,
    KnowledgeBase,
)
from elile.search.query import QueryCategory, SearchQuery

logger = structlog.get_logger()


class QueryEnricher:
    """Enriches queries using accumulated knowledge from prior phases.

    This class implements the cross-type query enrichment strategy, using
    facts discovered in earlier phases to generate more targeted queries
    for later phases.
    """

    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        """Initialize the query enricher.

        Args:
            knowledge_base: Accumulated knowledge from completed phases.
        """
        self._kb = knowledge_base

    def enrich_queries(
        self,
        info_type: InformationType,
        base_queries: list[SearchQuery],
    ) -> list[SearchQuery]:
        """Enrich queries using knowledge base data.

        Args:
            info_type: The information type being searched.
            base_queries: Original queries to enrich.

        Returns:
            Enriched list of queries with context from prior phases.
        """
        if not base_queries:
            return []

        enriched: list[SearchQuery] = []

        for query in base_queries:
            # Always include the original query
            enriched.append(query)

            # Add name variant queries
            enriched.extend(self._add_name_variants(query))

            # Type-specific enrichment
            type_enriched = self._enrich_for_type(info_type, query)
            enriched.extend(type_enriched)

        # Deduplicate while preserving order
        return self._deduplicate(enriched)

    def _add_name_variants(self, query: SearchQuery) -> list[SearchQuery]:
        """Add queries with confirmed name variants.

        Args:
            query: Base query to create variants from.

        Returns:
            List of queries with name variants applied.
        """
        variants = []
        for name in self._kb.confirmed_names:
            variant = query.with_name_variant(name)
            # Only add if actually different
            if variant.query != query.query:
                variants.append(variant)
        return variants

    def _enrich_for_type(
        self,
        info_type: InformationType,
        query: SearchQuery,
    ) -> list[SearchQuery]:
        """Apply type-specific enrichment rules.

        Args:
            info_type: The information type being searched.
            query: Base query to enrich.

        Returns:
            List of enriched queries for this type.
        """
        enriched = []

        match info_type:
            case InformationType.CRIMINAL:
                enriched.extend(self._enrich_criminal(query))

            case InformationType.CIVIL:
                enriched.extend(self._enrich_civil(query))

            case InformationType.FINANCIAL:
                enriched.extend(self._enrich_financial(query))

            case InformationType.LICENSES:
                enriched.extend(self._enrich_licenses(query))

            case InformationType.REGULATORY:
                enriched.extend(self._enrich_regulatory(query))

            case InformationType.ADVERSE_MEDIA:
                enriched.extend(self._enrich_adverse_media(query))

            case InformationType.DIGITAL_FOOTPRINT:
                enriched.extend(self._enrich_digital(query))

            case InformationType.NETWORK_D2 | InformationType.NETWORK_D3:
                enriched.extend(self._enrich_network(query))

            case _:
                pass  # No type-specific enrichment

        return enriched

    def _enrich_criminal(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich criminal record queries.

        Criminal record searches benefit from county-specific queries
        based on confirmed addresses and employer locations.

        Args:
            query: Base query to enrich.

        Returns:
            County-specific criminal record queries.
        """
        enriched = []

        # Add county-specific searches from addresses
        for county in self._kb.known_counties:
            enriched.append(query.with_county(county))

        # Add county searches from employer locations
        for employer in self._kb.employers:
            if employer.location and employer.location.county:
                county_query = query.with_county(employer.location.county)
                if county_query.query != query.query:
                    enriched.append(county_query)

        # Add state-level searches
        for state in self._kb.known_states:
            enriched.append(query.with_state(state))

        return enriched

    def _enrich_civil(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich civil litigation queries.

        Civil searches benefit from employer names and business context.

        Args:
            query: Base query to enrich.

        Returns:
            Context-enriched civil litigation queries.
        """
        enriched = []

        # Add employer context for employment-related litigation
        for employer in self._kb.employers:
            enriched.append(query.with_context(employer.employer_name))

        # Add state jurisdiction context
        for state in self._kb.known_states:
            enriched.append(query.with_state(state))

        return enriched

    def _enrich_financial(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich financial/credit queries.

        Financial searches can be enriched with address history.

        Args:
            query: Base query to enrich.

        Returns:
            Address-enriched financial queries.
        """
        enriched = []

        # Add state context for jurisdiction-specific financial records
        for state in self._kb.known_states:
            enriched.append(query.with_state(state))

        return enriched

    def _enrich_licenses(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich professional license queries.

        License searches benefit from education (degree type → licensing board)
        and known states/jurisdictions.

        Args:
            query: Base query to enrich.

        Returns:
            Education and jurisdiction-enriched license queries.
        """
        enriched = []

        # Map degree types to relevant licensing boards
        degree_to_license = {
            "J.D.": ["bar", "attorney", "lawyer"],
            "Juris Doctor": ["bar", "attorney", "lawyer"],
            "M.D.": ["medical", "physician"],
            "Doctor of Medicine": ["medical", "physician"],
            "D.O.": ["medical", "physician", "osteopathic"],
            "CPA": ["accounting", "CPA"],
            "MBA": ["financial advisor", "CFP"],
            "RN": ["nursing", "RN"],
            "PharmD": ["pharmacy", "pharmacist"],
        }

        for school in self._kb.schools:
            if school.degree_type:
                for degree, license_terms in degree_to_license.items():
                    if degree.lower() in school.degree_type.lower():
                        for term in license_terms:
                            enriched.append(query.with_context(term))

        # Add state jurisdiction context
        for state in self._kb.known_states:
            enriched.append(query.with_state(state))

        return enriched

    def _enrich_regulatory(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich regulatory action queries.

        Regulatory searches benefit from industry context from employment.

        Args:
            query: Base query to enrich.

        Returns:
            Industry-enriched regulatory queries.
        """
        enriched = []

        # Map job titles to regulatory bodies
        title_to_regulator = {
            "broker": ["FINRA", "SEC", "securities"],
            "trader": ["FINRA", "SEC", "CFTC"],
            "banker": ["OCC", "FDIC", "banking"],
            "investment": ["SEC", "FINRA"],
            "insurance": ["state insurance", "NAIC"],
            "healthcare": ["CMS", "HHS", "medical board"],
            "pharmaceutical": ["FDA"],
            "energy": ["FERC", "NRC"],
        }

        for employer in self._kb.employers:
            if employer.title:
                title_lower = employer.title.lower()
                for keyword, regulators in title_to_regulator.items():
                    if keyword in title_lower:
                        for regulator in regulators:
                            enriched.append(query.with_context(regulator))

        return enriched

    def _enrich_adverse_media(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich adverse media queries.

        Media searches benefit from all accumulated context: employers,
        schools, locations, and known associations.

        Args:
            query: Base query to enrich.

        Returns:
            Comprehensively enriched media queries.
        """
        enriched = []

        # Add employer context
        for employer in self._kb.employers:
            enriched.append(query.with_context(employer.employer_name))

        # Add school context
        for school in self._kb.schools:
            enriched.append(query.with_context(school.institution_name))

        # Add location context for geographically-relevant media
        for state in self._kb.known_states:
            enriched.append(query.with_state(state))

        # Add discovered organization context
        for org in self._kb.discovered_orgs:
            enriched.append(query.with_context(org.name))

        return enriched

    def _enrich_digital(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich digital footprint queries.

        Digital/OSINT searches benefit from employer and professional context.

        Args:
            query: Base query to enrich.

        Returns:
            Professional context-enriched digital queries.
        """
        enriched = []

        # Add employer context for professional presence
        for employer in self._kb.employers:
            enriched.append(query.with_context(employer.employer_name))
            if employer.title:
                enriched.append(query.with_context(employer.title))

        # Add school context
        for school in self._kb.schools:
            enriched.append(query.with_context(school.institution_name))

        return enriched

    def _enrich_network(self, query: SearchQuery) -> list[SearchQuery]:
        """Enrich network expansion queries.

        Network searches use discovered people and organizations.

        Args:
            query: Base query to enrich.

        Returns:
            Entity-enriched network queries.
        """
        enriched = []

        # Add discovered people as search targets
        for person in self._kb.discovered_people:
            enriched.append(query.with_context(person.name))
            if person.employer:
                enriched.append(query.with_context(person.employer))

        # Add discovered organizations
        for org in self._kb.discovered_orgs:
            enriched.append(query.with_context(org.name))

        return enriched

    def _deduplicate(self, queries: list[SearchQuery]) -> list[SearchQuery]:
        """Remove duplicate queries while preserving order and priority.

        Args:
            queries: List of queries that may contain duplicates.

        Returns:
            Deduplicated list preserving first occurrence of each query.
        """
        seen: set[str] = set()
        unique: list[SearchQuery] = []

        for query in queries:
            # Normalize query for comparison
            normalized = query.query.lower().strip()
            if normalized not in seen:
                seen.add(normalized)
                unique.append(query)

        logger.debug(
            "Deduplicated queries",
            original_count=len(queries),
            unique_count=len(unique),
        )

        return unique

    def generate_gap_queries(
        self,
        info_type: InformationType,
        gaps: list[str],
        subject_name: str,
    ) -> list[SearchQuery]:
        """Generate queries to fill identified gaps.

        Args:
            info_type: The information type with gaps.
            gaps: List of gap descriptions from the assess phase.
            subject_name: Subject's name for query construction.

        Returns:
            Queries designed to fill the identified gaps.
        """
        gap_queries = []

        # Map gap types to query strategies
        gap_strategies = {
            "employment_dates": f'"{subject_name}" employment history dates',
            "education_verification": f'"{subject_name}" degree verification',
            "address_history": f'"{subject_name}" address history residences',
            "criminal_county": f'"{subject_name}" criminal records',
            "civil_records": f'"{subject_name}" civil litigation lawsuit',
            "license_status": f'"{subject_name}" professional license status',
            "regulatory_actions": f'"{subject_name}" regulatory enforcement action',
        }

        for gap in gaps:
            gap_lower = gap.lower()
            for gap_type, query_template in gap_strategies.items():
                if gap_type.replace("_", " ") in gap_lower or gap_type in gap_lower:
                    gap_query = SearchQuery(
                        query=query_template,
                        category=self._type_to_category(info_type),
                        info_type=info_type,
                        priority=2,  # Gap-fill queries are slightly lower priority
                        is_gap_fill=True,
                    )
                    gap_queries.append(gap_query)
                    break
            else:
                # Generic gap query if no specific strategy matches
                gap_query = SearchQuery(
                    query=f'"{subject_name}" {gap}',
                    category=self._type_to_category(info_type),
                    info_type=info_type,
                    priority=2,
                    is_gap_fill=True,
                )
                gap_queries.append(gap_query)

        # Enrich gap queries with knowledge base
        return self.enrich_queries(info_type, gap_queries)

    def _type_to_category(self, info_type: InformationType) -> str:
        """Map information type to query category.

        Args:
            info_type: The information type.

        Returns:
            Corresponding query category string.
        """
        type_category_map = {
            InformationType.IDENTITY: QueryCategory.BIOGRAPHICAL,
            InformationType.EMPLOYMENT: QueryCategory.EMPLOYMENT,
            InformationType.EDUCATION: QueryCategory.EDUCATION,
            InformationType.CRIMINAL: QueryCategory.CRIMINAL,
            InformationType.CIVIL: QueryCategory.CIVIL,
            InformationType.FINANCIAL: QueryCategory.FINANCIAL,
            InformationType.LICENSES: QueryCategory.PROFESSIONAL,
            InformationType.REGULATORY: QueryCategory.REGULATORY,
            InformationType.SANCTIONS: QueryCategory.SANCTIONS,
            InformationType.ADVERSE_MEDIA: QueryCategory.MEDIA,
            InformationType.DIGITAL_FOOTPRINT: QueryCategory.DIGITAL,
            InformationType.NETWORK_D2: QueryCategory.NETWORK,
            InformationType.NETWORK_D3: QueryCategory.NETWORK,
            InformationType.RECONCILIATION: QueryCategory.BIOGRAPHICAL,
        }
        return type_category_map.get(info_type, QueryCategory.BIOGRAPHICAL)
