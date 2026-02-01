"""Unit tests for the PatternRecognizer."""

from datetime import date, timedelta
from uuid import uuid7

import pytest

from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.pattern_recognizer import (
    create_pattern_recognizer,
    Pattern,
    PatternRecognizer,
    PatternSummary,
    PatternType,
    RecognizerConfig,
    SEVERITY_RANK,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def recognizer() -> PatternRecognizer:
    """Create a default pattern recognizer."""
    return PatternRecognizer()


def create_finding(
    summary: str = "Test finding",
    severity: Severity = Severity.MEDIUM,
    category: FindingCategory | None = None,
    finding_date: date | None = None,
    finding_type: str | None = None,
) -> Finding:
    """Helper to create test findings."""
    return Finding(
        finding_id=uuid7(),
        summary=summary,
        severity=severity,
        category=category,
        finding_date=finding_date,
        finding_type=finding_type,
    )


# =============================================================================
# Initialization Tests
# =============================================================================


class TestPatternRecognizerInit:
    """Tests for PatternRecognizer initialization."""

    def test_init_default_config(self) -> None:
        """Test initialization with default config."""
        recognizer = PatternRecognizer()
        assert recognizer.config is not None
        assert recognizer.config.escalation_window_days == 365

    def test_init_custom_config(self) -> None:
        """Test initialization with custom config."""
        config = RecognizerConfig(escalation_window_days=180, burst_threshold=5)
        recognizer = PatternRecognizer(config=config)
        assert recognizer.config.escalation_window_days == 180
        assert recognizer.config.burst_threshold == 5

    def test_factory_function(self) -> None:
        """Test create_pattern_recognizer factory."""
        recognizer = create_pattern_recognizer()
        assert isinstance(recognizer, PatternRecognizer)

    def test_factory_with_config(self) -> None:
        """Test factory with custom config."""
        config = RecognizerConfig(min_confidence=0.5)
        recognizer = create_pattern_recognizer(config=config)
        assert recognizer.config.min_confidence == 0.5


# =============================================================================
# RecognizerConfig Tests
# =============================================================================


class TestRecognizerConfig:
    """Tests for RecognizerConfig validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = RecognizerConfig()
        assert config.escalation_window_days == 365
        assert config.min_findings_for_escalation == 3
        assert config.burst_window_days == 90
        assert config.burst_threshold == 3
        assert config.min_categories_for_multi == 3
        assert config.recent_days == 180

    def test_validation_bounds(self) -> None:
        """Test validation bounds on config values."""
        # Valid config
        config = RecognizerConfig(
            escalation_window_days=30,
            burst_window_days=7,
        )
        assert config.escalation_window_days == 30

        # Invalid - too low
        with pytest.raises(ValueError):
            RecognizerConfig(escalation_window_days=10)


# =============================================================================
# Pattern Model Tests
# =============================================================================


class TestPatternModel:
    """Tests for Pattern dataclass."""

    def test_default_values(self) -> None:
        """Test pattern default values."""
        pattern = Pattern()
        assert pattern.pattern_type == PatternType.MULTI_CATEGORY
        assert pattern.severity == Severity.MEDIUM
        assert pattern.confidence == 0.5

    def test_to_dict(self) -> None:
        """Test pattern serialization."""
        pattern = Pattern(
            pattern_type=PatternType.SEVERITY_ESCALATION,
            severity=Severity.HIGH,
            confidence=0.85,
            description="Test pattern",
            time_span=timedelta(days=90),
        )
        result = pattern.to_dict()

        assert result["pattern_type"] == "severity_escalation"
        assert result["severity"] == "high"
        assert result["confidence"] == 0.85
        assert result["time_span_days"] == 90


class TestPatternSummaryModel:
    """Tests for PatternSummary dataclass."""

    def test_default_values(self) -> None:
        """Test summary default values."""
        summary = PatternSummary()
        assert summary.total_patterns == 0
        assert summary.risk_score == 0.0

    def test_to_dict(self) -> None:
        """Test summary serialization."""
        summary = PatternSummary(
            total_patterns=3,
            risk_score=0.65,
            key_concerns=["Concern 1"],
        )
        result = summary.to_dict()

        assert result["total_patterns"] == 3
        assert result["risk_score"] == 0.65


# =============================================================================
# Escalation Pattern Tests
# =============================================================================


class TestEscalationPatterns:
    """Tests for escalation pattern detection."""

    def test_no_escalation_with_few_findings(
        self, recognizer: PatternRecognizer
    ) -> None:
        """Test no escalation with insufficient findings."""
        findings = [create_finding()]
        patterns = recognizer._detect_escalation_patterns(findings)
        assert len(patterns) == 0

    def test_no_escalation_without_dates(self, recognizer: PatternRecognizer) -> None:
        """Test no escalation without dated findings."""
        findings = [create_finding() for _ in range(5)]
        patterns = recognizer._detect_escalation_patterns(findings)
        assert len(patterns) == 0

    def test_severity_escalation_detection(
        self, recognizer: PatternRecognizer
    ) -> None:
        """Test detection of severity escalation."""
        today = date.today()
        findings = [
            # Early low severity
            create_finding(
                severity=Severity.LOW,
                finding_date=today - timedelta(days=180),
            ),
            create_finding(
                severity=Severity.LOW,
                finding_date=today - timedelta(days=150),
            ),
            # Later high severity
            create_finding(
                severity=Severity.HIGH,
                finding_date=today - timedelta(days=60),
            ),
            create_finding(
                severity=Severity.CRITICAL,
                finding_date=today - timedelta(days=30),
            ),
        ]

        patterns = recognizer._detect_escalation_patterns(findings)
        escalation = [
            p for p in patterns if p.pattern_type == PatternType.SEVERITY_ESCALATION
        ]

        assert len(escalation) == 1
        assert escalation[0].severity == Severity.HIGH

    def test_no_severity_escalation_when_stable(
        self, recognizer: PatternRecognizer
    ) -> None:
        """Test no escalation when severity is stable."""
        today = date.today()
        findings = [
            create_finding(
                severity=Severity.MEDIUM,
                finding_date=today - timedelta(days=i * 30),
            )
            for i in range(5)
        ]

        patterns = recognizer._detect_escalation_patterns(findings)
        escalation = [
            p for p in patterns if p.pattern_type == PatternType.SEVERITY_ESCALATION
        ]

        assert len(escalation) == 0


# =============================================================================
# Frequency Pattern Tests
# =============================================================================


class TestFrequencyPatterns:
    """Tests for frequency pattern detection."""

    def test_burst_activity_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of burst activity."""
        today = date.today()
        findings = [
            create_finding(finding_date=today - timedelta(days=10)),
            create_finding(finding_date=today - timedelta(days=20)),
            create_finding(finding_date=today - timedelta(days=30)),
            create_finding(finding_date=today - timedelta(days=40)),
        ]

        patterns = recognizer._detect_frequency_patterns(findings)
        burst = [p for p in patterns if p.pattern_type == PatternType.BURST_ACTIVITY]

        assert len(burst) == 1
        assert burst[0].severity == Severity.MEDIUM

    def test_no_burst_with_old_findings(self, recognizer: PatternRecognizer) -> None:
        """Test no burst when findings are old."""
        today = date.today()
        findings = [
            create_finding(finding_date=today - timedelta(days=200)),
            create_finding(finding_date=today - timedelta(days=250)),
            create_finding(finding_date=today - timedelta(days=300)),
        ]

        patterns = recognizer._detect_frequency_patterns(findings)
        burst = [p for p in patterns if p.pattern_type == PatternType.BURST_ACTIVITY]

        assert len(burst) == 0

    def test_recurring_issues_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of recurring issues."""
        findings = [
            create_finding(finding_type="dui_conviction"),
            create_finding(finding_type="dui_conviction"),
            create_finding(finding_type="dui_conviction"),
        ]

        patterns = recognizer._detect_frequency_patterns(findings)
        recurring = [
            p for p in patterns if p.pattern_type == PatternType.RECURRING_ISSUES
        ]

        assert len(recurring) == 1
        assert recurring[0].severity == Severity.HIGH


# =============================================================================
# Cross-Domain Pattern Tests
# =============================================================================


class TestCrossDomainPatterns:
    """Tests for cross-domain pattern detection."""

    def test_multi_category_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of multi-category pattern."""
        findings = [
            create_finding(category=FindingCategory.CRIMINAL),
            create_finding(category=FindingCategory.FINANCIAL),
            create_finding(category=FindingCategory.REGULATORY),
            create_finding(category=FindingCategory.VERIFICATION),
        ]

        patterns = recognizer._detect_cross_domain_patterns(findings)
        multi = [p for p in patterns if p.pattern_type == PatternType.MULTI_CATEGORY]

        assert len(multi) == 1
        assert len(multi[0].affected_categories) >= 3

    def test_no_multi_category_with_single_category(
        self, recognizer: PatternRecognizer
    ) -> None:
        """Test no multi-category with single category."""
        findings = [
            create_finding(category=FindingCategory.CRIMINAL),
            create_finding(category=FindingCategory.CRIMINAL),
        ]

        patterns = recognizer._detect_cross_domain_patterns(findings)
        multi = [p for p in patterns if p.pattern_type == PatternType.MULTI_CATEGORY]

        assert len(multi) == 0

    def test_systemic_issues_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of systemic issues."""
        findings = [
            create_finding(severity=Severity.HIGH),
            create_finding(severity=Severity.CRITICAL),
            create_finding(severity=Severity.HIGH),
            create_finding(severity=Severity.CRITICAL),
            create_finding(severity=Severity.HIGH),
        ]

        patterns = recognizer._detect_cross_domain_patterns(findings)
        systemic = [p for p in patterns if p.pattern_type == PatternType.SYSTEMIC_ISSUES]

        assert len(systemic) == 1


# =============================================================================
# Temporal Pattern Tests
# =============================================================================


class TestTemporalPatterns:
    """Tests for temporal pattern detection."""

    def test_recent_concentration_detection(
        self, recognizer: PatternRecognizer
    ) -> None:
        """Test detection of recent concentration."""
        today = date.today()
        findings = [
            # One old finding
            create_finding(finding_date=today - timedelta(days=365)),
            # Many recent findings
            create_finding(finding_date=today - timedelta(days=30)),
            create_finding(finding_date=today - timedelta(days=60)),
            create_finding(finding_date=today - timedelta(days=90)),
        ]

        patterns = recognizer._detect_temporal_patterns(findings)
        recent = [
            p for p in patterns if p.pattern_type == PatternType.RECENT_CONCENTRATION
        ]

        assert len(recent) == 1

    def test_timeline_cluster_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of timeline clusters."""
        today = date.today()
        findings = [
            # Tightly clustered together (small gaps: 5, 5, 5 days)
            create_finding(finding_date=today - timedelta(days=100)),
            create_finding(finding_date=today - timedelta(days=105)),
            create_finding(finding_date=today - timedelta(days=110)),
            create_finding(finding_date=today - timedelta(days=115)),
            # Big gap (185 days, which is > 3x the 5-day average)
            create_finding(finding_date=today - timedelta(days=300)),
        ]

        patterns = recognizer._detect_temporal_patterns(findings)
        cluster = [
            p for p in patterns if p.pattern_type == PatternType.TIMELINE_CLUSTER
        ]

        # The test checks if clustering pattern is detected when
        # there are tight clusters with large gaps between them
        assert len(cluster) == 1


# =============================================================================
# Behavioral Pattern Tests
# =============================================================================


class TestBehavioralPatterns:
    """Tests for behavioral pattern detection."""

    def test_repeat_offender_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of repeat offender pattern."""
        findings = [
            create_finding(category=FindingCategory.CRIMINAL, severity=Severity.HIGH),
            create_finding(category=FindingCategory.CRIMINAL, severity=Severity.HIGH),
            create_finding(category=FindingCategory.CRIMINAL, severity=Severity.CRITICAL),
        ]

        patterns = recognizer._detect_behavioral_patterns(findings)
        repeat = [p for p in patterns if p.pattern_type == PatternType.REPEAT_OFFENDER]

        assert len(repeat) == 1
        assert repeat[0].severity == Severity.HIGH

    def test_progressive_degradation_detection(
        self, recognizer: PatternRecognizer
    ) -> None:
        """Test detection of progressive degradation."""
        today = date.today()
        findings = [
            # Early low severity
            create_finding(
                severity=Severity.LOW, finding_date=today - timedelta(days=300)
            ),
            create_finding(
                severity=Severity.LOW, finding_date=today - timedelta(days=250)
            ),
            # Middle medium
            create_finding(
                severity=Severity.MEDIUM, finding_date=today - timedelta(days=150)
            ),
            # Recent high
            create_finding(
                severity=Severity.HIGH, finding_date=today - timedelta(days=50)
            ),
            create_finding(
                severity=Severity.CRITICAL, finding_date=today - timedelta(days=20)
            ),
        ]

        patterns = recognizer._detect_behavioral_patterns(findings)
        degradation = [
            p for p in patterns if p.pattern_type == PatternType.PROGRESSIVE_DEGRADATION
        ]

        assert len(degradation) == 1

    def test_improvement_trend_detection(self, recognizer: PatternRecognizer) -> None:
        """Test detection of improvement trend."""
        today = date.today()
        findings = [
            # Early high severity
            create_finding(
                severity=Severity.HIGH, finding_date=today - timedelta(days=300)
            ),
            create_finding(
                severity=Severity.CRITICAL, finding_date=today - timedelta(days=250)
            ),
            # Recent low
            create_finding(
                severity=Severity.LOW, finding_date=today - timedelta(days=50)
            ),
            create_finding(
                severity=Severity.LOW, finding_date=today - timedelta(days=20)
            ),
        ]

        patterns = recognizer._detect_behavioral_patterns(findings)
        improvement = [
            p for p in patterns if p.pattern_type == PatternType.IMPROVEMENT_TREND
        ]

        assert len(improvement) == 1


# =============================================================================
# Full Recognition Pipeline Tests
# =============================================================================


class TestFullRecognitionPipeline:
    """Tests for the complete recognize_patterns method."""

    def test_empty_input(self, recognizer: PatternRecognizer) -> None:
        """Test with empty findings."""
        patterns = recognizer.recognize_patterns([])
        assert patterns == []

    def test_mixed_patterns(self, recognizer: PatternRecognizer) -> None:
        """Test detection of multiple pattern types."""
        today = date.today()
        findings = [
            create_finding(
                category=FindingCategory.CRIMINAL,
                severity=Severity.LOW,
                finding_date=today - timedelta(days=200),
            ),
            create_finding(
                category=FindingCategory.FINANCIAL,
                severity=Severity.MEDIUM,
                finding_date=today - timedelta(days=100),
            ),
            create_finding(
                category=FindingCategory.REGULATORY,
                severity=Severity.HIGH,
                finding_date=today - timedelta(days=50),
            ),
            create_finding(
                category=FindingCategory.VERIFICATION,
                severity=Severity.HIGH,
                finding_date=today - timedelta(days=30),
            ),
        ]

        patterns = recognizer.recognize_patterns(findings)

        # Should detect multiple pattern types
        types = {p.pattern_type for p in patterns}
        # At least multi-category should be detected
        assert PatternType.MULTI_CATEGORY in types

    def test_minimum_confidence_filter(self) -> None:
        """Test that low-confidence patterns are filtered."""
        config = RecognizerConfig(min_confidence=0.9)
        recognizer = PatternRecognizer(config=config)

        findings = [
            create_finding(category=FindingCategory.CRIMINAL),
            create_finding(category=FindingCategory.FINANCIAL),
            create_finding(category=FindingCategory.REGULATORY),
        ]

        patterns = recognizer.recognize_patterns(findings)

        # All should have confidence >= 0.9
        assert all(p.confidence >= 0.9 for p in patterns)


# =============================================================================
# Summary Tests
# =============================================================================


class TestPatternSummary:
    """Tests for pattern summarization."""

    def test_empty_patterns(self, recognizer: PatternRecognizer) -> None:
        """Test summary with no patterns."""
        summary = recognizer.summarize_patterns([], [])

        assert summary.total_patterns == 0
        assert summary.risk_score == 0.0
        assert summary.highest_severity is None

    def test_summary_calculation(self, recognizer: PatternRecognizer) -> None:
        """Test summary with patterns."""
        patterns = [
            Pattern(
                pattern_type=PatternType.SEVERITY_ESCALATION,
                severity=Severity.HIGH,
                confidence=0.8,
            ),
            Pattern(
                pattern_type=PatternType.MULTI_CATEGORY,
                severity=Severity.MEDIUM,
                confidence=0.7,
            ),
        ]

        findings = [create_finding() for _ in range(5)]

        summary = recognizer.summarize_patterns(patterns, findings)

        assert summary.total_patterns == 2
        assert summary.highest_severity == Severity.HIGH
        assert summary.risk_score > 0
        assert summary.analyzed_findings == 5


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_severity_rank_mapping(self) -> None:
        """Test all severities have ranks."""
        for severity in Severity:
            assert severity in SEVERITY_RANK

    def test_severity_rank_ordering(self) -> None:
        """Test severity ranks are ordered correctly."""
        assert SEVERITY_RANK[Severity.LOW] < SEVERITY_RANK[Severity.MEDIUM]
        assert SEVERITY_RANK[Severity.MEDIUM] < SEVERITY_RANK[Severity.HIGH]
        assert SEVERITY_RANK[Severity.HIGH] < SEVERITY_RANK[Severity.CRITICAL]


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_single_finding(self, recognizer: PatternRecognizer) -> None:
        """Test with single finding."""
        findings = [create_finding()]
        patterns = recognizer.recognize_patterns(findings)
        # Should not crash, may have no patterns
        assert isinstance(patterns, list)

    def test_findings_without_categories(self, recognizer: PatternRecognizer) -> None:
        """Test with findings lacking categories."""
        findings = [create_finding(category=None) for _ in range(5)]
        patterns = recognizer.recognize_patterns(findings)
        assert isinstance(patterns, list)

    def test_findings_same_date(self, recognizer: PatternRecognizer) -> None:
        """Test with all findings on same date."""
        today = date.today()
        findings = [
            create_finding(finding_date=today, severity=Severity.HIGH)
            for _ in range(5)
        ]
        patterns = recognizer.recognize_patterns(findings)
        assert isinstance(patterns, list)

    def test_many_findings(self, recognizer: PatternRecognizer) -> None:
        """Test with many findings."""
        today = date.today()
        findings = [
            create_finding(
                finding_date=today - timedelta(days=i * 10),
                severity=Severity.MEDIUM,
                category=FindingCategory.CRIMINAL,
            )
            for i in range(20)
        ]
        patterns = recognizer.recognize_patterns(findings)

        # Should detect patterns without error
        assert len(patterns) >= 1  # At least recurring issues
