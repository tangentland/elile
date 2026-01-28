"""Application settings loaded from environment variables."""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelProvider(str, Enum):
    """Supported model providers."""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


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
