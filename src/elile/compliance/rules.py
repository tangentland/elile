"""Compliance rules repository for locale-aware background checks.

This module provides the ComplianceRule model and RuleRepository for
loading and querying compliance rules based on locale, check type,
and role category.
"""

from collections.abc import Sequence
from typing import Self

from pydantic import BaseModel, Field

from elile.agent.state import ServiceTier
from elile.compliance.types import (
    CheckRestriction,
    CheckType,
    ENHANCED_TIER_CHECKS,
    EXPLICIT_CONSENT_CHECKS,
    Locale,
    RestrictionType,
    RoleCategory,
)


class ComplianceRule(BaseModel):
    """A single compliance rule defining restrictions for a check.

    Rules are evaluated in order of specificity:
    1. Locale + CheckType + RoleCategory (most specific)
    2. Locale + CheckType
    3. Parent Locale + CheckType (if parent exists)
    4. Default rule

    Attributes:
        locale: The geographic jurisdiction this rule applies to
        check_type: The type of background check
        role_category: Optional role category (None = all roles)
        permitted: Whether the check is permitted
        restriction_type: Type of restriction if any
        lookback_days: Maximum lookback period (None = unlimited)
        requires_consent: Whether explicit consent is required
        requires_disclosure: Whether pre-check disclosure is required
        requires_enhanced_tier: Whether Enhanced tier is required
        permitted_roles: Roles for which this check is permitted (empty = all)
        notes: Additional notes about this rule
    """

    locale: Locale
    check_type: CheckType
    role_category: RoleCategory | None = None  # None = applies to all roles

    permitted: bool = True
    restriction_type: RestrictionType | None = None
    lookback_days: int | None = None
    requires_consent: bool = False
    requires_disclosure: bool = False
    requires_enhanced_tier: bool = False

    permitted_roles: list[RoleCategory] = Field(default_factory=list)
    notes: str | None = None

    def to_restriction(self) -> CheckRestriction:
        """Convert rule to a CheckRestriction."""
        return CheckRestriction(
            check_type=self.check_type,
            permitted=self.permitted,
            restriction_type=self.restriction_type,
            lookback_days=self.lookback_days,
            requires_consent=self.requires_consent,
            requires_disclosure=self.requires_disclosure,
            requires_enhanced_tier=self.requires_enhanced_tier,
            role_categories=self.permitted_roles,
            notes=self.notes,
        )


class RuleRepository:
    """Repository for loading and querying compliance rules.

    Provides efficient lookup of rules by locale, check type, and role.
    Rules are indexed for fast access.
    """

    def __init__(self, rules: Sequence[ComplianceRule] | None = None):
        """Initialize repository with optional rules.

        Args:
            rules: Initial rules to load. If None, loads default rules.
        """
        self._rules: list[ComplianceRule] = []
        self._by_locale: dict[Locale, list[ComplianceRule]] = {}
        self._by_check: dict[CheckType, list[ComplianceRule]] = {}
        self._by_locale_check: dict[tuple[Locale, CheckType], list[ComplianceRule]] = {}

        if rules:
            self.load_rules(rules)

    def load_rules(self, rules: Sequence[ComplianceRule]) -> None:
        """Load rules into the repository.

        Args:
            rules: Rules to load
        """
        for rule in rules:
            self._add_rule(rule)

    def _add_rule(self, rule: ComplianceRule) -> None:
        """Add a single rule to indexes."""
        self._rules.append(rule)

        # Index by locale
        if rule.locale not in self._by_locale:
            self._by_locale[rule.locale] = []
        self._by_locale[rule.locale].append(rule)

        # Index by check type
        if rule.check_type not in self._by_check:
            self._by_check[rule.check_type] = []
        self._by_check[rule.check_type].append(rule)

        # Index by locale + check
        key = (rule.locale, rule.check_type)
        if key not in self._by_locale_check:
            self._by_locale_check[key] = []
        self._by_locale_check[key].append(rule)

    def get_rules_for_locale(self, locale: Locale) -> list[ComplianceRule]:
        """Get all rules for a specific locale.

        Args:
            locale: The locale to query

        Returns:
            List of rules for the locale
        """
        return self._by_locale.get(locale, [])

    def get_rules_for_check(self, check_type: CheckType) -> list[ComplianceRule]:
        """Get all rules for a specific check type.

        Args:
            check_type: The check type to query

        Returns:
            List of rules for the check type
        """
        return self._by_check.get(check_type, [])

    def get_rule(
        self,
        locale: Locale,
        check_type: CheckType,
        role_category: RoleCategory | None = None,
    ) -> ComplianceRule | None:
        """Get the most specific rule for locale, check, and role.

        Searches in order of specificity:
        1. Exact match (locale + check + role)
        2. Locale + check (no role)
        3. Parent locale + check + role (for sub-locales)
        4. Parent locale + check

        Args:
            locale: The locale
            check_type: The check type
            role_category: Optional role category

        Returns:
            Most specific matching rule, or None
        """
        key = (locale, check_type)
        rules = self._by_locale_check.get(key, [])

        # First try exact match with role
        if role_category:
            for rule in rules:
                if rule.role_category == role_category:
                    return rule

        # Then try without role
        for rule in rules:
            if rule.role_category is None:
                return rule

        # Try parent locale if this is a sub-locale
        parent = self._get_parent_locale(locale)
        if parent:
            return self.get_rule(parent, check_type, role_category)

        return None

    def get_effective_rule(
        self,
        locale: Locale,
        check_type: CheckType,
        role_category: RoleCategory = RoleCategory.STANDARD,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> CheckRestriction:
        """Get the effective restriction for a check.

        Combines rule lookup with built-in restrictions (enhanced tier,
        explicit consent requirements).

        Args:
            locale: The locale
            check_type: The check type
            role_category: The role category
            tier: The service tier

        Returns:
            Effective restriction for the check
        """
        # Start with rule lookup
        rule = self.get_rule(locale, check_type, role_category)

        if rule:
            restriction = rule.to_restriction()
        else:
            # Default: permitted with no restrictions
            restriction = CheckRestriction(
                check_type=check_type,
                permitted=True,
            )

        # Apply built-in tier restrictions
        if check_type in ENHANCED_TIER_CHECKS:
            restriction.requires_enhanced_tier = True
            if tier == ServiceTier.STANDARD:
                restriction = CheckRestriction(
                    check_type=check_type,
                    permitted=False,
                    restriction_type=RestrictionType.TIER_RESTRICTED,
                    requires_enhanced_tier=True,
                    notes="Requires Enhanced tier",
                )

        # Apply built-in consent requirements
        if check_type in EXPLICIT_CONSENT_CHECKS:
            restriction.requires_consent = True

        # Apply role restrictions if specified
        if restriction.role_categories and role_category not in restriction.role_categories:
            restriction = CheckRestriction(
                check_type=check_type,
                permitted=False,
                restriction_type=RestrictionType.ROLE_RESTRICTED,
                role_categories=restriction.role_categories,
                notes=f"Not permitted for {role_category.value} role",
            )

        return restriction

    def _get_parent_locale(self, locale: Locale) -> Locale | None:
        """Get parent locale for sub-locales.

        Args:
            locale: The locale to check

        Returns:
            Parent locale or None
        """
        # US state sub-locales
        if locale.value.startswith("US_"):
            return Locale.US

        # Canada province sub-locales
        if locale.value.startswith("CA_"):
            return Locale.CA

        # EU country sub-locales could inherit from EU
        if locale in {Locale.DE, Locale.FR, Locale.NL}:
            return Locale.EU

        return None

    @classmethod
    def with_default_rules(cls) -> Self:
        """Create repository with default rules loaded.

        Returns:
            RuleRepository with default rules
        """
        from elile.compliance.default_rules import get_default_rules

        return cls(rules=get_default_rules())

    def count(self) -> int:
        """Get total number of rules.

        Returns:
            Number of rules in repository
        """
        return len(self._rules)

    def all_rules(self) -> list[ComplianceRule]:
        """Get all rules.

        Returns:
            List of all rules
        """
        return list(self._rules)
