# Task 2.4: Consent Management

## Overview
Implement consent tracking and verification for background checks, including FCRA disclosure compliance.

**Priority**: P0
**Status**: Complete
**Completed**: 2026-01-31
**Dependencies**: Task 2.1

## Deliverables

### Enums Created

1. **ConsentScope** - 13 consent scope types
   - BACKGROUND_CHECK (covers basic checks)
   - CRIMINAL_RECORDS, CREDIT_CHECK, EMPLOYMENT_VERIFICATION
   - EDUCATION_VERIFICATION, REFERENCE_CHECK, LICENSE_VERIFICATION
   - SANCTIONS_CHECK, DRUG_TESTING
   - SOCIAL_MEDIA, DIGITAL_FOOTPRINT
   - LOCATION_DATA, BEHAVIORAL_DATA
   - CONTINUOUS_MONITORING

2. **ConsentVerificationMethod** - 6 verification methods
   - E_SIGNATURE, WET_SIGNATURE, HRIS_API
   - SSO_ACKNOWLEDGMENT, RECORDED_VERBAL, MANUAL_ATTESTATION

### Models Created

1. **FCRADisclosure** - FCRA disclosure tracking
   - Standalone disclosure flag
   - Summary of rights provided
   - State-specific disclosures (CA_ICRAA, NY_FAIR_CHANCE)
   - Investigative consumer report disclosure

2. **Consent** - Consent record
   - Subject ID, granted date, expiration
   - Scopes covered
   - Verification method and reference
   - FCRA disclosure (for US)
   - Revocation tracking

3. **ConsentResult** - Verification result
   - Valid/invalid status
   - Missing scopes
   - Error messages

### ConsentManager Class
- `register_consent()`: Register a consent record
- `get_consents()`: Get all consents for subject
- `get_valid_consents()`: Get non-expired/revoked consents
- `verify_consent()`: Verify consent for required scopes
- `verify_check_types()`: Verify consent for check types
- `verify_fcra_disclosure()`: Verify FCRA disclosure compliance
- `revoke_consent()`: Revoke a consent record

### Helper Functions
- `create_consent()`: Factory for consent records
- `create_fcra_disclosure()`: Factory for FCRA disclosures

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/compliance/consent.py` | Consent models and manager |
| `tests/unit/test_consent.py` | 33 unit tests |

## Key Features

1. **Scope inheritance**
   - BACKGROUND_CHECK covers basic criminal, employment, education
   - Specific scopes for sensitive checks (credit, drug, location)

2. **Expiration and revocation**
   - Configurable expiration period
   - Revocation with reason tracking
   - is_valid checks both conditions

3. **FCRA compliance**
   - Standalone disclosure tracking
   - Summary of rights verification
   - State-specific disclosure validation (California, New York)

4. **Check type mapping**
   - Maps CheckType to ConsentScope automatically
   - Supports verification by check type list

## Test Coverage

- 33 unit tests
- Scope and method enum tests
- FCRA disclosure tests
- Consent lifecycle tests (create, expire, revoke)
- Consent manager tests
- FCRA verification tests (US, California, non-US)
