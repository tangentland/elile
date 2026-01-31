"""Compliance engine for evaluating background check permissions.

This module provides the ComplianceEngine class that evaluates whether
specific background checks are permitted based on locale, role, and tier.
"""

from datetime import timedelta

from elile.agent.state import ServiceTier
from elile.compliance.rules import RuleRepository
from elile.compliance.types import (
    CheckRestriction,
    CheckResult,
    CheckType,
    ENHANCED_TIER_CHECKS,
    EXPLICIT_CONSENT_CHECKS,
    HIRING_RESTRICTED_CHECKS,
    Locale,
    RestrictionType,
    RoleCategory,
)
from elile.core.logging import get_logger

logger = get_logger(__name__)


class ComplianceEngine:
    """Engine for evaluating compliance rules on background checks.

    The compliance engine determines whether a specific background check
    is permitted based on:
    - Geographic locale (jurisdiction-specific regulations)
    - Role category (job-specific requirements)
    - Service tier (Standard vs Enhanced)
    - Built-in restrictions (enhanced-only, consent requirements)

    Usage:
        engine = ComplianceEngine()
        result = engine.evaluate_check(
            locale=Locale.US,
            check_type=CheckType.CRIMINAL_NATIONAL,
            role_category=RoleCategory.FINANCIAL,
        )
        if result.permitted:
            # Proceed with check
            ...
    """

    def __init__(self, rule_repository: RuleRepository | None = None):
        """Initialize the compliance engine.

        Args:
            rule_repository: Repository of compliance rules. If None,
                uses the default rules.
        """
        self._repository = rule_repository or RuleRepository.with_default_rules()

    def evaluate_check(
        self,
        locale: Locale,
        check_type: CheckType,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> CheckResult:
        """Evaluate whether a background check is permitted.

        Args:
            locale: The geographic jurisdiction
            check_type: The type of background check
            role_category: The job role category
            tier: The service tier (Standard or Enhanced)

        Returns:
            CheckResult with permission status and restrictions
        """
        restrictions: list[CheckRestriction] = []
        block_reason: str | None = None

        # Get the effective restriction from rules
        restriction = self._repository.get_effective_rule(
            locale=locale,
            check_type=check_type,
            role_category=role_category,
            tier=tier,
        )
        restrictions.append(restriction)

        # Check if blocked
        if not restriction.permitted:
            block_reason = restriction.notes or self._get_block_reason(restriction)

        # Check hiring restrictions
        if check_type in HIRING_RESTRICTED_CHECKS and restriction.permitted:
            hiring_restriction = CheckRestriction(
                check_type=check_type,
                permitted=True,
                restriction_type=RestrictionType.CONDITIONAL,
                notes="Not for hiring decisions; security/monitoring use only",
            )
            restrictions.append(hiring_restriction)

        # Build combined requirements
        result = CheckResult(
            check_type=check_type,
            locale=locale,
            permitted=restriction.permitted,
            restrictions=restrictions,
            requires_consent=self._requires_consent(restriction, check_type),
            requires_disclosure=restriction.requires_disclosure,
            requires_enhanced_tier=restriction.requires_enhanced_tier,
            lookback_days=restriction.lookback_days,
            block_reason=block_reason,
        )

        logger.debug(
            "compliance_check_evaluated",
            locale=locale.value,
            check_type=check_type.value,
            role_category=role_category.value,
            tier=tier.value,
            permitted=result.permitted,
        )

        return result

    def get_permitted_checks(
        self,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> list[CheckType]:
        """Get all permitted checks for a locale/role/tier combination.

        Args:
            locale: The geographic jurisdiction
            role_category: The job role category
            tier: The service tier

        Returns:
            List of permitted check types
        """
        permitted: list[CheckType] = []

        for check_type in CheckType:
            result = self.evaluate_check(
                locale=locale,
                check_type=check_type,
                role_category=role_category,
                tier=tier,
            )
            if result.permitted:
                permitted.append(check_type)

        return permitted

    def get_blocked_checks(
        self,
        locale: Locale,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> list[tuple[CheckType, str]]:
        """Get all blocked checks with reasons.

        Args:
            locale: The geographic jurisdiction
            role_category: The job role category
            tier: The service tier

        Returns:
            List of (CheckType, reason) tuples for blocked checks
        """
        blocked: list[tuple[CheckType, str]] = []

        for check_type in CheckType:
            result = self.evaluate_check(
                locale=locale,
                check_type=check_type,
                role_category=role_category,
                tier=tier,
            )
            if not result.permitted:
                reason = result.block_reason or "Not permitted"
                blocked.append((check_type, reason))

        return blocked

    def get_lookback_period(
        self,
        locale: Locale,
        check_type: CheckType,
    ) -> timedelta | None:
        """Get the lookback period for a specific check.

        Args:
            locale: The geographic jurisdiction
            check_type: The type of background check

        Returns:
            Lookback period as timedelta, or None if unlimited
        """
        restriction = self._repository.get_effective_rule(
            locale=locale,
            check_type=check_type,
        )
        return restriction.lookback_period

    def requires_consent(
        self,
        locale: Locale,
        check_type: CheckType,
    ) -> bool:
        """Check if explicit consent is required for a check.

        Args:
            locale: The geographic jurisdiction
            check_type: The type of background check

        Returns:
            True if explicit consent is required
        """
        restriction = self._repository.get_effective_rule(
            locale=locale,
            check_type=check_type,
        )
        return self._requires_consent(restriction, check_type)

    def requires_disclosure(
        self,
        locale: Locale,
        check_type: CheckType,
    ) -> bool:
        """Check if pre-check disclosure is required.

        Args:
            locale: The geographic jurisdiction
            check_type: The type of background check

        Returns:
            True if pre-check disclosure is required
        """
        restriction = self._repository.get_effective_rule(
            locale=locale,
            check_type=check_type,
        )
        return restriction.requires_disclosure

    def validate_checks(
        self,
        locale: Locale,
        check_types: list[CheckType],
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> tuple[list[CheckType], list[tuple[CheckType, str]]]:
        """Validate a list of requested checks.

        Args:
            locale: The geographic jurisdiction
            check_types: List of requested check types
            role_category: The job role category
            tier: The service tier

        Returns:
            Tuple of (permitted_checks, blocked_checks_with_reasons)
        """
        permitted: list[CheckType] = []
        blocked: list[tuple[CheckType, str]] = []

        for check_type in check_types:
            result = self.evaluate_check(
                locale=locale,
                check_type=check_type,
                role_category=role_category,
                tier=tier,
            )
            if result.permitted:
                permitted.append(check_type)
            else:
                reason = result.block_reason or "Not permitted"
                blocked.append((check_type, reason))

        return permitted, blocked

    def _requires_consent(
        self,
        restriction: CheckRestriction,
        check_type: CheckType,
    ) -> bool:
        """Determine if consent is required.

        Combines rule-based consent with built-in consent requirements.
        """
        if restriction.requires_consent:
            return True
        if check_type in EXPLICIT_CONSENT_CHECKS:
            return True
        return False

    def _get_block_reason(self, restriction: CheckRestriction) -> str:
        """Get a human-readable block reason from restriction type."""
        if restriction.restriction_type == RestrictionType.BLOCKED:
            return "Check type not permitted in this jurisdiction"
        if restriction.restriction_type == RestrictionType.ROLE_RESTRICTED:
            roles = ", ".join(r.value for r in restriction.role_categories)
            return f"Only permitted for roles: {roles}"
        if restriction.restriction_type == RestrictionType.TIER_RESTRICTED:
            return "Requires Enhanced service tier"
        return "Check not permitted"


def get_compliance_engine() -> ComplianceEngine:
    """Get a compliance engine instance with default rules.

    Returns:
        ComplianceEngine configured with default rules
    """
    return ComplianceEngine()
