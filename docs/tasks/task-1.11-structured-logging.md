# Task 1.11: Structured Logging System

**Priority**: P1
**Phase**: 1 - Foundation
**Estimated Effort**: 2 days
**Dependencies**: Task 1.3 (API Framework)

## Context

Implement comprehensive structured logging for audit trails, debugging, and compliance. All data access operations must be logged with context for GDPR/FCRA compliance and security auditing.

**Architecture Reference**: [07-compliance.md](../docs/architecture/07-compliance.md) - Audit Trail
**Related**: [02-core-system.md](../docs/architecture/02-core-system.md) - Logging

## Objectives

1. Configure structured logging with JSON output
2. Create audit logger for compliance events
3. Add correlation IDs for request tracing
4. Implement sensitive data redaction
5. Support multiple log destinations (file, stdout, external services)

## Technical Approach

### Logging Configuration

```python
# src/elile/config/logging.py
import logging
import sys
from typing import Optional
from pydantic_settings import BaseSettings

class LoggingSettings(BaseSettings):
    """Logging configuration."""

    log_level: str = "INFO"
    log_format: str = "json"  # json or text
    log_file: Optional[str] = None
    log_file_max_bytes: int = 10_000_000  # 10MB
    log_file_backup_count: int = 5

    # Audit logging
    audit_log_enabled: bool = True
    audit_log_file: str = "logs/audit.log"

    # External logging
    datadog_enabled: bool = False
    datadog_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_prefix = "ELILE_"

logging_settings = LoggingSettings()
```

### Structured Logger

```python
# src/elile/logging/logger.py
import logging
import json
import traceback
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from elile.config.logging import logging_settings

# Context variables for request correlation
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
org_id_var: ContextVar[Optional[str]] = ContextVar("org_id", default=None)

class StructuredLogger:
    """Structured JSON logger."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, logging_settings.log_level))

    def _build_log_entry(
        self,
        level: str,
        message: str,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """Build structured log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "logger": self.logger.name,
        }

        # Add context
        if correlation_id := correlation_id_var.get():
            entry["correlation_id"] = correlation_id
        if user_id := user_id_var.get():
            entry["user_id"] = user_id
        if org_id := org_id_var.get():
            entry["org_id"] = org_id

        # Add custom fields
        entry.update(kwargs)

        return entry

    def _redact_sensitive(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive fields."""
        sensitive_fields = {
            "password", "ssn", "social_security_number",
            "credit_card", "api_key", "token", "secret"
        }

        redacted = {}
        for key, value in data.items():
            if any(field in key.lower() for field in sensitive_fields):
                redacted[key] = "***REDACTED***"
            elif isinstance(value, dict):
                redacted[key] = self._redact_sensitive(value)
            else:
                redacted[key] = value

        return redacted

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        entry = self._build_log_entry("INFO", message, **kwargs)
        self.logger.info(json.dumps(entry))

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        entry = self._build_log_entry("WARNING", message, **kwargs)
        self.logger.warning(json.dumps(entry))

    def error(
        self,
        message: str,
        exc: Optional[Exception] = None,
        **kwargs: Any
    ) -> None:
        """Log error message."""
        entry = self._build_log_entry("ERROR", message, **kwargs)

        if exc:
            entry["exception"] = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc()
            }

        self.logger.error(json.dumps(entry))

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        entry = self._build_log_entry("DEBUG", message, **kwargs)
        self.logger.debug(json.dumps(entry))

def get_logger(name: str) -> StructuredLogger:
    """Get structured logger instance."""
    return StructuredLogger(name)
```

### Audit Logger

```python
# src/elile/logging/audit.py
from typing import Optional, Dict, Any
from enum import Enum
from elile.logging.logger import StructuredLogger

class AuditEventType(str, Enum):
    """Audit event types."""

    # Data access
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"

    # Screening events
    SCREENING_CREATED = "screening_created"
    SCREENING_COMPLETED = "screening_completed"
    SCREENING_CANCELLED = "screening_cancelled"

    # Subject events
    SUBJECT_CREATED = "subject_created"
    SUBJECT_UPDATED = "subject_updated"
    SUBJECT_DELETED = "subject_deleted"

    # Consent events
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"

    # Security events
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    PERMISSION_DENIED = "permission_denied"

class AuditLogger:
    """Audit event logger for compliance."""

    def __init__(self):
        self.logger = StructuredLogger("elile.audit")

    def log_event(
        self,
        event_type: AuditEventType,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        details: Optional[Dict[str, Any]] = None,
        locale: Optional[str] = None
    ) -> None:
        """Log audit event."""
        self.logger.info(
            f"Audit: {action} {resource_type}",
            event_type=event_type.value,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            locale=locale,
            details=details or {}
        )

    def log_data_access(
        self,
        actor_id: str,
        subject_id: str,
        fields_accessed: list[str],
        purpose: str,
        locale: str
    ) -> None:
        """Log GDPR/FCRA data access."""
        self.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            actor_id=actor_id,
            resource_type="subject",
            resource_id=subject_id,
            action="access",
            result="success",
            locale=locale,
            details={
                "fields_accessed": fields_accessed,
                "purpose": purpose
            }
        )

    def log_screening_event(
        self,
        actor_id: str,
        screening_id: str,
        action: str,
        result: str,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log screening lifecycle event."""
        self.log_event(
            event_type=AuditEventType.SCREENING_CREATED,
            actor_id=actor_id,
            resource_type="screening",
            resource_id=screening_id,
            action=action,
            result=result,
            details=details
        )

# Global audit logger
audit_logger = AuditLogger()
```

### Request Context Middleware

```python
# src/elile/logging/middleware.py
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from elile.logging.logger import correlation_id_var, user_id_var, org_id_var

class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Middleware to set logging context from request."""

    async def dispatch(self, request: Request, call_next):
        # Generate or extract correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4())
        )
        correlation_id_var.set(correlation_id)

        # Extract user/org context from auth
        if hasattr(request.state, "user"):
            user_id_var.set(request.state.user.id)
            org_id_var.set(request.state.user.org_id)

        response = await call_next(request)

        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id

        return response
```

### Performance Logger

```python
# src/elile/logging/performance.py
import time
from functools import wraps
from typing import Callable, TypeVar
from elile.logging.logger import get_logger

T = TypeVar("T")
logger = get_logger("elile.performance")

def log_performance(threshold_ms: float = 1000):
    """Decorator to log slow operations."""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> T:
            start = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                if duration_ms > threshold_ms:
                    logger.warning(
                        f"Slow operation: {func.__name__}",
                        duration_ms=duration_ms,
                        threshold_ms=threshold_ms,
                        function=func.__name__
                    )

        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> T:
            start = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start) * 1000
                if duration_ms > threshold_ms:
                    logger.warning(
                        f"Slow operation: {func.__name__}",
                        duration_ms=duration_ms,
                        threshold_ms=threshold_ms,
                        function=func.__name__
                    )

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
```

## Implementation Checklist

### Core Infrastructure
- [ ] Configure structured logging
- [ ] Create StructuredLogger class
- [ ] Add JSON formatter
- [ ] Implement context variables
- [ ] Create logging middleware

### Audit Logging
- [ ] Implement AuditLogger
- [ ] Define audit event types
- [ ] Add data access logging
- [ ] Create compliance log format
- [ ] Add log retention policies

### Advanced Features
- [ ] Implement sensitive data redaction
- [ ] Add performance logging
- [ ] Create correlation ID tracking
- [ ] Support external log aggregation
- [ ] Add log sampling for high volume

### Testing
- [ ] Test log formatting
- [ ] Test context propagation
- [ ] Test sensitive data redaction
- [ ] Test audit event logging
- [ ] Verify compliance requirements

## Testing Strategy

```python
# tests/logging/test_audit_logger.py
import pytest
from elile.logging.audit import audit_logger, AuditEventType

def test_log_data_access():
    """Test GDPR data access logging."""
    audit_logger.log_data_access(
        actor_id="user_123",
        subject_id="sub_456",
        fields_accessed=["name", "email", "ssn"],
        purpose="employment_screening",
        locale="US-CA"
    )
    # Verify log entry created with required fields

def test_sensitive_redaction():
    """Test sensitive field redaction."""
    from elile.logging.logger import StructuredLogger

    logger = StructuredLogger("test")
    data = {
        "name": "John Doe",
        "ssn": "123-45-6789",
        "email": "john@example.com"
    }

    redacted = logger._redact_sensitive(data)
    assert redacted["ssn"] == "***REDACTED***"
    assert redacted["name"] == "John Doe"
```

## Success Criteria

- [ ] All API requests have correlation IDs
- [ ] Audit logs capture all data access events
- [ ] Sensitive fields automatically redacted
- [ ] Log retention meets compliance requirements
- [ ] Performance logging identifies slow operations
- [ ] Logs are searchable and parseable

## Documentation

- Document audit event types
- Create logging best practices guide
- Add examples for common log queries
- Document retention and archival policies

## Future Enhancements

- Add log aggregation (Datadog, ELK)
- Implement log-based alerting
- Add anomaly detection in logs
- Create log analytics dashboard
