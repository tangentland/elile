"""Tests for security configuration."""

import pytest

from elile.security.config import (
    CSPDirective,
    HTTPSConfig,
    RateLimitConfig,
    SecurityConfig,
    SecurityHeadersConfig,
    TrustedHostsConfig,
    create_default_security_config,
)


class TestSecurityHeadersConfig:
    """Tests for SecurityHeadersConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = SecurityHeadersConfig()

        assert config.x_content_type_options == "nosniff"
        assert config.x_frame_options == "DENY"
        assert config.x_xss_protection == "1; mode=block"
        assert config.strict_transport_security is True
        assert config.hsts_max_age == 31536000
        assert config.hsts_include_subdomains is True
        assert config.hsts_preload is False
        assert config.referrer_policy == "strict-origin-when-cross-origin"
        assert config.cache_control_no_store is True

    def test_default_csp_directives(self) -> None:
        """Test default CSP directives."""
        config = SecurityHeadersConfig()

        assert "default-src" in config.content_security_policy
        assert "'self'" in config.content_security_policy["default-src"]
        assert "frame-ancestors" in config.content_security_policy
        assert "'none'" in config.content_security_policy["frame-ancestors"]

    def test_default_permissions_policy(self) -> None:
        """Test default permissions policy."""
        config = SecurityHeadersConfig()

        # Geolocation, microphone, camera should be disabled
        assert config.permissions_policy.get("geolocation") == []
        assert config.permissions_policy.get("microphone") == []
        assert config.permissions_policy.get("camera") == []

    def test_cross_origin_headers(self) -> None:
        """Test cross-origin headers defaults."""
        config = SecurityHeadersConfig()

        assert config.cross_origin_embedder_policy == "require-corp"
        assert config.cross_origin_opener_policy == "same-origin"
        assert config.cross_origin_resource_policy == "same-origin"

    def test_immutable(self) -> None:
        """Test that config is immutable (frozen dataclass)."""
        config = SecurityHeadersConfig()

        with pytest.raises(AttributeError):
            config.x_frame_options = "SAMEORIGIN"  # type: ignore[misc]


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_values(self) -> None:
        """Test default rate limit configuration."""
        config = RateLimitConfig()

        assert config.enabled is True
        assert config.requests_per_minute == 60
        assert config.requests_per_second == 10
        assert config.window_size_seconds == 60
        assert config.include_in_headers is True
        assert config.use_forwarded_for is False

    def test_exempt_paths(self) -> None:
        """Test default exempt paths."""
        config = RateLimitConfig()

        assert "/health" in config.exempt_paths
        assert "/health/db" in config.exempt_paths
        assert "/health/ready" in config.exempt_paths
        assert "/metrics" in config.exempt_paths

    def test_per_endpoint_limits(self) -> None:
        """Test per-endpoint rate limits."""
        config = RateLimitConfig()

        assert "/v1/screenings" in config.per_endpoint_limits
        assert config.per_endpoint_limits["/v1/screenings"] == 30
        assert "/v1/reports" in config.per_endpoint_limits
        assert config.per_endpoint_limits["/v1/reports"] == 20

    def test_trusted_proxies(self) -> None:
        """Test trusted proxies default."""
        config = RateLimitConfig()

        assert "127.0.0.1" in config.trusted_proxies
        assert "::1" in config.trusted_proxies


class TestTrustedHostsConfig:
    """Tests for TrustedHostsConfig."""

    def test_default_values(self) -> None:
        """Test default trusted hosts configuration."""
        config = TrustedHostsConfig()

        assert config.enabled is True
        assert "localhost" in config.allowed_hosts
        assert "127.0.0.1" in config.allowed_hosts
        assert config.redirect_to_primary is False
        assert config.primary_host is None

    def test_custom_hosts(self) -> None:
        """Test custom allowed hosts."""
        config = TrustedHostsConfig(
            allowed_hosts=frozenset({"api.elile.com", "*.elile.com"}),
            redirect_to_primary=True,
            primary_host="api.elile.com",
        )

        assert "api.elile.com" in config.allowed_hosts
        assert "*.elile.com" in config.allowed_hosts
        assert config.redirect_to_primary is True
        assert config.primary_host == "api.elile.com"


class TestHTTPSConfig:
    """Tests for HTTPSConfig."""

    def test_default_values(self) -> None:
        """Test default HTTPS configuration."""
        config = HTTPSConfig()

        assert config.enforce_https is False
        assert config.behind_proxy is True
        assert "/health" in config.exempt_paths

    def test_production_config(self) -> None:
        """Test production HTTPS configuration."""
        config = HTTPSConfig(
            enforce_https=True,
            behind_proxy=True,
        )

        assert config.enforce_https is True
        assert config.behind_proxy is True


class TestSecurityConfig:
    """Tests for SecurityConfig."""

    def test_default_values(self) -> None:
        """Test default security configuration."""
        config = SecurityConfig()

        assert config.enable_security_middleware is True
        assert isinstance(config.headers, SecurityHeadersConfig)
        assert isinstance(config.rate_limit, RateLimitConfig)
        assert isinstance(config.trusted_hosts, TrustedHostsConfig)
        assert isinstance(config.https, HTTPSConfig)


class TestCreateDefaultSecurityConfig:
    """Tests for create_default_security_config factory."""

    def test_production_config(self) -> None:
        """Test production environment configuration."""
        config = create_default_security_config("production")

        # HSTS enabled with preload
        assert config.headers.strict_transport_security is True
        assert config.headers.hsts_max_age == 31536000
        assert config.headers.hsts_preload is True

        # Rate limiting enabled with X-Forwarded-For
        assert config.rate_limit.enabled is True
        assert config.rate_limit.use_forwarded_for is True

        # Trusted hosts enabled for production domain
        assert config.trusted_hosts.enabled is True
        assert "api.elile.com" in config.trusted_hosts.allowed_hosts

        # HTTPS enforced
        assert config.https.enforce_https is True

        # Security middleware enabled
        assert config.enable_security_middleware is True

    def test_staging_config(self) -> None:
        """Test staging environment configuration."""
        config = create_default_security_config("staging")

        # HSTS with shorter max-age
        assert config.headers.strict_transport_security is True
        assert config.headers.hsts_max_age == 86400
        assert config.headers.hsts_preload is False

        # More lenient rate limiting
        assert config.rate_limit.enabled is True
        assert config.rate_limit.requests_per_minute == 120

        # HTTPS enforced
        assert config.https.enforce_https is True

    def test_development_config(self) -> None:
        """Test development environment configuration."""
        config = create_default_security_config("development")

        # No HSTS in development
        assert config.headers.strict_transport_security is False
        assert config.headers.hsts_max_age == 0

        # Very lenient rate limiting
        assert config.rate_limit.enabled is True
        assert config.rate_limit.requests_per_minute == 1000

        # No trusted hosts validation
        assert config.trusted_hosts.enabled is False

        # No HTTPS redirect
        assert config.https.enforce_https is False

        # Security middleware still enabled
        assert config.enable_security_middleware is True

    def test_test_config(self) -> None:
        """Test test environment configuration."""
        config = create_default_security_config("test")

        # Minimal security for testing
        assert config.headers.strict_transport_security is False
        assert config.rate_limit.enabled is False
        assert config.trusted_hosts.enabled is False
        assert config.https.enforce_https is False
        assert config.enable_security_middleware is False


class TestCSPDirective:
    """Tests for CSPDirective enum."""

    def test_directive_values(self) -> None:
        """Test CSP directive enum values."""
        assert CSPDirective.DEFAULT_SRC.value == "default-src"
        assert CSPDirective.SCRIPT_SRC.value == "script-src"
        assert CSPDirective.STYLE_SRC.value == "style-src"
        assert CSPDirective.IMG_SRC.value == "img-src"
        assert CSPDirective.FRAME_ANCESTORS.value == "frame-ancestors"
        assert CSPDirective.UPGRADE_INSECURE_REQUESTS.value == "upgrade-insecure-requests"
