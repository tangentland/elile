# Task 7.7: Screening API Endpoints

## Overview

Implement FastAPI endpoints for screening operations including initiate, status, results, and cancellation with proper validation and error handling.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 7.1: Screening Orchestrator
- Task 1.5: FastAPI Setup

## Implementation

```python
# src/elile/api/v1/screening.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/v1/screenings", tags=["screening"])

@router.post("/", response_model=ScreeningResponse)
async def initiate_screening(
    request: ScreeningRequest,
    ctx: RequestContext = Depends(get_context)
):
    """Initiate new screening."""
    orchestrator = get_orchestrator()
    result = await orchestrator.execute_screening(request, ctx)
    return ScreeningResponse.from_result(result)

@router.get("/{screening_id}", response_model=ScreeningResponse)
async def get_screening(
    screening_id: UUID,
    ctx: RequestContext = Depends(get_context)
):
    """Get screening status/results."""
    screening = await get_screening_by_id(screening_id, ctx)
    return ScreeningResponse.from_db(screening)

@router.delete("/{screening_id}")
async def cancel_screening(
    screening_id: UUID,
    ctx: RequestContext = Depends(get_context)
):
    """Cancel screening."""
    await cancel_screening_by_id(screening_id, ctx)
    return {"status": "cancelled"}
```

## Acceptance Criteria

- [ ] POST /v1/screenings - initiate
- [ ] GET /v1/screenings/{id} - get status
- [ ] DELETE /v1/screenings/{id} - cancel
- [ ] Request validation with Pydantic
- [ ] Proper error handling

## Deliverables

- `src/elile/api/v1/screening.py`
- `tests/integration/test_screening_api.py`

## References

- Architecture: [09-integration.md](../../docs/architecture/09-integration.md) - API Endpoints

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
