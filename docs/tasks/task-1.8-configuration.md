# Task 1.8: Configuration Management

## Overview

Implement environment-based configuration using Pydantic Settings with validation, support for .env files, and environment-specific overrides (dev/staging/prod). Central configuration for all services.

**Priority**: P0 | **Effort**: 1 day | **Status**: Not Started

## Dependencies

- External: Pydantic 2.5+, python-dotenv

## Implementation Checklist

- [ ] Create Settings class with Pydantic BaseSettings
- [ ] Add validation for all config fields
- [ ] Support .env file loading
- [ ] Environment-specific configuration
- [ ] Singleton settings instance
- [ ] Write config validation tests
- [ ] Document all environment variables

## Key Implementation

```python
# src/elile/config/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, RedisDsn, SecretStr
from typing import Literal

class Settings(BaseSettings):
    """Application configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Environment
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # Database
    database_url: PostgresDsn
    database_pool_size: int = 20
    database_max_overflow: int = 10

    # Redis
    redis_url: RedisDsn = Field(default="redis://localhost:6379/0")
    redis_cache_ttl: int = 3600  # seconds

    # Security
    encryption_key: SecretStr  # Base64-encoded 32-byte key
    api_secret_key: SecretStr  # JWT signing key

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]

    # AI Models
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    google_api_key: SecretStr | None = None

    # Providers
    worldcheck_api_key: SecretStr | None = None
    experian_api_key: SecretStr | None = None

    # Features
    enable_real_providers: bool = False
    enable_monitoring: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

# Singleton instance
settings = Settings()

# src/elile/config/__init__.py
from .settings import settings

__all__ = ["settings"]
```

## Testing Requirements

### Unit Tests
- Settings load from environment variables
- Validation errors for invalid URLs
- SecretStr fields not logged/printed
- Default values applied correctly

### Integration Tests
- .env.test file loaded in tests
- Environment overrides work
- Missing required fields raise error

**Coverage Target**: 80%+

## Acceptance Criteria

- [ ] Settings class with Pydantic validation
- [ ] All config loaded from environment variables
- [ ] .env file support for local development
- [ ] Validation errors for invalid config
- [ ] Secrets (API keys) use SecretStr
- [ ] Settings singleton accessible across app
- [ ] .env.example file documented

## Deliverables

- `src/elile/config/settings.py`
- `src/elile/config/__init__.py`
- `.env.example` (with all variables documented)
- `.env.test` (for testing)
- `tests/unit/test_settings.py`

## References

- All phases depend on configuration
- Future: Task 12.2 (Vault for production secrets)

---

*Task Owner: [TBD]* | *Created: 2026-01-29*
