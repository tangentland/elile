# Codebase Index

Quick reference for navigating the Elile codebase. Updated alongside code changes.

## Module Map

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `src/elile/api/` | FastAPI application and middleware | `create_app()`, `APIError`, middleware stack |
| `src/elile/core/` | Core framework: context, audit, encryption, errors, logging | `RequestContext`, `AuditLogger`, `Encryptor`, `ErrorHandler`, `get_logger()` |
| `src/elile/compliance/` | Locale-aware compliance engine | `ComplianceEngine`, `Locale`, `CheckType`, `Consent`, `ServiceConfigValidator` |
| `src/elile/entity/` | Entity resolution and matching | `EntityMatcher`, `SubjectIdentifiers`, `MatchResult` |
| `src/elile/agent/` | LangGraph workflow orchestration | `IterativeSearchState`, `ServiceTier`, `SearchDegree` |
| `src/elile/config/` | Configuration and settings | `Settings`, `get_settings()`, `validate_configuration()` |
| `src/elile/db/` | Database models, repositories, and configuration | `Entity`, `AuditEvent`, `Tenant`, `BaseRepository` |
| `src/elile/db/repositories/` | Repository pattern for data access | `EntityRepository`, `ProfileRepository`, `CacheRepository` |
| `src/elile/db/types/` | Custom SQLAlchemy types | `EncryptedString`, `EncryptedJSON` |
| `src/elile/models/` | AI model adapters | `AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter` |
| `src/elile/search/` | Search query building and execution | `SearchEngine`, `QueryBuilder` |
| `src/elile/risk/` | Risk analysis and scoring | `RiskAnalyzer`, `RiskScorer` |
| `src/elile/utils/` | Shared utilities and base exceptions | `ElileError` |

## API Layer (`src/elile/api/`)

### Application Factory
```python
from elile.api.app import create_app
app = create_app()  # Configures all middleware and routers
```

### Middleware Stack (outer to inner)
1. `RequestLoggingMiddleware` - Audit all requests
2. `ErrorHandlingMiddleware` - Exception → HTTP response
3. `CORSMiddleware` - Cross-origin requests
4. `AuthenticationMiddleware` - Bearer token validation
5. `TenantValidationMiddleware` - X-Tenant-ID validation
6. `RequestContextMiddleware` - Set ContextVars

### Health Endpoints
| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `GET /health` | Basic liveness | No |
| `GET /health/db` | Database connectivity | No |
| `GET /health/ready` | Full readiness | No |

## Core Framework (`src/elile/core/`)

### Request Context
```python
from elile.core import RequestContext, request_context, get_current_context, create_context

ctx = create_context(tenant_id=tenant_id, actor_id=user_id, locale="US")
with request_context(ctx):
    current = get_current_context()
    current.assert_check_permitted("criminal_records")
```

### Audit Logging
```python
from elile.core import AuditLogger, audit_operation_v2
from elile.db.models.audit import AuditEventType

@audit_operation_v2(AuditEventType.DATA_ACCESSED)
async def fetch_records(db: AsyncSession) -> list[Record]:
    # tenant_id and correlation_id extracted from RequestContext automatically
    ...
```

### Encryption
```python
from elile.core.encryption import Encryptor

encryptor = Encryptor()
encrypted = encryptor.encrypt("sensitive data")
decrypted = encryptor.decrypt(encrypted)
```

### Error Handling
```python
from elile.core.error_handling import handle_errors, ErrorHandler

@handle_errors(default_return=None)
async def risky_operation():
    ...
```

## Database Layer (`src/elile/db/`)

### Repositories
```python
from elile.db.repositories import EntityRepository, ProfileRepository, CacheRepository

async with db_session() as session:
    repo = EntityRepository(session)
    entities = await repo.get_by_type(EntityType.INDIVIDUAL)
    entity = await repo.get(entity_id)
```

### Models
| Model | Table | Purpose |
|-------|-------|---------|
| `Entity` | entities | Core entity (person, org, address) |
| `EntityProfile` | entity_profiles | Point-in-time snapshot of an entity |
| `EntityRelation` | entity_relations | Relationships between entities |
| `CachedDataSource` | cached_data_sources | Cached provider responses |
| `AuditEvent` | audit_events | Immutable audit log entries |
| `Tenant` | tenants | Customer organizations (multi-tenancy) |

### Encrypted Types
```python
from elile.db.types import EncryptedString, EncryptedJSON

class MyModel(Base):
    secret: Mapped[str] = mapped_column(EncryptedString())
    secret_data: Mapped[dict] = mapped_column(EncryptedJSON())
```

## Compliance Framework (`src/elile/compliance/`)

### Compliance Engine
```python
from elile.compliance import ComplianceEngine, Locale, CheckType, RoleCategory

engine = ComplianceEngine()
result = engine.evaluate_check(
    locale=Locale.US,
    check_type=CheckType.CRIMINAL_NATIONAL,
    role_category=RoleCategory.FINANCIAL,
)
if result.permitted:
    # Proceed with check
    ...
```

### Consent Management
```python
from elile.compliance import Consent, ConsentManager, ConsentScope, create_consent

consent = create_consent(
    subject_id=subject_id,
    scopes=[ConsentScope.BACKGROUND_CHECK, ConsentScope.CREDIT_CHECK],
)
manager = ConsentManager()
manager.register_consent(consent)
result = manager.verify_consent(subject_id, [ConsentScope.CRIMINAL_RECORDS])
```

### Service Configuration Validation
```python
from elile.compliance import validate_service_config, Locale
from elile.agent.state import ServiceConfiguration, ServiceTier, SearchDegree

config = ServiceConfiguration(tier=ServiceTier.ENHANCED, degrees=SearchDegree.D3)
result = validate_service_config(config, Locale.US)
```

## Entity Resolution (`src/elile/entity/`)

### Entity Matcher
```python
from elile.entity import EntityMatcher, SubjectIdentifiers, MatchType, ResolutionDecision
from elile.agent.state import ServiceTier
from elile.db.models.entity import EntityType

# Create matcher with database session
matcher = EntityMatcher(session)

# Define subject identifiers
identifiers = SubjectIdentifiers(
    full_name="John Smith",
    date_of_birth=date(1980, 1, 15),
    ssn="123-45-6789",
    street_address="123 Main St",
    city="Springfield",
    state="IL",
)

# Resolve subject to existing entity or determine new entity needed
result = await matcher.resolve(identifiers, EntityType.INDIVIDUAL, ServiceTier.STANDARD)

if result.decision == ResolutionDecision.MATCH_EXISTING:
    entity_id = result.entity_id
elif result.decision == ResolutionDecision.PENDING_REVIEW:
    # Queue for analyst review (Enhanced tier)
    ...
else:
    # CREATE_NEW - create new entity
    ...
```

### Match Types
| Type | Description | Confidence |
|------|-------------|------------|
| `EXACT` | Canonical identifier match (SSN, EIN, passport) | 1.0 |
| `FUZZY` | Similarity-based match (name, DOB, address) | 0.70-0.99 |
| `NEW` | No match found | 0.0 |

### Resolution Decisions
| Decision | Tier | Confidence Range |
|----------|------|------------------|
| `MATCH_EXISTING` | Both | ≥0.85 |
| `PENDING_REVIEW` | Enhanced only | 0.70-0.84 |
| `CREATE_NEW` | Both | <0.70 or Standard tier 0.70-0.84 |

### Compliance Enums

| Enum | Values | Purpose |
|------|--------|---------|
| `Locale` | US, EU, UK, CA, AU, BR, etc. | Geographic jurisdictions |
| `CheckType` | 35 check types | Types of background checks |
| `RoleCategory` | STANDARD, FINANCIAL, GOVERNMENT, etc. | Job role categories |
| `ConsentScope` | BACKGROUND_CHECK, CREDIT_CHECK, etc. | Consent scope types |

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

### Entity Resolution (`src/elile/entity/types.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `MatchType` | EXACT, FUZZY, NEW | How entity was matched |
| `ResolutionDecision` | MATCH_EXISTING, CREATE_NEW, PENDING_REVIEW | Resolution outcome |
| `IdentifierType` | SSN, EIN, PASSPORT, DRIVERS_LICENSE, EMAIL, PHONE, etc. | Types of identifiers |
| `RelationType` | EMPLOYER, EMPLOYEE, HOUSEHOLD, FAMILY, DIRECTOR, etc. | Entity relationship types |

### Profile System (`src/elile/db/models/profile.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `ProfileTrigger` | SCREENING, MONITORING, MANUAL | What triggered profile creation |

### Cache System (`src/elile/db/models/cache.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `DataOrigin` | PAID_EXTERNAL, CUSTOMER_PROVIDED | Source of cached data |
| `FreshnessStatus` | FRESH, STALE, EXPIRED | Cache data freshness |

## Configuration (`src/elile/config/`)

### Settings
```python
from elile.config.settings import get_settings
settings = get_settings()  # Cached singleton
```

### Configuration Validation
```python
from elile.config.validation import validate_configuration, validate_or_raise

result = validate_configuration(settings)
if not result.is_valid:
    for error in result.errors:
        print(f"{error.field}: {error.message}")
```

## Common Patterns

### UUIDv7 for Identifiers
All primary keys use Python 3.14's native `uuid.uuid7()` for time-ordered IDs:
```python
from uuid import uuid7
entity_id: Mapped[UUID] = mapped_column(PortableUUID(), primary_key=True, default=uuid7)
```

### TypedDict for LangGraph State
```python
from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages
class IterativeSearchState(TypedDict):
    messages: Annotated[list, add_messages]
```

### Pydantic Models for Validation
```python
from pydantic import BaseModel, Field
class SubjectInfo(BaseModel):
    full_name: str
    locale: str = "US"
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (db_session, test_engine, mock_settings)
├── unit/                    # Unit tests (isolated, fast)
│   ├── test_context.py      # RequestContext tests
│   ├── test_audit_logger.py
│   ├── test_encryption.py
│   ├── test_error_handling.py
│   ├── test_config_validation.py
│   ├── test_repositories.py
│   ├── test_api_*.py        # API unit tests
│   └── ...
└── integration/             # Integration tests (with database)
    ├── test_context_integration.py
    ├── test_audit_system.py
    ├── test_api_*.py        # API integration tests
    └── ...
```

### Running Tests
```bash
# All tests
.venv/bin/pytest -v

# Specific test file
.venv/bin/pytest tests/unit/test_repositories.py -v

# With coverage
.venv/bin/pytest --cov=elile -v
```

## Key Files Reference

| File | Purpose | Task |
|------|---------|------|
| `src/elile/api/app.py` | FastAPI application factory | Task 1.5 |
| `src/elile/api/middleware/` | Middleware stack | Task 1.5 |
| `src/elile/core/context.py` | Request context framework | Task 1.3 |
| `src/elile/core/audit.py` | Audit logging service | Task 1.2 |
| `src/elile/core/encryption.py` | AES-256-GCM encryption | Task 1.6 |
| `src/elile/core/error_handling.py` | Error handling framework | Task 1.7 |
| `src/elile/core/exceptions.py` | Core exception classes | Task 1.3 |
| `src/elile/core/tenant.py` | Tenant management service | Task 1.4 |
| `src/elile/config/settings.py` | Application settings | - |
| `src/elile/config/validation.py` | Configuration validation | Task 1.8 |
| `src/elile/db/repositories/` | Repository pattern | Task 1.9 |
| `src/elile/db/types/encrypted.py` | Encrypted SQLAlchemy types | Task 1.6 |
| `src/elile/agent/state.py` | State definitions, enums, Pydantic models | - |
| `src/elile/db/models/base.py` | SQLAlchemy base class, portable types | Task 1.1 |
| `src/elile/compliance/types.py` | Locale, CheckType, RoleCategory enums | Task 2.1 |
| `src/elile/compliance/rules.py` | ComplianceRule, RuleRepository | Task 2.2 |
| `src/elile/compliance/engine.py` | ComplianceEngine | Task 2.3 |
| `src/elile/compliance/consent.py` | Consent, ConsentManager | Task 2.4 |
| `src/elile/compliance/validation.py` | ServiceConfigValidator | Task 2.5 |
| `src/elile/entity/types.py` | MatchResult, SubjectIdentifiers, enums | Task 3.1 |
| `src/elile/entity/matcher.py` | EntityMatcher class | Task 3.1 |

## Architecture References

See `docs/architecture/` for detailed design documents:
- `01-design.md` - Design principles
- `02-core-system.md` - Database, API structure
- `03-screening.md` - Service tiers, screening flow
- `07-compliance.md` - Compliance engine, security
