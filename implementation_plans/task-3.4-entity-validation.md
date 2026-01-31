# Task 3.4: Entity Validation & Verification

## Overview
Implement validation rules for entity identifiers and cross-field validation to ensure data quality and compliance.

**Priority**: P1
**Status**: Planned
**Dependencies**: Task 3.1

## Requirements

### Identifier Validation

Format validation for each identifier type:
- SSN: 9 digits, valid area/group numbers
- EIN: 9 digits, valid prefix
- Passport: Country-specific formats
- Phone: E.164 format validation
- Email: RFC 5322 compliance
- Address: Postal code lookup

### Cross-Field Validation

Logical consistency checks:
- DOB not in future
- DOB reasonable (not > 120 years ago)
- Employment dates logical (start < end)
- Age appropriate for claimed positions

### Compliance Validation

- GDPR erasure eligibility
- FCRA lookback limits
- Locale-specific restrictions

## Deliverables

### EntityValidator Class

- `validate_identifier(id_type, value)`: Format validation
- `validate_entity(entity)`: Full entity validation
- `validate_cross_fields(entity)`: Logical consistency
- `check_compliance(entity, locale)`: Compliance rules

### ValidationResult Model

- `valid`: Overall validity
- `errors`: List of ValidationError
- `warnings`: List of ValidationWarning

### Identifier Validators

Per-type validation functions:
- `validate_ssn(value)`: US SSN
- `validate_ein(value)`: US EIN
- `validate_passport(value, country)`: Passport
- `validate_phone(value)`: E.164 phone
- `validate_email(value)`: Email address
- `validate_address(address)`: Address components

## Files to Create

| File | Purpose |
|------|---------|
| `src/elile/entity/validation.py` | EntityValidator class |
| `src/elile/entity/validators/` | Per-type validators |
| `tests/unit/test_entity_validation.py` | Unit tests |

## Validation Rules

### SSN Validation
```python
def validate_ssn(value: str) -> ValidationResult:
    # Remove formatting
    digits = re.sub(r'\D', '', value)

    if len(digits) != 9:
        return ValidationResult(valid=False, errors=["SSN must be 9 digits"])

    # Area number validation (first 3 digits)
    area = int(digits[:3])
    if area == 0 or area == 666 or area >= 900:
        return ValidationResult(valid=False, errors=["Invalid SSN area number"])

    # Group number validation (middle 2 digits)
    group = int(digits[3:5])
    if group == 0:
        return ValidationResult(valid=False, errors=["Invalid SSN group number"])

    # Serial number validation (last 4 digits)
    serial = int(digits[5:])
    if serial == 0:
        return ValidationResult(valid=False, errors=["Invalid SSN serial number"])

    return ValidationResult(valid=True)
```

### Cross-Field Validation
```python
def validate_cross_fields(entity: Entity) -> ValidationResult:
    errors = []

    # DOB validation
    if entity.dob:
        if entity.dob > date.today():
            errors.append("Date of birth cannot be in future")
        if entity.dob < date.today() - timedelta(days=365*120):
            errors.append("Date of birth indicates age > 120 years")

    # Employment date validation
    for emp in entity.employment_history:
        if emp.start_date and emp.end_date:
            if emp.start_date > emp.end_date:
                errors.append(f"Employment start date after end date: {emp.employer}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)
```

## Integration Points

- EntityManager for validation on create/update
- ComplianceEngine for locale-specific rules
- AuditLogger for validation failures

## Test Cases

1. Valid SSN passes validation
2. Invalid SSN area number rejected
3. Future DOB rejected
4. Overlapping employment dates flagged
5. Invalid email format rejected
6. Valid E.164 phone accepted
