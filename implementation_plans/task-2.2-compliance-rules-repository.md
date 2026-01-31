# Task 2.2: Compliance Rules Repository

## Overview
Define compliance rule models and storage infrastructure for loading and querying locale-specific rules.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 2.1

## Deliverables

### ComplianceRule Model
A rule defining restrictions for a specific locale/check combination:
- `locale`: Geographic jurisdiction
- `check_type`: Type of background check
- `role_category`: Optional role-specific rule
- `permitted`: Whether check is allowed
- `restriction_type`: Type of restriction
- `lookback_days`: Maximum lookback period
- `requires_consent`: Explicit consent needed
- `requires_disclosure`: Pre-check disclosure needed
- `permitted_roles`: Roles for which check is permitted

### RuleRepository Class
Repository for efficient rule lookup:
- Indexed by locale, check_type, and (locale, check_type) pairs
- `get_rules_for_locale()`: All rules for a locale
- `get_rules_for_check()`: All rules for a check type
- `get_rule()`: Most specific matching rule (with inheritance)
- `get_effective_rule()`: Rule with built-in tier/consent restrictions
- `with_default_rules()`: Factory with pre-loaded rules

### Default Rules
Pre-configured rules for major jurisdictions:
- **US FCRA**: 7-year lookback, pre-check disclosure, role-restricted credit
- **EU GDPR**: Credit blocked, criminal role-restricted, Article 9 compliance
- **UK DBS**: Role-based criminal checks
- **Canada PIPEDA**: RCMP for criminal, consent required
- **Australia Privacy Act**: National Police Check via AFP
- **Brazil LGPD**: Credit blocked, strict criminal rules

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/compliance/rules.py` | ComplianceRule model, RuleRepository |
| `src/elile/compliance/default_rules.py` | Default rules for major locales |
| `tests/unit/test_compliance_rules.py` | 35 unit tests |

## Test Coverage

- 35 unit tests
- Rule model tests
- Repository CRUD tests
- Locale inheritance tests
- Default rules verification

## Design Decisions

1. **Inheritance-based lookup**: Sub-locales inherit rules from parent
2. **Specificity ordering**: Role-specific rules override general rules
3. **Built-in restrictions**: Tier and consent requirements applied automatically
4. **Extensible defaults**: Custom rules can override defaults
