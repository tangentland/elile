# Task 7.1: Screening Request Model & Orchestrator

## Overview

This task implements the core screening service types and orchestrator that coordinates all phases of a background screening investigation.

## Requirements

1. **Screening Request Model**: Define all inputs needed to execute a screening
2. **Screening Result Model**: Track status, risk assessment, costs, and generated reports
3. **Screening Orchestrator**: Coordinate all phases from validation to report generation
4. **Error Handling**: Specific exceptions for validation, compliance, and execution errors

## Files Created/Modified

### Created
- `src/elile/screening/__init__.py` - Module exports
- `src/elile/screening/types.py` - Request, result, and error models
- `src/elile/screening/orchestrator.py` - ScreeningOrchestrator class
- `tests/unit/test_screening_orchestrator.py` - 40 unit tests

## Key Implementation Details

### ScreeningRequest
Pydantic model with:
- `screening_id`: UUIDv7 auto-generated
- `tenant_id`: UUID of requesting tenant
- `subject`: SubjectIdentifiers (name, DOB, SSN, etc.)
- `locale`: Geographic jurisdiction (Locale enum)
- `service_tier`: STANDARD or ENHANCED
- `search_degree`: D1 (subject), D2 (connections), D3 (extended)
- `vigilance_level`: V0-V3 monitoring frequency
- `role_category`: Job role for relevance weighting
- `consent_token`: Proof of subject consent
- `report_types`: Reports to generate
- `priority`: Processing priority

### ScreeningResult
Dataclass tracking:
- Status (PENDING → IN_PROGRESS → ANALYZING → COMPLETE)
- Risk assessment (score, level, recommendation)
- Phase results with timing
- Cost summary
- Generated reports

### ScreeningOrchestrator
Coordinates 6 phases:
1. **Validation**: Validate request and subject identifiers
2. **Compliance**: Check locale-specific rules via ComplianceEngine
3. **Consent**: Verify consent token via ConsentManager
4. **Investigation**: Execute SAR loop via SARLoopOrchestrator
5. **Risk Analysis**: Calculate risk via RiskAggregator
6. **Report Generation**: Generate requested reports

### Key Patterns Used
- Factory function `create_screening_orchestrator()` for easy instantiation
- Context propagation via `RequestContext`
- Phase timing with `ScreeningPhaseResult`
- Cost tracking per phase
- Error categorization with specific exception types

## Test Results

```
======================== 40 passed, 2 warnings in 0.74s ========================
```

## Integration Points

- `ComplianceEngine`: Check locale and tier restrictions
- `ConsentManager`: Verify consent validity
- `SARLoopOrchestrator`: Execute investigation SAR loop
- `RiskAggregator`: Calculate comprehensive risk assessment
- `RequestContext`: Context propagation for audit logging

## Dependencies

- Phase 2 (Compliance): ComplianceEngine, ConsentManager
- Phase 3 (Entity): SubjectIdentifiers
- Phase 5 (Investigation): SARLoopOrchestrator
- Phase 6 (Risk): RiskAggregator

## Next Steps

Task 7.2 will add the Data Acquisition Coordinator for managing data provider queries.
