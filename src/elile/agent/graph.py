"""LangGraph workflow definition for the iterative search agent.

This module implements a phased workflow with Search-Assess-Refine (SAR) loops
for each information type, organized into sequential and parallel phases.

Phases:
1. FOUNDATION (sequential): identity -> employment -> education
2. RECORDS (parallel): criminal, civil, financial, licenses, regulatory, sanctions
3. INTELLIGENCE (parallel): adverse_media, digital_footprint (Enhanced only)
4. NETWORK (sequential by degree): D1 -> D2 -> D3 (Enhanced only)
5. RECONCILIATION: Process inconsistency queue, generate risk findings
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, StateGraph

from elile.agent.nodes import (
    assess_type,
    compile_report,
    initialize_search,
    process_reconciliation,
    refine_decision,
    search_type,
    transition_to_next_phase,
    transition_to_next_type,
)
from elile.agent.state import (
    PHASE_TYPES,
    InformationType,
    IterativeSearchState,
    SearchPhase,
)


def _get_phase_for_type(info_type: InformationType) -> SearchPhase:
    """Get the phase that an information type belongs to."""
    for phase, types in PHASE_TYPES.items():
        if info_type in types:
            return phase
    return SearchPhase.FOUNDATION


# =============================================================================
# Routing Functions
# =============================================================================


def route_refine_decision(state: IterativeSearchState) -> Literal["search", "next_type"]:
    """Route based on refine decision.

    Determines whether to continue the SAR loop for the current type
    or move to the next type.

    Args:
        state: Current workflow state.

    Returns:
        "search" to continue SAR loop, "next_type" to proceed.
    """
    current_type = state.get("current_type")
    if current_type is None:
        return "next_type"

    type_key = current_type.value
    type_progress = state.get("type_progress", {}).get(type_key)

    if type_progress is None:
        return "next_type"

    # If type is complete, move to next
    if type_progress.status == "complete":
        return "next_type"

    # Otherwise continue SAR loop
    return "search"


def route_next_type(state: IterativeSearchState) -> Literal["sar_loop", "next_phase"]:
    """Route to next type within phase or to phase transition.

    Args:
        state: Current workflow state.

    Returns:
        "sar_loop" to start new type, "next_phase" to transition phases.
    """
    current_phase = state.get("current_phase")
    current_type = state.get("current_type")
    type_progress = state.get("type_progress", {})
    service_config = state.get("service_config")

    if current_phase is None:
        return "next_phase"

    # Get types for current phase
    phase_types = PHASE_TYPES.get(current_phase, [])

    # Filter to enabled types
    if service_config:
        phase_types = [t for t in phase_types if service_config.is_type_enabled(t)]

    # Check if there are more types to process in this phase
    for info_type in phase_types:
        type_key = info_type.value
        progress = type_progress.get(type_key)

        # If this type hasn't been started or isn't complete, process it
        if progress is None or progress.status == "pending":
            return "sar_loop"

    # All types in phase complete, transition to next phase
    return "next_phase"


def route_phase_transition(
    state: IterativeSearchState,
) -> Literal["foundation", "records", "intelligence", "network", "reconciliation", "compile"]:
    """Route to the appropriate phase or end.

    Args:
        state: Current workflow state.

    Returns:
        Next phase name or "compile" to finish.
    """
    current_phase = state.get("current_phase")

    # Phase progression order
    phase_order = [
        SearchPhase.FOUNDATION,
        SearchPhase.RECORDS,
        SearchPhase.INTELLIGENCE,
        SearchPhase.NETWORK,
        SearchPhase.RECONCILIATION,
    ]

    if current_phase is None:
        return "foundation"

    try:
        current_idx = phase_order.index(current_phase)
        if current_idx < len(phase_order) - 1:
            next_phase = phase_order[current_idx + 1]
            return next_phase.value
        else:
            return "compile"
    except ValueError:
        return "compile"


def route_reconciliation(
    state: IterativeSearchState,
) -> Literal["compile", "reconciliation"]:
    """Route for reconciliation phase.

    Args:
        state: Current workflow state.

    Returns:
        "reconciliation" if there are inconsistencies, "compile" otherwise.
    """
    inconsistencies = state.get("inconsistency_queue", [])

    if inconsistencies:
        return "reconciliation"
    return "compile"


# =============================================================================
# Workflow Graph Construction
# =============================================================================


def create_iterative_search_graph() -> StateGraph:
    """Create the iterative search workflow graph.

    Returns:
        Compiled LangGraph workflow.
    """
    workflow = StateGraph(IterativeSearchState)

    # ==========================================================================
    # Add Nodes
    # ==========================================================================

    # Initialization
    workflow.add_node("initialize", initialize_search)

    # SAR Loop nodes (shared across all phases)
    workflow.add_node("search_type", search_type)
    workflow.add_node("assess_type", assess_type)
    workflow.add_node("refine_decision", refine_decision)

    # Type/Phase transition nodes
    workflow.add_node("next_type", transition_to_next_type)
    workflow.add_node("next_phase", transition_to_next_phase)

    # Reconciliation
    workflow.add_node("reconciliation", process_reconciliation)

    # Final compilation
    workflow.add_node("compile_report", compile_report)

    # ==========================================================================
    # Define Edges
    # ==========================================================================

    # Entry point
    workflow.set_entry_point("initialize")

    # Initialize -> first phase
    workflow.add_edge("initialize", "next_phase")

    # SAR Loop edges
    workflow.add_edge("search_type", "assess_type")
    workflow.add_edge("assess_type", "refine_decision")

    # Refine decision routing
    workflow.add_conditional_edges(
        "refine_decision",
        route_refine_decision,
        {
            "search": "search_type",  # Continue SAR loop
            "next_type": "next_type",  # Move to next type
        },
    )

    # Next type routing
    workflow.add_conditional_edges(
        "next_type",
        route_next_type,
        {
            "sar_loop": "search_type",  # Start new type's SAR loop
            "next_phase": "next_phase",  # All types complete, next phase
        },
    )

    # Phase transition routing
    workflow.add_conditional_edges(
        "next_phase",
        route_phase_transition,
        {
            "foundation": "search_type",  # Start foundation phase
            "records": "search_type",  # Start records phase
            "intelligence": "search_type",  # Start intelligence phase
            "network": "search_type",  # Start network phase
            "reconciliation": "reconciliation",  # Go to reconciliation
            "compile": "compile_report",  # Skip to compile if no recon needed
        },
    )

    # Reconciliation -> compile
    workflow.add_edge("reconciliation", "compile_report")

    # Compile -> END
    workflow.add_edge("compile_report", END)

    return workflow


# Create and compile the main workflow
iterative_search_graph = create_iterative_search_graph().compile()


# =============================================================================
# Legacy Graph (for backwards compatibility)
# =============================================================================

# Keep the old research_graph name for compatibility
# This imports from the legacy nodes module
try:
    from elile.agent.state import AgentState

    from elile.agent.nodes import (
        analyze_findings,
        compile_report as legacy_compile_report,
        evaluate_continuation,
        execute_searches,
        generate_search_queries,
        initialize_research,
        map_connections,
        should_continue_search,
    )

    # Create the legacy workflow graph
    legacy_workflow = StateGraph(AgentState)

    # Add nodes to the graph
    legacy_workflow.add_node("initialize", initialize_research)
    legacy_workflow.add_node("generate_queries", generate_search_queries)
    legacy_workflow.add_node("execute_searches", execute_searches)
    legacy_workflow.add_node("analyze_findings", analyze_findings)
    legacy_workflow.add_node("map_connections", map_connections)
    legacy_workflow.add_node("evaluate_continuation", evaluate_continuation)
    legacy_workflow.add_node("compile_report", legacy_compile_report)

    # Define the workflow edges
    legacy_workflow.set_entry_point("initialize")
    legacy_workflow.add_edge("initialize", "generate_queries")
    legacy_workflow.add_edge("generate_queries", "execute_searches")
    legacy_workflow.add_edge("execute_searches", "analyze_findings")
    legacy_workflow.add_edge("analyze_findings", "map_connections")
    legacy_workflow.add_edge("map_connections", "evaluate_continuation")

    # Add conditional routing for the search loop
    legacy_workflow.add_conditional_edges(
        "evaluate_continuation",
        should_continue_search,
        {
            "continue": "generate_queries",
            "compile": "compile_report",
        },
    )

    legacy_workflow.add_edge("compile_report", END)

    # Compile the graph
    research_graph = legacy_workflow.compile()

except ImportError:
    # If legacy nodes aren't available, just use the new graph
    research_graph = iterative_search_graph
