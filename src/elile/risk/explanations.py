"""Risk Score Explanations for human-readable risk reporting.

This module provides:
- Human-readable explanations for risk scores
- Contributing factor breakdowns with weights
- Natural language narratives
- What-if analysis support
- Export to multiple formats (Markdown, HTML, JSON, plain text)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from uuid_utils import uuid7

from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.anomaly_detector import Anomaly, AnomalyType
from elile.risk.pattern_recognizer import Pattern, PatternType
from elile.risk.risk_aggregator import ComprehensiveRiskAssessment, RiskAdjustment
from elile.risk.risk_scorer import Recommendation, RiskLevel, RiskScore

logger = structlog.get_logger()


# =============================================================================
# Enums
# =============================================================================


class ExplanationFormat(str, Enum):
    """Output format for explanations."""

    PLAIN_TEXT = "plain_text"
    MARKDOWN = "markdown"
    HTML = "html"
    JSON = "json"


class ExplanationDepth(str, Enum):
    """Level of detail in explanations."""

    SUMMARY = "summary"  # Brief overview only
    STANDARD = "standard"  # Normal level of detail
    DETAILED = "detailed"  # Full breakdown with all factors
    TECHNICAL = "technical"  # Maximum detail for technical review


class FactorImpact(str, Enum):
    """Impact level of a contributing factor."""

    CRITICAL = "critical"  # Major impact on score
    HIGH = "high"  # Significant impact
    MODERATE = "moderate"  # Notable impact
    LOW = "low"  # Minor impact
    MITIGATING = "mitigating"  # Reduces risk score


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class ContributingFactor:
    """A factor that contributes to the risk score.

    Captures what the factor is, its impact, and supporting evidence.
    """

    factor_id: UUID = field(default_factory=uuid7)
    name: str = ""
    description: str = ""
    category: str = ""  # e.g., "finding", "pattern", "anomaly", "network"
    impact: FactorImpact = FactorImpact.MODERATE
    score_contribution: float = 0.0  # Points contributed to score
    percentage_contribution: float = 0.0  # Percentage of total score
    evidence: list[str] = field(default_factory=list)
    related_finding_ids: list[UUID] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "factor_id": str(self.factor_id),
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "impact": self.impact.value,
            "score_contribution": self.score_contribution,
            "percentage_contribution": self.percentage_contribution,
            "evidence": self.evidence,
            "related_finding_ids": [str(f) for f in self.related_finding_ids],
        }


@dataclass
class ScoreBreakdown:
    """Detailed breakdown of how the score was calculated."""

    breakdown_id: UUID = field(default_factory=uuid7)

    # Base components
    base_score: int = 0
    findings_contribution: int = 0
    patterns_contribution: int = 0
    anomalies_contribution: int = 0
    network_contribution: int = 0
    deception_contribution: int = 0

    # Adjustments
    total_adjustments: float = 0.0
    positive_adjustments: float = 0.0  # Increased risk
    negative_adjustments: float = 0.0  # Mitigating factors

    # Final
    final_score: int = 0
    pre_cap_score: float = 0.0  # Score before capping
    was_capped: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "breakdown_id": str(self.breakdown_id),
            "base_score": self.base_score,
            "findings_contribution": self.findings_contribution,
            "patterns_contribution": self.patterns_contribution,
            "anomalies_contribution": self.anomalies_contribution,
            "network_contribution": self.network_contribution,
            "deception_contribution": self.deception_contribution,
            "total_adjustments": self.total_adjustments,
            "positive_adjustments": self.positive_adjustments,
            "negative_adjustments": self.negative_adjustments,
            "final_score": self.final_score,
            "pre_cap_score": self.pre_cap_score,
            "was_capped": self.was_capped,
        }


@dataclass
class WhatIfScenario:
    """A hypothetical scenario for what-if analysis.

    Shows how the score would change if certain factors were different.
    """

    scenario_id: UUID = field(default_factory=uuid7)
    name: str = ""
    description: str = ""

    # Changes
    removed_factors: list[str] = field(default_factory=list)  # Factors to remove
    modified_factors: dict[str, Any] = field(default_factory=dict)  # Factor changes

    # Results
    original_score: int = 0
    projected_score: int = 0
    score_change: int = 0
    original_level: RiskLevel = RiskLevel.LOW
    projected_level: RiskLevel = RiskLevel.LOW
    level_changed: bool = False

    # Analysis
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "scenario_id": str(self.scenario_id),
            "name": self.name,
            "description": self.description,
            "removed_factors": self.removed_factors,
            "modified_factors": self.modified_factors,
            "original_score": self.original_score,
            "projected_score": self.projected_score,
            "score_change": self.score_change,
            "original_level": self.original_level.value,
            "projected_level": self.projected_level.value,
            "level_changed": self.level_changed,
            "explanation": self.explanation,
        }


@dataclass
class RiskExplanation:
    """Complete explanation of a risk assessment.

    Combines all explanation components into a single comprehensive output.
    """

    explanation_id: UUID = field(default_factory=uuid7)
    assessment_id: UUID | None = None
    entity_id: UUID | None = None
    screening_id: UUID | None = None

    # Score overview
    score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    recommendation: Recommendation = Recommendation.PROCEED

    # Narrative sections
    summary: str = ""
    findings_narrative: str = ""
    patterns_narrative: str = ""
    anomalies_narrative: str = ""
    network_narrative: str = ""
    overall_narrative: str = ""

    # Structured data
    breakdown: ScoreBreakdown | None = None
    contributing_factors: list[ContributingFactor] = field(default_factory=list)
    key_concerns: list[str] = field(default_factory=list)
    mitigating_factors: list[str] = field(default_factory=list)

    # What-if scenarios
    what_if_scenarios: list[WhatIfScenario] = field(default_factory=list)

    # Metadata
    depth: ExplanationDepth = ExplanationDepth.STANDARD
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "explanation_id": str(self.explanation_id),
            "assessment_id": str(self.assessment_id) if self.assessment_id else None,
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "score": self.score,
            "risk_level": self.risk_level.value,
            "recommendation": self.recommendation.value,
            "summary": self.summary,
            "findings_narrative": self.findings_narrative,
            "patterns_narrative": self.patterns_narrative,
            "anomalies_narrative": self.anomalies_narrative,
            "network_narrative": self.network_narrative,
            "overall_narrative": self.overall_narrative,
            "breakdown": self.breakdown.to_dict() if self.breakdown else None,
            "contributing_factors": [f.to_dict() for f in self.contributing_factors],
            "key_concerns": self.key_concerns,
            "mitigating_factors": self.mitigating_factors,
            "what_if_scenarios": [s.to_dict() for s in self.what_if_scenarios],
            "depth": self.depth.value,
            "generated_at": self.generated_at.isoformat(),
        }


# =============================================================================
# Narrative Templates
# =============================================================================

# Risk level descriptions
RISK_LEVEL_DESCRIPTIONS = {
    RiskLevel.LOW: "low risk with no significant concerns identified",
    RiskLevel.MODERATE: "moderate risk with some areas requiring attention",
    RiskLevel.HIGH: "elevated risk with significant concerns that require review",
    RiskLevel.CRITICAL: "critical risk with serious concerns that may disqualify the subject",
}

# Recommendation explanations
RECOMMENDATION_EXPLANATIONS = {
    Recommendation.PROCEED: "proceed with standard onboarding procedures",
    Recommendation.PROCEED_WITH_CAUTION: "proceed but monitor the identified concerns during onboarding",
    Recommendation.REVIEW_REQUIRED: "conduct additional review before making a final decision",
    Recommendation.DO_NOT_PROCEED: "not proceed due to the critical risk factors identified",
}

# Category descriptions for narratives
CATEGORY_DESCRIPTIONS = {
    FindingCategory.CRIMINAL: "criminal history",
    FindingCategory.FINANCIAL: "financial background",
    FindingCategory.REGULATORY: "regulatory compliance",
    FindingCategory.REPUTATION: "reputation concerns",
    FindingCategory.VERIFICATION: "identity verification",
    FindingCategory.BEHAVIORAL: "behavioral indicators",
    FindingCategory.NETWORK: "network associations",
}

# Pattern type descriptions
PATTERN_DESCRIPTIONS = {
    PatternType.SEVERITY_ESCALATION: "a pattern of increasingly severe issues over time",
    PatternType.FREQUENCY_ESCALATION: "issues occurring more frequently over time",
    PatternType.BURST_ACTIVITY: "a concentrated burst of issues in a short period",
    PatternType.RECURRING_ISSUES: "recurring issues that have not been resolved",
    PatternType.MULTI_CATEGORY: "issues spanning multiple categories",
    PatternType.SYSTEMIC_ISSUES: "systemic problems across different areas",
    PatternType.TIMELINE_CLUSTER: "multiple issues clustered around specific time periods",
    PatternType.RECENT_CONCENTRATION: "a high concentration of recent issues",
    PatternType.PROGRESSIVE_DEGRADATION: "progressive deterioration over time",
    PatternType.PERIODIC_PATTERN: "issues occurring in a periodic pattern",
    PatternType.CORRELATED_FINDINGS: "findings that appear to be correlated",
    PatternType.REPEAT_OFFENDER: "repeated similar offenses",
    PatternType.DORMANT_PERIOD: "a period of inactivity after previous issues",
    PatternType.IMPROVEMENT_TREND: "a positive trend showing improvement",
}

# Anomaly type descriptions
ANOMALY_DESCRIPTIONS = {
    AnomalyType.STATISTICAL_OUTLIER: "statistically unusual data points",
    AnomalyType.UNUSUAL_FREQUENCY: "an unusual frequency of events",
    AnomalyType.IMPROBABLE_VALUE: "improbable or questionable values",
    AnomalyType.SUSPICIOUS_ACTIVITY: "potentially suspicious activity patterns",
    AnomalyType.SYSTEMATIC_INCONSISTENCIES: "systematic inconsistencies in reported information",
    AnomalyType.CROSS_FIELD_PATTERN: "inconsistencies across different data fields",
    AnomalyType.DIRECTIONAL_BIAS: "a consistent bias in discrepancies",
    AnomalyType.CHRONOLOGICAL_GAP: "unexplained gaps in chronology",
    AnomalyType.OVERLAPPING_PERIODS: "overlapping time periods that conflict",
    AnomalyType.TIMELINE_IMPOSSIBLE: "timeline inconsistencies that appear impossible",
    AnomalyType.CREDENTIAL_INFLATION: "potential inflation of credentials",
    AnomalyType.EXPERIENCE_INFLATION: "potential inflation of experience",
    AnomalyType.QUALIFICATION_GAP: "gaps between claimed and verified qualifications",
    AnomalyType.DECEPTION_PATTERN: "patterns indicative of deception",
    AnomalyType.FABRICATION_INDICATOR: "indicators of potential fabrication",
    AnomalyType.CONCEALMENT_ATTEMPT: "possible attempts to conceal information",
    AnomalyType.UNUSUAL_PATTERN: "unusual patterns in the data",
}


# =============================================================================
# Configuration
# =============================================================================


class ExplainerConfig(BaseModel):
    """Configuration for risk explainer."""

    # Default depth
    default_depth: ExplanationDepth = Field(
        default=ExplanationDepth.STANDARD,
        description="Default explanation depth",
    )

    # What-if scenarios
    include_what_if: bool = Field(
        default=True,
        description="Include what-if scenarios",
    )
    max_what_if_scenarios: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum what-if scenarios to generate",
    )

    # Narrative style
    formal_tone: bool = Field(
        default=True,
        description="Use formal language in narratives",
    )
    include_technical_details: bool = Field(
        default=False,
        description="Include technical details in narratives",
    )

    # Factor filtering
    min_contribution_percentage: float = Field(
        default=1.0,
        ge=0.0,
        le=100.0,
        description="Minimum percentage contribution to include factor",
    )


# =============================================================================
# Risk Explainer
# =============================================================================


class RiskExplainer:
    """Generates human-readable explanations for risk assessments.

    The explainer takes risk assessments and produces clear, understandable
    explanations suitable for HR managers, compliance officers, and other
    non-technical stakeholders.

    Example:
        explainer = RiskExplainer()

        # From comprehensive assessment
        explanation = explainer.explain_assessment(assessment)

        # From basic score
        explanation = explainer.explain_score(risk_score, findings)

        # Export in different formats
        markdown = explainer.export(explanation, ExplanationFormat.MARKDOWN)
        html = explainer.export(explanation, ExplanationFormat.HTML)
    """

    def __init__(self, config: ExplainerConfig | None = None) -> None:
        """Initialize explainer.

        Args:
            config: Optional explainer configuration.
        """
        self.config = config or ExplainerConfig()

    def explain_assessment(
        self,
        assessment: ComprehensiveRiskAssessment,
        findings: list[Finding] | None = None,
        patterns: list[Pattern] | None = None,
        anomalies: list[Anomaly] | None = None,
        depth: ExplanationDepth | None = None,
    ) -> RiskExplanation:
        """Generate explanation for a comprehensive risk assessment.

        Args:
            assessment: The comprehensive risk assessment.
            findings: Optional list of findings for detailed narratives.
            patterns: Optional list of patterns detected.
            anomalies: Optional list of anomalies detected.
            depth: Explanation depth level.

        Returns:
            Complete RiskExplanation.
        """
        depth = depth or self.config.default_depth
        findings = findings or []
        patterns = patterns or []
        anomalies = anomalies or []

        # Build breakdown
        breakdown = self._build_breakdown(assessment)

        # Build contributing factors
        contributing_factors = self._extract_contributing_factors(
            assessment, findings, patterns, anomalies
        )

        # Generate narratives
        summary = self._generate_summary(assessment)
        findings_narrative = self._generate_findings_narrative(assessment, findings, depth)
        patterns_narrative = self._generate_patterns_narrative(patterns, depth)
        anomalies_narrative = self._generate_anomalies_narrative(anomalies, depth)
        network_narrative = self._generate_network_narrative(assessment, depth)
        overall_narrative = self._generate_overall_narrative(assessment, depth)

        # Generate what-if scenarios
        what_if_scenarios = []
        if self.config.include_what_if:
            what_if_scenarios = self._generate_what_if_scenarios(
                assessment, findings, patterns, anomalies
            )

        explanation = RiskExplanation(
            assessment_id=assessment.assessment_id,
            entity_id=assessment.entity_id,
            screening_id=assessment.screening_id,
            score=assessment.final_score,
            risk_level=assessment.risk_level,
            recommendation=assessment.recommendation,
            summary=summary,
            findings_narrative=findings_narrative,
            patterns_narrative=patterns_narrative,
            anomalies_narrative=anomalies_narrative,
            network_narrative=network_narrative,
            overall_narrative=overall_narrative,
            breakdown=breakdown,
            contributing_factors=contributing_factors,
            key_concerns=assessment.key_concerns.copy(),
            mitigating_factors=assessment.mitigating_factors.copy(),
            what_if_scenarios=what_if_scenarios,
            depth=depth,
        )

        logger.info(
            "Generated risk explanation",
            assessment_id=str(assessment.assessment_id),
            score=assessment.final_score,
            depth=depth.value,
        )

        return explanation

    def explain_score(
        self,
        risk_score: RiskScore,
        findings: list[Finding] | None = None,
        depth: ExplanationDepth | None = None,
    ) -> RiskExplanation:
        """Generate explanation for a basic risk score.

        Args:
            risk_score: The risk score to explain.
            findings: Optional list of findings.
            depth: Explanation depth level.

        Returns:
            RiskExplanation.
        """
        depth = depth or self.config.default_depth
        findings = findings or []

        # Build basic breakdown
        breakdown = ScoreBreakdown(
            base_score=risk_score.overall_score,
            findings_contribution=risk_score.overall_score,
            final_score=risk_score.overall_score,
        )

        # Extract factors from score
        contributing_factors = self._extract_factors_from_score(risk_score, findings)

        # Generate summary
        summary = self._generate_score_summary(risk_score)

        # Generate findings narrative
        findings_narrative = ""
        if findings:
            findings_narrative = self._generate_simple_findings_narrative(findings, depth)

        explanation = RiskExplanation(
            entity_id=risk_score.entity_id,
            screening_id=risk_score.screening_id,
            score=risk_score.overall_score,
            risk_level=risk_score.risk_level,
            recommendation=risk_score.recommendation,
            summary=summary,
            findings_narrative=findings_narrative,
            breakdown=breakdown,
            contributing_factors=contributing_factors,
            depth=depth,
        )

        return explanation

    def export(
        self,
        explanation: RiskExplanation,
        format: ExplanationFormat = ExplanationFormat.MARKDOWN,
    ) -> str:
        """Export explanation to specified format.

        Args:
            explanation: The explanation to export.
            format: Output format.

        Returns:
            Formatted string.
        """
        if format == ExplanationFormat.PLAIN_TEXT:
            return self._export_plain_text(explanation)
        elif format == ExplanationFormat.MARKDOWN:
            return self._export_markdown(explanation)
        elif format == ExplanationFormat.HTML:
            return self._export_html(explanation)
        elif format == ExplanationFormat.JSON:
            import json
            return json.dumps(explanation.to_dict(), indent=2)
        else:
            return self._export_plain_text(explanation)

    def analyze_what_if(
        self,
        assessment: ComprehensiveRiskAssessment,
        remove_findings: list[Finding] | None = None,
        remove_patterns: list[Pattern] | None = None,
        remove_anomalies: list[Anomaly] | None = None,
    ) -> WhatIfScenario:
        """Analyze a what-if scenario.

        Args:
            assessment: Original assessment.
            remove_findings: Findings to hypothetically remove.
            remove_patterns: Patterns to hypothetically remove.
            remove_anomalies: Anomalies to hypothetically remove.

        Returns:
            WhatIfScenario with projected impact.
        """
        remove_findings = remove_findings or []
        remove_patterns = remove_patterns or []
        remove_anomalies = remove_anomalies or []

        # Calculate estimated score reduction
        score_reduction = 0.0

        # Estimate findings contribution
        for finding in remove_findings:
            severity_points = {
                Severity.LOW: 5,
                Severity.MEDIUM: 15,
                Severity.HIGH: 30,
                Severity.CRITICAL: 50,
            }
            score_reduction += severity_points.get(finding.severity, 10)

        # Estimate pattern contribution
        for pattern in remove_patterns:
            score_reduction += assessment.pattern_score * 20 / max(1, assessment.patterns_detected)

        # Estimate anomaly contribution
        for anomaly in remove_anomalies:
            score_reduction += assessment.anomaly_score * 20 / max(1, assessment.anomalies_detected)

        # Calculate projected score
        projected_score = max(0, int(assessment.final_score - score_reduction))
        projected_level = self._score_to_level(projected_score)

        # Build removed factors list
        removed_factors = []
        for f in remove_findings:
            removed_factors.append(f"Finding: {f.summary}")
        for p in remove_patterns:
            removed_factors.append(f"Pattern: {p.pattern_type.value}")
        for a in remove_anomalies:
            removed_factors.append(f"Anomaly: {a.anomaly_type.value}")

        # Generate explanation
        if projected_level != assessment.risk_level:
            explanation = (
                f"Removing these factors would reduce the score from {assessment.final_score} "
                f"to approximately {projected_score}, changing the risk level from "
                f"{assessment.risk_level.value} to {projected_level.value}."
            )
        else:
            explanation = (
                f"Removing these factors would reduce the score from {assessment.final_score} "
                f"to approximately {projected_score}, but the risk level would remain "
                f"{assessment.risk_level.value}."
            )

        return WhatIfScenario(
            name="Factor Removal Analysis",
            description=f"Impact of removing {len(removed_factors)} factor(s)",
            removed_factors=removed_factors,
            original_score=assessment.final_score,
            projected_score=projected_score,
            score_change=projected_score - assessment.final_score,
            original_level=assessment.risk_level,
            projected_level=projected_level,
            level_changed=projected_level != assessment.risk_level,
            explanation=explanation,
        )

    # =========================================================================
    # Private Methods - Breakdown Building
    # =========================================================================

    def _build_breakdown(self, assessment: ComprehensiveRiskAssessment) -> ScoreBreakdown:
        """Build score breakdown from assessment."""
        # Calculate component contributions
        pattern_contrib = int(assessment.pattern_score * assessment.adjustments.get("patterns", 0))
        anomaly_contrib = int(assessment.anomaly_score * assessment.adjustments.get("anomalies", 0))
        network_contrib = int(assessment.network_score * assessment.adjustments.get("network", 0))
        deception_contrib = int(
            assessment.deception_score * assessment.adjustments.get("deception", 0)
        )

        # Calculate positive and negative adjustments
        positive_adj = sum(
            adj for adj in [pattern_contrib, anomaly_contrib, network_contrib, deception_contrib]
            if adj > 0
        )
        negative_adj = sum(
            adj for adj in [pattern_contrib, anomaly_contrib, network_contrib, deception_contrib]
            if adj < 0
        )

        return ScoreBreakdown(
            base_score=assessment.base_score,
            findings_contribution=assessment.base_score,
            patterns_contribution=pattern_contrib,
            anomalies_contribution=anomaly_contrib,
            network_contribution=network_contrib,
            deception_contribution=deception_contrib,
            total_adjustments=assessment.total_adjustment,
            positive_adjustments=float(positive_adj),
            negative_adjustments=float(negative_adj),
            final_score=assessment.final_score,
            pre_cap_score=assessment.pre_cap_score,
            was_capped=assessment.pre_cap_score > 100,
        )

    def _extract_contributing_factors(
        self,
        assessment: ComprehensiveRiskAssessment,
        findings: list[Finding],
        patterns: list[Pattern],
        anomalies: list[Anomaly],
    ) -> list[ContributingFactor]:
        """Extract contributing factors from assessment components."""
        factors = []
        total_score = max(1, assessment.final_score)  # Avoid division by zero

        # Extract from findings
        for finding in findings:
            severity_points = {
                Severity.LOW: 5,
                Severity.MEDIUM: 15,
                Severity.HIGH: 30,
                Severity.CRITICAL: 50,
            }
            contribution = severity_points.get(finding.severity, 10)

            if (contribution / total_score * 100) >= self.config.min_contribution_percentage:
                factors.append(
                    ContributingFactor(
                        name=finding.summary,
                        description=finding.details[:200] if finding.details else "",
                        category="finding",
                        impact=self._severity_to_impact(finding.severity),
                        score_contribution=float(contribution),
                        percentage_contribution=contribution / total_score * 100,
                        evidence=[finding.details] if finding.details else [],
                        related_finding_ids=[finding.finding_id],
                    )
                )

        # Extract from patterns
        for pattern in patterns:
            pattern_contrib = assessment.pattern_score * 15 / max(1, len(patterns))
            if (pattern_contrib / total_score * 100) >= self.config.min_contribution_percentage:
                desc = PATTERN_DESCRIPTIONS.get(pattern.pattern_type, "detected pattern")
                factors.append(
                    ContributingFactor(
                        name=f"Pattern: {pattern.pattern_type.value.replace('_', ' ').title()}",
                        description=f"The assessment identified {desc}.",
                        category="pattern",
                        impact=self._severity_to_impact(pattern.severity),
                        score_contribution=pattern_contrib,
                        percentage_contribution=pattern_contrib / total_score * 100,
                        evidence=[f"Confidence: {pattern.confidence:.0%}"],
                    )
                )

        # Extract from anomalies
        for anomaly in anomalies:
            anomaly_contrib = assessment.anomaly_score * 20 / max(1, len(anomalies))
            if (anomaly_contrib / total_score * 100) >= self.config.min_contribution_percentage:
                desc = ANOMALY_DESCRIPTIONS.get(anomaly.anomaly_type, "detected anomaly")
                factors.append(
                    ContributingFactor(
                        name=f"Anomaly: {anomaly.anomaly_type.value.replace('_', ' ').title()}",
                        description=f"The assessment detected {desc}.",
                        category="anomaly",
                        impact=self._severity_to_impact(anomaly.severity),
                        score_contribution=anomaly_contrib,
                        percentage_contribution=anomaly_contrib / total_score * 100,
                        evidence=[anomaly.description] if anomaly.description else [],
                    )
                )

        # Sort by contribution (highest first)
        factors.sort(key=lambda f: f.score_contribution, reverse=True)

        return factors

    def _extract_factors_from_score(
        self,
        risk_score: RiskScore,
        findings: list[Finding],
    ) -> list[ContributingFactor]:
        """Extract contributing factors from basic risk score."""
        factors = []
        total_score = max(1, risk_score.overall_score)

        # Extract from category scores
        for category, score in risk_score.category_scores.items():
            if score > 0 and (score / total_score * 100) >= self.config.min_contribution_percentage:
                desc = CATEGORY_DESCRIPTIONS.get(category, category.value)
                factors.append(
                    ContributingFactor(
                        name=f"{desc.title()} Issues",
                        description=f"Findings related to {desc} contributed to the risk score.",
                        category="finding",
                        impact=self._score_to_impact(score),
                        score_contribution=float(score),
                        percentage_contribution=score / total_score * 100,
                    )
                )

        # Add findings details
        for finding in findings:
            severity_points = {
                Severity.LOW: 5,
                Severity.MEDIUM: 15,
                Severity.HIGH: 30,
                Severity.CRITICAL: 50,
            }
            contribution = severity_points.get(finding.severity, 10)

            if (contribution / total_score * 100) >= self.config.min_contribution_percentage:
                factors.append(
                    ContributingFactor(
                        name=finding.summary,
                        description=finding.details[:200] if finding.details else "",
                        category="finding",
                        impact=self._severity_to_impact(finding.severity),
                        score_contribution=float(contribution),
                        percentage_contribution=contribution / total_score * 100,
                        related_finding_ids=[finding.finding_id],
                    )
                )

        factors.sort(key=lambda f: f.score_contribution, reverse=True)
        return factors

    # =========================================================================
    # Private Methods - Narrative Generation
    # =========================================================================

    def _generate_summary(self, assessment: ComprehensiveRiskAssessment) -> str:
        """Generate summary narrative."""
        level_desc = RISK_LEVEL_DESCRIPTIONS[assessment.risk_level]
        rec_desc = RECOMMENDATION_EXPLANATIONS[assessment.recommendation]

        summary = (
            f"The risk assessment resulted in a score of {assessment.final_score} out of 100, "
            f"indicating {level_desc}. Based on this analysis, we recommend to {rec_desc}."
        )

        if assessment.critical_findings > 0:
            summary += f" The assessment identified {assessment.critical_findings} critical finding(s)."

        if assessment.key_concerns:
            summary += f" Key concerns include: {'; '.join(assessment.key_concerns[:3])}."

        return summary

    def _generate_score_summary(self, risk_score: RiskScore) -> str:
        """Generate summary for basic risk score."""
        level_desc = RISK_LEVEL_DESCRIPTIONS[risk_score.risk_level]
        rec_desc = RECOMMENDATION_EXPLANATIONS[risk_score.recommendation]

        return (
            f"The risk assessment resulted in a score of {risk_score.overall_score} out of 100, "
            f"indicating {level_desc}. Based on this analysis, we recommend to {rec_desc}."
        )

    def _generate_findings_narrative(
        self,
        assessment: ComprehensiveRiskAssessment,
        findings: list[Finding],
        depth: ExplanationDepth,
    ) -> str:
        """Generate narrative about findings."""
        if not findings:
            return "No significant findings were identified during the investigation."

        # Count by severity
        severity_counts = {s: 0 for s in Severity}
        category_counts: dict[FindingCategory, int] = {}

        for finding in findings:
            severity_counts[finding.severity] += 1
            category_counts[finding.category] = category_counts.get(finding.category, 0) + 1

        # Build narrative
        total = len(findings)
        narrative = f"The investigation identified {total} finding(s) across the background check. "

        # Severity breakdown
        if severity_counts[Severity.CRITICAL] > 0:
            narrative += (
                f"Of these, {severity_counts[Severity.CRITICAL]} are critical issues "
                f"requiring immediate attention. "
            )

        if severity_counts[Severity.HIGH] > 0:
            narrative += f"{severity_counts[Severity.HIGH]} are high-severity issues. "

        # Category breakdown (for detailed depth)
        if depth in [ExplanationDepth.DETAILED, ExplanationDepth.TECHNICAL]:
            top_categories = sorted(
                category_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]

            if top_categories:
                cat_desc = ", ".join(
                    f"{CATEGORY_DESCRIPTIONS.get(cat, cat.value)} ({count})"
                    for cat, count in top_categories
                )
                narrative += f"The primary areas of concern are {cat_desc}."

        return narrative

    def _generate_simple_findings_narrative(
        self,
        findings: list[Finding],
        depth: ExplanationDepth,
    ) -> str:
        """Generate simple findings narrative without assessment context."""
        if not findings:
            return ""

        total = len(findings)
        critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
        high = sum(1 for f in findings if f.severity == Severity.HIGH)

        narrative = f"The investigation identified {total} finding(s). "
        if critical > 0:
            narrative += f"{critical} critical and "
        if high > 0:
            narrative += f"{high} high-severity issues were found."

        return narrative

    def _generate_patterns_narrative(
        self,
        patterns: list[Pattern],
        depth: ExplanationDepth,
    ) -> str:
        """Generate narrative about detected patterns."""
        if not patterns:
            return "No significant behavioral patterns were detected in the findings."

        narrative = f"Pattern analysis identified {len(patterns)} notable pattern(s). "

        # Describe key patterns
        significant = [p for p in patterns if p.severity in [Severity.HIGH, Severity.CRITICAL]]
        if significant:
            pattern_descs = [
                PATTERN_DESCRIPTIONS.get(p.pattern_type, p.pattern_type.value)
                for p in significant[:3]
            ]
            narrative += f"Most significantly, the analysis revealed {', '.join(pattern_descs)}. "

        # Check for improvement patterns
        improving = [p for p in patterns if p.pattern_type == PatternType.IMPROVEMENT_TREND]
        if improving:
            narrative += "However, there is evidence of positive improvement over time. "

        return narrative

    def _generate_anomalies_narrative(
        self,
        anomalies: list[Anomaly],
        depth: ExplanationDepth,
    ) -> str:
        """Generate narrative about detected anomalies."""
        if not anomalies:
            return "No significant data anomalies were detected."

        narrative = f"Data validation identified {len(anomalies)} anomaly(ies). "

        # Check for deception indicators
        deception = [
            a for a in anomalies
            if a.anomaly_type in [
                AnomalyType.DECEPTION_PATTERN,
                AnomalyType.FABRICATION_INDICATOR,
                AnomalyType.CONCEALMENT_ATTEMPT,
            ]
        ]
        if deception:
            narrative += (
                f"Notably, {len(deception)} anomaly(ies) suggest potential deception "
                f"or misrepresentation, which significantly impacts the risk assessment. "
            )

        # Check for inconsistencies
        inconsistent = [
            a for a in anomalies
            if a.anomaly_type in [
                AnomalyType.SYSTEMATIC_INCONSISTENCIES,
                AnomalyType.CROSS_FIELD_PATTERN,
            ]
        ]
        if inconsistent:
            narrative += f"Additionally, {len(inconsistent)} inconsistencies were found in the reported information. "

        return narrative

    def _generate_network_narrative(
        self,
        assessment: ComprehensiveRiskAssessment,
        depth: ExplanationDepth,
    ) -> str:
        """Generate narrative about network analysis."""
        if assessment.risk_connections == 0:
            return "Network analysis did not identify any high-risk associations."

        narrative = (
            f"Network analysis identified {assessment.risk_connections} risk-relevant "
            f"connection(s) in the subject's professional and personal network. "
        )

        if assessment.network_score > 0.5:
            narrative += (
                "These connections represent a significant risk factor and warrant "
                "additional due diligence. "
            )
        elif assessment.network_score > 0.2:
            narrative += "Some of these connections may require monitoring during employment. "

        return narrative

    def _generate_overall_narrative(
        self,
        assessment: ComprehensiveRiskAssessment,
        depth: ExplanationDepth,
    ) -> str:
        """Generate comprehensive overall narrative."""
        narrative = []

        # Opening
        if assessment.risk_level == RiskLevel.LOW:
            narrative.append(
                "Overall, this assessment presents a favorable risk profile with minimal concerns."
            )
        elif assessment.risk_level == RiskLevel.MODERATE:
            narrative.append(
                "This assessment reveals some areas of concern that warrant attention, "
                "though they do not necessarily preclude employment."
            )
        elif assessment.risk_level == RiskLevel.HIGH:
            narrative.append(
                "This assessment has identified significant risk factors that require "
                "careful consideration before proceeding."
            )
        else:  # CRITICAL
            narrative.append(
                "This assessment has identified serious risk factors that present "
                "substantial concerns for the organization."
            )

        # Key factors
        if assessment.key_concerns:
            narrative.append(
                f"The primary concerns are: {'; '.join(assessment.key_concerns[:5])}."
            )

        # Mitigating factors
        if assessment.mitigating_factors:
            narrative.append(
                f"Mitigating factors include: {'; '.join(assessment.mitigating_factors[:3])}."
            )

        # Recommendation
        rec_desc = RECOMMENDATION_EXPLANATIONS[assessment.recommendation]
        narrative.append(f"Based on this analysis, we recommend to {rec_desc}.")

        return " ".join(narrative)

    # =========================================================================
    # Private Methods - What-If Analysis
    # =========================================================================

    def _generate_what_if_scenarios(
        self,
        assessment: ComprehensiveRiskAssessment,
        findings: list[Finding],
        patterns: list[Pattern],
        anomalies: list[Anomaly],
    ) -> list[WhatIfScenario]:
        """Generate what-if scenarios for the assessment."""
        scenarios = []
        max_scenarios = self.config.max_what_if_scenarios

        # Scenario 1: Remove critical findings
        critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
        if critical_findings and len(scenarios) < max_scenarios:
            scenario = self.analyze_what_if(
                assessment,
                remove_findings=critical_findings,
            )
            scenario.name = "Without Critical Findings"
            scenario.description = (
                f"What if the {len(critical_findings)} critical finding(s) were not present?"
            )
            scenarios.append(scenario)

        # Scenario 2: Remove deception anomalies
        deception_anomalies = [
            a for a in anomalies
            if a.anomaly_type in [
                AnomalyType.DECEPTION_PATTERN,
                AnomalyType.FABRICATION_INDICATOR,
                AnomalyType.CONCEALMENT_ATTEMPT,
            ]
        ]
        if deception_anomalies and len(scenarios) < max_scenarios:
            scenario = self.analyze_what_if(
                assessment,
                remove_anomalies=deception_anomalies,
            )
            scenario.name = "Without Deception Indicators"
            scenario.description = (
                f"What if the {len(deception_anomalies)} deception indicator(s) were not present?"
            )
            scenarios.append(scenario)

        # Scenario 3: Remove negative patterns
        negative_patterns = [
            p for p in patterns
            if p.pattern_type in [
                PatternType.SEVERITY_ESCALATION,
                PatternType.PROGRESSIVE_DEGRADATION,
                PatternType.REPEAT_OFFENDER,
            ]
        ]
        if negative_patterns and len(scenarios) < max_scenarios:
            scenario = self.analyze_what_if(
                assessment,
                remove_patterns=negative_patterns,
            )
            scenario.name = "Without Negative Patterns"
            scenario.description = (
                f"What if the {len(negative_patterns)} negative pattern(s) were not present?"
            )
            scenarios.append(scenario)

        return scenarios

    # =========================================================================
    # Private Methods - Export
    # =========================================================================

    def _export_plain_text(self, explanation: RiskExplanation) -> str:
        """Export as plain text."""
        lines = [
            "RISK ASSESSMENT EXPLANATION",
            "=" * 40,
            "",
            f"Risk Score: {explanation.score}/100",
            f"Risk Level: {explanation.risk_level.value.upper()}",
            f"Recommendation: {explanation.recommendation.value.replace('_', ' ').title()}",
            "",
            "SUMMARY",
            "-" * 20,
            explanation.summary,
            "",
        ]

        if explanation.findings_narrative:
            lines.extend([
                "FINDINGS ANALYSIS",
                "-" * 20,
                explanation.findings_narrative,
                "",
            ])

        if explanation.patterns_narrative:
            lines.extend([
                "PATTERN ANALYSIS",
                "-" * 20,
                explanation.patterns_narrative,
                "",
            ])

        if explanation.anomalies_narrative:
            lines.extend([
                "ANOMALY ANALYSIS",
                "-" * 20,
                explanation.anomalies_narrative,
                "",
            ])

        if explanation.key_concerns:
            lines.extend([
                "KEY CONCERNS",
                "-" * 20,
            ])
            for concern in explanation.key_concerns:
                lines.append(f"  - {concern}")
            lines.append("")

        if explanation.contributing_factors:
            lines.extend([
                "CONTRIBUTING FACTORS",
                "-" * 20,
            ])
            for factor in explanation.contributing_factors[:10]:
                lines.append(
                    f"  - {factor.name} ({factor.impact.value}): "
                    f"+{factor.score_contribution:.1f} pts ({factor.percentage_contribution:.1f}%)"
                )
            lines.append("")

        if explanation.what_if_scenarios:
            lines.extend([
                "WHAT-IF ANALYSIS",
                "-" * 20,
            ])
            for scenario in explanation.what_if_scenarios:
                lines.append(f"  {scenario.name}:")
                lines.append(f"    {scenario.explanation}")
            lines.append("")

        return "\n".join(lines)

    def _export_markdown(self, explanation: RiskExplanation) -> str:
        """Export as markdown."""
        lines = [
            "# Risk Assessment Explanation",
            "",
            f"**Risk Score:** {explanation.score}/100",
            f"**Risk Level:** {explanation.risk_level.value.upper()}",
            f"**Recommendation:** {explanation.recommendation.value.replace('_', ' ').title()}",
            "",
            "## Summary",
            "",
            explanation.summary,
            "",
        ]

        if explanation.findings_narrative:
            lines.extend([
                "## Findings Analysis",
                "",
                explanation.findings_narrative,
                "",
            ])

        if explanation.patterns_narrative:
            lines.extend([
                "## Pattern Analysis",
                "",
                explanation.patterns_narrative,
                "",
            ])

        if explanation.anomalies_narrative:
            lines.extend([
                "## Anomaly Analysis",
                "",
                explanation.anomalies_narrative,
                "",
            ])

        if explanation.network_narrative:
            lines.extend([
                "## Network Analysis",
                "",
                explanation.network_narrative,
                "",
            ])

        if explanation.key_concerns:
            lines.extend([
                "## Key Concerns",
                "",
            ])
            for concern in explanation.key_concerns:
                lines.append(f"- {concern}")
            lines.append("")

        if explanation.mitigating_factors:
            lines.extend([
                "## Mitigating Factors",
                "",
            ])
            for factor in explanation.mitigating_factors:
                lines.append(f"- {factor}")
            lines.append("")

        if explanation.contributing_factors:
            lines.extend([
                "## Contributing Factors",
                "",
                "| Factor | Impact | Contribution | % of Total |",
                "|--------|--------|--------------|------------|",
            ])
            for factor in explanation.contributing_factors[:10]:
                lines.append(
                    f"| {factor.name[:30]} | {factor.impact.value} | "
                    f"+{factor.score_contribution:.1f} | {factor.percentage_contribution:.1f}% |"
                )
            lines.append("")

        if explanation.breakdown:
            bd = explanation.breakdown
            lines.extend([
                "## Score Breakdown",
                "",
                f"- Base Score (Findings): {bd.base_score}",
                f"- Pattern Adjustment: {bd.patterns_contribution:+d}",
                f"- Anomaly Adjustment: {bd.anomalies_contribution:+d}",
                f"- Network Adjustment: {bd.network_contribution:+d}",
                f"- Deception Adjustment: {bd.deception_contribution:+d}",
                f"- **Final Score: {bd.final_score}**",
                "",
            ])

        if explanation.what_if_scenarios:
            lines.extend([
                "## What-If Analysis",
                "",
            ])
            for scenario in explanation.what_if_scenarios:
                lines.append(f"### {scenario.name}")
                lines.append("")
                lines.append(scenario.explanation)
                lines.append(
                    f"- Original Score: {scenario.original_score} → "
                    f"Projected: {scenario.projected_score} "
                    f"(Change: {scenario.score_change:+d})"
                )
                lines.append("")

        return "\n".join(lines)

    def _export_html(self, explanation: RiskExplanation) -> str:
        """Export as HTML."""
        # Convert markdown to basic HTML
        md = self._export_markdown(explanation)

        # Simple markdown to HTML conversion
        html_lines = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<style>",
            "body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }",
            "h1 { color: #333; }",
            "h2 { color: #555; border-bottom: 1px solid #ddd; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f5f5f5; }",
            ".score { font-size: 24px; font-weight: bold; }",
            ".critical { color: #d32f2f; }",
            ".high { color: #f57c00; }",
            ".moderate { color: #fbc02d; }",
            ".low { color: #388e3c; }",
            "</style>",
            "</head>",
            "<body>",
        ]

        # Convert markdown content
        level_class = explanation.risk_level.value.lower()
        html_lines.append(f'<h1>Risk Assessment Explanation</h1>')
        html_lines.append(f'<p class="score {level_class}">Score: {explanation.score}/100</p>')
        html_lines.append(f'<p><strong>Risk Level:</strong> <span class="{level_class}">{explanation.risk_level.value.upper()}</span></p>')
        html_lines.append(f'<p><strong>Recommendation:</strong> {explanation.recommendation.value.replace("_", " ").title()}</p>')

        html_lines.append(f'<h2>Summary</h2>')
        html_lines.append(f'<p>{explanation.summary}</p>')

        if explanation.findings_narrative:
            html_lines.append(f'<h2>Findings Analysis</h2>')
            html_lines.append(f'<p>{explanation.findings_narrative}</p>')

        if explanation.key_concerns:
            html_lines.append(f'<h2>Key Concerns</h2>')
            html_lines.append('<ul>')
            for concern in explanation.key_concerns:
                html_lines.append(f'<li>{concern}</li>')
            html_lines.append('</ul>')

        if explanation.contributing_factors:
            html_lines.append(f'<h2>Contributing Factors</h2>')
            html_lines.append('<table>')
            html_lines.append('<tr><th>Factor</th><th>Impact</th><th>Contribution</th></tr>')
            for factor in explanation.contributing_factors[:10]:
                html_lines.append(
                    f'<tr><td>{factor.name}</td><td>{factor.impact.value}</td>'
                    f'<td>+{factor.score_contribution:.1f} ({factor.percentage_contribution:.1f}%)</td></tr>'
                )
            html_lines.append('</table>')

        html_lines.extend([
            "</body>",
            "</html>",
        ])

        return "\n".join(html_lines)

    # =========================================================================
    # Private Methods - Utilities
    # =========================================================================

    def _severity_to_impact(self, severity: Severity) -> FactorImpact:
        """Convert severity to impact level."""
        mapping = {
            Severity.CRITICAL: FactorImpact.CRITICAL,
            Severity.HIGH: FactorImpact.HIGH,
            Severity.MEDIUM: FactorImpact.MODERATE,
            Severity.LOW: FactorImpact.LOW,
        }
        return mapping.get(severity, FactorImpact.MODERATE)

    def _score_to_impact(self, score: int) -> FactorImpact:
        """Convert score contribution to impact level."""
        if score >= 50:
            return FactorImpact.CRITICAL
        elif score >= 30:
            return FactorImpact.HIGH
        elif score >= 15:
            return FactorImpact.MODERATE
        else:
            return FactorImpact.LOW

    def _score_to_level(self, score: int) -> RiskLevel:
        """Convert score to risk level."""
        if score >= 80:
            return RiskLevel.CRITICAL
        elif score >= 60:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW


# =============================================================================
# Factory Function
# =============================================================================


def create_risk_explainer(
    config: ExplainerConfig | None = None,
) -> RiskExplainer:
    """Create a risk explainer with optional config.

    Args:
        config: Optional explainer configuration.

    Returns:
        Configured RiskExplainer instance.
    """
    return RiskExplainer(config=config)
