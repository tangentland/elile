"""Unit tests for ConfidenceScorer."""

from uuid import uuid7

import pytest

from elile.agent.state import InformationType
from elile.investigation.confidence_scorer import (
    DEFAULT_EXPECTED_FACTS,
    FOUNDATION_TYPES,
    ConfidenceScore,
    ConfidenceScorer,
    FactorBreakdown,
    ScorerConfig,
    create_confidence_scorer,
)
from elile.investigation.query_executor import QueryResult, QueryStatus
from elile.investigation.result_assessor import Fact


class TestScorerConfig:
    """Tests for ScorerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ScorerConfig()

        assert config.completeness_weight == 0.30
        assert config.corroboration_weight == 0.25
        assert config.query_success_weight == 0.20
        assert config.fact_confidence_weight == 0.15
        assert config.source_diversity_weight == 0.10

    def test_weights_sum_to_one(self):
        """Test that default weights sum to 1.0."""
        config = ScorerConfig()
        weights = config.get_weights()

        total = sum(weights.values())
        assert total == pytest.approx(1.0)

    def test_custom_config(self):
        """Test custom configuration."""
        config = ScorerConfig(
            completeness_weight=0.40,
            corroboration_weight=0.30,
            query_success_weight=0.15,
            fact_confidence_weight=0.10,
            source_diversity_weight=0.05,
        )

        assert config.completeness_weight == 0.40
        assert config.corroboration_weight == 0.30

    def test_get_weights(self):
        """Test getting weights as dictionary."""
        config = ScorerConfig()
        weights = config.get_weights()

        assert "completeness" in weights
        assert "corroboration" in weights
        assert "query_success" in weights
        assert "fact_confidence" in weights
        assert "source_diversity" in weights


class TestFactorBreakdown:
    """Tests for FactorBreakdown."""

    def test_breakdown_creation(self):
        """Test creating a factor breakdown."""
        breakdown = FactorBreakdown(
            name="completeness",
            raw_value=0.8,
            weight=0.30,
            weighted_value=0.24,
            description="4/5 expected facts",
        )

        assert breakdown.name == "completeness"
        assert breakdown.raw_value == 0.8
        assert breakdown.weight == 0.30
        assert breakdown.weighted_value == 0.24
        assert "4/5" in breakdown.description


class TestConfidenceScore:
    """Tests for ConfidenceScore."""

    def test_score_creation(self):
        """Test creating a confidence score."""
        score = ConfidenceScore(
            info_type=InformationType.IDENTITY,
            overall_score=0.75,
            completeness=0.8,
            corroboration=0.6,
            query_success=0.9,
            fact_confidence=0.85,
            source_diversity=0.67,
            threshold=0.85,
            meets_threshold=False,
        )

        assert score.info_type == InformationType.IDENTITY
        assert score.overall_score == 0.75
        assert score.meets_threshold is False

    def test_gap_to_threshold(self):
        """Test gap_to_threshold calculation."""
        score = ConfidenceScore(
            info_type=InformationType.IDENTITY,
            overall_score=0.70,
            threshold=0.85,
            meets_threshold=False,
        )

        assert score.gap_to_threshold == pytest.approx(0.15)

    def test_gap_to_threshold_when_met(self):
        """Test gap_to_threshold when threshold is met."""
        score = ConfidenceScore(
            info_type=InformationType.IDENTITY,
            overall_score=0.90,
            threshold=0.85,
            meets_threshold=True,
        )

        assert score.gap_to_threshold == 0.0

    def test_factors_dict(self):
        """Test getting factors as dictionary."""
        score = ConfidenceScore(
            info_type=InformationType.IDENTITY,
            overall_score=0.75,
            completeness=0.8,
            corroboration=0.6,
            query_success=0.9,
            fact_confidence=0.85,
            source_diversity=0.67,
        )

        factors = score.factors_dict
        assert factors["completeness"] == 0.8
        assert factors["corroboration"] == 0.6

    def test_to_dict(self):
        """Test serialization to dictionary."""
        score = ConfidenceScore(
            info_type=InformationType.IDENTITY,
            overall_score=0.75,
            threshold=0.85,
            meets_threshold=False,
            fact_count=4,
            expected_fact_count=5,
        )

        data = score.to_dict()
        assert data["info_type"] == "identity"
        assert data["overall_score"] == 0.75
        assert data["statistics"]["fact_count"] == 4


class TestDefaultExpectedFacts:
    """Tests for default expected facts constants."""

    def test_identity_expected_facts(self):
        """Test identity expected facts."""
        assert DEFAULT_EXPECTED_FACTS[InformationType.IDENTITY] == 5

    def test_employment_expected_facts(self):
        """Test employment expected facts."""
        assert DEFAULT_EXPECTED_FACTS[InformationType.EMPLOYMENT] == 3

    def test_criminal_expected_facts(self):
        """Test criminal expected facts."""
        assert DEFAULT_EXPECTED_FACTS[InformationType.CRIMINAL] == 1


class TestFoundationTypes:
    """Tests for foundation types constant."""

    def test_identity_is_foundation(self):
        """Test that identity is a foundation type."""
        assert InformationType.IDENTITY in FOUNDATION_TYPES

    def test_employment_is_foundation(self):
        """Test that employment is a foundation type."""
        assert InformationType.EMPLOYMENT in FOUNDATION_TYPES

    def test_criminal_not_foundation(self):
        """Test that criminal is not a foundation type."""
        assert InformationType.CRIMINAL not in FOUNDATION_TYPES


class TestConfidenceScorer:
    """Tests for ConfidenceScorer class."""

    @pytest.fixture
    def scorer(self):
        """Create a default scorer."""
        return ConfidenceScorer()

    @pytest.fixture
    def sample_facts(self):
        """Create sample facts."""
        return [
            Fact.create("name_variant", "John Smith", "sterling", confidence=0.95),
            Fact.create("dob", "1990-01-15", "sterling", confidence=0.90),
            Fact.create("address", {"city": "New York"}, "checkr", confidence=0.85),
            Fact.create("ssn_last4", "1234", "sterling", confidence=0.99),
            Fact.create("phone", "555-123-4567", "checkr", confidence=0.80),
        ]

    @pytest.fixture
    def sample_results(self):
        """Create sample query results."""
        return [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
            QueryResult(
                query_id=uuid7(),
                provider_id="checkr",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
        ]

    def test_creation_default(self):
        """Test creating scorer with defaults."""
        scorer = ConfidenceScorer()

        assert scorer.config is not None
        assert scorer.expected_facts is not None

    def test_creation_custom_config(self):
        """Test creating scorer with custom config."""
        config = ScorerConfig(completeness_weight=0.40)
        scorer = ConfidenceScorer(config=config)

        assert scorer.config.completeness_weight == 0.40

    def test_creation_custom_expected_facts(self):
        """Test creating scorer with custom expected facts."""
        expected = {InformationType.IDENTITY: 10}
        scorer = ConfidenceScorer(expected_facts=expected)

        assert scorer.expected_facts[InformationType.IDENTITY] == 10


class TestCompletenessCalculation:
    """Tests for completeness calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_completeness_full(self, scorer):
        """Test completeness when all expected facts present."""
        facts = [
            Fact.create("name_variant", "John", "sterling"),
            Fact.create("dob", "1990-01-15", "sterling"),
            Fact.create("address", {"city": "NY"}, "sterling"),
            Fact.create("ssn_last4", "1234", "sterling"),
            Fact.create("phone", "555-1234", "sterling"),
        ]

        completeness = scorer._calculate_completeness(InformationType.IDENTITY, facts)
        assert completeness == 1.0

    def test_completeness_partial(self, scorer):
        """Test completeness with partial facts."""
        facts = [
            Fact.create("name_variant", "John", "sterling"),
            Fact.create("dob", "1990-01-15", "sterling"),
        ]

        completeness = scorer._calculate_completeness(InformationType.IDENTITY, facts)
        # 2/5 = 0.4
        assert completeness == pytest.approx(0.4)

    def test_completeness_empty(self, scorer):
        """Test completeness with no facts."""
        completeness = scorer._calculate_completeness(InformationType.IDENTITY, [])
        assert completeness == 0.0

    def test_completeness_over_expected(self, scorer):
        """Test completeness capped at 1.0 when over expected."""
        facts = [Fact.create(f"fact_{i}", f"value_{i}", "sterling") for i in range(10)]

        completeness = scorer._calculate_completeness(InformationType.IDENTITY, facts)
        # Should be capped at 1.0 even though 10 > 5
        assert completeness == 1.0


class TestCorroborationCalculation:
    """Tests for corroboration calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_corroboration_full(self, scorer):
        """Test corroboration when all facts have multiple sources."""
        facts = [
            Fact.create("name_variant", "John", "sterling"),
            Fact.create("name_variant", "John", "checkr"),  # Same type, different source
            Fact.create("dob", "1990-01-15", "sterling"),
            Fact.create("dob", "1990-01-15", "checkr"),
        ]

        corroboration = scorer._calculate_corroboration(facts)
        # Both fact types have 2 sources
        assert corroboration == 1.0

    def test_corroboration_partial(self, scorer):
        """Test corroboration with partial multi-source."""
        facts = [
            Fact.create("name_variant", "John", "sterling"),
            Fact.create("name_variant", "John", "checkr"),  # Corroborated
            Fact.create("dob", "1990-01-15", "sterling"),  # Not corroborated
        ]

        corroboration = scorer._calculate_corroboration(facts)
        # 1/2 fact types corroborated
        assert corroboration == pytest.approx(0.5)

    def test_corroboration_none(self, scorer):
        """Test corroboration when no multi-source."""
        facts = [
            Fact.create("name_variant", "John", "sterling"),
            Fact.create("dob", "1990-01-15", "sterling"),
        ]

        corroboration = scorer._calculate_corroboration(facts)
        # No fact types have multiple sources
        assert corroboration == 0.0

    def test_corroboration_empty(self, scorer):
        """Test corroboration with no facts."""
        corroboration = scorer._calculate_corroboration([])
        assert corroboration == 0.0


class TestQuerySuccessCalculation:
    """Tests for query success calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_query_success_all(self, scorer):
        """Test query success when all succeed."""
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
            QueryResult(
                query_id=uuid7(),
                provider_id="checkr",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
        ]

        success_rate = scorer._calculate_query_success(results)
        assert success_rate == 1.0

    def test_query_success_partial(self, scorer):
        """Test query success with partial success."""
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
            QueryResult(
                query_id=uuid7(),
                provider_id="checkr",
                check_type="identity_basic",
                status=QueryStatus.FAILED,
            ),
        ]

        success_rate = scorer._calculate_query_success(results)
        assert success_rate == 0.5

    def test_query_success_none(self, scorer):
        """Test query success when all fail."""
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.FAILED,
            ),
        ]

        success_rate = scorer._calculate_query_success(results)
        assert success_rate == 0.0

    def test_query_success_empty(self, scorer):
        """Test query success with no results."""
        success_rate = scorer._calculate_query_success([])
        assert success_rate == 0.0


class TestFactConfidenceCalculation:
    """Tests for fact confidence calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_fact_confidence_average(self, scorer):
        """Test average fact confidence."""
        facts = [
            Fact.create("name", "John", "sterling", confidence=0.90),
            Fact.create("dob", "1990", "checkr", confidence=0.80),
        ]

        avg_confidence = scorer._calculate_fact_confidence(facts)
        assert avg_confidence == pytest.approx(0.85)

    def test_fact_confidence_single(self, scorer):
        """Test fact confidence with single fact."""
        facts = [Fact.create("name", "John", "sterling", confidence=0.95)]

        avg_confidence = scorer._calculate_fact_confidence(facts)
        assert avg_confidence == 0.95

    def test_fact_confidence_empty(self, scorer):
        """Test fact confidence with no facts."""
        avg_confidence = scorer._calculate_fact_confidence([])
        assert avg_confidence == 0.0


class TestSourceDiversityCalculation:
    """Tests for source diversity calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_source_diversity_full(self, scorer):
        """Test source diversity with 3+ sources."""
        facts = [
            Fact.create("name", "John", "sterling"),
            Fact.create("dob", "1990", "checkr"),
            Fact.create("address", "NYC", "hireright"),
        ]

        diversity = scorer._calculate_source_diversity(facts)
        # 3 sources = full score
        assert diversity == 1.0

    def test_source_diversity_partial(self, scorer):
        """Test source diversity with 2 sources."""
        facts = [
            Fact.create("name", "John", "sterling"),
            Fact.create("dob", "1990", "checkr"),
        ]

        diversity = scorer._calculate_source_diversity(facts)
        # 2/3 = 0.67
        assert diversity == pytest.approx(2 / 3)

    def test_source_diversity_single(self, scorer):
        """Test source diversity with 1 source."""
        facts = [
            Fact.create("name", "John", "sterling"),
            Fact.create("dob", "1990", "sterling"),
        ]

        diversity = scorer._calculate_source_diversity(facts)
        # 1/3 = 0.33
        assert diversity == pytest.approx(1 / 3)

    def test_source_diversity_empty(self, scorer):
        """Test source diversity with no facts."""
        diversity = scorer._calculate_source_diversity([])
        assert diversity == 0.0


class TestCalculateConfidence:
    """Tests for overall confidence calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_calculate_confidence_full(self, scorer):
        """Test confidence calculation with good data."""
        facts = [
            Fact.create("name_variant", "John", "sterling", confidence=0.95),
            Fact.create("name_variant", "John", "checkr", confidence=0.90),
            Fact.create("dob", "1990", "sterling", confidence=0.95),
            Fact.create("dob", "1990", "checkr", confidence=0.90),
            Fact.create("address", "NYC", "hireright", confidence=0.85),
            Fact.create("ssn_last4", "1234", "sterling", confidence=0.99),
            Fact.create("phone", "555", "checkr", confidence=0.80),
        ]

        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
            QueryResult(
                query_id=uuid7(),
                provider_id="checkr",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
            QueryResult(
                query_id=uuid7(),
                provider_id="hireright",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            ),
        ]

        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,
            facts=facts,
            query_results=results,
            threshold=0.85,
        )

        assert score.overall_score > 0.8
        assert score.info_type == InformationType.IDENTITY

    def test_calculate_confidence_returns_factors(self, scorer):
        """Test that confidence calculation returns all factors."""
        facts = [Fact.create("name", "John", "sterling", confidence=0.90)]
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            )
        ]

        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,
            facts=facts,
            query_results=results,
            threshold=0.85,
        )

        assert score.completeness >= 0.0
        assert score.corroboration >= 0.0
        assert score.query_success >= 0.0
        assert score.fact_confidence >= 0.0
        assert score.source_diversity >= 0.0

    def test_calculate_confidence_empty(self, scorer):
        """Test confidence with no data."""
        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,
            facts=[],
            query_results=[],
            threshold=0.85,
        )

        assert score.overall_score == 0.0
        assert score.meets_threshold is False


class TestFoundationTypeBoost:
    """Tests for foundation type threshold boost."""

    def test_foundation_type_higher_threshold(self):
        """Test that foundation types get higher effective threshold."""
        config = ScorerConfig(foundation_type_threshold_boost=0.05)
        scorer = ConfidenceScorer(config=config)

        facts = [Fact.create("name", "John", "sterling", confidence=0.90)]
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            )
        ]

        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,  # Foundation type
            facts=facts,
            query_results=results,
            threshold=0.85,
        )

        # Effective threshold should be 0.85 + 0.05 = 0.90
        assert score.threshold == 0.90
        assert score.is_foundation_type is True

    def test_non_foundation_type_normal_threshold(self):
        """Test that non-foundation types use normal threshold."""
        scorer = ConfidenceScorer()

        facts = [Fact.create("record", "clear", "sterling", confidence=0.90)]
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="criminal_national",
                status=QueryStatus.SUCCESS,
            )
        ]

        score = scorer.calculate_confidence(
            info_type=InformationType.CRIMINAL,  # Not foundation
            facts=facts,
            query_results=results,
            threshold=0.85,
        )

        # Threshold should remain 0.85
        assert score.threshold == 0.85
        assert score.is_foundation_type is False


class TestAggregateConfidence:
    """Tests for aggregate confidence calculation."""

    @pytest.fixture
    def scorer(self):
        """Create a scorer."""
        return ConfidenceScorer()

    def test_aggregate_empty(self, scorer):
        """Test aggregate with no scores."""
        aggregate = scorer.calculate_aggregate_confidence([])
        assert aggregate == 0.0

    def test_aggregate_single(self, scorer):
        """Test aggregate with single score."""
        score = ConfidenceScore(
            info_type=InformationType.CRIMINAL,
            overall_score=0.80,
            is_foundation_type=False,
        )

        aggregate = scorer.calculate_aggregate_confidence([score])
        assert aggregate == 0.80

    def test_aggregate_foundation_weighted(self, scorer):
        """Test that foundation types are weighted more heavily."""
        scores = [
            ConfidenceScore(
                info_type=InformationType.IDENTITY,
                overall_score=0.90,
                is_foundation_type=True,
            ),
            ConfidenceScore(
                info_type=InformationType.CRIMINAL,
                overall_score=0.80,
                is_foundation_type=False,
            ),
        ]

        aggregate = scorer.calculate_aggregate_confidence(scores)
        # (0.90 * 1.5 + 0.80 * 1.0) / (1.5 + 1.0) = (1.35 + 0.80) / 2.5 = 0.86
        assert aggregate == pytest.approx(0.86)


class TestExpectedFactsConfiguration:
    """Tests for expected facts configuration."""

    def test_get_expected_facts(self):
        """Test getting expected facts for a type."""
        scorer = ConfidenceScorer()
        expected = scorer.get_expected_facts(InformationType.IDENTITY)
        assert expected == 5

    def test_set_expected_facts(self):
        """Test setting expected facts for a type."""
        scorer = ConfidenceScorer()
        scorer.set_expected_facts(InformationType.IDENTITY, 10)

        assert scorer.get_expected_facts(InformationType.IDENTITY) == 10

    def test_custom_expected_facts_in_calculation(self):
        """Test that custom expected facts affect calculation."""
        expected = {InformationType.IDENTITY: 2}
        scorer = ConfidenceScorer(expected_facts=expected)

        facts = [
            Fact.create("name", "John", "sterling"),
            Fact.create("dob", "1990", "sterling"),
        ]

        completeness = scorer._calculate_completeness(InformationType.IDENTITY, facts)
        # 2/2 = 1.0 with custom expected
        assert completeness == 1.0


class TestFactorBreakdownInScore:
    """Tests for factor breakdown in confidence score."""

    def test_breakdown_included(self):
        """Test that factor breakdown is included in score."""
        scorer = ConfidenceScorer()

        facts = [Fact.create("name", "John", "sterling", confidence=0.90)]
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            )
        ]

        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,
            facts=facts,
            query_results=results,
            threshold=0.85,
        )

        assert len(score.factor_breakdown) == 5
        breakdown_names = {b.name for b in score.factor_breakdown}
        assert "completeness" in breakdown_names
        assert "corroboration" in breakdown_names

    def test_breakdown_weighted_values(self):
        """Test that breakdown weighted values are correct."""
        scorer = ConfidenceScorer()

        facts = [Fact.create("name", "John", "sterling", confidence=0.90)]
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
            )
        ]

        score = scorer.calculate_confidence(
            info_type=InformationType.IDENTITY,
            facts=facts,
            query_results=results,
            threshold=0.85,
        )

        for breakdown in score.factor_breakdown:
            expected_weighted = breakdown.raw_value * breakdown.weight
            assert breakdown.weighted_value == pytest.approx(expected_weighted)


class TestFactoryFunction:
    """Tests for create_confidence_scorer factory."""

    def test_create_default(self):
        """Test creating scorer with defaults."""
        scorer = create_confidence_scorer()
        assert isinstance(scorer, ConfidenceScorer)

    def test_create_with_config(self):
        """Test creating scorer with custom config."""
        config = ScorerConfig(completeness_weight=0.50)
        scorer = create_confidence_scorer(config=config)

        assert scorer.config.completeness_weight == 0.50

    def test_create_with_expected_facts(self):
        """Test creating scorer with custom expected facts."""
        expected = {InformationType.IDENTITY: 10}
        scorer = create_confidence_scorer(expected_facts=expected)

        assert scorer.expected_facts[InformationType.IDENTITY] == 10
