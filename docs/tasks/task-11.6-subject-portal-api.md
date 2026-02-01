# Task 11.6: Subject Portal API

**Priority**: P1
**Phase**: 11 - User Interfaces
**Estimated Effort**: 2 days
**Dependencies**: Task 11.1 (HR Portal API)

## Context

Create API backend for Subject Portal allowing candidates/employees to view their screening status, provide consent, and exercise data rights.

**Architecture Reference**: [11-interfaces.md](../docs/architecture/11-interfaces.md) - Subject Portal

## Objectives

1. Screening status API
2. Consent management
3. Data access requests
4. Dispute filing
5. Communication history

## Technical Approach

```python
# src/elile/api/routes/subject_portal.py
@router.get("/subject/screening-status")
async def get_screening_status(
    subject_id: str,
    current_user: Subject = Depends(get_current_subject)
) -> ScreeningStatus:
    # Verify authorization
    # Return subject's screening status
    pass
```

## Implementation Checklist

- [ ] Create subject APIs
- [ ] Add consent workflows
- [ ] Test data rights

## Success Criteria

- [ ] GDPR compliant
- [ ] Self-service works
