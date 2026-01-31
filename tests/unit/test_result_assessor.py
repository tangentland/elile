"""Unit tests for ResultAssessor."""

from datetime import UTC, datetime
from uuid import uuid7

import pytest

from elile.agent.state import (
    Address,
    InconsistencyType,
    InformationType,
    KnowledgeBase,
)
from elile.investigation.query_executor import QueryResult, QueryStatus
from elile.investigation.result_assessor import (
    AssessmentResult,
    ConfidenceFactors,
    DetectedInconsistency,
    DiscoveredEntity,
    Fact,
    Gap,
    ResultAssessor,
    create_result_assessor,
)


class TestFact:
    """Tests for Fact dataclass."""

    def test_fact_creation(self):
        """Test creating a Fact."""
        fact = Fact.create(
            fact_type="name_variant",
            value="John Smith",
            source_provider="sterling",
            confidence=0.95,
        )

        assert fact.fact_type == "name_variant"
        assert fact.value == "John Smith"
        assert fact.source_provider == "sterling"
        assert fact.confidence == 0.95
        assert fact.fact_id is not None
        assert fact.discovered_at is not None

    def test_fact_default_confidence(self):
        """Test Fact with default confidence."""
        fact = Fact.create(
            fact_type="address",
            value={"city": "New York"},
            source_provider="checkr",
        )

        assert fact.confidence == 0.85


class TestConfidenceFactors:
    """Tests for ConfidenceFactors."""

    def test_default_factors(self):
        """Test default factor values."""
        factors = ConfidenceFactors()

        assert factors.completeness == 0.0
        assert factors.corroboration == 0.0
        assert factors.query_success == 0.0
        assert factors.fact_confidence == 0.0
        assert factors.source_diversity == 0.0

    def test_weighted_score_calculation(self):
        """Test weighted score calculation."""
        factors = ConfidenceFactors(
            completeness=1.0,
            corroboration=1.0,
            query_success=1.0,
            fact_confidence=1.0,
            source_diversity=1.0,
        )

        # All factors at 1.0 should give 1.0 total
        assert factors.calculate_weighted_score() == 1.0

    def test_partial_weighted_score(self):
        """Test weighted score with partial values."""
        factors = ConfidenceFactors(
            completeness=0.5,  # 0.5 * 0.30 = 0.15
            corroboration=0.5,  # 0.5 * 0.25 = 0.125
            query_success=0.5,  # 0.5 * 0.20 = 0.10
            fact_confidence=0.5,  # 0.5 * 0.15 = 0.075
            source_diversity=0.5,  # 0.5 * 0.10 = 0.05
        )

        # Sum should be 0.5
        assert factors.calculate_weighted_score() == pytest.approx(0.5)


class TestGap:
    """Tests for Gap dataclass."""

    def test_gap_creation(self):
        """Test creating a Gap."""
        gap = Gap.create(
            gap_type="missing_address",
            description="No address found",
            info_type=InformationType.IDENTITY,
            priority=1,
        )

        assert gap.gap_type == "missing_address"
        assert gap.description == "No address found"
        assert gap.info_type == InformationType.IDENTITY
        assert gap.priority == 1
        assert gap.can_query is True

    def test_gap_non_queryable(self):
        """Test creating a non-queryable gap."""
        gap = Gap.create(
            gap_type="data_unavailable",
            description="Provider does not support this data type",
            info_type=InformationType.CRIMINAL,
            can_query=False,
        )

        assert gap.can_query is False


class TestDetectedInconsistency:
    """Tests for DetectedInconsistency dataclass."""

    def test_inconsistency_creation(self):
        """Test creating an inconsistency."""
        inc = DetectedInconsistency.create(
            field="employer_name",
            claimed_value="Acme Corp",
            found_value="Acme Corporation",
            source_a="sterling",
            source_b="checkr",
            severity="minor",
            inconsistency_type=InconsistencyType.SPELLING_VARIANT,
            deception_score=0.1,
        )

        assert inc.field == "employer_name"
        assert inc.claimed_value == "Acme Corp"
        assert inc.found_value == "Acme Corporation"
        assert inc.severity == "minor"
        assert inc.deception_score == 0.1


class TestDiscoveredEntity:
    """Tests for DiscoveredEntity dataclass."""

    def test_discovered_entity_creation(self):
        """Test creating a discovered entity."""
        entity = DiscoveredEntity.create(
            entity_type="organization",
            name="Acme Corp",
            discovered_from="employer",
            source_provider="sterling",
            relationship_to_subject="employer",
        )

        assert entity.entity_type == "organization"
        assert entity.name == "Acme Corp"
        assert entity.discovered_from == "employer"
        assert entity.relationship_to_subject == "employer"


class TestAssessmentResult:
    """Tests for AssessmentResult dataclass."""

    def test_should_continue_true(self):
        """Test should_continue when conditions are met."""
        result = AssessmentResult(
            info_type=InformationType.EMPLOYMENT,
            iteration_number=1,
            confidence_score=0.70,
            queryable_gaps=2,
        )

        assert result.should_continue is True

    def test_should_continue_false_high_confidence(self):
        """Test should_continue when confidence is high enough."""
        result = AssessmentResult(
            info_type=InformationType.EMPLOYMENT,
            iteration_number=1,
            confidence_score=0.90,
            queryable_gaps=2,
        )

        assert result.should_continue is False

    def test_should_continue_false_no_gaps(self):
        """Test should_continue when no queryable gaps."""
        result = AssessmentResult(
            info_type=InformationType.EMPLOYMENT,
            iteration_number=1,
            confidence_score=0.70,
            queryable_gaps=0,
        )

        assert result.should_continue is False

    def test_should_continue_false_diminishing_returns(self):
        """Test should_continue when info gain is too low."""
        result = AssessmentResult(
            info_type=InformationType.EMPLOYMENT,
            iteration_number=2,
            confidence_score=0.70,
            queryable_gaps=2,
            info_gain_rate=0.05,  # Below 0.1 threshold
        )

        assert result.should_continue is False


class TestResultAssessor:
    """Tests for ResultAssessor class."""

    @pytest.fixture
    def knowledge_base(self):
        """Create a fresh knowledge base."""
        return KnowledgeBase()

    @pytest.fixture
    def assessor(self, knowledge_base):
        """Create a ResultAssessor."""
        return ResultAssessor(knowledge_base=knowledge_base)

    def test_assess_empty_results(self, assessor):
        """Test assessing empty results."""
        assessment = assessor.assess_results(
            info_type=InformationType.IDENTITY,
            results=[],
            iteration_number=1,
        )

        assert assessment.info_type == InformationType.IDENTITY
        assert assessment.iteration_number == 1
        assert assessment.facts_extracted == []
        assert assessment.new_facts_count == 0
        assert assessment.confidence_score == 0.0

    def test_assess_successful_identity_results(self, assessor):
        """Test assessing successful identity query results."""
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.SUCCESS,
                normalized_data={
                    "full_name": "John Smith",
                    "name_variants": ["John Q. Smith", "Johnny Smith"],
                    "date_of_birth": "1990-01-15",
                    "addresses": [{"city": "New York", "state": "NY"}],
                },
            )
        ]

        assessment = assessor.assess_results(
            info_type=InformationType.IDENTITY,
            results=results,
            iteration_number=1,
        )

        assert len(assessment.facts_extracted) > 0
        assert assessment.queries_executed == 1
        assert assessment.queries_successful == 1
        assert assessment.confidence_score > 0.0

    def test_assess_failed_results(self, assessor):
        """Test assessing failed query results."""
        results = [
            QueryResult(
                query_id=uuid7(),
                provider_id="sterling",
                check_type="identity_basic",
                status=QueryStatus.FAILED,
                error_message="Provider error",
            )
        ]

        assessment = assessor.assess_results(
            info_type=InformationType.IDENTITY,
            results=results,
            iteration_number=1,
        )

        assert assessment.facts_extracted == []
        assert assessment.queries_successful == 0
        assert assessment.confidence_factors.query_success == 0.0


class TestFactExtraction:
    """Tests for fact extraction from provider data."""

    @pytest.fixture
    def assessor(self):
        """Create a ResultAssessor."""
        return ResultAssessor(knowledge_base=KnowledgeBase())

    def test_extract_identity_facts(self, assessor):
        """Test extracting identity facts."""
        data = {
            "full_name": "John Smith",
            "name_variants": ["John Q. Smith"],
            "date_of_birth": "1990-01-15",
            "ssn_last4": "1234",
            "addresses": [{"city": "New York"}],
            "phone": "555-123-4567",
        }

        facts = assessor._extract_facts(
            info_type=InformationType.IDENTITY,
            data=data,
            provider_id="sterling",
        )

        fact_types = {f.fact_type for f in facts}
        assert "name_variant" in fact_types
        assert "dob" in fact_types
        assert "ssn_last4" in fact_types
        assert "address" in fact_types
        assert "phone" in fact_types

    def test_extract_employment_facts(self, assessor):
        """Test extracting employment facts."""
        data = {
            "employers": [
                {"name": "Acme Corp", "title": "Engineer", "start_date": "2020-01-01"},
                {"name": "Tech Inc", "title": "Senior Engineer"},
            ],
            "verified": True,
        }

        facts = assessor._extract_facts(
            info_type=InformationType.EMPLOYMENT,
            data=data,
            provider_id="checkr",
        )

        employer_facts = [f for f in facts if f.fact_type == "employer"]
        assert len(employer_facts) == 2

    def test_extract_criminal_facts(self, assessor):
        """Test extracting criminal record facts."""
        data = {
            "records": [
                {"case_type": "misdemeanor", "date": "2015-03-01"},
            ],
        }

        facts = assessor._extract_facts(
            info_type=InformationType.CRIMINAL,
            data=data,
            provider_id="sterling",
        )

        assert len(facts) == 1
        assert facts[0].fact_type == "criminal_record"

    def test_extract_clear_criminal_record(self, assessor):
        """Test extracting clear criminal record."""
        data = {"clear": True}

        facts = assessor._extract_facts(
            info_type=InformationType.CRIMINAL,
            data=data,
            provider_id="sterling",
        )

        assert len(facts) == 1
        assert facts[0].fact_type == "criminal_clear"
        assert facts[0].value is True


class TestGapIdentification:
    """Tests for gap identification logic."""

    @pytest.fixture
    def assessor(self):
        """Create a ResultAssessor."""
        return ResultAssessor(knowledge_base=KnowledgeBase())

    def test_identify_identity_gaps(self, assessor):
        """Test identifying gaps in identity data."""
        # Facts without address
        facts = [
            Fact.create("name_variant", "John Smith", "sterling"),
            Fact.create("dob", "1990-01-15", "sterling"),
        ]

        gaps = assessor._identify_gaps(InformationType.IDENTITY, facts)

        gap_types = {g.gap_type for g in gaps}
        assert "missing_address" in gap_types

    def test_identify_employment_gaps_no_employment(self, assessor):
        """Test identifying employment gap when no employment found."""
        facts = []

        gaps = assessor._identify_gaps(InformationType.EMPLOYMENT, facts)

        gap_types = {g.gap_type for g in gaps}
        assert "no_employment_found" in gap_types

    def test_identify_employment_missing_end_date(self, assessor):
        """Test identifying missing end date gap."""
        facts = [
            Fact.create(
                "employer",
                {"name": "Acme Corp", "start_date": "2020-01-01"},
                "sterling",
            ),
        ]

        gaps = assessor._identify_gaps(InformationType.EMPLOYMENT, facts)

        gap_types = {g.gap_type for g in gaps}
        assert "missing_end_date" in gap_types


class TestInconsistencyDetection:
    """Tests for inconsistency detection."""

    @pytest.fixture
    def assessor(self):
        """Create a ResultAssessor."""
        return ResultAssessor(knowledge_base=KnowledgeBase())

    def test_detect_no_inconsistencies(self, assessor):
        """Test when there are no inconsistencies."""
        facts = [
            Fact.create("name_variant", "John Smith", "sterling"),
            Fact.create("name_variant", "John Smith", "checkr"),
        ]

        inconsistencies = assessor._detect_inconsistencies(InformationType.IDENTITY, facts)

        assert len(inconsistencies) == 0

    def test_detect_name_inconsistency(self, assessor):
        """Test detecting name inconsistency between sources."""
        facts = [
            Fact.create("employer", {"name": "Acme Corp"}, "sterling"),
            Fact.create("employer", {"name": "ACME Corporation"}, "checkr"),
        ]

        inconsistencies = assessor._detect_inconsistencies(InformationType.EMPLOYMENT, facts)

        assert len(inconsistencies) >= 1


class TestEntityDiscovery:
    """Tests for entity discovery."""

    @pytest.fixture
    def assessor(self):
        """Create a ResultAssessor."""
        return ResultAssessor(knowledge_base=KnowledgeBase())

    def test_discover_employer_entity(self, assessor):
        """Test discovering an employer entity."""
        facts = [
            Fact.create("employer", {"name": "Acme Corp"}, "sterling"),
        ]

        entities = assessor._discover_entities(facts)

        assert len(entities) == 1
        assert entities[0].entity_type == "organization"
        assert entities[0].name == "Acme Corp"
        assert entities[0].relationship_to_subject == "employer"

    def test_discover_school_entity(self, assessor):
        """Test discovering a school entity."""
        facts = [
            Fact.create("school", {"name": "MIT"}, "checkr"),
        ]

        entities = assessor._discover_entities(facts)

        assert len(entities) == 1
        assert entities[0].entity_type == "organization"
        assert entities[0].name == "MIT"


class TestKnowledgeBaseUpdate:
    """Tests for knowledge base updates."""

    @pytest.fixture
    def knowledge_base(self):
        """Create a fresh knowledge base."""
        return KnowledgeBase()

    def test_update_with_name_variant(self, knowledge_base):
        """Test updating KB with name variant."""
        assessor = ResultAssessor(knowledge_base=knowledge_base)
        facts = [Fact.create("name_variant", "John Q. Smith", "sterling")]

        assessor._update_knowledge_base(InformationType.IDENTITY, facts)

        assert "John Q. Smith" in knowledge_base.confirmed_names

    def test_update_with_address(self, knowledge_base):
        """Test updating KB with address."""
        assessor = ResultAssessor(knowledge_base=knowledge_base)
        facts = [
            Fact.create(
                "address",
                {"city": "New York", "state": "NY", "county": "New York County"},
                "sterling",
            )
        ]

        assessor._update_knowledge_base(InformationType.IDENTITY, facts)

        assert len(knowledge_base.confirmed_addresses) == 1
        assert "NY" in knowledge_base.known_states
        assert "New York County" in knowledge_base.known_counties


class TestCorroborationCalculation:
    """Tests for corroboration score calculation."""

    @pytest.fixture
    def assessor(self):
        """Create a ResultAssessor."""
        return ResultAssessor(knowledge_base=KnowledgeBase())

    def test_no_corroboration(self, assessor):
        """Test when no facts are corroborated."""
        facts = [
            Fact.create("name_variant", "John Smith", "sterling"),
            Fact.create("name_variant", "Johnny Smith", "checkr"),  # Different value
        ]

        score = assessor._calculate_corroboration(facts)

        assert score == 0.0

    def test_full_corroboration(self, assessor):
        """Test when all facts are corroborated."""
        facts = [
            Fact.create("name_variant", "John Smith", "sterling"),
            Fact.create("name_variant", "John Smith", "checkr"),  # Same value, different source
        ]

        score = assessor._calculate_corroboration(facts)

        assert score == 1.0


class TestFactoryFunction:
    """Tests for create_result_assessor factory."""

    def test_create_assessor(self):
        """Test creating assessor with factory function."""
        kb = KnowledgeBase()
        assessor = create_result_assessor(knowledge_base=kb)

        assert isinstance(assessor, ResultAssessor)
