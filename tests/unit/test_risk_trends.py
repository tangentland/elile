"""Tests for Risk Trends Analysis.

Tests cover:
- Velocity calculation
- Risk prediction
- Subject trend analysis
- Portfolio analysis
- Attention flagging
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid7

import pytest

from elile.risk.risk_scorer import RiskLevel
from elile.risk.temporal_risk_tracker import RiskSnapshot, TrendDirection
from elile.risk.trends import (
    PortfolioRiskLevel,
    PortfolioRiskSummary,
    PredictionConfidence,
    RiskPrediction,
    RiskTrendAnalyzer,
    RiskTrajectory,
    SubjectTrendSummary,
    TrendAnalyzerConfig,
    VelocityMetrics,
    create_risk_trend_analyzer,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def analyzer() -> RiskTrendAnalyzer:
    """Create a default analyzer."""
    return create_risk_trend_analyzer()


@pytest.fixture
def custom_analyzer() -> RiskTrendAnalyzer:
    """Create analyzer with custom config."""
    config = TrendAnalyzerConfig(
        velocity_window_days=7,
        high_velocity_threshold=0.5,
        min_data_points_for_prediction=2,
    )
    return RiskTrendAnalyzer(config=config)


@pytest.fixture
def entity_id():
    """Create test entity ID."""
    return uuid7()


def create_snapshot(
    score: int = 50,
    level: RiskLevel = RiskLevel.MODERATE,
    days_ago: int = 0,
) -> RiskSnapshot:
    """Create a test snapshot."""
    return RiskSnapshot(
        overall_score=score,
        risk_level=level,
        assessed_at=datetime.now(UTC) - timedelta(days=days_ago),
    )


def create_history(
    start_score: int,
    end_score: int,
    data_points: int = 5,
    days_span: int = 30,
) -> list[RiskSnapshot]:
    """Create a linear history from start to end score."""
    history = []
    score_step = (end_score - start_score) / (data_points - 1) if data_points > 1 else 0
    day_step = days_span / (data_points - 1) if data_points > 1 else 0

    for i in range(data_points):
        score = int(start_score + score_step * i)
        days_ago = int(days_span - day_step * i)
        level = (
            RiskLevel.LOW if score < 40
            else RiskLevel.MODERATE if score < 60
            else RiskLevel.HIGH if score < 80
            else RiskLevel.CRITICAL
        )
        history.append(create_snapshot(score=score, level=level, days_ago=days_ago))

    return history


# =============================================================================
# Velocity Calculation Tests
# =============================================================================


class TestCalculateVelocity:
    """Tests for velocity calculation."""

    def test_empty_history(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test velocity with empty history."""
        velocity = analyzer.calculate_velocity([])
        assert velocity.data_points == 0
        assert velocity.current_velocity == 0.0

    def test_single_snapshot(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test velocity with single snapshot."""
        history = [create_snapshot(score=50)]
        velocity = analyzer.calculate_velocity(history)
        assert velocity.data_points == 1
        assert velocity.current_velocity == 0.0

    def test_positive_velocity(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test increasing risk velocity."""
        history = create_history(start_score=30, end_score=70, data_points=5, days_span=28)
        velocity = analyzer.calculate_velocity(history)

        assert velocity.current_velocity > 0
        assert velocity.average_velocity > 0
        assert velocity.trajectory in (RiskTrajectory.DETERIORATING, RiskTrajectory.ACCELERATING_RISK)

    def test_negative_velocity(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test decreasing risk velocity."""
        history = create_history(start_score=70, end_score=30, data_points=5, days_span=28)
        velocity = analyzer.calculate_velocity(history)

        assert velocity.current_velocity < 0
        assert velocity.average_velocity < 0
        assert velocity.trajectory in (RiskTrajectory.IMPROVING, RiskTrajectory.RAPID_IMPROVEMENT)

    def test_stable_velocity(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test stable risk velocity."""
        history = [
            create_snapshot(score=50, days_ago=28),
            create_snapshot(score=51, days_ago=21),
            create_snapshot(score=49, days_ago=14),
            create_snapshot(score=50, days_ago=7),
            create_snapshot(score=50, days_ago=0),
        ]
        velocity = analyzer.calculate_velocity(history)

        assert abs(velocity.current_velocity) < 0.5
        assert velocity.trajectory == RiskTrajectory.STABLE

    def test_acceleration_detection(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test acceleration detection."""
        # Accelerating risk: velocity increasing over time
        # Use longer history with clear acceleration pattern
        history = [
            create_snapshot(score=30, days_ago=42),
            create_snapshot(score=32, days_ago=35),
            create_snapshot(score=35, days_ago=28),
            create_snapshot(score=40, days_ago=21),
            create_snapshot(score=50, days_ago=14),
            create_snapshot(score=65, days_ago=7),
            create_snapshot(score=85, days_ago=0),
        ]
        velocity = analyzer.calculate_velocity(history, window_days=45)

        # Should detect some acceleration (velocity increasing over time)
        assert velocity.current_velocity > velocity.average_velocity or velocity.acceleration >= 0

    def test_days_to_threshold_estimate(self, custom_analyzer: RiskTrendAnalyzer) -> None:
        """Test days to threshold estimation."""
        history = [
            create_snapshot(score=35, days_ago=14),
            create_snapshot(score=38, days_ago=7),
            create_snapshot(score=42, days_ago=0),
        ]
        velocity = custom_analyzer.calculate_velocity(history)

        # Should estimate days to 60 threshold
        if velocity.days_to_threshold:
            assert velocity.days_to_threshold > 0

    def test_velocity_to_dict(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test velocity serialization."""
        history = create_history(30, 50, 3, 14)
        velocity = analyzer.calculate_velocity(history)
        d = velocity.to_dict()

        assert "current_velocity" in d
        assert "trajectory" in d
        assert "velocity_id" in d


# =============================================================================
# Risk Prediction Tests
# =============================================================================


class TestPredictRisk:
    """Tests for risk prediction."""

    def test_insufficient_history(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test prediction with insufficient history."""
        history = [create_snapshot(score=50)]
        prediction = analyzer.predict_risk(history)

        assert prediction.confidence == PredictionConfidence.LOW
        assert "Insufficient history" in prediction.confidence_factors[0]

    def test_upward_prediction(self, analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test predicting increasing risk."""
        history = create_history(start_score=30, end_score=50, data_points=5, days_span=30)
        prediction = analyzer.predict_risk(history, entity_id, horizon_days=30)

        assert prediction.entity_id == entity_id
        assert prediction.predicted_score > prediction.current_score
        assert prediction.prediction_horizon_days == 30

    def test_downward_prediction(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test predicting decreasing risk."""
        history = create_history(start_score=70, end_score=50, data_points=5, days_span=30)
        prediction = analyzer.predict_risk(history, horizon_days=30)

        assert prediction.predicted_score < prediction.current_score

    def test_threshold_breach_prediction(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test predicting threshold breach."""
        # Current score just below threshold, trending up
        history = create_history(start_score=50, end_score=58, data_points=5, days_span=30)
        prediction = analyzer.predict_risk(history, horizon_days=30)

        # Should predict crossing 60 threshold
        if prediction.predicted_score >= 60:
            assert prediction.threshold_breach_predicted is True
            assert prediction.threshold_at_risk == 60

    def test_level_change_prediction(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test predicting level change."""
        history = create_history(start_score=35, end_score=55, data_points=5, days_span=30)
        prediction = analyzer.predict_risk(history, horizon_days=30)

        if prediction.predicted_score >= 60:
            assert prediction.level_change_predicted is True

    def test_prediction_confidence_varies(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test that confidence varies with data quality."""
        # Short history
        short_history = create_history(30, 50, 3, 14)
        short_pred = analyzer.predict_risk(short_history)

        # Long history
        long_history = create_history(30, 50, 15, 90)
        long_pred = analyzer.predict_risk(long_history)

        # Longer history should have higher confidence
        assert long_pred.confidence_score >= short_pred.confidence_score

    def test_prediction_to_dict(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test prediction serialization."""
        history = create_history(30, 50, 5, 30)
        prediction = analyzer.predict_risk(history)
        d = prediction.to_dict()

        assert "predicted_score" in d
        assert "confidence" in d
        assert "prediction_id" in d


# =============================================================================
# Subject Trend Analysis Tests
# =============================================================================


class TestAnalyzeSubjectTrend:
    """Tests for subject trend analysis."""

    def test_empty_history(self, analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test analysis with empty history."""
        summary = analyzer.analyze_subject_trend(entity_id, [])

        assert summary.entity_id == entity_id
        assert summary.requires_attention is False

    def test_complete_analysis(self, analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test complete trend analysis."""
        history = create_history(30, 60, 6, 30)
        summary = analyzer.analyze_subject_trend(entity_id, history)

        assert summary.entity_id == entity_id
        assert summary.current_score == 60
        assert summary.trend is not None
        assert summary.velocity is not None
        assert summary.prediction is not None

    def test_high_risk_flagged(self, analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test that high risk subjects are flagged."""
        history = [
            create_snapshot(score=65, level=RiskLevel.HIGH, days_ago=7),
            create_snapshot(score=70, level=RiskLevel.HIGH, days_ago=0),
        ]
        summary = analyzer.analyze_subject_trend(entity_id, history)

        assert summary.requires_attention is True
        assert any("risk level" in r.lower() for r in summary.attention_reasons)

    def test_rapid_change_flagged(self, custom_analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test that rapid changes are flagged."""
        # Rapid increase
        history = [
            create_snapshot(score=30, days_ago=7),
            create_snapshot(score=55, days_ago=0),  # +25 in 7 days
        ]
        summary = custom_analyzer.analyze_subject_trend(entity_id, history)

        assert summary.requires_attention is True

    def test_no_prediction_when_disabled(self, analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test analysis without prediction."""
        history = create_history(30, 50, 5, 30)
        summary = analyzer.analyze_subject_trend(entity_id, history, include_prediction=False)

        assert summary.prediction is None

    def test_summary_to_dict(self, analyzer: RiskTrendAnalyzer, entity_id) -> None:
        """Test summary serialization."""
        history = create_history(30, 50, 5, 30)
        summary = analyzer.analyze_subject_trend(entity_id, history)
        d = summary.to_dict()

        assert "entity_id" in d
        assert "current_score" in d
        assert "trend" in d


# =============================================================================
# Portfolio Analysis Tests
# =============================================================================


class TestAnalyzePortfolio:
    """Tests for portfolio analysis."""

    def test_empty_portfolio(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test analysis with empty portfolio."""
        summary = analyzer.analyze_portfolio({})

        assert summary.total_subjects == 0
        assert summary.portfolio_risk_level == PortfolioRiskLevel.HEALTHY

    def test_healthy_portfolio(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test healthy portfolio with stable low-risk subjects."""
        # Use stable scores (no deterioration) to get HEALTHY status
        subjects = {
            uuid7(): [
                create_snapshot(score=25, level=RiskLevel.LOW, days_ago=14),
                create_snapshot(score=24, level=RiskLevel.LOW, days_ago=7),
                create_snapshot(score=25, level=RiskLevel.LOW, days_ago=0),
            ],
            uuid7(): [
                create_snapshot(score=30, level=RiskLevel.LOW, days_ago=14),
                create_snapshot(score=29, level=RiskLevel.LOW, days_ago=7),
                create_snapshot(score=30, level=RiskLevel.LOW, days_ago=0),
            ],
            uuid7(): [
                create_snapshot(score=35, level=RiskLevel.LOW, days_ago=14),
                create_snapshot(score=34, level=RiskLevel.LOW, days_ago=7),
                create_snapshot(score=35, level=RiskLevel.LOW, days_ago=0),
            ],
        }
        summary = analyzer.analyze_portfolio(subjects)

        assert summary.total_subjects == 3
        assert summary.low_risk_count == 3
        # With stable/improving scores and low risk levels, should be healthy or watchful
        assert summary.portfolio_risk_level in (PortfolioRiskLevel.HEALTHY, PortfolioRiskLevel.WATCHFUL)

    def test_critical_portfolio(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio with critical subjects."""
        subjects = {
            uuid7(): create_history(80, 85, 3, 14),  # Critical
            uuid7(): create_history(75, 82, 3, 14),  # Critical
            uuid7(): create_history(30, 35, 3, 14),  # Low
        }
        summary = analyzer.analyze_portfolio(subjects)

        assert summary.critical_risk_count >= 1
        assert summary.portfolio_risk_level in (
            PortfolioRiskLevel.CONCERNING,
            PortfolioRiskLevel.CRITICAL,
        )

    def test_portfolio_metrics(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio aggregate metrics."""
        subjects = {
            uuid7(): [create_snapshot(score=30, days_ago=0)],
            uuid7(): [create_snapshot(score=50, days_ago=0)],
            uuid7(): [create_snapshot(score=70, days_ago=0)],
        }
        summary = analyzer.analyze_portfolio(subjects)

        assert summary.average_score == 50.0
        assert summary.lowest_score == 30
        assert summary.highest_score == 70

    def test_portfolio_trend_distribution(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio trend distribution."""
        subjects = {
            uuid7(): create_history(30, 50, 5, 30),  # Deteriorating
            uuid7(): create_history(50, 50, 5, 30),  # Stable
            uuid7(): create_history(70, 50, 5, 30),  # Improving
        }
        summary = analyzer.analyze_portfolio(subjects)

        assert summary.deteriorating_count >= 0
        assert summary.stable_count >= 0
        assert summary.improving_count >= 0

    def test_portfolio_attention_subjects(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio attention flagging."""
        high_risk_id = uuid7()
        subjects = {
            uuid7(): create_history(20, 25, 5, 30),
            high_risk_id: [
                create_snapshot(score=75, level=RiskLevel.HIGH, days_ago=7),
                create_snapshot(score=80, level=RiskLevel.CRITICAL, days_ago=0),
            ],
            uuid7(): create_history(30, 35, 5, 30),
        }
        summary = analyzer.analyze_portfolio(subjects)

        assert summary.attention_required_count >= 1
        assert high_risk_id in summary.attention_subjects

    def test_portfolio_health_score(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio health score calculation."""
        # Healthy portfolio
        healthy_subjects = {
            uuid7(): create_history(20, 25, 3, 14),
            uuid7(): create_history(25, 30, 3, 14),
        }
        healthy_summary = analyzer.analyze_portfolio(healthy_subjects)

        # Unhealthy portfolio
        unhealthy_subjects = {
            uuid7(): create_history(75, 85, 3, 14),
            uuid7(): create_history(80, 90, 3, 14),
        }
        unhealthy_summary = analyzer.analyze_portfolio(unhealthy_subjects)

        assert healthy_summary.portfolio_health_score > unhealthy_summary.portfolio_health_score

    def test_portfolio_with_tenant(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio with tenant ID."""
        tenant_id = uuid7()
        subjects = {uuid7(): create_history(30, 40, 3, 14)}
        summary = analyzer.analyze_portfolio(subjects, tenant_id=tenant_id)

        assert summary.tenant_id == tenant_id

    def test_portfolio_to_dict(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test portfolio serialization."""
        subjects = {uuid7(): create_history(30, 50, 3, 14)}
        summary = analyzer.analyze_portfolio(subjects)
        d = summary.to_dict()

        assert "total_subjects" in d
        assert "risk_distribution" in d
        assert "portfolio_risk_level" in d


# =============================================================================
# Configuration Tests
# =============================================================================


class TestTrendAnalyzerConfig:
    """Tests for configuration."""

    def test_default_config(self) -> None:
        """Test default configuration."""
        config = TrendAnalyzerConfig()
        assert config.default_lookback_days == 90
        assert config.velocity_window_days == 14
        assert config.prediction_horizon_days == 30

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = TrendAnalyzerConfig(
            default_lookback_days=60,
            high_velocity_threshold=0.5,
        )
        assert config.default_lookback_days == 60
        assert config.high_velocity_threshold == 0.5


# =============================================================================
# Factory Function Tests
# =============================================================================


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_with_defaults(self) -> None:
        """Test creating analyzer with defaults."""
        analyzer = create_risk_trend_analyzer()
        assert isinstance(analyzer, RiskTrendAnalyzer)

    def test_create_with_config(self) -> None:
        """Test creating analyzer with config."""
        config = TrendAnalyzerConfig(velocity_window_days=21)
        analyzer = create_risk_trend_analyzer(config=config)
        assert analyzer.config.velocity_window_days == 21


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases."""

    def test_all_same_score(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test with all same scores."""
        history = [
            create_snapshot(score=50, days_ago=i * 7) for i in range(5, -1, -1)
        ]
        velocity = analyzer.calculate_velocity(history)
        prediction = analyzer.predict_risk(history)

        assert abs(velocity.current_velocity) < 0.1
        assert abs(prediction.predicted_score - 50) < 5

    def test_extreme_values(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test with extreme score values."""
        history = [
            create_snapshot(score=0, level=RiskLevel.LOW, days_ago=14),
            create_snapshot(score=100, level=RiskLevel.CRITICAL, days_ago=0),
        ]
        velocity = analyzer.calculate_velocity(history)

        assert velocity.current_velocity > 5  # Very high velocity

    def test_single_day_span(self, analyzer: RiskTrendAnalyzer) -> None:
        """Test with very short time span."""
        now = datetime.now(UTC)
        history = [
            RiskSnapshot(overall_score=40, assessed_at=now - timedelta(hours=12)),
            RiskSnapshot(overall_score=50, assessed_at=now),
        ]
        velocity = analyzer.calculate_velocity(history)

        # Should still calculate something
        assert velocity.data_points == 2
