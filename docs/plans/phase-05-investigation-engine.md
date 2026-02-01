# Phase 5: Investigation Engine (SAR Loop)

## Overview

Phase 5 implements the Search-Assess-Refine (SAR) loop for stateful workflow orchestration. This is the core AI-powered investigation engine that iteratively discovers entities, analyzes findings, and determines next search steps.

**Duration Estimate**: 4-5 weeks
**Team Size**: 3-4 developers (AI/ML expertise required)
**Risk Level**: High (complex orchestration, AI model integration)
**Status**: ✅ Complete (16/16 tasks complete)
**Last Updated**: 2026-01-31

## Phase Goals

- ✅ Build SAR state machine for loop orchestration
- ✅ Implement query planner with type-specific templates
- ✅ Create result assessor for finding extraction
- ✅ Build finding extractor with AI integration
- ✅ Implement phase handlers (Foundation, Records, Intelligence, Network, Reconciliation)
- ✅ Implement investigation resume capability

## Tasks

| Seq | Task Name | Priority | Status | Dependencies | Key Files |
|-----|-----------|----------|--------|--------------|-----------|
| 5.1 | SAR State Machine | P0 | ✅ Complete | Phase 4 | `investigation/sar_machine.py`, `investigation/models.py` |
| 5.2 | Query Planner | P0 | ✅ Complete | 5.1 | `investigation/query_planner.py` |
| 5.3 | Query Executor | P0 | ✅ Complete | 4.6, 5.2 | `investigation/query_executor.py` |
| 5.4 | Result Assessor | P0 | ✅ Complete | 5.3, 5.1 | `investigation/result_assessor.py` |
| 5.5 | Query Refiner | P0 | ✅ Complete | 5.4, 5.2 | `investigation/query_refiner.py` |
| 5.6 | Information Type Manager | P0 | ✅ Complete | 5.1, 2.1 | `investigation/information_type_manager.py` |
| 5.7 | Confidence Scorer | P0 | ✅ Complete | 5.4, 5.1 | `investigation/confidence_scorer.py` |
| 5.8 | Iteration Controller | P0 | ✅ Complete | 5.1, 5.7 | `investigation/iteration_controller.py` |
| 5.9 | SAR Loop Orchestrator | P0 | ✅ Complete | 5.1-5.8 | `investigation/sar_orchestrator.py` |
| 5.10 | Finding Extractor | P0 | ✅ Complete | 5.4 | `investigation/finding_extractor.py` |
| 5.11 | Foundation Phase Handler | P1 | ✅ Complete | 5.9 | `investigation/phases/foundation.py` |
| 5.12 | Records Phase Handler | P1 | ✅ Complete | 5.11 | `investigation/phases/records.py` |
| 5.13 | Intelligence Phase Handler | P1 | ✅ Complete | 5.12 | `investigation/phases/intelligence.py` |
| 5.14 | Network Phase Handler | P1 | ✅ Complete | 5.13 | `investigation/phases/network.py` |
| 5.15 | Reconciliation Phase Handler | P1 | ✅ Complete | 5.14 | `investigation/phases/reconciliation.py` |
| 5.16 | Investigation Resume | P1 | ✅ Complete | 5.9 | `investigation/checkpoint.py` |

## Key Patterns

### SAR Loop Flow
```python
# SAR loop executed per information type
async def execute_sar_cycle(info_type: InformationType):
    while True:
        # SEARCH: Generate and execute queries
        queries = planner.plan_queries(info_type, knowledge_base, gaps)
        results = await executor.execute_queries(queries)

        # ASSESS: Analyze results and extract facts
        assessment = assessor.assess_results(info_type, results)

        # REFINE: Determine if iteration should continue
        decision = controller.should_continue_iteration(info_type, iteration)
        if not decision.should_continue:
            break

        # Prepare for next iteration
        gaps = assessment.gaps_identified
```

### Phase Processing
```python
# Foundation: Sequential processing (identity → employment → education)
for info_type in [IDENTITY, EMPLOYMENT, EDUCATION]:
    result = await orchestrator.execute_sar_cycle(info_type)
    update_baseline(result)

# Records: Parallel processing
results = await gather(*[
    orchestrator.execute_sar_cycle(info_type)
    for info_type in [CRIMINAL, CIVIL, FINANCIAL, LICENSES, REGULATORY, SANCTIONS]
])
```

## Implementation Summary

### Completed Components (16/16 tasks) ✅
- **SAR State Machine**: State tracking, phase transitions, completion detection
- **Query Planner**: Type-specific query generation, gap-targeted queries
- **Query Executor**: Async batch execution with provider integration
- **Result Assessor**: Fact extraction, gap identification, confidence calculation
- **Query Refiner**: Gap-targeted query generation with strategies
- **Information Type Manager**: Dependency-aware type sequencing
- **Confidence Scorer**: Weighted multi-factor confidence calculation
- **Iteration Controller**: Loop termination decisions (threshold, capped, diminished)
- **SAR Orchestrator**: Complete SAR cycle coordination
- **Finding Extractor**: AI-powered finding extraction with rule-based fallback
- **Foundation Phase**: Sequential identity/employment/education processing
- **Records Phase**: Parallel criminal/civil/financial/licenses/regulatory/sanctions
- **Intelligence Phase**: Parallel adverse media/digital footprint with tier filtering
- **Network Phase**: Sequential D2/D3 relationship analysis with risk detection
- **Reconciliation Phase**: Cross-source deduplication, conflict resolution, deception analysis
- **Investigation Resume**: State persistence, checkpointing, and resume capability

## Test Coverage

| Component | Unit Tests | Integration Tests |
|-----------|------------|------------------|
| SAR State Machine | 43 | 11 |
| Query Planner | 24 | - |
| Query Executor | 26 | - |
| Result Assessor | 32 | - |
| Query Refiner | 29 | - |
| Information Type Manager | 43 | - |
| Confidence Scorer | 54 | - |
| Iteration Controller | 46 | - |
| SAR Orchestrator | 27 | 6 |
| Finding Extractor | 35 | - |
| Foundation Phase | 38 | - |
| Records Phase | 48 | - |
| Intelligence Phase | 41 | - |
| Network Phase | 43 | - |
| Reconciliation Phase | 41 | - |
| Checkpoint Manager | 42 | - |
| **Total** | **612** | **17** |

## Phase Acceptance Criteria

### Functional Requirements
- [x] SAR workflow executes all phases
- [x] Query planner creates type-specific queries
- [x] Result assessor extracts facts and identifies gaps
- [x] Confidence scorer calculates multi-factor scores
- [x] Iteration controller handles loop termination
- [x] Phase handlers process types correctly

### Performance Requirements
- [x] SAR loop terminates properly (confidence threshold, max iterations, diminishing returns)
- [x] Parallel processing for Records phase types
- [x] Sequential processing for Foundation phase types

### Testing Requirements
- [x] 612+ unit tests for all components
- [x] Integration tests for SAR cycle
- [x] Edge case: No queries generated
- [x] Edge case: Max iterations reached
- [x] Edge case: Foundation phase failure blocks Records
- [x] Edge case: Deception pattern detection
- [x] Edge case: Checkpoint resume and recovery

---

*Last Updated: 2026-01-31*
