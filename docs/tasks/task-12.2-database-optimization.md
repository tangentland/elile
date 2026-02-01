# Task 12.2: Database Indexing & Query Optimization

## Overview

Implement database performance optimizations including strategic indexing, query optimization, connection pooling tuning, and query performance monitoring.

**Priority**: P0 | **Effort**: 2 days | **Status**: Not Started

## Dependencies

- Task 1.1: Database Schema

## Implementation

```sql
-- Critical indexes
CREATE INDEX idx_screenings_tenant_status ON screenings(tenant_id, status);
CREATE INDEX idx_screenings_created_at ON screenings(created_at DESC);
CREATE INDEX idx_entities_canonical_ssn ON entities USING hash ((canonical_identifiers->>'ssn'));
CREATE INDEX idx_findings_category_severity ON findings(category, severity);
CREATE INDEX idx_monitoring_next_check ON monitoring_configs(next_check_date) WHERE is_active = true;
CREATE INDEX idx_audit_events_timestamp ON audit_events(timestamp DESC);
CREATE INDEX idx_profiles_entity_version ON profiles(entity_id, version_number DESC);

-- Composite indexes for common queries
CREATE INDEX idx_screenings_lookup ON screenings(tenant_id, status, risk_level);
CREATE INDEX idx_findings_entity_date ON findings(subject_entity_id, finding_date DESC);
```

```python
# src/elile/db/optimization.py
# Connection pooling
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,  # Health checks
    pool_recycle=3600,   # Recycle connections hourly
    echo_pool=True       # Log pool stats
)

# Query optimization
async def get_screenings_optimized(ctx: RequestContext):
    """Optimized screening query."""
    return await session.execute(
        select(Screening)
        .options(
            selectinload(Screening.findings),  # Eager load
            joinedload(Screening.risk_score)
        )
        .where(Screening.tenant_id == ctx.tenant_id)
        .order_by(Screening.created_at.desc())
        .limit(50)
    )
```

## Acceptance Criteria

- [ ] All critical indexes created
- [ ] Query plans analyzed and optimized
- [ ] Connection pool tuned (size=20, overflow=10)
- [ ] Slow query logging enabled
- [ ] Database performance metrics

## Deliverables

- `migrations/versions/xxx_add_performance_indexes.py`
- `src/elile/db/optimization.py`
- Query performance report

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
