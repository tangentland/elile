# Task 5.9: SAR Loop Orchestrator

## Overview

Implement the main SAR loop orchestrator that coordinates all SAR components (state machine, planner, executor, assessor, refiner) to execute complete Search-Assess-Refine cycles for each information type.

**Priority**: P0 | **Effort**: 3 days | **Status**: Not Started

## Dependencies

- Task 5.1-5.8: All SAR components
- Task 1.2: Audit Logging

## Implementation Checklist

- [ ] Create SARLoopOrchestrator coordinating all components
- [ ] Implement complete SAR cycle execution
- [ ] Build error handling and recovery
- [ ] Add progress tracking
- [ ] Create orchestration state persistence
- [ ] Write comprehensive orchestrator tests

## Key Implementation

```python
# src/elile/investigation/sar_orchestrator.py
class SARLoopOrchestrator:
    """Orchestrates complete SAR loop cycles."""

    def __init__(
        self,
        state_machine: SARStateMachine,
        query_planner: QueryPlanner,
        query_executor: QueryExecutor,
        result_assessor: ResultAssessor,
        query_refiner: QueryRefiner,
        iteration_controller: IterationController,
        type_manager: InformationTypeManager,
        audit_logger: AuditLogger
    ):
        self.state = state_machine
        self.planner = query_planner
        self.executor = query_executor
        self.assessor = result_assessor
        self.refiner = query_refiner
        self.controller = iteration_controller
        self.types = type_manager
        self.audit = audit_logger

    async def execute_sar_cycle(
        self,
        info_type: InformationType,
        knowledge_base: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier,
        ctx: RequestContext
    ) -> SARTypeState:
        """
        Execute complete SAR cycle for information type.

        Args:
            info_type: Information type to process
            knowledge_base: Accumulated knowledge
            locale: Subject locale
            tier: Service tier
            ctx: Request context

        Returns:
            Completed type state
        """
        # Initialize type state
        type_state = self.state.initialize_type(info_type)

        iteration_number = 1
        gaps = []

        while True:
            # SEARCH Phase
            self.state.transition_phase(type_state, SARPhase.SEARCH)

            queries = await self.planner.plan_queries(
                info_type,
                knowledge_base,
                iteration_number,
                gaps,
                locale,
                tier
            )

            # Execute queries
            results = await self.executor.execute_queries(queries, ctx)

            # ASSESS Phase
            self.state.transition_phase(type_state, SARPhase.ASSESS)

            assessment = await self.assessor.assess_results(
                info_type, results, iteration_number, ctx
            )

            # Create iteration state
            iteration_state = SARIterationState(
                iteration_number=iteration_number,
                queries_generated=len(queries),
                results_found=len(results),
                facts_extracted=len(assessment.facts_extracted),
                new_facts_this_iteration=assessment.new_facts_count,
                confidence_score=assessment.confidence_score,
                gaps_identified=assessment.gaps_identified,
                info_gain_rate=assessment.info_gain_rate
            )

            # Decide if we should continue
            decision = self.controller.should_continue_iteration(
                info_type, iteration_state, type_state
            )

            # Complete iteration
            self.state.complete_iteration(type_state, iteration_state)

            if not decision.should_continue:
                # Mark complete
                self.state.transition_phase(
                    type_state,
                    decision.next_phase,
                    decision.reason
                )
                break

            # REFINE Phase - prepare for next iteration
            self.state.transition_phase(type_state, SARPhase.REFINE)

            gaps = assessment.gaps_identified
            iteration_number += 1

        return type_state

    async def execute_all_types(
        self,
        knowledge_base: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier,
        role_category: RoleCategory,
        ctx: RequestContext
    ) -> dict[InformationType, SARTypeState]:
        """
        Execute SAR cycles for all permitted types in dependency order.

        Args:
            knowledge_base: Knowledge base (updated during execution)
            locale: Subject locale
            tier: Service tier
            role_category: Role category
            ctx: Request context

        Returns:
            Dict of completed type states
        """
        completed_states = {}
        completed_types = []

        while True:
            # Get next types to process
            next_types = self.types.get_next_types(
                completed_types, tier, locale, role_category
            )

            if not next_types:
                # All types complete
                break

            # Process types in parallel (within same phase)
            type_states = await gather(*[
                self.execute_sar_cycle(
                    info_type, knowledge_base, locale, tier, ctx
                )
                for info_type in next_types
            ])

            # Record completed states
            for info_type, state in zip(next_types, type_states):
                completed_states[info_type] = state
                completed_types.append(info_type)

        return completed_states
```

## Testing Requirements

### Unit Tests
- Single type SAR cycle
- Multi-iteration cycle
- Error handling during phases
- State persistence across iterations

### Integration Tests
- Complete SAR cycle
- Multi-type sequential processing
- Phase dependency enforcement
- Knowledge base updates

**Coverage Target**: 90%+

## Acceptance Criteria

- [ ] SARLoopOrchestrator coordinates all components
- [ ] Complete SAR cycles execute for each type
- [ ] Types process in dependency order
- [ ] Knowledge base updates between types
- [ ] Error recovery at each phase
- [ ] Complete audit trail

## Deliverables

- `src/elile/investigation/sar_orchestrator.py`
- `tests/unit/test_sar_orchestrator.py`
- `tests/integration/test_complete_sar_cycle.py`

## References

- Architecture: [05-investigation.md](../../docs/architecture/05-investigation.md) - SAR Loop

---

*Task Owner: [TBD]* | *Created: 2026-01-30*
