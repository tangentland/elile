"""Tests for security headers middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from elile.security.config import SecurityHeadersConfig
from elile.security.headers import (
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
    TrustedHostMiddleware,
    build_csp_header,
    build_hsts_header,
    build_permissions_policy_header,
)


class TestBuildCSPHeader:
    """Tests for CSP header building."""

    def test_simple_directive(self) -> None:
        """Test simple CSP directive."""
        result = build_csp_header({"default-src": ["'self'"]})
        assert result == "default-src 'self'"

    def test_multiple_values(self) -> None:
        """Test directive with multiple values."""
        result = build_csp_header({"img-src": ["'self'", "data:", "https:"]})
        assert result == "img-src 'self' data: https:"

    def test_multiple_directives(self) -> None:
        """Test multiple directives."""
        result = build_csp_header(
            {
                "default-src": ["'self'"],
                "img-src": ["'self'", "https:"],
            }
        )
        assert "default-src 'self'" in result
        assert "img-src 'self' https:" in result
        assert "; " in result

    def test_empty_directive_value(self) -> None:
        """Test directive with no value (e.g., upgrade-insecure-requests)."""
        result = build_csp_header({"upgrade-insecure-requests": []})
        assert result == "upgrade-insecure-requests"


class TestBuildHSTSHeader:
    """Tests for HSTS header building."""

    def test_basic_hsts(self) -> None:
        """Test basic HSTS header."""
        result = build_hsts_header(max_age=31536000)
        assert "max-age=31536000" in result
        assert "includeSubDomains" in result
        assert "preload" not in result

    def test_hsts_without_subdomains(self) -> None:
        """Test HSTS without includeSubDomains."""
        result = build_hsts_header(max_age=86400, include_subdomains=False)
        assert "max-age=86400" in result
        assert "includeSubDomains" not in result

    def test_hsts_with_preload(self) -> None:
        """Test HSTS with preload."""
        result = build_hsts_header(max_age=31536000, preload=True)
        assert "preload" in result


class TestBuildPermissionsPolicyHeader:
    """Tests for Permissions-Policy header building."""

    def test_disabled_features(self) -> None:
        """Test disabling features."""
        result = build_permissions_policy_header(
            {
                "geolocation": [],
                "camera": [],
            }
        )
        assert "geolocation=()" in result
        assert "camera=()" in result

    def test_enabled_features(self) -> None:
        """Test enabling features for self."""
        result = build_permissions_policy_header(
            {
                "fullscreen": ["self"],
            }
        )
        assert "fullscreen=(self)" in result

    def test_mixed_features(self) -> None:
        """Test mixed enabled and disabled features."""
        result = build_permissions_policy_header(
            {
                "geolocation": [],
                "fullscreen": ["self"],
            }
        )
        assert "geolocation=()" in result
        assert "fullscreen=(self)" in result
        assert ", " in result


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    @pytest.fixture
    def app_with_security_headers(self) -> FastAPI:
        """Create test app with security headers middleware."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app_with_security_headers: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app_with_security_headers)

    def test_x_content_type_options(self, client: TestClient) -> None:
        """Test X-Content-Type-Options header."""
        response = client.get("/test")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client: TestClient) -> None:
        """Test X-Frame-Options header."""
        response = client.get("/test")
        assert response.headers.get("X-Frame-Options") == "DENY"

    def test_x_xss_protection(self, client: TestClient) -> None:
        """Test X-XSS-Protection header."""
        response = client.get("/test")
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"

    def test_hsts_header(self, client: TestClient) -> None:
        """Test Strict-Transport-Security header."""
        response = client.get("/test")
        hsts = response.headers.get("Strict-Transport-Security")
        assert hsts is not None
        assert "max-age=" in hsts
        assert "includeSubDomains" in hsts

    def test_csp_header(self, client: TestClient) -> None:
        """Test Content-Security-Policy header."""
        response = client.get("/test")
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src" in csp
        assert "'self'" in csp

    def test_referrer_policy(self, client: TestClient) -> None:
        """Test Referrer-Policy header."""
        response = client.get("/test")
        assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_permissions_policy(self, client: TestClient) -> None:
        """Test Permissions-Policy header."""
        response = client.get("/test")
        pp = response.headers.get("Permissions-Policy")
        assert pp is not None
        assert "geolocation=()" in pp

    def test_cross_origin_headers(self, client: TestClient) -> None:
        """Test cross-origin isolation headers."""
        response = client.get("/test")
        assert response.headers.get("Cross-Origin-Embedder-Policy") == "require-corp"
        assert response.headers.get("Cross-Origin-Opener-Policy") == "same-origin"
        assert response.headers.get("Cross-Origin-Resource-Policy") == "same-origin"

    def test_custom_config(self) -> None:
        """Test middleware with custom configuration."""
        app = FastAPI()
        config = SecurityHeadersConfig(
            x_frame_options="SAMEORIGIN",
            strict_transport_security=False,
        )
        app.add_middleware(SecurityHeadersMiddleware, config=config)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test")

        assert response.headers.get("X-Frame-Options") == "SAMEORIGIN"
        assert "Strict-Transport-Security" not in response.headers

    def test_exempt_paths(self) -> None:
        """Test exempt paths don't get security headers."""
        app = FastAPI()
        app.add_middleware(
            SecurityHeadersMiddleware,
            exempt_paths=frozenset({"/health"}),
        )

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/api")
        def api() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)

        # Exempt path should not have security headers
        response = client.get("/health")
        assert "X-Frame-Options" not in response.headers

        # Non-exempt path should have security headers
        response = client.get("/api")
        assert "X-Frame-Options" in response.headers

    def test_cache_control_for_api_endpoints(self, client: TestClient) -> None:
        """Test cache control headers for API endpoints."""
        # Create app with v1 endpoint
        app = FastAPI()
        config = SecurityHeadersConfig(cache_control_no_store=True)
        app.add_middleware(SecurityHeadersMiddleware, config=config)

        @app.get("/v1/test")
        def v1_test() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/v1/test")

        assert response.headers.get("Cache-Control") == "no-store, no-cache, must-revalidate"
        assert response.headers.get("Pragma") == "no-cache"


class TestTrustedHostMiddleware:
    """Tests for TrustedHostMiddleware."""

    @pytest.fixture
    def app_with_trusted_hosts(self) -> FastAPI:
        """Create test app with trusted hosts middleware."""
        app = FastAPI()
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=frozenset({"localhost", "127.0.0.1", "api.elile.com", "*.elile.com"}),
        )

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app_with_trusted_hosts: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(app_with_trusted_hosts)

    def test_allowed_host(self, client: TestClient) -> None:
        """Test request with allowed host."""
        response = client.get("/test", headers={"Host": "localhost"})
        assert response.status_code == 200

    def test_allowed_host_with_port(self) -> None:
        """Test request with allowed host including port."""
        app = FastAPI()
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=frozenset({"localhost"}),
        )

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app)
        response = client.get("/test", headers={"Host": "localhost:8000"})
        assert response.status_code == 200

    def test_wildcard_host(self, client: TestClient) -> None:
        """Test request with wildcard-matched host."""
        response = client.get("/test", headers={"Host": "staging.elile.com"})
        assert response.status_code == 200

    def test_blocked_host(self, client: TestClient) -> None:
        """Test request with blocked host."""
        response = client.get("/test", headers={"Host": "evil.com"})
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_host"

    def test_redirect_to_primary(self) -> None:
        """Test redirect to primary host."""
        app = FastAPI()
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=frozenset({"api.elile.com", "www.elile.com"}),
            redirect_to_primary=True,
            primary_host="api.elile.com",
        )

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app, follow_redirects=False)
        response = client.get("/test", headers={"Host": "evil.com"})
        assert response.status_code == 301


class TestHTTPSRedirectMiddleware:
    """Tests for HTTPSRedirectMiddleware."""

    @pytest.fixture
    def app_with_https_redirect(self) -> FastAPI:
        """Create test app with HTTPS redirect middleware."""
        app = FastAPI()
        app.add_middleware(
            HTTPSRedirectMiddleware,
            behind_proxy=True,
            exempt_paths=frozenset({"/health"}),
        )

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/health")
        def health() -> dict[str, str]:
            return {"status": "ok"}

        return app

    @pytest.fixture
    def client(self, app_with_https_redirect: FastAPI) -> TestClient:
        """Create test client that doesn't follow redirects."""
        return TestClient(app_with_https_redirect, follow_redirects=False)

    def test_http_redirects_to_https(self, client: TestClient) -> None:
        """Test that HTTP requests are redirected to HTTPS."""
        response = client.get("/test")
        assert response.status_code == 301
        assert "https://" in response.headers.get("location", "")

    def test_https_passes_through(self) -> None:
        """Test that HTTPS requests pass through."""
        app = FastAPI()
        app.add_middleware(HTTPSRedirectMiddleware, behind_proxy=True)

        @app.get("/test")
        def test_endpoint() -> dict[str, str]:
            return {"status": "ok"}

        client = TestClient(app, follow_redirects=False)
        # Simulate HTTPS via X-Forwarded-Proto
        response = client.get("/test", headers={"X-Forwarded-Proto": "https"})
        assert response.status_code == 200

    def test_exempt_paths_not_redirected(self, client: TestClient) -> None:
        """Test that exempt paths are not redirected."""
        response = client.get("/health")
        assert response.status_code == 200
