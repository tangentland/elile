"""Risk Trends Analysis for portfolio monitoring.

This module extends temporal risk tracking with:
- Velocity and acceleration calculations
- Trend prediction models
- Portfolio-level risk aggregation
- Cohort analysis
- Risk trajectory forecasting
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.risk.risk_scorer import RiskLevel
from elile.risk.temporal_risk_tracker import (
    EvolutionSignal,
    RiskSnapshot,
    RiskTrend,
    TemporalRiskTracker,
    TrackerConfig,
    TrendDirection,
)

logger = structlog.get_logger()


# =============================================================================
# Enums
# =============================================================================


class PredictionConfidence(str, Enum):
    """Confidence level for predictions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskTrajectory(str, Enum):
    """Overall risk trajectory classification."""

    IMPROVING = "improving"
    STABLE = "stable"
    DETERIORATING = "deteriorating"
    ACCELERATING_RISK = "accelerating_risk"
    RAPID_IMPROVEMENT = "rapid_improvement"


class PortfolioRiskLevel(str, Enum):
    """Portfolio-level risk classification."""

    HEALTHY = "healthy"
    WATCHFUL = "watchful"
    CONCERNING = "concerning"
    CRITICAL = "critical"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class VelocityMetrics:
    """Risk velocity and acceleration metrics.

    Velocity: Rate of score change per day
    Acceleration: Change in velocity over time
    """

    velocity_id: UUID = field(default_factory=uuid7)

    # Current velocity (points per day)
    current_velocity: float = 0.0
    average_velocity: float = 0.0
    peak_velocity: float = 0.0

    # Acceleration (change in velocity)
    acceleration: float = 0.0
    is_accelerating: bool = False
    is_decelerating: bool = False

    # Time context
    measurement_period_days: int = 30
    data_points: int = 0

    # Interpretation
    trajectory: RiskTrajectory = RiskTrajectory.STABLE
    days_to_threshold: int | None = None  # Estimated days until next threshold

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "velocity_id": str(self.velocity_id),
            "current_velocity": self.current_velocity,
            "average_velocity": self.average_velocity,
            "peak_velocity": self.peak_velocity,
            "acceleration": self.acceleration,
            "is_accelerating": self.is_accelerating,
            "is_decelerating": self.is_decelerating,
            "measurement_period_days": self.measurement_period_days,
            "data_points": self.data_points,
            "trajectory": self.trajectory.value,
            "days_to_threshold": self.days_to_threshold,
        }


@dataclass
class RiskPrediction:
    """Predicted future risk state."""

    prediction_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None

    # Current state
    current_score: int = 0
    current_level: RiskLevel = RiskLevel.LOW

    # Prediction
    predicted_score: int = 0
    predicted_level: RiskLevel = RiskLevel.LOW
    prediction_horizon_days: int = 30

    # Confidence
    confidence: PredictionConfidence = PredictionConfidence.MEDIUM
    confidence_score: float = 0.5
    confidence_factors: list[str] = field(default_factory=list)

    # Risk assessment
    level_change_predicted: bool = False
    threshold_breach_predicted: bool = False
    threshold_at_risk: int | None = None

    # Timing
    predicted_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "prediction_id": str(self.prediction_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "current_score": self.current_score,
            "current_level": self.current_level.value,
            "predicted_score": self.predicted_score,
            "predicted_level": self.predicted_level.value,
            "prediction_horizon_days": self.prediction_horizon_days,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "confidence_factors": self.confidence_factors,
            "level_change_predicted": self.level_change_predicted,
            "threshold_breach_predicted": self.threshold_breach_predicted,
            "threshold_at_risk": self.threshold_at_risk,
            "predicted_at": self.predicted_at.isoformat(),
        }


@dataclass
class SubjectTrendSummary:
    """Trend summary for a single subject."""

    entity_id: UUID
    current_score: int = 0
    current_level: RiskLevel = RiskLevel.LOW
    trend: RiskTrend | None = None
    velocity: VelocityMetrics | None = None
    prediction: RiskPrediction | None = None
    signals: list[EvolutionSignal] = field(default_factory=list)
    requires_attention: bool = False
    attention_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "entity_id": str(self.entity_id),
            "current_score": self.current_score,
            "current_level": self.current_level.value,
            "trend": self.trend.to_dict() if self.trend else None,
            "velocity": self.velocity.to_dict() if self.velocity else None,
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "signals": [s.to_dict() for s in self.signals],
            "requires_attention": self.requires_attention,
            "attention_reasons": self.attention_reasons,
        }


@dataclass
class PortfolioRiskSummary:
    """Aggregate risk summary for a portfolio of subjects."""

    summary_id: UUID = field(default_factory=uuid7)
    tenant_id: UUID | None = None

    # Portfolio composition
    total_subjects: int = 0
    subjects_analyzed: int = 0

    # Risk distribution
    low_risk_count: int = 0
    moderate_risk_count: int = 0
    high_risk_count: int = 0
    critical_risk_count: int = 0

    # Aggregate metrics
    average_score: float = 0.0
    median_score: int = 0
    score_std_dev: float = 0.0
    highest_score: int = 0
    lowest_score: int = 0

    # Trend distribution
    improving_count: int = 0
    stable_count: int = 0
    deteriorating_count: int = 0

    # Portfolio risk level
    portfolio_risk_level: PortfolioRiskLevel = PortfolioRiskLevel.HEALTHY
    portfolio_health_score: float = 1.0  # 0-1, higher is healthier

    # Subjects requiring attention
    attention_required_count: int = 0
    attention_subjects: list[UUID] = field(default_factory=list)

    # Signals summary
    total_signals: int = 0
    critical_signals: int = 0
    high_signals: int = 0

    # Analysis timing
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    analysis_period_days: int = 30

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "summary_id": str(self.summary_id),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "total_subjects": self.total_subjects,
            "subjects_analyzed": self.subjects_analyzed,
            "risk_distribution": {
                "low": self.low_risk_count,
                "moderate": self.moderate_risk_count,
                "high": self.high_risk_count,
                "critical": self.critical_risk_count,
            },
            "aggregate_metrics": {
                "average_score": self.average_score,
                "median_score": self.median_score,
                "score_std_dev": self.score_std_dev,
                "highest_score": self.highest_score,
                "lowest_score": self.lowest_score,
            },
            "trend_distribution": {
                "improving": self.improving_count,
                "stable": self.stable_count,
                "deteriorating": self.deteriorating_count,
            },
            "portfolio_risk_level": self.portfolio_risk_level.value,
            "portfolio_health_score": self.portfolio_health_score,
            "attention_required_count": self.attention_required_count,
            "attention_subjects": [str(s) for s in self.attention_subjects],
            "signals_summary": {
                "total": self.total_signals,
                "critical": self.critical_signals,
                "high": self.high_signals,
            },
            "analyzed_at": self.analyzed_at.isoformat(),
            "analysis_period_days": self.analysis_period_days,
        }


# =============================================================================
# Configuration
# =============================================================================


class TrendAnalyzerConfig(BaseModel):
    """Configuration for trend analyzer."""

    # Lookback periods
    default_lookback_days: int = Field(
        default=90, ge=7, le=365, description="Default lookback for trend analysis"
    )
    velocity_window_days: int = Field(
        default=14, ge=3, le=90, description="Window for velocity calculation"
    )
    prediction_horizon_days: int = Field(
        default=30, ge=7, le=180, description="Default prediction horizon"
    )

    # Thresholds for attention flagging
    high_velocity_threshold: float = Field(
        default=1.0, ge=0.1, le=5.0, description="Daily score change to flag"
    )
    acceleration_threshold: float = Field(
        default=0.1, ge=0.01, le=1.0, description="Acceleration to flag"
    )

    # Portfolio thresholds
    portfolio_critical_percent: float = Field(
        default=0.1, ge=0.0, le=1.0, description="% critical for concerning portfolio"
    )
    portfolio_high_percent: float = Field(
        default=0.2, ge=0.0, le=1.0, description="% high risk for watchful portfolio"
    )

    # Prediction thresholds
    min_data_points_for_prediction: int = Field(
        default=3, ge=2, le=20, description="Minimum history for predictions"
    )
    prediction_confidence_threshold: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Min confidence to make prediction"
    )

    # Risk thresholds for prediction
    risk_thresholds: list[int] = Field(
        default=[40, 60, 80], description="Risk score thresholds to predict breaches"
    )


# =============================================================================
# Risk Trend Analyzer
# =============================================================================


class RiskTrendAnalyzer:
    """Analyzes risk trends with velocity, predictions, and portfolio analysis.

    Extends TemporalRiskTracker with:
    - Velocity and acceleration metrics
    - Trend predictions based on history
    - Portfolio-level risk aggregation
    - Subject attention flagging

    Example:
        analyzer = RiskTrendAnalyzer()

        # Analyze single subject
        summary = analyzer.analyze_subject_trend(
            entity_id=subject_id,
            history=risk_history,
        )

        # Analyze portfolio
        portfolio = analyzer.analyze_portfolio(
            subjects={id1: history1, id2: history2, ...}
        )

        # Get prediction
        prediction = analyzer.predict_risk(
            entity_id=subject_id,
            history=risk_history,
            horizon_days=30,
        )
    """

    def __init__(
        self,
        config: TrendAnalyzerConfig | None = None,
        tracker_config: TrackerConfig | None = None,
    ) -> None:
        """Initialize analyzer.

        Args:
            config: Trend analyzer configuration.
            tracker_config: Configuration for underlying tracker.
        """
        self.config = config or TrendAnalyzerConfig()
        self.tracker = TemporalRiskTracker(config=tracker_config)
        self._risk_level_thresholds = {
            RiskLevel.LOW: (0, 40),
            RiskLevel.MODERATE: (40, 60),
            RiskLevel.HIGH: (60, 80),
            RiskLevel.CRITICAL: (80, 100),
        }

    def calculate_velocity(
        self,
        history: list[RiskSnapshot],
        window_days: int | None = None,
    ) -> VelocityMetrics:
        """Calculate risk velocity and acceleration.

        Args:
            history: Chronological risk snapshots.
            window_days: Days to analyze (default from config).

        Returns:
            VelocityMetrics with velocity and acceleration data.
        """
        if len(history) < 2:
            return VelocityMetrics(data_points=len(history))

        window = window_days or self.config.velocity_window_days

        # Sort and filter to window
        snapshots = sorted(history, key=lambda s: s.assessed_at)
        cutoff = datetime.now(UTC) - timedelta(days=window)
        recent = [s for s in snapshots if s.assessed_at >= cutoff]

        if len(recent) < 2:
            recent = snapshots[-2:] if len(snapshots) >= 2 else snapshots

        # Calculate daily velocities
        velocities = []
        for i in range(1, len(recent)):
            prev = recent[i - 1]
            curr = recent[i]
            days = max(1, (curr.assessed_at - prev.assessed_at).days)
            velocity = (curr.overall_score - prev.overall_score) / days
            velocities.append(velocity)

        if not velocities:
            return VelocityMetrics(data_points=len(recent))

        current_velocity = velocities[-1]
        average_velocity = sum(velocities) / len(velocities)
        peak_velocity = max(abs(v) for v in velocities)

        # Calculate acceleration (change in velocity)
        acceleration = 0.0
        if len(velocities) >= 2:
            recent_velocities = velocities[-3:] if len(velocities) >= 3 else velocities
            first_half = recent_velocities[: len(recent_velocities) // 2 + 1]
            second_half = recent_velocities[len(recent_velocities) // 2 :]
            if first_half and second_half:
                first_avg = sum(first_half) / len(first_half)
                second_avg = sum(second_half) / len(second_half)
                acceleration = second_avg - first_avg

        is_accelerating = acceleration > self.config.acceleration_threshold
        is_decelerating = acceleration < -self.config.acceleration_threshold

        # Determine trajectory
        trajectory = self._determine_trajectory(
            current_velocity, acceleration, is_accelerating, is_decelerating
        )

        # Estimate days to next threshold
        current_score = recent[-1].overall_score if recent else 0
        days_to_threshold = self._estimate_days_to_threshold(current_score, current_velocity)

        return VelocityMetrics(
            current_velocity=current_velocity,
            average_velocity=average_velocity,
            peak_velocity=peak_velocity,
            acceleration=acceleration,
            is_accelerating=is_accelerating,
            is_decelerating=is_decelerating,
            measurement_period_days=window,
            data_points=len(recent),
            trajectory=trajectory,
            days_to_threshold=days_to_threshold,
        )

    def predict_risk(
        self,
        history: list[RiskSnapshot],
        entity_id: UUID | None = None,
        horizon_days: int | None = None,
    ) -> RiskPrediction:
        """Predict future risk based on history.

        Args:
            history: Chronological risk snapshots.
            entity_id: Optional entity ID.
            horizon_days: Days ahead to predict.

        Returns:
            RiskPrediction with predicted state.
        """
        horizon = horizon_days or self.config.prediction_horizon_days

        if len(history) < self.config.min_data_points_for_prediction:
            return RiskPrediction(
                entity_id=entity_id,
                confidence=PredictionConfidence.LOW,
                confidence_score=0.1,
                confidence_factors=["Insufficient history for prediction"],
            )

        snapshots = sorted(history, key=lambda s: s.assessed_at)
        current = snapshots[-1]

        # Calculate velocity for prediction
        velocity = self.calculate_velocity(history)

        # Simple linear extrapolation
        predicted_change = velocity.average_velocity * horizon
        predicted_score = max(0, min(100, int(current.overall_score + predicted_change)))

        # Determine predicted level
        predicted_level = self._score_to_level(predicted_score)

        # Calculate confidence
        confidence_score, confidence_factors = self._calculate_prediction_confidence(
            history, velocity
        )
        confidence = self._score_to_confidence(confidence_score)

        # Check for threshold breaches
        threshold_breach = False
        threshold_at_risk = None
        for threshold in sorted(self.config.risk_thresholds):
            if current.overall_score < threshold <= predicted_score:
                threshold_breach = True
                threshold_at_risk = threshold
                break
            elif current.overall_score > threshold >= predicted_score:
                # Crossed down - still note it
                threshold_at_risk = threshold

        return RiskPrediction(
            entity_id=entity_id,
            current_score=current.overall_score,
            current_level=current.risk_level,
            predicted_score=predicted_score,
            predicted_level=predicted_level,
            prediction_horizon_days=horizon,
            confidence=confidence,
            confidence_score=confidence_score,
            confidence_factors=confidence_factors,
            level_change_predicted=predicted_level != current.risk_level,
            threshold_breach_predicted=threshold_breach,
            threshold_at_risk=threshold_at_risk,
        )

    def analyze_subject_trend(
        self,
        entity_id: UUID,
        history: list[RiskSnapshot],
        include_prediction: bool = True,
    ) -> SubjectTrendSummary:
        """Comprehensive trend analysis for a single subject.

        Args:
            entity_id: Subject entity ID.
            history: Risk history snapshots.
            include_prediction: Whether to include prediction.

        Returns:
            SubjectTrendSummary with full analysis.
        """
        if not history:
            return SubjectTrendSummary(
                entity_id=entity_id,
                requires_attention=False,
                attention_reasons=["No risk history available"],
            )

        snapshots = sorted(history, key=lambda s: s.assessed_at)
        current = snapshots[-1]

        # Get trend from tracker
        trend = self.tracker.analyze_trend(history, entity_id)

        # Calculate velocity
        velocity = self.calculate_velocity(history)

        # Get prediction
        prediction = None
        if include_prediction and len(history) >= self.config.min_data_points_for_prediction:
            prediction = self.predict_risk(history, entity_id)

        # Detect signals
        signals = self.tracker.detect_evolution_signals(history, entity_id)

        # Determine if attention required
        requires_attention, attention_reasons = self._assess_attention_required(
            current, trend, velocity, signals, prediction
        )

        return SubjectTrendSummary(
            entity_id=entity_id,
            current_score=current.overall_score,
            current_level=current.risk_level,
            trend=trend,
            velocity=velocity,
            prediction=prediction,
            signals=signals,
            requires_attention=requires_attention,
            attention_reasons=attention_reasons,
        )

    def analyze_portfolio(
        self,
        subjects: dict[UUID, list[RiskSnapshot]],
        tenant_id: UUID | None = None,
    ) -> PortfolioRiskSummary:
        """Analyze risk across a portfolio of subjects.

        Args:
            subjects: Mapping of entity ID to risk history.
            tenant_id: Optional tenant ID.

        Returns:
            PortfolioRiskSummary with aggregate analysis.
        """
        if not subjects:
            return PortfolioRiskSummary(
                tenant_id=tenant_id,
                portfolio_risk_level=PortfolioRiskLevel.HEALTHY,
            )

        # Analyze each subject
        summaries: list[SubjectTrendSummary] = []
        for entity_id, history in subjects.items():
            summary = self.analyze_subject_trend(
                entity_id=entity_id,
                history=history,
                include_prediction=True,
            )
            summaries.append(summary)

        # Collect scores and levels
        scores = [s.current_score for s in summaries]
        levels = [s.current_level for s in summaries]

        # Risk distribution
        low_count = sum(1 for l in levels if l == RiskLevel.LOW)
        moderate_count = sum(1 for l in levels if l == RiskLevel.MODERATE)
        high_count = sum(1 for l in levels if l == RiskLevel.HIGH)
        critical_count = sum(1 for l in levels if l == RiskLevel.CRITICAL)

        # Aggregate metrics
        avg_score = sum(scores) / len(scores) if scores else 0.0
        sorted_scores = sorted(scores)
        median_score = (
            sorted_scores[len(sorted_scores) // 2]
            if sorted_scores
            else 0
        )
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores) if scores else 0.0
        std_dev = variance**0.5

        # Trend distribution
        improving = sum(1 for s in summaries if s.trend and s.trend.direction == TrendDirection.DECREASING)
        stable = sum(1 for s in summaries if s.trend and s.trend.direction == TrendDirection.STABLE)
        deteriorating = sum(1 for s in summaries if s.trend and s.trend.direction == TrendDirection.INCREASING)

        # Attention required
        attention_subjects = [s.entity_id for s in summaries if s.requires_attention]

        # Signal counts
        all_signals = [sig for s in summaries for sig in s.signals]
        from elile.investigation.finding_extractor import Severity

        critical_signals = sum(1 for sig in all_signals if sig.severity == Severity.CRITICAL)
        high_signals = sum(1 for sig in all_signals if sig.severity == Severity.HIGH)

        # Portfolio risk level
        total = len(subjects)
        critical_percent = critical_count / total if total > 0 else 0
        high_percent = (critical_count + high_count) / total if total > 0 else 0

        if critical_percent >= self.config.portfolio_critical_percent:
            portfolio_level = PortfolioRiskLevel.CRITICAL
        elif high_percent >= self.config.portfolio_high_percent:
            portfolio_level = PortfolioRiskLevel.CONCERNING
        elif deteriorating > stable + improving:
            portfolio_level = PortfolioRiskLevel.WATCHFUL
        else:
            portfolio_level = PortfolioRiskLevel.HEALTHY

        # Health score (0-1, higher is better)
        health_score = 1.0 - (
            0.4 * critical_percent
            + 0.3 * (high_count / total if total > 0 else 0)
            + 0.2 * (deteriorating / total if total > 0 else 0)
            + 0.1 * (len(attention_subjects) / total if total > 0 else 0)
        )
        health_score = max(0.0, min(1.0, health_score))

        logger.info(
            "Analyzed portfolio risk",
            tenant_id=str(tenant_id) if tenant_id else None,
            total_subjects=total,
            portfolio_level=portfolio_level.value,
            health_score=health_score,
        )

        return PortfolioRiskSummary(
            tenant_id=tenant_id,
            total_subjects=total,
            subjects_analyzed=len(summaries),
            low_risk_count=low_count,
            moderate_risk_count=moderate_count,
            high_risk_count=high_count,
            critical_risk_count=critical_count,
            average_score=avg_score,
            median_score=median_score,
            score_std_dev=std_dev,
            highest_score=max(scores) if scores else 0,
            lowest_score=min(scores) if scores else 0,
            improving_count=improving,
            stable_count=stable,
            deteriorating_count=deteriorating,
            portfolio_risk_level=portfolio_level,
            portfolio_health_score=health_score,
            attention_required_count=len(attention_subjects),
            attention_subjects=attention_subjects,
            total_signals=len(all_signals),
            critical_signals=critical_signals,
            high_signals=high_signals,
            analysis_period_days=self.config.default_lookback_days,
        )

    def _determine_trajectory(
        self,
        velocity: float,
        acceleration: float,
        is_accelerating: bool,
        is_decelerating: bool,
    ) -> RiskTrajectory:
        """Determine risk trajectory from velocity/acceleration."""
        if velocity > self.config.high_velocity_threshold:
            if is_accelerating:
                return RiskTrajectory.ACCELERATING_RISK
            return RiskTrajectory.DETERIORATING
        elif velocity < -self.config.high_velocity_threshold:
            if is_decelerating:  # Decelerating negative velocity = rapid improvement
                return RiskTrajectory.RAPID_IMPROVEMENT
            return RiskTrajectory.IMPROVING
        else:
            return RiskTrajectory.STABLE

    def _estimate_days_to_threshold(
        self,
        current_score: int,
        velocity: float,
    ) -> int | None:
        """Estimate days until next threshold breach."""
        if abs(velocity) < 0.01:
            return None

        for threshold in sorted(self.config.risk_thresholds):
            if velocity > 0 and current_score < threshold:
                days = int((threshold - current_score) / velocity)
                if days > 0:
                    return days
            elif velocity < 0 and current_score > threshold:
                days = int((current_score - threshold) / abs(velocity))
                if days > 0:
                    return days

        return None

    def _score_to_level(self, score: int) -> RiskLevel:
        """Convert score to risk level."""
        for level, (low, high) in self._risk_level_thresholds.items():
            if low <= score < high:
                return level
        return RiskLevel.CRITICAL if score >= 80 else RiskLevel.LOW

    def _score_to_confidence(self, score: float) -> PredictionConfidence:
        """Convert confidence score to level."""
        if score >= 0.7:
            return PredictionConfidence.HIGH
        elif score >= 0.4:
            return PredictionConfidence.MEDIUM
        else:
            return PredictionConfidence.LOW

    def _calculate_prediction_confidence(
        self,
        history: list[RiskSnapshot],
        velocity: VelocityMetrics,
    ) -> tuple[float, list[str]]:
        """Calculate prediction confidence."""
        factors = []
        score = 0.5  # Base confidence

        # More data points = higher confidence
        if velocity.data_points >= 10:
            score += 0.2
            factors.append("Sufficient history (10+ data points)")
        elif velocity.data_points >= 5:
            score += 0.1
            factors.append("Moderate history (5+ data points)")
        else:
            score -= 0.1
            factors.append("Limited history")

        # Stable velocity = higher confidence
        if abs(velocity.acceleration) < self.config.acceleration_threshold:
            score += 0.1
            factors.append("Stable velocity")
        else:
            score -= 0.1
            factors.append("Volatile velocity")

        # Consistent direction = higher confidence
        if history:
            scores = [s.overall_score for s in history]
            if len(scores) >= 3:
                changes = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
                same_direction = sum(
                    1 for i in range(1, len(changes)) if changes[i] * changes[i - 1] > 0
                )
                if same_direction >= len(changes) * 0.7:
                    score += 0.15
                    factors.append("Consistent trend direction")

        return max(0.1, min(0.95, score)), factors

    def _assess_attention_required(
        self,
        current: RiskSnapshot,
        trend: RiskTrend | None,
        velocity: VelocityMetrics | None,
        signals: list[EvolutionSignal],
        prediction: RiskPrediction | None,
    ) -> tuple[bool, list[str]]:
        """Assess if subject requires attention."""
        reasons = []

        # High or critical risk level
        if current.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            reasons.append(f"Current risk level: {current.risk_level.value}")

        # High velocity
        if velocity and abs(velocity.current_velocity) > self.config.high_velocity_threshold:
            direction = "increasing" if velocity.current_velocity > 0 else "decreasing"
            reasons.append(f"Rapid risk {direction}")

        # Accelerating risk
        if velocity and velocity.is_accelerating and velocity.current_velocity > 0:
            reasons.append("Risk acceleration detected")

        # Critical or high severity signals
        from elile.investigation.finding_extractor import Severity

        critical_signals = [s for s in signals if s.severity == Severity.CRITICAL]
        high_signals = [s for s in signals if s.severity == Severity.HIGH]
        if critical_signals:
            reasons.append(f"{len(critical_signals)} critical signal(s)")
        if high_signals:
            reasons.append(f"{len(high_signals)} high-priority signal(s)")

        # Predicted threshold breach
        if prediction and prediction.threshold_breach_predicted:
            reasons.append(f"Predicted breach of {prediction.threshold_at_risk} threshold")

        return len(reasons) > 0, reasons


# =============================================================================
# Factory Function
# =============================================================================


def create_risk_trend_analyzer(
    config: TrendAnalyzerConfig | None = None,
    tracker_config: TrackerConfig | None = None,
) -> RiskTrendAnalyzer:
    """Create a risk trend analyzer with optional configs.

    Args:
        config: Trend analyzer configuration.
        tracker_config: Configuration for underlying tracker.

    Returns:
        Configured RiskTrendAnalyzer instance.
    """
    return RiskTrendAnalyzer(config=config, tracker_config=tracker_config)
