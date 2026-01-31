# Task 2.1: Locale and Check Type Definitions

## Overview
Define core enums and models for the compliance framework, establishing the foundation for locale-aware background check validation.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31

## Deliverables

### Core Enums Created

1. **Locale** (`src/elile/compliance/types.py`)
   - 25 geographic jurisdictions with specific compliance requirements
   - Organized by region: US, EU, UK, Canada, APAC, LATAM, Middle East/Africa
   - Sub-locales for state/province-specific rules (US_CA, CA_QC, etc.)

2. **CheckType** (`src/elile/compliance/types.py`)
   - 35 background check types covering all major categories
   - Identity, Criminal, Civil, Financial, Employment, Education, Sanctions, Media, Digital, Location

3. **RoleCategory** (`src/elile/compliance/types.py`)
   - 9 job role categories affecting compliance requirements
   - STANDARD, FINANCIAL, GOVERNMENT, HEALTHCARE, EDUCATION, TRANSPORTATION, EXECUTIVE, SECURITY, CONTRACTOR

4. **RestrictionType** (`src/elile/compliance/types.py`)
   - Types of restrictions on checks
   - BLOCKED, LOOKBACK_LIMITED, CONSENT_REQUIRED, DISCLOSURE_REQUIRED, ROLE_RESTRICTED, TIER_RESTRICTED, CONDITIONAL

### Models Created

1. **CheckRestriction** - Outcome of compliance rule evaluation
2. **CheckResult** - Complete result of evaluate_check method
3. **LocaleConfig** - Configuration for a specific locale

### Constants Defined

- `ENHANCED_TIER_CHECKS` - Check types requiring Enhanced tier
- `EXPLICIT_CONSENT_CHECKS` - Check types requiring explicit consent
- `HIRING_RESTRICTED_CHECKS` - Check types not for hiring decisions

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/compliance/__init__.py` | Package initialization |
| `src/elile/compliance/types.py` | Core type definitions |
| `tests/unit/test_compliance_types.py` | 32 unit tests |

## Test Coverage

- 32 unit tests
- All enums tested for value correctness
- All models tested for basic functionality
- Constants tested for expected contents

## Design Decisions

1. **String-based enums**: All enums inherit from `str` for JSON serialization
2. **Pydantic models**: Used for validation and serialization
3. **Sub-locale inheritance**: State/province locales can inherit from parent
4. **Lookback as days**: Stored as integer days for flexibility
