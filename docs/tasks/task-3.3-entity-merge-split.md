# Task 3.3: Entity Merge and Split Operations

**Priority**: P1
**Phase**: 3 - Subject & Screening Engine
**Estimated Effort**: 3 days
**Dependencies**: Task 3.1 (Subject Entity Resolution)

## Context

Implement entity merge and split operations to handle duplicate subjects discovered after screening creation, or to separate incorrectly merged entities. Critical for maintaining data integrity.

**Architecture Reference**: [02-core-system.md](../docs/architecture/02-core-system.md) - Data Models
**Related**: [03-screening.md](../docs/architecture/03-screening.md) - Subject Management

## Objectives

1. Implement subject merge with conflict resolution
2. Support entity split operations
3. Maintain referential integrity across screenings
4. Create audit trail for merge/split operations
5. Support rollback of merge operations

## Technical Approach

### Merge/Split Models

```python
# src/elile/subjects/merge_split/models.py
from enum import Enum
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel

class MergeConflictResolution(str, Enum):
    """How to resolve field conflicts."""
    KEEP_PRIMARY = "keep_primary"
    KEEP_SECONDARY = "keep_secondary"
    MERGE_ALL = "merge_all"
    MANUAL = "manual"

class MergeOperation(BaseModel):
    """Entity merge operation."""
    operation_id: str
    primary_subject_id: str
    secondary_subject_id: str
    performed_by: str
    performed_at: datetime

    field_resolutions: Dict[str, MergeConflictResolution]
    merged_screenings: List[str]
    merged_findings: List[str]

    reversible: bool = True
    reversed: bool = False
    reversed_at: Optional[datetime] = None

class SplitOperation(BaseModel):
    """Entity split operation."""
    operation_id: str
    source_subject_id: str
    new_subject_id: str
    performed_by: str
    performed_at: datetime

    split_screenings: List[str]
    split_criteria: Dict[str, any]
```

### Merge Service

```python
# src/elile/subjects/merge_split/merge_service.py
from typing import List, Dict
from elile.subjects.merge_split.models import MergeOperation, MergeConflictResolution
from elile.storage.unit_of_work import transaction
from elile.logging.audit import audit_logger

class SubjectMergeService:
    """Handle subject merging operations."""

    def merge_subjects(
        self,
        primary_id: str,
        secondary_id: str,
        user_id: str,
        conflict_resolutions: Dict[str, MergeConflictResolution]
    ) -> MergeOperation:
        """Merge two subjects."""
        with transaction() as uow:
            primary = uow.subjects.get_by_id(primary_id)
            secondary = uow.subjects.get_by_id(secondary_id)

            # Merge fields
            merged_data = self._merge_fields(
                primary, secondary, conflict_resolutions
            )

            # Update primary subject
            for field, value in merged_data.items():
                setattr(primary, field, value)
            uow.subjects.update(primary)

            # Reassign screenings
            screenings = uow.screenings.find_by_subject(secondary_id)
            for screening in screenings:
                screening.subject_id = primary_id
                uow.screenings.update(screening)

            # Mark secondary as merged
            secondary.merged_into = primary_id
            secondary.active = False
            uow.subjects.update(secondary)

            # Create merge operation record
            operation = MergeOperation(
                operation_id=generate_id(),
                primary_subject_id=primary_id,
                secondary_subject_id=secondary_id,
                performed_by=user_id,
                performed_at=datetime.utcnow(),
                field_resolutions=conflict_resolutions,
                merged_screenings=[s.id for s in screenings]
            )

            # Audit log
            audit_logger.log_event(
                event_type="subject_merged",
                actor_id=user_id,
                resource_type="subject",
                resource_id=primary_id,
                action="merge",
                result="success",
                details={"secondary_id": secondary_id}
            )

            return operation
```

## Implementation Checklist

- [ ] Implement merge service
- [ ] Implement split service
- [ ] Add conflict resolution
- [ ] Create rollback mechanism
- [ ] Add audit logging
- [ ] Test referential integrity

## Success Criteria

- [ ] Merge preserves all data
- [ ] Split correctly assigns screenings
- [ ] Audit trail complete
- [ ] Rollback works correctly
