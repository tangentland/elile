"""Tests for the Temporal Risk Tracker.

Tests cover:
- Risk delta calculation
- Evolution signal detection
- Trend analysis
- Spike detection
- Level transition detection
- Category change detection
- Threshold alerts
- Dormancy detection
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from elile.investigation.finding_extractor import Severity
from elile.risk.risk_scorer import Recommendation, RiskLevel, RiskScore
from elile.risk.temporal_risk_tracker import (
    CategoryDelta,
    EvolutionSignal,
    EvolutionSignalType,
    RiskDelta,
    RiskSnapshot,
    RiskTrend,
    TemporalRiskTracker,
    TrackerConfig,
    TrendDirection,
    create_temporal_risk_tracker,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def tracker() -> TemporalRiskTracker:
    """Create a default tracker."""
    return create_temporal_risk_tracker()


@pytest.fixture
def custom_tracker() -> TemporalRiskTracker:
    """Create a tracker with custom config."""
    config = TrackerConfig(
        significant_score_change=5,
        spike_threshold=10,
        trend_min_data_points=2,
    )
    return TemporalRiskTracker(config=config)


@pytest.fixture
def entity_id():
    """Create a test entity ID."""
    return uuid7()


def create_snapshot(
    score: int = 50,
    level: RiskLevel = RiskLevel.MODERATE,
    days_ago: int = 0,
    category_scores: dict | None = None,
    findings_count: int = 5,
    critical_count: int = 0,
    high_count: int = 1,
) -> RiskSnapshot:
    """Create a test snapshot."""
    return RiskSnapshot(
        overall_score=score,
        risk_level=level,
        category_scores=category_scores or {"criminal": 0.3, "financial": 0.2},
        findings_count=findings_count,
        critical_count=critical_count,
        high_count=high_count,
        assessed_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


def create_risk_score(
    score: int = 50,
    level: RiskLevel = RiskLevel.MODERATE,
    category_scores: dict | None = None,
) -> RiskScore:
    """Create a test RiskScore."""
    from elile.investigation.finding_extractor import FindingCategory

    # Convert string keys to FindingCategory if needed
    cat_scores = {}
    for cat, val in (category_scores or {"criminal": 0.3}).items():
        if isinstance(cat, str):
            try:
                cat_scores[FindingCategory(cat)] = int(val * 100)
            except ValueError:
                pass
        else:
            cat_scores[cat] = int(val * 100)

    return RiskScore(
        overall_score=score,
        risk_level=level,
        recommendation=Recommendation.PROCEED_WITH_CAUTION,
        category_scores=cat_scores,
        contributing_factors={"findings_count": 5, "critical_count": 0, "high_count": 1},
    )


# =============================================================================
# RiskSnapshot Tests
# =============================================================================


class TestRiskSnapshot:
    """Tests for RiskSnapshot dataclass."""

    def test_create_snapshot(self) -> None:
        """Test creating a snapshot."""
        snapshot = RiskSnapshot(
            overall_score=65,
            risk_level=RiskLevel.HIGH,
        )
        assert snapshot.overall_score == 65
        assert snapshot.risk_level == RiskLevel.HIGH
        assert snapshot.snapshot_id is not None

    def test_snapshot_to_dict(self) -> None:
        """Test snapshot serialization."""
        snapshot = RiskSnapshot(
            overall_score=45,
            risk_level=RiskLevel.MODERATE,
            category_scores={"criminal": 0.5},
        )
        d = snapshot.to_dict()
        assert d["overall_score"] == 45
        assert d["risk_level"] == "moderate"
        assert d["category_scores"]["criminal"] == 0.5

    def test_from_risk_score(self) -> None:
        """Test creating snapshot from RiskScore."""
        risk_score = create_risk_score(score=70, level=RiskLevel.HIGH)
        snapshot = RiskSnapshot.from_risk_score(risk_score)

        assert snapshot.overall_score == 70
        assert snapshot.risk_level == RiskLevel.HIGH
        assert snapshot.recommendation == Recommendation.PROCEED_WITH_CAUTION


# =============================================================================
# RiskDelta Tests
# =============================================================================


class TestRiskDelta:
    """Tests for RiskDelta dataclass."""

    def test_create_delta(self) -> None:
        """Test creating a delta."""
        delta = RiskDelta(
            previous_score=40,
            current_score=60,
            score_change=20,
        )
        assert delta.score_change == 20
        assert delta.delta_id is not None

    def test_delta_to_dict(self) -> None:
        """Test delta serialization."""
        delta = RiskDelta(
            previous_score=40,
            current_score=60,
            score_change=20,
            level_escalated=True,
        )
        d = delta.to_dict()
        assert d["score_change"] == 20
        assert d["level_escalated"] is True


# =============================================================================
# EvolutionSignal Tests
# =============================================================================


class TestEvolutionSignal:
    """Tests for EvolutionSignal dataclass."""

    def test_create_signal(self) -> None:
        """Test creating a signal."""
        signal = EvolutionSignal(
            signal_type=EvolutionSignalType.SUDDEN_SPIKE,
            severity=Severity.HIGH,
            confidence=0.9,
            description="Sudden risk spike detected",
        )
        assert signal.signal_type == EvolutionSignalType.SUDDEN_SPIKE
        assert signal.severity == Severity.HIGH
        assert signal.confidence == 0.9

    def test_signal_to_dict(self) -> None:
        """Test signal serialization."""
        signal = EvolutionSignal(
            signal_type=EvolutionSignalType.TRENDING_UP,
            severity=Severity.MEDIUM,
        )
        d = signal.to_dict()
        assert d["signal_type"] == "trending_up"
        assert d["severity"] == "medium"


# =============================================================================
# Calculate Risk Delta Tests
# =============================================================================


class TestCalculateRiskDelta:
    """Tests for calculate_risk_delta method."""

    def test_basic_delta_calculation(self, tracker: TemporalRiskTracker) -> None:
        """Test basic delta calculation."""
        baseline = create_snapshot(score=40, days_ago=30)
        current = create_snapshot(score=60, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.previous_score == 40
        assert delta.current_score == 60
        assert delta.score_change == 20
        assert delta.score_change_percent == 0.5  # 20/40

    def test_delta_with_risk_scores(self, tracker: TemporalRiskTracker) -> None:
        """Test delta calculation with RiskScore inputs."""
        baseline = create_risk_score(score=50)
        current = create_risk_score(score=70)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.score_change == 20

    def test_level_escalation_detection(self, tracker: TemporalRiskTracker) -> None:
        """Test level escalation detection."""
        baseline = create_snapshot(score=35, level=RiskLevel.LOW, days_ago=7)
        current = create_snapshot(score=65, level=RiskLevel.HIGH, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.level_changed is True
        assert delta.level_escalated is True
        assert delta.level_deescalated is False
        assert delta.previous_level == RiskLevel.LOW
        assert delta.current_level == RiskLevel.HIGH

    def test_level_deescalation_detection(self, tracker: TemporalRiskTracker) -> None:
        """Test level de-escalation detection."""
        baseline = create_snapshot(score=75, level=RiskLevel.HIGH, days_ago=30)
        current = create_snapshot(score=35, level=RiskLevel.LOW, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.level_changed is True
        assert delta.level_escalated is False
        assert delta.level_deescalated is True

    def test_recommendation_change_detection(self, tracker: TemporalRiskTracker) -> None:
        """Test recommendation change detection."""
        baseline = RiskSnapshot(
            overall_score=30,
            risk_level=RiskLevel.LOW,
            recommendation=Recommendation.PROCEED,
        )
        current = RiskSnapshot(
            overall_score=70,
            risk_level=RiskLevel.HIGH,
            recommendation=Recommendation.REVIEW_REQUIRED,
        )

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.recommendation_changed is True
        assert delta.previous_recommendation == Recommendation.PROCEED
        assert delta.current_recommendation == Recommendation.REVIEW_REQUIRED

    def test_category_deltas(self, tracker: TemporalRiskTracker) -> None:
        """Test category delta calculation."""
        baseline = create_snapshot(
            score=40,
            category_scores={"criminal": 0.3, "financial": 0.2},
            days_ago=14,
        )
        current = create_snapshot(
            score=60,
            category_scores={"criminal": 0.5, "regulatory": 0.3},
            days_ago=0,
        )

        delta = tracker.calculate_risk_delta(baseline, current)

        assert len(delta.category_deltas) >= 2
        assert "regulatory" in delta.new_categories
        assert "financial" in delta.resolved_categories

    def test_findings_change(self, tracker: TemporalRiskTracker) -> None:
        """Test findings change calculation."""
        baseline = create_snapshot(findings_count=5, days_ago=7)
        current = create_snapshot(findings_count=8, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.net_findings_change == 3
        assert delta.findings_added == 3

    def test_significance_assessment(self, tracker: TemporalRiskTracker) -> None:
        """Test significance assessment."""
        baseline = create_snapshot(score=40, level=RiskLevel.MODERATE, days_ago=7)
        current = create_snapshot(score=55, level=RiskLevel.HIGH, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.is_significant is True
        assert "Risk level changed" in delta.significance_reason

    def test_insignificant_change(self, tracker: TemporalRiskTracker) -> None:
        """Test insignificant change detection."""
        baseline = create_snapshot(score=50, level=RiskLevel.MODERATE, days_ago=7)
        current = create_snapshot(score=52, level=RiskLevel.MODERATE, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.is_significant is False


# =============================================================================
# Evolution Signal Detection Tests
# =============================================================================


class TestDetectEvolutionSignals:
    """Tests for detect_evolution_signals method."""

    def test_no_signals_with_single_snapshot(self, tracker: TemporalRiskTracker) -> None:
        """Test no signals with single snapshot."""
        history = [create_snapshot(score=50)]
        signals = tracker.detect_evolution_signals(history)
        assert len(signals) == 0

    def test_trending_up_signal(self, tracker: TemporalRiskTracker, entity_id) -> None:
        """Test trending up signal detection."""
        history = [
            create_snapshot(score=30, days_ago=28),
            create_snapshot(score=35, days_ago=21),
            create_snapshot(score=42, days_ago=14),
            create_snapshot(score=50, days_ago=7),
            create_snapshot(score=58, days_ago=0),
        ]

        signals = tracker.detect_evolution_signals(history, entity_id)

        trend_signals = [s for s in signals if s.signal_type == EvolutionSignalType.TRENDING_UP]
        assert len(trend_signals) >= 1

    def test_trending_down_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test trending down signal detection."""
        history = [
            create_snapshot(score=70, days_ago=28),
            create_snapshot(score=62, days_ago=21),
            create_snapshot(score=55, days_ago=14),
            create_snapshot(score=45, days_ago=7),
            create_snapshot(score=38, days_ago=0),
        ]

        signals = tracker.detect_evolution_signals(history)

        trend_signals = [s for s in signals if s.signal_type == EvolutionSignalType.TRENDING_DOWN]
        assert len(trend_signals) >= 1

    def test_sudden_spike_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test sudden spike signal detection."""
        history = [
            create_snapshot(score=40, days_ago=14),
            create_snapshot(score=42, days_ago=7),
            create_snapshot(score=75, days_ago=0),  # Spike of 33 points
        ]

        signals = tracker.detect_evolution_signals(history)

        spike_signals = [s for s in signals if s.signal_type == EvolutionSignalType.SUDDEN_SPIKE]
        assert len(spike_signals) >= 1
        if spike_signals:
            assert spike_signals[0].severity in (Severity.HIGH, Severity.CRITICAL)

    def test_sudden_drop_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test sudden drop signal detection."""
        history = [
            create_snapshot(score=70, days_ago=14),
            create_snapshot(score=68, days_ago=7),
            create_snapshot(score=45, days_ago=0),  # Drop of 23 points
        ]

        signals = tracker.detect_evolution_signals(history)

        drop_signals = [s for s in signals if s.signal_type == EvolutionSignalType.SUDDEN_DROP]
        assert len(drop_signals) >= 1

    def test_level_escalation_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test level escalation signal detection."""
        history = [
            create_snapshot(score=55, level=RiskLevel.MODERATE, days_ago=7),
            create_snapshot(score=75, level=RiskLevel.HIGH, days_ago=0),
        ]

        signals = tracker.detect_evolution_signals(history)

        level_signals = [s for s in signals if s.signal_type == EvolutionSignalType.LEVEL_ESCALATION]
        assert len(level_signals) >= 1

    def test_level_deescalation_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test level de-escalation signal detection."""
        history = [
            create_snapshot(score=75, level=RiskLevel.HIGH, days_ago=7),
            create_snapshot(score=45, level=RiskLevel.MODERATE, days_ago=0),
        ]

        signals = tracker.detect_evolution_signals(history)

        level_signals = [s for s in signals if s.signal_type == EvolutionSignalType.LEVEL_DEESCALATION]
        assert len(level_signals) >= 1

    def test_category_emergence_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test category emergence signal detection."""
        history = [
            create_snapshot(score=40, category_scores={"criminal": 0.3}, days_ago=7),
            create_snapshot(score=55, category_scores={"criminal": 0.3, "regulatory": 0.4}, days_ago=0),
        ]

        signals = tracker.detect_evolution_signals(history)

        cat_signals = [s for s in signals if s.signal_type == EvolutionSignalType.CATEGORY_EMERGENCE]
        assert len(cat_signals) >= 1

    def test_category_resolution_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test category resolution signal detection."""
        history = [
            create_snapshot(score=50, category_scores={"criminal": 0.3, "financial": 0.4}, days_ago=7),
            create_snapshot(score=35, category_scores={"criminal": 0.2}, days_ago=0),
        ]

        signals = tracker.detect_evolution_signals(history)

        cat_signals = [s for s in signals if s.signal_type == EvolutionSignalType.CATEGORY_RESOLUTION]
        assert len(cat_signals) >= 1

    def test_threshold_breach_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test threshold breach signal detection."""
        history = [
            create_snapshot(score=55, days_ago=7),
            create_snapshot(score=65, days_ago=0),  # Crosses 60 threshold
        ]

        signals = tracker.detect_evolution_signals(history)

        threshold_signals = [s for s in signals if s.signal_type == EvolutionSignalType.THRESHOLD_BREACH]
        assert len(threshold_signals) >= 1

    def test_rapid_escalation_signal(self, tracker: TemporalRiskTracker) -> None:
        """Test rapid escalation signal detection."""
        history = [
            create_snapshot(score=40, days_ago=10),
            create_snapshot(score=45, days_ago=7),
            create_snapshot(score=65, days_ago=0),  # +25 in 10 days
        ]

        signals = tracker.detect_evolution_signals(history)

        rapid_signals = [s for s in signals if s.signal_type == EvolutionSignalType.RAPID_ESCALATION]
        assert len(rapid_signals) >= 1


# =============================================================================
# Trend Analysis Tests
# =============================================================================


class TestAnalyzeTrend:
    """Tests for analyze_trend method."""

    def test_empty_history(self, tracker: TemporalRiskTracker) -> None:
        """Test with empty history."""
        trend = tracker.analyze_trend([])
        assert trend.direction == TrendDirection.STABLE
        assert trend.data_points == 0

    def test_increasing_trend(self, tracker: TemporalRiskTracker, entity_id) -> None:
        """Test increasing trend detection."""
        history = [
            create_snapshot(score=30, days_ago=28),
            create_snapshot(score=40, days_ago=21),
            create_snapshot(score=50, days_ago=14),
            create_snapshot(score=60, days_ago=7),
            create_snapshot(score=70, days_ago=0),
        ]

        trend = tracker.analyze_trend(history, entity_id)

        assert trend.direction == TrendDirection.INCREASING
        assert trend.entity_id == entity_id
        assert trend.data_points == 5

    def test_decreasing_trend(self, tracker: TemporalRiskTracker) -> None:
        """Test decreasing trend detection."""
        history = [
            create_snapshot(score=70, days_ago=28),
            create_snapshot(score=60, days_ago=21),
            create_snapshot(score=50, days_ago=14),
            create_snapshot(score=40, days_ago=7),
            create_snapshot(score=30, days_ago=0),
        ]

        trend = tracker.analyze_trend(history)

        assert trend.direction == TrendDirection.DECREASING

    def test_stable_trend(self, tracker: TemporalRiskTracker) -> None:
        """Test stable trend detection."""
        history = [
            create_snapshot(score=50, days_ago=28),
            create_snapshot(score=52, days_ago=21),
            create_snapshot(score=48, days_ago=14),
            create_snapshot(score=51, days_ago=7),
            create_snapshot(score=49, days_ago=0),
        ]

        trend = tracker.analyze_trend(history)

        assert trend.direction == TrendDirection.STABLE

    def test_volatile_trend(self, tracker: TemporalRiskTracker) -> None:
        """Test volatile trend detection."""
        history = [
            create_snapshot(score=30, days_ago=28),
            create_snapshot(score=70, days_ago=21),
            create_snapshot(score=25, days_ago=14),
            create_snapshot(score=75, days_ago=7),
            create_snapshot(score=40, days_ago=0),
        ]

        trend = tracker.analyze_trend(history)

        assert trend.direction == TrendDirection.VOLATILE

    def test_trend_statistics(self, tracker: TemporalRiskTracker) -> None:
        """Test trend statistics calculation."""
        history = [
            create_snapshot(score=40, days_ago=14),
            create_snapshot(score=50, days_ago=7),
            create_snapshot(score=60, days_ago=0),
        ]

        trend = tracker.analyze_trend(history)

        assert trend.average_score == 50.0
        assert trend.min_score == 40
        assert trend.max_score == 60
        assert trend.score_std_dev > 0

    def test_trend_includes_signals(self, tracker: TemporalRiskTracker) -> None:
        """Test that trend includes detected signals."""
        history = [
            create_snapshot(score=30, days_ago=14),
            create_snapshot(score=45, days_ago=7),
            create_snapshot(score=65, days_ago=0),
        ]

        trend = tracker.analyze_trend(history)

        assert len(trend.signals) > 0

    def test_trend_to_dict(self, tracker: TemporalRiskTracker) -> None:
        """Test trend serialization."""
        history = [
            create_snapshot(score=40, days_ago=7),
            create_snapshot(score=50, days_ago=0),
        ]

        trend = tracker.analyze_trend(history)
        d = trend.to_dict()

        assert "direction" in d
        assert "average_score" in d
        assert "signals" in d


# =============================================================================
# Configuration Tests
# =============================================================================


class TestTrackerConfig:
    """Tests for TrackerConfig."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = TrackerConfig()
        assert config.significant_score_change == 10
        assert config.spike_threshold == 15
        assert config.trend_min_data_points == 3

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = TrackerConfig(
            significant_score_change=5,
            spike_threshold=20,
            alert_thresholds=[50, 75],
        )
        assert config.significant_score_change == 5
        assert config.spike_threshold == 20
        assert config.alert_thresholds == [50, 75]

    def test_custom_config_affects_detection(self, custom_tracker: TemporalRiskTracker) -> None:
        """Test that custom config affects detection."""
        # With lower spike threshold (10), this should detect a spike
        history = [
            create_snapshot(score=40, days_ago=7),
            create_snapshot(score=55, days_ago=0),  # +15 change
        ]

        signals = custom_tracker.detect_evolution_signals(history)

        spike_signals = [s for s in signals if s.signal_type == EvolutionSignalType.SUDDEN_SPIKE]
        assert len(spike_signals) >= 1


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_identical_snapshots(self, tracker: TemporalRiskTracker) -> None:
        """Test with identical snapshots."""
        snapshot = create_snapshot(score=50)
        delta = tracker.calculate_risk_delta(snapshot, snapshot)

        assert delta.score_change == 0
        assert delta.level_changed is False
        assert delta.is_significant is False

    def test_zero_baseline_score(self, tracker: TemporalRiskTracker) -> None:
        """Test with zero baseline score."""
        baseline = create_snapshot(score=0, level=RiskLevel.LOW, days_ago=7)
        current = create_snapshot(score=50, level=RiskLevel.MODERATE, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.score_change == 50
        assert delta.score_change_percent == 0.0  # Avoid division by zero

    def test_max_score(self, tracker: TemporalRiskTracker) -> None:
        """Test with maximum score."""
        baseline = create_snapshot(score=85, level=RiskLevel.CRITICAL, days_ago=7)
        current = create_snapshot(score=100, level=RiskLevel.CRITICAL, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.current_score == 100
        assert delta.level_changed is False

    def test_negative_score_change(self, tracker: TemporalRiskTracker) -> None:
        """Test negative score change."""
        baseline = create_snapshot(score=70, days_ago=7)
        current = create_snapshot(score=40, days_ago=0)

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.score_change == -30
        assert delta.score_change_percent < 0

    def test_single_data_point_trend(self, tracker: TemporalRiskTracker) -> None:
        """Test trend with single data point."""
        history = [create_snapshot(score=50)]
        trend = tracker.analyze_trend(history)

        assert trend.data_points == 1
        assert trend.direction == TrendDirection.STABLE


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_with_default(self) -> None:
        """Test creating tracker with defaults."""
        tracker = create_temporal_risk_tracker()
        assert isinstance(tracker, TemporalRiskTracker)

    def test_create_with_config(self) -> None:
        """Test creating tracker with config."""
        config = TrackerConfig(spike_threshold=25)
        tracker = create_temporal_risk_tracker(config=config)
        assert tracker.config.spike_threshold == 25


# =============================================================================
# Integration Tests
# =============================================================================


class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_monitoring_scenario(self, tracker: TemporalRiskTracker, entity_id) -> None:
        """Test a complete monitoring scenario."""
        # Simulate monitoring over 2 months
        history = [
            # Month 1: Stable low risk
            create_snapshot(score=25, level=RiskLevel.LOW, days_ago=60),
            create_snapshot(score=28, level=RiskLevel.LOW, days_ago=53),
            create_snapshot(score=27, level=RiskLevel.LOW, days_ago=46),
            create_snapshot(score=30, level=RiskLevel.LOW, days_ago=39),
            # Month 2: Escalation
            create_snapshot(score=35, level=RiskLevel.LOW, days_ago=32),
            create_snapshot(score=45, level=RiskLevel.MODERATE, days_ago=25),
            create_snapshot(score=55, level=RiskLevel.MODERATE, days_ago=18),
            create_snapshot(score=65, level=RiskLevel.HIGH, days_ago=11),
            create_snapshot(score=72, level=RiskLevel.HIGH, days_ago=4),
            create_snapshot(score=78, level=RiskLevel.HIGH, days_ago=0),
        ]

        # Analyze trend
        trend = tracker.analyze_trend(history, entity_id)

        assert trend.direction == TrendDirection.INCREASING
        assert trend.min_score == 25
        assert trend.max_score == 78
        assert len(trend.signals) > 0

        # Check for specific signals
        signal_types = {s.signal_type for s in trend.signals}
        assert EvolutionSignalType.TRENDING_UP in signal_types or EvolutionSignalType.LEVEL_ESCALATION in signal_types

    def test_delta_between_two_assessments(self, tracker: TemporalRiskTracker) -> None:
        """Test delta calculation between two full assessments."""
        baseline = create_risk_score(
            score=40,
            level=RiskLevel.MODERATE,
            category_scores={"criminal": 0.3, "financial": 0.2},
        )

        current = create_risk_score(
            score=70,
            level=RiskLevel.HIGH,
            category_scores={"criminal": 0.5, "financial": 0.3, "regulatory": 0.4},
        )

        delta = tracker.calculate_risk_delta(baseline, current)

        assert delta.score_change == 30
        assert delta.level_escalated is True
        assert delta.is_significant is True
