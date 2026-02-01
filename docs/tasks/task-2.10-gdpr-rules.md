# Task 2.10: GDPR Compliance Rules (EU)

## Overview

Implement GDPR (General Data Protection Regulation) compliance rules for EU jurisdiction including purpose limitation, data minimization, and restricted criminal data processing. Seeds compliance_rules table with EU regulations.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 2.5: Compliance Rule Repository

## Implementation Checklist

- [ ] Create GDPR rule seed data
- [ ] Implement purpose limitation rules
- [ ] Add criminal data restrictions (Art. 10)
- [ ] Create data minimization rules
- [ ] Build right to erasure requirements
- [ ] Write GDPR compliance tests

## Key Implementation

```python
# src/elile/compliance/gdpr_rules.py
"""GDPR compliance rules for EU jurisdiction."""

GDPR_RULES = [
    # Criminal data restrictions (GDPR Art. 10)
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "criminal",
        "role_category": None,  # Default: prohibited
        "rule_logic": {
            "permitted": False,
            "reason": "GDPR Art. 10: Criminal data requires official authority or explicit consent"
        },
        "description": "Criminal data processing prohibited for general roles"
    },
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "criminal",
        "role_category": "regulated_finance",  # Banks, financial institutions
        "rule_logic": {
            "permitted": True,
            "legal_basis": "GDPR Art. 10 exception for regulated sectors"
        },
        "description": "Criminal checks permitted for regulated financial roles"
    },
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "criminal",
        "role_category": "government_security",
        "rule_logic": {
            "permitted": True,
            "legal_basis": "GDPR Art. 10 exception for public security"
        },
        "description": "Criminal checks permitted for government/security roles"
    },

    # Credit data restrictions
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "credit",
        "rule_logic": {
            "permitted": False,
            "reason": "Credit checks generally not permitted in EU employment screening"
        },
        "description": "Credit checks prohibited for employment (data minimization)"
    },

    # Permitted checks (data minimization principle)
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "sanctions",
        "rule_logic": {"permitted": True},
        "description": "Sanctions screening permitted (legitimate interest)"
    },
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "employment",
        "rule_logic": {"permitted": True},
        "description": "Employment verification permitted"
    },
    {
        "jurisdiction": "EU",
        "rule_type": "check_permitted",
        "check_type": "education",
        "rule_logic": {"permitted": True},
        "description": "Education verification permitted"
    },

    # Right to erasure (GDPR Art. 17)
    {
        "jurisdiction": "EU",
        "rule_type": "retention_limit",
        "check_type": None,
        "rule_logic": {
            "max_retention_days": 1825,  # 5 years
            "erasure_on_request": True,
            "anonymization_allowed": True
        },
        "description": "GDPR right to erasure and retention limits"
    },

    # Consent requirements (GDPR Art. 6)
    {
        "jurisdiction": "EU",
        "rule_type": "consent_required",
        "check_type": None,
        "rule_logic": {
            "scope": "enhanced",  # Explicit consent required
            "freely_given": True,
            "specific": True,
            "informed": True,
            "withdrawable": True
        },
        "description": "GDPR Art. 6: Explicit, informed, withdrawable consent required"
    },

    # Disclosure requirements (GDPR Art. 13)
    {
        "jurisdiction": "EU",
        "rule_type": "disclosure_required",
        "check_type": None,
        "rule_logic": {
            "notice_type": "data_processing_notice",
            "required_content": [
                "controller_identity",
                "processing_purposes",
                "legal_basis",
                "data_categories",
                "retention_period",
                "subject_rights",
                "right_to_withdraw",
                "complaint_authority"
            ]
        },
        "description": "GDPR Art. 13: Transparency obligations"
    },

    # Redaction for non-essential data
    {
        "jurisdiction": "EU",
        "rule_type": "redaction_required",
        "check_type": None,
        "rule_logic": {
            "fields": ["religion", "health_data", "genetic_data", "biometric_data"],
            "reason": "GDPR Art. 9: Special category data minimization"
        },
        "description": "Redact special category data unless explicitly consented"
    },
]

async def seed_gdpr_rules(db: AsyncSession):
    """Seed GDPR compliance rules into database."""
    from ..repositories.compliance import ComplianceRuleRepository
    from ..models.compliance import ComplianceRule

    repo = ComplianceRuleRepository(db)

    for rule_data in GDPR_RULES:
        rule = ComplianceRule(
            jurisdiction=rule_data["jurisdiction"],
            rule_type=rule_data["rule_type"],
            check_type=rule_data.get("check_type"),
            role_category=rule_data.get("role_category"),
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
- GDPR rule structure valid
- Criminal data prohibited for general roles
- Criminal data permitted for regulated roles
- Credit checks prohibited
- Right to erasure configured

### Integration Tests
- Seed GDPR rules successfully
- ComplianceEngine evaluates EU rules correctly
- Role-based criminal check filtering works

**Coverage Target**: 90%+ (compliance critical)

## Acceptance Criteria

- [ ] GDPR rules defined for EU jurisdiction
- [ ] Criminal checks restricted by role category
- [ ] Credit checks prohibited for employment
- [ ] Right to erasure configured (5-year retention)
- [ ] Explicit consent requirements specified
- [ ] Data minimization enforced
- [ ] Seed script populates rules

## Deliverables

- `src/elile/compliance/gdpr_rules.py`
- `src/elile/cli/seed_compliance_rules.py` (update with GDPR)
- `tests/unit/test_gdpr_rules.py`
- `tests/integration/test_gdpr_compliance.py`

## References

- Architecture: [07-compliance.md](../architecture/07-compliance.md) - GDPR compliance
- Legal: GDPR Art. 6 (lawfulness), Art. 9 (special categories), Art. 10 (criminal data), Art. 17 (erasure)
- Dependencies: Task 2.5 (rule repository)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
