"""
Postgres-Backed Cache
======================
Caches market data API responses in the market_data_cache table.
Required to stay within Alpha Vantage's 25 calls/day free tier.
Serves stale-but-labeled data rather than re-hitting the API.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import MarketDataCache


def _hash_params(params: dict[str, Any]) -> str:
    """SHA-256 hash of serialized params for cache key."""
    serialized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()


async def get_cached_response(
    session: AsyncSession,
    provider: str,
    endpoint: str,
    params: dict[str, Any],
) -> Optional[dict[str, Any]]:
    """
    Retrieve a cached response if it exists and hasn't expired.
    Returns None if no valid cache entry exists.
    Stale entries are returned with a '_cache_stale' flag rather than
    silently serving expired data.
    """
    params_hash = _hash_params(params)

    result = await session.execute(
        select(MarketDataCache).where(
            MarketDataCache.provider == provider,
            MarketDataCache.endpoint == endpoint,
            MarketDataCache.params_hash == params_hash,
        )
    )
    cached = result.scalar_one_or_none()

    if cached is None:
        return None

    # Check TTL
    expires_at = cached.cached_at + timedelta(seconds=cached.ttl_seconds)
    now = datetime.now(timezone.utc)

    if isinstance(cached.response_json, dict):
        response = dict(cached.response_json)
        response["_cached_at"] = cached.cached_at.isoformat()
        if now > expires_at:
            response["_cache_stale"] = True
            response["_cache_expired_at"] = expires_at.isoformat()
        else:
            response["_cache_stale"] = False
        return response
    elif isinstance(cached.response_json, list):
        return list(cached.response_json)
    return cached.response_json


async def set_cached_response(
    session: AsyncSession,
    provider: str,
    endpoint: str,
    params: dict[str, Any],
    response_json: Any,
    ttl_seconds: int,
) -> None:
    """
    Store or update a cached response.
    Uses upsert semantics — if the cache key already exists, update it.
    """
    params_hash = _hash_params(params)

    # Check for existing entry
    result = await session.execute(
        select(MarketDataCache).where(
            MarketDataCache.provider == provider,
            MarketDataCache.endpoint == endpoint,
            MarketDataCache.params_hash == params_hash,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.response_json = response_json
        existing.cached_at = datetime.now(timezone.utc)
        existing.ttl_seconds = ttl_seconds
    else:
        entry = MarketDataCache(
            provider=provider,
            endpoint=endpoint,
            params_hash=params_hash,
            response_json=response_json,
            ttl_seconds=ttl_seconds,
        )
        session.add(entry)

    await session.flush()


async def invalidate_cache(
    session: AsyncSession,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> int:
    """
    Invalidate cached entries. Optionally filter by provider and/or endpoint.
    Returns the number of entries deleted.
    """
    from sqlalchemy import delete

    stmt = delete(MarketDataCache)
    if provider:
        stmt = stmt.where(MarketDataCache.provider == provider)
    if endpoint:
        stmt = stmt.where(MarketDataCache.endpoint == endpoint)

    result = await session.execute(stmt)
    await session.flush()
    return result.rowcount  # type: ignore[return-value]
