"""LangGraph workflow definition for the research agent."""

from langgraph.graph import END, StateGraph

from elile.agent.nodes import (
    analyze_findings,
    compile_report,
    evaluate_continuation,
    execute_searches,
    generate_search_queries,
    initialize_research,
    map_connections,
    should_continue_search,
)
from elile.agent.state import AgentState

# Create the workflow graph
workflow = StateGraph(AgentState)

# Add nodes to the graph
workflow.add_node("initialize", initialize_research)
workflow.add_node("generate_queries", generate_search_queries)
workflow.add_node("execute_searches", execute_searches)
workflow.add_node("analyze_findings", analyze_findings)
workflow.add_node("map_connections", map_connections)
workflow.add_node("evaluate_continuation", evaluate_continuation)
workflow.add_node("compile_report", compile_report)

# Define the workflow edges
workflow.set_entry_point("initialize")
workflow.add_edge("initialize", "generate_queries")
workflow.add_edge("generate_queries", "execute_searches")
workflow.add_edge("execute_searches", "analyze_findings")
workflow.add_edge("analyze_findings", "map_connections")
workflow.add_edge("map_connections", "evaluate_continuation")

# Add conditional routing for the search loop
workflow.add_conditional_edges(
    "evaluate_continuation",
    should_continue_search,
    {
        "continue": "generate_queries",
        "compile": "compile_report",
    },
)

workflow.add_edge("compile_report", END)

# Compile the graph
research_graph = workflow.compile()
