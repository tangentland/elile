# Codebase Index

Quick reference for navigating the Elile codebase. Updated alongside code changes.

## Module Map

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `src/elile/core/` | Core framework: context, audit, exceptions | `RequestContext`, `AuditLogger`, `ComplianceError` |
| `src/elile/agent/` | LangGraph workflow orchestration | `IterativeSearchState`, `ServiceTier`, `SearchDegree` |
| `src/elile/config/` | Configuration and settings | `Settings`, `get_settings()` |
| `src/elile/db/` | Database models and configuration | `Entity`, `AuditEvent`, `Tenant` |
| `src/elile/models/` | AI model adapters | `AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter` |
| `src/elile/search/` | Search query building and execution | `SearchEngine`, `QueryBuilder` |
| `src/elile/risk/` | Risk analysis and scoring | `RiskAnalyzer`, `RiskScorer` |
| `src/elile/utils/` | Shared utilities and base exceptions | `ElileError` |

## Key Enums

### Service Configuration (`src/elile/agent/state.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `ServiceTier` | `STANDARD`, `ENHANCED` | Service level (depth of investigation) |
| `SearchDegree` | `D1`, `D2`, `D3` | Relationship breadth (subject only → extended network) |
| `VigilanceLevel` | `V0`, `V1`, `V2`, `V3` | Monitoring frequency (pre-screen → bi-monthly) |
| `InformationType` | identity, employment, criminal, etc. | Types of information searched |
| `SearchPhase` | FOUNDATION, RECORDS, INTELLIGENCE, NETWORK, RECONCILIATION | Search workflow phases |
| `InconsistencyType` | DATE_MINOR, EMPLOYMENT_GAP_HIDDEN, etc. | Risk levels of data inconsistencies |

### Audit System (`src/elile/db/models/audit.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `AuditEventType` | SCREENING_INITIATED, DATA_ACCESSED, etc. | Types of audit events |
| `AuditSeverity` | DEBUG, INFO, WARNING, ERROR, CRITICAL | Event severity levels |

### Context Framework (`src/elile/core/context.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `ActorType` | HUMAN, SERVICE, SYSTEM | Who is performing the operation |
| `CacheScope` | SHARED, TENANT_ISOLATED | Cache isolation level |

### Entity System (`src/elile/db/models/entity.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `EntityType` | INDIVIDUAL, ORGANIZATION, ADDRESS | Type of entity being tracked |

## Database Models (`src/elile/db/models/`)

| Model | Table | Purpose |
|-------|-------|---------|
| `Entity` | entities | Core entity (person, org, address) |
| `EntityProfile` | entity_profiles | Point-in-time snapshot of an entity |
| `EntityRelation` | entity_relations | Relationships between entities |
| `CachedDataSource` | cached_data_sources | Cached provider responses |
| `AuditEvent` | audit_events | Immutable audit log entries |
| `Tenant` | tenants | Customer organizations (multi-tenancy) |

## Common Patterns

### UUIDv7 for Identifiers
All primary keys use Python 3.14's native `uuid.uuid7()` for time-ordered IDs:
```python
from uuid import uuid7
entity_id: Mapped[UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid7)
```

### Settings Singleton
```python
from elile.config.settings import get_settings
settings = get_settings()  # Cached singleton
```

### Pydantic Models for Validation
```python
from pydantic import BaseModel, Field
class SubjectInfo(BaseModel):
    full_name: str
    locale: str = "US"
```

### TypedDict for LangGraph State
```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
class IterativeSearchState(TypedDict):
    messages: Annotated[list, add_messages]
```

### Request Context Pattern
```python
from elile.core import RequestContext, request_context, get_current_context, create_context

ctx = create_context(tenant_id=tenant_id, actor_id=user_id, locale="US")
with request_context(ctx):
    current = get_current_context()
    current.assert_check_permitted("criminal_records")
```

### Audit Decorator
```python
from elile.core import audit_operation_v2
from elile.db.models.audit import AuditEventType

@audit_operation_v2(AuditEventType.DATA_ACCESSED)
async def fetch_records(db: AsyncSession) -> list[Record]:
    # tenant_id and correlation_id extracted from RequestContext automatically
    ...
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (db_session, test_engine, mock_settings)
├── unit/                    # Unit tests (isolated, fast)
│   ├── test_context.py      # RequestContext tests
│   ├── test_context_exceptions.py
│   ├── test_audit_logger.py
│   ├── test_entity_model.py
│   ├── test_profile_model.py
│   ├── test_cache_model.py
│   └── test_scoring.py
└── integration/             # Integration tests (with database)
    ├── test_context_integration.py
    ├── test_audit_system.py
    └── test_database.py
```

### Running Tests
```bash
# All tests
.venv/bin/python -m pytest -c pytest_local.ini -v

# Specific test file
.venv/bin/python -m pytest -c pytest_local.ini tests/unit/test_context.py -v

# With coverage
.venv/bin/python -m pytest -c pytest_local.ini --cov=elile -v
```

## Key Files Reference

| File | Purpose |
|------|---------|
| `src/elile/core/context.py` | Request context framework (Task 1.3) |
| `src/elile/core/audit.py` | Audit logging service (Task 1.2) |
| `src/elile/core/exceptions.py` | Core exception classes |
| `src/elile/agent/state.py` | State definitions, enums, Pydantic models |
| `src/elile/db/models/base.py` | SQLAlchemy base class, portable types |
| `src/elile/config/settings.py` | Application settings (Pydantic Settings) |

## Architecture References

See `docs/architecture/` for detailed design documents:
- `01-design.md` - Design principles
- `02-core-system.md` - Database, API structure
- `03-screening.md` - Service tiers, screening flow
- `07-compliance.md` - Compliance engine, security
