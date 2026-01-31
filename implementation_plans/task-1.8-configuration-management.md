# Task 1.8: Configuration Management

## Overview

Add configuration validation to ensure the application starts with valid settings, with environment-specific checks for production safety.

**Priority**: P0 (Critical)
**Dependencies**: None

## Files Created

| File | Purpose |
|------|---------|
| `src/elile/config/validation.py` | Configuration validation utilities |
| `tests/unit/test_config_validation.py` | 20 unit tests |

## Component Design

### ValidationResult

Captures validation issues:

```python
@dataclass
class ValidationResult:
    field: str                    # Configuration field name
    severity: ValidationSeverity  # ERROR or WARNING
    message: str                  # Description of issue
    suggestion: str | None        # How to fix
```

### Validation Functions

```python
# Get list of validation issues
results = validate_configuration(settings)

# Raise on errors (use during startup)
validate_or_raise(settings)

# Get safe summary for logging
summary = get_configuration_summary(settings)
```

## Validation Rules

### Database

| Rule | Severity | Condition |
|------|----------|-----------|
| URL required | ERROR | DATABASE_URL not set |
| Valid database type | WARNING | Not postgresql or sqlite |
| Pool size minimum | WARNING | DATABASE_POOL_SIZE < 5 |
| Pool size maximum | WARNING | DATABASE_POOL_SIZE > 100 |

### Security

| Rule | Severity | Environment | Condition |
|------|----------|-------------|-----------|
| Encryption key | ERROR | production | ENCRYPTION_KEY not set |
| Encryption key | WARNING | non-prod | ENCRYPTION_KEY not set |
| API key | ERROR | production | API_SECRET_KEY not set |
| API key strength | WARNING | any | API_SECRET_KEY < 32 chars |

### API

| Rule | Severity | Condition |
|------|----------|-----------|
| Valid port | ERROR | API_PORT not in 1-65535 |
| CORS wildcard | ERROR | production + CORS_ORIGINS contains "*" |
| CORS configured | WARNING | production + no CORS_ORIGINS |

### Environment

| Rule | Severity | Condition |
|------|----------|-----------|
| Debug mode | ERROR | production + DEBUG=True |
| Log level | WARNING | production + log_level=DEBUG |

## Usage

### Application Startup

```python
from elile.config.validation import validate_or_raise

# In app.py lifespan or main()
try:
    validate_or_raise()
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    sys.exit(1)
```

### Logging Configuration Summary

```python
from elile.config.validation import get_configuration_summary

# Safe to log (excludes secrets)
summary = get_configuration_summary()
logger.info("Starting with configuration", extra=summary)
```

### Manual Validation

```python
from elile.config.validation import validate_configuration, ValidationSeverity

results = validate_configuration()
errors = [r for r in results if r.severity == ValidationSeverity.ERROR]
warnings = [r for r in results if r.severity == ValidationSeverity.WARNING]

for error in errors:
    logger.error(str(error))
for warning in warnings:
    logger.warning(str(warning))
```

## Test Summary

| Test Class | Tests | Description |
|------------|-------|-------------|
| TestValidationResult | 3 | Result formatting |
| TestDatabaseValidation | 4 | Database config checks |
| TestSecurityValidation | 4 | Security config checks |
| TestAPIValidation | 2 | API config checks |
| TestEnvironmentValidation | 2 | Environment checks |
| TestValidateOrRaise | 2 | Exception behavior |
| TestConfigurationSummary | 3 | Safe summary output |
| **Total** | **20** | |

## Configuration Summary Output

The `get_configuration_summary()` function returns a safe dictionary:

```python
{
    "environment": "development",
    "debug": True,
    "log_level": "INFO",
    "api_host": "0.0.0.0",
    "api_port": 8000,
    "cors_origins_count": 0,
    "database_pool_size": 20,
    "database_max_overflow": 10,
    "encryption_configured": False,
    "api_key_configured": False,
    "redis_configured": True,
    "default_model_provider": "anthropic",
    "rate_limit_rpm": 60,
}
```

Note: No actual secrets or connection strings are included.

## Verification

```bash
# Run tests
.venv/bin/pytest tests/unit/test_config_validation.py -v

# Test validation manually
python -c "from elile.config.validation import validate_configuration; print(validate_configuration())"
```

## Notes

- Validation is opt-in (call explicitly during startup)
- Errors block startup, warnings are logged
- Summary is safe for logging (no secrets)
- Production has stricter requirements than development
