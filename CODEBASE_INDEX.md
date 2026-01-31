# Codebase Index

Quick reference for navigating the Elile codebase. Updated alongside code changes.

## Module Map

| Module | Purpose | Key Classes/Functions |
|--------|---------|----------------------|
| `src/elile/api/` | FastAPI application and middleware | `create_app()`, `APIError`, middleware stack |
| `src/elile/core/` | Core framework: context, audit, encryption, errors, logging | `RequestContext`, `AuditLogger`, `Encryptor`, `ErrorHandler`, `get_logger()` |
| `src/elile/compliance/` | Locale-aware compliance engine | `ComplianceEngine`, `Locale`, `CheckType`, `Consent`, `ServiceConfigValidator` |
| `src/elile/entity/` | Entity resolution, matching, tenant isolation | `EntityMatcher`, `EntityManager`, `TenantAwareEntityService` |
| `src/elile/providers/` | Data provider abstraction and registry | `DataProvider`, `ProviderRegistry`, `ProviderResult` |
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

### Entity Deduplication
```python
from elile.entity import EntityDeduplicator, DeduplicationResult, MergeResult

# Check for duplicates before creating entity
dedup = EntityDeduplicator(session, audit_logger)
result = await dedup.check_duplicate(identifiers, EntityType.INDIVIDUAL)

if result.is_duplicate:
    # Use existing entity instead of creating new
    entity_id = result.existing_entity_id
else:
    # Safe to create new entity
    entity = await create_entity(identifiers)

# Merge duplicate entities (keeps older entity as canonical)
merge_result = await dedup.merge_entities(entity_a_id, entity_b_id)
canonical_id = merge_result.canonical_entity_id

# Handle identifier enrichment (triggers merge if match found)
merge_result = await dedup.on_identifier_added(
    entity_id, IdentifierType.SSN, "123-45-6789"
)
```

### Entity Manager (High-Level API)
```python
from elile.entity import EntityManager, SubjectIdentifiers, RelationType

manager = EntityManager(session, audit_logger)

# Create entity with automatic dedup check
identifiers = SubjectIdentifiers(
    full_name="John Smith",
    ssn="123-45-6789",
    email="john@example.com",
)
result = await manager.create_entity(EntityType.INDIVIDUAL, identifiers)
if result.created:
    entity_id = result.entity_id

# Add identifiers with confidence tracking
await manager.add_identifier(
    entity_id, IdentifierType.PASSPORT, "N12345678",
    confidence=0.95, source="travel_records"
)

# Manage relationships
await manager.add_relation(
    from_entity_id=person_id,
    to_entity_id=company_id,
    relation_type=RelationType.EMPLOYEE,
)

# Query relationship graph
neighbors = await manager.get_neighbors(entity_id, depth=2)
path = await manager.find_path(entity_a, entity_b)
```

### Relationship Graph
```python
from elile.entity import RelationshipGraph, RelationType

graph = RelationshipGraph(session)

# Add relationship edge
edge = await graph.add_edge(
    from_entity_id=from_id,
    to_entity_id=to_id,
    relation_type=RelationType.EMPLOYER,
    confidence=0.95,
)

# Get neighbors at various depths
neighbors_1 = await graph.get_neighbors(entity_id, depth=1)
neighbors_2 = await graph.get_neighbors(entity_id, depth=2)

# Find shortest path between entities
path = await graph.get_path(from_id, to_id, max_depth=5)
if path.exists:
    print(f"Path length: {path.length}")
```

### Tenant-Aware Entity Service
```python
from elile.entity import TenantAwareEntityService, EntityAccessControl, TenantScopedQuery
from elile.db.models.cache import DataOrigin

# Create tenant-aware service
service = TenantAwareEntityService(session, tenant_id=tenant_id)

# Create entity with tenant isolation
result = await service.create_entity(
    entity_type=EntityType.INDIVIDUAL,
    identifiers=identifiers,
    data_origin=DataOrigin.CUSTOMER_PROVIDED,  # Tenant-scoped
)

# Shared external data (accessible to all tenants)
result = await service.create_entity(
    entity_type=EntityType.INDIVIDUAL,
    identifiers=identifiers,
    data_origin=DataOrigin.PAID_EXTERNAL,  # Shared
)

# Access control verification
access_control = EntityAccessControl(session)
can_access = await access_control.can_access(entity_id, tenant_id)

# Tenant-scoped queries
query = (
    TenantScopedQuery(session)
    .with_tenant(tenant_id)
    .with_shared()  # Include shared external data
    .filter_by_type(EntityType.INDIVIDUAL)
)
entities = await query.execute(limit=100)
```

### Data Isolation Rules
| Data Origin | Tenant Access | Description |
|-------------|---------------|-------------|
| `CUSTOMER_PROVIDED` | Own tenant only | Strictly tenant-scoped data |
| `PAID_EXTERNAL` | All tenants | Shared cache for external data |

## Data Provider Framework (`src/elile/providers/`)

### Provider Registry
```python
from elile.providers import (
    DataProvider,
    BaseDataProvider,
    ProviderRegistry,
    get_provider_registry,
    ProviderInfo,
    ProviderCapability,
    ProviderResult,
    DataSourceCategory,
    CostTier,
)

# Get global registry
registry = get_provider_registry()

# Register a provider
registry.register(my_provider)

# Get best provider for a check type
provider = registry.get_provider_for_check(
    check_type=CheckType.CRIMINAL_NATIONAL,
    locale=Locale.US,
    service_tier=ServiceTier.STANDARD,
)

# Get all providers for fallback
providers = registry.get_providers_for_check(
    check_type=CheckType.CREDIT_REPORT,
    locale=Locale.US,
    healthy_only=True,
)

# Execute check
result = await provider.execute_check(
    check_type=CheckType.CRIMINAL_NATIONAL,
    subject=identifiers,
    locale=Locale.US,
)
```

### Provider Implementation
```python
class MyProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(ProviderInfo(
            provider_id="my_provider",
            name="My Provider",
            category=DataSourceCategory.CORE,
            capabilities=[
                ProviderCapability(
                    check_type=CheckType.CRIMINAL_NATIONAL,
                    supported_locales=[Locale.US, Locale.CA],
                    cost_tier=CostTier.LOW,
                ),
            ],
        ))

    async def execute_check(self, check_type, subject, locale, **kwargs):
        # Provider-specific implementation
        return ProviderResult(
            provider_id=self.provider_id,
            check_type=check_type,
            locale=locale,
            success=True,
            normalized_data={"records": [...]},
        )

    async def health_check(self):
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.HEALTHY,
            last_check=datetime.utcnow(),
        )
```

### Provider Enums
| Enum | Values | Purpose |
|------|--------|---------|
| `DataSourceCategory` | CORE, PREMIUM | Tier availability (Standard vs Enhanced) |
| `CostTier` | FREE, LOW, MEDIUM, HIGH, PREMIUM | Billing optimization |
| `ProviderStatus` | HEALTHY, DEGRADED, UNHEALTHY, MAINTENANCE | Health status |

### Rate Limiting
```python
from elile.providers import (
    RateLimitConfig,
    ProviderRateLimitRegistry,
    get_rate_limit_registry,
    RateLimitExceededError,
)

# Get global rate limit registry
rate_limits = get_rate_limit_registry()

# Configure provider-specific rate limits
rate_limits.configure_provider("sterling", RateLimitConfig(
    tokens_per_second=10.0,  # Sustained rate
    max_tokens=50.0,  # Burst capacity
))

# Before making a request
try:
    await rate_limits.acquire_or_raise("sterling")
    result = await provider.execute_check(...)
except RateLimitExceededError as e:
    # Handle rate limit (e.g., queue request, use fallback)
    print(f"Retry after {e.retry_after_seconds}s")

# Check if request is allowed without consuming
result = await rate_limits.check("sterling")
if not result.allowed:
    print(f"Wait {result.retry_after_seconds}s")

# Synchronous check for quick decisions
if rate_limits.can_execute("sterling"):
    await rate_limits.acquire("sterling")
    ...
```

### Response Caching
```python
from elile.providers import (
    ProviderCacheService,
    CacheFreshnessConfig,
    CacheEntry,
    CacheLookupResult,
)
from elile.db.models.cache import DataOrigin

# Create cache service with session
cache = ProviderCacheService(session)

# Cache-aside pattern with get_or_fetch
result, was_cached = await cache.get_or_fetch(
    entity_id=entity_id,
    provider_id="sterling",
    check_type=CheckType.CRIMINAL_NATIONAL,
    locale=Locale.US,
    fetch_fn=lambda: provider.execute_check(...),
)
if was_cached:
    print("Cache hit - saved API call")

# Manual cache lookup
lookup = await cache.get(entity_id, provider_id, check_type)
if lookup.is_fresh_hit:
    return lookup.entry.normalized_data
elif lookup.is_stale_hit:
    print(f"Using stale data, age: {lookup.entry.age.days} days")

# Store provider result
entry = await cache.store(
    entity_id=entity_id,
    result=provider_result,
    data_origin=DataOrigin.PAID_EXTERNAL,  # Shared across tenants
)

# Tenant-isolated storage
entry = await cache.store(
    entity_id=entity_id,
    result=provider_result,
    tenant_id=tenant_id,
    data_origin=DataOrigin.CUSTOMER_PROVIDED,  # Only this tenant
)

# Get cache statistics
stats = cache.stats
print(f"Hit rate: {stats.hit_rate:.1%}")
```

### Cost Tracking
```python
from elile.providers import (
    ProviderCostService,
    get_cost_service,
    BudgetConfig,
    BudgetStatus,
    BudgetExceededError,
    CostRecord,
    CostSummary,
)

# Get global cost service
cost_service = get_cost_service()

# Record query cost
record = await cost_service.record_cost(
    query_id=query_id,
    provider_id="sterling",
    check_type="criminal_national",
    cost=Decimal("5.00"),
    tenant_id=tenant_id,
    screening_id=screening_id,
)

# Record cache savings (when cache hit avoids API call)
await cost_service.record_cache_savings(
    query_id=query_id,
    provider_id="sterling",
    saved_amount=Decimal("5.00"),
    tenant_id=tenant_id,
)

# Configure tenant budget
await cost_service.set_budget(BudgetConfig(
    tenant_id=tenant_id,
    monthly_limit=Decimal("10000.00"),
    daily_limit=Decimal("500.00"),
    warning_threshold=0.8,  # Warn at 80%
    hard_limit=True,  # Block when exceeded
))

# Check budget before expensive query
status = await cost_service.check_budget(tenant_id, estimated_cost=Decimal("10.00"))
if status.would_exceed(Decimal("10.00")):
    if status.hard_limit:
        raise BudgetExceededError(tenant_id, status)

# Or use check_budget_or_raise for automatic exception
await cost_service.check_budget_or_raise(tenant_id, Decimal("10.00"))

# Get cost analytics
summary = await cost_service.get_tenant_costs(
    tenant_id=tenant_id,
    start_date=month_start,
    end_date=month_end,
)
print(f"Total: ${summary.total_cost}")
print(f"Cache savings: ${summary.cache_savings}")
print(f"By provider: {summary.by_provider}")
print(f"Cache hit rate: {summary.cache_hit_rate:.1%}")
```

### Request Routing
```python
from elile.providers import (
    RequestRouter,
    RoutedRequest,
    RoutedResult,
    RoutingConfig,
    FailureReason,
    RouteFailure,
)

# Create router with all services
router = RequestRouter(
    registry=get_provider_registry(),
    cache=ProviderCacheService(session),
    rate_limiter=get_rate_limit_registry(),
    circuit_registry=CircuitBreakerRegistry(),
    cost_service=get_cost_service(),
)

# Route single request
result = await router.route_request(
    check_type=CheckType.CRIMINAL_NATIONAL,
    subject=identifiers,
    locale=Locale.US,
    entity_id=entity_id,
    tenant_id=tenant_id,
    service_tier=ServiceTier.STANDARD,
)

if result.success:
    print(f"Provider: {result.provider_id}")
    print(f"Cache hit: {result.cache_hit}")
    print(f"Attempts: {result.attempts}")
    print(f"Cost: ${result.cost_incurred}")
else:
    print(f"Failed: {result.failure.reason}")
    for provider_id, error in result.failure.provider_errors:
        print(f"  {provider_id}: {error}")

# Route batch of requests in parallel
requests = [
    RoutedRequest.create(
        check_type=CheckType.CRIMINAL_NATIONAL,
        subject=identifiers,
        locale=Locale.US,
        entity_id=entity_id,
        tenant_id=tenant_id,
    ),
    RoutedRequest.create(
        check_type=CheckType.CREDIT_REPORT,
        subject=identifiers,
        locale=Locale.US,
        entity_id=entity_id,
        tenant_id=tenant_id,
    ),
]

results = await router.route_batch(requests, parallel=True)
```

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
| `src/elile/entity/deduplication.py` | EntityDeduplicator, MergeResult | Task 3.2 |
| `src/elile/entity/manager.py` | EntityManager high-level API | Task 3.3 |
| `src/elile/entity/identifiers.py` | IdentifierManager class | Task 3.3 |
| `src/elile/entity/graph.py` | RelationshipGraph class | Task 3.3 |
| `src/elile/entity/validation.py` | EntityValidator, identifier validation | Task 3.4 |
| `src/elile/entity/tenant.py` | TenantAwareEntityService, EntityAccessControl | Task 3.5 |
| `src/elile/providers/types.py` | Provider types, enums, result models | Task 4.1 |
| `src/elile/providers/protocol.py` | DataProvider Protocol, BaseDataProvider | Task 4.1 |
| `src/elile/providers/registry.py` | ProviderRegistry, provider lookup | Task 4.1 |
| `src/elile/providers/health.py` | CircuitBreaker, HealthMonitor, ProviderMetrics | Task 4.2 |
| `src/elile/providers/rate_limit.py` | TokenBucket, ProviderRateLimitRegistry, RateLimitConfig | Task 4.3 |
| `src/elile/providers/cache.py` | ProviderCacheService, CacheEntry, CacheFreshnessConfig | Task 4.4 |
| `src/elile/providers/cost.py` | ProviderCostService, BudgetConfig, CostRecord, CostSummary | Task 4.5 |
| `src/elile/providers/router.py` | RequestRouter, RoutedRequest, RoutedResult, RoutingConfig | Task 4.6 |

## Architecture References

See `docs/architecture/` for detailed design documents:
- `01-design.md` - Design principles
- `02-core-system.md` - Database, API structure
- `03-screening.md` - Service tiers, screening flow
- `07-compliance.md` - Compliance engine, security
