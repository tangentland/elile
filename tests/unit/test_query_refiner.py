"""Unit tests for QueryRefiner."""

from datetime import date
from uuid import uuid7

import pytest

from elile.agent.state import InformationType, KnowledgeBase, ServiceTier
from elile.compliance.types import Locale
from elile.investigation.query_planner import QueryType
from elile.investigation.query_refiner import (
    GAP_STRATEGIES,
    QueryRefiner,
    RefinerConfig,
    RefinementResult,
    create_query_refiner,
)
from elile.investigation.result_assessor import (
    AssessmentResult,
    ConfidenceFactors,
    Gap,
)


class TestRefinerConfig:
    """Tests for RefinerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RefinerConfig()

        assert config.max_queries_per_gap == 3
        assert config.max_total_queries == 15
        assert config.include_alternative_providers is True
        assert config.min_gap_priority == 3

    def test_custom_config(self):
        """Test custom configuration."""
        config = RefinerConfig(
            max_queries_per_gap=5,
            max_total_queries=20,
            include_alternative_providers=False,
            min_gap_priority=2,
        )

        assert config.max_queries_per_gap == 5
        assert config.max_total_queries == 20
        assert config.include_alternative_providers is False
        assert config.min_gap_priority == 2


class TestRefinementResult:
    """Tests for RefinementResult."""

    def test_empty_result(self):
        """Test RefinementResult with no queries."""
        result = RefinementResult(
            info_type=InformationType.IDENTITY,
            iteration_number=2,
            gaps_addressed=0,
            queries=[],
        )

        assert result.query_count == 0
        assert result.has_queries is False

    def test_result_with_queries(self):
        """Test RefinementResult with queries."""
        from elile.compliance.types import CheckType
        from elile.investigation.query_planner import SearchQuery

        query = SearchQuery(
            query_id=uuid7(),
            info_type=InformationType.IDENTITY,
            query_type=QueryType.GAP_FILL,
            provider_id="sterling",
            check_type=CheckType.SSN_TRACE,
            search_params={"name": "John Smith"},
            iteration_number=2,
        )

        result = RefinementResult(
            info_type=InformationType.IDENTITY,
            iteration_number=2,
            gaps_addressed=1,
            queries=[query],
        )

        assert result.query_count == 1
        assert result.has_queries is True


class TestGapStrategies:
    """Tests for gap-specific strategies."""

    def test_identity_gap_strategies_exist(self):
        """Test that identity gap strategies are defined."""
        assert "missing_address" in GAP_STRATEGIES
        assert "missing_dob" in GAP_STRATEGIES
        assert "missing_name_variant" in GAP_STRATEGIES

    def test_employment_gap_strategies_exist(self):
        """Test that employment gap strategies are defined."""
        assert "no_employment_found" in GAP_STRATEGIES
        assert "missing_end_date" in GAP_STRATEGIES

    def test_education_gap_strategies_exist(self):
        """Test that education gap strategies are defined."""
        assert "no_education_found" in GAP_STRATEGIES
        assert "missing_school" in GAP_STRATEGIES

    def test_strategy_structure(self):
        """Test that strategies have required fields."""
        for gap_type, strategy in GAP_STRATEGIES.items():
            assert "check_types" in strategy, f"Strategy {gap_type} missing check_types"
            assert "focus" in strategy, f"Strategy {gap_type} missing focus"
            assert isinstance(strategy["check_types"], list)


class TestQueryRefiner:
    """Tests for QueryRefiner class."""

    @pytest.fixture
    def knowledge_base(self):
        """Create a knowledge base with basic data."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith", "John Q. Smith"]
        kb.confirmed_dob = date(1990, 1, 15)
        kb.confirmed_ssn_last4 = "1234"
        kb.known_states = ["NY", "CA"]
        return kb

    @pytest.fixture
    def refiner(self):
        """Create a QueryRefiner."""
        return QueryRefiner()

    def test_refine_empty_assessment(self, refiner, knowledge_base):
        """Test refining assessment with no gaps."""
        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            gaps_identified=[],
            confidence_score=0.90,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.query_count == 0
        assert result.gaps_addressed == 0

    def test_refine_single_gap(self, refiner, knowledge_base):
        """Test refining assessment with single gap."""
        gap = Gap.create(
            gap_type="missing_address",
            description="No address found",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            gaps_identified=[gap],
            queryable_gaps=1,
            confidence_score=0.60,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.query_count > 0
        assert result.gaps_addressed == 1
        assert all(q.targeting_gap == "missing_address" for q in result.queries)

    def test_refine_multiple_gaps(self, refiner, knowledge_base):
        """Test refining assessment with multiple gaps."""
        gaps = [
            Gap.create(
                gap_type="missing_address",
                description="No address found",
                info_type=InformationType.IDENTITY,
                priority=1,
            ),
            Gap.create(
                gap_type="missing_dob",
                description="No DOB confirmed",
                info_type=InformationType.IDENTITY,
                priority=2,
            ),
        ]

        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            gaps_identified=gaps,
            queryable_gaps=2,
            confidence_score=0.50,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.query_count > 0
        assert result.gaps_addressed >= 1

    def test_refine_non_queryable_gap_skipped(self, refiner, knowledge_base):
        """Test that non-queryable gaps are skipped."""
        gap = Gap.create(
            gap_type="data_unavailable",
            description="Data not available",
            info_type=InformationType.IDENTITY,
            priority=1,
            can_query=False,
        )

        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            gaps_identified=[gap],
            queryable_gaps=0,
            confidence_score=0.60,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.query_count == 0
        assert result.gaps_addressed == 0


class TestGapPrioritization:
    """Tests for gap prioritization logic."""

    @pytest.fixture
    def refiner(self):
        """Create a QueryRefiner."""
        return QueryRefiner()

    def test_no_gaps_prioritized_first(self, refiner):
        """Test that 'no_*' gaps are prioritized over 'missing_*' gaps."""
        gaps = [
            Gap.create(
                gap_type="missing_address",
                description="Missing address",
                info_type=InformationType.IDENTITY,
                priority=1,
            ),
            Gap.create(
                gap_type="no_employment_found",
                description="No employment",
                info_type=InformationType.EMPLOYMENT,
                priority=1,
            ),
        ]

        prioritized = refiner._prioritize_gaps(gaps, InformationType.IDENTITY)

        assert prioritized[0].gap_type == "no_employment_found"
        assert prioritized[1].gap_type == "missing_address"

    def test_priority_within_category(self, refiner):
        """Test that gaps are sorted by priority within category."""
        gaps = [
            Gap.create(
                gap_type="missing_address",
                description="Missing address",
                info_type=InformationType.IDENTITY,
                priority=2,
            ),
            Gap.create(
                gap_type="missing_dob",
                description="Missing DOB",
                info_type=InformationType.IDENTITY,
                priority=1,
            ),
        ]

        prioritized = refiner._prioritize_gaps(gaps, InformationType.IDENTITY)

        assert prioritized[0].gap_type == "missing_dob"
        assert prioritized[1].gap_type == "missing_address"


class TestQueryGeneration:
    """Tests for query generation logic."""

    @pytest.fixture
    def knowledge_base(self):
        """Create a knowledge base with data."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        kb.confirmed_dob = date(1990, 1, 15)
        kb.known_states = ["NY"]
        kb.known_counties = ["New York County"]
        return kb

    @pytest.fixture
    def refiner(self):
        """Create a QueryRefiner."""
        return QueryRefiner()

    def test_query_type_is_gap_fill(self, refiner, knowledge_base):
        """Test that generated queries have GAP_FILL type."""
        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        queries = refiner._generate_gap_queries(
            gap=gap,
            info_type=InformationType.IDENTITY,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
            iteration_number=2,
        )

        assert len(queries) > 0
        assert all(q.query_type == QueryType.GAP_FILL for q in queries)

    def test_query_targets_gap(self, refiner, knowledge_base):
        """Test that queries target the specified gap."""
        gap = Gap.create(
            gap_type="no_employment_found",
            description="No employment",
            info_type=InformationType.EMPLOYMENT,
            priority=1,
        )

        queries = refiner._generate_gap_queries(
            gap=gap,
            info_type=InformationType.EMPLOYMENT,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
            iteration_number=2,
        )

        assert len(queries) > 0
        assert all(q.targeting_gap == "no_employment_found" for q in queries)

    def test_no_queries_without_name(self, refiner):
        """Test that no queries are generated without a primary name."""
        kb = KnowledgeBase()  # Empty KB

        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        queries = refiner._generate_gap_queries(
            gap=gap,
            info_type=InformationType.IDENTITY,
            knowledge_base=kb,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
            iteration_number=2,
        )

        assert len(queries) == 0


class TestQueryDeduplication:
    """Tests for query deduplication."""

    @pytest.fixture
    def refiner(self):
        """Create a QueryRefiner."""
        return QueryRefiner()

    def test_duplicate_queries_removed(self, refiner):
        """Test that duplicate queries are removed."""
        from elile.compliance.types import CheckType
        from elile.investigation.query_planner import SearchQuery

        query1 = SearchQuery(
            query_id=uuid7(),
            info_type=InformationType.IDENTITY,
            query_type=QueryType.GAP_FILL,
            provider_id="sterling",
            check_type=CheckType.SSN_TRACE,
            search_params={"name": "John Smith"},
            iteration_number=2,
            targeting_gap="missing_address",
        )

        query2 = SearchQuery(
            query_id=uuid7(),  # Different ID
            info_type=InformationType.IDENTITY,
            query_type=QueryType.GAP_FILL,
            provider_id="sterling",  # Same provider
            check_type=CheckType.SSN_TRACE,  # Same check type
            search_params={"name": "John Smith"},  # Same params
            iteration_number=2,
            targeting_gap="missing_address",  # Same gap
        )

        deduped = refiner._deduplicate_queries([query1, query2])

        assert len(deduped) == 1

    def test_different_providers_not_deduped(self, refiner):
        """Test that queries to different providers are not deduped."""
        from elile.compliance.types import CheckType
        from elile.investigation.query_planner import SearchQuery

        query1 = SearchQuery(
            query_id=uuid7(),
            info_type=InformationType.IDENTITY,
            query_type=QueryType.GAP_FILL,
            provider_id="sterling",
            check_type=CheckType.SSN_TRACE,
            search_params={"name": "John Smith"},
            iteration_number=2,
            targeting_gap="missing_address",
        )

        query2 = SearchQuery(
            query_id=uuid7(),
            info_type=InformationType.IDENTITY,
            query_type=QueryType.GAP_FILL,
            provider_id="checkr",  # Different provider
            check_type=CheckType.SSN_TRACE,
            search_params={"name": "John Smith"},
            iteration_number=2,
            targeting_gap="missing_address",
        )

        deduped = refiner._deduplicate_queries([query1, query2])

        assert len(deduped) == 2


class TestSearchParamsEnrichment:
    """Tests for search params enrichment from knowledge base."""

    @pytest.fixture
    def refiner(self):
        """Create a QueryRefiner."""
        return QueryRefiner()

    def test_includes_name_variants(self, refiner):
        """Test that name variants are included in params."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith", "John Q. Smith", "Johnny Smith"]

        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        params = refiner._build_search_params(
            gap=gap,
            knowledge_base=kb,
            primary_name="John Smith",
            focus="address_history",
            locale=Locale.US,
        )

        assert params["name"] == "John Smith"
        assert "name_variants" in params
        assert "John Q. Smith" in params["name_variants"]

    def test_includes_dob_when_known(self, refiner):
        """Test that DOB is included when known."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        kb.confirmed_dob = date(1990, 5, 15)

        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        params = refiner._build_search_params(
            gap=gap,
            knowledge_base=kb,
            primary_name="John Smith",
            focus="address_history",
            locale=Locale.US,
        )

        assert params["dob"] == "1990-05-15"

    def test_employment_gap_includes_employers(self, refiner):
        """Test that employment gaps include known employers."""
        from elile.agent.state import EmployerRecord

        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        kb.employers = [
            EmployerRecord(employer_name="Acme Corp", source="sterling"),
            EmployerRecord(employer_name="Tech Inc", source="checkr"),
        ]

        gap = Gap.create(
            gap_type="missing_employment_dates",
            description="Missing dates",
            info_type=InformationType.EMPLOYMENT,
            priority=1,
        )

        params = refiner._build_search_params(
            gap=gap,
            knowledge_base=kb,
            primary_name="John Smith",
            focus="employment_dates",
            locale=Locale.US,
        )

        assert "known_employers" in params
        assert "Acme Corp" in params["known_employers"]

    def test_criminal_gap_includes_jurisdictions(self, refiner):
        """Test that criminal gaps include jurisdiction info."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        kb.known_states = ["NY", "CA"]
        kb.known_counties = ["New York County", "Los Angeles County"]

        gap = Gap.create(
            gap_type="missing_criminal_record",
            description="No criminal check",
            info_type=InformationType.CRIMINAL,
            priority=1,
        )

        params = refiner._build_search_params(
            gap=gap,
            knowledge_base=kb,
            primary_name="John Smith",
            focus="criminal_search",
            locale=Locale.US,
        )

        assert "states" in params
        assert "NY" in params["states"]
        assert "counties" in params
        assert "New York County" in params["counties"]


class TestMaxQueriesLimit:
    """Tests for query limits."""

    def test_respects_max_queries_per_gap(self):
        """Test that max queries per gap is respected."""
        config = RefinerConfig(max_queries_per_gap=1)
        refiner = QueryRefiner(config=config)

        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]

        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        queries = refiner._generate_gap_queries(
            gap=gap,
            info_type=InformationType.IDENTITY,
            knowledge_base=kb,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "checkr", "hireright"],
            iteration_number=2,
        )

        assert len(queries) <= 1

    def test_respects_max_total_queries(self):
        """Test that max total queries is respected."""
        config = RefinerConfig(max_total_queries=5, max_queries_per_gap=10)
        refiner = QueryRefiner(config=config)

        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]

        gaps = [
            Gap.create(
                gap_type="missing_address",
                description="No address",
                info_type=InformationType.IDENTITY,
                priority=1,
            ),
            Gap.create(
                gap_type="missing_dob",
                description="No DOB",
                info_type=InformationType.IDENTITY,
                priority=1,
            ),
            Gap.create(
                gap_type="no_employment_found",
                description="No employment",
                info_type=InformationType.EMPLOYMENT,
                priority=1,
            ),
        ]

        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            gaps_identified=gaps,
            queryable_gaps=3,
            confidence_score=0.50,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=kb,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling", "checkr"],
        )

        assert result.query_count <= 5


class TestFactoryFunction:
    """Tests for create_query_refiner factory."""

    def test_create_refiner_default(self):
        """Test creating refiner with defaults."""
        refiner = create_query_refiner()

        assert isinstance(refiner, QueryRefiner)
        assert refiner.config.max_queries_per_gap == 3

    def test_create_refiner_with_config(self):
        """Test creating refiner with custom config."""
        config = RefinerConfig(max_queries_per_gap=5)
        refiner = create_query_refiner(config=config)

        assert refiner.config.max_queries_per_gap == 5


class TestIterationNumber:
    """Tests for iteration number handling."""

    @pytest.fixture
    def knowledge_base(self):
        """Create a knowledge base."""
        kb = KnowledgeBase()
        kb.confirmed_names = ["John Smith"]
        return kb

    @pytest.fixture
    def refiner(self):
        """Create a QueryRefiner."""
        return QueryRefiner()

    def test_increments_iteration_number(self, refiner, knowledge_base):
        """Test that refinement increments iteration number."""
        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=1,
            gaps_identified=[gap],
            queryable_gaps=1,
            confidence_score=0.60,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.iteration_number == 2
        assert all(q.iteration_number == 2 for q in result.queries)

    def test_third_iteration(self, refiner, knowledge_base):
        """Test refinement from second to third iteration."""
        gap = Gap.create(
            gap_type="missing_address",
            description="No address",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        assessment = AssessmentResult(
            info_type=InformationType.IDENTITY,
            iteration_number=2,  # Second iteration
            gaps_identified=[gap],
            queryable_gaps=1,
            confidence_score=0.70,
        )

        result = refiner.refine_queries(
            assessment=assessment,
            knowledge_base=knowledge_base,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
            available_providers=["sterling"],
        )

        assert result.iteration_number == 3
