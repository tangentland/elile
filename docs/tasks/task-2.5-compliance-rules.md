# Task 2.5: Compliance Rule Repository

## Overview

Create database-driven compliance rule repository with rule types (check_permitted, lookback_limit, redaction) and support for jurisdiction + role-specific rules. See [07-compliance.md](../architecture/07-compliance.md) for compliance framework.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema

## Implementation Checklist

- [ ] Create ComplianceRule model with JSON rule_logic
- [ ] Add indexes for jurisdiction + check_type queries
- [ ] Implement rule CRUD repository
- [ ] Build rule template system
- [ ] Create rule versioning support
- [ ] Write rule repository tests

## Key Implementation

```python
# src/elile/models/compliance.py
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class RuleType(str, Enum):
    CHECK_PERMITTED = "check_permitted"      # Is check type allowed?
    LOOKBACK_LIMIT = "lookback_limit"        # Max years to search
    REDACTION_REQUIRED = "redaction_required" # Fields to redact
    CONSENT_REQUIRED = "consent_required"    # Consent scope needed
    DISCLOSURE_REQUIRED = "disclosure_required" # Must disclose to subject

class ComplianceRule(Base, TimestampMixin):
    """Jurisdiction and role-specific compliance rules."""
    __tablename__ = "compliance_rules"

    rule_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    jurisdiction: Mapped[str] = mapped_column(String(10), nullable=False)  # US, EU, CA, etc.
    rule_type: Mapped[RuleType] = mapped_column(String(50), nullable=False)

    # Optional filters (null = applies to all)
    check_type: Mapped[str] = mapped_column(String(50), nullable=True)  # criminal, credit, etc.
    role_category: Mapped[str] = mapped_column(String(50), nullable=True)  # government, finance, etc.

    # Rule definition (JSON)
    rule_logic: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Metadata
    active: Mapped[bool] = mapped_column(default=True)
    priority: Mapped[int] = mapped_column(default=100)  # Lower = higher priority
    description: Mapped[str] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index('idx_compliance_jurisdiction', 'jurisdiction'),
        Index('idx_compliance_rule_type', 'rule_type'),
        Index('idx_compliance_check_type', 'check_type'),
        Index('idx_compliance_active', 'active'),
    )

# src/elile/repositories/compliance.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

class ComplianceRuleRepository:
    """Repository for compliance rules."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_rules_for_jurisdiction(
        self,
        jurisdiction: str,
        check_type: str | None = None,
        role_category: str | None = None
    ) -> list[ComplianceRule]:
        """Get all applicable rules for jurisdiction + filters."""
        query = select(ComplianceRule).where(
            ComplianceRule.jurisdiction == jurisdiction,
            ComplianceRule.active == True
        ).order_by(ComplianceRule.priority.asc())

        if check_type:
            query = query.where(
                (ComplianceRule.check_type == check_type) |
                (ComplianceRule.check_type.is_(None))
            )

        if role_category:
            query = query.where(
                (ComplianceRule.role_category == role_category) |
                (ComplianceRule.role_category.is_(None))
            )

        result = await self.db.execute(query)
        return result.scalars().all()

    async def create_rule(self, rule: ComplianceRule) -> ComplianceRule:
        """Create new compliance rule."""
        self.db.add(rule)
        await self.db.flush()
        return rule
```

## Testing Requirements

### Unit Tests
- ComplianceRule model structure
- Repository queries by jurisdiction
- Rule filtering by check_type and role
- Rule priority ordering

### Integration Tests
- CRUD operations on rules
- Query performance with 100+ rules
- Index usage verification

**Coverage Target**: 85%+

## Acceptance Criteria

- [ ] ComplianceRule model with all rule types
- [ ] JSON rule_logic field for flexible rules
- [ ] Indexes on jurisdiction, rule_type, check_type
- [ ] Repository supports filtered queries
- [ ] Rules ordered by priority
- [ ] Active/inactive rule filtering

## Deliverables

- `src/elile/models/compliance.py`
- `src/elile/repositories/compliance.py`
- `migrations/versions/00X_add_compliance_rules.py`
- `tests/unit/test_compliance_repository.py`

## References

- Architecture: [07-compliance.md](../architecture/07-compliance.md) - Compliance engine
- Dependencies: Task 1.1 (database), Task 2.6 (rule evaluator)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
