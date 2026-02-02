"""Security headers middleware.

Implements comprehensive security headers including:
- Content-Security-Policy (CSP)
- X-Frame-Options (clickjacking protection)
- X-Content-Type-Options (MIME sniffing prevention)
- X-XSS-Protection (XSS filter for older browsers)
- Strict-Transport-Security (HSTS)
- Referrer-Policy
- Permissions-Policy
- Cross-Origin headers (COEP, COOP, CORP)
"""

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from elile.security.config import SecurityHeadersConfig

if TYPE_CHECKING:
    from fastapi import Request, Response


def build_csp_header(directives: dict[str, list[str]]) -> str:
    """Build Content-Security-Policy header value from directives.

    Args:
        directives: Mapping of directive names to their values

    Returns:
        Formatted CSP header string

    Example:
        >>> build_csp_header({"default-src": ["'self'"], "img-src": ["'self'", "https:"]})
        "default-src 'self'; img-src 'self' https:"
    """
    parts = []
    for directive, values in directives.items():
        if values:
            parts.append(f"{directive} {' '.join(values)}")
        else:
            # Directives without values (like upgrade-insecure-requests)
            parts.append(directive)
    return "; ".join(parts)


def build_permissions_policy_header(permissions: dict[str, list[str]]) -> str:
    """Build Permissions-Policy header value.

    Args:
        permissions: Mapping of feature names to allowed origins

    Returns:
        Formatted Permissions-Policy header string

    Example:
        >>> build_permissions_policy_header({"geolocation": [], "camera": ["self"]})
        "geolocation=(), camera=(self)"
    """
    parts = []
    for feature, origins in permissions.items():
        if not origins:
            parts.append(f"{feature}=()")
        else:
            origins_str = " ".join(origins)
            parts.append(f"{feature}=({origins_str})")
    return ", ".join(parts)


def build_hsts_header(
    max_age: int,
    include_subdomains: bool = True,
    preload: bool = False,
) -> str:
    """Build Strict-Transport-Security header value.

    Args:
        max_age: Max-age value in seconds
        include_subdomains: Include includeSubDomains directive
        preload: Include preload directive

    Returns:
        Formatted HSTS header string
    """
    parts = [f"max-age={max_age}"]
    if include_subdomains:
        parts.append("includeSubDomains")
    if preload:
        parts.append("preload")
    return "; ".join(parts)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to all responses.

    This middleware adds comprehensive security headers to protect against:
    - Clickjacking (X-Frame-Options, CSP frame-ancestors)
    - MIME type sniffing (X-Content-Type-Options)
    - XSS attacks (X-XSS-Protection, CSP)
    - Man-in-the-middle attacks (HSTS)
    - Information leakage (Referrer-Policy)
    - Feature abuse (Permissions-Policy)
    - Cross-origin attacks (COEP, COOP, CORP)

    Example:
        from fastapi import FastAPI
        from elile.security.headers import SecurityHeadersMiddleware
        from elile.security.config import SecurityHeadersConfig

        app = FastAPI()
        config = SecurityHeadersConfig()
        app.add_middleware(SecurityHeadersMiddleware, config=config)
    """

    def __init__(
        self,
        app: ASGIApp,
        config: SecurityHeadersConfig | None = None,
        exempt_paths: frozenset[str] | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            config: Security headers configuration
            exempt_paths: Paths that should not receive security headers
        """
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()
        self.exempt_paths = exempt_paths or frozenset()

        # Pre-build static headers for performance
        self._static_headers = self._build_static_headers()

    def _build_static_headers(self) -> dict[str, str]:
        """Pre-build headers that don't change per-request."""
        headers: dict[str, str] = {}
        config = self.config

        # X-Content-Type-Options
        if config.x_content_type_options:
            headers["X-Content-Type-Options"] = config.x_content_type_options

        # X-Frame-Options
        if config.x_frame_options:
            headers["X-Frame-Options"] = config.x_frame_options

        # X-XSS-Protection (legacy but still useful for older browsers)
        if config.x_xss_protection:
            headers["X-XSS-Protection"] = config.x_xss_protection

        # Strict-Transport-Security (HSTS)
        if config.strict_transport_security and config.hsts_max_age > 0:
            headers["Strict-Transport-Security"] = build_hsts_header(
                max_age=config.hsts_max_age,
                include_subdomains=config.hsts_include_subdomains,
                preload=config.hsts_preload,
            )

        # Content-Security-Policy
        if config.content_security_policy:
            headers["Content-Security-Policy"] = build_csp_header(config.content_security_policy)

        # Referrer-Policy
        if config.referrer_policy:
            headers["Referrer-Policy"] = config.referrer_policy

        # Permissions-Policy
        if config.permissions_policy:
            headers["Permissions-Policy"] = build_permissions_policy_header(
                config.permissions_policy
            )

        # Cross-Origin headers
        if config.cross_origin_embedder_policy:
            headers["Cross-Origin-Embedder-Policy"] = config.cross_origin_embedder_policy

        if config.cross_origin_opener_policy:
            headers["Cross-Origin-Opener-Policy"] = config.cross_origin_opener_policy

        if config.cross_origin_resource_policy:
            headers["Cross-Origin-Resource-Policy"] = config.cross_origin_resource_policy

        return headers

    async def dispatch(
        self,
        request: "Request",
        call_next: Callable[["Request"], Awaitable["Response"]],
    ) -> "Response":
        """Process request and add security headers to response."""
        # Skip exempt paths
        if request.url.path in self.exempt_paths:
            response: "Response" = await call_next(request)
            return response

        # Get response
        response = await call_next(request)

        # Add security headers
        # Note: response.headers is MutableHeaders which supports dict-like access
        for header_name, header_value in self._static_headers.items():
            # Don't overwrite existing headers (allow per-route customization)
            if header_name not in response.headers:
                response.headers[header_name] = header_value

        # Add Cache-Control for sensitive endpoints if configured
        # Apply to API endpoints (not static assets)
        if (
            self.config.cache_control_no_store
            and request.url.path.startswith("/v1/")
            and "Cache-Control" not in response.headers
        ):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        return response


class TrustedHostMiddleware(BaseHTTPMiddleware):
    """Middleware that validates the Host header.

    Protects against host header attacks by rejecting requests
    with untrusted Host headers.

    Example:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts={"api.elile.com", "*.elile.com"},
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        allowed_hosts: frozenset[str] | None = None,
        redirect_to_primary: bool = False,
        primary_host: str | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            allowed_hosts: Set of allowed host patterns (supports * wildcard)
            redirect_to_primary: Whether to redirect non-primary hosts
            primary_host: Primary host for redirects
        """
        super().__init__(app)
        self.allowed_hosts = allowed_hosts or frozenset({"localhost", "127.0.0.1"})
        self.redirect_to_primary = redirect_to_primary
        self.primary_host = primary_host

        # Pre-compile wildcard patterns
        self._wildcard_patterns: list[str] = []
        self._exact_hosts: set[str] = set()

        for host in self.allowed_hosts:
            if host.startswith("*."):
                self._wildcard_patterns.append(host[2:])  # Remove "*."
            else:
                self._exact_hosts.add(host.lower())

    def _is_host_allowed(self, host: str) -> bool:
        """Check if a host is allowed."""
        host_lower = host.lower()

        # Remove port if present
        if ":" in host_lower:
            host_lower = host_lower.rsplit(":", 1)[0]

        # Check exact match
        if host_lower in self._exact_hosts:
            return True

        # Check wildcard patterns
        for pattern in self._wildcard_patterns:
            if host_lower.endswith(pattern) or host_lower == pattern[1:]:
                return True

        return False

    async def dispatch(
        self,
        request: "Request",
        call_next: Callable[["Request"], Awaitable["Response"]],
    ) -> "Response":
        """Process request and validate Host header."""
        from fastapi.responses import JSONResponse, RedirectResponse

        host = request.headers.get("host", "")

        if not self._is_host_allowed(host):
            if self.redirect_to_primary and self.primary_host:
                # Redirect to primary host
                url = str(request.url).replace(host, self.primary_host)
                return RedirectResponse(url=url, status_code=301)
            else:
                # Reject the request
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "invalid_host",
                        "message": "Invalid Host header",
                    },
                )

        response: "Response" = await call_next(request)
        return response


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware that redirects HTTP to HTTPS.

    Supports both direct HTTPS detection and proxy scenarios
    where X-Forwarded-Proto header indicates the original protocol.

    Example:
        app.add_middleware(
            HTTPSRedirectMiddleware,
            behind_proxy=True,
            exempt_paths={"/health"},
        )
    """

    def __init__(
        self,
        app: ASGIApp,
        behind_proxy: bool = True,
        exempt_paths: frozenset[str] | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            app: The ASGI application
            behind_proxy: Whether to trust X-Forwarded-Proto header
            exempt_paths: Paths that allow HTTP access
        """
        super().__init__(app)
        self.behind_proxy = behind_proxy
        self.exempt_paths = exempt_paths or frozenset()

    def _is_https(self, request: "Request") -> bool:
        """Check if the request is using HTTPS."""
        # Direct HTTPS
        if request.url.scheme == "https":
            return True

        # Behind proxy - check X-Forwarded-Proto
        if self.behind_proxy:
            proto = request.headers.get("x-forwarded-proto", "").lower()
            if proto == "https":
                return True

        return False

    async def dispatch(
        self,
        request: "Request",
        call_next: Callable[["Request"], Awaitable["Response"]],
    ) -> "Response":
        """Process request and redirect to HTTPS if needed."""
        from fastapi.responses import RedirectResponse

        # Skip exempt paths
        if request.url.path in self.exempt_paths:
            response: "Response" = await call_next(request)
            return response

        # Check if already HTTPS
        if self._is_https(request):
            response = await call_next(request)
            return response

        # Build HTTPS URL
        https_url = request.url.replace(scheme="https")

        # Redirect to HTTPS
        return RedirectResponse(url=str(https_url), status_code=301)
