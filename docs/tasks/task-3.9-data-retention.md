# Task 3.9: Data Retention Policies

**Priority**: P1
**Phase**: 3 - Subject & Screening Engine
**Estimated Effort**: 2 days
**Dependencies**: Task 2.1 (Compliance Rules Engine)

## Context

Implement automated data retention policies compliant with GDPR, FCRA, and jurisdiction-specific requirements. Automatic archival and deletion based on configurable retention periods.

**Architecture Reference**: [07-compliance.md](../docs/architecture/07-compliance.md) - Data Retention
**Related**: [02-core-system.md](../docs/architecture/02-core-system.md) - Storage

## Objectives

1. Define retention policies by locale and data type
2. Implement automated archival workflows
3. Support hard delete vs soft delete
4. Create retention policy enforcement
5. Add compliance reporting for retained data

## Technical Approach

```python
# src/elile/compliance/retention/models.py
from enum import Enum
from datetime import timedelta

class RetentionPolicy(BaseModel):
    """Data retention policy."""
    locale: str
    data_type: str
    retention_period_days: int
    archive_after_days: int
    deletion_method: str  # soft_delete, hard_delete, anonymize

    # GDPR right to erasure support
    subject_request_override: bool = True
```

## Implementation Checklist

- [ ] Define retention policies by locale
- [ ] Implement archival service
- [ ] Add deletion workflows
- [ ] Create compliance reports
- [ ] Test retention enforcement

## Success Criteria

- [ ] Policies comply with all jurisdictions
- [ ] Automated archival works correctly
- [ ] Subject data deletion on request
