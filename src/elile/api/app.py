"""FastAPI application factory."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from elile.api.middleware import (
    AuthenticationMiddleware,
    ErrorHandlingMiddleware,
    ObservabilityMiddleware,
    RequestContextMiddleware,
    RequestLoggingMiddleware,
    TenantValidationMiddleware,
)
from elile.api.routers import health_router, v1_router
from elile.config.settings import Settings, get_settings
from elile.observability import (
    TracingManager,
    get_metrics_manager,
    get_tracing_manager,
)
from elile.security import (
    InMemoryRateLimitStore,
    RateLimiterMiddleware,
    SecurityHeadersMiddleware,
    create_default_security_config,
)
from elile.security.headers import HTTPSRedirectMiddleware, TrustedHostMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    This is the application factory that assembles all components:
    - Middleware (in correct order)
    - Routers
    - Exception handlers
    - Lifespan management

    Args:
        settings: Optional settings override (useful for testing)

    Returns:
        Configured FastAPI application

    Example:
        # Production
        app = create_app()

        # Testing
        test_settings = Settings(DEBUG=True, API_SECRET_KEY=SecretStr("test"))
        app = create_app(settings=test_settings)

        # Run with uvicorn
        uvicorn elile.api.app:create_app --factory
    """
    if settings is None:
        settings = get_settings()

    # Create app with metadata
    app = FastAPI(
        title="Elile API",
        description="Employee risk assessment platform API",
        version="0.1.0",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=_lifespan,
    )

    # Store settings on app state for access in dependencies
    app.state.settings = settings

    # Configure middleware (order matters - outermost to innermost)
    _configure_middleware(app, settings)

    # Include routers
    _configure_routers(app)

    return app


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager.

    Handles startup and shutdown events.

    Args:
        app: FastAPI application

    Yields:
        None (context for application lifetime)
    """
    # Startup
    import logging

    logger = logging.getLogger("elile.api")
    logger.info("Starting Elile API...")

    # Initialize observability (tracing and metrics)
    tracing_manager: TracingManager | None = None
    try:
        tracing_manager = get_tracing_manager()
        tracing_manager.initialize()
        tracing_manager.instrument_fastapi(app)
        tracing_manager.instrument_httpx()
        logger.info("OpenTelemetry tracing initialized")

        metrics_manager = get_metrics_manager()
        metrics_manager.initialize(
            service_name="elile",
            service_version="0.1.0",
            environment=(
                app.state.settings.ENVIRONMENT if hasattr(app.state, "settings") else "development"
            ),
        )
        logger.info("Prometheus metrics initialized")
    except Exception as e:
        logger.warning(f"Observability initialization error: {e}")

    # Initialize database connection pool
    try:
        from elile.db.config import init_db

        await init_db()
        logger.info("Database connection pool initialized")

        # Instrument SQLAlchemy if tracing is enabled
        if tracing_manager and tracing_manager.config.enabled:
            try:
                from elile.db.config import get_engine

                engine = get_engine()
                if engine:
                    tracing_manager.instrument_sqlalchemy(engine)
                    logger.info("SQLAlchemy tracing instrumented")
            except Exception as e:
                logger.warning(f"SQLAlchemy instrumentation skipped: {e}")
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    yield

    # Shutdown
    logger.info("Shutting down Elile API...")

    # Close database connections
    try:
        from elile.db.config import close_db

        await close_db()
        logger.info("Database connections closed")
    except Exception as e:
        logger.warning(f"Database shutdown error: {e}")

    # Shutdown tracing
    if tracing_manager:
        try:
            tracing_manager.shutdown()
            logger.info("OpenTelemetry tracing shutdown")
        except Exception as e:
            logger.warning(f"Tracing shutdown error: {e}")


def _configure_middleware(app: FastAPI, settings: Settings) -> None:
    """Configure middleware stack.

    Middleware order (outermost to innermost execution):
    1. ObservabilityMiddleware - Records metrics and traces
    2. SecurityHeadersMiddleware - Adds security headers
    3. HTTPSRedirectMiddleware - Redirects HTTP to HTTPS (production)
    4. TrustedHostMiddleware - Validates Host header (production)
    5. RateLimiterMiddleware - Rate limiting
    6. RequestLoggingMiddleware - Logs all requests
    7. ErrorHandlingMiddleware - Converts exceptions to HTTP responses
    8. CORSMiddleware - Handles CORS (if configured)
    9. AuthenticationMiddleware - Validates Bearer token
    10. TenantValidationMiddleware - Validates X-Tenant-ID
    11. RequestContextMiddleware - Sets ContextVar for request context

    Note: Middleware is added in reverse order because Starlette
    processes them from last-added to first-added.

    Args:
        app: FastAPI application
        settings: Application settings
    """
    # Get security configuration for the environment
    security_config = create_default_security_config(settings.ENVIRONMENT)

    # Add middleware in reverse order (last added = outermost)

    # Innermost: Request context (needs tenant and actor from upstream)
    app.add_middleware(RequestContextMiddleware)

    # Tenant validation (needs auth first)
    app.add_middleware(TenantValidationMiddleware)

    # Authentication
    app.add_middleware(AuthenticationMiddleware)

    # CORS (if origins configured)
    if hasattr(settings, "CORS_ORIGINS") and settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Error handling (catches exceptions from all inner middleware)
    app.add_middleware(ErrorHandlingMiddleware)

    # Rate limiting (if enabled)
    if security_config.rate_limit.enabled:
        app.add_middleware(
            RateLimiterMiddleware,
            store=InMemoryRateLimitStore(),
            config=security_config.rate_limit,
        )

    # Request logging
    app.add_middleware(RequestLoggingMiddleware)

    # Trusted hosts validation (if enabled - typically in production)
    if security_config.trusted_hosts.enabled:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=security_config.trusted_hosts.allowed_hosts,
            redirect_to_primary=security_config.trusted_hosts.redirect_to_primary,
            primary_host=security_config.trusted_hosts.primary_host,
        )

    # HTTPS redirect (if enabled - typically in production)
    if security_config.https.enforce_https:
        app.add_middleware(
            HTTPSRedirectMiddleware,
            behind_proxy=security_config.https.behind_proxy,
            exempt_paths=security_config.https.exempt_paths,
        )

    # Security headers (always enabled unless explicitly disabled)
    if security_config.enable_security_middleware:
        app.add_middleware(
            SecurityHeadersMiddleware,
            config=security_config.headers,
        )

    # Outermost: Observability (metrics and tracing)
    app.add_middleware(ObservabilityMiddleware)


def _configure_routers(app: FastAPI) -> None:
    """Configure API routers.

    Args:
        app: FastAPI application
    """
    # Health check endpoints (no prefix - at root level)
    app.include_router(health_router)

    # API v1 routers (screenings, etc.)
    app.include_router(v1_router)


# Convenience for running directly
# Usage: uvicorn elile.api.app:app
app = create_app()
