"""Severity Calculator for determining finding severity levels.

This module provides the SeverityCalculator that:
1. Determines severity using rule-based assessment
2. Supports AI-assisted severity for ambiguous cases
3. Applies context-based adjustments (role, recency, etc.)
4. Provides audit trail for severity decisions
"""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.compliance.types import RoleCategory
from elile.core.logging import get_logger
from elile.investigation.finding_extractor import Finding, FindingCategory, Severity
from elile.risk.finding_classifier import SubCategory

logger = get_logger(__name__)


# =============================================================================
# Severity Rules Configuration
# =============================================================================


# Rule-based severity by finding type patterns
SEVERITY_RULES: dict[str, Severity] = {
    # Critical patterns
    "felony conviction": Severity.CRITICAL,
    "active warrant": Severity.CRITICAL,
    "sex offense": Severity.CRITICAL,
    "violent crime": Severity.CRITICAL,
    "murder": Severity.CRITICAL,
    "manslaughter": Severity.CRITICAL,
    "terrorism": Severity.CRITICAL,
    "ofac sanction": Severity.CRITICAL,
    "sanctions list": Severity.CRITICAL,
    "money laundering": Severity.CRITICAL,
    "embezzlement": Severity.CRITICAL,
    "fraud conviction": Severity.CRITICAL,
    "identity theft conviction": Severity.CRITICAL,
    "pep designation": Severity.CRITICAL,
    # High patterns
    "recent bankruptcy": Severity.HIGH,
    "chapter 7 bankruptcy": Severity.HIGH,
    "license revocation": Severity.HIGH,
    "license suspension": Severity.HIGH,
    "dui conviction": Severity.HIGH,
    "dwi conviction": Severity.HIGH,
    "drug conviction": Severity.HIGH,
    "assault conviction": Severity.HIGH,
    "theft conviction": Severity.HIGH,
    "forgery": Severity.HIGH,
    "regulatory enforcement": Severity.HIGH,
    "finra bar": Severity.HIGH,
    "sec action": Severity.HIGH,
    "tax evasion": Severity.HIGH,
    "tax lien": Severity.HIGH,
    "deception detected": Severity.HIGH,
    "fabricated": Severity.HIGH,
    "systematic inconsistency": Severity.HIGH,
    # Medium patterns
    "misdemeanor conviction": Severity.MEDIUM,
    "civil judgment": Severity.MEDIUM,
    "bankruptcy discharged": Severity.MEDIUM,
    "traffic violation": Severity.MEDIUM,
    "collection account": Severity.MEDIUM,
    "employment discrepancy": Severity.MEDIUM,
    "education discrepancy": Severity.MEDIUM,
    "adverse media": Severity.MEDIUM,
    "litigation": Severity.MEDIUM,
    "lawsuit": Severity.MEDIUM,
    "complaint filed": Severity.MEDIUM,
    "warning letter": Severity.MEDIUM,
    "shell company connection": Severity.MEDIUM,
    # Low patterns
    "employment gap": Severity.LOW,
    "address discrepancy": Severity.LOW,
    "minor traffic": Severity.LOW,
    "parking violation": Severity.LOW,
    "name variation": Severity.LOW,
    "date discrepancy minor": Severity.LOW,
    "professional membership lapsed": Severity.LOW,
}

# Subcategory to default severity mapping
SUBCATEGORY_SEVERITY: dict[SubCategory, Severity] = {
    # Criminal - generally high/critical
    SubCategory.CRIMINAL_FELONY: Severity.CRITICAL,
    SubCategory.CRIMINAL_VIOLENT: Severity.CRITICAL,
    SubCategory.CRIMINAL_SEX: Severity.CRITICAL,
    SubCategory.CRIMINAL_FINANCIAL: Severity.HIGH,
    SubCategory.CRIMINAL_DRUG: Severity.HIGH,
    SubCategory.CRIMINAL_DUI: Severity.HIGH,
    SubCategory.CRIMINAL_MISDEMEANOR: Severity.MEDIUM,
    SubCategory.CRIMINAL_TRAFFIC: Severity.LOW,
    # Financial
    SubCategory.FINANCIAL_BANKRUPTCY: Severity.HIGH,
    SubCategory.FINANCIAL_JUDGMENT: Severity.MEDIUM,
    SubCategory.FINANCIAL_LIEN: Severity.MEDIUM,
    SubCategory.FINANCIAL_FORECLOSURE: Severity.MEDIUM,
    SubCategory.FINANCIAL_COLLECTION: Severity.LOW,
    SubCategory.FINANCIAL_CREDIT: Severity.LOW,
    # Regulatory
    SubCategory.REGULATORY_SANCTION: Severity.CRITICAL,
    SubCategory.REGULATORY_PEP: Severity.CRITICAL,
    SubCategory.REGULATORY_BAR: Severity.HIGH,
    SubCategory.REGULATORY_ENFORCEMENT: Severity.HIGH,
    SubCategory.REGULATORY_LICENSE: Severity.MEDIUM,
    # Reputation
    SubCategory.REPUTATION_LITIGATION: Severity.MEDIUM,
    SubCategory.REPUTATION_MEDIA: Severity.MEDIUM,
    SubCategory.REPUTATION_COMPLAINT: Severity.LOW,
    SubCategory.REPUTATION_SOCIAL: Severity.LOW,
    # Verification
    SubCategory.VERIFICATION_IDENTITY: Severity.HIGH,
    SubCategory.VERIFICATION_DISCREPANCY: Severity.MEDIUM,
    SubCategory.VERIFICATION_EMPLOYMENT: Severity.MEDIUM,
    SubCategory.VERIFICATION_EDUCATION: Severity.MEDIUM,
    SubCategory.VERIFICATION_GAP: Severity.LOW,
    # Behavioral
    SubCategory.BEHAVIORAL_DECEPTION: Severity.HIGH,
    SubCategory.BEHAVIORAL_PATTERN: Severity.MEDIUM,
    # Network
    SubCategory.NETWORK_PEP: Severity.HIGH,
    SubCategory.NETWORK_SHELL: Severity.MEDIUM,
    SubCategory.NETWORK_ASSOCIATION: Severity.LOW,
    # Default
    SubCategory.UNCLASSIFIED: Severity.MEDIUM,
}

# Role-based severity adjustments (category, role) -> adjustment
# Positive = increase severity, negative = decrease
ROLE_SEVERITY_ADJUSTMENTS: dict[tuple[FindingCategory, RoleCategory], int] = {
    # Criminal findings more severe for government/security roles
    (FindingCategory.CRIMINAL, RoleCategory.GOVERNMENT): +1,
    (FindingCategory.CRIMINAL, RoleCategory.SECURITY): +1,
    (FindingCategory.CRIMINAL, RoleCategory.EDUCATION): +1,  # Working with children
    # Financial findings more severe for finance roles
    (FindingCategory.FINANCIAL, RoleCategory.FINANCIAL): +1,
    (FindingCategory.FINANCIAL, RoleCategory.EXECUTIVE): +1,
    # Regulatory findings more severe for regulated industries
    (FindingCategory.REGULATORY, RoleCategory.FINANCIAL): +1,
    (FindingCategory.REGULATORY, RoleCategory.HEALTHCARE): +1,
    # Verification findings more severe for security-sensitive roles
    (FindingCategory.VERIFICATION, RoleCategory.GOVERNMENT): +1,
    (FindingCategory.VERIFICATION, RoleCategory.SECURITY): +1,
}


# =============================================================================
# Models
# =============================================================================


@dataclass
class SeverityDecision:
    """Record of a severity determination decision.

    Provides audit trail for how severity was calculated.
    """

    decision_id: UUID = field(default_factory=uuid7)
    finding_id: UUID | None = None
    initial_severity: Severity = Severity.MEDIUM
    final_severity: Severity = Severity.MEDIUM
    determination_method: str = "rule"  # rule, subcategory, ai, default
    matched_rules: list[str] = field(default_factory=list)
    role_adjustment: int = 0
    recency_adjustment: int = 0
    context_notes: list[str] = field(default_factory=list)
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "decision_id": str(self.decision_id),
            "finding_id": str(self.finding_id) if self.finding_id else None,
            "initial_severity": self.initial_severity.value,
            "final_severity": self.final_severity.value,
            "determination_method": self.determination_method,
            "matched_rules": self.matched_rules,
            "role_adjustment": self.role_adjustment,
            "recency_adjustment": self.recency_adjustment,
            "context_notes": self.context_notes,
            "decided_at": self.decided_at.isoformat(),
        }


class CalculatorConfig(BaseModel):
    """Configuration for severity calculator."""

    # Rule matching
    use_rule_matching: bool = Field(default=True, description="Enable rule-based matching")
    use_subcategory_defaults: bool = Field(
        default=True, description="Use subcategory default severities"
    )
    use_ai_fallback: bool = Field(
        default=False, description="Use AI for ambiguous cases (requires AI adapter)"
    )

    # Context adjustments
    enable_role_adjustment: bool = Field(
        default=True, description="Adjust severity based on role"
    )
    enable_recency_adjustment: bool = Field(
        default=True, description="Increase severity for recent findings"
    )

    # Recency thresholds (days)
    recent_boost_days: int = Field(
        default=365, ge=0, description="Days for recent finding boost"
    )
    recency_boost_amount: int = Field(
        default=1, ge=0, le=2, description="Severity levels to boost for recent"
    )

    # Default behavior
    default_severity: Severity = Field(
        default=Severity.MEDIUM, description="Default when no rules match"
    )


class AIModelProtocol(Protocol):
    """Protocol for AI model adapter for severity assessment."""

    async def assess_severity(
        self,
        finding_summary: str,
        finding_details: str,
        category: FindingCategory | None,
        context: dict[str, Any],
    ) -> Severity:
        """Assess severity using AI model."""
        ...


# =============================================================================
# Severity Calculator
# =============================================================================


class SeverityCalculator:
    """Calculates finding severity using rules and optional AI.

    The SeverityCalculator:
    1. Matches finding text against rule patterns
    2. Falls back to subcategory-based defaults
    3. Optionally uses AI for ambiguous cases
    4. Applies role and recency adjustments
    5. Produces audit trail for decisions

    Example:
        ```python
        calculator = SeverityCalculator()

        severity, decision = calculator.calculate_severity(
            finding=finding,
            role_category=RoleCategory.FINANCIAL,
        )
        print(f"Severity: {severity}")
        print(f"Method: {decision.determination_method}")
        ```
    """

    def __init__(
        self,
        config: CalculatorConfig | None = None,
        ai_model: AIModelProtocol | None = None,
    ):
        """Initialize the severity calculator.

        Args:
            config: Calculator configuration.
            ai_model: Optional AI model adapter for AI-assisted assessment.
        """
        self.config = config or CalculatorConfig()
        self.ai_model = ai_model

    def calculate_severity(
        self,
        finding: Finding,
        role_category: RoleCategory | None = None,
        subcategory: SubCategory | None = None,
        context: dict[str, Any] | None = None,
    ) -> tuple[Severity, SeverityDecision]:
        """Calculate severity for a finding.

        Args:
            finding: Finding to assess.
            role_category: Optional role for adjustment.
            subcategory: Optional subcategory for default severity.
            context: Optional additional context.

        Returns:
            Tuple of (Severity, SeverityDecision).
        """
        decision = SeverityDecision(finding_id=finding.finding_id)
        context = context or {}

        # Get text for matching
        text = self._get_finding_text(finding).lower()

        # Step 1: Try rule-based matching
        severity = None
        if self.config.use_rule_matching:
            severity, matched = self._match_rules(text)
            if severity:
                decision.determination_method = "rule"
                decision.matched_rules = matched

        # Step 2: Try subcategory-based default
        if severity is None and self.config.use_subcategory_defaults and subcategory:
            severity = self._get_subcategory_severity(subcategory)
            if severity:
                decision.determination_method = "subcategory"
                decision.context_notes.append(f"Used subcategory default: {subcategory.value}")

        # Step 3: Use default
        if severity is None:
            severity = self.config.default_severity
            decision.determination_method = "default"
            decision.context_notes.append("No rules matched, used default severity")

        decision.initial_severity = severity

        # Step 4: Apply role adjustment
        if self.config.enable_role_adjustment and role_category and finding.category:
            adjustment = self._get_role_adjustment(finding.category, role_category)
            if adjustment != 0:
                severity = self._adjust_severity(severity, adjustment)
                decision.role_adjustment = adjustment
                decision.context_notes.append(
                    f"Role adjustment: {adjustment:+d} for {role_category.value}"
                )

        # Step 5: Apply recency adjustment
        if self.config.enable_recency_adjustment and finding.finding_date:
            recency_adj = self._get_recency_adjustment(finding.finding_date)
            if recency_adj != 0:
                severity = self._adjust_severity(severity, recency_adj)
                decision.recency_adjustment = recency_adj
                decision.context_notes.append(f"Recency adjustment: {recency_adj:+d}")

        decision.final_severity = severity

        logger.debug(
            "Severity calculated",
            finding_id=str(finding.finding_id),
            severity=severity.value,
            method=decision.determination_method,
            adjustments=decision.role_adjustment + decision.recency_adjustment,
        )

        return severity, decision

    def calculate_severities(
        self,
        findings: list[Finding],
        role_category: RoleCategory | None = None,
        subcategories: dict[UUID, SubCategory] | None = None,
        update_findings: bool = True,
    ) -> list[tuple[Severity, SeverityDecision]]:
        """Calculate severity for multiple findings.

        Args:
            findings: List of findings.
            role_category: Optional role for adjustment.
            subcategories: Optional mapping of finding_id to subcategory.
            update_findings: Whether to update finding.severity.

        Returns:
            List of (Severity, SeverityDecision) tuples.
        """
        subcategories = subcategories or {}
        results = []

        for finding in findings:
            subcategory = subcategories.get(finding.finding_id)
            severity, decision = self.calculate_severity(
                finding=finding,
                role_category=role_category,
                subcategory=subcategory,
            )
            if update_findings:
                finding.severity = severity
            results.append((severity, decision))

        logger.info(
            "Severities calculated",
            total=len(findings),
            critical=sum(1 for s, _ in results if s == Severity.CRITICAL),
            high=sum(1 for s, _ in results if s == Severity.HIGH),
        )

        return results

    def _get_finding_text(self, finding: Finding) -> str:
        """Get text from finding for rule matching."""
        parts = [
            finding.summary or "",
            finding.details or "",
            finding.finding_type or "",
        ]
        return " ".join(parts)

    def _match_rules(self, text: str) -> tuple[Severity | None, list[str]]:
        """Match text against severity rules.

        Returns highest severity match and all matched rules.
        """
        matched: list[str] = []
        highest_severity: Severity | None = None

        for pattern, severity in SEVERITY_RULES.items():
            if pattern in text:
                matched.append(pattern)
                if highest_severity is None or self._severity_value(
                    severity
                ) > self._severity_value(highest_severity):
                    highest_severity = severity

        return highest_severity, matched

    def _get_subcategory_severity(self, subcategory: SubCategory) -> Severity | None:
        """Get default severity for a subcategory."""
        return SUBCATEGORY_SEVERITY.get(subcategory)

    def _get_role_adjustment(
        self, category: FindingCategory, role: RoleCategory
    ) -> int:
        """Get role-based severity adjustment."""
        return ROLE_SEVERITY_ADJUSTMENTS.get((category, role), 0)

    def _get_recency_adjustment(self, finding_date: date) -> int:
        """Get recency-based adjustment.

        Recent findings (within threshold) get boosted severity.
        """
        days_ago = (date.today() - finding_date).days
        if days_ago <= self.config.recent_boost_days:
            return self.config.recency_boost_amount
        return 0

    def _adjust_severity(self, severity: Severity, adjustment: int) -> Severity:
        """Adjust severity by level steps.

        Positive adjustment increases severity, negative decreases.
        Capped at CRITICAL max and LOW min.
        """
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        current_idx = order.index(severity)
        new_idx = max(0, min(len(order) - 1, current_idx + adjustment))
        return order[new_idx]

    def _severity_value(self, severity: Severity) -> int:
        """Get numeric value for severity comparison."""
        values = {
            Severity.LOW: 0,
            Severity.MEDIUM: 1,
            Severity.HIGH: 2,
            Severity.CRITICAL: 3,
        }
        return values[severity]


def create_severity_calculator(
    config: CalculatorConfig | None = None,
    ai_model: AIModelProtocol | None = None,
) -> SeverityCalculator:
    """Create a severity calculator.

    Args:
        config: Optional calculator configuration.
        ai_model: Optional AI model for AI-assisted assessment.

    Returns:
        Configured SeverityCalculator.
    """
    return SeverityCalculator(config=config, ai_model=ai_model)
