# Task 5.3: Query Executor - Implementation Plan

## Overview

Implements the query execution layer that bridges the investigation domain (SearchQuery, QueryResult) with the provider infrastructure (RequestRouter, RoutedRequest, RoutedResult). Handles batch execution, result collection, and maintains execution statistics for the SAR loop.

## Requirements

1. QueryExecutor class with async `execute_queries()` method
2. QueryResult dataclass for execution outcomes
3. QueryStatus enum for status tracking
4. ExecutionSummary for batch statistics
5. ExecutorConfig for concurrency and batch size
6. Integration with existing RequestRouter
7. Priority-based query sorting
8. SearchQuery to RoutedRequest conversion

## Design Decisions

### Integration with RequestRouter

Rather than reimplementing retry, rate limiting, circuit breaker, and caching logic, the QueryExecutor integrates with the existing `RequestRouter` from Task 4.6. This provides:

- Retry with exponential backoff
- Rate limiting per provider
- Circuit breaker protection
- Response caching
- Cost tracking
- Fallback provider selection

### Domain Bridging

The QueryExecutor converts between investigation domain objects and provider domain objects:

| Investigation Domain | Provider Domain |
|---------------------|-----------------|
| `SearchQuery` | `RoutedRequest` |
| `QueryResult` | `RoutedResult` |
| `search_params` dict | `SubjectIdentifiers` |

### Batch Execution

Queries are executed in configurable batches through the RequestRouter's `route_batch()` method, which handles parallelism internally. Priority sorting ensures high-priority queries execute first.

## Files Created

### `src/elile/investigation/query_executor.py`
- **QueryStatus** enum: SUCCESS, FAILED, TIMEOUT, RATE_LIMITED, NO_PROVIDER, SKIPPED
- **QueryResult** dataclass with:
  - `query_id`: UUID from SearchQuery
  - `provider_id`: Provider that executed the query
  - `check_type`: String value of CheckType
  - `status`: QueryStatus enum
  - `normalized_data`: Dict of extracted data
  - `findings_count`: Number of records/matches found
  - `duration_ms`: Execution time
  - `cache_hit`: Whether result was cached
  - `error_message`: Error description if failed
- **ExecutionSummary** dataclass with:
  - Counts by status (successful, failed, timed_out, rate_limited, no_provider, skipped)
  - `cache_hits`: Number of cached results
  - `providers_used`: Set of providers
  - `success_rate`: Percentage calculation
- **ExecutorConfig** Pydantic model with:
  - `max_concurrent_queries`: Concurrency limit (default 10)
  - `batch_size`: Queries per batch (default 10)
  - `process_by_priority`: Sort by priority (default True)
  - `routing_config`: Pass-through to RequestRouter
- **QueryExecutor** class with:
  - `execute_queries()`: Batch execution with summary
  - `execute_single()`: Single query convenience method
  - `_to_routed_request()`: Convert SearchQuery to RoutedRequest
  - `_build_subject_identifiers()`: Map search_params to SubjectIdentifiers
  - `_to_query_result()`: Convert RoutedResult to QueryResult
  - `_sort_queries()`: Priority-based sorting

### `tests/unit/test_query_executor.py`
- 26 unit tests covering:
  - QueryResult creation and properties
  - ExecutionSummary statistics
  - ExecutorConfig defaults and customization
  - Empty query list handling
  - Successful query execution
  - Failed query execution
  - Timeout handling
  - Rate limiting handling
  - Cache hit tracking
  - No provider available handling
  - Batch execution with multiple queries
  - Priority sorting
  - Subject identifier mapping
  - Factory function

## Key Patterns

### Status Mapping

Maps RoutedResult failure reasons to QueryStatus:

| FailureReason | QueryStatus |
|---------------|-------------|
| `NO_PROVIDER` | `NO_PROVIDER` |
| `TIMEOUT` | `TIMEOUT` |
| `ALL_RATE_LIMITED` | `RATE_LIMITED` |
| Other | `FAILED` |

### Findings Extraction

Counts findings from normalized_data by checking for common keys:
- `records`
- `results`
- `matches`
- `findings`
- `items`

### Subject Identifier Mapping

Maps search_params keys to SubjectIdentifiers fields:
- `full_name` / `name` → `full_name`
- `first_name` → `first_name`
- `date_of_birth` / `dob` → `date_of_birth`
- `street_address` / `address` → `street_address`
- `postal_code` / `zip_code` → `postal_code`
- Direct mappings for SSN, EIN, email, phone, etc.

## Test Results

All 26 unit tests passing:
```
tests/unit/test_query_executor.py::TestQueryResult::test_result_creation PASSED
tests/unit/test_query_executor.py::TestQueryResult::test_failed_result PASSED
tests/unit/test_query_executor.py::TestQueryResult::test_result_without_data PASSED
tests/unit/test_query_executor.py::TestExecutionSummary::test_empty_summary PASSED
tests/unit/test_query_executor.py::TestExecutionSummary::test_update_from_success PASSED
tests/unit/test_query_executor.py::TestExecutionSummary::test_update_from_failure PASSED
tests/unit/test_query_executor.py::TestExecutionSummary::test_update_from_timeout PASSED
tests/unit/test_query_executor.py::TestExecutionSummary::test_update_from_rate_limited PASSED
tests/unit/test_query_executor.py::TestExecutionSummary::test_success_rate_calculation PASSED
tests/unit/test_query_executor.py::TestExecutorConfig::test_default_config PASSED
tests/unit/test_query_executor.py::TestExecutorConfig::test_custom_config PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_empty_queries PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_single_query_success PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_single_query_failure PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_no_provider PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_timeout PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_rate_limited PASSED
tests/unit/test_query_executor.py::TestQueryExecutor::test_execute_with_cache_hit PASSED
tests/unit/test_query_executor.py::TestBatchExecution::test_execute_multiple_queries PASSED
tests/unit/test_query_executor.py::TestBatchExecution::test_priority_sorting PASSED
tests/unit/test_query_executor.py::TestSubjectIdentifierMapping::test_full_subject_mapping PASSED
tests/unit/test_query_executor.py::TestExecuteSingle::test_execute_single_success PASSED
tests/unit/test_query_executor.py::TestFactoryFunction::test_create_executor PASSED
tests/unit/test_query_executor.py::TestFactoryFunction::test_create_executor_with_config PASSED
tests/unit/test_query_executor.py::TestFindingsCount::test_findings_from_records PASSED
tests/unit/test_query_executor.py::TestFindingsCount::test_findings_from_matches PASSED
```

## Dependencies

- Task 4.1: Provider Registry (ProviderRegistry)
- Task 4.2: Provider Health (CircuitBreakerRegistry)
- Task 4.6: Request Routing (RequestRouter, RoutedRequest, RoutedResult)
- Task 5.2: Query Planner (SearchQuery)
- `elile.agent.state`: ServiceTier
- `elile.entity.types`: SubjectIdentifiers
- `elile.compliance.types`: Locale, CheckType

## API Example

```python
from elile.investigation import (
    QueryExecutor,
    QueryPlanner,
    QueryResult,
    ExecutionSummary,
    create_query_executor,
)
from elile.providers.router import RequestRouter, RoutingConfig

# Set up executor with router
router = RequestRouter(
    registry=provider_registry,
    cache=cache_service,
    rate_limiter=rate_limit_registry,
    circuit_registry=circuit_breakers,
    cost_service=cost_service,
    config=RoutingConfig(max_retries=3, timeout=30.0),
)
executor = create_query_executor(router=router)

# Plan and execute queries
planner = QueryPlanner()
plan_result = planner.plan_queries(
    info_type=InformationType.CRIMINAL,
    knowledge_base=kb,
    iteration_number=1,
    gaps=[],
    locale=Locale.US,
    tier=ServiceTier.STANDARD,
    available_providers=["sterling", "checkr"],
    subject_name="John Smith",
)

# Execute planned queries
results, summary = await executor.execute_queries(
    queries=plan_result.queries,
    entity_id=subject_entity_id,
    tenant_id=tenant_id,
    locale=Locale.US,
)

# Process results for SAR loop
for result in results:
    if result.is_success:
        kb.add_findings(InformationType.CRIMINAL, result.normalized_data)
        iteration.new_facts_this_iteration += result.findings_count
```

## Completion Date

2026-01-31
