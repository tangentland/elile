"""Unit tests for the AnomalyDetector."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4, uuid7

import pytest

from elile.agent.state import InconsistencyType
from elile.investigation.finding_extractor import Severity
from elile.investigation.result_assessor import DetectedInconsistency, Fact
from elile.risk.anomaly_detector import (
    ANOMALY_TYPE_SEVERITY,
    DECEPTION_LIKELIHOOD,
    Anomaly,
    AnomalyDetector,
    AnomalyType,
    create_anomaly_detector,
    DeceptionAssessment,
    DetectorConfig,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def detector() -> AnomalyDetector:
    """Create a default anomaly detector."""
    return AnomalyDetector()


@pytest.fixture
def sample_facts() -> list[Fact]:
    """Create sample facts for testing."""
    return [
        Fact.create(
            fact_type="name",
            value="John Smith",
            source_provider="provider_a",
            confidence=0.95,
        ),
        Fact.create(
            fact_type="employer",
            value="Acme Corp",
            source_provider="provider_b",
            confidence=0.85,
        ),
        Fact.create(
            fact_type="education",
            value="Bachelor's Degree",
            source_provider="provider_c",
            confidence=0.9,
        ),
    ]


def create_inconsistency(
    field: str = "employer",
    claimed_value: str = "Acme Corp",
    found_value: str = "Acme Inc",
    inconsistency_type: InconsistencyType = InconsistencyType.EMPLOYER_DISCREPANCY,
    severity: str = "moderate",
    deception_score: float = 0.3,
) -> DetectedInconsistency:
    """Helper to create test inconsistencies."""
    return DetectedInconsistency.create(
        field=field,
        claimed_value=claimed_value,
        found_value=found_value,
        source_a="provider_a",
        source_b="provider_b",
        severity=severity,  # type: ignore
        inconsistency_type=inconsistency_type,
        deception_score=deception_score,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestAnomalyDetectorInit:
    """Tests for AnomalyDetector initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        detector = AnomalyDetector()
        assert detector.config is not None
        assert detector.config.systematic_threshold == 4
        assert detector.config.detect_statistical is True

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = DetectorConfig(systematic_threshold=3, detect_statistical=False)
        detector = AnomalyDetector(config=config)
        assert detector.config.systematic_threshold == 3
        assert detector.config.detect_statistical is False

    def test_factory_function(self) -> None:
        """Test create_anomaly_detector factory."""
        detector = create_anomaly_detector()
        assert isinstance(detector, AnomalyDetector)

    def test_factory_with_config(self) -> None:
        """Test factory with custom config."""
        config = DetectorConfig(systematic_threshold=5)
        detector = create_anomaly_detector(config=config)
        assert detector.config.systematic_threshold == 5


# =============================================================================
# DetectorConfig Tests
# =============================================================================


class TestDetectorConfig:
    """Tests for DetectorConfig validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DetectorConfig()
        assert config.systematic_threshold == 4
        assert config.deception_warning_threshold == 0.5
        assert config.deception_critical_threshold == 0.75
        assert config.statistical_sensitivity == 2.0
        assert config.min_confidence == 0.3

    def test_validation_bounds(self) -> None:
        """Test validation bounds on config values."""
        # Valid config
        config = DetectorConfig(
            systematic_threshold=2,
            deception_warning_threshold=0.0,
            deception_critical_threshold=1.0,
        )
        assert config.systematic_threshold == 2

        # Invalid - threshold too low
        with pytest.raises(ValueError):
            DetectorConfig(systematic_threshold=1)


# =============================================================================
# Anomaly Model Tests
# =============================================================================


class TestAnomalyModel:
    """Tests for Anomaly dataclass."""

    def test_default_values(self) -> None:
        """Test anomaly default values."""
        anomaly = Anomaly()
        assert anomaly.anomaly_type == AnomalyType.UNUSUAL_PATTERN
        assert anomaly.severity == Severity.MEDIUM
        assert anomaly.confidence == 0.5
        assert anomaly.deception_score == 0.0

    def test_to_dict(self) -> None:
        """Test anomaly serialization."""
        anomaly = Anomaly(
            anomaly_type=AnomalyType.CREDENTIAL_INFLATION,
            severity=Severity.HIGH,
            confidence=0.85,
            description="Test anomaly",
            deception_score=0.7,
        )
        result = anomaly.to_dict()

        assert result["anomaly_type"] == "credential_inflation"
        assert result["severity"] == "high"
        assert result["confidence"] == 0.85
        assert result["deception_score"] == 0.7


class TestDeceptionAssessmentModel:
    """Tests for DeceptionAssessment dataclass."""

    def test_default_values(self) -> None:
        """Test deception assessment defaults."""
        assessment = DeceptionAssessment()
        assert assessment.overall_score == 0.0
        assert assessment.risk_level == "none"
        assert assessment.anomaly_count == 0

    def test_to_dict(self) -> None:
        """Test assessment serialization."""
        assessment = DeceptionAssessment(
            overall_score=0.75,
            risk_level="high",
            contributing_factors=["Factor 1"],
            anomaly_count=3,
        )
        result = assessment.to_dict()

        assert result["overall_score"] == 0.75
        assert result["risk_level"] == "high"
        assert len(result["contributing_factors"]) == 1


# =============================================================================
# Statistical Anomaly Detection Tests
# =============================================================================


class TestStatisticalAnomalyDetection:
    """Tests for statistical anomaly detection."""

    def test_no_anomalies_with_normal_data(self, detector: AnomalyDetector) -> None:
        """Test no anomalies detected with normal data."""
        facts = [
            Fact.create("name", "John", "provider_a", 0.9),
            Fact.create("employer", "Acme", "provider_b", 0.85),
        ]
        anomalies = detector._detect_statistical_anomalies(facts)
        # Normal data should have few/no statistical anomalies
        assert len(anomalies) < 2

    def test_unusual_frequency_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of unusual fact frequency."""
        # Create many facts of the same type
        facts = [
            Fact.create("address", f"Address {i}", "provider", 0.8) for i in range(15)
        ]

        anomalies = detector._detect_statistical_anomalies(facts)
        frequency_anomalies = [
            a for a in anomalies if a.anomaly_type == AnomalyType.UNUSUAL_FREQUENCY
        ]

        assert len(frequency_anomalies) >= 1
        assert frequency_anomalies[0].affected_fields == ["address"]

    def test_improbable_value_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of improbable values."""
        facts = [
            Fact.create("years_experience", 100, "provider", 0.5),  # Improbable
        ]

        anomalies = detector._detect_statistical_anomalies(facts)
        improbable = [
            a for a in anomalies if a.anomaly_type == AnomalyType.IMPROBABLE_VALUE
        ]

        # Should detect improbable experience value
        assert len(improbable) >= 1

    def test_low_confidence_fact_flagged(self, detector: AnomalyDetector) -> None:
        """Test that low confidence facts may be flagged."""
        facts = [
            Fact.create("years_experience", 60, "provider", 0.2),  # Low confidence + improbable value
        ]

        anomalies = detector._detect_statistical_anomalies(facts)
        # Low confidence + high value should contribute to improbability
        assert any(a.anomaly_type == AnomalyType.IMPROBABLE_VALUE for a in anomalies)


# =============================================================================
# Inconsistency Pattern Detection Tests
# =============================================================================


class TestInconsistencyPatternDetection:
    """Tests for inconsistency pattern detection."""

    def test_no_patterns_with_few_inconsistencies(
        self, detector: AnomalyDetector
    ) -> None:
        """Test no pattern detected with few inconsistencies."""
        inconsistencies = [create_inconsistency()]
        anomalies = detector._detect_inconsistency_patterns(inconsistencies)

        # Single inconsistency shouldn't trigger systematic pattern
        systematic = [
            a
            for a in anomalies
            if a.anomaly_type == AnomalyType.SYSTEMATIC_INCONSISTENCIES
        ]
        assert len(systematic) == 0

    def test_systematic_pattern_detection(self, detector: AnomalyDetector) -> None:
        """Test systematic pattern detection with 4+ inconsistencies."""
        inconsistencies = [
            create_inconsistency(field="employer"),
            create_inconsistency(field="title"),
            create_inconsistency(field="education"),
            create_inconsistency(field="start_date"),
        ]

        anomalies = detector._detect_inconsistency_patterns(inconsistencies)
        systematic = [
            a
            for a in anomalies
            if a.anomaly_type == AnomalyType.SYSTEMATIC_INCONSISTENCIES
        ]

        assert len(systematic) == 1
        assert systematic[0].severity == Severity.HIGH
        assert systematic[0].deception_score >= 0.5

    def test_cross_field_pattern_detection(self, detector: AnomalyDetector) -> None:
        """Test cross-field pattern detection."""
        inconsistencies = [
            create_inconsistency(field="employer_name"),
            create_inconsistency(field="education_degree"),
            create_inconsistency(field="address_city"),
        ]

        anomalies = detector._detect_inconsistency_patterns(inconsistencies)
        cross_field = [
            a for a in anomalies if a.anomaly_type == AnomalyType.CROSS_FIELD_PATTERN
        ]

        assert len(cross_field) == 1
        assert len(cross_field[0].affected_fields) >= 3

    def test_directional_bias_detection(self, detector: AnomalyDetector) -> None:
        """Test directional bias detection (all errors favor subject)."""
        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.TITLE_MISMATCH
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYMENT_GAP_HIDDEN
            ),
        ]

        anomalies = detector._detect_inconsistency_patterns(inconsistencies)
        directional = [
            a for a in anomalies if a.anomaly_type == AnomalyType.DIRECTIONAL_BIAS
        ]

        assert len(directional) == 1
        assert directional[0].severity == Severity.HIGH


# =============================================================================
# Timeline Anomaly Detection Tests
# =============================================================================


class TestTimelineAnomalyDetection:
    """Tests for timeline anomaly detection."""

    def test_timeline_impossible_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of timeline impossibilities."""
        inconsistencies = [
            create_inconsistency(
                field="start_date",
                claimed_value="2025-01-01",
                found_value="2010-01-01",
                inconsistency_type=InconsistencyType.TIMELINE_IMPOSSIBLE,
            )
        ]

        facts: list[Fact] = []
        anomalies = detector._detect_timeline_anomalies(facts, inconsistencies)

        timeline = [
            a for a in anomalies if a.anomaly_type == AnomalyType.TIMELINE_IMPOSSIBLE
        ]

        assert len(timeline) == 1
        assert timeline[0].severity == Severity.CRITICAL
        assert timeline[0].deception_score >= 0.8

    def test_no_timeline_issues_with_valid_data(
        self, detector: AnomalyDetector
    ) -> None:
        """Test no timeline issues with valid dates."""
        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYER_DISCREPANCY
            )
        ]
        facts: list[Fact] = []
        anomalies = detector._detect_timeline_anomalies(facts, inconsistencies)

        timeline = [
            a for a in anomalies if a.anomaly_type == AnomalyType.TIMELINE_IMPOSSIBLE
        ]
        assert len(timeline) == 0


# =============================================================================
# Credential Anomaly Detection Tests
# =============================================================================


class TestCredentialAnomalyDetection:
    """Tests for credential inflation detection."""

    def test_education_inflation_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of education credential inflation."""
        inconsistencies = [
            create_inconsistency(
                field="degree",
                claimed_value="PhD",
                found_value="Bachelor's",
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED,
            )
        ]

        facts: list[Fact] = []
        anomalies = detector._detect_credential_anomalies(facts, inconsistencies)

        credential = [
            a for a in anomalies if a.anomaly_type == AnomalyType.CREDENTIAL_INFLATION
        ]

        assert len(credential) == 1
        assert credential[0].severity == Severity.HIGH
        assert credential[0].deception_score >= 0.7

    def test_title_inflation_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of title inflation."""
        inconsistencies = [
            create_inconsistency(
                field="job_title",
                claimed_value="Senior Director",
                found_value="Manager",
                inconsistency_type=InconsistencyType.TITLE_MISMATCH,
            )
        ]

        facts: list[Fact] = []
        anomalies = detector._detect_credential_anomalies(facts, inconsistencies)

        experience = [
            a for a in anomalies if a.anomaly_type == AnomalyType.EXPERIENCE_INFLATION
        ]

        assert len(experience) == 1
        assert experience[0].severity == Severity.MEDIUM


# =============================================================================
# Deception Indicator Detection Tests
# =============================================================================


class TestDeceptionIndicatorDetection:
    """Tests for deception indicator detection."""

    def test_employer_fabrication_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of fabricated employers."""
        inconsistencies = [
            create_inconsistency(
                field="employer",
                claimed_value="Fake Company LLC",
                found_value="No record found",
                inconsistency_type=InconsistencyType.EMPLOYER_FABRICATED,
            )
        ]

        facts: list[Fact] = []
        anomalies = detector._detect_deception_indicators(facts, inconsistencies)

        fabrication = [
            a for a in anomalies if a.anomaly_type == AnomalyType.FABRICATION_INDICATOR
        ]

        assert len(fabrication) == 1
        assert fabrication[0].severity == Severity.CRITICAL
        assert fabrication[0].deception_score >= 0.9

    def test_hidden_gap_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of hidden employment gaps."""
        inconsistencies = [
            create_inconsistency(
                field="employment_period",
                claimed_value="2018-2022",
                found_value="2018-2020 (2-year gap)",
                inconsistency_type=InconsistencyType.EMPLOYMENT_GAP_HIDDEN,
            )
        ]

        facts: list[Fact] = []
        anomalies = detector._detect_deception_indicators(facts, inconsistencies)

        concealment = [
            a for a in anomalies if a.anomaly_type == AnomalyType.CONCEALMENT_ATTEMPT
        ]

        assert len(concealment) == 1
        assert concealment[0].severity == Severity.HIGH

    def test_multiple_identities_detection(self, detector: AnomalyDetector) -> None:
        """Test detection of multiple identity indicators."""
        inconsistencies = [
            create_inconsistency(
                field="full_name",
                claimed_value="John Smith",
                found_value="James Wilson",
                inconsistency_type=InconsistencyType.MULTIPLE_IDENTITIES,
            )
        ]

        facts: list[Fact] = []
        anomalies = detector._detect_deception_indicators(facts, inconsistencies)

        deception = [
            a for a in anomalies if a.anomaly_type == AnomalyType.DECEPTION_PATTERN
        ]

        assert len(deception) == 1
        assert deception[0].severity == Severity.CRITICAL
        assert deception[0].deception_score >= 0.9


# =============================================================================
# Full Detection Pipeline Tests
# =============================================================================


class TestFullDetectionPipeline:
    """Tests for the complete detect_anomalies method."""

    def test_empty_input(self, detector: AnomalyDetector) -> None:
        """Test with empty facts and inconsistencies."""
        anomalies = detector.detect_anomalies([], [])
        assert anomalies == []

    def test_mixed_anomalies(
        self, detector: AnomalyDetector, sample_facts: list[Fact]
    ) -> None:
        """Test detection of multiple anomaly types."""
        inconsistencies = [
            create_inconsistency(
                field="degree",
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED,
            ),
            create_inconsistency(
                field="employer",
                inconsistency_type=InconsistencyType.EMPLOYER_FABRICATED,
            ),
        ]

        anomalies = detector.detect_anomalies(sample_facts, inconsistencies)

        # Should detect both credential and deception anomalies
        types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.CREDENTIAL_INFLATION in types
        assert AnomalyType.FABRICATION_INDICATOR in types

    def test_minimum_confidence_filter(self) -> None:
        """Test that low-confidence anomalies are filtered."""
        config = DetectorConfig(min_confidence=0.8)
        detector = AnomalyDetector(config=config)

        # Create low-severity inconsistencies
        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.SPELLING_VARIANT,
                deception_score=0.1,
            )
        ]

        anomalies = detector.detect_anomalies([], inconsistencies)

        # Low-confidence anomalies should be filtered
        assert all(a.confidence >= 0.8 for a in anomalies)

    def test_feature_flags(self) -> None:
        """Test that feature flags control detection."""
        config = DetectorConfig(
            detect_statistical=False,
            detect_timeline=False,
            detect_credential=False,
            detect_deception=False,
        )
        detector = AnomalyDetector(config=config)

        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED,
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.TIMELINE_IMPOSSIBLE,
            ),
        ]

        # Create high-frequency facts
        facts = [Fact.create("test", f"val{i}", "p", 0.9) for i in range(15)]

        anomalies = detector.detect_anomalies(facts, inconsistencies)

        # Only inconsistency patterns should be detected
        types = {a.anomaly_type for a in anomalies}
        assert AnomalyType.STATISTICAL_OUTLIER not in types
        assert AnomalyType.CREDENTIAL_INFLATION not in types


# =============================================================================
# Deception Assessment Tests
# =============================================================================


class TestDeceptionAssessment:
    """Tests for deception assessment."""

    def test_no_deception_with_clean_data(self, detector: AnomalyDetector) -> None:
        """Test low deception score with clean data."""
        assessment = detector.assess_deception([], [])

        assert assessment.overall_score < 0.1
        assert assessment.risk_level == "none"

    def test_high_deception_with_critical_anomalies(
        self, detector: AnomalyDetector
    ) -> None:
        """Test high deception score with critical anomalies."""
        anomalies = [
            Anomaly(
                anomaly_type=AnomalyType.FABRICATION_INDICATOR,
                severity=Severity.CRITICAL,
                deception_score=0.9,
            ),
            Anomaly(
                anomaly_type=AnomalyType.DECEPTION_PATTERN,
                severity=Severity.CRITICAL,
                deception_score=0.85,
            ),
        ]

        assessment = detector.assess_deception(anomalies, [])

        assert assessment.overall_score >= 0.7
        assert assessment.risk_level in ("high", "critical")
        assert len(assessment.contributing_factors) > 0

    def test_deception_from_inconsistencies(self, detector: AnomalyDetector) -> None:
        """Test deception assessment from inconsistencies."""
        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYER_FABRICATED,
                deception_score=0.9,
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED,
                deception_score=0.8,
            ),
        ]

        assessment = detector.assess_deception([], inconsistencies)

        assert assessment.overall_score >= 0.5
        assert assessment.inconsistency_count == 2

    def test_pattern_modifiers(self, detector: AnomalyDetector) -> None:
        """Test pattern modifiers in assessment."""
        # Create inconsistencies with directional bias
        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.TITLE_MISMATCH
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYMENT_GAP_HIDDEN
            ),
        ]

        assessment = detector.assess_deception([], inconsistencies)

        # Should have directional bias modifier
        assert any("bias" in m.lower() for m in assessment.pattern_modifiers)

    def test_risk_level_thresholds(self, detector: AnomalyDetector) -> None:
        """Test risk level determination by score."""
        # Test none level
        assert detector._score_to_risk_level(0.05) == "none"

        # Test low level
        assert detector._score_to_risk_level(0.2) == "low"

        # Test moderate level
        assert detector._score_to_risk_level(0.4) == "moderate"

        # Test high level (above warning threshold)
        assert detector._score_to_risk_level(0.6) == "high"

        # Test critical level (above critical threshold)
        assert detector._score_to_risk_level(0.85) == "critical"


# =============================================================================
# Helper Method Tests
# =============================================================================


class TestHelperMethods:
    """Tests for internal helper methods."""

    def test_has_directional_bias(self, detector: AnomalyDetector) -> None:
        """Test directional bias detection helper."""
        # All inflation types
        inflation_inc = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.TITLE_MISMATCH
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYMENT_GAP_HIDDEN
            ),
        ]
        assert detector._has_directional_bias(inflation_inc) is True

        # Mixed types
        mixed_inc = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EDUCATION_INFLATED
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.SPELLING_VARIANT
            ),
        ]
        assert detector._has_directional_bias(mixed_inc) is False

        # Too few
        assert detector._has_directional_bias([]) is False

    def test_has_cross_domain_pattern(self, detector: AnomalyDetector) -> None:
        """Test cross-domain pattern detection helper."""
        # Multiple domains
        multi_domain = [
            create_inconsistency(field="education_degree"),
            create_inconsistency(field="employer_name"),
            create_inconsistency(field="address_city"),
        ]
        assert detector._has_cross_domain_pattern(multi_domain) is True

        # Single domain
        single_domain = [
            create_inconsistency(field="employer_name"),
            create_inconsistency(field="employer_title"),
        ]
        assert detector._has_cross_domain_pattern(single_domain) is False

    def test_calculate_inconsistency_deception_score(
        self, detector: AnomalyDetector
    ) -> None:
        """Test deception score calculation from inconsistencies."""
        # Empty
        assert detector._calculate_inconsistency_deception_score([]) == 0.0

        # Low severity
        low_inc = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.SPELLING_VARIANT,
                deception_score=0.1,
            )
        ]
        score = detector._calculate_inconsistency_deception_score(low_inc)
        assert score < 0.3

        # High severity
        high_inc = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYER_FABRICATED,
                deception_score=0.9,
            )
        ]
        score = detector._calculate_inconsistency_deception_score(high_inc)
        assert score >= 0.5


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_anomaly_type_severity_mapping(self) -> None:
        """Test all anomaly types have severity mappings."""
        for anomaly_type in AnomalyType:
            assert anomaly_type in ANOMALY_TYPE_SEVERITY

    def test_deception_likelihood_mapping(self) -> None:
        """Test deception likelihood values are valid."""
        for inc_type, likelihood in DECEPTION_LIKELIHOOD.items():
            assert 0.0 <= likelihood <= 1.0

    def test_critical_anomaly_types_are_critical(self) -> None:
        """Test critical anomaly types have critical severity."""
        critical_types = [
            AnomalyType.TIMELINE_IMPOSSIBLE,
            AnomalyType.DECEPTION_PATTERN,
            AnomalyType.FABRICATION_INDICATOR,
        ]
        for anomaly_type in critical_types:
            assert ANOMALY_TYPE_SEVERITY[anomaly_type] == Severity.CRITICAL


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_many_inconsistencies(self, detector: AnomalyDetector) -> None:
        """Test handling of many inconsistencies."""
        inconsistencies = [
            create_inconsistency(field=f"field_{i}") for i in range(20)
        ]

        anomalies = detector.detect_anomalies([], inconsistencies)

        # Should detect systematic pattern
        systematic = [
            a
            for a in anomalies
            if a.anomaly_type == AnomalyType.SYSTEMATIC_INCONSISTENCIES
        ]
        assert len(systematic) >= 1

    def test_mixed_severity_inconsistencies(self, detector: AnomalyDetector) -> None:
        """Test with mixed severity inconsistencies."""
        inconsistencies = [
            create_inconsistency(
                inconsistency_type=InconsistencyType.SPELLING_VARIANT,
                deception_score=0.1,
            ),
            create_inconsistency(
                inconsistency_type=InconsistencyType.EMPLOYER_FABRICATED,
                deception_score=0.9,
            ),
        ]

        anomalies = detector.detect_anomalies([], inconsistencies)
        assessment = detector.assess_deception(anomalies, inconsistencies)

        # Score should be influenced by high-severity
        assert assessment.overall_score >= 0.3

    def test_only_facts_no_inconsistencies(
        self, detector: AnomalyDetector, sample_facts: list[Fact]
    ) -> None:
        """Test with only facts, no inconsistencies."""
        anomalies = detector.detect_anomalies(sample_facts, [])

        # Should still run statistical analysis
        assert isinstance(anomalies, list)

    def test_duplicate_fact_types(self, detector: AnomalyDetector) -> None:
        """Test handling of duplicate fact types."""
        facts = [
            Fact.create("name", "John Smith", "provider_a", 0.9),
            Fact.create("name", "John Q. Smith", "provider_b", 0.85),
            Fact.create("name", "J. Smith", "provider_c", 0.8),
        ]

        anomalies = detector.detect_anomalies(facts, [])

        # Should handle gracefully
        assert isinstance(anomalies, list)
