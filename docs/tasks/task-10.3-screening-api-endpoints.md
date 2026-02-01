# Task 10.3: Complete Screening API

## Overview

Implement complete screening API endpoints including initiate, status, results, reports, and monitoring endpoints with full validation and documentation.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 10.1: API Gateway
- Task 10.2: Authentication Middleware
- Task 7.7: Basic Screening Endpoints

## Implementation

```python
# src/elile/api/v1/screening_complete.py
@router.get("/{screening_id}/report")
async def download_report(
    screening_id: UUID,
    persona: ReportPersona,
    format: OutputFormat = OutputFormat.PDF,
    ctx: RequestContext = Depends(authenticate_request)
):
    """Download screening report."""
    report = await report_service.generate_report(
        screening_id, persona, format, ctx
    )
    return StreamingResponse(
        io.BytesIO(report.content),
        media_type="application/pdf"
    )

@router.post("/{screening_id}/monitor")
async def start_monitoring(
    screening_id: UUID,
    vigilance_level: VigilanceLevel,
    ctx: RequestContext = Depends(authenticate_request)
):
    """Start ongoing monitoring."""
    config = await monitoring_service.start_monitoring(
        screening_id, vigilance_level, ctx
    )
    return config
```

## Acceptance Criteria

- [ ] GET /screenings/{id}/report - download report
- [ ] POST /screenings/{id}/monitor - start monitoring
- [ ] PUT /screenings/{id}/monitor - update vigilance
- [ ] DELETE /screenings/{id}/monitor - stop monitoring
- [ ] Complete OpenAPI specs

## Deliverables

- `src/elile/api/v1/screening_complete.py`
- `tests/integration/test_complete_screening_api.py`

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
