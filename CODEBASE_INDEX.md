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
| `src/elile/investigation/` | SAR (Search-Assess-Refine) loop orchestration | `SARStateMachine`, `SARConfig`, `QueryPlanner`, `SearchQuery` |
| `src/elile/agent/` | LangGraph workflow orchestration | `IterativeSearchState`, `ServiceTier`, `SearchDegree` |
| `src/elile/config/` | Configuration and settings | `Settings`, `get_settings()`, `validate_configuration()` |
| `src/elile/db/` | Database models, repositories, and configuration | `Entity`, `AuditEvent`, `Tenant`, `BaseRepository` |
| `src/elile/db/repositories/` | Repository pattern for data access | `EntityRepository`, `ProfileRepository`, `CacheRepository` |
| `src/elile/db/types/` | Custom SQLAlchemy types | `EncryptedString`, `EncryptedJSON` |
| `src/elile/models/` | AI model adapters | `AnthropicAdapter`, `OpenAIAdapter`, `GeminiAdapter` |
| `src/elile/search/` | Search query building and execution | `SearchEngine`, `QueryBuilder` |
| `src/elile/risk/` | Risk analysis and scoring | `RiskScorer`, `FindingClassifier`, `SeverityCalculator`, `AnomalyDetector` |
| `src/elile/screening/` | End-to-end screening workflow orchestration | `ScreeningOrchestrator`, `ScreeningRequest`, `ScreeningResult` |
| `src/elile/reporting/` | Persona-specific report generation | `ReportGenerator`, `TemplateRegistry`, `ReportPersona`, `OutputFormat` |
| `src/elile/monitoring/` | Ongoing employee vigilance and monitoring | `MonitoringScheduler`, `VigilanceManager`, `MonitoringConfig`, `MonitoringCheck`, `LifecycleEvent` |
| `src/elile/hris/` | HRIS integration gateway and event processing | `HRISGateway`, `HRISAdapter`, `HRISEvent`, `HRISEventProcessor`, `HRISResultPublisher`, `GatewayConfig` |
| `src/elile/observability/` | OpenTelemetry tracing and Prometheus metrics | `TracingManager`, `MetricsManager`, `TracingConfig`, `MetricsConfig` |
| `src/elile/utils/` | Shared utilities and base exceptions | `ElileError` |

## API Layer (`src/elile/api/`)

### Application Factory
```python
from elile.api.app import create_app
app = create_app()  # Configures all middleware and routers
```

### Middleware Stack (outer to inner)
1. `ObservabilityMiddleware` - Metrics and tracing for requests
2. `RequestLoggingMiddleware` - Audit all requests
3. `ErrorHandlingMiddleware` - Exception → HTTP response
4. `CORSMiddleware` - Cross-origin requests
5. `AuthenticationMiddleware` - Bearer token validation
6. `TenantValidationMiddleware` - X-Tenant-ID validation
7. `RequestContextMiddleware` - Set ContextVars

### Health & Observability Endpoints
| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `GET /health` | Basic liveness | No |
| `GET /health/db` | Database connectivity | No |
| `GET /health/ready` | Full readiness | No |
| `GET /metrics` | Prometheus metrics | No |

### Screening API (`/v1/screenings/`)
| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `POST /v1/screenings/` | Initiate a new screening | Yes |
| `GET /v1/screenings/{id}` | Get screening status and results | Yes |
| `DELETE /v1/screenings/{id}` | Cancel a screening | Yes |
| `GET /v1/screenings/` | List screenings (paginated) | Yes |

**Key schemas:**
- `ScreeningCreateRequest` - Request body for POST (subject info, locale, tier, consent)
- `ScreeningResponse` - Response with status, progress, risk score, findings
- `ScreeningListResponse` - Paginated list of screenings

**Validation rules:**
- D3 search degree requires Enhanced service tier
- Date of birth must be in YYYY-MM-DD format
- Subject full_name is required

### HRIS Webhook API (`/v1/hris/webhooks/`)
| Endpoint | Purpose | Auth Required |
|----------|---------|---------------|
| `POST /v1/hris/webhooks/{tenant_id}` | Receive HRIS webhook | Signature |
| `POST /v1/hris/webhooks/{tenant_id}/test` | Test webhook connectivity | No |
| `GET /v1/hris/webhooks/{tenant_id}/status` | Check connection status | No |

**Key schemas:**
- `WebhookResponse` - Confirmation of webhook receipt (event_id, timestamp, status)
- `WebhookTestResponse` - Test endpoint response (platform, connection status)
- `WebhookConnectionStatus` - Detailed connection status

**Authentication:**
- HRIS webhooks bypass Bearer token auth and use webhook signature validation
- Signature validated via HRISGateway.validate_inbound_event()

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

## Investigation Framework (`src/elile/investigation/`)

The SAR (Search-Assess-Refine) loop orchestrates iterative information gathering for each information type.

### SAR State Machine
```python
from elile.investigation import (
    SARStateMachine,
    SARConfig,
    SARPhase,
    CompletionReason,
)
from elile.agent.state import InformationType

# Create state machine with custom config
config = SARConfig(
    confidence_threshold=0.85,       # Complete when confidence >= threshold
    foundation_confidence_threshold=0.90,  # Higher for identity/employment/education
    max_iterations_per_type=3,       # Cap iterations if confidence not met
    foundation_max_iterations=4,     # More iterations for foundation types
    min_gain_threshold=0.1,          # Stop if info gain < 10%
)
machine = SARStateMachine(config)

# Initialize and run SAR loop for a type
machine.initialize_type(InformationType.CRIMINAL)
iteration = machine.start_iteration(InformationType.CRIMINAL)

# ... execute queries, analyze results ...

# Record iteration metrics
iteration.queries_executed = 10
iteration.new_facts_this_iteration = 8
iteration.confidence_score = 0.75

# Complete iteration - returns True if should continue
should_continue = machine.complete_iteration(InformationType.CRIMINAL, iteration)

if not should_continue:
    state = machine.get_type_state(InformationType.CRIMINAL)
    print(f"Completed: {state.completion_reason}")
    # CompletionReason.CONFIDENCE_MET, MAX_ITERATIONS, DIMINISHING_RETURNS, or SKIPPED
```

### SAR Phase Flow

Each information type cycles through: `SEARCH → ASSESS → REFINE → (loop or complete)`

| Phase | Description |
|-------|-------------|
| `SEARCH` | Generating and executing queries |
| `ASSESS` | Analyzing results, calculating confidence |
| `REFINE` | Deciding to continue or complete |
| `COMPLETE` | Confidence threshold met |
| `CAPPED` | Max iterations reached |
| `DIMINISHED` | Diminishing returns detected |

### Foundation Types

Foundation types (identity, employment, education) use higher thresholds:
- Confidence threshold: 0.90 (vs 0.85 standard)
- Max iterations: 4 (vs 3 standard)

```python
from elile.investigation import FOUNDATION_TYPES

machine.is_foundation_type(InformationType.IDENTITY)  # True
machine.get_confidence_threshold(InformationType.IDENTITY)  # 0.90
machine.get_max_iterations(InformationType.IDENTITY)  # 4
```

### Investigation Summary
```python
summary = machine.get_summary()
# SARSummary with:
# - types_processed, types_complete, types_capped, types_diminished, types_skipped
# - total_iterations, total_facts, total_queries
# - average_confidence, min_confidence, max_confidence
```

### Query Planner

Generates search queries for each information type using accumulated knowledge:

```python
from elile.investigation import (
    QueryPlanner,
    SearchQuery,
    QueryPlanResult,
    QueryType,
    INFO_TYPE_TO_CHECK_TYPES,
)
from elile.agent.state import InformationType, KnowledgeBase
from elile.compliance.types import Locale, CheckType
from elile.providers.types import ServiceTier

planner = QueryPlanner()
kb = KnowledgeBase()  # Accumulates facts across iterations

# Plan queries for an information type
result: QueryPlanResult = planner.plan_queries(
    info_type=InformationType.CRIMINAL,
    knowledge_base=kb,
    iteration_number=1,
    gaps=[],  # List of knowledge gaps to fill
    locale=Locale.US,
    tier=ServiceTier.STANDARD,
    available_providers=["sterling", "checkr"],
    subject_name="John Smith",
)

# Result contains:
# - queries: list[SearchQuery] - queries to execute
# - enrichment_sources: list[InformationType] - types used for enrichment
# - skipped_reason: str | None - why no queries if empty
```

#### Query Types

| Type | Description | Priority |
|------|-------------|----------|
| `INITIAL` | First iteration queries | 1 (highest) |
| `ENRICHED` | Queries using facts from other types | 2 |
| `GAP_FILL` | Queries targeting knowledge gaps | 2 |
| `REFINEMENT` | Follow-up queries based on findings | 3 |

#### Cross-Type Enrichment

The planner enriches queries using facts from completed information types:
- Criminal queries: Add counties from known addresses
- Employment queries: Add name variants from identity verification
- Adverse media queries: Use all known entities and locations
- Network queries: Use discovered associated entities

```python
# Example: Criminal queries enriched with address counties
# If KnowledgeBase has fact: "Subject lived in Los Angeles County"
# Criminal query will include county-level search parameters

# Check what check types map to each information type
check_types = INFO_TYPE_TO_CHECK_TYPES[InformationType.CRIMINAL]
# [CheckType.CRIMINAL_NATIONAL, CheckType.CRIMINAL_COUNTY, ...]
```

#### SearchQuery Structure

```python
@dataclass
class SearchQuery:
    query_id: UUID             # UUIDv7 identifier
    info_type: InformationType # Type being searched
    query_type: QueryType      # INITIAL, ENRICHED, GAP_FILL, REFINEMENT
    provider_id: str           # Target provider
    check_type: CheckType      # Type of check to perform
    search_params: dict[str, Any]  # Provider-specific parameters
    iteration_number: int      # Current SAR iteration
    priority: int              # 0=low, higher=more important
```

### Query Executor

Executes search queries against data providers with retry, rate limiting, and caching:

```python
from elile.investigation import (
    QueryExecutor,
    QueryResult,
    QueryStatus,
    ExecutionSummary,
    ExecutorConfig,
    create_query_executor,
)
from elile.providers.router import RequestRouter

# Create executor with router
router = RequestRouter(registry=provider_registry)
executor = create_query_executor(router=router)

# Execute queries from planner
results, summary = await executor.execute_queries(
    queries=planned_queries,
    entity_id=entity_id,
    tenant_id=tenant_id,
    locale=Locale.US,
    service_tier=ServiceTier.STANDARD,
)

# Check results
for result in results:
    if result.status == QueryStatus.SUCCESS:
        process_findings(result.normalized_data)
    else:
        log_failure(result.error_message)

# Review execution summary
print(f"Success rate: {summary.success_rate:.1f}%")
print(f"Cache hits: {summary.cache_hits}")
```

#### Query Status Values

| Status | Description |
|--------|-------------|
| `SUCCESS` | Query executed successfully |
| `FAILED` | Query failed after retries |
| `TIMEOUT` | Query timed out |
| `RATE_LIMITED` | Provider rate limit exceeded |
| `NO_PROVIDER` | No provider available for check type |
| `SKIPPED` | Query was skipped (e.g., duplicate) |

### SAR Loop Orchestrator

The orchestrator coordinates all SAR components to execute complete investigations:

```python
from elile.investigation import (
    SARLoopOrchestrator,
    OrchestratorConfig,
    InvestigationResult,
    TypeCycleResult,
    ProgressEvent,
    create_sar_orchestrator,
)
from elile.agent.state import KnowledgeBase, ServiceTier
from elile.compliance.types import Locale, RoleCategory

# Create orchestrator with all components
orchestrator = SARLoopOrchestrator(
    state_machine=state_machine,
    query_planner=planner,
    query_executor=executor,
    result_assessor=assessor,
    query_refiner=refiner,
    iteration_controller=controller,
    type_manager=type_manager,
    config=OrchestratorConfig(
        process_types_parallel=True,
        max_parallel_types=5,
        continue_on_type_error=True,
    ),
)

# Register progress handler
async def on_progress(event: ProgressEvent):
    print(f"{event.event_type}: {event.message}")

orchestrator.on_progress(on_progress)

# Execute complete investigation
kb = KnowledgeBase()
result: InvestigationResult = await orchestrator.execute_investigation(
    knowledge_base=kb,
    subject_identifiers=identifiers,
    locale=Locale.US,
    tier=ServiceTier.STANDARD,
    role_category=RoleCategory.STANDARD,
    available_providers=["sterling", "checkr"],
    entity_id=entity_id,
    tenant_id=tenant_id,
)

# Check results
if result.success:
    print(f"Complete: {result.types_completed} types, {result.total_facts} facts")
for info_type, type_result in result.type_results.items():
    print(f"  {info_type.value}: {type_result.final_confidence:.1%} confidence")
```

#### Factory Function

Use the factory for quick setup (requires injecting QueryExecutor):

```python
orchestrator = create_sar_orchestrator(
    sar_config=SARConfig(confidence_threshold=0.85),
    orchestrator_config=OrchestratorConfig(max_parallel_types=3),
)
# Note: You must inject a properly configured QueryExecutor
```

#### Progress Events

| Event Type | When Emitted |
|------------|--------------|
| `investigation_started` | Investigation begins |
| `phase_started` | New information phase begins |
| `iteration_started` | SAR iteration begins for a type |
| `iteration_completed` | SAR iteration completes |
| `investigation_completed` | Full investigation completes |
| `investigation_failed` | Investigation fails with error |

### Finding Extractor

Extracts structured findings from facts using AI or rule-based analysis:

```python
from elile.investigation import (
    FindingExtractor,
    Finding,
    FindingCategory,
    Severity,
    ExtractionResult,
    ExtractorConfig,
)
from elile.agent.state import InformationType
from elile.compliance.types import RoleCategory

# Create extractor (with or without AI model)
extractor = FindingExtractor(
    ai_model=claude_adapter,  # Optional - uses rules if None
    config=ExtractorConfig(
        min_confidence=0.5,
        enable_corroboration=True,
    ),
)

# Extract findings from facts
result: ExtractionResult = await extractor.extract_findings(
    facts=facts,
    info_type=InformationType.CRIMINAL,
    role_category=RoleCategory.FINANCIAL,
    entity_id=entity_id,
)

for finding in result.findings:
    print(f"{finding.severity}: {finding.summary}")
    print(f"  Category: {finding.category}")
    print(f"  Confidence: {finding.confidence:.1%}")
    print(f"  Relevance: {finding.relevance_to_role:.1%}")
    print(f"  Corroborated: {finding.corroborated}")
```

#### Finding Categories

| Category | Description |
|----------|-------------|
| `CRIMINAL` | Criminal records, convictions, arrests |
| `FINANCIAL` | Bankruptcy, liens, judgments |
| `REGULATORY` | License issues, sanctions, compliance |
| `REPUTATION` | Adverse media, references |
| `VERIFICATION` | Identity, employment, education verification |
| `BEHAVIORAL` | Social media concerns, patterns |
| `NETWORK` | Connections to concerning entities |

#### Severity Levels

| Severity | Description |
|----------|-------------|
| `CRITICAL` | Immediate disqualifying factors |
| `HIGH` | Significant concerns requiring review |
| `MEDIUM` | Notable issues to consider |
| `LOW` | Minor items for awareness |

### Phase Handlers (`src/elile/investigation/phases/`)

Phase-specific handlers coordinate SAR loop execution for groups of information types:

#### Foundation Phase (Sequential Processing)
```python
from elile.investigation.phases import (
    FoundationPhaseHandler,
    FoundationConfig,
    BaselineProfile,
    VerificationStatus,
    create_foundation_handler,
)

handler = create_foundation_handler(orchestrator=orchestrator)

result = await handler.execute(
    knowledge_base=kb,
    subject_identifiers=identifiers,
    locale=Locale.US,
    tier=ServiceTier.STANDARD,
    available_providers=["sterling"],
    entity_id=entity_id,
    tenant_id=tenant_id,
)

if result.can_proceed:
    baseline = result.baseline_profile
    print(f"Identity verified: {baseline.identity.name_verified}")
```

#### Records Phase (Parallel Processing)
```python
from elile.investigation.phases import (
    RecordsPhaseHandler,
    RecordsConfig,
    RecordsProfile,
    RecordSeverity,
    create_records_handler,
)

handler = create_records_handler(
    orchestrator=orchestrator,
    config=RecordsConfig(
        process_parallel=True,
        require_sanctions_check=True,
    ),
)

result = await handler.execute(
    foundation_result=foundation_result,
    knowledge_base=kb,
    subject_identifiers=identifiers,
    locale=Locale.US,
    tier=ServiceTier.STANDARD,
    role_category=RoleCategory.FINANCIAL,
    available_providers=["sterling", "checkr"],
    entity_id=entity_id,
    tenant_id=tenant_id,
)

if result.records_profile.has_critical_findings:
    print("ALERT: Critical findings detected")
```

#### Intelligence Phase (Parallel Processing, Tier-Aware)
```python
from elile.investigation.phases import (
    IntelligencePhaseHandler,
    IntelligenceConfig,
    IntelligenceProfile,
    RiskIndicator,
    create_intelligence_handler,
)

handler = create_intelligence_handler(
    orchestrator=orchestrator,
    config=IntelligenceConfig(
        include_digital_footprint=True,  # Requires Enhanced tier
    ),
)

result = await handler.execute(
    records_result=records_result,
    knowledge_base=kb,
    subject_identifiers=identifiers,
    locale=Locale.US,
    tier=ServiceTier.ENHANCED,
    role_category=RoleCategory.EXECUTIVE,
    available_providers=["newsapi", "socialmedia"],
    entity_id=entity_id,
    tenant_id=tenant_id,
)

if result.intelligence_profile.has_critical_findings:
    print(f"ALERT: Adverse media detected ({result.intelligence_profile.adverse_media_count} items)")
```

#### Network Phase (Sequential Processing, Tier-Aware)
```python
from elile.investigation.phases import (
    NetworkPhaseHandler,
    NetworkConfig,
    NetworkProfile,
    RiskLevel,
    create_network_handler,
)

handler = create_network_handler(
    orchestrator=orchestrator,
    config=NetworkConfig(
        include_d3=True,  # Requires Enhanced tier
    ),
)

result = await handler.execute(
    intelligence_result=intelligence_result,
    knowledge_base=kb,
    subject_identifiers=identifiers,
    locale=Locale.US,
    tier=ServiceTier.ENHANCED,
    role_category=RoleCategory.EXECUTIVE,
    available_providers=["network_provider"],
    entity_id=entity_id,
    tenant_id=tenant_id,
)

if result.network_profile.has_critical_connections:
    print(f"ALERT: Critical connections detected ({len(result.network_profile.risk_connections)} items)")
```

#### Reconciliation Phase (Cross-Source Deduplication)
```python
from elile.investigation.phases import (
    ReconciliationPhaseHandler,
    ReconciliationConfig,
    ReconciliationProfile,
    DeceptionRiskLevel,
    create_reconciliation_handler,
)

handler = create_reconciliation_handler(
    orchestrator=orchestrator,
    config=ReconciliationConfig(
        auto_resolve_low_severity=True,
        systematic_pattern_threshold=4,  # 4+ inconsistencies = systematic pattern
        deception_critical_threshold=0.8,
    ),
)

result = await handler.execute(
    network_result=network_result,
    all_findings=all_findings_from_phases,
    knowledge_base=kb,
    subject_identifiers=identifiers,
    locale=Locale.US,
    tier=ServiceTier.ENHANCED,
    role_category=RoleCategory.EXECUTIVE,
    available_providers=["verification_provider"],
    entity_id=entity_id,
    tenant_id=tenant_id,
)

if result.reconciliation_profile.deception_analysis.deception_risk == DeceptionRiskLevel.CRITICAL:
    print(f"ALERT: Critical deception risk detected (score: {result.reconciliation_profile.deception_analysis.deception_score})")
```

#### Phase Processing Order
| Phase | Types | Processing Mode |
|-------|-------|-----------------|
| Foundation | identity, employment, education | Sequential |
| Records | criminal, civil, financial, licenses, regulatory, sanctions | Parallel |
| Intelligence | adverse_media, digital_footprint | Parallel |
| Network | network_d2, network_d3 | Sequential |
| Reconciliation | reconciliation | Single |

## Risk Analysis (`src/elile/risk/`)

The risk analysis module categorizes findings, calculates risk scores, and provides role-based relevance.

### Finding Classifier

Classifies findings into risk categories with AI validation and reclassification:

```python
from elile.risk import (
    FindingClassifier,
    ClassificationResult,
    ClassifierConfig,
    SubCategory,
    create_finding_classifier,
)
from elile.investigation.finding_extractor import Finding, FindingCategory
from elile.compliance.types import RoleCategory

# Create classifier with default config
classifier = create_finding_classifier()

# Or with custom configuration
classifier = FindingClassifier(config=ClassifierConfig(
    min_validation_confidence=0.7,  # Keep AI category if >= 0.7 confidence
    confidence_per_match=0.15,       # Boost per keyword match
    max_keyword_confidence=0.9,      # Cap confidence from keywords
    enable_subcategory=True,         # Enable sub-category detection
    default_relevance=0.5,           # Default role relevance
))

# Classify a single finding
finding = Finding(
    summary="Felony conviction for theft",
    details="Subject convicted of grand theft in 2020.",
)

result = classifier.classify_finding(
    finding=finding,
    role_category=RoleCategory.FINANCIAL,
)

print(f"Category: {result.assigned_category}")        # CRIMINAL
print(f"Sub-category: {result.sub_category}")         # CRIMINAL_FELONY
print(f"Confidence: {result.category_confidence}")    # 0.6
print(f"Role relevance: {result.relevance_to_role}")  # 0.9
print(f"Reclassified: {result.was_reclassified}")     # False/True

# Batch classification
findings = [finding1, finding2, finding3]
results = classifier.classify_findings(findings, RoleCategory.EXECUTIVE)

# Get distribution
distribution = classifier.get_category_distribution(results)
# {CRIMINAL: 2, FINANCIAL: 1}

sub_distribution = classifier.get_subcategory_distribution(results)
# {CRIMINAL_FELONY: 1, CRIMINAL_DUI: 1, FINANCIAL_BANKRUPTCY: 1}
```

### Finding Categories and Sub-Categories

| Category | Sub-Categories |
|----------|---------------|
| CRIMINAL | felony, misdemeanor, traffic, dui, violent, financial, drug, sex |
| FINANCIAL | bankruptcy, lien, judgment, foreclosure, collection, credit |
| REGULATORY | license, sanction, enforcement, bar, pep |
| REPUTATION | litigation, media, complaint, social |
| VERIFICATION | identity, employment, education, discrepancy, gap |
| BEHAVIORAL | pattern, deception |
| NETWORK | association, shell, pep |

### Role Relevance Matrix

The classifier uses a complete role-relevance matrix. Example relevance scores:

| Category | GOVERNMENT | FINANCIAL | HEALTHCARE | EXECUTIVE | STANDARD |
|----------|------------|-----------|------------|-----------|----------|
| CRIMINAL | 1.0 | 0.9 | 0.85 | 0.85 | 0.7 |
| FINANCIAL | 0.8 | 1.0 | 0.65 | 0.9 | 0.5 |
| REGULATORY | 0.95 | 1.0 | 1.0 | 0.85 | 0.5 |
| VERIFICATION | 1.0 | 1.0 | 0.95 | 1.0 | 0.8 |

### Risk Scorer

Calculates composite risk scores (0-100) with severity weighting, recency decay, and corroboration:

```python
from elile.risk import (
    RiskScorer,
    RiskScore,
    RiskLevel,
    Recommendation,
    ScorerConfig,
    create_risk_scorer,
)

# Create scorer
scorer = create_risk_scorer()

# Calculate risk score
score = scorer.calculate_risk_score(
    findings=classified_findings,
    role_category=RoleCategory.FINANCIAL,
    entity_id=entity_id,
)

print(f"Overall Score: {score.overall_score}/100")
print(f"Risk Level: {score.risk_level.value}")  # low/moderate/high/critical
print(f"Recommendation: {score.recommendation.value}")  # proceed/review_required/etc.

# Category breakdown
for category, cat_score in score.category_scores.items():
    print(f"  {category.value}: {cat_score}")

# Contributing factors
print(f"Critical findings: {score.contributing_factors['critical_findings']}")
print(f"Corroborated: {score.contributing_factors['corroborated_findings']}")
```

### Scoring Components

| Factor | Effect |
|--------|--------|
| Severity | Base score: LOW=10, MEDIUM=25, HIGH=50, CRITICAL=75 |
| Recency | Decay: ≤1yr=1.0, 1-3yr=0.9, 3-7yr=0.7, 7+yr=0.5 |
| Corroboration | Bonus: 1.2x for multi-source findings |
| Category Weight | Criminal=1.5x, Regulatory=1.3x, Verification=1.2x |

### Risk Levels and Recommendations

| Level | Score Range | Recommendation |
|-------|-------------|----------------|
| LOW | 0-25 | PROCEED |
| MODERATE | 26-50 | PROCEED_WITH_CAUTION |
| HIGH | 51-75 | REVIEW_REQUIRED |
| CRITICAL | 76-100 | DO_NOT_PROCEED |

### Severity Calculator

Determines finding severity using rule-based assessment with role and recency adjustments:

```python
from elile.risk import (
    SeverityCalculator,
    SeverityDecision,
    CalculatorConfig,
    create_severity_calculator,
    SEVERITY_RULES,
    SUBCATEGORY_SEVERITY,
    ROLE_SEVERITY_ADJUSTMENTS,
)
from elile.investigation.finding_extractor import Severity

# Create calculator
calculator = create_severity_calculator()

# Calculate severity for a finding
severity, decision = calculator.calculate_severity(
    finding=finding,
    role_category=RoleCategory.FINANCIAL,
    subcategory=SubCategory.CRIMINAL_FELONY,
)

print(f"Severity: {severity.value}")  # critical/high/medium/low
print(f"Method: {decision.determination_method}")  # rule/subcategory/default
print(f"Matched rules: {decision.matched_rules}")  # ['felony conviction']
print(f"Role adjustment: {decision.role_adjustment}")  # +1 or 0
print(f"Recency adjustment: {decision.recency_adjustment}")  # +1 or 0

# Batch processing
results = calculator.calculate_severities(
    findings=findings,
    role_category=RoleCategory.GOVERNMENT,
    subcategories={finding_id: subcategory for ...},
    update_findings=True,  # Update finding.severity in place
)
```

### Severity Rules

Rules match text patterns in finding summary, details, and finding_type:

| Pattern | Severity |
|---------|----------|
| "felony conviction", "murder", "ofac sanction" | CRITICAL |
| "recent bankruptcy", "dui conviction", "finra bar" | HIGH |
| "misdemeanor conviction", "civil judgment", "employment discrepancy" | MEDIUM |
| "employment gap", "address discrepancy", "parking violation" | LOW |

### Severity Adjustments

| Adjustment Type | Condition | Effect |
|-----------------|-----------|--------|
| Role (Criminal + Government) | Criminal finding for government role | +1 severity level |
| Role (Financial + Financial) | Financial finding for finance role | +1 severity level |
| Recency (≤365 days) | Finding within past year | +1 severity level |

### Anomaly Detector

Identifies unusual patterns, statistical outliers, and deception indicators:

```python
from elile.risk import (
    AnomalyDetector,
    Anomaly,
    AnomalyType,
    DeceptionAssessment,
    DetectorConfig,
    create_anomaly_detector,
)
from elile.investigation.result_assessor import Fact, DetectedInconsistency

# Create detector
detector = create_anomaly_detector()

# Detect anomalies
anomalies = detector.detect_anomalies(
    facts=extracted_facts,
    inconsistencies=detected_inconsistencies,
)

for anomaly in anomalies:
    print(f"Type: {anomaly.anomaly_type.value}")
    print(f"Severity: {anomaly.severity.value}")
    print(f"Deception score: {anomaly.deception_score}")

# Assess overall deception likelihood
assessment = detector.assess_deception(anomalies, inconsistencies)
print(f"Deception risk: {assessment.risk_level}")
print(f"Overall score: {assessment.overall_score}")
```

### Anomaly Types

| Category | Types |
|----------|-------|
| Statistical | outlier, unusual_frequency, improbable_value |
| Inconsistency | systematic, cross_field, directional_bias |
| Timeline | impossible, chronological_gap, overlapping |
| Credential | inflation (education, title), qualification_gap |
| Deception | pattern, concealment, fabrication |

### Deception Risk Levels

| Level | Score Range | Meaning |
|-------|-------------|---------|
| none | 0.0-0.1 | No deception signals |
| low | 0.1-0.3 | Minor concerns |
| moderate | 0.3-0.5 | Requires attention |
| high | 0.5-0.75 | Significant deception risk |
| critical | 0.75-1.0 | Strong deception indicators |

### Pattern Recognizer

Identifies behavioral patterns in findings including escalation, frequency, and cross-domain patterns:

```python
from elile.risk import (
    PatternRecognizer,
    Pattern,
    PatternSummary,
    PatternType,
    RecognizerConfig,
    create_pattern_recognizer,
)

# Create recognizer
recognizer = create_pattern_recognizer()

# Recognize patterns in findings
patterns = recognizer.recognize_patterns(findings)

for pattern in patterns:
    print(f"{pattern.pattern_type.value}: {pattern.description}")
    print(f"Severity: {pattern.severity}, Confidence: {pattern.confidence}")

# Get pattern summary
summary = recognizer.summarize_patterns(patterns, findings)
print(f"Risk score: {summary.risk_score}")
print(f"Key concerns: {summary.key_concerns}")
```

### Pattern Types

| Category | Types |
|----------|-------|
| Escalation | severity_escalation, frequency_escalation |
| Frequency | burst_activity, recurring_issues, periodic_pattern |
| Cross-domain | multi_category, systemic_issues, correlated_findings |
| Temporal | timeline_cluster, dormant_period, recent_concentration |
| Behavioral | repeat_offender, progressive_degradation, improvement_trend |

### Connection Analyzer

Analyzes entity connections and network risk for D2/D3 investigations:

```python
from elile.risk import (
    ConnectionAnalyzer,
    ConnectionAnalysisResult,
    ConnectionGraph,
    AnalyzerConfig,
    create_connection_analyzer,
)
from elile.agent.state import SearchDegree

# Create analyzer
analyzer = create_connection_analyzer()

# Analyze connections
result = analyzer.analyze_connections(
    subject_entity=subject,
    discovered_entities=entities,
    relations=relations,
    degree=SearchDegree.D2,
)

print(f"Total propagated risk: {result.total_propagated_risk:.2f}")
print(f"Risk connections: {len(result.risk_connections_found)}")
print(f"Highest risk: {result.highest_connection_risk.value}")

# Get visualization data for graph rendering
viz_data = analyzer.get_visualization_data(result)
# Returns: {nodes: [...], edges: [...], metadata: {...}}

# Analyze from NetworkProfile
result = analyzer.analyze_from_network_profile(
    network_profile=profile,
    degree=SearchDegree.D3,
)
```

### Connection Risk Types

| Category | Types |
|----------|-------|
| Regulatory | sanctions_connection, pep_connection, watchlist_connection |
| Structural | shell_company, circular_ownership, opaque_structure |
| Behavioral | frequent_entity_changes, rapid_network_growth, unusual_concentration |
| Association | criminal_association, fraud_association, high_risk_industry, adverse_media_association |

### Risk Propagation

Risk propagates through network connections with decay factors:
- **CRITICAL**: 70% retained per hop
- **HIGH**: 60% retained per hop
- **MODERATE**: 50% retained per hop
- **LOW**: 30% retained per hop

Connection strength and relation type affect propagation:
- **OWNERSHIP**: 100% risk factor
- **FINANCIAL**: 95% risk factor
- **BUSINESS/POLITICAL**: 90% risk factor
- **FAMILY/LEGAL**: 80% risk factor
- **EMPLOYMENT**: 60% risk factor
- **SOCIAL/EDUCATIONAL**: 20-30% risk factor

## Screening Service (`src/elile/screening/`)

The screening service orchestrates end-to-end background screening workflows.

### Screening Orchestrator

```python
from elile.screening import (
    ScreeningOrchestrator,
    ScreeningRequest,
    ScreeningResult,
    ScreeningStatus,
    OrchestratorConfig,
    create_screening_orchestrator,
)
from elile.entity.types import SubjectIdentifiers
from elile.compliance.types import Locale, RoleCategory
from elile.agent.state import ServiceTier, SearchDegree, VigilanceLevel

# Create orchestrator
orchestrator = create_screening_orchestrator()

# Create screening request
request = ScreeningRequest(
    tenant_id=tenant_id,
    subject=SubjectIdentifiers(
        full_name="John Smith",
        date_of_birth=date(1985, 3, 15),
        ssn="123-45-6789",
    ),
    locale=Locale.US,
    service_tier=ServiceTier.STANDARD,
    search_degree=SearchDegree.D1,
    vigilance_level=VigilanceLevel.V0,
    role_category=RoleCategory.STANDARD,
    consent_token="consent-abc123",
)

# Execute screening
result = await orchestrator.execute_screening(request)

if result.status == ScreeningStatus.COMPLETE:
    print(f"Risk score: {result.risk_score}")
    print(f"Risk level: {result.risk_level}")
    print(f"Recommendation: {result.recommendation}")
```

### Screening Request

| Field | Type | Description |
|-------|------|-------------|
| `screening_id` | UUID | Auto-generated UUIDv7 |
| `tenant_id` | UUID | Tenant requesting the screening |
| `subject` | SubjectIdentifiers | Subject information (name, DOB, SSN, etc.) |
| `locale` | Locale | Geographic jurisdiction |
| `service_tier` | ServiceTier | STANDARD or ENHANCED |
| `search_degree` | SearchDegree | D1 (subject), D2 (connections), D3 (extended) |
| `vigilance_level` | VigilanceLevel | Ongoing monitoring frequency |
| `role_category` | RoleCategory | Job role for relevance weighting |
| `consent_token` | str | Proof of subject consent |
| `report_types` | list[ReportType] | Reports to generate |
| `priority` | ScreeningPriority | Processing priority |

### Screening Result

| Field | Type | Description |
|-------|------|-------------|
| `result_id` | UUID | Result identifier |
| `screening_id` | UUID | Reference to request |
| `status` | ScreeningStatus | Current status |
| `risk_assessment_id` | UUID | Reference to risk assessment |
| `risk_score` | int | Overall risk score (0-100) |
| `risk_level` | str | low/moderate/high/critical |
| `recommendation` | str | proceed/review_required/do_not_proceed |
| `reports` | list[GeneratedReport] | Generated reports |
| `phases` | list[ScreeningPhaseResult] | Phase timing and status |
| `cost_summary` | ScreeningCostSummary | Cost breakdown |

### Screening Phases

The orchestrator executes these phases in sequence:

| Phase | Description |
|-------|-------------|
| Validation | Validate request and subject identifiers |
| Compliance | Check locale-specific compliance rules |
| Consent | Verify consent token validity |
| Investigation | Execute SAR loop for all information types |
| Risk Analysis | Calculate risk score and assessment |
| Report Generation | Generate requested report types |

### Screening Status Values

| Status | Description |
|--------|-------------|
| `PENDING` | Request received, not started |
| `VALIDATING` | Validating request |
| `IN_PROGRESS` | Investigation running |
| `ANALYZING` | Risk analysis in progress |
| `GENERATING_REPORT` | Report generation |
| `COMPLETE` | Successfully completed |
| `FAILED` | Failed due to error |
| `CANCELLED` | Cancelled |
| `COMPLIANCE_BLOCKED` | Blocked by compliance rules |

### Report Types

| Type | Audience | Purpose |
|------|----------|---------|
| `SUMMARY` | HR Manager | Risk level and recommendation |
| `AUDIT` | Compliance | Data sources and consent trail |
| `INVESTIGATION` | Security | Detailed findings |
| `CASE_FILE` | Investigator | Complete raw data |
| `DISCLOSURE` | Subject | FCRA-compliant summary |
| `PORTFOLIO` | Executive | Aggregate metrics |

### Result Compiler

The ResultCompiler aggregates screening results for report generation:

```python
from elile.screening import (
    ResultCompiler,
    CompilerConfig,
    CompiledResult,
    create_result_compiler,
)

# Create compiler
compiler = create_result_compiler()

# Compile results from SAR loop and risk assessment
compiled = compiler.compile_results(
    sar_results=sar_type_states,  # Dict[InformationType, SARTypeState]
    findings=findings,             # List[Finding]
    risk_assessment=assessment,    # ComprehensiveRiskAssessment
    connections=connections,       # List[DiscoveredEntity]
    relations=relations,          # List[EntityRelation]
    risk_connections=risk_conns,  # List[RiskConnection]
    screening_id=screening_id,
)

# Access compiled summaries
print(f"Total findings: {compiled.findings_summary.total_findings}")
print(f"Critical findings: {compiled.findings_summary.by_severity[Severity.CRITICAL]}")
print(f"Types processed: {compiled.investigation_summary.types_processed}")
print(f"Network entities: {compiled.connection_summary.entities_discovered}")

# Convert to ScreeningResult for API response
result = compiler.to_screening_result(compiled, screening_id=screening_id)
```

### Compiled Result Summaries

| Summary Type | Contents |
|--------------|----------|
| `FindingsSummary` | Category breakdowns, severity counts, narrative |
| `CategorySummary` | Per-category finding counts, key findings, corroboration |
| `InvestigationSummary` | SAR loop stats, iterations, confidence metrics |
| `ConnectionSummary` | D2/D3 entity counts, risk connections, PEP/sanctions |

## Observability (`src/elile/observability/`)

### OpenTelemetry Tracing (`tracing.py`)
```python
from elile.observability import TracingManager, TracingConfig, traced_async

# Initialize tracing
config = TracingConfig(
    service_name="elile",
    otlp_endpoint="http://localhost:4317",
)
manager = TracingManager(config)
manager.initialize()
manager.instrument_fastapi(app)

# Use tracing decorator
@traced_async("screening.execute")
async def execute_screening():
    add_span_attributes(screening_id=str(screening.id))
    ...
```

### Prometheus Metrics (`metrics.py`)
```python
from elile.observability import (
    observe_screening_duration,
    record_provider_query,
    observe_risk_score,
)

# Record screening duration
with observe_screening_duration(tier="standard", degree="d1") as ctx:
    result = await execute_screening()
    ctx["status"] = "success"

# Record provider queries
record_provider_query(
    provider_id="sterling",
    check_type="criminal_national",
    status="success",
    duration_seconds=1.5,
)
```

### Key Metrics
| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `elile_screening_duration_seconds` | Histogram | tier, degree, status | Screening execution time |
| `elile_screenings_total` | Counter | tier, degree, status, locale | Total screenings processed |
| `elile_provider_query_duration_seconds` | Histogram | provider_id, check_type, status | Provider query latency |
| `elile_sar_confidence_score` | Histogram | info_type | SAR loop confidence scores |
| `elile_risk_score` | Histogram | role_category | Risk score distribution |
| `elile_http_request_duration_seconds` | Histogram | method, endpoint, status_code | HTTP request latency |

### Specialized Tracing Decorators
```python
from elile.observability import trace_screening, trace_provider_query, trace_sar_loop

@trace_screening(screening_id=screening_id, tier="standard", degree="d1")
async def execute_screening(): ...

@trace_provider_query(provider_id="sterling", check_type="criminal")
async def query_provider(): ...

@trace_sar_loop(info_type="criminal", iteration=1)
async def run_sar_iteration(): ...
```

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

### Investigation Framework (`src/elile/investigation/models.py`)

| Enum | Values | Purpose |
|------|--------|---------|
| `SARPhase` | SEARCH, ASSESS, REFINE, COMPLETE, CAPPED, DIMINISHED | SAR loop phases |
| `CompletionReason` | CONFIDENCE_MET, MAX_ITERATIONS, DIMINISHING_RETURNS, SKIPPED, ERROR | Why type completed |

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
| `src/elile/investigation/models.py` | SARPhase, CompletionReason, SARIterationState, SARTypeState, SARConfig, SARSummary | Task 5.1 |
| `src/elile/investigation/sar_machine.py` | SARStateMachine, create_sar_machine, FOUNDATION_TYPES | Task 5.1 |
| `src/elile/investigation/query_planner.py` | QueryPlanner, QueryPlanResult, SearchQuery, QueryType, INFO_TYPE_TO_CHECK_TYPES | Task 5.2 |
| `src/elile/investigation/query_executor.py` | QueryExecutor, QueryResult, QueryStatus, ExecutionSummary, ExecutorConfig | Task 5.3 |
| `src/elile/investigation/result_assessor.py` | ResultAssessor, AssessmentResult, Fact, Gap, DetectedInconsistency, DiscoveredEntity | Task 5.4 |
| `src/elile/investigation/query_refiner.py` | QueryRefiner, RefinerConfig, RefinementResult, GAP_STRATEGIES | Task 5.5 |
| `src/elile/investigation/information_type_manager.py` | InformationTypeManager, InformationPhase, TypeDependency, TypeSequence | Task 5.6 |
| `src/elile/investigation/confidence_scorer.py` | ConfidenceScorer, ConfidenceScore, ScorerConfig, FactorBreakdown, DEFAULT_EXPECTED_FACTS | Task 5.7 |
| `src/elile/investigation/iteration_controller.py` | IterationController, IterationDecision, ControllerConfig, DecisionType | Task 5.8 |
| `src/elile/investigation/sar_orchestrator.py` | SARLoopOrchestrator, InvestigationResult, TypeCycleResult, OrchestratorConfig, ProgressEvent, create_sar_orchestrator | Task 5.9 |
| `src/elile/investigation/finding_extractor.py` | FindingExtractor, Finding, FindingCategory, Severity, ExtractionResult, ExtractorConfig, DataSourceRef | Task 5.10 |
| `src/elile/investigation/phases/__init__.py` | Phase handler exports | Task 5.11 |
| `src/elile/investigation/phases/foundation.py` | FoundationPhaseHandler, BaselineProfile, IdentityBaseline, EmploymentBaseline, EducationBaseline, VerificationStatus, FoundationConfig, FoundationPhaseResult | Task 5.11 |
| `src/elile/investigation/phases/records.py` | RecordsPhaseHandler, RecordsProfile, RecordSeverity, RecordType, CriminalRecord, CivilRecord, FinancialRecord, LicenseRecord, RegulatoryRecord, SanctionsRecord, RecordsConfig, RecordsPhaseResult | Task 5.12 |
| `src/elile/investigation/phases/intelligence.py` | IntelligencePhaseHandler, IntelligenceProfile, IntelligenceConfig, IntelligencePhaseResult, MediaMention, MediaSentiment, MediaCategory, SocialProfile, SocialPlatform, ProfessionalPresence, RiskIndicator | Task 5.13 |
| `src/elile/investigation/phases/network.py` | NetworkPhaseHandler, NetworkProfile, NetworkConfig, NetworkPhaseResult, DiscoveredEntity, EntityRelation, RiskConnection, RelationType, EntityType, RiskLevel, ConnectionStrength | Task 5.14 |
| `src/elile/investigation/phases/reconciliation.py` | ReconciliationPhaseHandler, ReconciliationProfile, ReconciliationConfig, ReconciliationPhaseResult, Inconsistency, InconsistencyType, ConflictResolution, ResolutionStatus, DeceptionAnalysis, DeceptionRiskLevel | Task 5.15 |
| `src/elile/investigation/checkpoint.py` | InvestigationCheckpointManager, InvestigationCheckpoint, CheckpointConfig, CheckpointReason, CheckpointStatus, TypeStateSnapshot, ResumeResult, create_checkpoint_manager | Task 5.16 |
| `src/elile/risk/finding_classifier.py` | FindingClassifier, ClassificationResult, ClassifierConfig, SubCategory, CATEGORY_KEYWORDS, SUBCATEGORY_KEYWORDS, ROLE_RELEVANCE_MATRIX, create_finding_classifier | Task 6.1 |
| `src/elile/risk/risk_scorer.py` | RiskScorer, RiskScore, RiskLevel, Recommendation, ScorerConfig, create_risk_scorer | Task 6.2 |
| `src/elile/screening/__init__.py` | Screening module exports | Task 7.1 |
| `src/elile/screening/types.py` | ScreeningRequest, ScreeningResult, ScreeningStatus, ReportType, ScreeningPhaseResult, ScreeningCostSummary, GeneratedReport, ScreeningError | Task 7.1 |
| `src/elile/screening/orchestrator.py` | ScreeningOrchestrator, OrchestratorConfig, create_screening_orchestrator | Task 7.1 |
| `src/elile/screening/degree_handlers.py` | D1Handler, D2Handler, D3Handler, DegreeHandlerConfig, D1Result, D2Result, D3Result, create_d1_handler, create_d2_handler, create_d3_handler | Task 7.2-7.3 |
| `src/elile/screening/tier_router.py` | TierRouter, TierRouterConfig, TierCapabilities, DataSourceSpec, DataSourceTier, RoutingResult, create_tier_router, create_default_data_sources | Task 7.4 |
| `src/elile/screening/state_manager.py` | ScreeningStateManager, StateManagerConfig, ScreeningState, ScreeningPhase, ProgressEvent, ProgressEventType, StateStore, InMemoryStateStore, create_state_manager | Task 7.5 |
| `src/elile/screening/result_compiler.py` | ResultCompiler, CompilerConfig, CompiledResult, FindingsSummary, CategorySummary, InvestigationSummary, SARSummary, ConnectionSummary, SummaryFormat, create_result_compiler | Task 7.6 |
| `src/elile/reporting/__init__.py` | Reporting module exports | Task 8.1 |
| `src/elile/reporting/types.py` | ReportPersona, OutputFormat, RedactionLevel, ReportSection, DisclosureType, GeneratedReport, GeneratedReportMetadata, ReportContent, ReportRequest, FieldRule, BrandingConfig, LayoutConfig | Task 8.1 |
| `src/elile/reporting/template_definitions.py` | ReportTemplate, TemplateRegistry, create_template_registry | Task 8.1 |
| `src/elile/reporting/report_generator.py` | ReportGenerator, GeneratorConfig, create_report_generator | Task 8.1 |
| `src/elile/reporting/templates/__init__.py` | Templates package exports, re-exports from template_definitions | Task 8.2-8.3 |
| `src/elile/reporting/templates/hr_summary.py` | HRSummaryBuilder, HRSummaryConfig, HRSummaryContent, RiskAssessmentDisplay, FindingIndicator, CategoryScore, CategoryStatus, RecommendedAction | Task 8.2 |
| `src/elile/reporting/templates/compliance_audit.py` | ComplianceAuditBuilder, ComplianceAuditConfig, ComplianceAuditContent, ComplianceStatus, ConsentVerificationSection, ConsentRecord, DisclosureRecord, ComplianceRulesSection, AppliedRule, DataSourcesSection, DataSourceAccess, AuditTrailSection, AuditTrailEvent, DataHandlingSection, DataHandlingAttestation, DataHandlingStatus | Task 8.3 |
| `src/elile/monitoring/__init__.py` | Monitoring module exports | Task 9.1-9.4 |
| `src/elile/monitoring/types.py` | MonitoringConfig, MonitoringCheck, MonitoringStatus, CheckType, CheckStatus, LifecycleEvent, LifecycleEventType, ProfileDelta, DeltaSeverity, MonitoringAlert, AlertSeverity, ScheduleResult, MonitoringError | Task 9.1 |
| `src/elile/monitoring/scheduler.py` | MonitoringScheduler, SchedulerConfig, MonitoringStore, InMemoryMonitoringStore, AUTO_ALERT_THRESHOLDS, HUMAN_REVIEW_THRESHOLDS, create_monitoring_scheduler | Task 9.1 |
| `src/elile/monitoring/vigilance_manager.py` | VigilanceManager, ManagerConfig, VigilanceDecision, VigilanceUpdate, VigilanceChangeReason, EscalationAction, RoleVigilanceMapping, SchedulerProtocol, ROLE_DEFAULT_VIGILANCE, RISK_THRESHOLD_V2, RISK_THRESHOLD_V3, create_vigilance_manager | Task 9.2 |
| `src/elile/monitoring/delta_detector.py` | DeltaDetector, DetectorConfig, DeltaResult, DeltaType, FindingChange, ConnectionChange, RiskScoreChange, create_delta_detector, severity_rank, severity_to_delta_severity | Task 9.3 |
| `src/elile/monitoring/alert_generator.py` | AlertGenerator, AlertConfig, AlertStatus, GeneratedAlert, EscalationTrigger, NotificationChannel, NotificationChannelType, NotificationResult, MockEmailChannel, MockWebhookChannel, MockSMSChannel, AUTO_ALERT_THRESHOLDS, create_alert_generator | Task 9.4 |
| `src/elile/hris/__init__.py` | HRIS module exports | Task 10.1 |
| `src/elile/hris/gateway.py` | HRISGateway, GatewayConfig, HRISAdapter, BaseHRISAdapter, MockHRISAdapter, HRISEvent, HRISEventType, HRISPlatform, HRISConnection, HRISConnectionStatus, ScreeningUpdate, AlertUpdate, EmployeeInfo, WebhookValidationResult, create_hris_gateway | Task 10.1 |
| `src/elile/api/routers/v1/hris_webhook.py` | HRIS webhook receiver endpoints (POST /{tenant_id}, /test, GET /status) | Task 10.2 |
| `src/elile/api/schemas/hris_webhook.py` | WebhookResponse, WebhookTestResponse, WebhookConnectionStatus, WebhookErrorCode | Task 10.2 |
| `src/elile/hris/event_processor.py` | HRISEventProcessor, ProcessorConfig, ProcessingResult, ProcessingStatus, ProcessingAction, EventStore, InMemoryEventStore, create_event_processor | Task 10.3 |
| `src/elile/hris/result_publisher.py` | HRISResultPublisher, PublisherConfig, PublishResult, PublishStatus, PublishEventType, DeliveryRecord, create_result_publisher | Task 10.4 |
| `src/elile/api/routers/v1/dashboard.py` | HR Dashboard API endpoints (portfolio, screenings, alerts, risk-distribution) | Task 11.1 |
| `src/elile/api/schemas/dashboard.py` | HRPortfolioResponse, HRScreeningsListResponse, HRAlertsListResponse, RiskDistributionResponse, PortfolioMetrics, RiskDistribution, RiskDistributionItem, AlertSummary, ScreeningSummary | Task 11.1 |
| `src/elile/api/routers/v1/compliance.py` | Compliance Portal API endpoints (audit-log, consent-tracking, data-erasure, reports, metrics) | Task 11.2 |
| `src/elile/api/schemas/compliance.py` | AuditLogResponse, ConsentTrackingResponse, DataErasureRequest, DataErasureResponse, ComplianceReportsListResponse, ComplianceMetricsResponse, ErasureStatus, ComplianceStatus | Task 11.2 |

## Architecture References

See `docs/architecture/` for detailed design documents:
- `01-design.md` - Design principles
- `02-core-system.md` - Database, API structure
- `03-screening.md` - Service tiers, screening flow
- `07-compliance.md` - Compliance engine, security
