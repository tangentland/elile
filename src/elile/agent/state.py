"""TypedDict state definitions for the research agent workflow."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages
from pydantic import BaseModel


class SearchResult(BaseModel):
    """A single search result with source and extracted information."""

    query: str
    source: str
    content: str
    relevance_score: float
    timestamp: str


class RiskFinding(BaseModel):
    """A risk indicator or red flag identified during research."""

    category: str
    description: str
    severity: str  # low, medium, high, critical
    confidence: float
    sources: list[str]


class EntityConnection(BaseModel):
    """A connection between two entities discovered during research."""

    source_entity: str
    target_entity: str
    relationship_type: str
    description: str
    confidence: float
    sources: list[str]


class AgentState(TypedDict):
    """Main state for the research agent workflow.

    Attributes:
        messages: Conversation history with add semantics.
        target: The entity being researched.
        search_queries: Generated search queries to execute.
        search_results: Results from executed searches.
        findings: Extracted facts and information.
        risk_findings: Identified risk indicators.
        connections: Mapped entity connections.
        search_depth: Current depth of search iteration.
        should_continue: Whether to continue searching.
        final_report: The compiled research report.
    """

    messages: Annotated[list, add_messages]
    target: str
    search_queries: list[str]
    search_results: list[SearchResult]
    findings: list[str]
    risk_findings: list[RiskFinding]
    connections: list[EntityConnection]
    search_depth: int
    should_continue: bool
    final_report: str | None
