"""Database configuration and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from elile.config.settings import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db() -> None:
    """Initialize the database connection pool.

    Called during application startup to ensure the connection pool
    is ready before accepting requests.
    """
    # The engine is lazily initialized, so we just verify connectivity
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Close database connections gracefully.

    Called during application shutdown to release all connections
    in the pool.
    """
    await engine.dispose()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for obtaining a database session.

    Use this when you need a session outside of FastAPI dependency injection,
    such as in middleware or background tasks.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(query)

    Yields:
        AsyncSession: A database session that will be automatically closed
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to inject database sessions.

    Usage:
        @app.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            # Use db session here
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
