"""Risk Scorer for calculating composite risk scores from findings.

This module provides the RiskScorer that:
1. Calculates composite risk scores (0-100) from findings
2. Applies severity weighting, recency decay, corroboration bonuses
3. Provides category breakdown scoring
4. Determines risk levels and recommendations
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import RoleCategory
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity

logger = get_logger(__name__)


class RiskLevel(str, Enum):
    """Risk level classification."""

    LOW = "low"  # 0-25
    MODERATE = "moderate"  # 26-50
    HIGH = "high"  # 51-75
    CRITICAL = "critical"  # 76-100


class Recommendation(str, Enum):
    """Hiring recommendation based on risk assessment."""

    PROCEED = "proceed"  # Low risk, recommend proceeding
    PROCEED_WITH_CAUTION = "proceed_with_caution"  # Moderate risk, some concerns
    REVIEW_REQUIRED = "review_required"  # High risk, requires human review
    DO_NOT_PROCEED = "do_not_proceed"  # Critical risk, recommend against


@dataclass
class RiskScore:
    """Composite risk score with breakdown.

    Attributes:
        score_id: Unique identifier for this score.
        overall_score: Composite risk score (0-100).
        risk_level: Classified risk level.
        category_scores: Score breakdown by finding category.
        contributing_factors: Factor analysis (counts and statistics).
        recommendation: Hiring recommendation.
        scored_at: When the score was calculated.
        entity_id: Entity the score relates to (optional).
        screening_id: Screening this score is part of (optional).
    """

    score_id: UUID = field(default_factory=uuid7)
    overall_score: int = 0
    risk_level: RiskLevel = RiskLevel.LOW
    category_scores: dict[FindingCategory, int] = field(default_factory=dict)
    contributing_factors: dict[str, float] = field(default_factory=dict)
    recommendation: Recommendation = Recommendation.PROCEED
    scored_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    entity_id: UUID | None = None
    screening_id: UUID | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score_id": str(self.score_id),
            "overall_score": self.overall_score,
            "risk_level": self.risk_level.value,
            "category_scores": {
                cat.value: score for cat, score in self.category_scores.items()
            },
            "contributing_factors": self.contributing_factors,
            "recommendation": self.recommendation.value,
            "scored_at": self.scored_at.isoformat(),
            "entity_id": str(self.entity_id) if self.entity_id else None,
            "screening_id": str(self.screening_id) if self.screening_id else None,
        }


class ScorerConfig(BaseModel):
    """Configuration for risk scorer."""

    # Severity base scores
    severity_low: int = Field(default=10, ge=0, le=100, description="Base score for LOW severity")
    severity_medium: int = Field(
        default=25, ge=0, le=100, description="Base score for MEDIUM severity"
    )
    severity_high: int = Field(default=50, ge=0, le=100, description="Base score for HIGH severity")
    severity_critical: int = Field(
        default=75, ge=0, le=100, description="Base score for CRITICAL severity"
    )

    # Category weights (multipliers)
    criminal_weight: float = Field(
        default=1.5, ge=0.0, le=3.0, description="Weight for criminal findings"
    )
    financial_weight: float = Field(
        default=1.0, ge=0.0, le=3.0, description="Weight for financial findings"
    )
    regulatory_weight: float = Field(
        default=1.3, ge=0.0, le=3.0, description="Weight for regulatory findings"
    )
    reputation_weight: float = Field(
        default=0.8, ge=0.0, le=3.0, description="Weight for reputation findings"
    )
    verification_weight: float = Field(
        default=1.2, ge=0.0, le=3.0, description="Weight for verification findings"
    )
    behavioral_weight: float = Field(
        default=1.0, ge=0.0, le=3.0, description="Weight for behavioral findings"
    )
    network_weight: float = Field(
        default=0.9, ge=0.0, le=3.0, description="Weight for network findings"
    )

    # Recency decay factors
    recency_unknown: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Recency factor for unknown dates"
    )
    recency_1_year: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Recency factor for last year"
    )
    recency_1_3_years: float = Field(
        default=0.9, ge=0.0, le=1.0, description="Recency factor for 1-3 years"
    )
    recency_3_7_years: float = Field(
        default=0.7, ge=0.0, le=1.0, description="Recency factor for 3-7 years"
    )
    recency_7_plus_years: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Recency factor for 7+ years"
    )

    # Corroboration bonus
    corroboration_bonus: float = Field(
        default=1.2, ge=1.0, le=2.0, description="Multiplier for corroborated findings"
    )

    # Risk level thresholds
    moderate_threshold: int = Field(
        default=26, ge=0, le=100, description="Score threshold for MODERATE"
    )
    high_threshold: int = Field(default=51, ge=0, le=100, description="Score threshold for HIGH")
    critical_threshold: int = Field(
        default=76, ge=0, le=100, description="Score threshold for CRITICAL"
    )

    @property
    def severity_scores(self) -> dict[Severity, int]:
        """Get severity base scores as dict."""
        return {
            Severity.LOW: self.severity_low,
            Severity.MEDIUM: self.severity_medium,
            Severity.HIGH: self.severity_high,
            Severity.CRITICAL: self.severity_critical,
        }

    @property
    def category_weights(self) -> dict[FindingCategory, float]:
        """Get category weights as dict."""
        return {
            FindingCategory.CRIMINAL: self.criminal_weight,
            FindingCategory.FINANCIAL: self.financial_weight,
            FindingCategory.REGULATORY: self.regulatory_weight,
            FindingCategory.REPUTATION: self.reputation_weight,
            FindingCategory.VERIFICATION: self.verification_weight,
            FindingCategory.BEHAVIORAL: self.behavioral_weight,
            FindingCategory.NETWORK: self.network_weight,
        }


class RiskScorer:
    """Calculates composite risk scores from findings.

    The RiskScorer:
    1. Calculates composite scores (0-100) from classified findings
    2. Applies severity weighting based on finding severity
    3. Applies recency decay (older findings weighted less)
    4. Applies corroboration bonuses for multi-source findings
    5. Provides category breakdown and contributing factors
    6. Determines risk level and recommendation

    Example:
        ```python
        scorer = RiskScorer()

        score = scorer.calculate_risk_score(
            findings=findings,
            role_category=RoleCategory.FINANCIAL,
        )
        print(f"Overall: {score.overall_score}")
        print(f"Level: {score.risk_level}")
        print(f"Recommendation: {score.recommendation}")
        ```
    """

    def __init__(self, config: ScorerConfig | None = None):
        """Initialize the risk scorer.

        Args:
            config: Scorer configuration.
        """
        self.config = config or ScorerConfig()

    def calculate_risk_score(
        self,
        findings: list[Finding],
        role_category: RoleCategory,
        entity_id: UUID | None = None,
        screening_id: UUID | None = None,
    ) -> RiskScore:
        """Calculate overall risk score from findings.

        Args:
            findings: List of findings to score.
            role_category: Role for relevance weighting.
            entity_id: Optional entity ID for tracking.
            screening_id: Optional screening ID for tracking.

        Returns:
            RiskScore with overall score and breakdown.
        """
        if not findings:
            score = RiskScore(
                overall_score=0,
                risk_level=RiskLevel.LOW,
                category_scores={},
                contributing_factors={"total_findings": 0.0},
                recommendation=Recommendation.PROCEED,
                entity_id=entity_id,
                screening_id=screening_id,
            )
            logger.debug(
                "Risk score calculated",
                overall=0,
                level="low",
                findings_count=0,
            )
            return score

        # Calculate category scores
        category_scores = self._calculate_category_scores(findings)

        # Calculate weighted overall
        overall = self._calculate_overall_score(findings, category_scores)

        # Determine level and recommendation
        level = self._determine_risk_level(overall)
        recommendation = self._determine_recommendation(level, findings)

        # Identify contributing factors
        factors = self._identify_factors(findings)

        score = RiskScore(
            overall_score=min(int(overall), 100),
            risk_level=level,
            category_scores=category_scores,
            contributing_factors=factors,
            recommendation=recommendation,
            entity_id=entity_id,
            screening_id=screening_id,
        )

        logger.debug(
            "Risk score calculated",
            overall=score.overall_score,
            level=level.value,
            recommendation=recommendation.value,
            findings_count=len(findings),
            categories=len(category_scores),
        )

        return score

    def _calculate_category_scores(
        self,
        findings: list[Finding],
    ) -> dict[FindingCategory, int]:
        """Calculate score per category.

        Args:
            findings: List of findings.

        Returns:
            Dict mapping category to score.
        """
        scores: dict[FindingCategory, int] = {}

        # Group by category
        by_category: dict[FindingCategory, list[Finding]] = {}
        for f in findings:
            if f.category is None:
                continue
            if f.category not in by_category:
                by_category[f.category] = []
            by_category[f.category].append(f)

        # Score each category
        for category, category_findings in by_category.items():
            category_score = 0.0

            for finding in category_findings:
                # Base score from severity
                base = self.config.severity_scores.get(finding.severity, 0)

                # Apply recency decay
                recency_factor = self._calculate_recency_factor(finding.finding_date)

                # Apply confidence
                confidence_factor = finding.confidence if finding.confidence else 0.5

                # Apply corroboration bonus
                corroboration_bonus = (
                    self.config.corroboration_bonus if finding.corroborated else 1.0
                )

                # Apply relevance (if available from classifier)
                relevance_factor = (
                    finding.relevance_to_role if finding.relevance_to_role else 0.5
                )

                # Calculate finding score
                finding_score = (
                    base
                    * recency_factor
                    * confidence_factor
                    * corroboration_bonus
                    * relevance_factor
                )

                category_score += finding_score

            scores[category] = min(int(category_score), 100)

        return scores

    def _calculate_overall_score(
        self,
        findings: list[Finding],
        category_scores: dict[FindingCategory, int],
    ) -> float:
        """Calculate weighted overall score.

        Args:
            findings: List of findings.
            category_scores: Per-category scores.

        Returns:
            Weighted overall score.
        """
        if not category_scores:
            return 0.0

        weighted_sum = sum(
            score * self.config.category_weights.get(category, 1.0)
            for category, score in category_scores.items()
        )

        weight_total = sum(
            self.config.category_weights.get(category, 1.0) for category in category_scores.keys()
        )

        return weighted_sum / weight_total if weight_total else 0.0

    def _calculate_recency_factor(self, finding_date: date | None) -> float:
        """Calculate recency decay factor.

        More recent findings have higher weight:
        - Last year: 1.0
        - 1-3 years: 0.9
        - 3-7 years: 0.7
        - 7+ years: 0.5
        - Unknown: 0.8

        Args:
            finding_date: Date of the finding.

        Returns:
            Recency factor (0.5 - 1.0).
        """
        if not finding_date:
            return self.config.recency_unknown

        years_ago = (date.today() - finding_date).days / 365.25

        if years_ago <= 1:
            return self.config.recency_1_year
        elif years_ago <= 3:
            return self.config.recency_1_3_years
        elif years_ago <= 7:
            return self.config.recency_3_7_years
        else:
            return self.config.recency_7_plus_years

    def _determine_risk_level(self, score: float) -> RiskLevel:
        """Determine risk level from score.

        Args:
            score: Overall risk score.

        Returns:
            RiskLevel classification.
        """
        if score >= self.config.critical_threshold:
            return RiskLevel.CRITICAL
        elif score >= self.config.high_threshold:
            return RiskLevel.HIGH
        elif score >= self.config.moderate_threshold:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.LOW

    def _determine_recommendation(
        self,
        level: RiskLevel,
        findings: list[Finding],
    ) -> Recommendation:
        """Determine hiring recommendation.

        Args:
            level: Risk level.
            findings: List of findings.

        Returns:
            Recommendation for hiring decision.
        """
        # Check for any critical findings
        has_critical = any(f.severity == Severity.CRITICAL for f in findings)

        if has_critical or level == RiskLevel.CRITICAL:
            return Recommendation.DO_NOT_PROCEED
        elif level == RiskLevel.HIGH:
            return Recommendation.REVIEW_REQUIRED
        elif level == RiskLevel.MODERATE:
            return Recommendation.PROCEED_WITH_CAUTION
        else:
            return Recommendation.PROCEED

    def _identify_factors(self, findings: list[Finding]) -> dict[str, float]:
        """Identify contributing risk factors.

        Args:
            findings: List of findings.

        Returns:
            Dict of factor name to count/value.
        """
        today = date.today()
        factors = {
            "total_findings": float(len(findings)),
            "critical_findings": float(
                sum(1 for f in findings if f.severity == Severity.CRITICAL)
            ),
            "high_findings": float(sum(1 for f in findings if f.severity == Severity.HIGH)),
            "medium_findings": float(sum(1 for f in findings if f.severity == Severity.MEDIUM)),
            "low_findings": float(sum(1 for f in findings if f.severity == Severity.LOW)),
            "corroborated_findings": float(sum(1 for f in findings if f.corroborated)),
            "recent_findings": float(
                sum(
                    1
                    for f in findings
                    if f.finding_date and (today - f.finding_date).days <= 365
                )
            ),
            "categories_affected": float(
                len(set(f.category for f in findings if f.category is not None))
            ),
        }
        return factors

    def get_category_breakdown(
        self,
        score: RiskScore,
    ) -> list[tuple[FindingCategory, int, str]]:
        """Get sorted category breakdown with descriptions.

        Args:
            score: Calculated risk score.

        Returns:
            List of (category, score, description) tuples sorted by score desc.
        """
        descriptions = {
            FindingCategory.CRIMINAL: "Criminal history findings",
            FindingCategory.FINANCIAL: "Financial distress indicators",
            FindingCategory.REGULATORY: "Regulatory violations and sanctions",
            FindingCategory.REPUTATION: "Reputation and litigation concerns",
            FindingCategory.VERIFICATION: "Identity and credential issues",
            FindingCategory.BEHAVIORAL: "Behavioral pattern indicators",
            FindingCategory.NETWORK: "Network and association risks",
        }

        breakdown = [
            (category, cat_score, descriptions.get(category, "Unknown category"))
            for category, cat_score in score.category_scores.items()
        ]

        return sorted(breakdown, key=lambda x: x[1], reverse=True)


def create_risk_scorer(config: ScorerConfig | None = None) -> RiskScorer:
    """Create a risk scorer.

    Args:
        config: Optional scorer configuration.

    Returns:
        Configured RiskScorer.
    """
    return RiskScorer(config=config)
