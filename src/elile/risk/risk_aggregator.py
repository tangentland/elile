"""Risk Aggregator for comprehensive risk assessment.

This module provides the RiskAggregator that:
1. Aggregates findings, patterns, anomalies, and connections
2. Applies weighted adjustments to base scores
3. Generates comprehensive risk assessments
4. Provides detailed adjustment breakdowns
5. Produces final recommendations with supporting evidence
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import RoleCategory
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, Severity
from elile.risk.anomaly_detector import Anomaly, AnomalyType, DeceptionAssessment
from elile.risk.connection_analyzer import (
    ConnectionAnalysisResult,
    ConnectionRiskType,
    RiskPropagationPath,
)
from elile.risk.pattern_recognizer import Pattern, PatternSummary, PatternType
from elile.risk.risk_scorer import Recommendation, RiskLevel, RiskScore

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class AssessmentConfidence(str, Enum):
    """Confidence level of the assessment."""

    VERY_LOW = "very_low"  # Limited data, unreliable
    LOW = "low"  # Some gaps in data
    MEDIUM = "medium"  # Reasonable data coverage
    HIGH = "high"  # Good data coverage
    VERY_HIGH = "very_high"  # Comprehensive data


# Adjustment weights for different risk components
DEFAULT_ADJUSTMENT_WEIGHTS = {
    "patterns": 0.15,  # 15% max adjustment from patterns
    "anomalies": 0.20,  # 20% max adjustment from anomalies
    "network": 0.15,  # 15% max adjustment from network
    "deception": 0.25,  # 25% max adjustment from deception
}

# Pattern type severity weights
PATTERN_SEVERITY_WEIGHT: dict[PatternType, float] = {
    # High severity patterns
    PatternType.SEVERITY_ESCALATION: 0.9,
    PatternType.PROGRESSIVE_DEGRADATION: 0.85,
    PatternType.REPEAT_OFFENDER: 0.8,
    PatternType.SYSTEMIC_ISSUES: 0.8,
    PatternType.RECURRING_ISSUES: 0.7,
    # Medium severity patterns
    PatternType.FREQUENCY_ESCALATION: 0.6,
    PatternType.BURST_ACTIVITY: 0.5,
    PatternType.MULTI_CATEGORY: 0.5,
    PatternType.RECENT_CONCENTRATION: 0.5,
    PatternType.CORRELATED_FINDINGS: 0.5,
    # Lower severity patterns
    PatternType.TIMELINE_CLUSTER: 0.3,
    PatternType.PERIODIC_PATTERN: 0.3,
    PatternType.DORMANT_PERIOD: 0.2,
    PatternType.IMPROVEMENT_TREND: -0.2,  # Negative = reduces score
}

# Anomaly type severity weights
ANOMALY_SEVERITY_WEIGHT: dict[AnomalyType, float] = {
    # Critical anomalies
    AnomalyType.DECEPTION_PATTERN: 1.0,
    AnomalyType.FABRICATION_INDICATOR: 1.0,
    AnomalyType.TIMELINE_IMPOSSIBLE: 0.95,
    # High severity anomalies
    AnomalyType.CONCEALMENT_ATTEMPT: 0.85,
    AnomalyType.CREDENTIAL_INFLATION: 0.8,
    AnomalyType.SYSTEMATIC_INCONSISTENCIES: 0.8,
    AnomalyType.DIRECTIONAL_BIAS: 0.75,
    # Medium severity anomalies
    AnomalyType.EXPERIENCE_INFLATION: 0.6,
    AnomalyType.CROSS_FIELD_PATTERN: 0.55,
    AnomalyType.CHRONOLOGICAL_GAP: 0.5,
    AnomalyType.OVERLAPPING_PERIODS: 0.5,
    AnomalyType.IMPROBABLE_VALUE: 0.45,
    AnomalyType.SUSPICIOUS_ACTIVITY: 0.45,
    # Lower severity anomalies
    AnomalyType.QUALIFICATION_GAP: 0.3,
    AnomalyType.UNUSUAL_PATTERN: 0.25,
    AnomalyType.STATISTICAL_OUTLIER: 0.2,
    AnomalyType.UNUSUAL_FREQUENCY: 0.2,
}

# Connection risk type weights
CONNECTION_RISK_WEIGHT: dict[ConnectionRiskType, float] = {
    # Critical connection risks
    ConnectionRiskType.SANCTIONS_CONNECTION: 1.0,
    ConnectionRiskType.PEP_CONNECTION: 0.85,
    ConnectionRiskType.WATCHLIST_CONNECTION: 0.9,
    ConnectionRiskType.CRIMINAL_ASSOCIATION: 0.8,
    ConnectionRiskType.FRAUD_ASSOCIATION: 0.8,
    # High severity connection risks
    ConnectionRiskType.SHELL_COMPANY: 0.7,
    ConnectionRiskType.CIRCULAR_OWNERSHIP: 0.7,
    ConnectionRiskType.OPAQUE_STRUCTURE: 0.6,
    ConnectionRiskType.HIGH_RISK_INDUSTRY: 0.55,
    # Medium severity connection risks
    ConnectionRiskType.ADVERSE_MEDIA_ASSOCIATION: 0.5,
    ConnectionRiskType.FREQUENT_ENTITY_CHANGES: 0.45,
    ConnectionRiskType.RAPID_NETWORK_GROWTH: 0.4,
    ConnectionRiskType.UNUSUAL_CONCENTRATION: 0.4,
}


# =============================================================================
# Models
# =============================================================================


@dataclass
class RiskAdjustment:
    """An adjustment applied to the base risk score.

    Captures the source, amount, and reasoning for each adjustment.
    """

    adjustment_id: UUID = field(default_factory=uuid7)
    source: str = ""  # e.g., "patterns", "anomalies", "network", "deception"
    amount: float = 0.0  # Adjustment amount (can be negative)
    reason: str = ""
    confidence: float = 0.5  # How confident in this adjustment (0.0-1.0)
    evidence: list[str] = field(default_factory=list)
    related_items: list[UUID] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "adjustment_id": str(self.adjustment_id),
            "source": self.source,
            "amount": self.amount,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "related_items": [str(i) for i in self.related_items],
        }


@dataclass
class ComprehensiveRiskAssessment:
    """Complete risk assessment combining all risk factors.

    This is the final output of the RiskAggregator, providing:
    - Final composite score
    - Base score from findings
    - Adjustments from patterns, anomalies, connections
    - Comprehensive recommendation with supporting evidence
    - Confidence level in the assessment
    """

    assessment_id: UUID = field(default_factory=uuid7)
    entity_id: UUID | None = None
    screening_id: UUID | None = None

    # Scores
    final_score: int = 0  # 0-100
    base_score: int = 0  # From RiskScorer
    pre_cap_score: float = 0.0  # Score before capping at 100

    # Risk level and recommendation
    risk_level: RiskLevel = RiskLevel.LOW
    recommendation: Recommendation = Recommendation.PROCEED
    recommendation_reasons: list[str] = field(default_factory=list)

    # Adjustments breakdown
    adjustments: dict[str, float] = field(default_factory=dict)
    adjustment_details: list[RiskAdjustment] = field(default_factory=list)
    total_adjustment: float = 0.0

    # Component scores (0.0-1.0 normalized)
    pattern_score: float = 0.0
    anomaly_score: float = 0.0
    network_score: float = 0.0
    deception_score: float = 0.0

    # Assessment confidence
    confidence_level: AssessmentConfidence = AssessmentConfidence.MEDIUM
    confidence_factors: list[str] = field(default_factory=list)

    # Key risk indicators
    critical_findings: int = 0
    high_findings: int = 0
    patterns_detected: int = 0
    anomalies_detected: int = 0
    risk_connections: int = 0

    # Summary
    summary: str = ""
    key_concerns: list[str] = field(default_factory=list)
    mitigating_factors: list[str] = field(default_factory=list)

    # Timestamps
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "assessment_id": str(self.assessment_id),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "final_score": self.final_score,
            "base_score": self.base_score,
            "pre_cap_score": self.pre_cap_score,
            "risk_level": self.risk_level.value,
            "recommendation": self.recommendation.value,
            "recommendation_reasons": self.recommendation_reasons,
            "adjustments": self.adjustments,
            "adjustment_details": [a.to_dict() for a in self.adjustment_details],
            "total_adjustment": self.total_adjustment,
            "pattern_score": self.pattern_score,
            "anomaly_score": self.anomaly_score,
            "network_score": self.network_score,
            "deception_score": self.deception_score,
            "confidence_level": self.confidence_level.value,
            "confidence_factors": self.confidence_factors,
            "critical_findings": self.critical_findings,
            "high_findings": self.high_findings,
            "patterns_detected": self.patterns_detected,
            "anomalies_detected": self.anomalies_detected,
            "risk_connections": self.risk_connections,
            "summary": self.summary,
            "key_concerns": self.key_concerns,
            "mitigating_factors": self.mitigating_factors,
            "assessed_at": self.assessed_at.isoformat(),
        }


class AggregatorConfig(BaseModel):
    """Configuration for risk aggregator."""

    # Adjustment weights (how much each component can adjust the score)
    pattern_weight: float = Field(
        default=0.15, ge=0.0, le=0.5, description="Max adjustment from patterns (0-0.5)"
    )
    anomaly_weight: float = Field(
        default=0.20, ge=0.0, le=0.5, description="Max adjustment from anomalies (0-0.5)"
    )
    network_weight: float = Field(
        default=0.15, ge=0.0, le=0.5, description="Max adjustment from network (0-0.5)"
    )
    deception_weight: float = Field(
        default=0.25, ge=0.0, le=0.5, description="Max adjustment from deception (0-0.5)"
    )

    # Thresholds
    critical_threshold: int = Field(
        default=80, ge=0, le=100, description="Score threshold for critical"
    )
    high_threshold: int = Field(
        default=60, ge=0, le=100, description="Score threshold for high"
    )
    moderate_threshold: int = Field(
        default=40, ge=0, le=100, description="Score threshold for moderate"
    )

    # Behavior flags
    cap_at_100: bool = Field(default=True, description="Cap final score at 100")
    allow_negative_adjustments: bool = Field(
        default=True, description="Allow score reductions for positive patterns"
    )
    min_score: int = Field(default=0, ge=0, description="Minimum possible score")

    # Recommendation behavior
    auto_escalate_critical_findings: bool = Field(
        default=True, description="Auto-escalate if critical findings present"
    )
    auto_escalate_deception: bool = Field(
        default=True, description="Auto-escalate on high deception score"
    )
    deception_escalation_threshold: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Deception score to trigger escalation"
    )


# =============================================================================
# Risk Aggregator
# =============================================================================


class RiskAggregator:
    """Aggregates all risk components into comprehensive assessment.

    The RiskAggregator combines:
    - Base risk score from findings (RiskScorer output)
    - Pattern adjustments (behavioral patterns)
    - Anomaly adjustments (statistical/deception anomalies)
    - Network adjustments (connection risks)
    - Deception assessment (intent indicators)

    Example:
        ```python
        aggregator = RiskAggregator()

        assessment = aggregator.aggregate_risk(
            base_score=risk_score,
            patterns=patterns,
            anomalies=anomalies,
            connections=connection_result,
            deception=deception_assessment,
            findings=findings,
            role_category=RoleCategory.FINANCIAL,
        )

        print(f"Final Score: {assessment.final_score}")
        print(f"Recommendation: {assessment.recommendation}")
        print(f"Adjustments: {assessment.adjustments}")
        ```
    """

    def __init__(self, config: AggregatorConfig | None = None):
        """Initialize the risk aggregator.

        Args:
            config: Aggregator configuration.
        """
        self.config = config or AggregatorConfig()

    def aggregate_risk(
        self,
        base_score: RiskScore,
        patterns: list[Pattern] | None = None,
        pattern_summary: PatternSummary | None = None,
        anomalies: list[Anomaly] | None = None,
        connections: ConnectionAnalysisResult | None = None,
        deception: DeceptionAssessment | None = None,
        findings: list[Finding] | None = None,
        role_category: RoleCategory | None = None,
        entity_id: UUID | None = None,
        screening_id: UUID | None = None,
    ) -> ComprehensiveRiskAssessment:
        """Aggregate all risk factors into comprehensive assessment.

        Args:
            base_score: Base risk score from RiskScorer.
            patterns: List of recognized patterns.
            pattern_summary: Summary of patterns (optional, used for risk_score).
            anomalies: List of detected anomalies.
            connections: Connection analysis result.
            deception: Deception assessment.
            findings: Original findings for context.
            role_category: Role for context-aware assessment.
            entity_id: Entity being assessed.
            screening_id: Screening this assessment is part of.

        Returns:
            ComprehensiveRiskAssessment with final score and recommendations.
        """
        patterns = patterns or []
        anomalies = anomalies or []
        findings = findings or []

        logger.info(
            "Aggregating risk",
            base_score=base_score.overall_score,
            patterns=len(patterns),
            anomalies=len(anomalies),
            has_connections=connections is not None,
            has_deception=deception is not None,
        )

        # Initialize assessment
        assessment = ComprehensiveRiskAssessment(
            entity_id=entity_id or base_score.entity_id,
            screening_id=screening_id or base_score.screening_id,
            base_score=base_score.overall_score,
        )

        # Count findings by severity
        assessment.critical_findings = sum(
            1 for f in findings if f.severity == Severity.CRITICAL
        )
        assessment.high_findings = sum(
            1 for f in findings if f.severity == Severity.HIGH
        )
        assessment.patterns_detected = len(patterns)
        assessment.anomalies_detected = len(anomalies)

        # Calculate adjustments
        adjustment_details: list[RiskAdjustment] = []
        adjustments: dict[str, float] = {}

        # Pattern adjustment
        pattern_adj = self._calculate_pattern_adjustment(patterns, pattern_summary)
        if pattern_adj.amount != 0:
            adjustment_details.append(pattern_adj)
            adjustments["patterns"] = pattern_adj.amount
            assessment.pattern_score = self._normalize_pattern_score(
                patterns, pattern_summary
            )

        # Anomaly adjustment
        anomaly_adj = self._calculate_anomaly_adjustment(anomalies)
        if anomaly_adj.amount != 0:
            adjustment_details.append(anomaly_adj)
            adjustments["anomalies"] = anomaly_adj.amount
            assessment.anomaly_score = self._normalize_anomaly_score(anomalies)

        # Network adjustment
        if connections:
            network_adj = self._calculate_network_adjustment(connections)
            if network_adj.amount != 0:
                adjustment_details.append(network_adj)
                adjustments["network"] = network_adj.amount
                assessment.network_score = connections.total_propagated_risk
            assessment.risk_connections = len(connections.risk_connections_found)

        # Deception adjustment
        if deception:
            deception_adj = self._calculate_deception_adjustment(deception)
            if deception_adj.amount != 0:
                adjustment_details.append(deception_adj)
                adjustments["deception"] = deception_adj.amount
            assessment.deception_score = deception.overall_score

        # Calculate final score
        total_adjustment = sum(adjustments.values())

        # Apply negative adjustment limits if disabled
        if not self.config.allow_negative_adjustments:
            total_adjustment = max(0, total_adjustment)

        pre_cap_score = base_score.overall_score + total_adjustment
        final_score = pre_cap_score

        # Apply score bounds
        if self.config.cap_at_100:
            final_score = min(100, final_score)
        final_score = max(self.config.min_score, final_score)

        assessment.final_score = int(final_score)
        assessment.pre_cap_score = pre_cap_score
        assessment.total_adjustment = total_adjustment
        assessment.adjustments = adjustments
        assessment.adjustment_details = adjustment_details

        # Determine risk level
        assessment.risk_level = self._determine_risk_level(
            assessment.final_score,
            assessment.critical_findings,
            deception,
        )

        # Generate recommendation
        recommendation, reasons = self._generate_recommendation(
            assessment,
            base_score,
            patterns,
            anomalies,
            connections,
            deception,
            findings,
            role_category,
        )
        assessment.recommendation = recommendation
        assessment.recommendation_reasons = reasons

        # Calculate confidence
        assessment.confidence_level, assessment.confidence_factors = (
            self._assess_confidence(
                findings, patterns, anomalies, connections, deception
            )
        )

        # Generate summary and key concerns
        assessment.summary = self._generate_summary(assessment, role_category)
        assessment.key_concerns = self._identify_key_concerns(
            patterns, anomalies, connections, deception, findings
        )
        assessment.mitigating_factors = self._identify_mitigating_factors(
            patterns, findings
        )

        logger.info(
            "Risk aggregation complete",
            final_score=assessment.final_score,
            base_score=assessment.base_score,
            total_adjustment=assessment.total_adjustment,
            risk_level=assessment.risk_level.value,
            recommendation=assessment.recommendation.value,
        )

        return assessment

    def _calculate_pattern_adjustment(
        self,
        patterns: list[Pattern],
        summary: PatternSummary | None,
    ) -> RiskAdjustment:
        """Calculate score adjustment from patterns.

        Args:
            patterns: List of patterns.
            summary: Pattern summary.

        Returns:
            RiskAdjustment for patterns.
        """
        if not patterns:
            return RiskAdjustment(source="patterns", amount=0.0, reason="No patterns detected")

        # Calculate weighted pattern score
        weighted_sum = 0.0
        total_weight = 0.0

        evidence: list[str] = []
        related: list[UUID] = []

        for pattern in patterns:
            weight = PATTERN_SEVERITY_WEIGHT.get(pattern.pattern_type, 0.3)
            pattern_contribution = weight * pattern.confidence
            weighted_sum += pattern_contribution
            total_weight += abs(weight)

            if abs(weight) >= 0.5:
                evidence.append(f"{pattern.pattern_type.value}: {pattern.description[:50]}")
            related.append(pattern.pattern_id)

        # Average weighted score
        if total_weight > 0:
            normalized_score = weighted_sum / total_weight
        else:
            normalized_score = 0.0

        # Also consider summary risk score if available
        if summary and summary.risk_score > 0:
            normalized_score = max(normalized_score, summary.risk_score)

        # Scale to max adjustment
        max_adjustment = self.config.pattern_weight * 100
        adjustment_amount = normalized_score * max_adjustment

        reason = self._format_pattern_reason(patterns, adjustment_amount)

        return RiskAdjustment(
            source="patterns",
            amount=adjustment_amount,
            reason=reason,
            confidence=min(0.9, 0.5 + len(patterns) * 0.05),
            evidence=evidence[:5],
            related_items=related[:10],
        )

    def _calculate_anomaly_adjustment(
        self,
        anomalies: list[Anomaly],
    ) -> RiskAdjustment:
        """Calculate score adjustment from anomalies.

        Args:
            anomalies: List of anomalies.

        Returns:
            RiskAdjustment for anomalies.
        """
        if not anomalies:
            return RiskAdjustment(source="anomalies", amount=0.0, reason="No anomalies detected")

        # Calculate weighted anomaly score
        weighted_sum = 0.0
        total_weight = 0.0
        max_single_score = 0.0

        evidence: list[str] = []
        related: list[UUID] = []

        for anomaly in anomalies:
            weight = ANOMALY_SEVERITY_WEIGHT.get(anomaly.anomaly_type, 0.3)
            anomaly_contribution = weight * anomaly.confidence

            # Deception score adds extra weight
            if anomaly.deception_score > 0:
                anomaly_contribution *= (1 + anomaly.deception_score * 0.5)

            weighted_sum += anomaly_contribution
            total_weight += weight
            max_single_score = max(max_single_score, anomaly_contribution)

            if weight >= 0.5:
                evidence.append(f"{anomaly.anomaly_type.value}: {anomaly.description[:50]}")
            related.append(anomaly.anomaly_id)

        # Use combination of average and max (don't want one anomaly to dominate)
        if total_weight > 0:
            avg_score = weighted_sum / total_weight
            # Blend average with max to capture both breadth and severity
            normalized_score = (avg_score * 0.6) + (max_single_score * 0.4)
        else:
            normalized_score = 0.0

        # Scale to max adjustment
        max_adjustment = self.config.anomaly_weight * 100
        adjustment_amount = min(normalized_score, 1.0) * max_adjustment

        reason = self._format_anomaly_reason(anomalies, adjustment_amount)

        return RiskAdjustment(
            source="anomalies",
            amount=adjustment_amount,
            reason=reason,
            confidence=min(0.9, 0.5 + len(anomalies) * 0.05),
            evidence=evidence[:5],
            related_items=related[:10],
        )

    def _calculate_network_adjustment(
        self,
        connections: ConnectionAnalysisResult,
    ) -> RiskAdjustment:
        """Calculate score adjustment from network analysis.

        Args:
            connections: Connection analysis result.

        Returns:
            RiskAdjustment for network.
        """
        if not connections.risk_connections_found and connections.total_propagated_risk < 0.1:
            return RiskAdjustment(
                source="network", amount=0.0, reason="No significant network risk"
            )

        # Use propagated risk as base
        propagated_risk = connections.total_propagated_risk

        # Add weight for specific risk connection types
        connection_risk_sum = 0.0
        evidence: list[str] = []

        for conn in connections.risk_connections_found:
            conn_type = ConnectionRiskType(conn.risk_category) if conn.risk_category in [e.value for e in ConnectionRiskType] else None
            weight = CONNECTION_RISK_WEIGHT.get(conn_type, 0.4) if conn_type else 0.4
            connection_risk_sum += weight * (conn.confidence or 0.5)

            if conn.entity:
                evidence.append(f"{conn.risk_category}: {conn.entity.name}")

        # Combine propagated risk with connection type risk
        if connections.risk_connections_found:
            avg_conn_risk = connection_risk_sum / len(connections.risk_connections_found)
            combined_score = (propagated_risk * 0.6) + (avg_conn_risk * 0.4)
        else:
            combined_score = propagated_risk

        # Scale to max adjustment
        max_adjustment = self.config.network_weight * 100
        adjustment_amount = min(combined_score, 1.0) * max_adjustment

        reason = self._format_network_reason(connections, adjustment_amount)

        return RiskAdjustment(
            source="network",
            amount=adjustment_amount,
            reason=reason,
            confidence=min(0.85, 0.5 + len(connections.risk_connections_found) * 0.05),
            evidence=evidence[:5],
            related_items=[],
        )

    def _calculate_deception_adjustment(
        self,
        deception: DeceptionAssessment,
    ) -> RiskAdjustment:
        """Calculate score adjustment from deception assessment.

        Args:
            deception: Deception assessment.

        Returns:
            RiskAdjustment for deception.
        """
        if deception.overall_score < 0.1:
            return RiskAdjustment(
                source="deception", amount=0.0, reason="No significant deception indicators"
            )

        # Direct use of deception score
        deception_score = deception.overall_score

        # Apply multiplier for high-risk levels
        if deception.risk_level == "critical":
            deception_score = min(1.0, deception_score * 1.3)
        elif deception.risk_level == "high":
            deception_score = min(1.0, deception_score * 1.15)

        # Scale to max adjustment
        max_adjustment = self.config.deception_weight * 100
        adjustment_amount = deception_score * max_adjustment

        evidence = deception.contributing_factors[:3] + deception.pattern_modifiers[:2]

        reason = self._format_deception_reason(deception, adjustment_amount)

        return RiskAdjustment(
            source="deception",
            amount=adjustment_amount,
            reason=reason,
            confidence=min(0.9, 0.6 + deception.overall_score * 0.3),
            evidence=evidence,
            related_items=[],
        )

    def _normalize_pattern_score(
        self,
        patterns: list[Pattern],
        summary: PatternSummary | None,
    ) -> float:
        """Normalize pattern score to 0.0-1.0.

        Args:
            patterns: List of patterns.
            summary: Pattern summary.

        Returns:
            Normalized score.
        """
        if summary and summary.risk_score > 0:
            return summary.risk_score

        if not patterns:
            return 0.0

        # Calculate from patterns
        total_severity = sum(
            PATTERN_SEVERITY_WEIGHT.get(p.pattern_type, 0.3) * p.confidence
            for p in patterns
        )
        return min(1.0, total_severity / max(1, len(patterns)))

    def _normalize_anomaly_score(self, anomalies: list[Anomaly]) -> float:
        """Normalize anomaly score to 0.0-1.0.

        Args:
            anomalies: List of anomalies.

        Returns:
            Normalized score.
        """
        if not anomalies:
            return 0.0

        total_severity = sum(
            ANOMALY_SEVERITY_WEIGHT.get(a.anomaly_type, 0.3) * a.confidence
            for a in anomalies
        )
        return min(1.0, total_severity / max(1, len(anomalies)))

    def _determine_risk_level(
        self,
        score: int,
        critical_findings: int,
        deception: DeceptionAssessment | None,
    ) -> RiskLevel:
        """Determine risk level from score and context.

        Args:
            score: Final risk score.
            critical_findings: Number of critical findings.
            deception: Deception assessment.

        Returns:
            RiskLevel classification.
        """
        # Auto-escalate for critical findings
        if self.config.auto_escalate_critical_findings and critical_findings > 0:
            return RiskLevel.CRITICAL

        # Auto-escalate for high deception
        if (
            self.config.auto_escalate_deception
            and deception
            and deception.overall_score >= self.config.deception_escalation_threshold
        ):
            if score >= self.config.moderate_threshold:
                return RiskLevel.CRITICAL

        # Standard threshold-based determination
        if score >= self.config.critical_threshold:
            return RiskLevel.CRITICAL
        elif score >= self.config.high_threshold:
            return RiskLevel.HIGH
        elif score >= self.config.moderate_threshold:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    def _generate_recommendation(
        self,
        assessment: ComprehensiveRiskAssessment,
        base_score: RiskScore,
        patterns: list[Pattern],
        anomalies: list[Anomaly],
        connections: ConnectionAnalysisResult | None,
        deception: DeceptionAssessment | None,
        findings: list[Finding],
        role_category: RoleCategory | None,
    ) -> tuple[Recommendation, list[str]]:
        """Generate recommendation with supporting reasons.

        Args:
            assessment: Current assessment state.
            base_score: Base risk score.
            patterns: Detected patterns.
            anomalies: Detected anomalies.
            connections: Connection analysis.
            deception: Deception assessment.
            findings: Original findings.
            role_category: Role category.

        Returns:
            Tuple of (Recommendation, list of reasons).
        """
        reasons: list[str] = []
        recommendation = base_score.recommendation

        # Critical level always results in DO_NOT_PROCEED
        if assessment.risk_level == RiskLevel.CRITICAL:
            recommendation = Recommendation.DO_NOT_PROCEED

            if assessment.critical_findings > 0:
                reasons.append(f"{assessment.critical_findings} critical finding(s) identified")
            if deception and deception.overall_score >= 0.7:
                reasons.append(f"High deception risk ({deception.overall_score:.0%})")
            if assessment.final_score >= self.config.critical_threshold:
                reasons.append(f"Risk score ({assessment.final_score}) exceeds critical threshold")

        # High level results in REVIEW_REQUIRED
        elif assessment.risk_level == RiskLevel.HIGH:
            recommendation = Recommendation.REVIEW_REQUIRED

            if assessment.high_findings > 0:
                reasons.append(f"{assessment.high_findings} high-severity finding(s)")
            if patterns and any(p.severity == Severity.HIGH for p in patterns):
                reasons.append("High-severity behavioral patterns detected")
            if connections and connections.risk_connections_found:
                reasons.append(f"{len(connections.risk_connections_found)} risky network connection(s)")

        # Moderate level results in PROCEED_WITH_CAUTION
        elif assessment.risk_level == RiskLevel.MODERATE:
            recommendation = Recommendation.PROCEED_WITH_CAUTION

            if assessment.total_adjustment > 10:
                reasons.append(f"Score increased by {assessment.total_adjustment:.0f} points from analysis")
            if anomalies:
                reasons.append(f"{len(anomalies)} anomaly(ies) detected")
            if patterns:
                reasons.append(f"{len(patterns)} pattern(s) identified")

        # Low level results in PROCEED
        else:
            recommendation = Recommendation.PROCEED

            if assessment.final_score == 0:
                reasons.append("No adverse findings detected")
            else:
                reasons.append(f"Low risk score ({assessment.final_score})")

            # Check for positive indicators
            improvement = [p for p in patterns if p.pattern_type == PatternType.IMPROVEMENT_TREND]
            if improvement:
                reasons.append("Positive trend: improvement over time")

        # Role-specific context
        if role_category and role_category != RoleCategory.STANDARD:
            if recommendation in (Recommendation.PROCEED_WITH_CAUTION, Recommendation.REVIEW_REQUIRED):
                reasons.append(f"Enhanced scrutiny for {role_category.value} role")

        return recommendation, reasons

    def _assess_confidence(
        self,
        findings: list[Finding],
        patterns: list[Pattern],
        anomalies: list[Anomaly],
        connections: ConnectionAnalysisResult | None,
        deception: DeceptionAssessment | None,
    ) -> tuple[AssessmentConfidence, list[str]]:
        """Assess confidence level in the assessment.

        Args:
            findings: Findings analyzed.
            patterns: Patterns detected.
            anomalies: Anomalies detected.
            connections: Connection analysis.
            deception: Deception assessment.

        Returns:
            Tuple of (confidence level, factors contributing to confidence).
        """
        factors: list[str] = []
        score = 0.5  # Base confidence

        # More findings = higher confidence
        if len(findings) >= 10:
            score += 0.15
            factors.append("Comprehensive finding coverage")
        elif len(findings) >= 5:
            score += 0.1
            factors.append("Good finding coverage")
        elif len(findings) < 2:
            score -= 0.15
            factors.append("Limited findings data")

        # Pattern analysis adds confidence
        if patterns:
            score += 0.05
            factors.append("Pattern analysis completed")

        # Anomaly detection adds confidence
        if anomalies is not None:  # Even empty list means analysis was done
            score += 0.05
            factors.append("Anomaly detection completed")

        # Network analysis adds confidence
        if connections and connections.connections_analyzed > 0:
            score += 0.1
            factors.append(f"Network analysis ({connections.connections_analyzed} connections)")

        # Deception assessment adds confidence
        if deception:
            score += 0.1
            factors.append("Deception assessment completed")

        # Corroboration improves confidence
        corroborated = sum(1 for f in findings if f.corroborated)
        if corroborated > len(findings) * 0.5:
            score += 0.1
            factors.append("High corroboration rate")

        # Map score to confidence level
        if score >= 0.85:
            level = AssessmentConfidence.VERY_HIGH
        elif score >= 0.7:
            level = AssessmentConfidence.HIGH
        elif score >= 0.5:
            level = AssessmentConfidence.MEDIUM
        elif score >= 0.35:
            level = AssessmentConfidence.LOW
        else:
            level = AssessmentConfidence.VERY_LOW

        return level, factors

    def _generate_summary(
        self,
        assessment: ComprehensiveRiskAssessment,
        role_category: RoleCategory | None,
    ) -> str:
        """Generate human-readable summary.

        Args:
            assessment: Current assessment.
            role_category: Role category.

        Returns:
            Summary string.
        """
        parts = []

        # Score summary
        parts.append(
            f"Overall risk score: {assessment.final_score}/100 ({assessment.risk_level.value})"
        )

        # Score composition
        if assessment.total_adjustment != 0:
            direction = "increased" if assessment.total_adjustment > 0 else "decreased"
            parts.append(
                f"Base score of {assessment.base_score} {direction} by {abs(assessment.total_adjustment):.0f} points"
            )

        # Key statistics
        stats = []
        if assessment.critical_findings > 0:
            stats.append(f"{assessment.critical_findings} critical")
        if assessment.high_findings > 0:
            stats.append(f"{assessment.high_findings} high-severity")
        if stats:
            parts.append(f"Findings: {', '.join(stats)}")

        # Additional analysis
        analyses = []
        if assessment.patterns_detected > 0:
            analyses.append(f"{assessment.patterns_detected} patterns")
        if assessment.anomalies_detected > 0:
            analyses.append(f"{assessment.anomalies_detected} anomalies")
        if assessment.risk_connections > 0:
            analyses.append(f"{assessment.risk_connections} risky connections")
        if analyses:
            parts.append(f"Analysis identified: {', '.join(analyses)}")

        # Recommendation
        parts.append(f"Recommendation: {assessment.recommendation.value.replace('_', ' ').title()}")

        # Role context
        if role_category and role_category != RoleCategory.STANDARD:
            parts.append(f"Assessment context: {role_category.value} role")

        return ". ".join(parts)

    def _identify_key_concerns(
        self,
        patterns: list[Pattern],
        anomalies: list[Anomaly],
        connections: ConnectionAnalysisResult | None,
        deception: DeceptionAssessment | None,
        findings: list[Finding],
    ) -> list[str]:
        """Identify key concerns for the assessment.

        Args:
            patterns: Detected patterns.
            anomalies: Detected anomalies.
            connections: Connection analysis.
            deception: Deception assessment.
            findings: Original findings.

        Returns:
            List of key concern descriptions.
        """
        concerns: list[str] = []

        # Critical and high findings
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        for finding in critical[:2]:
            concerns.append(f"CRITICAL: {finding.summary[:60]}")

        high = [f for f in findings if f.severity == Severity.HIGH]
        for finding in high[:2]:
            concerns.append(f"HIGH: {finding.summary[:60]}")

        # High-severity patterns
        severe_patterns = [p for p in patterns if p.severity in (Severity.HIGH, Severity.CRITICAL)]
        for pattern in severe_patterns[:2]:
            concerns.append(f"Pattern: {pattern.description[:50]}")

        # Critical anomalies
        critical_anomalies = [a for a in anomalies if a.severity in (Severity.HIGH, Severity.CRITICAL)]
        for anomaly in critical_anomalies[:2]:
            concerns.append(f"Anomaly: {anomaly.description[:50]}")

        # Network risks
        if connections:
            for conn in connections.risk_connections_found[:2]:
                if conn.entity:
                    concerns.append(f"Connection: {conn.risk_description[:50]}")

        # Deception
        if deception and deception.overall_score >= 0.5:
            concerns.append(f"Deception risk: {deception.risk_level} ({deception.overall_score:.0%})")

        return concerns[:10]

    def _identify_mitigating_factors(
        self,
        patterns: list[Pattern],
        findings: list[Finding],
    ) -> list[str]:
        """Identify mitigating factors that reduce risk.

        Args:
            patterns: Detected patterns.
            findings: Original findings.

        Returns:
            List of mitigating factor descriptions.
        """
        factors: list[str] = []

        # Improvement trends
        improvements = [p for p in patterns if p.pattern_type == PatternType.IMPROVEMENT_TREND]
        for imp in improvements:
            factors.append(f"Improvement: {imp.description[:50]}")

        # Old findings (recency)
        from datetime import date

        today = date.today()
        old_findings = [
            f for f in findings
            if f.finding_date and (today - f.finding_date).days > 365 * 5
        ]
        if old_findings and len(old_findings) == len(findings):
            factors.append("All findings are more than 5 years old")
        elif old_findings:
            factors.append(f"{len(old_findings)} finding(s) are more than 5 years old")

        # Low severity
        low_only = all(f.severity == Severity.LOW for f in findings)
        if findings and low_only:
            factors.append("All findings are low severity")

        # Dormant periods (no recent issues)
        dormant = [p for p in patterns if p.pattern_type == PatternType.DORMANT_PERIOD]
        for d in dormant:
            factors.append(f"Dormant period: {d.description[:50]}")

        return factors[:5]

    def _format_pattern_reason(
        self,
        patterns: list[Pattern],
        adjustment: float,
    ) -> str:
        """Format reason string for pattern adjustment.

        Args:
            patterns: Detected patterns.
            adjustment: Adjustment amount.

        Returns:
            Reason string.
        """
        if not patterns:
            return "No patterns detected"

        high_severity = [p for p in patterns if p.severity in (Severity.HIGH, Severity.CRITICAL)]
        if high_severity:
            return f"{len(patterns)} pattern(s) detected, {len(high_severity)} high-severity → +{adjustment:.0f} points"
        else:
            return f"{len(patterns)} pattern(s) detected → +{adjustment:.0f} points"

    def _format_anomaly_reason(
        self,
        anomalies: list[Anomaly],
        adjustment: float,
    ) -> str:
        """Format reason string for anomaly adjustment.

        Args:
            anomalies: Detected anomalies.
            adjustment: Adjustment amount.

        Returns:
            Reason string.
        """
        if not anomalies:
            return "No anomalies detected"

        critical = [a for a in anomalies if a.severity == Severity.CRITICAL]
        if critical:
            return f"{len(anomalies)} anomaly(ies), {len(critical)} critical → +{adjustment:.0f} points"
        else:
            return f"{len(anomalies)} anomaly(ies) detected → +{adjustment:.0f} points"

    def _format_network_reason(
        self,
        connections: ConnectionAnalysisResult,
        adjustment: float,
    ) -> str:
        """Format reason string for network adjustment.

        Args:
            connections: Connection analysis result.
            adjustment: Adjustment amount.

        Returns:
            Reason string.
        """
        risk_count = len(connections.risk_connections_found)
        propagated = connections.total_propagated_risk

        if risk_count > 0:
            return f"{risk_count} risky connection(s), {propagated:.0%} propagated risk → +{adjustment:.0f} points"
        elif propagated > 0:
            return f"Network propagated risk of {propagated:.0%} → +{adjustment:.0f} points"
        else:
            return "No significant network risk"

    def _format_deception_reason(
        self,
        deception: DeceptionAssessment,
        adjustment: float,
    ) -> str:
        """Format reason string for deception adjustment.

        Args:
            deception: Deception assessment.
            adjustment: Adjustment amount.

        Returns:
            Reason string.
        """
        return f"Deception risk {deception.risk_level} ({deception.overall_score:.0%}) → +{adjustment:.0f} points"


def create_risk_aggregator(config: AggregatorConfig | None = None) -> RiskAggregator:
    """Create a risk aggregator.

    Args:
        config: Optional aggregator configuration.

    Returns:
        Configured RiskAggregator.
    """
    return RiskAggregator(config=config)
