# Task 11.4: Investigation Workbench API

**Priority**: P1
**Phase**: 11 - User Interfaces
**Estimated Effort**: 3 days
**Dependencies**: Task 11.1 (HR Portal API)

## Context

Create API backend for Investigation Workbench providing deep-dive investigation tools, evidence management, and analysis capabilities.

**Architecture Reference**: [11-interfaces.md](../docs/architecture/11-interfaces.md) - Investigation Workbench

## Objectives

1. Investigation management API
2. Evidence tracking
3. Network analysis endpoints
4. Annotation and notes
5. Timeline visualization

## Technical Approach

```python
# src/elile/api/routes/investigation.py
@router.get("/investigations/{id}/evidence")
async def get_evidence(id: str) -> EvidenceChain:
    # Retrieve all evidence
    # Maintain chain of custody
    # Support filtering
    pass
```

## Implementation Checklist

- [ ] Create investigation APIs
- [ ] Add evidence management
- [ ] Test workflows

## Success Criteria

- [ ] Complete investigation tools
- [ ] Evidence chain maintained
