# Task 2.7: Consent Management System

## Overview

Implement consent record tracking with scope (basic/enhanced/premium), expiration, and revocation support. Integrates with HRIS workflow for consent grants. See [07-compliance.md](../architecture/07-compliance.md) for consent requirements.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema
- Task 1.4: Multi-Tenancy (tenant_id)

## Implementation Checklist

- [ ] Create ConsentRecord model with scope and expiration
- [ ] Implement consent verification service
- [ ] Build consent revocation workflow
- [ ] Add consent audit logging
- [ ] Create consent status queries
- [ ] Write consent management tests

## Key Implementation

```python
# src/elile/models/consent.py
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, TimestampMixin

class ConsentScope(str, Enum):
    BASIC = "basic"          # Standard tier checks
    ENHANCED = "enhanced"    # Enhanced tier checks
    PREMIUM = "premium"      # All check types including sensitive

class ConsentRecord(Base, TimestampMixin):
    """Consent granted by subject for background screening."""
    __tablename__ = "consent_records"

    consent_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    subject_entity_id: Mapped[UUID] = mapped_column(ForeignKey("entities.entity_id"), nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.tenant_id"), nullable=False)

    # Consent details
    consent_scope: Mapped[ConsentScope] = mapped_column(String(20), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    # Audit trail
    consent_text: Mapped[str] = mapped_column(Text, nullable=False)  # Actual consent language
    signature_proof: Mapped[dict] = mapped_column(JSON, nullable=False)  # IP, timestamp, acceptance method

    __table_args__ = (
        Index('idx_consent_entity', 'subject_entity_id'),
        Index('idx_consent_tenant', 'tenant_id'),
        Index('idx_consent_granted', 'granted_at'),
    )

# src/elile/services/consent.py
from datetime import datetime

class ConsentService:
    """Service for managing consent records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def verify_consent(
        self,
        entity_id: UUID,
        required_scope: ConsentScope,
        ctx: RequestContext
    ) -> ConsentRecord | None:
        """
        Verify valid consent exists for entity with required scope.

        Returns:
            ConsentRecord if valid consent exists, None otherwise
        """
        from sqlalchemy import select

        query = select(ConsentRecord).where(
            ConsentRecord.subject_entity_id == entity_id,
            ConsentRecord.tenant_id == ctx.tenant_id,
            ConsentRecord.revoked_at.is_(None)
        ).order_by(ConsentRecord.granted_at.desc())

        result = await self.db.execute(query)
        consents = result.scalars().all()

        now = datetime.utcnow()
        for consent in consents:
            # Check expiration
            if consent.expires_at and consent.expires_at < now:
                continue

            # Check scope hierarchy
            if CONSENT_HIERARCHY[consent.consent_scope] >= CONSENT_HIERARCHY[required_scope]:
                return consent

        return None

    async def grant_consent(
        self,
        entity_id: UUID,
        scope: ConsentScope,
        consent_text: str,
        signature_proof: dict,
        ctx: RequestContext,
        expires_at: datetime | None = None
    ) -> ConsentRecord:
        """Create new consent record."""
        consent = ConsentRecord(
            subject_entity_id=entity_id,
            tenant_id=ctx.tenant_id,
            consent_scope=scope,
            granted_at=datetime.utcnow(),
            expires_at=expires_at,
            consent_text=consent_text,
            signature_proof=signature_proof
        )

        self.db.add(consent)
        await self.db.flush()

        # Audit log
        await audit_logger.log_event(
            AuditEventType.CONSENT_GRANTED,
            ctx,
            {"consent_id": str(consent.consent_id), "scope": scope},
            entity_id=entity_id
        )

        return consent

    async def revoke_consent(
        self,
        consent_id: UUID,
        ctx: RequestContext
    ) -> ConsentRecord:
        """Revoke existing consent."""
        consent = await self.db.get(ConsentRecord, consent_id)
        if not consent or consent.tenant_id != ctx.tenant_id:
            raise PermissionDeniedError("Consent not found")

        consent.revoked_at = datetime.utcnow()
        await self.db.flush()

        # Audit log
        await audit_logger.log_event(
            AuditEventType.CONSENT_REVOKED,
            ctx,
            {"consent_id": str(consent_id)},
            entity_id=consent.subject_entity_id
        )

        return consent

CONSENT_HIERARCHY = {
    ConsentScope.BASIC: 1,
    ConsentScope.ENHANCED: 2,
    ConsentScope.PREMIUM: 3
}
```

## Testing Requirements

### Unit Tests
- Consent model structure
- Consent verification with scope hierarchy
- Expired consent rejected
- Revoked consent rejected

### Integration Tests
- Grant/revoke workflow end-to-end
- Multi-tenant consent isolation
- Consent audit logging

**Coverage Target**: 90%+ (compliance critical)

## Acceptance Criteria

- [ ] ConsentRecord model with scope and expiration
- [ ] verify_consent() checks scope hierarchy
- [ ] Expired consents not returned
- [ ] Revoked consents not returned
- [ ] grant_consent() creates audit event
- [ ] revoke_consent() sets revoked_at timestamp
- [ ] Multi-tenant isolation enforced

## Deliverables

- `src/elile/models/consent.py`
- `src/elile/services/consent.py`
- `migrations/versions/00X_add_consent_records.py`
- `tests/unit/test_consent_service.py`
- `tests/integration/test_consent_workflow.py`

## References

- Architecture: [07-compliance.md](../architecture/07-compliance.md) - Consent management
- Dependencies: Task 1.1 (database), Task 1.4 (multi-tenancy)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
