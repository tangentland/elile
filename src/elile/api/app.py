"""FastAPI application factory."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from elile.api.middleware import (
    AuthenticationMiddleware,
    ErrorHandlingMiddleware,
    RequestContextMiddleware,
    RequestLoggingMiddleware,
    TenantValidationMiddleware,
)
from elile.api.routers import health_router
from elile.config.settings import Settings, get_settings


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

    # Initialize database connection pool
    try:
        from elile.db.config import init_db
        await init_db()
        logger.info("Database connection pool initialized")
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


def _configure_middleware(app: FastAPI, settings: Settings) -> None:
    """Configure middleware stack.

    Middleware order (outermost to innermost execution):
    1. RequestLoggingMiddleware - Logs all requests
    2. ErrorHandlingMiddleware - Converts exceptions to HTTP responses
    3. CORSMiddleware - Handles CORS (if configured)
    4. AuthenticationMiddleware - Validates Bearer token
    5. TenantValidationMiddleware - Validates X-Tenant-ID
    6. RequestContextMiddleware - Sets ContextVar for request context

    Note: Middleware is added in reverse order because Starlette
    processes them from last-added to first-added.

    Args:
        app: FastAPI application
        settings: Application settings
    """
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

    # Outermost: Request logging
    app.add_middleware(RequestLoggingMiddleware)


def _configure_routers(app: FastAPI) -> None:
    """Configure API routers.

    Args:
        app: FastAPI application
    """
    # Health check endpoints (no prefix - at root level)
    app.include_router(health_router)

    # Future: Add versioned API routers
    # app.include_router(v1_router, prefix="/v1")


# Convenience for running directly
# Usage: uvicorn elile.api.app:app
app = create_app()
