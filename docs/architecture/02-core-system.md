# Core System Infrastructure

> **Prerequisites**: [01-design.md](01-design.md)
>
> **See also**: [06-data-sources.md](06-data-sources.md) for provider details, [10-platform.md](10-platform.md) for deployment

This document covers the foundational infrastructure shared across all domains: data storage, caching, API patterns, and technology stack.

## Theory of Operation

Elile operates as a **stateful investigation orchestrator** that coordinates multi-source data acquisition, entity resolution, and risk analysis while maintaining strict compliance boundaries.

### Core Operational Principles

1. **Locale-First Enforcement**: Every request carries locale context; compliance rules filter permitted operations before any data acquisition
2. **Entity-Centric Model**: All data resolves to and aggregates around canonical entities (individuals, organizations, addresses)
3. **Cache-Before-Query**: System checks platform-wide cache before incurring provider costs; freshness policies determine reuse
4. **Immutable Profiles**: Each screening creates a versioned snapshot; deltas between versions power evolution analytics
5. **Audit-First Architecture**: All operations generate structured audit events before execution; compliance trail is non-negotiable

### Request Lifecycle

```
┌─────────────────────────────────────────────────────────────────┐
│                    REQUEST LIFECYCLE                             │
│                                                                  │
│  1. INGRESS                                                     │
│     - Request arrives with subject + locale + consent           │
│     - System validates authentication, authorization, consent   │
│     - Creates audit context (request_id, timestamp, actor)      │
│                                                                  │
│  2. COMPLIANCE GATING                                           │
│     - Locale determines permitted check types                   │
│     - Role type filters available data sources                  │
│     - Consent scope limits data collection                      │
│     - System builds "allowed checks" bitmap                     │
│                                                                  │
│  3. ENTITY RESOLUTION                                           │
│     - Subject identifiers → canonical entity lookup             │
│     - Create new entity if not exists                           │
│     - Load entity profile history                               │
│                                                                  │
│  4. DATA ACQUISITION                                            │
│     - For each allowed check:                                   │
│       a. Query cache (check freshness)                          │
│       b. If stale/expired: query provider                       │
│       c. Store result in cache                                  │
│       d. Log cost, source, timestamp                            │
│     - Parallel execution where possible                         │
│                                                                  │
│  5. INVESTIGATION (SAR LOOP)                                    │
│     - LangGraph orchestrates Search-Assess-Refine cycle         │
│     - AI agents analyze findings → discover new entities        │
│     - Recursive entity resolution for connections               │
│     - Depth limited by service tier (D1/D2/D3)                  │
│                                                                  │
│  6. RISK ANALYSIS                                               │
│     - Aggregate findings across all entities                    │
│     - Multi-model scoring (Claude, GPT-4, Gemini)               │
│     - If previous profile exists: compute delta + signals       │
│     - Generate evolution pattern alerts                         │
│                                                                  │
│  7. PROFILE CREATION                                            │
│     - Create immutable profile snapshot (version N)             │
│     - Link findings, connections, risk score                    │
│     - Store data sources used, stale flags                      │
│     - Compute delta from profile (N-1) if exists                │
│                                                                  │
│  8. REPORTING                                                   │
│     - Generate persona-specific reports                         │
│     - Apply locale-specific redactions (GDPR, etc.)             │
│     - Create audit-compliant disclosure docs                    │
│                                                                  │
│  9. AUDIT CLOSURE                                               │
│     - Finalize audit log with all operations performed          │
│     - Record total cost, sources accessed, findings count       │
│     - Emit completion event                                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Stateful Workflow Management

The system uses **LangGraph** for orchestrating long-running, stateful investigations:

- **State Persistence**: Investigation state persists across async operations (provider API calls, AI model invocations)
- **Conditional Routing**: Graph nodes route based on findings (e.g., "found shell company" → trigger corporate registry deep-dive)
- **Human-in-the-Loop**: Investigators can pause, inspect, and redirect workflows mid-execution
- **Resumable**: Workflows survive process restarts via state checkpointing

### Multi-Tenancy Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    TENANT ISOLATION LAYERS                       │
│                                                                  │
│  Layer 1: AUTHENTICATION                                        │
│    - API keys scoped to customer org                           │
│    - JWT tokens carry tenant_id claim                          │
│                                                                  │
│  Layer 2: DATA ISOLATION (cache)                               │
│    - Shared cache: Paid external provider data                 │
│    - Isolated cache: Customer-provided HRIS data               │
│    - Query patterns enforce tenant_id filters                  │
│                                                                  │
│  Layer 3: CONFIGURATION                                         │
│    - Per-tenant compliance overrides                           │
│    - Custom freshness policies                                 │
│    - Locale-specific data retention rules                      │
│                                                                  │
│  Layer 4: AUDIT TRAIL                                          │
│    - All logs tagged with tenant_id                            │
│    - Cross-tenant queries blocked at ORM level                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Application Control Flow

### Entry Point: Screening Request

```python
# Pseudo-code for screening request handling

async def handle_screening_request(request: ScreeningRequest) -> ScreeningResult:
    """
    Main entry point for all screening operations.

    Request carries:
    - subject: SubjectIdentifiers (name, DOB, SSN, etc.)
    - locale: str (ISO 3166-1 alpha-2 country code)
    - service_tier: ServiceTier (standard | enhanced)
    - degree: InvestigationDegree (D1 | D2 | D3)
    - consent_token: str
    - tenant_id: UUID
    """

    # PHASE 1: INGRESS & VALIDATION
    audit_ctx = create_audit_context(request)
    log_audit_event(audit_ctx, "screening_initiated", request.metadata)

    try:
        validate_authentication(request.auth_token)
        validate_authorization(request.tenant_id, request.auth_token)
        validate_consent(request.consent_token, request.subject)
    except ValidationError as e:
        log_audit_event(audit_ctx, "validation_failed", error=e)
        raise

    # PHASE 2: COMPLIANCE GATING
    compliance_engine = ComplianceEngine(locale=request.locale)
    allowed_checks = compliance_engine.filter_permitted_checks(
        base_checks=TIER_TO_CHECKS[request.service_tier],
        subject_role=request.subject.role_type,
        consent_scope=request.consent_token.scope
    )

    if not allowed_checks:
        log_audit_event(audit_ctx, "no_permitted_checks")
        raise ComplianceError("No checks permitted for this locale/role combination")

    log_audit_event(audit_ctx, "compliance_gating_complete",
                   allowed_checks=allowed_checks)

    # PHASE 3: ENTITY RESOLUTION
    entity_resolver = EntityResolver()
    subject_entity = await entity_resolver.resolve_or_create(
        identifiers=request.subject.identifiers,
        tenant_id=request.tenant_id
    )

    # Load profile history for delta analysis
    profile_history = await load_entity_profiles(subject_entity.entity_id)
    previous_profile = profile_history[-1] if profile_history else None

    log_audit_event(audit_ctx, "entity_resolved",
                   entity_id=subject_entity.entity_id,
                   has_history=bool(previous_profile))

    # PHASE 4: DATA ACQUISITION
    data_acquisition_ctx = DataAcquisitionContext(
        entity=subject_entity,
        allowed_checks=allowed_checks,
        service_tier=request.service_tier,
        tenant_id=request.tenant_id,
        audit_ctx=audit_ctx
    )

    acquired_data = await acquire_data_for_checks(data_acquisition_ctx)
    # Returns: dict[CheckType, CachedDataSource]

    # PHASE 5: INVESTIGATION (SAR LOOP)
    investigation_ctx = InvestigationContext(
        subject_entity=subject_entity,
        acquired_data=acquired_data,
        degree=request.degree,
        service_tier=request.service_tier,
        locale=request.locale,
        audit_ctx=audit_ctx
    )

    investigation_result = await run_investigation_workflow(investigation_ctx)
    # LangGraph workflow: search → assess → refine (recursive)
    # Discovers connections, runs secondary checks, builds entity graph

    # PHASE 6: RISK ANALYSIS
    risk_analyzer = MultiModelRiskAnalyzer()
    risk_score = await risk_analyzer.compute_risk(
        findings=investigation_result.all_findings,
        entity_graph=investigation_result.entity_graph,
        locale=request.locale
    )

    # If previous profile exists, detect evolution patterns
    evolution_signals = []
    if previous_profile:
        evolution_analyzer = EvolutionAnalyzer()
        evolution_signals = await evolution_analyzer.detect_patterns(
            current_findings=investigation_result.all_findings,
            previous_profile=previous_profile,
            entity_graph=investigation_result.entity_graph
        )

    log_audit_event(audit_ctx, "risk_analysis_complete",
                   risk_score=risk_score,
                   evolution_signals=len(evolution_signals))

    # PHASE 7: PROFILE CREATION
    new_profile = await create_entity_profile(
        entity_id=subject_entity.entity_id,
        version=(previous_profile.version + 1 if previous_profile else 1),
        findings=investigation_result.all_findings,
        risk_score=risk_score,
        connections=investigation_result.entity_graph.edges,
        data_sources_used=acquired_data.keys(),
        stale_data_used=[ds for ds in acquired_data.values()
                        if ds.freshness_status == FreshnessStatus.STALE],
        evolution_signals=evolution_signals,
        trigger_type=ProfileTrigger.SCREENING,
        trigger_id=audit_ctx.request_id
    )

    # Compute delta if previous version exists
    if previous_profile:
        new_profile.delta = compute_profile_delta(previous_profile, new_profile)

    await store_entity_profile(new_profile)

    log_audit_event(audit_ctx, "profile_created",
                   profile_id=new_profile.profile_id,
                   version=new_profile.version)

    # PHASE 8: REPORTING
    report_generator = ReportGenerator(locale=request.locale)
    reports = {
        "summary": await report_generator.generate_summary_report(new_profile),
        "audit": await report_generator.generate_audit_report(new_profile, audit_ctx),
        "investigation": await report_generator.generate_investigation_report(new_profile)
    }

    # Apply locale-specific redactions
    redactor = LocaleRedactor(locale=request.locale)
    reports = {k: await redactor.redact(v) for k, v in reports.items()}

    # PHASE 9: AUDIT CLOSURE
    log_audit_event(audit_ctx, "screening_complete",
                   profile_id=new_profile.profile_id,
                   total_cost=sum(ds.cost_incurred for ds in acquired_data.values()),
                   findings_count=len(investigation_result.all_findings),
                   sources_accessed=list(acquired_data.keys()))

    finalize_audit_log(audit_ctx)

    return ScreeningResult(
        profile=new_profile,
        reports=reports,
        audit_id=audit_ctx.audit_id,
        total_cost=sum(ds.cost_incurred for ds in acquired_data.values())
    )
```

### Data Acquisition Flow (Detail)

```python
# Pseudo-code for data acquisition orchestration

async def acquire_data_for_checks(ctx: DataAcquisitionContext) -> dict[CheckType, CachedDataSource]:
    """
    Acquire data for all allowed checks, using cache where possible.

    Execution strategy:
    - High-priority checks (sanctions/PEP): sequential, blocking
    - Standard checks: parallel, non-blocking
    - Stale data handling: tier-aware policy
    """

    results = {}
    tasks = []

    # Partition checks by priority
    high_priority = [c for c in ctx.allowed_checks if c in HIGH_PRIORITY_CHECKS]
    standard_priority = [c for c in ctx.allowed_checks if c not in HIGH_PRIORITY_CHECKS]

    # PHASE 1: High-priority checks (sequential, must succeed)
    for check_type in high_priority:
        log_audit_event(ctx.audit_ctx, "check_started", check_type=check_type)

        try:
            result = await acquire_single_check(
                entity=ctx.entity,
                check_type=check_type,
                service_tier=ctx.service_tier,
                tenant_id=ctx.tenant_id,
                audit_ctx=ctx.audit_ctx
            )
            results[check_type] = result

            log_audit_event(ctx.audit_ctx, "check_completed",
                          check_type=check_type,
                          freshness=result.freshness_status,
                          cost=result.cost_incurred)
        except ProviderError as e:
            log_audit_event(ctx.audit_ctx, "check_failed",
                          check_type=check_type, error=str(e))
            # High-priority failures block the entire screening
            raise

    # PHASE 2: Standard checks (parallel, best-effort)
    for check_type in standard_priority:
        task = asyncio.create_task(
            acquire_single_check(
                entity=ctx.entity,
                check_type=check_type,
                service_tier=ctx.service_tier,
                tenant_id=ctx.tenant_id,
                audit_ctx=ctx.audit_ctx
            )
        )
        tasks.append((check_type, task))

    # Wait for all tasks, continue on individual failures
    for check_type, task in tasks:
        try:
            result = await task
            results[check_type] = result

            log_audit_event(ctx.audit_ctx, "check_completed",
                          check_type=check_type,
                          freshness=result.freshness_status,
                          cost=result.cost_incurred)
        except ProviderError as e:
            log_audit_event(ctx.audit_ctx, "check_failed",
                          check_type=check_type, error=str(e))
            # Standard check failures don't block; we proceed with available data
            continue

    return results


async def acquire_single_check(
    entity: Entity,
    check_type: CheckType,
    service_tier: ServiceTier,
    tenant_id: UUID,
    audit_ctx: AuditContext
) -> CachedDataSource:
    """
    Acquire data for a single check type, using cache-first strategy.
    """

    # STEP 1: Query cache
    cache = DataSourceCache()
    cached = await cache.get(
        entity_id=entity.entity_id,
        check_type=check_type
    )

    if cached:
        log_audit_event(audit_ctx, "cache_hit",
                       check_type=check_type,
                       freshness=cached.freshness_status,
                       age_hours=(datetime.utcnow() - cached.acquired_at).total_seconds() / 3600)

        # STEP 2: Check freshness
        if cached.freshness_status == FreshnessStatus.FRESH:
            # Use as-is
            return cached

        elif cached.freshness_status == FreshnessStatus.STALE:
            # Apply tier-aware policy
            stale_policy = STALE_POLICY_MATRIX[check_type][service_tier]

            if stale_policy == StaleAction.USE_AND_FLAG:
                # Use stale data, queue async refresh
                log_audit_event(audit_ctx, "using_stale_data",
                              check_type=check_type,
                              policy="use_and_flag")

                # Queue background refresh (don't wait)
                asyncio.create_task(refresh_cache_async(entity, check_type))

                return cached

            elif stale_policy == StaleAction.BLOCK_AND_REFRESH:
                # Fall through to provider query
                log_audit_event(audit_ctx, "stale_data_blocked",
                              check_type=check_type,
                              policy="block_and_refresh")
                pass

        elif cached.freshness_status == FreshnessStatus.EXPIRED:
            # Must refresh
            log_audit_event(audit_ctx, "expired_data",
                          check_type=check_type)
            pass

    else:
        log_audit_event(audit_ctx, "cache_miss", check_type=check_type)

    # STEP 3: Query provider
    provider = get_provider_for_check_type(check_type)

    log_audit_event(audit_ctx, "querying_provider",
                   check_type=check_type,
                   provider=provider.provider_id)

    try:
        raw_response = await provider.query(
            entity=entity,
            check_type=check_type
        )
    except ProviderError as e:
        log_audit_event(audit_ctx, "provider_error",
                       check_type=check_type,
                       provider=provider.provider_id,
                       error=str(e))
        raise

    # STEP 4: Normalize and cache result
    normalized_data = provider.normalize_response(raw_response)

    freshness_config = FRESHNESS_WINDOWS[check_type]
    fresh_until = datetime.utcnow() + freshness_config.freshness_window
    stale_until = datetime.utcnow() + freshness_config.stale_window

    cached_result = CachedDataSource(
        cache_id=uuid4(),
        entity_id=entity.entity_id,
        provider_id=provider.provider_id,
        check_type=check_type,
        data_origin=DataOrigin.PAID_EXTERNAL,  # vs CUSTOMER_PROVIDED
        customer_id=None,  # Shared cache
        acquired_at=datetime.utcnow(),
        freshness_status=FreshnessStatus.FRESH,
        fresh_until=fresh_until,
        stale_until=stale_until,
        raw_response=encrypt(raw_response),
        normalized_data=normalized_data,
        cost_incurred=provider.cost_per_query,
        cost_currency="USD"
    )

    await cache.store(cached_result)

    log_audit_event(audit_ctx, "provider_query_complete",
                   check_type=check_type,
                   cost=cached_result.cost_incurred,
                   records_returned=len(normalized_data.get("records", [])))

    return cached_result
```

## Request Context Propagation

All operations in the system carry **immutable request context** that flows through every layer, ensuring compliance enforcement and audit trail integrity.

### Context Structure

```python
class RequestContext(BaseModel):
    """
    Immutable context attached to every request.
    Propagates through all layers to enforce compliance and enable auditing.
    """

    # IDENTITY
    request_id: UUID              # Unique request identifier
    tenant_id: UUID               # Customer organization
    actor_id: str                 # User/service performing action
    actor_type: ActorType         # human | service | system

    # LOCALE & COMPLIANCE
    locale: str                   # ISO 3166-1 alpha-2 (e.g., "US", "GB", "DE")
    compliance_rules: ComplianceRuleset  # Pre-computed ruleset for locale
    permitted_checks: set[CheckType]     # Filtered checks for this locale
    permitted_sources: set[str]          # Provider IDs allowed in this locale

    # CONSENT
    consent_token: str            # Reference to stored consent record
    consent_scope: ConsentScope   # What data types are permitted
    consent_expiry: datetime      # When consent expires

    # SERVICE PARAMETERS
    service_tier: ServiceTier     # standard | enhanced
    investigation_degree: InvestigationDegree  # D1 | D2 | D3

    # AUDIT TRAIL
    audit_id: UUID                # Links to audit log record
    initiated_at: datetime        # Request start time
    correlation_id: UUID | None   # For linking related requests

    # COST TRACKING
    budget_limit: Decimal | None  # Max cost for this request
    cost_accumulated: Decimal     # Running total (updated during execution)

    # CACHE ISOLATION
    cache_scope: CacheScope       # shared | tenant_isolated

    def assert_check_permitted(self, check_type: CheckType) -> None:
        """Raise ComplianceError if check not permitted in this context."""
        if check_type not in self.permitted_checks:
            raise ComplianceError(
                f"Check {check_type} not permitted for locale {self.locale}"
            )

    def assert_source_permitted(self, provider_id: str) -> None:
        """Raise ComplianceError if provider not permitted in this context."""
        if provider_id not in self.permitted_sources:
            raise ComplianceError(
                f"Provider {provider_id} not permitted for locale {self.locale}"
            )

    def assert_budget_available(self, cost: Decimal) -> None:
        """Raise BudgetExceededError if cost would exceed budget."""
        if self.budget_limit:
            if self.cost_accumulated + cost > self.budget_limit:
                raise BudgetExceededError(
                    f"Cost {cost} would exceed budget limit {self.budget_limit}"
                )

    def record_cost(self, cost: Decimal) -> None:
        """Increment accumulated cost (called after successful provider query)."""
        self.cost_accumulated += cost
```

### Context Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                   REQUEST CONTEXT FLOW                           │
│                                                                  │
│  API Gateway                                                    │
│       │                                                          │
│       ├─ Extract auth token, tenant_id, locale from request     │
│       ├─ Load compliance rules for locale                       │
│       ├─ Validate consent token                                 │
│       ├─ Create RequestContext (immutable)                      │
│       │                                                          │
│       ▼                                                          │
│  Screening Service                                              │
│       │                                                          │
│       ├─ Pass context to entity resolver                        │
│       ├─ Pass context to data acquisition layer                 │
│       ├─ Pass context to investigation workflow                 │
│       │                                                          │
│       ▼                                                          │
│  Entity Resolver                                                │
│       │                                                          │
│       ├─ Use ctx.tenant_id for cache isolation                  │
│       ├─ Log to ctx.audit_id                                    │
│       │                                                          │
│       ▼                                                          │
│  Data Acquisition                                               │
│       │                                                          │
│       ├─ ctx.assert_check_permitted(check_type)                 │
│       ├─ ctx.assert_source_permitted(provider_id)               │
│       ├─ ctx.assert_budget_available(cost)                      │
│       ├─ Query provider                                         │
│       ├─ ctx.record_cost(actual_cost)                           │
│       ├─ Log to ctx.audit_id                                    │
│       │                                                          │
│       ▼                                                          │
│  LangGraph Workflow (Investigation)                             │
│       │                                                          │
│       ├─ Context in workflow state                              │
│       ├─ Each node validates against ctx.permitted_checks       │
│       ├─ Each AI model call logs to ctx.audit_id               │
│       ├─ Recursive calls inherit context                        │
│       │                                                          │
│       ▼                                                          │
│  Risk Analyzer                                                  │
│       │                                                          │
│       ├─ Use ctx.locale for jurisdiction-specific risk weights  │
│       ├─ Multi-model calls log to ctx.audit_id                  │
│       │                                                          │
│       ▼                                                          │
│  Report Generator                                               │
│       │                                                          │
│       ├─ Use ctx.locale for redaction rules (GDPR, etc.)        │
│       ├─ Use ctx.consent_scope to filter disclosed data         │
│       ├─ Apply locale-specific formatting                       │
│       │                                                          │
│       ▼                                                          │
│  Audit Logger                                                   │
│       │                                                          │
│       ├─ Finalize audit record at ctx.audit_id                  │
│       ├─ Include ctx.cost_accumulated, ctx.permitted_checks     │
│       ├─ Store complete request/response trail                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Context Enforcement Points

Every layer validates context before proceeding:

```python
# Example: Data acquisition layer

async def query_provider(
    entity: Entity,
    check_type: CheckType,
    provider: Provider,
    ctx: RequestContext  # ← Context flows through
) -> ProviderResponse:
    """
    Query external provider with compliance enforcement.
    """

    # ENFORCEMENT POINT 1: Check type permitted?
    ctx.assert_check_permitted(check_type)

    # ENFORCEMENT POINT 2: Provider permitted in this locale?
    ctx.assert_source_permitted(provider.provider_id)

    # ENFORCEMENT POINT 3: Budget available?
    ctx.assert_budget_available(provider.cost_per_query)

    # ENFORCEMENT POINT 4: Consent still valid?
    if datetime.utcnow() > ctx.consent_expiry:
        raise ConsentExpiredError("Consent expired")

    # Audit before action
    log_audit_event(
        audit_id=ctx.audit_id,
        event_type="provider_query_initiated",
        provider=provider.provider_id,
        check_type=check_type,
        entity_id=entity.entity_id
    )

    try:
        # Execute query
        response = await provider.query(entity)

        # Update cost tracking
        ctx.record_cost(provider.cost_per_query)

        # Audit success
        log_audit_event(
            audit_id=ctx.audit_id,
            event_type="provider_query_completed",
            provider=provider.provider_id,
            cost=provider.cost_per_query,
            records_returned=len(response.records)
        )

        return response

    except ProviderError as e:
        # Audit failure
        log_audit_event(
            audit_id=ctx.audit_id,
            event_type="provider_query_failed",
            provider=provider.provider_id,
            error=str(e)
        )
        raise
```

### Multi-Tenant Context Isolation

Context ensures tenant data isolation:

```python
# Cache queries automatically filter by tenant

async def get_cached_data(
    entity_id: UUID,
    check_type: CheckType,
    ctx: RequestContext
) -> CachedDataSource | None:
    """
    Retrieve cached data with automatic tenant isolation.
    """

    # Build query with tenant filter
    query = (
        select(CachedDataSource)
        .where(CachedDataSource.entity_id == entity_id)
        .where(CachedDataSource.check_type == check_type)
    )

    # TENANT ISOLATION:
    # - Shared cache: accessible to all tenants
    # - Customer-provided cache: filtered by tenant_id
    if ctx.cache_scope == CacheScope.TENANT_ISOLATED:
        query = query.where(CachedDataSource.customer_id == ctx.tenant_id)
    else:
        # Shared cache: only paid external sources
        query = query.where(CachedDataSource.data_origin == DataOrigin.PAID_EXTERNAL)

    result = await db.execute(query)
    return result.scalar_one_or_none()
```

### Context in LangGraph Workflows

Context is embedded in workflow state:

```python
class InvestigationState(TypedDict):
    """LangGraph workflow state."""

    # Context (immutable, flows through entire graph)
    request_context: RequestContext

    # Working data (mutable, updated by nodes)
    subject_entity: Entity
    discovered_entities: list[Entity]
    findings: list[Finding]
    entity_graph: EntityGraph
    current_depth: int

    # Metadata
    iteration_count: int
    last_node: str


# Workflow nodes validate against context

async def search_node(state: InvestigationState) -> InvestigationState:
    """Search for new information based on current findings."""

    ctx = state["request_context"]

    # Check if we've exceeded degree limit
    max_depth = DEGREE_TO_MAX_DEPTH[ctx.investigation_degree]
    if state["current_depth"] >= max_depth:
        return state  # Stop recursion

    # Determine next checks to run based on findings
    next_checks = determine_next_checks(state["findings"])

    # Filter by permitted checks (compliance enforcement)
    permitted_next_checks = [c for c in next_checks if c in ctx.permitted_checks]

    # Execute checks
    new_data = await acquire_data_for_checks(
        entities=state["discovered_entities"],
        checks=permitted_next_checks,
        ctx=ctx  # ← Context flows to data layer
    )

    # Update state
    state["findings"].extend(new_data.findings)
    state["iteration_count"] += 1

    return state
```

## Entity Data Lake

Centralized storage for all discovered entities with cached provider data.

```
┌─────────────────────────────────────────────────────────────────┐
│                      ENTITY DATA LAKE                            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    ENTITY REGISTRY                       │    │
│  │                                                          │    │
│  │  All entities (subjects + discovered connections):      │    │
│  │  - Individuals (employees, candidates, associates)      │    │
│  │  - Organizations (employers, business entities)         │    │
│  │  - Addresses (residences, business locations)           │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  DATA SOURCE CACHE                       │    │
│  │                                                          │    │
│  │  Per-entity, per-source cached results:                 │    │
│  │  - Raw provider response (encrypted)                    │    │
│  │  - Acquisition timestamp                                 │    │
│  │  - Freshness status (fresh | stale | expired)           │    │
│  │  - Cost incurred                                         │    │
│  │  - Source provider                                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                 CROSS-SCREENING INDEX                    │    │
│  │                                                          │    │
│  │  Links entities across screenings:                       │    │
│  │  - Employee A → Company X (employer)                    │    │
│  │  - Employee B → Company X (employer) ← SHARED           │    │
│  │  - Employee C → Person D (household)                    │    │
│  │  - Employee E → Person D (business partner) ← SHARED    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Cache Sharing Model

Data caching strategy based on data origin:

| Data Origin | Cache Scope | Rationale |
|-------------|-------------|-----------|
| **Paid external providers** | Platform-wide (shared) | Cost already incurred; maximize ROI |
| **Customer-provided data** | Customer-isolated | Proprietary; competitive sensitivity |

```
┌─────────────────────────────────────────────────────────────────┐
│                      CACHE ARCHITECTURE                          │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SHARED CACHE (Platform-wide)               │    │
│  │                                                          │    │
│  │  Paid external sources - shared across all customers:   │    │
│  │  - Court records (PACER, state courts)                  │    │
│  │  - Corporate registries                                  │    │
│  │  - Sanctions/PEP lists                                   │    │
│  │  - Credit bureaus                                        │    │
│  │  - Data brokers (Acxiom, etc.)                          │    │
│  │  - OSINT providers                                       │    │
│  │  - All paid API responses                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │         CUSTOMER-ISOLATED CACHE (per tenant)            │    │
│  │                                                          │    │
│  │  Customer-provided data - isolated per customer:        │    │
│  │  - Employee records from HRIS                           │    │
│  │  - Internal verification results                        │    │
│  │  - Customer-specific reference checks                   │    │
│  │  - Proprietary risk assessments                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Freshness Model

Different data types age at different rates:

| Data Category | Freshness Window | Stale Window | Rationale |
|---------------|------------------|--------------|-----------|
| Sanctions/PEP | 0 (always refresh) | N/A | Regulatory requirement |
| Criminal records | 7 days | 30 days | Court batch updates |
| Adverse media | 24 hours | 7 days | Time-sensitive |
| Civil litigation | 14 days | 60 days | Less time-sensitive |
| Credit/Financial | 30 days | 90 days | Monthly cycles |
| Corporate registry | 30 days | 90 days | Quarterly filings |
| OSINT/Digital | 30 days | 90 days | Online presence evolves |
| Employment verification | 90 days | 180 days | Stable data |
| Behavioral/Data broker | 90 days | 180 days | Patterns change slowly |
| Education | 365 days | Never expires | Rarely changes |

**Freshness States:**
```
┌──────────┐   (freshness_window)   ┌──────────┐   (stale_window)   ┌──────────┐
│  FRESH   │ ─────────────────────► │  STALE   │ ─────────────────► │ EXPIRED  │
│          │                        │          │                     │          │
│ Use as-is│                        │ Use with │                     │ Must     │
│          │                        │ flag     │                     │ refresh  │
└──────────┘                        └──────────┘                     └──────────┘
```

## Stale Data Policy (Tier-Aware)

When data is stale, behavior varies by check type and service tier:

```
┌─────────────────────────────────────────────────────────────────┐
│                    STALE DATA POLICY MATRIX                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Check Type              │ Standard Tier    │ Enhanced Tier     │
│  ────────────────────────┼──────────────────┼─────────────────  │
│  Sanctions/PEP           │ BLOCK (refresh)  │ BLOCK (refresh)   │
│  Criminal records        │ Use + flag       │ BLOCK (refresh)   │
│  Adverse media           │ Use + flag       │ BLOCK (refresh)   │
│  Civil litigation        │ Use + flag       │ Use + flag        │
│  Credit/Financial        │ Use + flag       │ Use + flag        │
│  Employment verification │ Use + flag       │ Use + flag        │
│  Education               │ Use + flag       │ Use + flag        │
│  Corporate registry      │ Use + flag       │ Use + flag        │
│  Behavioral/Data broker  │ N/A              │ Use + flag        │
│  OSINT/Digital footprint │ N/A              │ Use + flag        │
│                                                                  │
│  BLOCK    = Wait for fresh data before proceeding               │
│  Use+flag = Proceed with stale data, flag in report,            │
│             queue async refresh                                  │
│                                                                  │
│  All policies configurable at platform level                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Acquisition Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         DATA ACQUISITION FLOW                             │
│                                                                           │
│  Screening Request                                                        │
│       │                                                                   │
│       ▼                                                                   │
│  ┌─────────────────┐                                                     │
│  │ Resolve Entity  │ (see Entity Resolution in 06-data-sources.md)       │
│  │ (find or create)│                                                     │
│  └────────┬────────┘                                                     │
│           │                                                               │
│           ▼                                                               │
│  ┌─────────────────┐     ┌───────────────┐     ┌───────────────┐        │
│  │ Check Cache for │────►│    FRESH?     │────►│  Use cached   │        │
│  │ required checks │     │               │ Yes │  data         │        │
│  └─────────────────┘     └───────┬───────┘     └───────────────┘        │
│                                  │ No                                     │
│                                  ▼                                        │
│                          ┌───────────────┐     ┌───────────────┐        │
│                          │    STALE?     │────►│ Check policy  │        │
│                          │               │ Yes │ (tier-aware)  │        │
│                          └───────┬───────┘     └───────┬───────┘        │
│                                  │ No                  │                 │
│                                  ▼                     ▼                 │
│                          ┌───────────────┐     ┌───────────────┐        │
│                          │   EXPIRED /   │     │ Use + flag OR │        │
│                          │   MISSING     │     │ Block + wait  │        │
│                          └───────┬───────┘     └───────────────┘        │
│                                  │                                        │
│                                  ▼                                        │
│                          ┌───────────────┐                               │
│                          │ Query Provider│                               │
│                          │ + Cache Result│                               │
│                          │ + Track Cost  │                               │
│                          └───────────────┘                               │
│                                                                           │
└──────────────────────────────────────────────────────────────────────────┘
```

## Versioned Entity Profiles

Each screening iteration creates an immutable profile snapshot:

```
┌─────────────────────────────────────────────────────────────────┐
│                    ENTITY PROFILE STORE                          │
│                                                                  │
│  Entity: John Smith (employee_12345)                            │
│  ├── Profile v1 (2024-01-15) ─ Pre-employment screening        │
│  │   ├── Findings snapshot                                      │
│  │   ├── Risk score: 0.15 (low)                                │
│  │   ├── Connections: 12 entities                              │
│  │   └── Data sources used: [list]                             │
│  │                                                               │
│  ├── Profile v2 (2024-07-15) ─ 6-month monitoring              │
│  │   ├── Findings snapshot                                      │
│  │   ├── Risk score: 0.22 (low) ↑                              │
│  │   ├── Connections: 18 entities (+6)                         │
│  │   ├── Delta from v1: New civil judgment discovered          │
│  │   └── Data sources used: [list]                             │
│  │                                                               │
│  └── Profile v3 (2025-01-15) ─ Annual re-screen                │
│      ├── Findings snapshot                                      │
│      ├── Risk score: 0.45 (medium) ↑↑                          │
│      ├── Connections: 35 entities (+17)                        │
│      ├── Delta from v2: 3 new shell companies detected         │
│      ├── Evolution signals: [network_expansion_rapid]          │
│      └── Data sources used: [list]                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Risk Evolution Analytics

Pattern detection across profile versions to identify emerging risks.

```
┌─────────────────────────────────────────────────────────────────┐
│                  RISK EVOLUTION ANALYZER                         │
│                                                                  │
│  PHASE 1: RULE-BASED SIGNATURES (Initial Implementation)       │
│  ─────────────────────────────────────────────────────────      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              TEMPORAL PATTERN DETECTOR                   │    │
│  │                                                          │    │
│  │  Analyzes profile version deltas for:                   │    │
│  │                                                          │    │
│  │  NETWORK EVOLUTION                                       │    │
│  │  - Rapid network expansion (>200% in 6mo = shell co.)   │    │
│  │  - New high-risk connections appearing                  │    │
│  │  - Connections to newly-sanctioned entities             │    │
│  │  - Network clustering changes                           │    │
│  │                                                          │    │
│  │  FINANCIAL TRAJECTORY                                    │    │
│  │  - Progressive credit deterioration                     │    │
│  │  - Accumulating judgments/liens                         │    │
│  │  - Lifestyle inflation (behavioral data)               │    │
│  │  - New undisclosed business interests                   │    │
│  │                                                          │    │
│  │  BEHAVIORAL DRIFT                                        │    │
│  │  - Employment instability pattern                        │    │
│  │  - Geographic mobility anomalies                        │    │
│  │  - Digital footprint changes                            │    │
│  │                                                          │    │
│  │  LEGAL ESCALATION                                        │    │
│  │  - Civil → Criminal progression                         │    │
│  │  - Increasing litigation frequency                      │    │
│  │  - Regulatory action accumulation                       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              SIGNATURE LIBRARY                           │    │
│  │                                                          │    │
│  │  Known risk evolution patterns (rule-based):            │    │
│  │  - "Insider threat trajectory"                          │    │
│  │  - "Financial distress cascade"                         │    │
│  │  - "Shell company buildup"                              │    │
│  │  - "Influence network construction"                     │    │
│  │  - "Identity fragmentation"                             │    │
│  │                                                          │    │
│  │  Analyst feedback loop: confirm/reject signals          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  PHASE 2: ML AUGMENTATION (Future, when data accumulates)      │
│  ─────────────────────────────────────────────────────────      │
│  - Training data from confirmed Phase 1 signals                │
│  - Anomaly detection for unknown patterns                      │
│  - Pattern discovery from historical profiles                  │
│  - Human-in-the-loop validation                                │
│                                                                  │
│  Prerequisites:                                                 │
│  - Sufficient profile version history                          │
│  - Labeled outcomes (confirmed risks, false positives)         │
│  - Analyst feedback corpus                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Data Retention Policy

| Data Class | Default Retention | Configurable | Notes |
|------------|-------------------|--------------|-------|
| Profile versions | Indefinite | Yes | Core analytical value |
| Findings/analysis | Indefinite | Yes | Core analytical value |
| Connection graphs | Indefinite | Yes | Core analytical value |
| Raw provider responses | 1 year | Yes | Minimize storage |
| Behavioral data | 2 years | Yes | Privacy consideration |
| Audit logs | 7 years | No | Compliance requirement |

## GDPR Erasure Capability

```
┌─────────────────────────────────────────────────────────────────┐
│                    GDPR ERASURE PROCESS                          │
│                                                                  │
│  Triggered by:                                                  │
│  - Subject erasure request (Art. 17)                           │
│  - Locale-based automatic policy (EU subjects)                 │
│  - Customer-initiated purge                                    │
│                                                                  │
│  Process:                                                       │
│  1. Validate request (identity, legal basis)                   │
│  2. Identify all entity references across system               │
│  3. For each data class:                                       │
│     - Delete OR anonymize (configurable)                       │
│     - Anonymization preserves aggregate analytics              │
│  4. Cascade through:                                           │
│     - Entity registry                                          │
│     - Profile versions                                         │
│     - Cached provider data                                     │
│     - Connection graphs (remove or anonymize edges)            │
│  5. Create audit record of erasure (retained for compliance)   │
│  6. Notify dependent systems                                   │
│                                                                  │
│  Exceptions (retained per legal requirement):                  │
│  - Audit logs (anonymized subject reference)                   │
│  - Aggregated/anonymized analytics                             │
│  - Legal hold data                                             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Core Data Models

```python
class Entity(BaseModel):
    """Core entity in the system."""
    entity_id: UUID
    entity_type: EntityType  # individual | organization | address
    canonical_identifiers: dict[str, str]  # SSN, EIN, passport, etc.
    created_at: datetime

    # Cross-reference tracking
    screenings: list[UUID]  # Screenings referencing this entity
    related_entities: list[EntityRelation]


class CachedDataSource(BaseModel):
    """Cached data from a provider for an entity."""
    cache_id: UUID
    entity_id: UUID
    provider_id: str
    check_type: CheckType

    # Origin (determines sharing scope)
    data_origin: DataOrigin  # paid_external | customer_provided
    customer_id: UUID | None  # Set if customer_provided

    # Freshness
    acquired_at: datetime
    freshness_status: FreshnessStatus  # fresh | stale | expired
    fresh_until: datetime
    stale_until: datetime

    # Data
    raw_response: bytes  # Encrypted
    normalized_data: dict

    # Cost tracking
    cost_incurred: Decimal
    cost_currency: str


class EntityProfile(BaseModel):
    """Versioned profile snapshot for an entity."""
    profile_id: UUID
    entity_id: UUID
    version: int
    created_at: datetime

    # Trigger
    trigger_type: ProfileTrigger  # screening | monitoring | manual
    trigger_id: UUID  # Reference to screening/monitoring run

    # Snapshot
    findings: list[Finding]
    risk_score: RiskScore
    connections: list[EntityConnection]
    connection_count: int

    # Sources used
    data_sources_used: list[DataSourceRef]
    stale_data_used: list[DataSourceRef]  # Flagged stale sources

    # Comparison to previous
    previous_version: int | None
    delta: ProfileDelta | None


class ProfileDelta(BaseModel):
    """Changes between profile versions."""
    new_findings: list[Finding]
    resolved_findings: list[Finding]
    changed_findings: list[FindingChange]

    risk_score_change: float
    connection_count_change: int
    new_connections: list[EntityConnection]
    lost_connections: list[EntityConnection]

    # Computed signals
    evolution_signals: list[EvolutionSignal]


class EvolutionSignal(BaseModel):
    """Detected pattern in profile evolution."""
    signal_type: str  # e.g., "network_expansion", "financial_deterioration"
    confidence: float
    severity: str  # low | medium | high | critical
    description: str
    contributing_factors: list[str]
    pattern_signature: str | None  # Reference to known pattern library

    # Analyst feedback (for ML training)
    analyst_confirmed: bool | None
    feedback_timestamp: datetime | None


class DataOrigin(str, Enum):
    PAID_EXTERNAL = "paid_external"      # Shared cache
    CUSTOMER_PROVIDED = "customer_provided"  # Isolated cache


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    EXPIRED = "expired"
```

## Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Language | Python 3.14 | Async support, AI/ML ecosystem |
| Orchestration | LangGraph | Stateful workflows, conditional routing |
| AI Models | Claude, GPT-4, Gemini | Multi-model redundancy |
| API Framework | FastAPI | Async, OpenAPI, validation |
| Database | PostgreSQL | ACID, JSON support, mature |
| Cache | Redis | Session state, rate limiting |
| Background Jobs | ARQ / Dramatiq | Async job processing (Redis-backed) |
| Scheduler | APScheduler | In-process vigilance scheduling |
| Secrets | Environment / Vault | Secure credential management |
| Observability | OpenTelemetry + Prometheus | Tracing, metrics |
| Logging | structlog | Structured audit logs |

---

*See [06-data-sources.md](06-data-sources.md) for provider integration details*
*See [10-platform.md](10-platform.md) for deployment and scaling*
