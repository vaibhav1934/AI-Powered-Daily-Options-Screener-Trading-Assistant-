"""
Async Database Session Factory
===============================
SQLAlchemy async engine + session, configured from DatabaseConfig.
Uses asyncpg driver. Connection pooling is tuned from config.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()
_db_url = _settings.database.database_url
_db_host = (urlparse(_db_url).hostname or "").lower()
_is_supabase_pooler = "pooler.supabase.com" in _db_host

_pool_size = _settings.database.pool_size
_pool_max_overflow = _settings.database.pool_max_overflow
_connect_args: dict[str, str] = {}

if _is_supabase_pooler:
    # Supabase session poolers commonly enforce low client limits per session mode.
    _pool_size = min(_pool_size, 3)
    _pool_max_overflow = 0
    _connect_args["ssl"] = "require"
    _connect_args["statement_cache_size"] = 0

if _db_url.startswith("sqlite"):
    engine = create_async_engine(
        _db_url,
        echo=False,
    )
else:
    engine = create_async_engine(
        _db_url,
        pool_size=_pool_size,
        max_overflow=_pool_max_overflow,
        pool_recycle=_settings.database.pool_recycle,
        pool_timeout=_settings.database.pool_timeout,
        pool_use_lifo=True,
        pool_pre_ping=True,
        connect_args=_connect_args,
        echo=False,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async session, auto-closes on exit."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
