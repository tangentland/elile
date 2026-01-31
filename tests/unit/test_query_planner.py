"""Unit tests for QueryPlanner.

Tests cover:
- Query generation for each information type
- Cross-type enrichment logic
- Knowledge base integration
- Gap-based refinement queries
- Jurisdiction extraction for criminal queries
- Query deduplication
- Query type assignment
"""

from datetime import date

import pytest

from elile.agent.state import (
    Address,
    EducationRecord,
    EmployerRecord,
    InformationType,
    KnowledgeBase,
    LicenseRecord,
    PersonEntity,
    OrgEntity,
    ServiceTier,
)
from elile.compliance.types import CheckType, Locale
from elile.investigation import (
    INFO_TYPE_TO_CHECK_TYPES,
    QueryPlanResult,
    QueryPlanner,
    QueryType,
    SearchQuery,
)


class TestSearchQuery:
    """Tests for SearchQuery dataclass."""

    def test_query_creation(self):
        """Test creating a search query."""
        from uuid import uuid7

        query = SearchQuery(
            query_id=uuid7(),
            info_type=InformationType.IDENTITY,
            query_type=QueryType.INITIAL,
            provider_id="sterling",
            check_type=CheckType.IDENTITY_BASIC,
            search_params={"name": "John Smith"},
            iteration_number=1,
        )

        assert query.info_type == InformationType.IDENTITY
        assert query.query_type == QueryType.INITIAL
        assert query.provider_id == "sterling"
        assert query.search_params["name"] == "John Smith"
        assert query.iteration_number == 1
        assert query.targeting_gap is None
        assert query.enriched_from == []

    def test_query_to_dict(self):
        """Test query serialization."""
        from uuid import uuid7

        query_id = uuid7()
        query = SearchQuery(
            query_id=query_id,
            info_type=InformationType.CRIMINAL,
            query_type=QueryType.ENRICHED,
            provider_id="checkr",
            check_type=CheckType.CRIMINAL_COUNTY,
            search_params={"name": "Jane Doe", "county": "Cook"},
            iteration_number=1,
            enriched_from=[InformationType.IDENTITY],
        )

        result = query.to_dict()

        assert result["query_id"] == str(query_id)
        assert result["info_type"] == "criminal"
        assert result["query_type"] == "enriched"
        assert result["provider_id"] == "checkr"
        assert result["check_type"] == "criminal_county"
        assert result["enriched_from"] == ["identity"]


class TestQueryPlanResult:
    """Tests for QueryPlanResult."""

    def test_result_properties(self):
        """Test query plan result properties."""
        from uuid import uuid7

        queries = [
            SearchQuery(
                query_id=uuid7(),
                info_type=InformationType.IDENTITY,
                query_type=QueryType.INITIAL,
                provider_id="sterling",
                check_type=CheckType.IDENTITY_BASIC,
                search_params={},
                iteration_number=1,
            )
            for _ in range(3)
        ]

        result = QueryPlanResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            queries=queries,
            enrichment_sources=[],
        )

        assert result.query_count == 3
        assert result.has_queries is True

    def test_empty_result(self):
        """Test empty query plan result."""
        result = QueryPlanResult(
            info_type=InformationType.RECONCILIATION,
            iteration_number=1,
            queries=[],
            enrichment_sources=[],
        )

        assert result.query_count == 0
        assert result.has_queries is False


class TestQueryPlanner:
    """Tests for QueryPlanner."""

    @pytest.fixture
    def planner(self):
        """Create a QueryPlanner instance."""
        return QueryPlanner()

    @pytest.fixture
    def empty_kb(self):
        """Create an empty KnowledgeBase."""
        return KnowledgeBase()

    @pytest.fixture
    def populated_kb(self):
        """Create a populated KnowledgeBase."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith", "John A Smith", "J Smith"]
        kb.confirmed_dob = date(1980, 5, 15)
        kb.confirmed_ssn_last4 = "1234"
        kb.confirmed_addresses = [
            Address(
                street="123 Main St",
                city="Chicago",
                state="IL",
                county="Cook",
                postal_code="60601",
            ),
            Address(
                street="456 Oak Ave",
                city="Springfield",
                state="IL",
                county="Sangamon",
                postal_code="62701",
            ),
        ]
        kb.known_counties = ["Cook", "Sangamon"]
        kb.known_states = ["IL"]
        kb.employers = [
            EmployerRecord(
                employer_name="Acme Corp",
                title="Software Engineer",
                start_date="2015-01-01",
                end_date="2020-12-31",
                source="user_provided",
            )
        ]
        kb.schools = [
            EducationRecord(
                institution_name="State University",
                degree_type="Bachelor",
                field_of_study="Computer Science",
                end_date="2014-05-15",
                source="user_provided",
            )
        ]
        return kb


class TestIdentityQueries(TestQueryPlanner):
    """Tests for identity query generation."""

    def test_identity_queries_with_name_only(self, planner, empty_kb):
        """Test identity queries with just a name."""
        result = planner.plan_queries(
            info_type=InformationType.IDENTITY,
            knowledge_base=empty_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
            subject_name="John Smith",
        )

        assert result.has_queries
        assert result.info_type == InformationType.IDENTITY
        assert all(q.info_type == InformationType.IDENTITY for q in result.queries)
        assert all(q.query_type == QueryType.INITIAL for q in result.queries)
        assert all("name" in q.search_params for q in result.queries)

    def test_identity_queries_with_full_info(self, planner, populated_kb):
        """Test identity queries with full knowledge base."""
        result = planner.plan_queries(
            info_type=InformationType.IDENTITY,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "checkr"],
        )

        assert result.has_queries
        # Should have queries for multiple providers
        provider_ids = {q.provider_id for q in result.queries}
        assert "sterling" in provider_ids or "checkr" in provider_ids

        # Should include SSN last 4 and addresses
        for query in result.queries:
            if "ssn_last4" in query.search_params:
                assert query.search_params["ssn_last4"] == "1234"

    def test_no_queries_without_name(self, planner, empty_kb):
        """Test that no queries are generated without a name."""
        result = planner.plan_queries(
            info_type=InformationType.IDENTITY,
            knowledge_base=empty_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
            # No subject_name provided
        )

        assert not result.has_queries


class TestCriminalQueries(TestQueryPlanner):
    """Tests for criminal query generation with jurisdiction targeting."""

    def test_criminal_queries_enriched_with_counties(self, planner, populated_kb):
        """Test criminal queries use known counties."""
        result = planner.plan_queries(
            info_type=InformationType.CRIMINAL,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.has_queries
        assert InformationType.IDENTITY in result.enrichment_sources

        # Check for county-specific queries
        county_queries = [
            q for q in result.queries if q.check_type == CheckType.CRIMINAL_COUNTY
        ]
        if county_queries:
            counties_queried = {q.search_params.get("county") for q in county_queries}
            assert "Cook" in counties_queried or "Sangamon" in counties_queried

    def test_criminal_queries_include_name_variants(self, planner, populated_kb):
        """Test criminal queries include name variants."""
        result = planner.plan_queries(
            info_type=InformationType.CRIMINAL,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        for query in result.queries:
            if "name_variants" in query.search_params:
                assert len(query.search_params["name_variants"]) > 0


class TestEmploymentQueries(TestQueryPlanner):
    """Tests for employment query generation."""

    def test_employment_queries_enriched_with_identity(self, planner, populated_kb):
        """Test employment queries are enriched with identity facts."""
        result = planner.plan_queries(
            info_type=InformationType.EMPLOYMENT,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.has_queries
        assert InformationType.IDENTITY in result.enrichment_sources
        assert all(q.query_type == QueryType.ENRICHED for q in result.queries)

    def test_employment_queries_include_employers_to_verify(self, planner, populated_kb):
        """Test employment queries include employers for verification."""
        result = planner.plan_queries(
            info_type=InformationType.EMPLOYMENT,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        for query in result.queries:
            if "employers_to_verify" in query.search_params:
                employers = query.search_params["employers_to_verify"]
                assert any(e["name"] == "Acme Corp" for e in employers)


class TestAdverseMediaQueries(TestQueryPlanner):
    """Tests for adverse media query generation with full enrichment."""

    def test_adverse_media_uses_all_knowledge(self, planner, populated_kb):
        """Test adverse media queries use names, employers, and schools."""
        result = planner.plan_queries(
            info_type=InformationType.ADVERSE_MEDIA,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.has_queries
        assert InformationType.IDENTITY in result.enrichment_sources
        assert InformationType.EMPLOYMENT in result.enrichment_sources
        assert InformationType.EDUCATION in result.enrichment_sources

        # Check search terms include diverse sources
        for query in result.queries:
            search_terms = query.search_params.get("search_terms", [])
            # Should include name
            assert any("Smith" in term for term in search_terms)
            # Should include employer
            assert any("Acme" in term for term in search_terms)
            # Should include school
            assert any("University" in term for term in search_terms)


class TestSanctionsQueries(TestQueryPlanner):
    """Tests for sanctions/watchlist queries."""

    def test_sanctions_queries_no_enrichment_needed(self, planner, populated_kb):
        """Test sanctions queries don't require enrichment."""
        result = planner.plan_queries(
            info_type=InformationType.SANCTIONS,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["world_check"],
        )

        assert result.has_queries
        # Sanctions queries are INITIAL type, not ENRICHED
        assert all(q.query_type == QueryType.INITIAL for q in result.queries)
        # High priority
        assert all(q.priority == 10 for q in result.queries)


class TestRefinementQueries(TestQueryPlanner):
    """Tests for gap-based refinement queries."""

    def test_refinement_queries_target_gaps(self, planner, populated_kb):
        """Test refinement queries target specific gaps."""
        result = planner.plan_queries(
            info_type=InformationType.EMPLOYMENT,
            knowledge_base=populated_kb,
            iteration_number=2,  # Second iteration
            gaps=["employment_dates_missing", "title_verification_needed"],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        # Should have gap-fill queries
        gap_queries = [q for q in result.queries if q.query_type == QueryType.GAP_FILL]
        assert len(gap_queries) > 0

        # Each gap query should target a specific gap
        for query in gap_queries:
            assert query.targeting_gap is not None

    def test_refinement_queries_high_priority(self, planner, populated_kb):
        """Test refinement queries have high priority."""
        result = planner.plan_queries(
            info_type=InformationType.EMPLOYMENT,
            knowledge_base=populated_kb,
            iteration_number=2,
            gaps=["employment_dates_missing"],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        for query in result.queries:
            if query.query_type == QueryType.GAP_FILL:
                assert query.priority >= 8  # High priority


class TestQueryDeduplication(TestQueryPlanner):
    """Tests for query deduplication."""

    def test_duplicate_queries_removed(self, planner, populated_kb):
        """Test that duplicate queries are removed."""
        # Generate queries twice with same params
        result1 = planner.plan_queries(
            info_type=InformationType.IDENTITY,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "sterling"],  # Duplicate provider
        )

        # Should deduplicate queries with same params
        query_keys = set()
        for q in result1.queries:
            key = (q.provider_id, q.check_type, str(sorted(q.search_params.items())))
            assert key not in query_keys, "Duplicate query found"
            query_keys.add(key)


class TestTierFiltering(TestQueryPlanner):
    """Tests for service tier filtering."""

    def test_standard_tier_excludes_enhanced_checks(self, planner, populated_kb):
        """Test Standard tier excludes Enhanced-only check types."""
        result = planner.plan_queries(
            info_type=InformationType.DIGITAL_FOOTPRINT,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        # Digital footprint is Enhanced-only, so Standard should get no queries
        # (the check types are filtered out)
        for query in result.queries:
            assert query.check_type not in {
                CheckType.DIGITAL_FOOTPRINT,
                CheckType.SOCIAL_MEDIA,
            }

    def test_enhanced_tier_includes_all_checks(self, planner, populated_kb):
        """Test Enhanced tier includes all check types."""
        result = planner.plan_queries(
            info_type=InformationType.DIGITAL_FOOTPRINT,
            knowledge_base=populated_kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            available_providers=["sterling"],
        )

        # Enhanced tier should get digital footprint queries
        check_types = {q.check_type for q in result.queries}
        # Should have digital footprint or social media check types
        assert CheckType.DIGITAL_FOOTPRINT in check_types or CheckType.SOCIAL_MEDIA in check_types


class TestNetworkQueries(TestQueryPlanner):
    """Tests for network expansion queries."""

    def test_network_queries_use_discovered_entities(self, planner):
        """Test network queries use discovered people and orgs."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        kb.discovered_people = [
            PersonEntity(
                name="Jane Doe",
                entity_type="person",
                relationship_to_subject="colleague",
                source="employment_records",
            ),
        ]
        kb.discovered_orgs = [
            OrgEntity(
                name="Acme Corp",
                entity_type="organization",
                relationship_to_subject="employer",
                source="employment_records",
            ),
        ]

        result = planner.plan_queries(
            info_type=InformationType.NETWORK_D2,
            knowledge_base=kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.ENHANCED,
            available_providers=["sterling"],
        )

        # Should have queries for discovered entities
        entity_names = set()
        for query in result.queries:
            if "entity_name" in query.search_params:
                entity_names.add(query.search_params["entity_name"])

        assert "Jane Doe" in entity_names or "Acme Corp" in entity_names


class TestInfoTypeToCheckTypeMapping(TestQueryPlanner):
    """Tests for INFO_TYPE_TO_CHECK_TYPES mapping."""

    def test_all_info_types_have_mapping(self):
        """Test all InformationType values have a mapping."""
        for info_type in InformationType:
            assert info_type in INFO_TYPE_TO_CHECK_TYPES

    def test_identity_maps_to_identity_checks(self):
        """Test identity maps to identity check types."""
        check_types = INFO_TYPE_TO_CHECK_TYPES[InformationType.IDENTITY]
        assert CheckType.IDENTITY_BASIC in check_types

    def test_criminal_maps_to_criminal_checks(self):
        """Test criminal maps to criminal check types."""
        check_types = INFO_TYPE_TO_CHECK_TYPES[InformationType.CRIMINAL]
        assert CheckType.CRIMINAL_NATIONAL in check_types
        assert CheckType.CRIMINAL_COUNTY in check_types

    def test_reconciliation_has_no_checks(self):
        """Test reconciliation has no direct check types."""
        check_types = INFO_TYPE_TO_CHECK_TYPES[InformationType.RECONCILIATION]
        assert check_types == []


class TestQueryLimiting(TestQueryPlanner):
    """Tests for query count limiting."""

    def test_queries_limited_to_max(self):
        """Test queries are limited to max_queries_per_iteration."""
        planner = QueryPlanner(max_queries_per_iteration=5)

        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        kb.known_counties = ["Cook", "DuPage", "Lake", "Will", "Kane", "McHenry", "Kendall"]

        result = planner.plan_queries(
            info_type=InformationType.CRIMINAL,
            knowledge_base=kb,
            iteration_number=1,
            gaps=[],
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "checkr", "hireright"],
        )

        assert result.query_count <= 5
