"""Screening service for end-to-end background screening workflow.

This package provides the screening orchestration layer that coordinates
all phases of a background screening investigation:

1. Request validation
2. Compliance checking
3. Consent verification
4. Investigation (SAR loop)
5. Risk analysis
6. Report generation

Usage:
    from elile.screening import (
        ScreeningOrchestrator,
        ScreeningRequest,
        ScreeningResult,
        ScreeningStatus,
    )

    # Create request
    request = ScreeningRequest(
        tenant_id=tenant_id,
        subject=SubjectIdentifiers(name="John Smith"),
        locale=Locale.US,
        consent_token="consent-abc123",
    )

    # Execute screening
    orchestrator = ScreeningOrchestrator()
    result = await orchestrator.execute_screening(request)

    if result.status == ScreeningStatus.COMPLETE:
        print(f"Risk score: {result.risk_score}")
"""

from elile.screening.cost_estimator import (
    BulkCostEstimate,
    CostBreakdown,
    CostCategory,
    CostComparison,
    CostEstimate,
    CostEstimator,
    EstimatorConfig,
    create_cost_estimator,
    get_cost_estimator,
    reset_cost_estimator,
)
from elile.screening.degree_handlers import (
    D1Handler,
    D1Result,
    D2Handler,
    D2Result,
    D3Handler,
    D3Result,
    DegreeHandlerConfig,
    create_d1_handler,
    create_d2_handler,
    create_d3_handler,
)
from elile.screening.index import (
    ConnectionStrength,
    ConnectionType,
    CrossScreeningIndex,
    CrossScreeningIndexError,
    CrossScreeningResult,
    EntityReference,
    IndexConfig,
    IndexingError,
    IndexStatistics,
    NetworkEdge,
    NetworkGraph,
    NetworkNode,
    ScreeningEntity,
    ScreeningNotIndexedError,
    SubjectConnection,
    SubjectNotFoundError,
    create_index,
    get_cross_screening_index,
)
from elile.screening.orchestrator import (
    OrchestratorConfig,
    ScreeningOrchestrator,
    create_screening_orchestrator,
)
from elile.screening.progress import (
    ETAEstimate,
    HistoricalDuration,
    PhaseProgress,
    ProgressNotification,
    ProgressNotificationType,
    ProgressStep,
    ProgressTracker,
    ProgressTrackerConfig,
    ScreeningProgress,
    StallReason,
    create_progress_tracker,
    get_progress_tracker,
    reset_progress_tracker,
)
from elile.screening.queue import (
    DequeueResult,
    InMemoryQueueStorage,
    QueueConfig,
    QueuedScreening,
    QueueMetrics,
    QueueStatus,
    QueueStorage,
    RedisQueueStorage,
    ScreeningQueueManager,
    WorkerStatus,
    create_queue_manager,
    create_queue_manager_async,
)
from elile.screening.result_compiler import (
    CategorySummary,
    CompiledResult,
    CompilerConfig,
    ConnectionSummary,
    FindingsSummary,
    InvestigationSummary,
    ResultCompiler,
    SARSummary,
    SummaryFormat,
    create_result_compiler,
)
from elile.screening.state_manager import (
    InMemoryStateStore,
    ProgressEvent,
    ProgressEventType,
    ScreeningPhase,
    ScreeningState,
    ScreeningStateManager,
    StateManagerConfig,
    StateStore,
    create_state_manager,
)
from elile.screening.tier_router import (
    DataSourceSpec,
    DataSourceTier,
    RoutingResult,
    TierCapabilities,
    TierRouter,
    TierRouterConfig,
    create_default_data_sources,
    create_tier_router,
)
from elile.screening.types import (
    GeneratedReport,
    ReportType,
    ScreeningComplianceError,
    ScreeningCostSummary,
    ScreeningError,
    ScreeningExecutionError,
    ScreeningPhaseResult,
    ScreeningPriority,
    ScreeningRequest,
    ScreeningRequestCreate,
    ScreeningResult,
    ScreeningStatus,
    ScreeningValidationError,
)

__all__ = [
    # Orchestrator
    "ScreeningOrchestrator",
    "create_screening_orchestrator",
    "OrchestratorConfig",
    # Degree Handlers
    "D1Handler",
    "D1Result",
    "D2Handler",
    "D2Result",
    "D3Handler",
    "D3Result",
    "DegreeHandlerConfig",
    "create_d1_handler",
    "create_d2_handler",
    "create_d3_handler",
    # Tier Router
    "TierRouter",
    "TierRouterConfig",
    "TierCapabilities",
    "DataSourceSpec",
    "DataSourceTier",
    "RoutingResult",
    "create_tier_router",
    "create_default_data_sources",
    # State Manager
    "ScreeningStateManager",
    "StateManagerConfig",
    "ScreeningState",
    "ScreeningPhase",
    "ProgressEvent",
    "ProgressEventType",
    "StateStore",
    "InMemoryStateStore",
    "create_state_manager",
    # Result Compiler
    "ResultCompiler",
    "CompilerConfig",
    "CompiledResult",
    "FindingsSummary",
    "CategorySummary",
    "InvestigationSummary",
    "SARSummary",
    "ConnectionSummary",
    "SummaryFormat",
    "create_result_compiler",
    # Request/Response models
    "ScreeningRequest",
    "ScreeningRequestCreate",
    "ScreeningResult",
    "ScreeningPhaseResult",
    "ScreeningCostSummary",
    "GeneratedReport",
    # Enums
    "ScreeningStatus",
    "ReportType",
    "ScreeningPriority",
    # Errors
    "ScreeningError",
    "ScreeningValidationError",
    "ScreeningComplianceError",
    "ScreeningExecutionError",
    # Cross-Screening Index
    "CrossScreeningIndex",
    "create_index",
    "get_cross_screening_index",
    "IndexConfig",
    "IndexStatistics",
    "ConnectionStrength",
    "ConnectionType",
    "CrossScreeningResult",
    "EntityReference",
    "NetworkEdge",
    "NetworkGraph",
    "NetworkNode",
    "ScreeningEntity",
    "SubjectConnection",
    "CrossScreeningIndexError",
    "IndexingError",
    "ScreeningNotIndexedError",
    "SubjectNotFoundError",
    # Queue Manager
    "ScreeningQueueManager",
    "QueueConfig",
    "QueuedScreening",
    "QueueMetrics",
    "QueueStatus",
    "WorkerStatus",
    "DequeueResult",
    "QueueStorage",
    "InMemoryQueueStorage",
    "RedisQueueStorage",
    "create_queue_manager",
    "create_queue_manager_async",
    # Cost Estimator
    "CostEstimator",
    "CostEstimate",
    "CostBreakdown",
    "CostCategory",
    "CostComparison",
    "BulkCostEstimate",
    "EstimatorConfig",
    "create_cost_estimator",
    "get_cost_estimator",
    "reset_cost_estimator",
    # Progress Tracker
    "ProgressTracker",
    "ProgressTrackerConfig",
    "ScreeningProgress",
    "ProgressStep",
    "PhaseProgress",
    "ETAEstimate",
    "ProgressNotification",
    "ProgressNotificationType",
    "StallReason",
    "HistoricalDuration",
    "create_progress_tracker",
    "get_progress_tracker",
    "reset_progress_tracker",
]
