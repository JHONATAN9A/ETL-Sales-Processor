"""Async SQLAlchemy engine and session factory for PostgreSQL."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    settings.database_url,
    echo=False,        # Set to True locally for SQL query logging via the logger
    pool_pre_ping=True,  # Detect stale connections before handing them to a handler
    pool_size=10,
    max_overflow=20,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

# async_sessionmaker is the modern typed replacement for sessionmaker(class_=AsyncSession)
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncSession:
    """Yield an async database session for use as a FastAPI dependency.

    Opens a session, yields it to the route handler, and guarantees the
    session is closed — even if an exception is raised — via the async
    context manager.

    Yields:
        An ``AsyncSession`` bound to the shared engine.

    Example:
```python
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db)):
            ...
```
    """
    async with async_session() as session:
        logger.debug("Database session opened")
        try:
            yield session
        except Exception:
            logger.exception("Unhandled exception inside database session — rolling back")
            await session.rollback()
            raise
        finally:
            logger.debug("Database session closed")