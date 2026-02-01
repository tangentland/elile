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
    - ResultAssessor: Assesses results and extracts findings
    - AssessmentResult: Complete assessment with confidence and gaps

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
from elile.investigation.information_type_manager import (
    PHASE_ORDER,
    PHASE_TYPES,
    TYPE_DEPENDENCIES,
    InformationPhase,
    InformationTypeManager,
    TypeDependency,
    TypeSequence,
    create_information_type_manager,
)
from elile.investigation.query_refiner import (
    QueryRefiner,
    RefinerConfig,
    RefinementResult,
    create_query_refiner,
)
from elile.investigation.confidence_scorer import (
    ConfidenceScore,
    ConfidenceScorer,
    FactorBreakdown,
    ScorerConfig,
    create_confidence_scorer,
    DEFAULT_EXPECTED_FACTS,
)
from elile.investigation.result_assessor import (
    AssessmentResult,
    ConfidenceFactors,
    DetectedInconsistency,
    DiscoveredEntity,
    Fact,
    Gap,
    ResultAssessor,
    create_result_assessor,
)
from elile.investigation.sar_machine import (
    FOUNDATION_TYPES,
    SARStateMachine,
    create_sar_machine,
)
from elile.investigation.iteration_controller import (
    ControllerConfig,
    DecisionType,
    IterationController,
    IterationDecision,
    create_iteration_controller,
)
from elile.investigation.sar_orchestrator import (
    InvestigationResult,
    OrchestratorConfig,
    OrchestratorPhase,
    ProgressEvent,
    SARLoopOrchestrator,
    TypeCycleResult,
    create_sar_orchestrator,
)
from elile.investigation.checkpoint import (
    CheckpointConfig,
    CheckpointData,
    CheckpointManager,
    CheckpointReason,
    CheckpointStatus,
    CheckpointStorage,
    InMemoryCheckpointStorage,
    ResumeResult,
    ResumeStrategy,
    create_checkpoint_manager,
)

__all__ = [
    # State machine
    "SARStateMachine",
    "create_sar_machine",
    # Iteration controller
    "IterationController",
    "create_iteration_controller",
    "IterationDecision",
    "DecisionType",
    "ControllerConfig",
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
    # SAR orchestrator
    "SARLoopOrchestrator",
    "create_sar_orchestrator",
    "InvestigationResult",
    "TypeCycleResult",
    "OrchestratorConfig",
    "OrchestratorPhase",
    "ProgressEvent",
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
    # Result assessor
    "ResultAssessor",
    "create_result_assessor",
    "AssessmentResult",
    "ConfidenceFactors",
    "Fact",
    "Gap",
    "DetectedInconsistency",
    "DiscoveredEntity",
    # Query refiner
    "QueryRefiner",
    "create_query_refiner",
    "RefinerConfig",
    "RefinementResult",
    # Information type manager
    "InformationTypeManager",
    "create_information_type_manager",
    "InformationPhase",
    "TypeDependency",
    "TypeSequence",
    "PHASE_ORDER",
    "PHASE_TYPES",
    "TYPE_DEPENDENCIES",
    # Confidence scorer
    "ConfidenceScorer",
    "create_confidence_scorer",
    "ConfidenceScore",
    "ScorerConfig",
    "FactorBreakdown",
    "DEFAULT_EXPECTED_FACTS",
    # Checkpoint manager
    "CheckpointManager",
    "create_checkpoint_manager",
    "CheckpointData",
    "CheckpointConfig",
    "CheckpointReason",
    "CheckpointStatus",
    "CheckpointStorage",
    "InMemoryCheckpointStorage",
    "ResumeResult",
    "ResumeStrategy",
]
