"""SAR Loop Orchestrator for coordinating complete investigations.

This module provides the SARLoopOrchestrator that coordinates all SAR
components (state machine, planner, executor, assessor, refiner, controller)
to execute complete Search-Assess-Refine cycles for each information type.

The orchestrator:
1. Manages the complete SAR loop lifecycle for an investigation
2. Coordinates component interactions in correct sequence
3. Handles error recovery at each phase
4. Tracks progress through investigation
5. Supports checkpoint/resume for long-running investigations

Architecture Reference: docs/architecture/05-investigation.md
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID, uuid7

from pydantic import BaseModel, Field

from elile.agent.state import InformationType, KnowledgeBase, ServiceTier
from elile.compliance.types import Locale
from elile.core.logging import get_logger
from elile.investigation.information_type_manager import InformationTypeManager
from elile.investigation.iteration_controller import IterationController, IterationDecision
from elile.investigation.models import (
    CompletionReason,
    SARConfig,
    SARIterationState,
    SARPhase,
    SARSummary,
    SARTypeState,
)
from elile.investigation.query_executor import QueryResult
from elile.investigation.query_planner import QueryPlanner, SearchQuery
from elile.investigation.query_refiner import QueryRefiner, RefinementResult
from elile.investigation.result_assessor import AssessmentResult, Gap, ResultAssessor
from elile.investigation.sar_machine import SARStateMachine

if TYPE_CHECKING:
    from elile.core.audit import AuditLogger

logger = get_logger(__name__)


class OrchestratorPhase(str, Enum):
    """Phases in the orchestration lifecycle."""

    INITIALIZING = "initializing"
    PLANNING = "planning"
    EXECUTING = "executing"
    ASSESSING = "assessing"
    REFINING = "refining"
    COMPLETING = "completing"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class TypeCycleResult:
    """Result from completing a SAR cycle for a single type."""

    result_id: UUID = field(default_factory=uuid7)
    info_type: InformationType = InformationType.IDENTITY
    type_state: SARTypeState | None = None

    # Execution summary
    iterations_completed: int = 0
    total_queries_executed: int = 0
    total_facts_extracted: int = 0
    final_confidence: float = 0.0
    completion_reason: CompletionReason | None = None

    # Errors
    error_occurred: bool = False
    error_message: str | None = None
    error_phase: OrchestratorPhase | None = None

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "result_id": str(self.result_id),
            "info_type": self.info_type.value,
            "iterations_completed": self.iterations_completed,
            "total_queries_executed": self.total_queries_executed,
            "total_facts_extracted": self.total_facts_extracted,
            "final_confidence": self.final_confidence,
            "completion_reason": self.completion_reason.value if self.completion_reason else None,
            "error_occurred": self.error_occurred,
            "error_message": self.error_message,
            "error_phase": self.error_phase.value if self.error_phase else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


@dataclass
class InvestigationResult:
    """Complete result from an investigation run."""

    investigation_id: UUID = field(default_factory=uuid7)

    # Type results
    type_results: dict[InformationType, TypeCycleResult] = field(default_factory=dict)
    type_states: dict[InformationType, SARTypeState] = field(default_factory=dict)

    # Summary statistics
    types_completed: int = 0
    types_failed: int = 0
    types_skipped: int = 0
    total_iterations: int = 0
    total_queries: int = 0
    total_facts: int = 0

    # Aggregate metrics
    average_confidence: float = 0.0
    lowest_confidence: float = 0.0
    lowest_confidence_type: InformationType | None = None

    # Status
    is_complete: bool = False
    has_errors: bool = False

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    duration_ms: float = 0.0

    def add_type_result(self, result: TypeCycleResult) -> None:
        """Add a type result and update statistics."""
        self.type_results[result.info_type] = result

        if result.type_state:
            self.type_states[result.info_type] = result.type_state

        if result.error_occurred:
            self.types_failed += 1
            self.has_errors = True
        elif result.completion_reason == CompletionReason.SKIPPED:
            self.types_skipped += 1
        else:
            self.types_completed += 1

        self.total_iterations += result.iterations_completed
        self.total_queries += result.total_queries_executed
        self.total_facts += result.total_facts_extracted

        # Update confidence metrics
        self._update_confidence_metrics()

    def _update_confidence_metrics(self) -> None:
        """Update aggregate confidence metrics."""
        confidences = [
            r.final_confidence
            for r in self.type_results.values()
            if r.final_confidence > 0 and not r.error_occurred
        ]
        if confidences:
            self.average_confidence = sum(confidences) / len(confidences)
            self.lowest_confidence = min(confidences)

            for result in self.type_results.values():
                if result.final_confidence == self.lowest_confidence:
                    self.lowest_confidence_type = result.info_type
                    break

    def finalize(self) -> None:
        """Mark investigation as complete."""
        self.is_complete = True
        self.completed_at = datetime.now(UTC)
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "investigation_id": str(self.investigation_id),
            "type_results": {k.value: v.to_dict() for k, v in self.type_results.items()},
            "types_completed": self.types_completed,
            "types_failed": self.types_failed,
            "types_skipped": self.types_skipped,
            "total_iterations": self.total_iterations,
            "total_queries": self.total_queries,
            "total_facts": self.total_facts,
            "average_confidence": self.average_confidence,
            "lowest_confidence": self.lowest_confidence,
            "lowest_confidence_type": (
                self.lowest_confidence_type.value if self.lowest_confidence_type else None
            ),
            "is_complete": self.is_complete,
            "has_errors": self.has_errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
        }


@dataclass
class ProgressEvent:
    """Progress tracking event for investigation monitoring."""

    event_id: UUID = field(default_factory=uuid7)
    event_type: str = ""

    # Context
    info_type: InformationType | None = None
    phase: OrchestratorPhase | None = None
    iteration_number: int = 0

    # Progress
    message: str = ""
    progress_percent: float = 0.0

    # Timing
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "info_type": self.info_type.value if self.info_type else None,
            "phase": self.phase.value if self.phase else None,
            "iteration_number": self.iteration_number,
            "message": self.message,
            "progress_percent": self.progress_percent,
            "timestamp": self.timestamp.isoformat(),
        }


class OrchestratorConfig(BaseModel):
    """Configuration for SARLoopOrchestrator."""

    # Execution settings
    max_concurrent_types: int = Field(default=1, ge=1, le=10)
    enable_parallel_queries: bool = Field(default=True)

    # Error handling
    retry_failed_queries: bool = Field(default=True)
    max_retries_per_query: int = Field(default=3, ge=0, le=10)
    continue_on_type_error: bool = Field(default=True)

    # Progress tracking
    emit_progress_events: bool = Field(default=True)
    progress_interval_seconds: float = Field(default=5.0, ge=1.0, le=60.0)

    # SAR configuration
    sar_config: SARConfig = Field(default_factory=SARConfig)


# Type alias for progress callback
ProgressCallback = Callable[[ProgressEvent], None]


class SARLoopOrchestrator:
    """Orchestrates complete SAR loop cycles for investigations.

    The SARLoopOrchestrator coordinates all SAR components to execute
    complete Search-Assess-Refine cycles for each information type.
    It manages the investigation lifecycle from initialization through
    completion, handling errors and tracking progress.

    Components coordinated:
    - SARStateMachine: State management for each type
    - QueryPlanner: Generates search queries
    - QueryExecutor: Executes queries against providers
    - ResultAssessor: Assesses results and extracts findings
    - QueryRefiner: Generates refinement queries
    - IterationController: Controls iteration flow
    - InformationTypeManager: Manages type dependencies

    Example:
        ```python
        orchestrator = SARLoopOrchestrator(
            state_machine=state_machine,
            query_planner=planner,
            query_executor=executor,
            result_assessor=assessor,
            query_refiner=refiner,
            iteration_controller=controller,
            type_manager=type_manager,
        )

        result = await orchestrator.execute_investigation(
            subject_name="John Smith",
            knowledge_base=kb,
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
        )

        print(f"Completed {result.types_completed} types")
        print(f"Average confidence: {result.average_confidence:.2f}")
        ```
    """

    def __init__(
        self,
        state_machine: SARStateMachine | None = None,
        query_planner: QueryPlanner | None = None,
        query_executor: Any | None = None,  # QueryExecutor but avoid import cycle
        result_assessor: ResultAssessor | None = None,
        query_refiner: QueryRefiner | None = None,
        iteration_controller: IterationController | None = None,
        type_manager: InformationTypeManager | None = None,
        config: OrchestratorConfig | None = None,
        audit_logger: "AuditLogger | None" = None,
    ):
        """Initialize the orchestrator.

        Args:
            state_machine: SAR state machine. Created if not provided.
            query_planner: Query planner. Created if not provided.
            query_executor: Query executor. Created if not provided.
            result_assessor: Result assessor. Created if not provided.
            query_refiner: Query refiner. Created if not provided.
            iteration_controller: Iteration controller. Created if not provided.
            type_manager: Type manager. Created if not provided.
            config: Orchestrator configuration.
            audit_logger: Optional audit logger.
        """
        self.config = config or OrchestratorConfig()

        # Initialize components
        self.state = state_machine or SARStateMachine(config=self.config.sar_config)
        self.planner = query_planner or QueryPlanner()
        self.executor = query_executor
        self._assessor = result_assessor  # May be None, created per-execution with KB
        self.refiner = query_refiner or QueryRefiner()
        self.controller = iteration_controller or IterationController(config=self.config.sar_config)
        self.types = type_manager or InformationTypeManager()

        self.audit = audit_logger

        # Progress tracking
        self._progress_callbacks: list[ProgressCallback] = []
        self._current_phase: OrchestratorPhase = OrchestratorPhase.INITIALIZING

    @property
    def assessor(self) -> ResultAssessor | None:
        """Get the assessor, if one was provided at init."""
        return self._assessor

    def add_progress_callback(self, callback: ProgressCallback) -> None:
        """Add a callback for progress events."""
        self._progress_callbacks.append(callback)

    def remove_progress_callback(self, callback: ProgressCallback) -> None:
        """Remove a progress callback."""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)

    async def execute_investigation(
        self,
        subject_name: str,
        knowledge_base: KnowledgeBase | None = None,
        locale: Locale = Locale.US,
        tier: ServiceTier = ServiceTier.STANDARD,
        types_to_process: list[InformationType] | None = None,
    ) -> InvestigationResult:
        """Execute a complete investigation for a subject.

        Processes all enabled information types in dependency order,
        executing complete SAR cycles for each.

        Args:
            subject_name: Subject name for search queries.
            knowledge_base: Existing knowledge base. Created if not provided.
            locale: Subject locale for compliance.
            tier: Service tier for provider selection.
            types_to_process: Specific types to process. If None, all enabled types.

        Returns:
            InvestigationResult with all type results.
        """
        kb = knowledge_base or KnowledgeBase()
        result = InvestigationResult()

        self._emit_progress(
            "investigation_started",
            message=f"Starting investigation for {subject_name}",
            progress_percent=0.0,
        )

        try:
            # Get types to process in dependency order
            if types_to_process:
                types_sequence = types_to_process
            else:
                types_sequence = self.types.get_execution_order(tier, locale)

            total_types = len(types_sequence)

            # Process each type
            for idx, info_type in enumerate(types_sequence):
                progress_pct = (idx / total_types) * 100

                self._emit_progress(
                    "type_started",
                    info_type=info_type,
                    message=f"Processing {info_type.value}",
                    progress_percent=progress_pct,
                )

                try:
                    type_result = await self._execute_type_cycle(
                        info_type=info_type,
                        subject_name=subject_name,
                        knowledge_base=kb,
                        locale=locale,
                        tier=tier,
                    )
                    result.add_type_result(type_result)

                except Exception as e:
                    logger.error(
                        "Type cycle failed",
                        info_type=info_type.value,
                        error=str(e),
                    )
                    error_result = TypeCycleResult(
                        info_type=info_type,
                        error_occurred=True,
                        error_message=str(e),
                        error_phase=self._current_phase,
                    )
                    error_result.completed_at = datetime.now(UTC)
                    result.add_type_result(error_result)

                    if not self.config.continue_on_type_error:
                        raise

            result.finalize()

            self._emit_progress(
                "investigation_completed",
                message=f"Investigation complete: {result.types_completed} types",
                progress_percent=100.0,
            )

        except Exception as e:
            logger.error("Investigation failed", error=str(e))
            result.has_errors = True
            result.finalize()

        return result

    async def execute_single_type(
        self,
        info_type: InformationType,
        subject_name: str,
        knowledge_base: KnowledgeBase | None = None,
        locale: Locale = Locale.US,
        tier: ServiceTier = ServiceTier.STANDARD,
    ) -> TypeCycleResult:
        """Execute SAR cycle for a single information type.

        Args:
            info_type: Information type to process.
            subject_name: Subject name for search queries.
            knowledge_base: Existing knowledge base.
            locale: Subject locale.
            tier: Service tier.

        Returns:
            TypeCycleResult for the processed type.
        """
        kb = knowledge_base or KnowledgeBase()
        return await self._execute_type_cycle(
            info_type=info_type,
            subject_name=subject_name,
            knowledge_base=kb,
            locale=locale,
            tier=tier,
        )

    async def _execute_type_cycle(
        self,
        info_type: InformationType,
        subject_name: str,
        knowledge_base: KnowledgeBase,
        locale: Locale,
        tier: ServiceTier,
    ) -> TypeCycleResult:
        """Execute complete SAR cycle for an information type.

        Args:
            info_type: Information type to process.
            subject_name: Subject name.
            knowledge_base: Knowledge base (updated during execution).
            locale: Subject locale.
            tier: Service tier.

        Returns:
            TypeCycleResult with execution results.
        """
        result = TypeCycleResult(info_type=info_type)
        self._current_phase = OrchestratorPhase.INITIALIZING

        try:
            # Initialize type state
            type_state = self.state.initialize_type(info_type)
            result.type_state = type_state

            gaps: list[Gap] = []
            iteration_number = 0

            while True:
                iteration_number += 1

                # Start iteration
                iteration = type_state.start_iteration()

                # SEARCH Phase
                self._current_phase = OrchestratorPhase.PLANNING
                self._emit_progress(
                    "search_started",
                    info_type=info_type,
                    phase=OrchestratorPhase.PLANNING,
                    iteration_number=iteration_number,
                    message=f"Planning queries for {info_type.value} iteration {iteration_number}",
                )

                queries = await self._plan_queries(
                    info_type=info_type,
                    knowledge_base=knowledge_base,
                    iteration_number=iteration_number,
                    gaps=gaps,
                    locale=locale,
                    tier=tier,
                    subject_name=subject_name,
                )

                iteration.queries_generated = len(queries)

                # Execute queries
                self._current_phase = OrchestratorPhase.EXECUTING
                self._emit_progress(
                    "executing",
                    info_type=info_type,
                    phase=OrchestratorPhase.EXECUTING,
                    iteration_number=iteration_number,
                    message=f"Executing {len(queries)} queries",
                )

                query_results = await self._execute_queries(queries)
                iteration.queries_executed = len(query_results)
                iteration.queries_successful = sum(1 for r in query_results if r.is_success)

                # ASSESS Phase
                self._current_phase = OrchestratorPhase.ASSESSING
                self._emit_progress(
                    "assessing",
                    info_type=info_type,
                    phase=OrchestratorPhase.ASSESSING,
                    iteration_number=iteration_number,
                    message="Assessing results",
                )

                assessment = await self._assess_results(
                    info_type=info_type,
                    query_results=query_results,
                    iteration_number=iteration_number,
                    knowledge_base=knowledge_base,
                )

                # Update iteration state
                iteration.results_found = len(query_results)
                iteration.facts_extracted = len(assessment.facts_extracted)
                iteration.new_facts_this_iteration = assessment.new_facts_count
                iteration.confidence_score = assessment.confidence_score
                iteration.info_gain_rate = assessment.info_gain_rate
                iteration.gaps_identified = [g.gap_type for g in assessment.gaps_identified]

                # Complete iteration in state machine
                type_state.complete_iteration(iteration)

                # Decide if we should continue
                decision = self.controller.should_continue_iteration(
                    info_type, iteration, type_state
                )

                if not decision.should_continue:
                    # Mark type complete
                    reason, confidence = self.controller.evaluate_completion(info_type, type_state)
                    type_state.mark_complete(reason, confidence)

                    result.iterations_completed = len(type_state.iterations)
                    result.total_queries_executed = type_state.total_queries_executed
                    result.total_facts_extracted = type_state.total_facts_extracted
                    result.final_confidence = type_state.final_confidence
                    result.completion_reason = type_state.completion_reason
                    break

                # REFINE Phase - prepare for next iteration
                self._current_phase = OrchestratorPhase.REFINING
                gaps = assessment.gaps_identified

            self._current_phase = OrchestratorPhase.COMPLETE

        except Exception as e:
            result.error_occurred = True
            result.error_message = str(e)
            result.error_phase = self._current_phase
            logger.error(
                "Type cycle error",
                info_type=info_type.value,
                phase=self._current_phase.value,
                error=str(e),
            )

        result.completed_at = datetime.now(UTC)
        result.duration_ms = (result.completed_at - result.started_at).total_seconds() * 1000

        return result

    async def _plan_queries(
        self,
        info_type: InformationType,
        knowledge_base: KnowledgeBase,
        iteration_number: int,
        gaps: list[Gap],
        locale: Locale,
        tier: ServiceTier,
        subject_name: str,
    ) -> list[SearchQuery]:
        """Plan queries for an iteration.

        Args:
            info_type: Information type.
            knowledge_base: Current knowledge base.
            iteration_number: Current iteration number.
            gaps: Gaps from previous assessment.
            locale: Subject locale.
            tier: Service tier.
            subject_name: Subject name.

        Returns:
            List of queries to execute.
        """
        if iteration_number == 1:
            # First iteration - use planner for initial queries
            plan_result = self.planner.plan_queries(
                info_type=info_type,
                knowledge_base=knowledge_base,
                iteration_number=iteration_number,
                gaps=[],
                locale=locale,
                tier=tier,
                available_providers=["sterling", "checkr"],  # Will be dynamic
                subject_name=subject_name,
            )
            return plan_result.queries
        else:
            # Subsequent iterations - use refiner for gap-targeting queries
            # Create a minimal assessment result for the refiner
            from elile.investigation.result_assessor import AssessmentResult

            assessment = AssessmentResult(
                info_type=info_type,
                iteration_number=iteration_number - 1,
                gaps_identified=gaps,
            )
            refinement = self.refiner.refine_queries(
                assessment=assessment,
                knowledge_base=knowledge_base,
                locale=locale,
                tier=tier,
            )
            return refinement.queries

    async def _execute_queries(
        self,
        queries: list[SearchQuery],
    ) -> list[QueryResult]:
        """Execute a list of queries.

        Args:
            queries: Queries to execute.

        Returns:
            List of query results.
        """
        if self.executor is None:
            # No executor configured - return mock results
            logger.warning("No query executor configured, returning mock results")
            from elile.investigation.query_executor import QueryResult, QueryStatus

            return [
                QueryResult(
                    query_id=q.query_id,
                    provider_id=q.provider_id,
                    check_type=q.check_type.value,
                    status=QueryStatus.SUCCESS,
                    raw_data={"mock": True},
                    normalized_data={"mock": True},
                )
                for q in queries
            ]

        # Use executor for real execution
        # Note: The executor's execute_batch method handles parallel execution
        from elile.entity.types import SubjectIdentifiers

        # This is a simplified version - full implementation would
        # handle subject identifiers properly
        execution_summary = await self.executor.execute_batch(
            queries=queries,
            subject=SubjectIdentifiers(),  # Would be populated from KB
            locale=Locale.US,
            tier=ServiceTier.STANDARD,
        )
        return execution_summary.results

    async def _assess_results(
        self,
        info_type: InformationType,
        query_results: list[QueryResult],
        iteration_number: int,
        knowledge_base: KnowledgeBase,
    ) -> AssessmentResult:
        """Assess query results.

        Args:
            info_type: Information type.
            query_results: Results from executed queries.
            iteration_number: Current iteration number.
            knowledge_base: Knowledge base for the assessor.

        Returns:
            Assessment result.
        """
        # Create assessor with knowledge base if not provided
        assessor = self._assessor or ResultAssessor(knowledge_base)
        return assessor.assess(
            info_type=info_type,
            query_results=query_results,
            iteration_number=iteration_number,
        )

    def get_summary(self) -> SARSummary:
        """Get current SAR summary from state machine."""
        return self.state.get_summary()

    def _emit_progress(
        self,
        event_type: str,
        info_type: InformationType | None = None,
        phase: OrchestratorPhase | None = None,
        iteration_number: int = 0,
        message: str = "",
        progress_percent: float = 0.0,
    ) -> None:
        """Emit a progress event to all callbacks."""
        if not self.config.emit_progress_events:
            return

        event = ProgressEvent(
            event_type=event_type,
            info_type=info_type,
            phase=phase,
            iteration_number=iteration_number,
            message=message,
            progress_percent=progress_percent,
        )

        for callback in self._progress_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.warning("Progress callback failed", error=str(e))


def create_sar_orchestrator(
    config: OrchestratorConfig | None = None,
    audit_logger: "AuditLogger | None" = None,
) -> SARLoopOrchestrator:
    """Factory function to create a configured SARLoopOrchestrator.

    Args:
        config: Optional orchestrator configuration.
        audit_logger: Optional audit logger.

    Returns:
        Configured SARLoopOrchestrator instance.
    """
    return SARLoopOrchestrator(config=config, audit_logger=audit_logger)
