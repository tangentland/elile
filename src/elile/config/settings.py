"""Application settings loaded from environment variables."""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelProvider(str, Enum):
    """Supported model providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class IterativeSearchConfig(BaseModel):
    """Configuration for iterative search behavior.

    Controls the Search-Assess-Refine loop behavior, including thresholds
    for confidence, iteration limits, and phase-specific overrides.
    """

    # Confidence thresholds
    confidence_threshold: float = 0.85
    """Type confidence threshold to mark type as complete."""

    # Iteration limits
    max_iterations_per_type: int = 3
    """Hard cap on iterations per information type."""

    # Diminishing returns
    min_gain_threshold: float = 0.1
    """Minimum new facts / queries ratio to continue iterating."""

    # Phase-specific overrides
    foundation_confidence_threshold: float = 0.90
    """Higher confidence threshold for foundation phase types."""

    foundation_max_iterations: int = 4
    """Allow more iterations for critical foundation phase."""

    # Network phase controls
    network_max_entities_per_degree: int = 20
    """Maximum entities to expand in D2/D3 network phases."""

    # Reconciliation phase
    max_reconciliation_queries: int = 10
    """Maximum queries for conflict resolution."""

    auto_resolve_low_severity: bool = True
    """Automatically mark low-severity inconsistencies as explained."""

    # Priority configuration for query dispatcher
    priority_base_foundation: int = 5
    """Base priority for foundation phase (highest)."""

    priority_base_records: int = 3
    """Base priority for records phase."""

    priority_base_intelligence: int = 2
    """Base priority for intelligence phase."""

    priority_base_network: int = 2
    """Base priority for network phase."""

    priority_base_reconciliation: int = 4
    """Base priority for reconciliation phase (high to resolve conflicts)."""

    # Inconsistency analysis
    systematic_pattern_threshold: int = 4
    """Number of inconsistencies to trigger systematic pattern detection."""

    cross_type_pattern_threshold: int = 3
    """Number of types with inconsistencies to trigger cross-type pattern."""


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # Default Model Configuration
    default_model_provider: ModelProvider = ModelProvider.ANTHROPIC
    anthropic_model: str = "claude-sonnet-4-20250514"
    openai_model: str = "gpt-4o"
    google_model: str = "gemini-2.0-flash"

    # LangSmith Tracing
    langchain_tracing_v2: bool = False
    langchain_api_key: SecretStr | None = None
    langchain_project: str = "elile"

    # Application Configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    rate_limit_rpm: int = 60
    max_search_depth: int = 5
    max_concurrent_searches: int = 3

    # Iterative Search Configuration
    iterative_search: IterativeSearchConfig = IterativeSearchConfig()

    def get_api_key(self, provider: ModelProvider) -> SecretStr | None:
        """Get API key for the specified provider."""
        match provider:
            case ModelProvider.ANTHROPIC:
                return self.anthropic_api_key
            case ModelProvider.OPENAI:
                return self.openai_api_key
            case ModelProvider.GOOGLE:
                return self.google_api_key

    def get_model_name(self, provider: ModelProvider) -> str:
        """Get default model name for the specified provider."""
        match provider:
            case ModelProvider.ANTHROPIC:
                return self.anthropic_model
            case ModelProvider.OPENAI:
                return self.openai_model
            case ModelProvider.GOOGLE:
                return self.google_model


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
