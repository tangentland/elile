# Task 2.9: FCRA Compliance Rules (US)

## Overview

Implement Fair Credit Reporting Act (FCRA) compliance rules for US jurisdiction including 7-year lookback limits, adverse action requirements, and disclosure obligations. Seeds compliance_rules table with US regulations.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 2.5: Compliance Rule Repository

## Implementation Checklist

- [ ] Create FCRA rule seed data
- [ ] Implement 7-year lookback limits
- [ ] Add adverse action disclosure rules
- [ ] Create ban-the-box state rules
- [ ] Build credit report restrictions
- [ ] Write FCRA compliance tests

## Key Implementation

```python
# src/elile/compliance/fcra_rules.py
"""FCRA compliance rules for US jurisdiction."""

FCRA_RULES = [
    # 7-year lookback limit (FCRA § 605)
    {
        "jurisdiction": "US",
        "rule_type": "lookback_limit",
        "check_type": "criminal",
        "rule_logic": {"days": 2555},  # 7 years
        "description": "FCRA 7-year lookback for criminal records"
    },
    {
        "jurisdiction": "US",
        "rule_type": "lookback_limit",
        "check_type": "civil",
        "rule_logic": {"days": 2555},  # 7 years
        "description": "FCRA 7-year lookback for civil judgments"
    },
    {
        "jurisdiction": "US",
        "rule_type": "lookback_limit",
        "check_type": "bankruptcy",
        "rule_logic": {"days": 3650},  # 10 years
        "description": "FCRA 10-year lookback for bankruptcy"
    },

    # Permitted checks
    {
        "jurisdiction": "US",
        "rule_type": "check_permitted",
        "check_type": "criminal",
        "rule_logic": {"permitted": True},
        "description": "Criminal checks permitted with consent"
    },
    {
        "jurisdiction": "US",
        "rule_type": "check_permitted",
        "check_type": "credit",
        "rule_logic": {"permitted": True, "conditions": ["permissible_purpose"]},
        "description": "Credit checks require permissible purpose (FCRA § 604)"
    },
    {
        "jurisdiction": "US",
        "rule_type": "check_permitted",
        "check_type": "employment",
        "rule_logic": {"permitted": True},
        "description": "Employment verification permitted"
    },

    # Adverse action requirements (FCRA § 615)
    {
        "jurisdiction": "US",
        "rule_type": "disclosure_required",
        "check_type": None,  # Applies to all
        "rule_logic": {
            "notice_type": "adverse_action",
            "timing": "before_action",
            "required_content": [
                "pre_adverse_action_notice",
                "copy_of_report",
                "summary_of_rights",
                "dispute_process"
            ]
        },
        "description": "FCRA adverse action disclosure requirements"
    },

    # State-specific: Ban-the-box (California)
    {
        "jurisdiction": "US-CA",
        "rule_type": "check_permitted",
        "check_type": "criminal",
        "rule_logic": {
            "permitted": True,
            "timing_restriction": "after_conditional_offer"
        },
        "description": "California ban-the-box: Criminal check only after conditional offer"
    },

    # Consent requirements
    {
        "jurisdiction": "US",
        "rule_type": "consent_required",
        "check_type": None,
        "rule_logic": {
            "scope": "basic",
            "standalone_disclosure": True,
            "written_consent": True
        },
        "description": "FCRA requires standalone written consent"
    },
]

async def seed_fcra_rules(db: AsyncSession):
    """Seed FCRA compliance rules into database."""
    from ..repositories.compliance import ComplianceRuleRepository
    from ..models.compliance import ComplianceRule

    repo = ComplianceRuleRepository(db)

    for rule_data in FCRA_RULES:
        rule = ComplianceRule(
            jurisdiction=rule_data["jurisdiction"],
            rule_type=rule_data["rule_type"],
            check_type=rule_data.get("check_type"),
            rule_logic=rule_data["rule_logic"],
            description=rule_data["description"],
            active=True,
            priority=100
        )
        await repo.create_rule(rule)

    await db.commit()
```

## Testing Requirements

### Unit Tests
- FCRA rule structure valid
- 7-year lookback applied correctly
- Adverse action disclosure required
- Credit checks require permissible purpose

### Integration Tests
- Seed FCRA rules successfully
- ComplianceEngine evaluates US rules correctly
- Lookback limits enforced in queries

**Coverage Target**: 90%+ (compliance critical)

## Acceptance Criteria

- [ ] FCRA rules defined for US jurisdiction
- [ ] 7-year lookback for criminal/civil records
- [ ] 10-year lookback for bankruptcy
- [ ] Adverse action disclosure required
- [ ] State-specific rules (ban-the-box) supported
- [ ] Consent requirements specified
- [ ] Seed script populates rules

## Deliverables

- `src/elile/compliance/fcra_rules.py`
- `src/elile/cli/seed_compliance_rules.py` (seed script)
- `tests/unit/test_fcra_rules.py`
- `tests/integration/test_fcra_compliance.py`

## References

- Architecture: [07-compliance.md](../architecture/07-compliance.md) - FCRA compliance
- Legal: Fair Credit Reporting Act § 605, § 604, § 615
- Dependencies: Task 2.5 (rule repository)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
