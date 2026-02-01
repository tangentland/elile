"""Temporal Risk Tracker for monitoring risk changes over time.

This module implements risk change detection and evolution signal generation
for ongoing employee monitoring. It tracks:
- Risk score deltas between timepoints
- Trending patterns (upward/downward)
- Sudden risk spikes
- Category-specific changes
- Evolution signals for alerting
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.investigation.finding_extractor import Severity
from elile.risk.risk_scorer import Recommendation, RiskLevel, RiskScore

logger = structlog.get_logger()


# =============================================================================
# Enums
# =============================================================================


class TrendDirection(str, Enum):
    """Direction of risk trend."""

    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


class EvolutionSignalType(str, Enum):
    """Types of risk evolution signals."""

    # Trend signals
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RAPID_ESCALATION = "rapid_escalation"
    GRADUAL_IMPROVEMENT = "gradual_improvement"

    # Spike signals
    SUDDEN_SPIKE = "sudden_spike"
    SUDDEN_DROP = "sudden_drop"

    # Level transitions
    LEVEL_ESCALATION = "level_escalation"
    LEVEL_DEESCALATION = "level_deescalation"

    # Category signals
    CATEGORY_EMERGENCE = "category_emergence"
    CATEGORY_RESOLUTION = "category_resolution"
    MULTI_CATEGORY_INCREASE = "multi_category_increase"

    # Pattern signals
    RECURRING_FINDINGS = "recurring_findings"
    ACCELERATING_ISSUES = "accelerating_issues"
    DORMANCY_BROKEN = "dormancy_broken"

    # Threshold signals
    THRESHOLD_BREACH = "threshold_breach"
    APPROACHING_THRESHOLD = "approaching_threshold"


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class RiskSnapshot:
    """A point-in-time risk assessment snapshot.

    Used to build risk history for temporal analysis.
    """

    snapshot_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None
    screening_id: UUID | None = None

    # Risk scores
    overall_score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    recommendation: Recommendation = Recommendation.PROCEED

    # Category breakdown
    category_scores: dict[str, float] = field(default_factory=dict)

    # Findings at this point
    findings_count: int = 0
    critical_count: int = 0
    high_count: int = 0

    # Timing
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "snapshot_id": str(self.snapshot_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "overall_score": self.overall_score,
            "risk_level": self.risk_level.value,
            "recommendation": self.recommendation.value,
            "category_scores": self.category_scores,
            "findings_count": self.findings_count,
            "critical_count": self.critical_count,
            "high_count": self.high_count,
            "assessed_at": self.assessed_at.isoformat(),
        }

    @classmethod
    def from_risk_score(
        cls, risk_score: RiskScore, entity_id: UUID | None = None, screening_id: UUID | None = None
    ) -> "RiskSnapshot":
        """Create snapshot from RiskScore."""
        # Convert FindingCategory dict to string dict
        category_scores = {
            (cat.value if hasattr(cat, "value") else str(cat)): score
            for cat, score in risk_score.category_scores.items()
        }
        # Extract counts from contributing_factors if available
        factors = risk_score.contributing_factors
        findings_count = int(factors.get("findings_count", 0))
        critical_count = int(factors.get("critical_count", 0))
        high_count = int(factors.get("high_count", 0))

        return cls(
            entity_id=entity_id or risk_score.entity_id,
            screening_id=screening_id or risk_score.screening_id,
            overall_score=risk_score.overall_score,
            risk_level=risk_score.risk_level,
            recommendation=risk_score.recommendation,
            category_scores=category_scores,
            findings_count=findings_count,
            critical_count=critical_count,
            high_count=high_count,
            assessed_at=risk_score.scored_at,
        )


@dataclass
class CategoryDelta:
    """Change in a specific risk category."""

    category: str
    previous_score: float
    current_score: float
    delta: float
    is_new: bool = False
    is_resolved: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category,
            "previous_score": self.previous_score,
            "current_score": self.current_score,
            "delta": self.delta,
            "is_new": self.is_new,
            "is_resolved": self.is_resolved,
        }


@dataclass
class RiskDelta:
    """Change in risk between two timepoints.

    Captures the difference between a baseline and current risk assessment.
    """

    delta_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None

    # Score changes
    previous_score: int = 0
    current_score: int = 0
    score_change: int = 0
    score_change_percent: float = 0.0

    # Level changes
    previous_level: RiskLevel = RiskLevel.LOW
    current_level: RiskLevel = RiskLevel.LOW
    level_changed: bool = False
    level_escalated: bool = False
    level_deescalated: bool = False

    # Recommendation changes
    previous_recommendation: Recommendation = Recommendation.PROCEED
    current_recommendation: Recommendation = Recommendation.PROCEED
    recommendation_changed: bool = False

    # Findings changes
    findings_added: int = 0
    findings_removed: int = 0
    net_findings_change: int = 0

    # Category changes
    category_deltas: list[CategoryDelta] = field(default_factory=list)
    new_categories: list[str] = field(default_factory=list)
    resolved_categories: list[str] = field(default_factory=list)

    # Timing
    baseline_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    current_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    time_span: timedelta = field(default_factory=lambda: timedelta())

    # Assessment
    is_significant: bool = False
    significance_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "delta_id": str(self.delta_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "previous_score": self.previous_score,
            "current_score": self.current_score,
            "score_change": self.score_change,
            "score_change_percent": self.score_change_percent,
            "previous_level": self.previous_level.value,
            "current_level": self.current_level.value,
            "level_changed": self.level_changed,
            "level_escalated": self.level_escalated,
            "level_deescalated": self.level_deescalated,
            "previous_recommendation": self.previous_recommendation.value,
            "current_recommendation": self.current_recommendation.value,
            "recommendation_changed": self.recommendation_changed,
            "findings_added": self.findings_added,
            "findings_removed": self.findings_removed,
            "net_findings_change": self.net_findings_change,
            "category_deltas": [cd.to_dict() for cd in self.category_deltas],
            "new_categories": self.new_categories,
            "resolved_categories": self.resolved_categories,
            "baseline_time": self.baseline_time.isoformat(),
            "current_time": self.current_time.isoformat(),
            "time_span_days": self.time_span.days,
            "is_significant": self.is_significant,
            "significance_reason": self.significance_reason,
        }


@dataclass
class EvolutionSignal:
    """A detected risk evolution signal.

    Signals represent important patterns or changes that may require attention.
    """

    signal_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None

    signal_type: EvolutionSignalType = EvolutionSignalType.TRENDING_UP
    severity: Severity = Severity.MEDIUM
    confidence: float = 0.5

    description: str = ""
    contributing_factors: list[str] = field(default_factory=list)
    pattern_signature: str | None = None

    # Context
    score_at_detection: int = 0
    level_at_detection: RiskLevel = RiskLevel.LOW
    time_span_analyzed: timedelta = field(default_factory=lambda: timedelta())

    # Recommendations
    recommended_action: str = ""
    urgency: str = "normal"  # immediate, urgent, normal, low

    # Timing
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "signal_id": str(self.signal_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "signal_type": self.signal_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "description": self.description,
            "contributing_factors": self.contributing_factors,
            "pattern_signature": self.pattern_signature,
            "score_at_detection": self.score_at_detection,
            "level_at_detection": self.level_at_detection.value,
            "time_span_analyzed_days": self.time_span_analyzed.days,
            "recommended_action": self.recommended_action,
            "urgency": self.urgency,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class RiskTrend:
    """Overall risk trend analysis."""

    trend_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None

    # Trend direction
    direction: TrendDirection = TrendDirection.STABLE
    direction_confidence: float = 0.5

    # Trend statistics
    average_score: float = 0.0
    min_score: int = 0
    max_score: int = 0
    score_variance: float = 0.0
    score_std_dev: float = 0.0

    # Rate of change
    average_daily_change: float = 0.0
    peak_daily_change: float = 0.0

    # Timespan
    analysis_start: datetime = field(default_factory=lambda: datetime.now(UTC))
    analysis_end: datetime = field(default_factory=lambda: datetime.now(UTC))
    data_points: int = 0

    # Signals detected during trend analysis
    signals: list[EvolutionSignal] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trend_id": str(self.trend_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "direction": self.direction.value,
            "direction_confidence": self.direction_confidence,
            "average_score": self.average_score,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "score_variance": self.score_variance,
            "score_std_dev": self.score_std_dev,
            "average_daily_change": self.average_daily_change,
            "peak_daily_change": self.peak_daily_change,
            "analysis_start": self.analysis_start.isoformat(),
            "analysis_end": self.analysis_end.isoformat(),
            "data_points": self.data_points,
            "signals": [s.to_dict() for s in self.signals],
        }


# =============================================================================
# Configuration
# =============================================================================


class TrackerConfig(BaseModel):
    """Configuration for temporal risk tracker."""

    # Significance thresholds
    significant_score_change: int = Field(
        default=10, ge=1, le=50, description="Score change to consider significant"
    )
    significant_percent_change: float = Field(
        default=0.15, ge=0.01, le=1.0, description="Percent change to consider significant"
    )

    # Spike detection
    spike_threshold: int = Field(
        default=15, ge=5, le=50, description="Score change to consider a spike"
    )
    spike_window_days: int = Field(
        default=7, ge=1, le=90, description="Window for spike detection"
    )

    # Trend detection
    trend_window_days: int = Field(
        default=30, ge=7, le=365, description="Window for trend analysis"
    )
    trend_min_data_points: int = Field(
        default=3, ge=2, le=20, description="Minimum snapshots for trend"
    )
    trend_confidence_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Confidence to confirm trend"
    )

    # Evolution signal thresholds
    rapid_escalation_threshold: int = Field(
        default=20, ge=5, le=50, description="Score increase for rapid escalation"
    )
    rapid_escalation_days: int = Field(
        default=14, ge=1, le=60, description="Days for rapid escalation detection"
    )

    # Threshold alerting
    alert_thresholds: list[int] = Field(
        default=[40, 60, 80],
        description="Score thresholds that trigger alerts when crossed",
    )
    approaching_threshold_buffer: int = Field(
        default=5, ge=1, le=20, description="Buffer before threshold for warning"
    )

    # Dormancy detection
    dormancy_period_days: int = Field(
        default=180, ge=30, le=730, description="Days of stability to consider dormant"
    )
    dormancy_max_change: int = Field(
        default=5, ge=1, le=20, description="Max score change during dormancy"
    )


# =============================================================================
# Temporal Risk Tracker
# =============================================================================


class TemporalRiskTracker:
    """Tracks risk changes over time and detects evolution signals.

    The tracker:
    1. Calculates risk deltas between timepoints
    2. Detects trending patterns (up/down/volatile)
    3. Identifies sudden spikes
    4. Generates evolution signals for alerting
    5. Tracks category-specific changes

    Example:
        tracker = TemporalRiskTracker()

        # Calculate delta between baseline and current
        delta = tracker.calculate_risk_delta(baseline_snapshot, current_snapshot)

        # Analyze risk history for signals
        signals = tracker.detect_evolution_signals(risk_history)

        # Get overall trend
        trend = tracker.analyze_trend(risk_history)
    """

    def __init__(self, config: TrackerConfig | None = None) -> None:
        """Initialize tracker.

        Args:
            config: Optional tracker configuration.
        """
        self.config = config or TrackerConfig()
        self._risk_level_values = {
            RiskLevel.LOW: 0,
            RiskLevel.MODERATE: 1,
            RiskLevel.HIGH: 2,
            RiskLevel.CRITICAL: 3,
        }

    def calculate_risk_delta(
        self,
        baseline: RiskSnapshot | RiskScore,
        current: RiskSnapshot | RiskScore,
    ) -> RiskDelta:
        """Calculate change in risk between two timepoints.

        Args:
            baseline: Previous risk assessment.
            current: Current risk assessment.

        Returns:
            RiskDelta with detailed change analysis.
        """
        # Convert to snapshots if needed
        if isinstance(baseline, RiskScore):
            baseline = RiskSnapshot.from_risk_score(baseline)
        if isinstance(current, RiskScore):
            current = RiskSnapshot.from_risk_score(current)

        # Calculate score change
        score_change = current.overall_score - baseline.overall_score
        score_change_percent = (
            score_change / baseline.overall_score if baseline.overall_score > 0 else 0.0
        )

        # Determine level changes
        level_changed = baseline.risk_level != current.risk_level
        prev_level_val = self._risk_level_values[baseline.risk_level]
        curr_level_val = self._risk_level_values[current.risk_level]
        level_escalated = curr_level_val > prev_level_val
        level_deescalated = curr_level_val < prev_level_val

        # Calculate findings changes
        net_findings_change = current.findings_count - baseline.findings_count
        findings_added = max(0, net_findings_change)
        findings_removed = max(0, -net_findings_change)

        # Calculate category deltas
        category_deltas = self._calculate_category_deltas(
            baseline.category_scores, current.category_scores
        )

        # Identify new and resolved categories
        new_categories = [cd.category for cd in category_deltas if cd.is_new]
        resolved_categories = [cd.category for cd in category_deltas if cd.is_resolved]

        # Calculate time span
        time_span = current.assessed_at - baseline.assessed_at

        # Determine significance
        is_significant, significance_reason = self._assess_significance(
            score_change=score_change,
            score_change_percent=score_change_percent,
            level_changed=level_changed,
            new_categories=new_categories,
        )

        delta = RiskDelta(
            entity_id=current.entity_id,
            previous_score=baseline.overall_score,
            current_score=current.overall_score,
            score_change=score_change,
            score_change_percent=score_change_percent,
            previous_level=baseline.risk_level,
            current_level=current.risk_level,
            level_changed=level_changed,
            level_escalated=level_escalated,
            level_deescalated=level_deescalated,
            previous_recommendation=baseline.recommendation,
            current_recommendation=current.recommendation,
            recommendation_changed=baseline.recommendation != current.recommendation,
            findings_added=findings_added,
            findings_removed=findings_removed,
            net_findings_change=net_findings_change,
            category_deltas=category_deltas,
            new_categories=new_categories,
            resolved_categories=resolved_categories,
            baseline_time=baseline.assessed_at,
            current_time=current.assessed_at,
            time_span=time_span,
            is_significant=is_significant,
            significance_reason=significance_reason,
        )

        logger.info(
            "Calculated risk delta",
            entity_id=str(current.entity_id) if current.entity_id else None,
            score_change=score_change,
            level_changed=level_changed,
            is_significant=is_significant,
        )

        return delta

    def detect_evolution_signals(
        self,
        risk_history: list[RiskSnapshot | RiskScore],
        entity_id: UUID | None = None,
    ) -> list[EvolutionSignal]:
        """Detect risk evolution patterns from history.

        Args:
            risk_history: Chronological list of risk snapshots.
            entity_id: Optional entity ID for signals.

        Returns:
            List of detected evolution signals.
        """
        if len(risk_history) < 2:
            return []

        # Convert to snapshots and sort chronologically
        snapshots = [
            s if isinstance(s, RiskSnapshot) else RiskSnapshot.from_risk_score(s)
            for s in risk_history
        ]
        snapshots.sort(key=lambda s: s.assessed_at)

        signals: list[EvolutionSignal] = []
        current = snapshots[-1]

        # Detect trending patterns
        trend_signals = self._detect_trend_signals(snapshots, entity_id)
        signals.extend(trend_signals)

        # Detect spikes
        spike_signals = self._detect_spike_signals(snapshots, entity_id)
        signals.extend(spike_signals)

        # Detect level transitions
        level_signals = self._detect_level_signals(snapshots, entity_id)
        signals.extend(level_signals)

        # Detect category changes
        category_signals = self._detect_category_signals(snapshots, entity_id)
        signals.extend(category_signals)

        # Detect threshold breaches
        threshold_signals = self._detect_threshold_signals(snapshots, entity_id)
        signals.extend(threshold_signals)

        # Detect dormancy breaks
        dormancy_signals = self._detect_dormancy_signals(snapshots, entity_id)
        signals.extend(dormancy_signals)

        logger.info(
            "Detected evolution signals",
            entity_id=str(entity_id) if entity_id else None,
            history_length=len(snapshots),
            signals_detected=len(signals),
        )

        return signals

    def analyze_trend(
        self,
        risk_history: list[RiskSnapshot | RiskScore],
        entity_id: UUID | None = None,
    ) -> RiskTrend:
        """Analyze overall risk trend from history.

        Args:
            risk_history: Chronological list of risk snapshots.
            entity_id: Optional entity ID.

        Returns:
            RiskTrend with comprehensive trend analysis.
        """
        # Convert and sort
        snapshots = [
            s if isinstance(s, RiskSnapshot) else RiskSnapshot.from_risk_score(s)
            for s in risk_history
        ]
        snapshots.sort(key=lambda s: s.assessed_at)

        if not snapshots:
            return RiskTrend(entity_id=entity_id)

        # Extract scores
        scores = [s.overall_score for s in snapshots]

        # Calculate statistics
        average_score = sum(scores) / len(scores)
        min_score = min(scores)
        max_score = max(scores)

        # Calculate variance and std dev
        variance = sum((s - average_score) ** 2 for s in scores) / len(scores) if scores else 0.0
        std_dev = variance**0.5

        # Calculate daily changes
        daily_changes = self._calculate_daily_changes(snapshots)
        avg_daily_change = sum(daily_changes) / len(daily_changes) if daily_changes else 0.0
        peak_daily_change = max(abs(c) for c in daily_changes) if daily_changes else 0.0

        # Determine trend direction
        direction, direction_confidence = self._determine_trend_direction(snapshots)

        # Detect signals
        signals = self.detect_evolution_signals(snapshots, entity_id)

        trend = RiskTrend(
            entity_id=entity_id,
            direction=direction,
            direction_confidence=direction_confidence,
            average_score=average_score,
            min_score=min_score,
            max_score=max_score,
            score_variance=variance,
            score_std_dev=std_dev,
            average_daily_change=avg_daily_change,
            peak_daily_change=peak_daily_change,
            analysis_start=snapshots[0].assessed_at,
            analysis_end=snapshots[-1].assessed_at,
            data_points=len(snapshots),
            signals=signals,
        )

        logger.info(
            "Analyzed risk trend",
            entity_id=str(entity_id) if entity_id else None,
            direction=direction.value,
            average_score=average_score,
            data_points=len(snapshots),
        )

        return trend

    def _calculate_category_deltas(
        self,
        previous: dict[str, float],
        current: dict[str, float],
    ) -> list[CategoryDelta]:
        """Calculate deltas for each category."""
        all_categories = set(previous.keys()) | set(current.keys())
        deltas = []

        for category in all_categories:
            prev_score = previous.get(category, 0.0)
            curr_score = current.get(category, 0.0)
            delta = curr_score - prev_score

            is_new = category not in previous and curr_score > 0
            is_resolved = category in previous and prev_score > 0 and curr_score == 0

            deltas.append(
                CategoryDelta(
                    category=category,
                    previous_score=prev_score,
                    current_score=curr_score,
                    delta=delta,
                    is_new=is_new,
                    is_resolved=is_resolved,
                )
            )

        return deltas

    def _assess_significance(
        self,
        score_change: int,
        score_change_percent: float,
        level_changed: bool,
        new_categories: list[str],
    ) -> tuple[bool, str]:
        """Assess if a change is significant."""
        reasons = []

        if abs(score_change) >= self.config.significant_score_change:
            reasons.append(f"Score changed by {score_change} points")

        if abs(score_change_percent) >= self.config.significant_percent_change:
            reasons.append(f"Score changed by {score_change_percent:.1%}")

        if level_changed:
            reasons.append("Risk level changed")

        if new_categories:
            reasons.append(f"New risk categories: {', '.join(new_categories)}")

        is_significant = len(reasons) > 0
        reason = "; ".join(reasons) if reasons else ""

        return is_significant, reason

    def _detect_trend_signals(
        self,
        snapshots: list[RiskSnapshot],
        entity_id: UUID | None,
    ) -> list[EvolutionSignal]:
        """Detect trending pattern signals."""
        signals = []

        if len(snapshots) < self.config.trend_min_data_points:
            return signals

        # Get recent snapshots within trend window
        cutoff = datetime.now(UTC) - timedelta(days=self.config.trend_window_days)
        recent = [s for s in snapshots if s.assessed_at >= cutoff]

        if len(recent) < self.config.trend_min_data_points:
            recent = snapshots[-self.config.trend_min_data_points :]

        scores = [s.overall_score for s in recent]
        current = snapshots[-1]

        # Check for trending up
        if self._is_trending_up(scores):
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.TRENDING_UP,
                    severity=Severity.MEDIUM,
                    confidence=0.7,
                    description=f"Risk trending upward over {len(recent)} assessments",
                    contributing_factors=[
                        f"Score increased from {scores[0]} to {scores[-1]}",
                        f"Consistent upward trend detected",
                    ],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=recent[-1].assessed_at - recent[0].assessed_at,
                    recommended_action="Review recent findings and monitor closely",
                    urgency="normal",
                )
            )

        # Check for trending down
        elif self._is_trending_down(scores):
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.TRENDING_DOWN,
                    severity=Severity.LOW,
                    confidence=0.7,
                    description=f"Risk trending downward over {len(recent)} assessments",
                    contributing_factors=[
                        f"Score decreased from {scores[0]} to {scores[-1]}",
                        f"Consistent downward trend detected",
                    ],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=recent[-1].assessed_at - recent[0].assessed_at,
                    recommended_action="Continue monitoring - positive trajectory",
                    urgency="low",
                )
            )

        # Check for rapid escalation
        if len(recent) >= 2:
            first = recent[0]
            last = recent[-1]
            days = (last.assessed_at - first.assessed_at).days or 1

            if (
                days <= self.config.rapid_escalation_days
                and last.overall_score - first.overall_score >= self.config.rapid_escalation_threshold
            ):
                signals.append(
                    EvolutionSignal(
                        entity_id=entity_id,
                        signal_type=EvolutionSignalType.RAPID_ESCALATION,
                        severity=Severity.HIGH,
                        confidence=0.85,
                        description=f"Rapid risk escalation: +{last.overall_score - first.overall_score} points in {days} days",
                        contributing_factors=[
                            f"Score jumped from {first.overall_score} to {last.overall_score}",
                            f"Change occurred within {days} days",
                        ],
                        score_at_detection=current.overall_score,
                        level_at_detection=current.risk_level,
                        time_span_analyzed=last.assessed_at - first.assessed_at,
                        recommended_action="Immediate review recommended",
                        urgency="urgent",
                    )
                )

        return signals

    def _detect_spike_signals(
        self,
        snapshots: list[RiskSnapshot],
        entity_id: UUID | None,
    ) -> list[EvolutionSignal]:
        """Detect sudden spike signals."""
        signals = []

        if len(snapshots) < 2:
            return signals

        current = snapshots[-1]
        cutoff = datetime.now(UTC) - timedelta(days=self.config.spike_window_days)

        # Find baseline (earliest snapshot in window or most recent before window)
        baseline = None
        for s in reversed(snapshots[:-1]):
            if s.assessed_at >= cutoff:
                continue
            baseline = s
            break

        if not baseline:
            baseline = snapshots[0] if len(snapshots) > 1 else snapshots[-1]

        score_change = current.overall_score - baseline.overall_score

        # Check for sudden spike
        if score_change >= self.config.spike_threshold:
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.SUDDEN_SPIKE,
                    severity=Severity.CRITICAL if score_change >= 25 else Severity.HIGH,
                    confidence=0.9,
                    description=f"Sudden risk spike: +{score_change} points",
                    contributing_factors=[
                        f"Score jumped from {baseline.overall_score} to {current.overall_score}",
                        f"Change detected within {self.config.spike_window_days} day window",
                    ],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=current.assessed_at - baseline.assessed_at,
                    recommended_action="Urgent review required - significant risk increase",
                    urgency="immediate" if score_change >= 25 else "urgent",
                )
            )

        # Check for sudden drop
        elif score_change <= -self.config.spike_threshold:
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.SUDDEN_DROP,
                    severity=Severity.LOW,
                    confidence=0.8,
                    description=f"Sudden risk drop: {score_change} points",
                    contributing_factors=[
                        f"Score dropped from {baseline.overall_score} to {current.overall_score}",
                        f"Change detected within {self.config.spike_window_days} day window",
                    ],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=current.assessed_at - baseline.assessed_at,
                    recommended_action="Verify findings resolution - confirm positive change",
                    urgency="normal",
                )
            )

        return signals

    def _detect_level_signals(
        self,
        snapshots: list[RiskSnapshot],
        entity_id: UUID | None,
    ) -> list[EvolutionSignal]:
        """Detect risk level transition signals."""
        signals = []

        if len(snapshots) < 2:
            return signals

        current = snapshots[-1]
        previous = snapshots[-2]

        if current.risk_level == previous.risk_level:
            return signals

        curr_val = self._risk_level_values[current.risk_level]
        prev_val = self._risk_level_values[previous.risk_level]

        if curr_val > prev_val:
            severity = Severity.HIGH if current.risk_level == RiskLevel.CRITICAL else Severity.MEDIUM
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.LEVEL_ESCALATION,
                    severity=severity,
                    confidence=0.95,
                    description=f"Risk level escalated: {previous.risk_level.value} → {current.risk_level.value}",
                    contributing_factors=[
                        f"Previous level: {previous.risk_level.value}",
                        f"Current level: {current.risk_level.value}",
                        f"Score: {current.overall_score}",
                    ],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=current.assessed_at - previous.assessed_at,
                    recommended_action="Review escalation factors and update monitoring",
                    urgency="urgent" if current.risk_level == RiskLevel.CRITICAL else "normal",
                )
            )
        else:
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.LEVEL_DEESCALATION,
                    severity=Severity.LOW,
                    confidence=0.95,
                    description=f"Risk level de-escalated: {previous.risk_level.value} → {current.risk_level.value}",
                    contributing_factors=[
                        f"Previous level: {previous.risk_level.value}",
                        f"Current level: {current.risk_level.value}",
                        f"Score: {current.overall_score}",
                    ],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=current.assessed_at - previous.assessed_at,
                    recommended_action="Update monitoring cadence to reflect lower risk",
                    urgency="low",
                )
            )

        return signals

    def _detect_category_signals(
        self,
        snapshots: list[RiskSnapshot],
        entity_id: UUID | None,
    ) -> list[EvolutionSignal]:
        """Detect category-related signals."""
        signals = []

        if len(snapshots) < 2:
            return signals

        current = snapshots[-1]
        previous = snapshots[-2]

        # Find new categories
        new_cats = set(current.category_scores.keys()) - set(previous.category_scores.keys())
        for cat in new_cats:
            if current.category_scores.get(cat, 0) > 0:
                signals.append(
                    EvolutionSignal(
                        entity_id=entity_id,
                        signal_type=EvolutionSignalType.CATEGORY_EMERGENCE,
                        severity=Severity.MEDIUM,
                        confidence=0.85,
                        description=f"New risk category emerged: {cat}",
                        contributing_factors=[
                            f"Category: {cat}",
                            f"Score: {current.category_scores[cat]:.2f}",
                        ],
                        score_at_detection=current.overall_score,
                        level_at_detection=current.risk_level,
                        time_span_analyzed=current.assessed_at - previous.assessed_at,
                        recommended_action=f"Review {cat} findings",
                        urgency="normal",
                    )
                )

        # Find resolved categories
        resolved_cats = set(previous.category_scores.keys()) - set(current.category_scores.keys())
        for cat in resolved_cats:
            if previous.category_scores.get(cat, 0) > 0:
                signals.append(
                    EvolutionSignal(
                        entity_id=entity_id,
                        signal_type=EvolutionSignalType.CATEGORY_RESOLUTION,
                        severity=Severity.LOW,
                        confidence=0.85,
                        description=f"Risk category resolved: {cat}",
                        contributing_factors=[
                            f"Category: {cat}",
                            f"Previous score: {previous.category_scores[cat]:.2f}",
                        ],
                        score_at_detection=current.overall_score,
                        level_at_detection=current.risk_level,
                        time_span_analyzed=current.assessed_at - previous.assessed_at,
                        recommended_action="Verify resolution is complete",
                        urgency="low",
                    )
                )

        # Check for multi-category increase
        increased_cats = [
            cat
            for cat in current.category_scores
            if current.category_scores.get(cat, 0) > previous.category_scores.get(cat, 0) * 1.2
        ]
        if len(increased_cats) >= 3:
            signals.append(
                EvolutionSignal(
                    entity_id=entity_id,
                    signal_type=EvolutionSignalType.MULTI_CATEGORY_INCREASE,
                    severity=Severity.HIGH,
                    confidence=0.8,
                    description=f"Multiple risk categories increased: {', '.join(increased_cats)}",
                    contributing_factors=[f"Categories with increases: {len(increased_cats)}"],
                    score_at_detection=current.overall_score,
                    level_at_detection=current.risk_level,
                    time_span_analyzed=current.assessed_at - previous.assessed_at,
                    recommended_action="Comprehensive review - multiple risk factors increasing",
                    urgency="urgent",
                )
            )

        return signals

    def _detect_threshold_signals(
        self,
        snapshots: list[RiskSnapshot],
        entity_id: UUID | None,
    ) -> list[EvolutionSignal]:
        """Detect threshold-related signals."""
        signals = []

        if len(snapshots) < 2:
            return signals

        current = snapshots[-1]
        previous = snapshots[-2]

        for threshold in self.config.alert_thresholds:
            # Check for threshold breach
            if previous.overall_score < threshold <= current.overall_score:
                signals.append(
                    EvolutionSignal(
                        entity_id=entity_id,
                        signal_type=EvolutionSignalType.THRESHOLD_BREACH,
                        severity=Severity.HIGH if threshold >= 60 else Severity.MEDIUM,
                        confidence=0.95,
                        description=f"Risk threshold breached: {threshold}",
                        contributing_factors=[
                            f"Previous score: {previous.overall_score}",
                            f"Current score: {current.overall_score}",
                            f"Threshold: {threshold}",
                        ],
                        score_at_detection=current.overall_score,
                        level_at_detection=current.risk_level,
                        time_span_analyzed=current.assessed_at - previous.assessed_at,
                        recommended_action=f"Review - score crossed {threshold} threshold",
                        urgency="urgent" if threshold >= 60 else "normal",
                    )
                )

            # Check for approaching threshold
            elif (
                current.overall_score >= threshold - self.config.approaching_threshold_buffer
                and current.overall_score < threshold
                and previous.overall_score < threshold - self.config.approaching_threshold_buffer
            ):
                signals.append(
                    EvolutionSignal(
                        entity_id=entity_id,
                        signal_type=EvolutionSignalType.APPROACHING_THRESHOLD,
                        severity=Severity.LOW,
                        confidence=0.7,
                        description=f"Approaching risk threshold: {threshold}",
                        contributing_factors=[
                            f"Current score: {current.overall_score}",
                            f"Threshold: {threshold}",
                            f"Buffer: {threshold - current.overall_score} points",
                        ],
                        score_at_detection=current.overall_score,
                        level_at_detection=current.risk_level,
                        time_span_analyzed=current.assessed_at - previous.assessed_at,
                        recommended_action=f"Monitor closely - approaching {threshold} threshold",
                        urgency="normal",
                    )
                )

        return signals

    def _detect_dormancy_signals(
        self,
        snapshots: list[RiskSnapshot],
        entity_id: UUID | None,
    ) -> list[EvolutionSignal]:
        """Detect dormancy-break signals."""
        signals = []

        if len(snapshots) < 3:
            return signals

        current = snapshots[-1]

        # Look for a period of stability followed by change
        dormancy_cutoff = current.assessed_at - timedelta(days=self.config.dormancy_period_days)
        dormant_snapshots = [s for s in snapshots[:-1] if s.assessed_at >= dormancy_cutoff]

        if len(dormant_snapshots) < 2:
            return signals

        # Check if period was dormant (low variance)
        dormant_scores = [s.overall_score for s in dormant_snapshots]
        dormant_range = max(dormant_scores) - min(dormant_scores)

        if dormant_range <= self.config.dormancy_max_change:
            avg_dormant = sum(dormant_scores) / len(dormant_scores)
            change_from_dormant = abs(current.overall_score - avg_dormant)

            if change_from_dormant >= self.config.significant_score_change:
                signals.append(
                    EvolutionSignal(
                        entity_id=entity_id,
                        signal_type=EvolutionSignalType.DORMANCY_BROKEN,
                        severity=Severity.HIGH if current.overall_score > avg_dormant else Severity.MEDIUM,
                        confidence=0.75,
                        description=f"Risk emerged from dormancy: change of {change_from_dormant:.0f} points",
                        contributing_factors=[
                            f"Dormant period: {self.config.dormancy_period_days} days",
                            f"Dormant average: {avg_dormant:.0f}",
                            f"Current score: {current.overall_score}",
                        ],
                        score_at_detection=current.overall_score,
                        level_at_detection=current.risk_level,
                        time_span_analyzed=timedelta(days=self.config.dormancy_period_days),
                        recommended_action="Investigate cause of change after stable period",
                        urgency="urgent" if current.overall_score > avg_dormant else "normal",
                    )
                )

        return signals

    def _is_trending_up(self, scores: list[int]) -> bool:
        """Check if scores show upward trend."""
        if len(scores) < 3:
            return False

        # Simple linear trend check - compare first half avg to second half avg
        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        # Also check if final score is higher than first
        return second_avg > first_avg + 3 and scores[-1] > scores[0]

    def _is_trending_down(self, scores: list[int]) -> bool:
        """Check if scores show downward trend."""
        if len(scores) < 3:
            return False

        mid = len(scores) // 2
        first_half = scores[:mid]
        second_half = scores[mid:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        return second_avg < first_avg - 3 and scores[-1] < scores[0]

    def _calculate_daily_changes(self, snapshots: list[RiskSnapshot]) -> list[float]:
        """Calculate score changes per day."""
        if len(snapshots) < 2:
            return []

        changes = []
        for i in range(1, len(snapshots)):
            prev = snapshots[i - 1]
            curr = snapshots[i]
            days = (curr.assessed_at - prev.assessed_at).days or 1
            daily_change = (curr.overall_score - prev.overall_score) / days
            changes.append(daily_change)

        return changes

    def _determine_trend_direction(
        self, snapshots: list[RiskSnapshot]
    ) -> tuple[TrendDirection, float]:
        """Determine overall trend direction and confidence."""
        if len(snapshots) < 2:
            return TrendDirection.STABLE, 0.5

        scores = [s.overall_score for s in snapshots]

        # Calculate changes between consecutive points
        changes = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
        positive_changes = sum(1 for c in changes if c > 0)
        negative_changes = sum(1 for c in changes if c < 0)
        total_changes = len(changes)

        # Calculate variance for volatility detection
        avg_score = sum(scores) / len(scores)
        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores)
        std_dev = variance**0.5

        # High variance = volatile (need significant jumping around, not just a trend)
        # Check for direction reversals (up then down then up, etc.)
        if len(scores) >= 4:
            score_changes = [scores[i] - scores[i - 1] for i in range(1, len(scores))]
            reversals = sum(
                1
                for i in range(1, len(score_changes))
                if (score_changes[i] > 2 and score_changes[i - 1] < -2)
                or (score_changes[i] < -2 and score_changes[i - 1] > 2)
            )
            # Volatile if we have many reversals relative to data points
            if reversals >= (len(scores) - 2) * 0.4 and std_dev > 15:
                return TrendDirection.VOLATILE, min(0.9, std_dev / 20)

        # Determine direction
        if positive_changes > total_changes * 0.6:
            confidence = positive_changes / total_changes
            return TrendDirection.INCREASING, confidence
        elif negative_changes > total_changes * 0.6:
            confidence = negative_changes / total_changes
            return TrendDirection.DECREASING, confidence
        else:
            return TrendDirection.STABLE, 0.7


# =============================================================================
# Factory Function
# =============================================================================


def create_temporal_risk_tracker(config: TrackerConfig | None = None) -> TemporalRiskTracker:
    """Create a temporal risk tracker with optional config.

    Args:
        config: Optional tracker configuration.

    Returns:
        Configured TemporalRiskTracker instance.
    """
    return TemporalRiskTracker(config=config)
