"""Configuration validation for startup checks.

Validates that required configuration is present and valid before the
application starts accepting requests.

Usage:
    from elile.config.validation import validate_configuration

    # During startup
    errors = validate_configuration()
    if errors:
        for error in errors:
            logger.error(f"Configuration error: {error}")
        sys.exit(1)
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from elile.config.settings import Settings, get_settings


logger = logging.getLogger("elile.config")


class ValidationSeverity(str, Enum):
    """Severity of configuration validation issues."""

    ERROR = "error"  # Must be fixed, app cannot start
    WARNING = "warning"  # Should be fixed, app can start but may have issues


@dataclass
class ValidationResult:
    """Result of a configuration validation check."""

    field: str
    severity: ValidationSeverity
    message: str
    suggestion: str | None = None

    def __str__(self) -> str:
        prefix = "ERROR" if self.severity == ValidationSeverity.ERROR else "WARNING"
        result = f"[{prefix}] {self.field}: {self.message}"
        if self.suggestion:
            result += f"\n  Suggestion: {self.suggestion}"
        return result


def validate_configuration(settings: Settings | None = None) -> list[ValidationResult]:
    """Validate application configuration.

    Runs all configuration checks and returns a list of validation results.

    Args:
        settings: Settings to validate (default: global settings)

    Returns:
        List of validation results (empty if all checks pass)
    """
    if settings is None:
        settings = get_settings()

    results: list[ValidationResult] = []

    # Run all validators
    results.extend(_validate_database(settings))
    results.extend(_validate_security(settings))
    results.extend(_validate_api(settings))
    results.extend(_validate_redis(settings))
    results.extend(_validate_environment(settings))

    return results


def validate_or_raise(settings: Settings | None = None) -> None:
    """Validate configuration and raise if errors found.

    Args:
        settings: Settings to validate

    Raises:
        ConfigurationError: If any validation errors are found
    """
    results = validate_configuration(settings)
    errors = [r for r in results if r.severity == ValidationSeverity.ERROR]

    if errors:
        error_messages = "\n".join(str(e) for e in errors)
        raise ConfigurationError(f"Configuration validation failed:\n{error_messages}")

    # Log warnings
    warnings = [r for r in results if r.severity == ValidationSeverity.WARNING]
    for warning in warnings:
        logger.warning(str(warning))


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


# =============================================================================
# Validators
# =============================================================================


def _validate_database(settings: Settings) -> list[ValidationResult]:
    """Validate database configuration."""
    results: list[ValidationResult] = []

    # Check DATABASE_URL format
    if not settings.DATABASE_URL:
        results.append(
            ValidationResult(
                field="DATABASE_URL",
                severity=ValidationSeverity.ERROR,
                message="Database URL is not configured",
                suggestion="Set DATABASE_URL environment variable",
            )
        )
    elif not settings.DATABASE_URL.startswith(("postgresql", "sqlite")):
        results.append(
            ValidationResult(
                field="DATABASE_URL",
                severity=ValidationSeverity.WARNING,
                message=f"Unexpected database type in URL: {settings.DATABASE_URL[:20]}...",
                suggestion="Elile is designed for PostgreSQL or SQLite",
            )
        )

    # Check pool size
    if settings.DATABASE_POOL_SIZE < 5:
        results.append(
            ValidationResult(
                field="DATABASE_POOL_SIZE",
                severity=ValidationSeverity.WARNING,
                message=f"Pool size {settings.DATABASE_POOL_SIZE} may be too small for production",
                suggestion="Recommended minimum is 5 connections",
            )
        )

    if settings.DATABASE_POOL_SIZE > 100:
        results.append(
            ValidationResult(
                field="DATABASE_POOL_SIZE",
                severity=ValidationSeverity.WARNING,
                message=f"Pool size {settings.DATABASE_POOL_SIZE} may be excessive",
                suggestion="Consider reducing to prevent database connection exhaustion",
            )
        )

    return results


def _validate_security(settings: Settings) -> list[ValidationResult]:
    """Validate security configuration."""
    results: list[ValidationResult] = []

    # Production requires encryption key
    if settings.ENVIRONMENT == "production":
        if settings.ENCRYPTION_KEY is None:
            results.append(
                ValidationResult(
                    field="ENCRYPTION_KEY",
                    severity=ValidationSeverity.ERROR,
                    message="Encryption key is required in production",
                    suggestion="Generate with: python -c 'from elile.core.encryption import generate_key, key_to_string; print(key_to_string(generate_key()))'",
                )
            )

        if settings.API_SECRET_KEY is None:
            results.append(
                ValidationResult(
                    field="API_SECRET_KEY",
                    severity=ValidationSeverity.ERROR,
                    message="API secret key is required in production",
                    suggestion="Generate a secure random string for API authentication",
                )
            )
    else:
        # Warnings for non-production
        if settings.ENCRYPTION_KEY is None:
            results.append(
                ValidationResult(
                    field="ENCRYPTION_KEY",
                    severity=ValidationSeverity.WARNING,
                    message="Encryption key not configured - sensitive data will be stored unencrypted",
                    suggestion="Set ENCRYPTION_KEY for data protection even in development",
                )
            )

    # Check API key strength if set
    if settings.API_SECRET_KEY is not None:
        key_value = settings.API_SECRET_KEY.get_secret_value()
        if len(key_value) < 32:
            results.append(
                ValidationResult(
                    field="API_SECRET_KEY",
                    severity=ValidationSeverity.WARNING,
                    message="API secret key is short and may be weak",
                    suggestion="Use at least 32 characters for secure API keys",
                )
            )

    return results


def _validate_api(settings: Settings) -> list[ValidationResult]:
    """Validate API configuration."""
    results: list[ValidationResult] = []

    # Check port range
    if not (1 <= settings.API_PORT <= 65535):
        results.append(
            ValidationResult(
                field="API_PORT",
                severity=ValidationSeverity.ERROR,
                message=f"Invalid port number: {settings.API_PORT}",
                suggestion="Use a port between 1 and 65535",
            )
        )

    # Check CORS in production
    if settings.ENVIRONMENT == "production":
        if not settings.CORS_ORIGINS:
            results.append(
                ValidationResult(
                    field="CORS_ORIGINS",
                    severity=ValidationSeverity.WARNING,
                    message="No CORS origins configured - API will reject cross-origin requests",
                    suggestion="Set CORS_ORIGINS to allow specific domains",
                )
            )
        elif "*" in settings.CORS_ORIGINS:
            results.append(
                ValidationResult(
                    field="CORS_ORIGINS",
                    severity=ValidationSeverity.ERROR,
                    message="Wildcard CORS origin not allowed in production",
                    suggestion="Specify exact allowed origins",
                )
            )

    return results


def _validate_redis(settings: Settings) -> list[ValidationResult]:
    """Validate Redis configuration."""
    results: list[ValidationResult] = []

    if settings.REDIS_URL:
        if not settings.REDIS_URL.startswith("redis://"):
            results.append(
                ValidationResult(
                    field="REDIS_URL",
                    severity=ValidationSeverity.WARNING,
                    message="Redis URL has unexpected format",
                    suggestion="Expected format: redis://host:port/db",
                )
            )

    return results


def _validate_environment(settings: Settings) -> list[ValidationResult]:
    """Validate environment-specific settings."""
    results: list[ValidationResult] = []

    # Debug should be off in production
    if settings.ENVIRONMENT == "production" and settings.DEBUG:
        results.append(
            ValidationResult(
                field="DEBUG",
                severity=ValidationSeverity.ERROR,
                message="Debug mode must be disabled in production",
                suggestion="Set DEBUG=false for production",
            )
        )

    # Log level recommendations
    if settings.ENVIRONMENT == "production" and settings.log_level == "DEBUG":
        results.append(
            ValidationResult(
                field="log_level",
                severity=ValidationSeverity.WARNING,
                message="DEBUG log level in production may expose sensitive data",
                suggestion="Use INFO or WARNING for production",
            )
        )

    return results


def get_configuration_summary(settings: Settings | None = None) -> dict[str, Any]:
    """Get a summary of current configuration (safe for logging).

    Excludes sensitive values like API keys and connection strings.

    Args:
        settings: Settings to summarize

    Returns:
        Dictionary with configuration summary
    """
    if settings is None:
        settings = get_settings()

    return {
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
        "log_level": settings.log_level,
        "api_host": settings.API_HOST,
        "api_port": settings.API_PORT,
        "cors_origins_count": len(settings.CORS_ORIGINS),
        "database_pool_size": settings.DATABASE_POOL_SIZE,
        "database_max_overflow": settings.DATABASE_MAX_OVERFLOW,
        "encryption_configured": settings.ENCRYPTION_KEY is not None,
        "api_key_configured": settings.API_SECRET_KEY is not None,
        "redis_configured": bool(settings.REDIS_URL),
        "default_model_provider": settings.default_model_provider.value,
        "rate_limit_rpm": settings.rate_limit_rpm,
    }
