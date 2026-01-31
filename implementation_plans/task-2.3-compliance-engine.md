# Task 2.3: Compliance Engine Core

## Overview
Implement the main compliance evaluation engine that determines whether background checks are permitted based on locale, role, and tier.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 2.1, Task 2.2

## Deliverables

### ComplianceEngine Class
Main engine for evaluating compliance rules:
- `evaluate_check()`: Determine if a check is permitted
- `get_permitted_checks()`: List all permitted checks for locale/role/tier
- `get_blocked_checks()`: List blocked checks with reasons
- `get_lookback_period()`: Get lookback period for a check
- `requires_consent()`: Check if explicit consent needed
- `requires_disclosure()`: Check if pre-check disclosure needed
- `validate_checks()`: Validate a list of requested checks

### Key Features

1. **Multi-factor evaluation**
   - Locale-specific rules
   - Role category restrictions
   - Service tier constraints
   - Built-in tier restrictions (Enhanced-only checks)
   - Consent requirements

2. **Comprehensive results**
   - Permission status
   - List of applicable restrictions
   - Block reason when not permitted
   - Combined requirements (consent, disclosure, tier)

3. **Audit logging integration**
   - Logs compliance decisions for traceability

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/compliance/engine.py` | ComplianceEngine implementation |
| `tests/unit/test_compliance_engine.py` | 33 unit tests |

## Usage Example

```python
from elile.compliance import ComplianceEngine, Locale, CheckType, RoleCategory

engine = ComplianceEngine()
result = engine.evaluate_check(
    locale=Locale.US,
    check_type=CheckType.CRIMINAL_NATIONAL,
    role_category=RoleCategory.FINANCIAL,
)

if result.permitted:
    if result.requires_consent:
        # Obtain explicit consent
        pass
    # Proceed with check
else:
    print(f"Blocked: {result.block_reason}")
```

## Test Coverage

- 33 unit tests
- Initialization tests
- Evaluation tests (permitted, blocked, lookback, consent)
- Tier restriction tests
- Locale-specific tests (US, EU, UK, Brazil, Canada)
- Custom repository tests

## Design Decisions

1. **Layered evaluation**: Rules first, then built-in restrictions
2. **Default to permitted**: Unknown checks permitted unless blocked
3. **Combined requirements**: Merges rule and built-in requirements
4. **Logging**: Debug-level logging of all evaluations
