"""Unit tests for the Delta Detector.

Tests cover:
- Finding comparison (new, resolved, changed)
- Risk score comparison
- Connection comparison
- Escalation detection
- Review requirement detection
- ProfileDelta generation
- Summary generation
"""

from uuid import uuid7

import pytest

from elile.investigation.finding_extractor import (
    DataSourceRef,
    Finding,
    FindingCategory,
    Severity,
)
from elile.monitoring.delta_detector import (
    ConnectionChange,
    DeltaDetector,
    DeltaType,
    DetectorConfig,
    FindingChange,
    RiskScoreChange,
    create_delta_detector,
    severity_rank,
    severity_to_delta_severity,
)
from elile.monitoring.types import DeltaSeverity
from elile.risk.risk_scorer import RiskLevel, RiskScore

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def detector() -> DeltaDetector:
    """Create a delta detector with default config."""
    return create_delta_detector()


@pytest.fixture
def detector_with_detail_tracking() -> DeltaDetector:
    """Create a delta detector that tracks detail changes."""
    return DeltaDetector(config=DetectorConfig(track_detail_changes=True))


def make_finding(
    finding_id=None,
    finding_type: str = "generic",
    category: FindingCategory = FindingCategory.CRIMINAL,
    summary: str = "Test finding",
    details: str = "Test details",
    severity: Severity = Severity.MEDIUM,
    confidence: float = 0.8,
) -> Finding:
    """Helper to create a Finding."""
    return Finding(
        finding_id=finding_id or uuid7(),
        finding_type=finding_type,
        category=category,
        summary=summary,
        details=details,
        severity=severity,
        confidence=confidence,
    )


def make_risk_score(
    overall_score: int = 50,
    risk_level: RiskLevel = RiskLevel.MODERATE,
    category_scores: dict | None = None,
) -> RiskScore:
    """Helper to create a RiskScore."""
    return RiskScore(
        overall_score=overall_score,
        risk_level=risk_level,
        category_scores=category_scores or {},
    )


# =============================================================================
# Basic Tests
# =============================================================================


class TestDeltaDetectorBasic:
    """Basic delta detector tests."""

    def test_create_detector_default_config(self) -> None:
        """Test creating detector with default config."""
        detector = create_delta_detector()
        assert detector is not None
        assert isinstance(detector.config, DetectorConfig)
        assert detector.config.risk_score_threshold == 5

    def test_create_detector_custom_config(self) -> None:
        """Test creating detector with custom config."""
        config = DetectorConfig(risk_score_threshold=10, track_detail_changes=True)
        detector = DeltaDetector(config=config)
        assert detector.config.risk_score_threshold == 10
        assert detector.config.track_detail_changes is True

    def test_no_changes_detected(self, detector: DeltaDetector) -> None:
        """Test when there are no changes."""
        finding = make_finding()
        result = detector.detect_deltas(
            baseline_findings=[finding],
            current_findings=[finding],
        )
        assert result.has_changes is False
        assert result.total_changes == 0
        assert len(result.deltas) == 0
        assert result.summary == "No changes detected"


# =============================================================================
# Finding Comparison Tests
# =============================================================================


class TestFindingComparison:
    """Tests for finding comparison."""

    def test_detect_new_finding(self, detector: DeltaDetector) -> None:
        """Test detecting a new finding."""
        baseline = []
        new_finding = make_finding(summary="New criminal record")
        current = [new_finding]

        result = detector.detect_deltas(
            baseline_findings=baseline,
            current_findings=current,
        )

        assert len(result.new_findings) == 1
        assert result.new_findings[0].finding_id == new_finding.finding_id
        assert result.has_changes is True
        assert "1 new finding" in result.summary

    def test_detect_multiple_new_findings(self, detector: DeltaDetector) -> None:
        """Test detecting multiple new findings."""
        baseline = []
        findings = [
            make_finding(severity=Severity.HIGH, summary="Finding 1"),
            make_finding(severity=Severity.CRITICAL, summary="Finding 2"),
            make_finding(severity=Severity.LOW, summary="Finding 3"),
        ]

        result = detector.detect_deltas(
            baseline_findings=baseline,
            current_findings=findings,
        )

        assert len(result.new_findings) == 3
        assert "3 new finding(s)" in result.summary
        assert "1 critical" in result.summary

    def test_detect_resolved_finding(self, detector: DeltaDetector) -> None:
        """Test detecting a resolved finding."""
        resolved_finding = make_finding(summary="Previously problematic record")
        baseline = [resolved_finding]
        current = []

        result = detector.detect_deltas(
            baseline_findings=baseline,
            current_findings=current,
        )

        assert len(result.resolved_findings) == 1
        assert result.resolved_findings[0].finding_id == resolved_finding.finding_id
        assert "1 resolved finding" in result.summary

    def test_detect_severity_increase(self, detector: DeltaDetector) -> None:
        """Test detecting severity increase."""
        finding_id = uuid7()
        baseline_finding = make_finding(finding_id=finding_id, severity=Severity.LOW)
        current_finding = make_finding(finding_id=finding_id, severity=Severity.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[baseline_finding],
            current_findings=[current_finding],
        )

        assert len(result.changed_findings) == 1
        change = result.changed_findings[0]
        assert change.change_type == DeltaType.FINDING_SEVERITY_INCREASED
        assert change.old_severity == Severity.LOW
        assert change.new_severity == Severity.HIGH
        assert "1 severity increase" in result.summary

    def test_detect_severity_decrease(self, detector: DeltaDetector) -> None:
        """Test detecting severity decrease."""
        finding_id = uuid7()
        baseline_finding = make_finding(finding_id=finding_id, severity=Severity.CRITICAL)
        current_finding = make_finding(finding_id=finding_id, severity=Severity.LOW)

        result = detector.detect_deltas(
            baseline_findings=[baseline_finding],
            current_findings=[current_finding],
        )

        assert len(result.changed_findings) == 1
        change = result.changed_findings[0]
        assert change.change_type == DeltaType.FINDING_SEVERITY_DECREASED
        assert change.old_severity == Severity.CRITICAL
        assert change.new_severity == Severity.LOW
        assert "1 severity decrease" in result.summary

    def test_detect_detail_changes_disabled(self, detector: DeltaDetector) -> None:
        """Test that detail changes are ignored by default."""
        finding_id = uuid7()
        baseline_finding = make_finding(finding_id=finding_id, details="Old details")
        current_finding = make_finding(finding_id=finding_id, details="New details")

        result = detector.detect_deltas(
            baseline_findings=[baseline_finding],
            current_findings=[current_finding],
        )

        assert len(result.changed_findings) == 0
        assert result.has_changes is False

    def test_detect_detail_changes_enabled(
        self, detector_with_detail_tracking: DeltaDetector
    ) -> None:
        """Test that detail changes are tracked when enabled."""
        finding_id = uuid7()
        baseline_finding = make_finding(finding_id=finding_id, details="Old details")
        current_finding = make_finding(finding_id=finding_id, details="New details")

        result = detector_with_detail_tracking.detect_deltas(
            baseline_findings=[baseline_finding],
            current_findings=[current_finding],
        )

        assert len(result.changed_findings) == 1
        change = result.changed_findings[0]
        assert change.change_type == DeltaType.FINDING_DETAILS_CHANGED

    def test_no_change_for_same_finding(self, detector: DeltaDetector) -> None:
        """Test that identical findings don't create changes."""
        finding = make_finding()
        result = detector.detect_deltas(
            baseline_findings=[finding],
            current_findings=[finding],
        )

        assert len(result.new_findings) == 0
        assert len(result.resolved_findings) == 0
        assert len(result.changed_findings) == 0

    def test_complex_finding_changes(self, detector: DeltaDetector) -> None:
        """Test complex scenario with multiple finding changes."""
        # IDs for tracking
        kept_id = uuid7()
        increased_id = uuid7()
        resolved_id = uuid7()

        baseline = [
            make_finding(finding_id=kept_id, severity=Severity.MEDIUM, summary="Kept"),
            make_finding(finding_id=increased_id, severity=Severity.LOW, summary="Increased"),
            make_finding(finding_id=resolved_id, severity=Severity.HIGH, summary="Resolved"),
        ]

        new_finding = make_finding(severity=Severity.CRITICAL, summary="Brand new")
        current = [
            make_finding(finding_id=kept_id, severity=Severity.MEDIUM, summary="Kept"),
            make_finding(finding_id=increased_id, severity=Severity.HIGH, summary="Increased"),
            new_finding,
        ]

        result = detector.detect_deltas(
            baseline_findings=baseline,
            current_findings=current,
        )

        assert len(result.new_findings) == 1
        assert len(result.resolved_findings) == 1
        assert len(result.changed_findings) == 1
        assert result.total_changes == 3


# =============================================================================
# Risk Score Comparison Tests
# =============================================================================


class TestRiskScoreComparison:
    """Tests for risk score comparison."""

    def test_detect_risk_score_increase(self, detector: DeltaDetector) -> None:
        """Test detecting risk score increase."""
        baseline = make_risk_score(overall_score=30, risk_level=RiskLevel.MODERATE)
        current = make_risk_score(overall_score=60, risk_level=RiskLevel.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.risk_score_change is not None
        assert result.risk_score_change.score_change == 30
        assert result.risk_score_change.old_level == RiskLevel.MODERATE
        assert result.risk_score_change.new_level == RiskLevel.HIGH
        assert result.risk_score_change.level_changed is True
        assert "risk score increased by 30" in result.summary

    def test_detect_risk_score_decrease(self, detector: DeltaDetector) -> None:
        """Test detecting risk score decrease."""
        baseline = make_risk_score(overall_score=80, risk_level=RiskLevel.CRITICAL)
        current = make_risk_score(overall_score=40, risk_level=RiskLevel.MODERATE)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.risk_score_change is not None
        assert result.risk_score_change.score_change == -40
        assert result.risk_score_change.level_changed is True
        assert "risk score decreased by 40" in result.summary

    def test_ignore_small_risk_score_change(self, detector: DeltaDetector) -> None:
        """Test that small score changes are ignored."""
        baseline = make_risk_score(overall_score=50, risk_level=RiskLevel.MODERATE)
        current = make_risk_score(overall_score=52, risk_level=RiskLevel.MODERATE)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.risk_score_change is None
        assert result.has_changes is False

    def test_risk_level_change_without_significant_score(self, detector: DeltaDetector) -> None:
        """Test level change detected even with small score change."""
        # Just at the threshold boundary
        baseline = make_risk_score(overall_score=50, risk_level=RiskLevel.MODERATE)
        current = make_risk_score(overall_score=51, risk_level=RiskLevel.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.risk_score_change is not None
        assert result.risk_score_change.level_changed is True

    def test_category_score_changes(self, detector: DeltaDetector) -> None:
        """Test tracking category score changes."""
        baseline = make_risk_score(
            overall_score=30,
            risk_level=RiskLevel.MODERATE,
            category_scores={
                FindingCategory.CRIMINAL: 20,
                FindingCategory.FINANCIAL: 10,
            },
        )
        current = make_risk_score(
            overall_score=50,
            risk_level=RiskLevel.MODERATE,
            category_scores={
                FindingCategory.CRIMINAL: 35,
                FindingCategory.FINANCIAL: 15,
            },
        )

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.risk_score_change is not None
        assert result.risk_score_change.category_changes.get("criminal") == 15
        assert result.risk_score_change.category_changes.get("financial") == 5


# =============================================================================
# Connection Comparison Tests
# =============================================================================


class TestConnectionComparison:
    """Tests for connection comparison."""

    def test_detect_new_connection(self, detector: DeltaDetector) -> None:
        """Test detecting new connections."""
        new_entity_id = uuid7()
        baseline_connections: list[dict] = []
        current_connections = [
            {"entity_id": str(new_entity_id), "name": "New Corp", "risk_level": "high"}
        ]

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_connections=baseline_connections,
            current_connections=current_connections,
        )

        assert len(result.connection_changes) == 1
        change = result.connection_changes[0]
        assert change.change_type == DeltaType.NEW_CONNECTION
        assert change.entity_id == new_entity_id
        assert change.entity_name == "New Corp"
        assert "1 new connection" in result.summary

    def test_detect_lost_connection(self, detector: DeltaDetector) -> None:
        """Test detecting lost connections."""
        lost_entity_id = uuid7()
        baseline_connections = [
            {"entity_id": str(lost_entity_id), "name": "Old Corp", "risk_level": "low"}
        ]
        current_connections: list[dict] = []

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_connections=baseline_connections,
            current_connections=current_connections,
        )

        assert len(result.connection_changes) == 1
        change = result.connection_changes[0]
        assert change.change_type == DeltaType.LOST_CONNECTION
        assert "1 lost connection" in result.summary

    def test_detect_connection_risk_change(self, detector: DeltaDetector) -> None:
        """Test detecting connection risk changes."""
        entity_id = uuid7()
        baseline_connections = [
            {"entity_id": str(entity_id), "name": "Corp X", "risk_score": 0.3}
        ]
        current_connections = [
            {"entity_id": str(entity_id), "name": "Corp X", "risk_score": 0.7}
        ]

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_connections=baseline_connections,
            current_connections=current_connections,
        )

        assert len(result.connection_changes) == 1
        change = result.connection_changes[0]
        assert change.change_type == DeltaType.CONNECTION_RISK_CHANGED

    def test_ignore_small_connection_risk_change(self, detector: DeltaDetector) -> None:
        """Test ignoring small connection risk changes."""
        entity_id = uuid7()
        baseline_connections = [
            {"entity_id": str(entity_id), "name": "Corp X", "risk_score": 0.3}
        ]
        current_connections = [
            {"entity_id": str(entity_id), "name": "Corp X", "risk_score": 0.35}
        ]

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_connections=baseline_connections,
            current_connections=current_connections,
        )

        assert len(result.connection_changes) == 0

    def test_disable_connection_comparison(self) -> None:
        """Test disabling connection comparison."""
        detector = DeltaDetector(config=DetectorConfig(compare_connections=False))
        entity_id = uuid7()
        baseline_connections: list[dict] = []
        current_connections = [{"entity_id": str(entity_id), "name": "New"}]

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_connections=baseline_connections,
            current_connections=current_connections,
        )

        # Should not detect changes when disabled
        assert len(result.connection_changes) == 0


# =============================================================================
# Escalation Tests
# =============================================================================


class TestEscalationDetection:
    """Tests for escalation detection."""

    def test_new_critical_finding_is_escalation(self, detector: DeltaDetector) -> None:
        """Test that new critical finding triggers escalation."""
        critical_finding = make_finding(severity=Severity.CRITICAL)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[critical_finding],
        )

        assert result.has_escalation is True
        assert "[ESCALATION]" in result.summary

    def test_new_high_finding_not_escalation(self, detector: DeltaDetector) -> None:
        """Test that new high finding alone is not escalation."""
        high_finding = make_finding(severity=Severity.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[high_finding],
        )

        assert result.has_escalation is False

    def test_risk_level_increase_is_escalation(self, detector: DeltaDetector) -> None:
        """Test that risk level increase triggers escalation."""
        baseline = make_risk_score(overall_score=30, risk_level=RiskLevel.MODERATE)
        current = make_risk_score(overall_score=60, risk_level=RiskLevel.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.has_escalation is True

    def test_risk_level_decrease_not_escalation(self, detector: DeltaDetector) -> None:
        """Test that risk level decrease is not escalation."""
        baseline = make_risk_score(overall_score=80, risk_level=RiskLevel.CRITICAL)
        current = make_risk_score(overall_score=30, risk_level=RiskLevel.MODERATE)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.has_escalation is False

    def test_severity_increase_to_critical_is_escalation(self, detector: DeltaDetector) -> None:
        """Test that severity increase to critical is escalation."""
        finding_id = uuid7()
        baseline = [make_finding(finding_id=finding_id, severity=Severity.HIGH)]
        current = [make_finding(finding_id=finding_id, severity=Severity.CRITICAL)]

        result = detector.detect_deltas(
            baseline_findings=baseline,
            current_findings=current,
        )

        assert result.has_escalation is True

    def test_disable_critical_finding_escalation(self) -> None:
        """Test disabling critical finding escalation."""
        detector = DeltaDetector(
            config=DetectorConfig(new_critical_finding_is_escalation=False)
        )
        critical_finding = make_finding(severity=Severity.CRITICAL)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[critical_finding],
        )

        assert result.has_escalation is False


# =============================================================================
# Review Required Tests
# =============================================================================


class TestReviewRequired:
    """Tests for review requirement detection."""

    def test_escalation_requires_review(self, detector: DeltaDetector) -> None:
        """Test that escalation always requires review."""
        critical_finding = make_finding(severity=Severity.CRITICAL)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[critical_finding],
        )

        assert result.requires_review is True
        assert "[ESCALATION]" in result.summary

    def test_new_high_finding_requires_review(self, detector: DeltaDetector) -> None:
        """Test that new high finding requires review."""
        high_finding = make_finding(severity=Severity.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[high_finding],
        )

        assert result.requires_review is True
        assert "[REVIEW REQUIRED]" in result.summary

    def test_new_low_finding_no_review(self, detector: DeltaDetector) -> None:
        """Test that new low finding doesn't require review."""
        low_finding = make_finding(severity=Severity.LOW)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[low_finding],
        )

        assert result.requires_review is False
        assert "[REVIEW" not in result.summary

    def test_significant_risk_increase_requires_review(self, detector: DeltaDetector) -> None:
        """Test that significant risk increase requires review."""
        baseline = make_risk_score(overall_score=30, risk_level=RiskLevel.MODERATE)
        current = make_risk_score(overall_score=55, risk_level=RiskLevel.MODERATE)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        assert result.requires_review is True

    def test_disable_high_finding_review(self) -> None:
        """Test disabling high finding review requirement."""
        detector = DeltaDetector(
            config=DetectorConfig(new_high_finding_requires_review=False)
        )
        high_finding = make_finding(severity=Severity.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[high_finding],
        )

        assert result.requires_review is False


# =============================================================================
# ProfileDelta Generation Tests
# =============================================================================


class TestProfileDeltaGeneration:
    """Tests for ProfileDelta generation."""

    def test_generate_delta_for_new_finding(self, detector: DeltaDetector) -> None:
        """Test generating ProfileDelta for new finding."""
        source = DataSourceRef(provider_id="sterling", provider_name="Sterling")
        new_finding = make_finding(
            severity=Severity.HIGH,
            category=FindingCategory.CRIMINAL,
            summary="New criminal record",
        )
        new_finding.sources = [source]

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[new_finding],
        )

        assert len(result.deltas) == 1
        delta = result.deltas[0]
        assert delta.delta_type == DeltaType.NEW_FINDING.value
        assert delta.category == "criminal"
        assert delta.severity == DeltaSeverity.HIGH
        assert "New finding" in delta.description
        assert delta.source_provider == "sterling"

    def test_generate_delta_for_resolved_finding(self, detector: DeltaDetector) -> None:
        """Test generating ProfileDelta for resolved finding."""
        resolved_finding = make_finding(
            severity=Severity.HIGH,
            summary="Resolved issue",
        )

        result = detector.detect_deltas(
            baseline_findings=[resolved_finding],
            current_findings=[],
        )

        assert len(result.deltas) == 1
        delta = result.deltas[0]
        assert delta.delta_type == DeltaType.RESOLVED_FINDING.value
        assert delta.severity == DeltaSeverity.POSITIVE
        assert delta.requires_review is False

    def test_generate_delta_for_severity_change(self, detector: DeltaDetector) -> None:
        """Test generating ProfileDelta for severity change."""
        finding_id = uuid7()
        baseline = [make_finding(finding_id=finding_id, severity=Severity.LOW)]
        current = [make_finding(finding_id=finding_id, severity=Severity.CRITICAL)]

        result = detector.detect_deltas(
            baseline_findings=baseline,
            current_findings=current,
        )

        deltas = [d for d in result.deltas if d.delta_type == DeltaType.FINDING_SEVERITY_INCREASED.value]
        assert len(deltas) == 1
        assert deltas[0].severity == DeltaSeverity.CRITICAL

    def test_generate_delta_for_risk_score(self, detector: DeltaDetector) -> None:
        """Test generating ProfileDelta for risk score change."""
        baseline = make_risk_score(overall_score=30, risk_level=RiskLevel.MODERATE)
        current = make_risk_score(overall_score=80, risk_level=RiskLevel.CRITICAL)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_risk_score=baseline,
            current_risk_score=current,
        )

        risk_deltas = [d for d in result.deltas if d.category == "risk_score"]
        assert len(risk_deltas) == 1
        assert risk_deltas[0].severity == DeltaSeverity.CRITICAL

    def test_generate_delta_for_new_connection(self, detector: DeltaDetector) -> None:
        """Test generating ProfileDelta for new connection."""
        entity_id = uuid7()
        current_connections = [
            {"entity_id": str(entity_id), "name": "High Risk Corp", "risk_level": "high"}
        ]

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
            baseline_connections=[],
            current_connections=current_connections,
        )

        conn_deltas = [d for d in result.deltas if d.category == "connection"]
        assert len(conn_deltas) == 1
        assert conn_deltas[0].severity == DeltaSeverity.HIGH


# =============================================================================
# Helper Function Tests
# =============================================================================


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_severity_rank(self) -> None:
        """Test severity ranking."""
        assert severity_rank(Severity.LOW) < severity_rank(Severity.MEDIUM)
        assert severity_rank(Severity.MEDIUM) < severity_rank(Severity.HIGH)
        assert severity_rank(Severity.HIGH) < severity_rank(Severity.CRITICAL)

    def test_severity_to_delta_severity(self) -> None:
        """Test severity to delta severity conversion."""
        assert severity_to_delta_severity(Severity.LOW) == DeltaSeverity.LOW
        assert severity_to_delta_severity(Severity.MEDIUM) == DeltaSeverity.MEDIUM
        assert severity_to_delta_severity(Severity.HIGH) == DeltaSeverity.HIGH
        assert severity_to_delta_severity(Severity.CRITICAL) == DeltaSeverity.CRITICAL


# =============================================================================
# Data Class Tests
# =============================================================================


class TestDataClasses:
    """Tests for data classes."""

    def test_delta_result_to_dict(self, detector: DeltaDetector) -> None:
        """Test DeltaResult serialization."""
        finding = make_finding(severity=Severity.HIGH)

        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[finding],
        )

        data = result.to_dict()
        assert "result_id" in data
        assert "new_findings" in data
        assert len(data["new_findings"]) == 1
        assert data["has_changes"] is True
        assert data["total_changes"] == 1

    def test_finding_change_to_dict(self) -> None:
        """Test FindingChange serialization."""
        change = FindingChange(
            finding_id=uuid7(),
            change_type=DeltaType.FINDING_SEVERITY_INCREASED,
            old_severity=Severity.LOW,
            new_severity=Severity.HIGH,
            description="Test change",
        )

        data = change.to_dict()
        assert data["change_type"] == "finding_severity_increased"
        assert data["old_severity"] == "low"
        assert data["new_severity"] == "high"

    def test_connection_change_to_dict(self) -> None:
        """Test ConnectionChange serialization."""
        change = ConnectionChange(
            entity_id=uuid7(),
            change_type=DeltaType.NEW_CONNECTION,
            entity_name="Test Corp",
            new_risk_level="high",
            description="New connection",
        )

        data = change.to_dict()
        assert data["change_type"] == "new_connection"
        assert data["entity_name"] == "Test Corp"

    def test_risk_score_change_to_dict(self) -> None:
        """Test RiskScoreChange serialization."""
        change = RiskScoreChange(
            old_score=30,
            new_score=60,
            score_change=30,
            old_level=RiskLevel.MODERATE,
            new_level=RiskLevel.HIGH,
            level_changed=True,
            category_changes={"criminal": 20},
        )

        data = change.to_dict()
        assert data["old_score"] == 30
        assert data["new_score"] == 60
        assert data["level_changed"] is True
        assert data["category_changes"]["criminal"] == 20


# =============================================================================
# Configuration Tests
# =============================================================================


class TestDetectorConfig:
    """Tests for detector configuration."""

    def test_default_config_values(self) -> None:
        """Test default configuration values."""
        config = DetectorConfig()
        assert config.risk_score_threshold == 5
        assert config.risk_level_change_is_escalation is True
        assert config.new_critical_finding_is_escalation is True
        assert config.new_high_finding_requires_review is True
        assert config.track_detail_changes is False
        assert config.compare_connections is True
        assert config.connection_risk_threshold == 0.2

    def test_custom_config_values(self) -> None:
        """Test custom configuration values."""
        config = DetectorConfig(
            risk_score_threshold=10,
            track_detail_changes=True,
            connection_risk_threshold=0.5,
        )
        assert config.risk_score_threshold == 10
        assert config.track_detail_changes is True
        assert config.connection_risk_threshold == 0.5

    def test_config_validation(self) -> None:
        """Test configuration validation."""
        # Risk threshold bounds
        with pytest.raises(ValueError):
            DetectorConfig(risk_score_threshold=0)

        with pytest.raises(ValueError):
            DetectorConfig(risk_score_threshold=100)

        # Connection risk threshold bounds
        with pytest.raises(ValueError):
            DetectorConfig(connection_risk_threshold=-0.1)

        with pytest.raises(ValueError):
            DetectorConfig(connection_risk_threshold=1.5)


# =============================================================================
# Integration-Like Tests
# =============================================================================


class TestIntegrationScenarios:
    """Integration-like tests for realistic scenarios."""

    def test_full_monitoring_check_scenario(self, detector: DeltaDetector) -> None:
        """Test a realistic full monitoring check scenario."""
        # Baseline: 2 findings, moderate risk
        baseline_findings = [
            make_finding(
                finding_id=uuid7(),
                summary="Old bankruptcy",
                category=FindingCategory.FINANCIAL,
                severity=Severity.MEDIUM,
            ),
            make_finding(
                finding_id=uuid7(),
                summary="Traffic violation",
                category=FindingCategory.CRIMINAL,
                severity=Severity.LOW,
            ),
        ]
        baseline_risk = make_risk_score(overall_score=35, risk_level=RiskLevel.MODERATE)
        baseline_connections = [
            {"entity_id": str(uuid7()), "name": "Former Employer", "risk_score": 0.1}
        ]

        # Current: resolve one, add one, risk increases
        new_finding = make_finding(
            summary="New felony",
            category=FindingCategory.CRIMINAL,
            severity=Severity.CRITICAL,
        )
        current_findings = [
            baseline_findings[0],  # Keep bankruptcy
            new_finding,  # New felony
            # Traffic violation resolved
        ]
        current_risk = make_risk_score(overall_score=75, risk_level=RiskLevel.HIGH)
        new_connection_id = uuid7()
        current_connections = [
            baseline_connections[0],  # Keep former employer
            {"entity_id": str(new_connection_id), "name": "Suspicious LLC", "risk_level": "high"},
        ]

        result = detector.detect_deltas(
            baseline_findings=baseline_findings,
            current_findings=current_findings,
            baseline_risk_score=baseline_risk,
            current_risk_score=current_risk,
            baseline_connections=baseline_connections,
            current_connections=current_connections,
        )

        # Should detect all changes
        assert len(result.new_findings) == 1
        assert len(result.resolved_findings) == 1
        assert result.risk_score_change is not None
        assert result.risk_score_change.score_change == 40
        assert len(result.connection_changes) == 1

        # Should have escalation due to critical finding
        assert result.has_escalation is True
        assert result.requires_review is True

        # Should generate multiple deltas
        assert len(result.deltas) >= 3  # new finding, resolved, risk, connection

    def test_empty_profiles_no_changes(self, detector: DeltaDetector) -> None:
        """Test comparing empty profiles."""
        result = detector.detect_deltas(
            baseline_findings=[],
            current_findings=[],
        )

        assert result.has_changes is False
        assert result.total_changes == 0
        assert result.summary == "No changes detected"

    def test_large_number_of_findings(self, detector: DeltaDetector) -> None:
        """Test performance with many findings."""
        # Create 100 baseline findings
        baseline_findings = [
            make_finding(finding_id=uuid7(), summary=f"Finding {i}")
            for i in range(100)
        ]

        # Remove 10, add 20 new, change 5 severities
        kept_ids = [f.finding_id for f in baseline_findings[10:95]]  # Keep 85
        changed_ids = [f.finding_id for f in baseline_findings[95:100]]  # Change 5

        current_findings = [
            make_finding(finding_id=fid, summary=f"Kept {i}")
            for i, fid in enumerate(kept_ids)
        ]
        current_findings.extend([
            make_finding(
                finding_id=fid,
                severity=Severity.HIGH,  # Changed from default MEDIUM
                summary=f"Changed {i}",
            )
            for i, fid in enumerate(changed_ids)
        ])
        current_findings.extend([
            make_finding(summary=f"New finding {i}")
            for i in range(20)
        ])

        result = detector.detect_deltas(
            baseline_findings=baseline_findings,
            current_findings=current_findings,
        )

        assert len(result.new_findings) == 20
        assert len(result.resolved_findings) == 10
        assert len(result.changed_findings) == 5
        assert result.total_changes == 35
