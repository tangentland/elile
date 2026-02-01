# Task 2.6: Compliance Engine

## Overview

Build compliance rule evaluator that loads jurisdiction-specific rules and creates ComplianceRuleset with permitted checks, lookback limits, and redaction rules. Enforces compliance before data acquisition.

**Priority**: P0 | **Effort**: 2-3 days | **Status**: Not Started

## Dependencies

- Task 2.5: Compliance Rule Repository
- Task 1.3: Request Context (locale)

## Implementation Checklist

- [ ] Create ComplianceRuleset model with evaluated rules
- [ ] Implement rule evaluation engine
- [ ] Build permitted checks filter
- [ ] Create lookback limit calculator
- [ ] Implement redaction rule aggregator
- [ ] Write compliance engine tests

## Key Implementation

```python
# src/elile/compliance/engine.py
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class ComplianceRuleset:
    """Evaluated compliance rules for a specific context."""
    jurisdiction: str
    role_category: str | None
    permitted_checks: set[str]  # check types allowed
    lookback_limits: dict[str, int]  # check_type -> days
    redaction_rules: list[dict]  # Fields to redact
    disclosure_requirements: list[str]
    consent_scope_required: str  # basic, enhanced, premium

class ComplianceEngine:
    """Evaluates compliance rules for jurisdiction + role."""

    def __init__(self, rule_repo: ComplianceRuleRepository):
        self.rule_repo = rule_repo

    async def evaluate_compliance(
        self,
        jurisdiction: str,
        role_category: str | None = None,
        ctx: RequestContext | None = None
    ) -> ComplianceRuleset:
        """
        Load and evaluate compliance rules for jurisdiction.

        Returns:
            ComplianceRuleset with permitted checks and constraints
        """
        # Load all applicable rules
        rules = await self.rule_repo.get_rules_for_jurisdiction(
            jurisdiction=jurisdiction,
            role_category=role_category
        )

        # Initialize ruleset
        permitted_checks = set()
        lookback_limits = {}
        redaction_rules = []
        disclosure_requirements = []
        consent_scope = "basic"

        # Evaluate each rule
        for rule in rules:
            if rule.rule_type == RuleType.CHECK_PERMITTED:
                # Add permitted check types
                if rule.rule_logic.get("permitted", False):
                    permitted_checks.add(rule.check_type)

            elif rule.rule_type == RuleType.LOOKBACK_LIMIT:
                # Set lookback limits (most restrictive wins)
                check_type = rule.check_type
                days = rule.rule_logic.get("days")
                if check_type and days:
                    existing = lookback_limits.get(check_type, float('inf'))
                    lookback_limits[check_type] = min(existing, days)

            elif rule.rule_type == RuleType.REDACTION_REQUIRED:
                redaction_rules.append(rule.rule_logic)

            elif rule.rule_type == RuleType.DISCLOSURE_REQUIRED:
                disclosure_requirements.append(rule.rule_logic.get("notice_type"))

            elif rule.rule_type == RuleType.CONSENT_REQUIRED:
                required_scope = rule.rule_logic.get("scope", "basic")
                if CONSENT_HIERARCHY[required_scope] > CONSENT_HIERARCHY[consent_scope]:
                    consent_scope = required_scope

        return ComplianceRuleset(
            jurisdiction=jurisdiction,
            role_category=role_category,
            permitted_checks=permitted_checks,
            lookback_limits=lookback_limits,
            redaction_rules=redaction_rules,
            disclosure_requirements=disclosure_requirements,
            consent_scope_required=consent_scope
        )

    def is_check_permitted(
        self,
        ruleset: ComplianceRuleset,
        check_type: str
    ) -> bool:
        """Check if a check type is permitted."""
        return check_type in ruleset.permitted_checks

    def get_lookback_limit(
        self,
        ruleset: ComplianceRuleset,
        check_type: str
    ) -> timedelta | None:
        """Get lookback limit for check type."""
        days = ruleset.lookback_limits.get(check_type)
        return timedelta(days=days) if days else None
```

## Testing Requirements

### Unit Tests
- Ruleset evaluation combines all rules
- Permitted checks filter works
- Lookback limits use most restrictive
- Redaction rules aggregated

### Integration Tests
- Load US rules and verify FCRA compliance
- Load EU rules and verify GDPR compliance
- Test role-specific rule overrides

**Coverage Target**: 90%+ (compliance critical)

## Acceptance Criteria

- [ ] ComplianceEngine evaluates jurisdiction rules
- [ ] ComplianceRuleset includes permitted checks
- [ ] Lookback limits enforced (most restrictive)
- [ ] Redaction rules aggregated
- [ ] Consent scope determined from rules
- [ ] is_check_permitted() validation works
- [ ] Integration with Task 2.7 (consent)

## Deliverables

- `src/elile/compliance/engine.py`
- `tests/unit/test_compliance_engine.py`
- `tests/integration/test_compliance_evaluation.py`

## References

- Architecture: [07-compliance.md](../architecture/07-compliance.md) - Compliance engine
- Dependencies: Task 2.5 (rules), Task 1.3 (context)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
