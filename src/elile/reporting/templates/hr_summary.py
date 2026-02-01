"""HR Summary Report Content Builder.

This module provides the HRSummaryBuilder for generating HR Manager
summary reports with risk assessment, category breakdown, key findings,
and recommended actions in a user-friendly format.

Architecture Reference: docs/architecture/08-reporting.md - HR Manager Summary Report
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.core.logging import get_logger
from elile.investigation.finding_extractor import FindingCategory, Severity
from elile.risk.risk_scorer import Recommendation, RiskLevel
from elile.screening.result_compiler import (
    CategorySummary,
    CompiledResult,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
)

logger = get_logger(__name__)


# =============================================================================
# Enums and Constants
# =============================================================================


class CategoryStatus(str, Enum):
    """Status indicator for a category in HR report."""

    CLEAR = "clear"  # No issues found
    REVIEW = "review"  # Minor issues requiring review
    FLAG = "flag"  # Significant issues requiring attention
    FAIL = "fail"  # Critical issues found


# Category display names for user-friendly output
CATEGORY_DISPLAY_NAMES: dict[FindingCategory, str] = {
    FindingCategory.CRIMINAL: "Criminal",
    FindingCategory.FINANCIAL: "Financial",
    FindingCategory.REGULATORY: "Regulatory",
    FindingCategory.REPUTATION: "Reputation",
    FindingCategory.VERIFICATION: "Verification",
    FindingCategory.BEHAVIORAL: "Behavioral",
    FindingCategory.NETWORK: "Connections",
}

# Information type to category display name mapping
INFO_TYPE_DISPLAY_NAMES: dict[str, str] = {
    "identity": "Identity",
    "employment": "Employment",
    "education": "Education",
    "criminal": "Criminal",
    "civil": "Civil",
    "financial": "Financial",
    "licenses": "Licenses",
    "regulatory": "Regulatory",
    "sanctions": "Sanctions",
    "adverse_media": "Adverse Media",
    "digital_footprint": "Digital Footprint",
    "network_d2": "Connections (D2)",
    "network_d3": "Connections (D3)",
    "reconciliation": "Reconciliation",
}


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class RiskAssessmentDisplay:
    """Risk assessment display for HR summary.

    Provides visual representation of the risk score including
    a progress bar representation and clear action guidance.

    Attributes:
        score: Numeric risk score (0-100).
        level: Risk level classification.
        recommendation: Recommended action.
        recommendation_text: Human-readable recommendation.
        score_bar: Visual representation of score (e.g., "▓▓▓▓░░░░░░").
        score_percentage: Score as percentage string.
        requires_review: Whether manual review is required.
        review_reasons: List of reasons requiring review.
    """

    score: int = 0
    level: RiskLevel = RiskLevel.LOW
    recommendation: Recommendation = Recommendation.PROCEED
    recommendation_text: str = ""
    score_bar: str = ""
    score_percentage: str = "0%"
    requires_review: bool = False
    review_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "level": self.level.value,
            "recommendation": self.recommendation.value,
            "recommendation_text": self.recommendation_text,
            "score_bar": self.score_bar,
            "score_percentage": self.score_percentage,
            "requires_review": self.requires_review,
            "review_reasons": self.review_reasons,
        }


@dataclass
class FindingIndicator:
    """Pass/Flag/Fail indicator for a check category.

    Provides quick visual status for a specific check type.

    Attributes:
        name: Display name of the check.
        status: Pass/Flag/Fail status.
        icon: Icon character for display.
        note: Optional brief note.
    """

    name: str = ""
    status: CategoryStatus = CategoryStatus.CLEAR
    icon: str = "✓"
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "status": self.status.value,
            "icon": self.icon,
            "note": self.note,
        }


@dataclass
class CategoryScore:
    """Score breakdown for a single category.

    Provides detailed scoring for one check category.

    Attributes:
        category: Finding category.
        name: Display name.
        status: Overall status.
        score: Category score (0-100).
        findings_count: Number of findings.
        highest_severity: Highest severity in category.
        notes: Brief summary notes.
        key_items: List of key finding summaries.
    """

    category: FindingCategory = FindingCategory.VERIFICATION
    name: str = ""
    status: CategoryStatus = CategoryStatus.CLEAR
    score: int = 100
    findings_count: int = 0
    highest_severity: Severity | None = None
    notes: str = ""
    key_items: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "category": self.category.value,
            "name": self.name,
            "status": self.status.value,
            "score": self.score,
            "findings_count": self.findings_count,
            "highest_severity": self.highest_severity.value if self.highest_severity else None,
            "notes": self.notes,
            "key_items": self.key_items,
        }


@dataclass
class RecommendedAction:
    """A recommended action for HR to take.

    Attributes:
        action_id: Unique identifier.
        priority: Priority order (1 = highest).
        action: The recommended action text.
        reason: Why this action is recommended.
        related_category: Related finding category.
        related_findings: Number of related findings.
    """

    action_id: UUID = field(default_factory=uuid7)
    priority: int = 1
    action: str = ""
    reason: str = ""
    related_category: FindingCategory | None = None
    related_findings: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action_id": str(self.action_id),
            "priority": self.priority,
            "action": self.action,
            "reason": self.reason,
            "related_category": self.related_category.value if self.related_category else None,
            "related_findings": self.related_findings,
        }


@dataclass
class HRSummaryContent:
    """Complete HR Summary report content.

    This is the main output structure containing all sections
    of an HR Manager summary report.

    Attributes:
        content_id: Unique content identifier.
        screening_id: Reference to screening.
        generated_at: Generation timestamp.
        risk_assessment: Overall risk assessment display.
        key_findings: List of Pass/Flag/Fail indicators.
        category_breakdown: Detailed category scores.
        recommended_actions: List of recommended actions.
        overall_narrative: Human-readable summary.
        verification_status: Overall verification status.
        data_completeness: Data completeness percentage.
        connection_summary: Network analysis summary (if applicable).
    """

    content_id: UUID = field(default_factory=uuid7)
    screening_id: UUID | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Core sections
    risk_assessment: RiskAssessmentDisplay = field(default_factory=RiskAssessmentDisplay)
    key_findings: list[FindingIndicator] = field(default_factory=list)
    category_breakdown: list[CategoryScore] = field(default_factory=list)
    recommended_actions: list[RecommendedAction] = field(default_factory=list)

    # Summary information
    overall_narrative: str = ""
    verification_status: str = "complete"
    data_completeness: float = 1.0

    # Optional network summary
    connection_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "content_id": str(self.content_id),
            "screening_id": str(self.screening_id) if self.screening_id else None,
            "generated_at": self.generated_at.isoformat(),
            "risk_assessment": self.risk_assessment.to_dict(),
            "key_findings": [f.to_dict() for f in self.key_findings],
            "category_breakdown": [c.to_dict() for c in self.category_breakdown],
            "recommended_actions": [a.to_dict() for a in self.recommended_actions],
            "overall_narrative": self.overall_narrative,
            "verification_status": self.verification_status,
            "data_completeness": self.data_completeness,
            "connection_summary": self.connection_summary,
        }


# =============================================================================
# Builder Configuration
# =============================================================================


class HRSummaryConfig(BaseModel):
    """Configuration for HRSummaryBuilder."""

    # Score thresholds for status determination
    clear_threshold: int = Field(default=25, ge=0, le=100, description="Max score for CLEAR status")
    review_threshold: int = Field(
        default=50, ge=0, le=100, description="Max score for REVIEW status"
    )
    flag_threshold: int = Field(default=75, ge=0, le=100, description="Max score for FLAG status")

    # Display settings
    score_bar_width: int = Field(default=30, ge=10, le=50, description="Width of score bar")
    max_key_items: int = Field(default=3, ge=1, le=10, description="Max key items per category")
    max_recommended_actions: int = Field(
        default=5, ge=1, le=10, description="Max recommended actions"
    )

    # Content settings
    include_connection_summary: bool = Field(
        default=True, description="Include connection summary for D2/D3"
    )
    generate_narrative: bool = Field(default=True, description="Generate overall narrative")

    # Category weights for score calculation (higher = more impactful)
    category_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "criminal": 1.5,
            "financial": 1.2,
            "regulatory": 1.3,
            "verification": 1.0,
            "reputation": 0.8,
            "behavioral": 1.0,
            "network": 0.9,
        }
    )


# =============================================================================
# HR Summary Builder
# =============================================================================


class HRSummaryBuilder:
    """Builder for HR Manager summary report content.

    Transforms compiled screening results into user-friendly HR summary
    content with risk visualization, key findings, and actionable
    recommendations.

    Example:
        ```python
        builder = HRSummaryBuilder()

        # Build from compiled result
        content = builder.build(compiled_result)

        # Access sections
        print(f"Risk Score: {content.risk_assessment.score}")
        print(f"Recommendation: {content.risk_assessment.recommendation_text}")

        for indicator in content.key_findings:
            print(f"{indicator.icon} {indicator.name}: {indicator.status.value}")

        for action in content.recommended_actions:
            print(f"{action.priority}. {action.action}")
        ```

    Attributes:
        config: Builder configuration.
    """

    def __init__(self, config: HRSummaryConfig | None = None) -> None:
        """Initialize the HR Summary builder.

        Args:
            config: Builder configuration.
        """
        self.config = config or HRSummaryConfig()

    def build(self, compiled_result: CompiledResult) -> HRSummaryContent:
        """Build HR summary content from compiled screening result.

        Args:
            compiled_result: The compiled screening result.

        Returns:
            HRSummaryContent with all sections populated.
        """
        logger.info(
            "Building HR summary content",
            screening_id=(
                str(compiled_result.screening_id) if compiled_result.screening_id else None
            ),
            risk_score=compiled_result.risk_score,
        )

        # Build each section
        risk_assessment = self._build_risk_assessment(compiled_result)
        key_findings = self._build_key_findings(compiled_result)
        category_breakdown = self._build_category_breakdown(compiled_result)
        recommended_actions = self._build_recommended_actions(compiled_result, category_breakdown)

        # Build connection summary if applicable
        connection_summary = None
        if (
            self.config.include_connection_summary
            and compiled_result.connection_summary.entities_discovered > 0
        ):
            connection_summary = self._build_connection_summary(compiled_result.connection_summary)

        # Build narrative
        narrative = ""
        if self.config.generate_narrative:
            narrative = self._build_narrative(
                compiled_result, risk_assessment, key_findings, category_breakdown
            )

        content = HRSummaryContent(
            screening_id=compiled_result.screening_id,
            risk_assessment=risk_assessment,
            key_findings=key_findings,
            category_breakdown=category_breakdown,
            recommended_actions=recommended_actions,
            overall_narrative=narrative,
            verification_status=compiled_result.findings_summary.verification_status,
            data_completeness=compiled_result.findings_summary.data_completeness,
            connection_summary=connection_summary,
        )

        logger.info(
            "HR summary content built",
            content_id=str(content.content_id),
            findings_count=len(key_findings),
            categories_count=len(category_breakdown),
            actions_count=len(recommended_actions),
        )

        return content

    def _build_risk_assessment(self, compiled_result: CompiledResult) -> RiskAssessmentDisplay:
        """Build the risk assessment display section.

        Args:
            compiled_result: The compiled screening result.

        Returns:
            RiskAssessmentDisplay with score visualization.
        """
        score = compiled_result.risk_score
        level = RiskLevel(compiled_result.risk_level)
        recommendation = Recommendation(compiled_result.recommendation)

        # Generate score bar
        filled = int((score / 100) * self.config.score_bar_width)
        empty = self.config.score_bar_width - filled
        score_bar = "▓" * filled + "░" * empty

        # Generate recommendation text
        recommendation_text = self._get_recommendation_text(recommendation, level)

        # Determine if review required and why
        requires_review = recommendation in (
            Recommendation.REVIEW_REQUIRED,
            Recommendation.PROCEED_WITH_CAUTION,
        )
        review_reasons = self._get_review_reasons(compiled_result)

        return RiskAssessmentDisplay(
            score=score,
            level=level,
            recommendation=recommendation,
            recommendation_text=recommendation_text,
            score_bar=score_bar,
            score_percentage=f"{score}%",
            requires_review=requires_review,
            review_reasons=review_reasons,
        )

    def _get_recommendation_text(self, recommendation: Recommendation, level: RiskLevel) -> str:
        """Get human-readable recommendation text.

        Args:
            recommendation: The recommendation enum.
            level: The risk level.

        Returns:
            Human-readable recommendation string.
        """
        texts = {
            Recommendation.PROCEED: "Proceed with hiring.",
            Recommendation.PROCEED_WITH_CAUTION: "Proceed with caution. Review flagged items.",
            Recommendation.REVIEW_REQUIRED: "Manual review required before decision.",
            Recommendation.DO_NOT_PROCEED: "Do not proceed. Critical issues identified.",
        }
        base_text = texts.get(recommendation, "Review required.")

        # Add level context
        if level == RiskLevel.MODERATE:
            base_text += " Minor concerns noted."
        elif level == RiskLevel.HIGH:
            base_text += " Significant concerns require attention."
        elif level == RiskLevel.CRITICAL:
            base_text += " Critical findings require immediate review."

        return base_text

    def _get_review_reasons(self, compiled_result: CompiledResult) -> list[str]:
        """Get list of reasons requiring review.

        Args:
            compiled_result: The compiled screening result.

        Returns:
            List of review reason strings.
        """
        reasons = []
        findings_summary = compiled_result.findings_summary

        # Check for critical/high findings
        critical_count = findings_summary.by_severity.get(Severity.CRITICAL, 0)
        high_count = findings_summary.by_severity.get(Severity.HIGH, 0)

        if critical_count > 0:
            reasons.append(f"{critical_count} critical finding(s) require immediate attention")
        if high_count > 0:
            reasons.append(f"{high_count} high severity finding(s) warrant review")

        # Check for specific category concerns
        for category, summary in findings_summary.by_category.items():
            if summary.critical_count > 0:
                name = CATEGORY_DISPLAY_NAMES.get(category, category.value)
                reasons.append(f"Critical {name.lower()} issue(s) found")
            elif summary.high_count > 0 and category in (
                FindingCategory.CRIMINAL,
                FindingCategory.FINANCIAL,
            ):
                name = CATEGORY_DISPLAY_NAMES.get(category, category.value)
                reasons.append(f"High severity {name.lower()} finding(s)")

        # Check for verification issues
        verification = findings_summary.by_category.get(FindingCategory.VERIFICATION)
        if (
            verification
            and verification.total_findings > 0
            and (verification.high_count > 0 or verification.critical_count > 0)
        ):
            reasons.append("Verification discrepancies detected")

        # Check connection risks
        connection_summary = compiled_result.connection_summary
        if connection_summary.critical_connections > 0:
            reasons.append(f"{connection_summary.critical_connections} critical connection(s)")
        if connection_summary.sanctions_connections > 0:
            reasons.append("Sanctions list connection(s) identified")
        if connection_summary.pep_connections > 0:
            reasons.append("Politically exposed person connection(s)")

        return reasons[:5]  # Limit to top 5 reasons

    def _build_key_findings(self, compiled_result: CompiledResult) -> list[FindingIndicator]:
        """Build Pass/Flag/Fail indicators for key check types.

        Args:
            compiled_result: The compiled screening result.

        Returns:
            List of FindingIndicator for each check type.
        """
        indicators = []
        findings_summary = compiled_result.findings_summary
        investigation_summary = compiled_result.investigation_summary

        # Define the standard checks to report
        check_types = [
            ("Identity", "identity", FindingCategory.VERIFICATION),
            ("Employment", "employment", FindingCategory.VERIFICATION),
            ("Education", "education", FindingCategory.VERIFICATION),
            ("Criminal Records", "criminal", FindingCategory.CRIMINAL),
            ("Financial", "financial", FindingCategory.FINANCIAL),
            ("Sanctions/PEP", "sanctions", FindingCategory.REGULATORY),
            ("Licenses", "licenses", FindingCategory.REGULATORY),
            ("Adverse Media", "adverse_media", FindingCategory.REPUTATION),
        ]

        for display_name, info_type, category in check_types:
            indicator = self._build_indicator_for_type(
                display_name, info_type, category, findings_summary, investigation_summary
            )
            indicators.append(indicator)

        # Add connection indicator if D2/D3 was performed
        connection_summary = compiled_result.connection_summary
        if connection_summary.entities_discovered > 0:
            conn_indicator = self._build_connection_indicator(connection_summary)
            indicators.append(conn_indicator)

        return indicators

    def _build_indicator_for_type(
        self,
        display_name: str,
        info_type: str,
        category: FindingCategory,
        findings_summary: FindingsSummary,
        investigation_summary: InvestigationSummary,
    ) -> FindingIndicator:
        """Build indicator for a specific check type.

        Args:
            display_name: Display name for the check.
            info_type: Information type key.
            category: Finding category.
            findings_summary: Findings summary.
            investigation_summary: Investigation summary.

        Returns:
            FindingIndicator for this check type.
        """
        # Check if this type was processed
        from elile.agent.state import InformationType

        try:
            info_type_enum = InformationType(info_type)
            type_summary = investigation_summary.by_type.get(info_type_enum)
            was_processed = type_summary is not None and type_summary.iterations_completed > 0
        except ValueError:
            was_processed = False
            type_summary = None

        if not was_processed:
            # Type was not processed - show as not applicable
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.CLEAR,
                icon="—",
                note="Not checked",
            )

        # Get category findings
        category_summary = findings_summary.by_category.get(category)

        if category_summary is None or category_summary.total_findings == 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.CLEAR,
                icon="✓",
                note="No issues found",
            )

        # Determine status based on findings
        if category_summary.critical_count > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.FAIL,
                icon="✗",
                note=f"{category_summary.critical_count} critical issue(s)",
            )
        elif category_summary.high_count > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.FLAG,
                icon="⚠",
                note=f"{category_summary.high_count} high severity issue(s)",
            )
        elif category_summary.medium_count > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.REVIEW,
                icon="⚠",
                note=f"{category_summary.medium_count} item(s) to review",
            )
        else:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.CLEAR,
                icon="✓",
                note=f"{category_summary.low_count} minor item(s)",
            )

    def _build_connection_indicator(
        self, connection_summary: ConnectionSummary
    ) -> FindingIndicator:
        """Build indicator for connection/network analysis.

        Args:
            connection_summary: Connection analysis summary.

        Returns:
            FindingIndicator for connections.
        """
        display_name = "Connections"

        if connection_summary.critical_connections > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.FAIL,
                icon="✗",
                note=f"{connection_summary.critical_connections} critical connection(s)",
            )
        elif connection_summary.high_risk_connections > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.FLAG,
                icon="⚠",
                note=f"{connection_summary.high_risk_connections} high risk connection(s)",
            )
        elif connection_summary.risk_connections > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.REVIEW,
                icon="⚠",
                note=f"{connection_summary.risk_connections} connection(s) to review",
            )
        elif connection_summary.pep_connections > 0 or connection_summary.sanctions_connections > 0:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.FLAG,
                icon="⚠",
                note="PEP or sanctions connections",
            )
        else:
            return FindingIndicator(
                name=display_name,
                status=CategoryStatus.CLEAR,
                icon="✓",
                note="No adverse connections",
            )

    def _build_category_breakdown(self, compiled_result: CompiledResult) -> list[CategoryScore]:
        """Build detailed category score breakdown.

        Args:
            compiled_result: The compiled screening result.

        Returns:
            List of CategoryScore for each category with findings.
        """
        scores = []
        findings_summary = compiled_result.findings_summary

        # Process each category with findings
        for category, summary in findings_summary.by_category.items():
            score = self._build_category_score(category, summary)
            scores.append(score)

        # Add categories that were checked but had no findings
        checked_categories = set(findings_summary.by_category.keys())
        all_categories = [
            FindingCategory.CRIMINAL,
            FindingCategory.FINANCIAL,
            FindingCategory.REGULATORY,
            FindingCategory.VERIFICATION,
            FindingCategory.REPUTATION,
        ]

        for category in all_categories:
            if category not in checked_categories:
                scores.append(
                    CategoryScore(
                        category=category,
                        name=CATEGORY_DISPLAY_NAMES.get(category, category.value),
                        status=CategoryStatus.CLEAR,
                        score=100,
                        findings_count=0,
                        highest_severity=None,
                        notes="No records found",
                        key_items=[],
                    )
                )

        # Sort by score (lowest first, i.e., most concerning first)
        scores.sort(key=lambda x: (x.score, x.name))

        return scores

    def _build_category_score(
        self, category: FindingCategory, summary: CategorySummary
    ) -> CategoryScore:
        """Build score for a single category.

        Args:
            category: The finding category.
            summary: The category summary.

        Returns:
            CategoryScore for this category.
        """
        display_name = CATEGORY_DISPLAY_NAMES.get(category, category.value.title())

        # Calculate score (100 = perfect, lower = more concerning)
        score = self._calculate_category_score(summary)

        # Determine status
        if score >= 100 - self.config.clear_threshold:
            status = CategoryStatus.CLEAR
        elif score >= 100 - self.config.review_threshold:
            status = CategoryStatus.REVIEW
        elif score >= 100 - self.config.flag_threshold:
            status = CategoryStatus.FLAG
        else:
            status = CategoryStatus.FAIL

        # Generate notes
        notes = self._generate_category_notes(summary, status)

        # Get key items (limited)
        key_items = summary.key_findings[: self.config.max_key_items]

        return CategoryScore(
            category=category,
            name=display_name,
            status=status,
            score=score,
            findings_count=summary.total_findings,
            highest_severity=summary.highest_severity,
            notes=notes,
            key_items=key_items,
        )

    def _calculate_category_score(self, summary: CategorySummary) -> int:
        """Calculate a 0-100 score for a category.

        Higher scores are better (100 = no issues).

        Args:
            summary: The category summary.

        Returns:
            Score from 0-100.
        """
        if summary.total_findings == 0:
            return 100

        # Base deductions per severity
        deductions = 0
        deductions += summary.critical_count * 30
        deductions += summary.high_count * 20
        deductions += summary.medium_count * 10
        deductions += summary.low_count * 3

        # Bonus for corroboration (indicates higher accuracy, not additional concern)
        # But corroborated critical findings are more concerning
        if summary.corroborated_count > 0 and summary.critical_count > 0:
            deductions += 10  # Additional concern for corroborated critical findings

        # Cap at 100 deduction
        deductions = min(deductions, 100)

        return max(0, 100 - deductions)

    def _generate_category_notes(self, summary: CategorySummary, _status: CategoryStatus) -> str:
        """Generate brief notes for a category.

        Args:
            summary: The category summary.
            _status: The determined status (reserved for future use).

        Returns:
            Brief notes string.
        """
        if summary.total_findings == 0:
            return "No records found"

        parts = []

        if summary.critical_count > 0:
            parts.append(f"{summary.critical_count} critical")
        if summary.high_count > 0:
            parts.append(f"{summary.high_count} high")
        if summary.medium_count > 0:
            parts.append(f"{summary.medium_count} medium")

        if not parts and summary.low_count > 0:
            return f"{summary.low_count} minor item(s)"

        finding_text = ", ".join(parts)

        if summary.corroborated_count > 0:
            finding_text += f" ({summary.corroborated_count} corroborated)"

        return finding_text

    def _build_recommended_actions(
        self, compiled_result: CompiledResult, category_breakdown: list[CategoryScore]
    ) -> list[RecommendedAction]:
        """Build list of recommended actions based on findings.

        Args:
            compiled_result: The compiled screening result.
            category_breakdown: The category scores.

        Returns:
            List of RecommendedAction in priority order.
        """
        actions: list[RecommendedAction] = []
        priority = 1

        # Collect issues that need action
        findings_summary = compiled_result.findings_summary
        connection_summary = compiled_result.connection_summary

        # 1. Address critical findings first
        for cat_score in category_breakdown:
            if cat_score.status == CategoryStatus.FAIL:
                action = self._create_critical_action(cat_score, priority)
                actions.append(action)
                priority += 1

        # 2. Review high severity findings
        for cat_score in category_breakdown:
            if (
                cat_score.status == CategoryStatus.FLAG
                and cat_score.highest_severity == Severity.HIGH
            ):
                action = self._create_review_action(cat_score, priority)
                actions.append(action)
                priority += 1

        # 3. Verification discrepancies
        verification = findings_summary.by_category.get(FindingCategory.VERIFICATION)
        if verification and verification.high_count > 0:
            actions.append(
                RecommendedAction(
                    priority=priority,
                    action="Verify employment and education details directly with institutions",
                    reason="Discrepancies detected in verification records",
                    related_category=FindingCategory.VERIFICATION,
                    related_findings=verification.high_count,
                )
            )
            priority += 1

        # 4. Connection/network concerns
        if connection_summary.pep_connections > 0:
            actions.append(
                RecommendedAction(
                    priority=priority,
                    action="Review politically exposed person connections for relevance",
                    reason=f"{connection_summary.pep_connections} PEP connection(s) identified",
                    related_category=FindingCategory.NETWORK,
                    related_findings=connection_summary.pep_connections,
                )
            )
            priority += 1

        if connection_summary.sanctions_connections > 0:
            actions.append(
                RecommendedAction(
                    priority=priority,
                    action="Escalate sanctions list connections for compliance review",
                    reason=f"{connection_summary.sanctions_connections} sanctions connection(s)",
                    related_category=FindingCategory.NETWORK,
                    related_findings=connection_summary.sanctions_connections,
                )
            )
            priority += 1

        # 5. General proceed action if no major issues
        if not actions:
            recommendation = Recommendation(compiled_result.recommendation)
            if recommendation == Recommendation.PROCEED:
                actions.append(
                    RecommendedAction(
                        priority=1,
                        action="Proceed with hiring process",
                        reason="No significant concerns identified",
                        related_category=None,
                        related_findings=0,
                    )
                )
            else:
                actions.append(
                    RecommendedAction(
                        priority=1,
                        action="Complete standard HR review before proceeding",
                        reason="Minor items noted for awareness",
                        related_category=None,
                        related_findings=findings_summary.total_findings,
                    )
                )

        # Limit to max configured actions
        return actions[: self.config.max_recommended_actions]

    def _create_critical_action(self, cat_score: CategoryScore, priority: int) -> RecommendedAction:
        """Create action for critical category issues.

        Args:
            cat_score: The category score with critical issues.
            priority: Action priority.

        Returns:
            RecommendedAction for critical issues.
        """
        category_name = cat_score.name.lower()

        action_templates = {
            FindingCategory.CRIMINAL: "Conduct detailed review of criminal findings before proceeding",
            FindingCategory.FINANCIAL: "Review financial findings and verify current status",
            FindingCategory.REGULATORY: "Verify regulatory compliance and license status",
            FindingCategory.VERIFICATION: "Investigate verification discrepancies with direct sources",
            FindingCategory.REPUTATION: "Review adverse media findings for relevance and accuracy",
            FindingCategory.BEHAVIORAL: "Assess behavioral pattern concerns with additional context",
            FindingCategory.NETWORK: "Evaluate network connections for potential conflicts",
        }

        action_text = action_templates.get(
            cat_score.category, f"Review {category_name} findings before proceeding"
        )

        return RecommendedAction(
            priority=priority,
            action=action_text,
            reason=f"Critical {category_name} issues identified",
            related_category=cat_score.category,
            related_findings=cat_score.findings_count,
        )

    def _create_review_action(self, cat_score: CategoryScore, priority: int) -> RecommendedAction:
        """Create action for flagged category issues.

        Args:
            cat_score: The category score with flagged issues.
            priority: Action priority.

        Returns:
            RecommendedAction for flagged issues.
        """
        category_name = cat_score.name.lower()

        return RecommendedAction(
            priority=priority,
            action=f"Review {category_name} findings for context and recency",
            reason=f"High severity {category_name} finding(s) warrant attention",
            related_category=cat_score.category,
            related_findings=cat_score.findings_count,
        )

    def _build_connection_summary(self, connection_summary: ConnectionSummary) -> dict[str, Any]:
        """Build simplified connection summary for HR.

        Args:
            connection_summary: Full connection summary.

        Returns:
            Dictionary with key connection metrics.
        """
        return {
            "entities_discovered": connection_summary.entities_discovered,
            "risk_connections": connection_summary.risk_connections,
            "highest_risk_level": connection_summary.highest_risk_level.value,
            "pep_connections": connection_summary.pep_connections,
            "sanctions_connections": connection_summary.sanctions_connections,
            "key_risks": connection_summary.key_risks[:3],  # Limit for HR summary
        }

    def _build_narrative(
        self,
        _compiled_result: CompiledResult,
        risk_assessment: RiskAssessmentDisplay,
        key_findings: list[FindingIndicator],
        category_breakdown: list[CategoryScore],
    ) -> str:
        """Build overall narrative summary for HR.

        Args:
            _compiled_result: The compiled screening result (reserved for future use).
            risk_assessment: The risk assessment display.
            key_findings: The key findings indicators.
            category_breakdown: The category scores.

        Returns:
            Human-readable narrative string.
        """
        parts = []

        # Opening with risk level
        level = risk_assessment.level
        score = risk_assessment.score

        if level == RiskLevel.LOW:
            parts.append(
                f"The background screening has been completed with a risk score of {score}/100. "
                "No significant concerns were identified."
            )
        elif level == RiskLevel.MODERATE:
            parts.append(
                f"The background screening has been completed with a moderate risk score of {score}/100. "
                "Some items require review before proceeding."
            )
        elif level == RiskLevel.HIGH:
            parts.append(
                f"The background screening has identified significant concerns with a risk score of {score}/100. "
                "Manual review is required before proceeding."
            )
        else:
            parts.append(
                f"The background screening has identified critical issues with a risk score of {score}/100. "
                "Immediate review is required."
            )

        # Summarize key findings
        clear_count = sum(1 for f in key_findings if f.status == CategoryStatus.CLEAR)
        flag_count = sum(
            1 for f in key_findings if f.status in (CategoryStatus.FLAG, CategoryStatus.REVIEW)
        )
        fail_count = sum(1 for f in key_findings if f.status == CategoryStatus.FAIL)

        if fail_count > 0:
            parts.append(f"{fail_count} check(s) resulted in critical findings.")
        if flag_count > 0:
            parts.append(f"{flag_count} check(s) have items flagged for review.")
        if clear_count > 0 and fail_count == 0:
            parts.append(f"{clear_count} check(s) passed with no issues.")

        # Mention key areas of concern
        concerning_categories = [
            c for c in category_breakdown if c.status in (CategoryStatus.FLAG, CategoryStatus.FAIL)
        ]
        if concerning_categories:
            names = [c.name for c in concerning_categories[:3]]
            if len(names) == 1:
                parts.append(f"Primary area of concern: {names[0]}.")
            else:
                parts.append(f"Key areas of concern: {', '.join(names)}.")

        # Recommendation
        parts.append(risk_assessment.recommendation_text)

        return " ".join(parts)


# =============================================================================
# Factory Functions
# =============================================================================


def create_hr_summary_builder(config: HRSummaryConfig | None = None) -> HRSummaryBuilder:
    """Factory function to create an HR Summary builder.

    Args:
        config: Optional builder configuration.

    Returns:
        Configured HRSummaryBuilder instance.
    """
    return HRSummaryBuilder(config=config)
