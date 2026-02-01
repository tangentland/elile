# Task 1.9: Repository Pattern Implementation

**Priority**: P1
**Phase**: 1 - Foundation
**Estimated Effort**: 3 days
**Dependencies**: Task 1.1 (Database Schema), Task 1.2 (Data Models)

## Context

Implement the repository pattern to abstract database access and provide a clean interface for data operations. This pattern decouples business logic from data access implementation, making the codebase more maintainable and testable.

**Architecture Reference**: [02-core-system.md](../docs/architecture/02-core-system.md) - Database Layer
**Related**: [10-platform.md](../docs/architecture/10-platform.md) - Module Structure

## Objectives

1. Create base repository interface with standard CRUD operations
2. Implement concrete repositories for each entity
3. Add query builders for complex filtering
4. Support transactions and unit of work pattern
5. Enable repository testing with in-memory backends

## Technical Approach

### Repository Base Class

```python
# src/elile/storage/repository.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete

T = TypeVar("T")

class Repository(ABC, Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: Session, model_class: type[T]):
        self.session = session
        self.model_class = model_class

    def create(self, entity: T) -> T:
        """Create new entity."""
        self.session.add(entity)
        self.session.flush()
        return entity

    def get_by_id(self, entity_id: str) -> Optional[T]:
        """Retrieve entity by ID."""
        return self.session.get(self.model_class, entity_id)

    def update(self, entity: T) -> T:
        """Update existing entity."""
        self.session.merge(entity)
        self.session.flush()
        return entity

    def delete(self, entity_id: str) -> bool:
        """Delete entity by ID."""
        result = self.session.execute(
            delete(self.model_class).where(self.model_class.id == entity_id)
        )
        return result.rowcount > 0

    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        """List entities with pagination."""
        stmt = select(self.model_class).limit(limit).offset(offset)
        result = self.session.execute(stmt)
        return list(result.scalars().all())
```

### Screening Repository

```python
# src/elile/storage/repositories/screening_repository.py
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from elile.storage.repository import Repository
from elile.storage.models import Screening, ScreeningStatus, ServiceTier

class ScreeningRepository(Repository[Screening]):
    """Repository for screening operations."""

    def __init__(self, session: Session):
        super().__init__(session, Screening)

    def get_with_findings(self, screening_id: str) -> Optional[Screening]:
        """Get screening with all findings eagerly loaded."""
        stmt = (
            select(Screening)
            .where(Screening.id == screening_id)
            .options(joinedload(Screening.findings))
        )
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def find_by_subject(self, subject_id: str) -> List[Screening]:
        """Find all screenings for a subject."""
        stmt = (
            select(Screening)
            .where(Screening.subject_id == subject_id)
            .order_by(Screening.created_at.desc())
        )
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def find_active_by_org(
        self,
        org_id: str,
        tier: Optional[ServiceTier] = None
    ) -> List[Screening]:
        """Find active screenings for organization."""
        stmt = select(Screening).where(
            Screening.org_id == org_id,
            Screening.status.in_([
                ScreeningStatus.PENDING,
                ScreeningStatus.IN_PROGRESS
            ])
        )

        if tier:
            stmt = stmt.where(Screening.tier == tier)

        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def count_by_status(self, org_id: str) -> dict[ScreeningStatus, int]:
        """Get screening counts by status for organization."""
        from sqlalchemy import func

        stmt = (
            select(Screening.status, func.count(Screening.id))
            .where(Screening.org_id == org_id)
            .group_by(Screening.status)
        )

        result = self.session.execute(stmt)
        return {status: count for status, count in result.all()}
```

### Subject Repository

```python
# src/elile/storage/repositories/subject_repository.py
from typing import Optional, List
from sqlalchemy import select, or_
from sqlalchemy.orm import Session
from elile.storage.repository import Repository
from elile.storage.models import Subject

class SubjectRepository(Repository[Subject]):
    """Repository for subject operations."""

    def __init__(self, session: Session):
        super().__init__(session, Subject)

    def find_by_email(self, email: str) -> Optional[Subject]:
        """Find subject by email address."""
        stmt = select(Subject).where(Subject.email == email)
        result = self.session.execute(stmt)
        return result.scalar_one_or_none()

    def search(
        self,
        org_id: str,
        query: str,
        limit: int = 50
    ) -> List[Subject]:
        """Search subjects by name or email."""
        search_term = f"%{query}%"
        stmt = (
            select(Subject)
            .where(
                Subject.org_id == org_id,
                or_(
                    Subject.full_name.ilike(search_term),
                    Subject.email.ilike(search_term)
                )
            )
            .limit(limit)
        )
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def find_duplicates(
        self,
        full_name: str,
        date_of_birth: str,
        org_id: str
    ) -> List[Subject]:
        """Find potential duplicate subjects."""
        stmt = select(Subject).where(
            Subject.org_id == org_id,
            Subject.full_name == full_name,
            Subject.date_of_birth == date_of_birth
        )
        result = self.session.execute(stmt)
        return list(result.scalars().all())
```

### Finding Repository

```python
# src/elile/storage/repositories/finding_repository.py
from typing import List
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from elile.storage.repository import Repository
from elile.storage.models import Finding, RiskLevel

class FindingRepository(Repository[Finding]):
    """Repository for finding operations."""

    def __init__(self, session: Session):
        super().__init__(session, Finding)

    def find_by_screening(
        self,
        screening_id: str,
        min_risk: Optional[RiskLevel] = None
    ) -> List[Finding]:
        """Get findings for screening, optionally filtered by risk."""
        stmt = select(Finding).where(Finding.screening_id == screening_id)

        if min_risk:
            risk_order = [
                RiskLevel.CRITICAL,
                RiskLevel.HIGH,
                RiskLevel.MEDIUM,
                RiskLevel.LOW
            ]
            allowed_risks = risk_order[:risk_order.index(min_risk) + 1]
            stmt = stmt.where(Finding.risk_level.in_(allowed_risks))

        stmt = stmt.order_by(Finding.discovered_at.desc())
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def find_by_category(
        self,
        screening_id: str,
        category: str
    ) -> List[Finding]:
        """Get findings by category."""
        stmt = (
            select(Finding)
            .where(
                Finding.screening_id == screening_id,
                Finding.category == category
            )
            .order_by(Finding.discovered_at.desc())
        )
        result = self.session.execute(stmt)
        return list(result.scalars().all())
```

### Unit of Work Pattern

```python
# src/elile/storage/unit_of_work.py
from typing import Optional
from contextlib import contextmanager
from sqlalchemy.orm import Session
from elile.storage.database import get_session
from elile.storage.repositories.screening_repository import ScreeningRepository
from elile.storage.repositories.subject_repository import SubjectRepository
from elile.storage.repositories.finding_repository import FindingRepository

class UnitOfWork:
    """Unit of work pattern for managing transactions."""

    def __init__(self, session: Optional[Session] = None):
        self._session = session
        self._owned_session = session is None

        # Initialize repositories lazily
        self._screening_repo: Optional[ScreeningRepository] = None
        self._subject_repo: Optional[SubjectRepository] = None
        self._finding_repo: Optional[FindingRepository] = None

    @property
    def session(self) -> Session:
        """Get or create database session."""
        if self._session is None:
            self._session = next(get_session())
        return self._session

    @property
    def screenings(self) -> ScreeningRepository:
        """Get screening repository."""
        if self._screening_repo is None:
            self._screening_repo = ScreeningRepository(self.session)
        return self._screening_repo

    @property
    def subjects(self) -> SubjectRepository:
        """Get subject repository."""
        if self._subject_repo is None:
            self._subject_repo = SubjectRepository(self.session)
        return self._subject_repo

    @property
    def findings(self) -> FindingRepository:
        """Get finding repository."""
        if self._finding_repo is None:
            self._finding_repo = FindingRepository(self.session)
        return self._finding_repo

    def commit(self) -> None:
        """Commit transaction."""
        self.session.commit()

    def rollback(self) -> None:
        """Rollback transaction."""
        self.session.rollback()

    def close(self) -> None:
        """Close session if owned."""
        if self._owned_session and self._session:
            self._session.close()
            self._session = None

@contextmanager
def transaction():
    """Context manager for transactional operations."""
    uow = UnitOfWork()
    try:
        yield uow
        uow.commit()
    except Exception:
        uow.rollback()
        raise
    finally:
        uow.close()
```

## Implementation Checklist

### Base Infrastructure
- [ ] Create repository base class with CRUD operations
- [ ] Implement type-safe generic repository
- [ ] Add query builder support
- [ ] Create unit of work pattern
- [ ] Implement transaction context manager

### Entity Repositories
- [ ] Implement ScreeningRepository
- [ ] Implement SubjectRepository
- [ ] Implement FindingRepository
- [ ] Implement OrganizationRepository
- [ ] Implement AlertRepository

### Advanced Queries
- [ ] Add eager loading support
- [ ] Implement complex filtering
- [ ] Add full-text search capabilities
- [ ] Create aggregation queries
- [ ] Support batch operations

### Testing
- [ ] Create in-memory repository for testing
- [ ] Write repository unit tests
- [ ] Test transaction rollback
- [ ] Test concurrent access
- [ ] Add performance benchmarks

## Testing Strategy

```python
# tests/storage/test_screening_repository.py
import pytest
from elile.storage.unit_of_work import transaction
from elile.storage.models import Screening, ServiceTier, Degree

def test_create_screening():
    """Test screening creation."""
    with transaction() as uow:
        screening = Screening(
            org_id="org_123",
            subject_id="sub_456",
            tier=ServiceTier.STANDARD,
            degree=Degree.D1
        )
        created = uow.screenings.create(screening)

        assert created.id is not None
        assert created.org_id == "org_123"

def test_find_by_subject():
    """Test finding screenings by subject."""
    with transaction() as uow:
        screenings = uow.screenings.find_by_subject("sub_456")
        assert len(screenings) > 0
        assert all(s.subject_id == "sub_456" for s in screenings)

def test_transaction_rollback():
    """Test transaction rollback on error."""
    try:
        with transaction() as uow:
            screening = Screening(org_id="org_123", subject_id="sub_456")
            uow.screenings.create(screening)
            raise ValueError("Test error")
    except ValueError:
        pass

    # Verify screening was not persisted
    with transaction() as uow:
        count = len(uow.screenings.find_by_subject("sub_456"))
        assert count == 0
```

## Success Criteria

- [ ] All repositories implement standard CRUD operations
- [ ] Unit of work pattern manages transactions correctly
- [ ] Complex queries execute efficiently (< 100ms)
- [ ] Transaction rollback works correctly
- [ ] Repository tests achieve >90% coverage
- [ ] In-memory repositories support testing

## Documentation

- Document repository pattern in architecture guide
- Create examples for common query patterns
- Add transaction management best practices
- Document eager loading strategies

## Future Enhancements

- Add query result caching
- Implement repository event hooks
- Support read replicas
- Add query performance monitoring
