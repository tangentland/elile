"""Security hardening module for Elile API.

This module provides comprehensive security measures including:
- Security headers (X-Frame-Options, CSP, HSTS, etc.)
- Input sanitization and validation
- Rate limiting
- CSRF protection
- SQL injection prevention utilities
- Trusted host validation
"""

from .config import (
    CSPDirective,
    RateLimitConfig,
    SecurityConfig,
    SecurityHeadersConfig,
    TrustedHostsConfig,
    create_default_security_config,
)
from .headers import (
    SecurityHeadersMiddleware,
    build_csp_header,
)
from .rate_limiter import (
    InMemoryRateLimitStore,
    RateLimiter,
    RateLimiterMiddleware,
    RateLimitExceeded,
    RateLimitResult,
    RateLimitStore,
    SlidingWindowCounter,
)
from .sanitization import (
    HTMLSanitizer,
    InputSanitizer,
    SQLSafetyChecker,
    sanitize_filename,
    sanitize_html,
    sanitize_string,
    validate_email,
    validate_url,
)

__all__ = [
    # Configuration
    "SecurityConfig",
    "SecurityHeadersConfig",
    "RateLimitConfig",
    "TrustedHostsConfig",
    "CSPDirective",
    "create_default_security_config",
    # Headers
    "SecurityHeadersMiddleware",
    "build_csp_header",
    # Rate Limiting
    "RateLimiter",
    "RateLimiterMiddleware",
    "RateLimitStore",
    "InMemoryRateLimitStore",
    "SlidingWindowCounter",
    "RateLimitResult",
    "RateLimitExceeded",
    # Sanitization
    "InputSanitizer",
    "HTMLSanitizer",
    "SQLSafetyChecker",
    "sanitize_string",
    "sanitize_html",
    "sanitize_filename",
    "validate_email",
    "validate_url",
]
