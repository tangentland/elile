# Task 5.2: Query Planner - Implementation Plan

## Overview

Implements an intelligent query planner that generates search queries for each information type using accumulated knowledge from the KnowledgeBase. Performs cross-type query enrichment using facts from completed types.

## Requirements

1. QueryPlanner class with `plan_queries()` method
2. SearchQuery dataclass with query specification
3. QueryPlanResult for planning outcomes
4. QueryType enum for query categorization
5. Cross-type enrichment using KnowledgeBase
6. Type-specific query generation
7. Query deduplication
8. Tier-aware filtering

## Files Created

### `src/elile/investigation/query_planner.py`
- **QueryType** enum: INITIAL, ENRICHED, GAP_FILL, REFINEMENT
- **SearchQuery** dataclass with:
  - `query_id`: UUIDv7 identifier
  - `provider_id`: Target provider
  - `check_type`: CheckType enum value
  - `search_params`: Provider-specific parameters
  - `priority`: 1=high, 2=medium, 3=low
  - `query_type`: QueryType enum value
  - `parent_query_id`: For refinement chains
  - `expected_info_types`: What info this query may return
- **QueryPlanResult** dataclass with:
  - `queries`: List of SearchQuery
  - `enrichment_sources`: List of InformationType used
  - `skipped_reason`: Why no queries if empty
- **INFO_TYPE_TO_CHECK_TYPES** mapping: Maps InformationType to list of CheckType
- **QueryPlanner** class with:
  - `plan_queries()`: Main planning method
  - `_generate_initial_queries()`: First iteration queries
  - `_generate_enriched_queries()`: Queries using cross-type facts
  - `_generate_gap_fill_queries()`: Queries targeting knowledge gaps
  - `_generate_refinement_queries()`: Follow-up queries
  - Type-specific generators for each InformationType

### `tests/unit/test_query_planner.py`
- 24 unit tests covering:
  - SearchQuery creation and serialization
  - QueryPlanResult properties
  - Identity queries with various inputs
  - Criminal queries with cross-type enrichment
  - Employment queries with identity enrichment
  - Adverse media queries using all knowledge
  - Sanctions queries (no enrichment needed)
  - Refinement queries targeting gaps
  - Query deduplication
  - Tier filtering (Standard vs Enhanced)
  - Network queries using discovered entities
  - INFO_TYPE_TO_CHECK_TYPES mapping coverage

## Key Patterns

### Cross-Type Enrichment
The planner uses facts from completed information types to enrich later queries:
- Criminal queries: Add counties from known addresses
- Employment queries: Add name variants from identity verification
- Adverse media queries: Use all known entities and locations
- Network queries: Use discovered associated entities

### Query Deduplication
Queries are deduplicated by (provider_id, check_type) pair to avoid redundant API calls.

### Tier-Aware Filtering
- Standard tier: Only CORE provider checks
- Enhanced tier: CORE and PREMIUM provider checks

## Test Results

All 24 unit tests passing:
```
tests/unit/test_query_planner.py::TestSearchQuery::test_query_creation PASSED
tests/unit/test_query_planner.py::TestSearchQuery::test_query_to_dict PASSED
tests/unit/test_query_planner.py::TestQueryPlanResult::test_result_properties PASSED
tests/unit/test_query_planner.py::TestQueryPlanResult::test_empty_result PASSED
tests/unit/test_query_planner.py::TestIdentityQueries::test_identity_queries_with_name_only PASSED
tests/unit/test_query_planner.py::TestIdentityQueries::test_identity_queries_with_full_info PASSED
tests/unit/test_query_planner.py::TestIdentityQueries::test_no_queries_without_name PASSED
tests/unit/test_query_planner.py::TestCriminalQueries::test_criminal_queries_enriched_with_counties PASSED
tests/unit/test_query_planner.py::TestCriminalQueries::test_criminal_queries_include_name_variants PASSED
tests/unit/test_query_planner.py::TestEmploymentQueries::test_employment_queries_enriched_with_identity PASSED
tests/unit/test_query_planner.py::TestEmploymentQueries::test_employment_queries_include_employers_to_verify PASSED
tests/unit/test_query_planner.py::TestAdverseMediaQueries::test_adverse_media_uses_all_knowledge PASSED
tests/unit/test_query_planner.py::TestSanctionsQueries::test_sanctions_queries_no_enrichment_needed PASSED
tests/unit/test_query_planner.py::TestRefinementQueries::test_refinement_queries_target_gaps PASSED
tests/unit/test_query_planner.py::TestRefinementQueries::test_refinement_queries_high_priority PASSED
tests/unit/test_query_planner.py::TestQueryDeduplication::test_duplicate_queries_removed PASSED
tests/unit/test_query_planner.py::TestTierFiltering::test_standard_tier_excludes_enhanced_checks PASSED
tests/unit/test_query_planner.py::TestTierFiltering::test_enhanced_tier_includes_all_checks PASSED
tests/unit/test_query_planner.py::TestNetworkQueries::test_network_queries_use_discovered_entities PASSED
tests/unit/test_query_planner.py::TestInfoTypeToCheckTypeMapping::test_all_info_types_have_mapping PASSED
tests/unit/test_query_planner.py::TestInfoTypeToCheckTypeMapping::test_identity_maps_to_identity_checks PASSED
tests/unit/test_query_planner.py::TestInfoTypeToCheckTypeMapping::test_criminal_maps_to_criminal_checks PASSED
tests/unit/test_query_planner.py::TestInfoTypeToCheckTypeMapping::test_reconciliation_has_no_checks PASSED
tests/unit/test_query_planner.py::TestQueryLimiting::test_queries_limited_to_max PASSED
```

## Dependencies

- Task 5.1: SAR State Machine (for SARConfig and iteration context)
- Task 2.1: Locale and CheckType definitions
- `elile.agent.state`: InformationType, KnowledgeBase
- `elile.compliance.types`: Locale, CheckType
- `elile.providers.types`: ServiceTier

## API Example

```python
from elile.investigation import QueryPlanner, SearchQuery, QueryPlanResult
from elile.agent.state import InformationType, KnowledgeBase
from elile.compliance.types import Locale
from elile.providers.types import ServiceTier

planner = QueryPlanner()
kb = KnowledgeBase()

# Add facts from completed identity verification
kb.add_fact(InformationType.IDENTITY, "name_variant", "John Q. Smith")
kb.add_fact(InformationType.IDENTITY, "county", "Los Angeles County")

# Plan criminal queries enriched with identity facts
result = planner.plan_queries(
    info_type=InformationType.CRIMINAL,
    knowledge_base=kb,
    iteration_number=1,
    gaps=[],
    locale=Locale.US,
    tier=ServiceTier.STANDARD,
    available_providers=["sterling", "checkr"],
    subject_name="John Smith",
)

# Result contains enriched queries
for query in result.queries:
    print(f"{query.check_type}: {query.search_params}")
    # Criminal queries will include:
    # - name_variants: ["John Q. Smith"]
    # - counties: ["Los Angeles County"]
```

## Completion Date

2026-01-31
