"""Node functions for the iterative search agent workflow.

This module implements the Search-Assess-Refine (SAR) loop nodes and
phase transition logic for the phased search workflow.
"""

from datetime import datetime, timezone

import structlog

from elile.agent.state import (
    PHASE_TYPES,
    AgentState,
    Entity,
    Finding,
    Inconsistency,
    InformationType,
    IterativeSearchState,
    KnowledgeBase,
    Report,
    RiskFinding,
    SearchPhase,
    ServiceConfiguration,
    SubjectInfo,
    TypeProgress,
)
from elile.config.settings import get_settings
from elile.risk.inconsistency import InconsistencyAnalyzer
from elile.risk.scoring import calculate_risk_score
from elile.search.enricher import QueryEnricher
from elile.search.query import QueryBuilder, QueryCategory, SearchQuery

logger = structlog.get_logger()


# =============================================================================
# Initialization Node
# =============================================================================


async def initialize_search(state: IterativeSearchState) -> dict:
    """Initialize the iterative search workflow.

    Sets up initial state, validates configuration, and prepares
    tracking structures for all information types.

    Args:
        state: Current workflow state.

    Returns:
        State updates for initialization.
    """
    subject = state.get("subject")
    service_config = state.get("service_config")

    if subject is None:
        raise ValueError("Subject information is required")

    if service_config is None:
        service_config = ServiceConfiguration()

    # Validate configuration
    if not service_config.validate_configuration():
        raise ValueError("Invalid service configuration: D3 requires Enhanced tier")

    logger.info(
        "Initializing iterative search",
        subject=subject.full_name,
        tier=service_config.tier.value,
        degrees=service_config.degrees.value,
    )

    # Initialize type progress for all enabled types
    type_progress: dict[str, TypeProgress] = {}
    for phase, types in PHASE_TYPES.items():
        for info_type in types:
            if service_config.is_type_enabled(info_type):
                type_progress[info_type.value] = TypeProgress(
                    info_type=info_type,
                    status="pending",
                )
            else:
                # Mark disabled types as skipped
                type_progress[info_type.value] = TypeProgress(
                    info_type=info_type,
                    status="complete",
                    completion_reason="skipped",
                )

    # Initialize knowledge base with provided information
    knowledge_base = KnowledgeBase(
        confirmed_names=[subject.full_name],
    )

    # Add provided addresses
    for addr in subject.provided_addresses:
        knowledge_base.add_address(addr)

    return {
        "service_config": service_config,
        "current_phase": None,  # Will be set by first phase transition
        "current_type": None,
        "type_progress": type_progress,
        "knowledge_base": knowledge_base,
        "inconsistency_queue": [],
        "entity_queue": [],
        "current_iteration": 0,
        "current_queries": [],
        "current_results": [],
        "iteration_findings": [],
        "iteration_info_gain": 0.0,
        "all_findings": [],
        "risk_findings": [],
        "connections": [],
        "final_report": None,
    }


# =============================================================================
# SAR Loop Nodes: Search, Assess, Refine
# =============================================================================


async def search_type(state: IterativeSearchState) -> dict:
    """SEARCH phase of the SAR loop.

    Generates and executes queries for the current information type,
    using knowledge base enrichment.

    Args:
        state: Current workflow state.

    Returns:
        State updates with query results.
    """
    current_type = state.get("current_type")
    current_iteration = state.get("current_iteration", 0)
    knowledge_base = state.get("knowledge_base", KnowledgeBase())
    subject = state.get("subject")
    type_progress = state.get("type_progress", {})

    if current_type is None or subject is None:
        logger.warning("No current type or subject for search")
        return {}

    type_key = current_type.value
    progress = type_progress.get(type_key)

    logger.info(
        "Executing search phase",
        info_type=type_key,
        iteration=current_iteration,
        knowledge_base_names=len(knowledge_base.confirmed_names),
    )

    # Generate base queries for this type
    base_queries = _generate_type_queries(current_type, subject, knowledge_base)

    # Enrich queries using knowledge base
    enricher = QueryEnricher(knowledge_base)
    enriched_queries = enricher.enrich_queries(current_type, base_queries)

    # If this is not the first iteration, add gap-fill queries
    if progress and progress.gaps and current_iteration > 0:
        gap_queries = enricher.generate_gap_queries(
            current_type,
            progress.gaps,
            subject.full_name,
        )
        enriched_queries.extend(gap_queries)

    # Mark queries with iteration number
    final_queries = [q.for_iteration(current_iteration) for q in enriched_queries]

    logger.info(
        "Generated queries",
        base_count=len(base_queries),
        enriched_count=len(enriched_queries),
        final_count=len(final_queries),
    )

    # TODO: Execute queries through search engine
    # For now, return empty results - actual execution will be implemented
    # when search providers are integrated

    from elile.agent.state import SearchResult

    results: list[SearchResult] = []

    # Update type progress
    if type_key in type_progress:
        updated_progress = type_progress[type_key].model_copy()
        updated_progress.status = "in_progress"
        updated_progress.iterations = current_iteration + 1
        updated_progress.queries_executed = len(final_queries)
        type_progress[type_key] = updated_progress

    return {
        "current_queries": [q.query for q in final_queries],
        "current_results": results,
        "type_progress": type_progress,
    }


async def assess_type(state: IterativeSearchState) -> dict:
    """ASSESS phase of the SAR loop.

    Analyzes search results to:
    - Extract structured findings
    - Calculate type confidence score
    - Identify gaps (expected info not found)
    - Detect inconsistencies
    - Discover new entities for network phases

    Args:
        state: Current workflow state.

    Returns:
        State updates with findings and assessments.
    """
    current_type = state.get("current_type")
    current_results = state.get("current_results", [])
    current_queries = state.get("current_queries", [])
    type_progress = state.get("type_progress", {})
    knowledge_base = state.get("knowledge_base", KnowledgeBase())
    all_findings = state.get("all_findings", [])
    inconsistency_queue = state.get("inconsistency_queue", [])
    entity_queue = state.get("entity_queue", [])

    if current_type is None:
        return {}

    type_key = current_type.value
    progress = type_progress.get(type_key)

    logger.info(
        "Assessing results",
        info_type=type_key,
        result_count=len(current_results),
        query_count=len(current_queries),
    )

    # TODO: Implement model-based finding extraction
    # This should use the model to:
    # 1. Extract structured facts from results
    # 2. Identify gaps in expected information
    # 3. Detect inconsistencies with existing knowledge
    # 4. Discover new entities (people, organizations)

    # Placeholder: Generate findings from results
    new_findings: list[Finding] = []
    gaps: list[str] = []
    new_inconsistencies: list[Inconsistency] = []
    discovered_entities: list[Entity] = []

    # Calculate information gain rate
    query_count = len(current_queries) if current_queries else 1
    info_gain = len(new_findings) / query_count

    # Calculate type confidence (placeholder logic)
    # Real implementation would use model to assess completeness
    result_count = len(current_results)
    confidence = min(0.95, 0.3 + (result_count * 0.1) + (len(new_findings) * 0.05))

    # Update type progress
    if progress:
        updated_progress = progress.model_copy()
        updated_progress.findings.extend(new_findings)
        updated_progress.gaps = gaps
        updated_progress.discovered_entities.extend(discovered_entities)
        updated_progress.results_received = result_count
        updated_progress.info_gain_rate = info_gain
        updated_progress.confidence = confidence
        type_progress[type_key] = updated_progress

    # Update knowledge base based on type
    knowledge_base = _update_knowledge_base(current_type, knowledge_base, new_findings)

    logger.info(
        "Assessment complete",
        info_type=type_key,
        new_findings=len(new_findings),
        gaps=len(gaps),
        confidence=confidence,
        info_gain=info_gain,
    )

    return {
        "type_progress": type_progress,
        "knowledge_base": knowledge_base,
        "iteration_findings": new_findings,
        "iteration_info_gain": info_gain,
        "all_findings": all_findings + new_findings,
        "inconsistency_queue": inconsistency_queue + new_inconsistencies,
        "entity_queue": entity_queue + discovered_entities,
    }


async def refine_decision(state: IterativeSearchState) -> dict:
    """REFINE phase of the SAR loop.

    Decides whether to:
    - Continue searching (loop back to SEARCH)
    - Mark type as complete and proceed to next type

    Decision logic:
    1. If confidence >= threshold: complete (threshold reached)
    2. If iterations >= max: complete (max iterations)
    3. If info_gain < min_gain: complete (diminishing returns)
    4. Otherwise: continue with gap-fill queries

    Args:
        state: Current workflow state.

    Returns:
        State updates with completion decision.
    """
    current_type = state.get("current_type")
    type_progress = state.get("type_progress", {})
    current_iteration = state.get("current_iteration", 0)

    settings = get_settings()
    config = settings.iterative_search

    if current_type is None:
        return {}

    type_key = current_type.value
    progress = type_progress.get(type_key)

    if progress is None:
        return {"current_iteration": current_iteration + 1}

    # Get thresholds (phase-specific for foundation)
    current_phase = state.get("current_phase")
    if current_phase == SearchPhase.FOUNDATION:
        confidence_threshold = config.foundation_confidence_threshold
        max_iterations = config.foundation_max_iterations
    else:
        confidence_threshold = config.confidence_threshold
        max_iterations = config.max_iterations_per_type

    # Decision logic
    completion_reason = None

    if progress.confidence >= confidence_threshold:
        completion_reason = "threshold"
    elif progress.iterations >= max_iterations:
        completion_reason = "max_iter"
    elif progress.info_gain_rate < config.min_gain_threshold and progress.iterations > 0:
        completion_reason = "diminishing"

    if completion_reason:
        # Mark type as complete
        updated_progress = progress.model_copy()
        updated_progress.status = "complete"
        updated_progress.completion_reason = completion_reason
        type_progress[type_key] = updated_progress

        logger.info(
            "Type complete",
            info_type=type_key,
            reason=completion_reason,
            confidence=progress.confidence,
            iterations=progress.iterations,
        )

        return {
            "type_progress": type_progress,
            "current_iteration": 0,  # Reset for next type
        }
    else:
        # Continue SAR loop
        logger.info(
            "Continuing SAR loop",
            info_type=type_key,
            confidence=progress.confidence,
            iterations=progress.iterations,
            info_gain=progress.info_gain_rate,
        )

        return {
            "current_iteration": current_iteration + 1,
        }


# =============================================================================
# Phase Transition Nodes
# =============================================================================


async def transition_to_next_type(state: IterativeSearchState) -> dict:
    """Transition to the next information type within the current phase.

    Args:
        state: Current workflow state.

    Returns:
        State updates with next type.
    """
    current_phase = state.get("current_phase")
    type_progress = state.get("type_progress", {})
    service_config = state.get("service_config")

    if current_phase is None:
        return {}

    # Get types for current phase
    phase_types = PHASE_TYPES.get(current_phase, [])

    # Filter to enabled types
    if service_config:
        phase_types = [t for t in phase_types if service_config.is_type_enabled(t)]

    # Find next pending type
    next_type = None
    for info_type in phase_types:
        type_key = info_type.value
        progress = type_progress.get(type_key)

        if progress is None or progress.status == "pending":
            next_type = info_type
            break

    if next_type:
        logger.info(
            "Transitioning to next type",
            phase=current_phase.value,
            next_type=next_type.value,
        )
        return {
            "current_type": next_type,
            "current_iteration": 0,
        }
    else:
        logger.info(
            "All types in phase complete",
            phase=current_phase.value,
        )
        return {
            "current_type": None,
        }


async def transition_to_next_phase(state: IterativeSearchState) -> dict:
    """Transition to the next search phase.

    Args:
        state: Current workflow state.

    Returns:
        State updates with next phase.
    """
    current_phase = state.get("current_phase")
    service_config = state.get("service_config")
    type_progress = state.get("type_progress", {})

    # Phase order
    phase_order = [
        SearchPhase.FOUNDATION,
        SearchPhase.RECORDS,
        SearchPhase.INTELLIGENCE,
        SearchPhase.NETWORK,
        SearchPhase.RECONCILIATION,
    ]

    # Determine next phase
    if current_phase is None:
        next_phase = SearchPhase.FOUNDATION
    else:
        try:
            current_idx = phase_order.index(current_phase)
            if current_idx < len(phase_order) - 1:
                next_phase = phase_order[current_idx + 1]
            else:
                next_phase = None
        except ValueError:
            next_phase = None

    if next_phase is None:
        logger.info("All phases complete")
        return {}

    # Get first enabled type in next phase
    phase_types = PHASE_TYPES.get(next_phase, [])
    if service_config:
        phase_types = [t for t in phase_types if service_config.is_type_enabled(t)]

    first_type = phase_types[0] if phase_types else None

    logger.info(
        "Transitioning to next phase",
        from_phase=current_phase.value if current_phase else None,
        to_phase=next_phase.value,
        first_type=first_type.value if first_type else None,
    )

    return {
        "current_phase": next_phase,
        "current_type": first_type,
        "current_iteration": 0,
    }


# =============================================================================
# Reconciliation Node
# =============================================================================


async def process_reconciliation(state: IterativeSearchState) -> dict:
    """Process the inconsistency queue and generate risk findings.

    Analyzes patterns in detected inconsistencies and generates
    appropriate risk findings for the final report.

    Args:
        state: Current workflow state.

    Returns:
        State updates with reconciliation results.
    """
    inconsistency_queue = state.get("inconsistency_queue", [])
    risk_findings = state.get("risk_findings", [])

    settings = get_settings()
    config = settings.iterative_search

    logger.info(
        "Processing reconciliation",
        inconsistency_count=len(inconsistency_queue),
    )

    if not inconsistency_queue:
        return {}

    # Analyze inconsistency patterns
    analyzer = InconsistencyAnalyzer(
        systematic_threshold=config.systematic_pattern_threshold,
        cross_type_threshold=config.cross_type_pattern_threshold,
    )

    new_risk_findings = analyzer.analyze_patterns(inconsistency_queue)

    # Auto-resolve low severity if configured
    if config.auto_resolve_low_severity:
        for inc in inconsistency_queue:
            if inc.risk_severity == "low" and not inc.resolved:
                inc.resolved = True
                inc.resolution = "Auto-resolved as low severity"
                inc.resolution_outcome = "explained"

    logger.info(
        "Reconciliation complete",
        new_risk_findings=len(new_risk_findings),
        resolved_count=sum(1 for inc in inconsistency_queue if inc.resolved),
    )

    return {
        "inconsistency_queue": inconsistency_queue,
        "risk_findings": risk_findings + new_risk_findings,
    }


# =============================================================================
# Report Compilation Node
# =============================================================================


async def compile_report(state: IterativeSearchState) -> dict:
    """Compile the final research report.

    Synthesizes all findings, risks, connections, and inconsistencies
    into a comprehensive research report.

    Args:
        state: Current workflow state.

    Returns:
        State updates with final report.
    """
    subject = state.get("subject")
    all_findings = state.get("all_findings", [])
    risk_findings = state.get("risk_findings", [])
    connections = state.get("connections", [])
    inconsistency_queue = state.get("inconsistency_queue", [])
    type_progress = state.get("type_progress", {})

    if subject is None:
        return {}

    logger.info(
        "Compiling final report",
        findings=len(all_findings),
        risks=len(risk_findings),
        connections=len(connections),
        inconsistencies=len(inconsistency_queue),
    )

    # Calculate overall risk score
    risk_score = calculate_risk_score(risk_findings)

    # Build type confidence map
    type_confidence = {
        type_key: progress.confidence
        for type_key, progress in type_progress.items()
        if progress.status == "complete" and progress.completion_reason != "skipped"
    }

    # Generate summary
    summary = _generate_summary(subject, all_findings, risk_findings, risk_score)

    # Create report
    report = Report(
        subject=subject,
        summary=summary,
        risk_score=risk_score.overall_score,
        risk_level=risk_score.level.value,
        findings=all_findings,
        risk_findings=risk_findings,
        connections=connections,
        inconsistencies=inconsistency_queue,
        type_confidence=type_confidence,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    logger.info(
        "Report compiled",
        risk_level=risk_score.level.value,
        risk_score=risk_score.overall_score,
    )

    return {
        "final_report": report,
    }


# =============================================================================
# Helper Functions
# =============================================================================


def _generate_type_queries(
    info_type: InformationType,
    subject: SubjectInfo,
    knowledge_base: KnowledgeBase,
) -> list[SearchQuery]:
    """Generate base queries for an information type.

    Args:
        info_type: The information type to generate queries for.
        subject: Subject information.
        knowledge_base: Accumulated knowledge.

    Returns:
        List of base queries for this type.
    """
    builder = QueryBuilder(subject.full_name, info_type)

    match info_type:
        case InformationType.IDENTITY:
            builder.add_query(
                f'"{subject.full_name}" identity verification',
                QueryCategory.BIOGRAPHICAL,
                priority=1,
            )
            if subject.date_of_birth:
                builder.add_query(
                    f'"{subject.full_name}" born {subject.date_of_birth}',
                    QueryCategory.BIOGRAPHICAL,
                    priority=2,
                )

        case InformationType.EMPLOYMENT:
            builder.add_query(
                f'"{subject.full_name}" employment history',
                QueryCategory.EMPLOYMENT,
                priority=1,
            )
            for employer in subject.provided_employers:
                builder.add_query(
                    f'"{subject.full_name}" {employer}',
                    QueryCategory.EMPLOYMENT,
                    priority=2,
                )

        case InformationType.EDUCATION:
            builder.add_query(
                f'"{subject.full_name}" education degree',
                QueryCategory.EDUCATION,
                priority=1,
            )
            for school in subject.provided_schools:
                builder.add_query(
                    f'"{subject.full_name}" {school}',
                    QueryCategory.EDUCATION,
                    priority=2,
                )

        case InformationType.CRIMINAL:
            builder.add_query(
                f'"{subject.full_name}" criminal records',
                QueryCategory.CRIMINAL,
                priority=1,
            )

        case InformationType.CIVIL:
            builder.add_query(
                f'"{subject.full_name}" lawsuit litigation',
                QueryCategory.CIVIL,
                priority=1,
            )

        case InformationType.FINANCIAL:
            builder.add_query(
                f'"{subject.full_name}" bankruptcy liens judgments',
                QueryCategory.FINANCIAL,
                priority=1,
            )

        case InformationType.LICENSES:
            builder.add_query(
                f'"{subject.full_name}" professional license',
                QueryCategory.PROFESSIONAL,
                priority=1,
            )

        case InformationType.REGULATORY:
            builder.add_query(
                f'"{subject.full_name}" regulatory enforcement action',
                QueryCategory.REGULATORY,
                priority=1,
            )

        case InformationType.SANCTIONS:
            builder.add_query(
                f'"{subject.full_name}" sanctions OFAC PEP',
                QueryCategory.SANCTIONS,
                priority=1,
            )

        case InformationType.ADVERSE_MEDIA:
            builder.add_query(
                f'"{subject.full_name}" news controversy',
                QueryCategory.MEDIA,
                priority=1,
            )

        case InformationType.DIGITAL_FOOTPRINT:
            builder.add_query(
                f'"{subject.full_name}" LinkedIn profile',
                QueryCategory.DIGITAL,
                priority=1,
            )

        case InformationType.NETWORK_D2 | InformationType.NETWORK_D3:
            # Network queries based on discovered entities
            for person in knowledge_base.discovered_people[:5]:
                builder.add_query(
                    f'"{person.name}" background',
                    QueryCategory.NETWORK,
                    priority=2,
                )
            for org in knowledge_base.discovered_orgs[:5]:
                builder.add_query(
                    f'"{org.name}" company information',
                    QueryCategory.NETWORK,
                    priority=2,
                )

        case _:
            pass

    return builder.build()


def _update_knowledge_base(
    info_type: InformationType,
    knowledge_base: KnowledgeBase,
    findings: list[Finding],
) -> KnowledgeBase:
    """Update knowledge base with findings from a completed type.

    Args:
        info_type: The information type that produced these findings.
        knowledge_base: Current knowledge base.
        findings: New findings to incorporate.

    Returns:
        Updated knowledge base.
    """
    # This is a placeholder - real implementation would parse
    # structured findings and update the knowledge base accordingly

    # For now, just return the knowledge base unchanged
    return knowledge_base


def _generate_summary(
    subject: SubjectInfo,
    findings: list[Finding],
    risk_findings: list[RiskFinding],
    risk_score,
) -> str:
    """Generate a summary for the report.

    Args:
        subject: Subject information.
        findings: All findings.
        risk_findings: Risk findings.
        risk_score: Calculated risk score.

    Returns:
        Summary text.
    """
    summary_parts = [
        f"Background investigation report for {subject.full_name}.",
        f"Risk Level: {risk_score.level.value.upper()}",
        f"Overall Risk Score: {risk_score.overall_score:.2f}",
        f"Total Findings: {len(findings)}",
        f"Risk Indicators: {len(risk_findings)}",
    ]

    if risk_findings:
        high_severity = [f for f in risk_findings if f.severity in ("high", "critical")]
        if high_severity:
            summary_parts.append(
                f"High/Critical Findings: {len(high_severity)}"
            )

    return " | ".join(summary_parts)


# =============================================================================
# Legacy Node Functions (for backwards compatibility)
# =============================================================================


async def initialize_research(state: AgentState) -> dict:
    """Initialize the research workflow with the target entity.

    DEPRECATED: Use initialize_search with IterativeSearchState.

    Sets up initial state and prepares for the first round of searches.
    """
    logger.info("Initializing research", target=state["target"])

    return {
        "search_queries": [],
        "search_results": [],
        "findings": [],
        "risk_findings": [],
        "connections": [],
        "search_depth": 0,
        "should_continue": True,
        "final_report": None,
    }


async def generate_search_queries(state: AgentState) -> dict:
    """Generate search queries based on current knowledge.

    DEPRECATED: Use search_type with IterativeSearchState.
    """
    logger.info(
        "Generating search queries",
        target=state["target"],
        depth=state["search_depth"],
        existing_findings=len(state.get("findings", [])),
    )

    queries: list[str] = []

    return {"search_queries": queries}


async def execute_searches(state: AgentState) -> dict:
    """Execute the generated search queries.

    DEPRECATED: Use search_type with IterativeSearchState.
    """
    queries = state.get("search_queries", [])
    logger.info("Executing searches", query_count=len(queries))

    from elile.agent.state import SearchResult

    results: list[SearchResult] = []

    return {"search_results": state.get("search_results", []) + results}


async def analyze_findings(state: AgentState) -> dict:
    """Analyze search results to extract facts and identify risks.

    DEPRECATED: Use assess_type with IterativeSearchState.
    """
    results = state.get("search_results", [])
    logger.info("Analyzing findings", result_count=len(results))

    new_findings: list[str] = []
    new_risks: list[RiskFinding] = []

    return {
        "findings": state.get("findings", []) + new_findings,
        "risk_findings": state.get("risk_findings", []) + new_risks,
    }


async def map_connections(state: AgentState) -> dict:
    """Map connections between entities discovered in research.

    DEPRECATED: Use assess_type with IterativeSearchState.
    """
    findings = state.get("findings", [])
    logger.info("Mapping connections", finding_count=len(findings))

    from elile.agent.state import EntityConnection

    new_connections: list[EntityConnection] = []

    return {"connections": state.get("connections", []) + new_connections}


async def evaluate_continuation(state: AgentState) -> dict:
    """Evaluate whether to continue searching or compile the report.

    DEPRECATED: Use refine_decision with IterativeSearchState.
    """
    settings = get_settings()
    current_depth = state.get("search_depth", 0)
    max_depth = settings.max_search_depth

    logger.info(
        "Evaluating continuation",
        current_depth=current_depth,
        max_depth=max_depth,
        findings=len(state.get("findings", [])),
    )

    should_continue = current_depth < max_depth and len(state.get("findings", [])) > 0

    return {
        "search_depth": current_depth + 1,
        "should_continue": should_continue,
    }


def should_continue_search(state: AgentState) -> str:
    """Routing function to determine next step in the workflow.

    DEPRECATED: Use route_refine_decision with IterativeSearchState.

    Returns:
        "continue" to perform another search iteration.
        "compile" to compile the final report.
    """
    if state.get("should_continue", False):
        return "continue"
    return "compile"
