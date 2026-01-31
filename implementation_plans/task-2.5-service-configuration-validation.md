# Task 2.5: Service Configuration Validation

## Overview
Implement enhanced service configuration validation that integrates tier constraints, locale compatibility, and role restrictions.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 2.1, Task 2.3

## Deliverables

### Models Created

1. **ValidationError** - Single validation error
   - `field`: Field with error
   - `message`: Error description
   - `code`: Machine-readable error code

2. **ValidationResult** - Validation outcome
   - `valid`: Overall validity
   - `errors`: List of errors
   - `warnings`: List of warnings
   - Helper methods: `add_error()`, `add_warning()`

### ServiceConfigValidator Class
- `validate()`: Validate configuration against locale and role
- `validate_check_list()`: Validate list of check types
- `get_available_checks()`: Get permitted CheckTypes
- `get_available_info_types()`: Get permitted InformationTypes

### Validation Rules

1. **Tier Constraints**
   - D3 (Extended Network) requires Enhanced tier
   - Enhanced-only info types blocked with Standard tier

2. **Locale Compatibility**
   - Check types validated against locale rules
   - Blocked checks generate errors

3. **Role Restrictions**
   - Role-restricted checks validated against role category
   - Credit checks for financial roles only (in US)

4. **Core Check Warnings**
   - Warning when excluding identity or sanctions checks
   - Non-blocking but logged

### Convenience Functions
- `validate_service_config()`: Quick validation
- `validate_or_raise()`: Validate and raise ValueError on failure

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/compliance/validation.py` | Validator implementation |
| `tests/unit/test_service_validation.py` | 26 unit tests |

## Usage Example

```python
from elile.agent.state import ServiceConfiguration, SearchDegree, ServiceTier
from elile.compliance import validate_service_config, Locale

config = ServiceConfiguration(
    tier=ServiceTier.STANDARD,
    degrees=SearchDegree.D3,  # Invalid: requires Enhanced
)

result = validate_service_config(config, Locale.US)
if not result.valid:
    for error in result.errors:
        print(f"{error.field}: {error.message}")
```

## Error Codes

| Code | Description |
|------|-------------|
| `d3_requires_enhanced` | D3 requires Enhanced tier |
| `info_type_requires_enhanced` | Info type needs Enhanced tier |
| `check_not_permitted` | Check blocked in locale |
| `excluding_core_check` | Warning for excluding core check |
| `requires_consent` | Warning for consent requirement |

## Test Coverage

- 26 unit tests
- Valid/invalid configuration tests
- Tier constraint tests
- Locale-specific tests (US, EU, Brazil)
- Role category tests
- Check list validation tests
- Available checks/info types tests
