"""Security configuration types and defaults.

Provides centralized configuration for all security features including
headers, rate limiting, trusted hosts, and CORS settings.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class CSPDirective(str, Enum):
    """Content Security Policy directive names."""

    DEFAULT_SRC = "default-src"
    SCRIPT_SRC = "script-src"
    STYLE_SRC = "style-src"
    IMG_SRC = "img-src"
    FONT_SRC = "font-src"
    CONNECT_SRC = "connect-src"
    MEDIA_SRC = "media-src"
    OBJECT_SRC = "object-src"
    FRAME_SRC = "frame-src"
    FRAME_ANCESTORS = "frame-ancestors"
    BASE_URI = "base-uri"
    FORM_ACTION = "form-action"
    UPGRADE_INSECURE_REQUESTS = "upgrade-insecure-requests"
    BLOCK_ALL_MIXED_CONTENT = "block-all-mixed-content"


@dataclass(frozen=True, slots=True)
class SecurityHeadersConfig:
    """Configuration for security headers.

    Attributes:
        x_content_type_options: Prevent MIME type sniffing
        x_frame_options: Clickjacking protection
        x_xss_protection: XSS filter (legacy, but still useful for older browsers)
        strict_transport_security: HSTS configuration
        hsts_max_age: HSTS max-age in seconds (default: 1 year)
        hsts_include_subdomains: Include subdomains in HSTS
        hsts_preload: Enable HSTS preload (requires submission to preload list)
        content_security_policy: CSP directives
        referrer_policy: Referrer policy
        permissions_policy: Feature/permissions policy
        cache_control_no_store: Add no-store for sensitive endpoints
        cross_origin_embedder_policy: COEP header
        cross_origin_opener_policy: COOP header
        cross_origin_resource_policy: CORP header
    """

    x_content_type_options: str = "nosniff"
    x_frame_options: Literal["DENY", "SAMEORIGIN"] = "DENY"
    x_xss_protection: str = "1; mode=block"

    # HSTS settings
    strict_transport_security: bool = True
    hsts_max_age: int = 31536000  # 1 year
    hsts_include_subdomains: bool = True
    hsts_preload: bool = False  # Only enable after adding to preload list

    # CSP directives (mapping of directive -> values)
    content_security_policy: dict[str, list[str]] = field(
        default_factory=lambda: {
            "default-src": ["'self'"],
            "script-src": ["'self'"],
            "style-src": ["'self'", "'unsafe-inline'"],  # unsafe-inline for inline styles
            "img-src": ["'self'", "data:", "https:"],
            "font-src": ["'self'"],
            "connect-src": ["'self'"],
            "frame-ancestors": ["'none'"],
            "base-uri": ["'self'"],
            "form-action": ["'self'"],
            "object-src": ["'none'"],
        }
    )

    # Referrer policy
    referrer_policy: str = "strict-origin-when-cross-origin"

    # Permissions/Feature policy
    permissions_policy: dict[str, list[str]] = field(
        default_factory=lambda: {
            "geolocation": [],  # Disable
            "microphone": [],  # Disable
            "camera": [],  # Disable
            "payment": [],  # Disable
            "usb": [],  # Disable
        }
    )

    # Cache control for sensitive responses
    cache_control_no_store: bool = True

    # Cross-origin isolation headers
    cross_origin_embedder_policy: str | None = "require-corp"
    cross_origin_opener_policy: str | None = "same-origin"
    cross_origin_resource_policy: str | None = "same-origin"


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    """Configuration for rate limiting.

    Attributes:
        enabled: Whether rate limiting is active
        requests_per_minute: Default rate limit per minute
        requests_per_second: Burst rate limit per second
        window_size_seconds: Sliding window size for rate calculation
        include_in_headers: Include rate limit info in response headers
        exempt_paths: Paths that bypass rate limiting
        per_endpoint_limits: Custom limits for specific endpoints
        use_forwarded_for: Trust X-Forwarded-For header for client IP
        trusted_proxies: List of trusted proxy IPs when using X-Forwarded-For
    """

    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_second: int = 10  # Burst capacity
    window_size_seconds: int = 60
    include_in_headers: bool = True

    # Exempt paths (e.g., health checks)
    exempt_paths: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "/health",
                "/health/db",
                "/health/ready",
                "/metrics",
            }
        )
    )

    # Per-endpoint limits (path pattern -> requests per minute)
    per_endpoint_limits: dict[str, int] = field(
        default_factory=lambda: {
            "/v1/screenings": 30,  # Lower limit for expensive operations
            "/v1/reports": 20,  # Report generation is resource-intensive
        }
    )

    # Client identification
    use_forwarded_for: bool = False  # Only enable behind trusted proxy
    trusted_proxies: frozenset[str] = field(default_factory=lambda: frozenset({"127.0.0.1", "::1"}))


@dataclass(frozen=True, slots=True)
class TrustedHostsConfig:
    """Configuration for trusted hosts validation.

    Attributes:
        enabled: Whether to validate Host header
        allowed_hosts: List of allowed hosts (supports wildcards like *.example.com)
        redirect_to_primary: Redirect non-primary hosts to primary
        primary_host: Primary host for redirects
    """

    enabled: bool = True
    allowed_hosts: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "localhost",
                "127.0.0.1",
                "::1",
            }
        )
    )
    redirect_to_primary: bool = False
    primary_host: str | None = None


@dataclass(frozen=True, slots=True)
class HTTPSConfig:
    """Configuration for HTTPS enforcement.

    Attributes:
        enforce_https: Redirect HTTP to HTTPS
        exempt_paths: Paths that allow HTTP (e.g., health checks)
        behind_proxy: Whether app is behind a TLS-terminating proxy
    """

    enforce_https: bool = False  # Enable in production
    exempt_paths: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "/health",
                "/health/db",
                "/health/ready",
            }
        )
    )
    behind_proxy: bool = True  # Trust X-Forwarded-Proto


@dataclass(frozen=True, slots=True)
class SecurityConfig:
    """Master security configuration.

    Aggregates all security-related configurations into a single object.

    Attributes:
        headers: Security headers configuration
        rate_limit: Rate limiting configuration
        trusted_hosts: Trusted hosts configuration
        https: HTTPS enforcement configuration
        enable_security_middleware: Master switch for security middleware
    """

    headers: SecurityHeadersConfig = field(default_factory=SecurityHeadersConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    trusted_hosts: TrustedHostsConfig = field(default_factory=TrustedHostsConfig)
    https: HTTPSConfig = field(default_factory=HTTPSConfig)

    # Master switch
    enable_security_middleware: bool = True


def create_default_security_config(
    environment: Literal["development", "staging", "production", "test"] = "development",
) -> SecurityConfig:
    """Create security configuration appropriate for the environment.

    Args:
        environment: The deployment environment

    Returns:
        SecurityConfig appropriate for the environment
    """
    if environment == "production":
        return SecurityConfig(
            headers=SecurityHeadersConfig(
                strict_transport_security=True,
                hsts_max_age=31536000,
                hsts_include_subdomains=True,
                hsts_preload=True,
            ),
            rate_limit=RateLimitConfig(
                enabled=True,
                requests_per_minute=60,
                use_forwarded_for=True,  # Typically behind load balancer
            ),
            trusted_hosts=TrustedHostsConfig(
                enabled=True,
                allowed_hosts=frozenset(
                    {
                        "api.elile.com",
                        "*.elile.com",
                    }
                ),
            ),
            https=HTTPSConfig(
                enforce_https=True,
                behind_proxy=True,
            ),
            enable_security_middleware=True,
        )
    elif environment == "staging":
        return SecurityConfig(
            headers=SecurityHeadersConfig(
                strict_transport_security=True,
                hsts_max_age=86400,  # 1 day for staging
                hsts_preload=False,
            ),
            rate_limit=RateLimitConfig(
                enabled=True,
                requests_per_minute=120,  # More lenient for testing
            ),
            trusted_hosts=TrustedHostsConfig(
                enabled=True,
                allowed_hosts=frozenset(
                    {
                        "staging.elile.com",
                        "*.staging.elile.com",
                        "localhost",
                    }
                ),
            ),
            https=HTTPSConfig(
                enforce_https=True,
                behind_proxy=True,
            ),
            enable_security_middleware=True,
        )
    elif environment == "test":
        return SecurityConfig(
            headers=SecurityHeadersConfig(
                strict_transport_security=False,  # Don't need HSTS in tests
            ),
            rate_limit=RateLimitConfig(
                enabled=False,  # Disable rate limiting in tests
            ),
            trusted_hosts=TrustedHostsConfig(
                enabled=False,  # Accept any host in tests
            ),
            https=HTTPSConfig(
                enforce_https=False,
            ),
            enable_security_middleware=False,  # Minimal security for testing
        )
    else:  # development
        return SecurityConfig(
            headers=SecurityHeadersConfig(
                strict_transport_security=False,  # No HSTS in development
                hsts_max_age=0,
            ),
            rate_limit=RateLimitConfig(
                enabled=True,
                requests_per_minute=1000,  # Very lenient for development
            ),
            trusted_hosts=TrustedHostsConfig(
                enabled=False,  # Accept any host in development
            ),
            https=HTTPSConfig(
                enforce_https=False,  # No HTTPS in local development
            ),
            enable_security_middleware=True,
        )
