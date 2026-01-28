"""Pytest fixtures for Elile tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from elile.agent.state import AgentState, EntityConnection, RiskFinding, SearchResult
from elile.config.settings import ModelProvider, Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    return Settings(
        anthropic_api_key=SecretStr("test-anthropic-key"),
        openai_api_key=SecretStr("test-openai-key"),
        google_api_key=SecretStr("test-google-key"),
        default_model_provider=ModelProvider.ANTHROPIC,
        log_level="DEBUG",
        rate_limit_rpm=100,
        max_search_depth=3,
        max_concurrent_searches=2,
    )


@pytest.fixture
def patch_settings(mock_settings: Settings) -> Generator[Settings, None, None]:
    """Patch get_settings to return mock settings."""
    with patch("elile.config.settings.get_settings", return_value=mock_settings):
        yield mock_settings


@pytest.fixture
def sample_search_result() -> SearchResult:
    """Create a sample search result for testing."""
    return SearchResult(
        query="test query",
        source="https://example.com",
        content="Sample search result content",
        relevance_score=0.85,
        timestamp="2025-01-01T00:00:00Z",
    )


@pytest.fixture
def sample_risk_finding() -> RiskFinding:
    """Create a sample risk finding for testing."""
    return RiskFinding(
        category="financial",
        description="Test risk finding",
        severity="medium",
        confidence=0.75,
        sources=["https://example.com"],
    )


@pytest.fixture
def sample_connection() -> EntityConnection:
    """Create a sample entity connection for testing."""
    return EntityConnection(
        source_entity="Entity A",
        target_entity="Entity B",
        relationship_type="business_partner",
        description="Test connection",
        confidence=0.8,
        sources=["https://example.com"],
    )


@pytest.fixture
def initial_agent_state() -> AgentState:
    """Create an initial agent state for testing."""
    return AgentState(
        messages=[],
        target="Test Target",
        search_queries=[],
        search_results=[],
        findings=[],
        risk_findings=[],
        connections=[],
        search_depth=0,
        should_continue=True,
        final_report=None,
    )
