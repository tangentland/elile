# Task 11.3: Security Console API

**Priority**: P1
**Phase**: 11 - User Interfaces
**Estimated Effort**: 3 days
**Dependencies**: Task 11.1 (HR Portal API)

## Context

Create API backend for Security Console interface focused on threat assessment, investigation monitoring, and security-specific reporting.

**Architecture Reference**: [11-interfaces.md](../docs/architecture/11-interfaces.md) - Security Console

## Objectives

1. Threat intelligence API
2. Investigation tracking
3. Security alerts
4. Risk assessment views
5. Network visualization data

## Technical Approach

```python
# src/elile/api/routes/security_console.py
@router.get("/security/threats")
async def get_threats(
    org_id: str,
    severity: Optional[str] = None
) -> List[ThreatIntel]:
    # Aggregate security threats
    # Filter by severity
    # Return enriched data
    pass
```

## Implementation Checklist

- [ ] Create security APIs
- [ ] Add threat intelligence
- [ ] Test authorization

## Success Criteria

- [ ] Complete security data
- [ ] Fast queries
