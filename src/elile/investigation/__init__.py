"""Investigation module for SAR (Search-Assess-Refine) loop orchestration.

This module provides the core investigation engine that implements the
iterative Search-Assess-Refine loop for each information type during
background screening investigations.

Key Components:
    - SARStateMachine: Orchestrates the SAR loop lifecycle
    - SARConfig: Configuration for thresholds and limits
    - SARTypeState: Tracks state for each information type
    - SARIterationState: Tracks state for each iteration
    - QueryPlanner: Generates search queries with cross-type enrichment
    - SearchQuery: Represents a single query to execute
    - QueryExecutor: Executes search queries against data providers
    - QueryResult: Result from query execution

Example:
    ```python
    from elile.investigation import (
        SARStateMachine,
        SARConfig,
        SARPhase,
        CompletionReason,
        QueryPlanner,
        SearchQuery,
    )
    from elile.agent.state import InformationType, KnowledgeBase

    # Create state machine with custom config
    config = SARConfig(
        confidence_threshold=0.85,
        max_iterations_per_type=3,
        min_gain_threshold=0.1,
    )
    machine = SARStateMachine(config)

    # Create query planner
    planner = QueryPlanner()

    # Initialize and run SAR loop
    machine.initialize_type(InformationType.IDENTITY)
    iteration = machine.start_iteration(InformationType.IDENTITY)

    # Plan queries for this iteration
    kb = KnowledgeBase()
    result = planner.plan_queries(
        info_type=InformationType.IDENTITY,
        knowledge_base=kb,
        iteration_number=1,
        gaps=[],
        locale=Locale.US,
        tier=ServiceTier.STANDARD,
        available_providers=["sterling"],
        subject_name="John Smith",
    )

    # ... execute queries, assess results ...

    # Complete iteration
    should_continue = machine.complete_iteration(
        InformationType.IDENTITY,
        iteration
    )
    ```
"""

from elile.investigation.models import (
    CompletionReason,
    SARConfig,
    SARIterationState,
    SARPhase,
    SARSummary,
    SARTypeState,
)
from elile.investigation.query_executor import (
    ExecutionSummary,
    ExecutorConfig,
    QueryExecutor,
    QueryResult,
    QueryStatus,
    create_query_executor,
)
from elile.investigation.query_planner import (
    INFO_TYPE_TO_CHECK_TYPES,
    QueryPlanner,
    QueryPlanResult,
    QueryType,
    SearchQuery,
)
from elile.investigation.sar_machine import (
    FOUNDATION_TYPES,
    SARStateMachine,
    create_sar_machine,
)

__all__ = [
    # State machine
    "SARStateMachine",
    "create_sar_machine",
    # Configuration
    "SARConfig",
    # State models
    "SARTypeState",
    "SARIterationState",
    "SARSummary",
    # Enums
    "SARPhase",
    "CompletionReason",
    # Constants
    "FOUNDATION_TYPES",
    # Query planner
    "QueryPlanner",
    "QueryPlanResult",
    "SearchQuery",
    "QueryType",
    "INFO_TYPE_TO_CHECK_TYPES",
    # Query executor
    "QueryExecutor",
    "create_query_executor",
    "QueryResult",
    "QueryStatus",
    "ExecutorConfig",
    "ExecutionSummary",
]
