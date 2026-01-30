"""Risk scoring calculations and models."""

from enum import Enum

from pydantic import BaseModel

from elile.agent.state import RiskFinding


class RiskLevel(str, Enum):
    """Risk severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskScore(BaseModel):
    """Calculated risk score for an entity."""

    overall_score: float  # 0.0 to 1.0
    level: RiskLevel
    category_scores: dict[str, float]
    finding_count: int
    high_severity_count: int
    confidence: float


def _severity_weight(severity: str) -> float:
    """Get the weight for a severity level."""
    weights = {
        "low": 0.25,
        "medium": 0.5,
        "high": 0.75,
        "critical": 1.0,
    }
    return weights.get(severity.lower(), 0.5)


def _score_to_level(score: float) -> RiskLevel:
    """Convert a numeric score to a risk level."""
    if score >= 0.75:
        return RiskLevel.CRITICAL
    elif score >= 0.5:
        return RiskLevel.HIGH
    elif score >= 0.25:
        return RiskLevel.MEDIUM
    else:
        return RiskLevel.LOW


def calculate_risk_score(findings: list[RiskFinding]) -> RiskScore:
    """Calculate overall risk score from findings.

    Args:
        findings: List of risk findings to analyze.

    Returns:
        Calculated risk score with breakdown by category.
    """
    if not findings:
        return RiskScore(
            overall_score=0.0,
            level=RiskLevel.LOW,
            category_scores={},
            finding_count=0,
            high_severity_count=0,
            confidence=0.0,
        )

    # Group findings by category
    category_findings: dict[str, list[RiskFinding]] = {}
    for finding in findings:
        if finding.category not in category_findings:
            category_findings[finding.category] = []
        category_findings[finding.category].append(finding)

    # Calculate category scores
    category_scores: dict[str, float] = {}
    for category, cat_findings in category_findings.items():
        weighted_sum = sum(_severity_weight(f.severity) * f.confidence for f in cat_findings)
        category_scores[category] = min(1.0, weighted_sum / len(cat_findings))

    # Calculate overall score
    overall_score = sum(category_scores.values()) / len(category_scores) if category_scores else 0.0

    # Count high severity findings
    high_severity_count = sum(1 for f in findings if f.severity in ("high", "critical"))

    # Calculate average confidence
    avg_confidence = sum(f.confidence for f in findings) / len(findings)

    return RiskScore(
        overall_score=overall_score,
        level=_score_to_level(overall_score),
        category_scores=category_scores,
        finding_count=len(findings),
        high_severity_count=high_severity_count,
        confidence=avg_confidence,
    )
