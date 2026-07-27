"""
Per-Provider Rate Limiter
==========================
Isolated in core/ so it's swappable per provider without touching /framework.
Implements token-bucket style rate limiting with backoff for:
  - Finnhub: 60 calls/min
  - Alpha Vantage: 25 calls/day
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from app.core.exceptions import RateLimitExceededError

logger = logging.getLogger(__name__)


@dataclass
class RateLimitBucket:
    """Token bucket rate limiter for a single provider."""

    provider: str
    max_calls: int
    window_seconds: float  # e.g. 60 for per-minute, 86400 for per-day
    _timestamps: list[float] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def _prune_expired(self) -> None:
        """Remove timestamps outside the current window."""
        cutoff = time.monotonic() - self.window_seconds
        self._timestamps = [t for t in self._timestamps if t > cutoff]

    @property
    def remaining_calls(self) -> int:
        """Number of calls remaining in the current window."""
        self._prune_expired()
        return max(0, self.max_calls - len(self._timestamps))

    @property
    def is_exhausted(self) -> bool:
        """Whether the rate limit has been reached."""
        return self.remaining_calls <= 0

    @property
    def retry_after_seconds(self) -> Optional[float]:
        """Seconds until the next call can be made. None if calls are available."""
        if not self.is_exhausted:
            return None
        if not self._timestamps:
            return None
        oldest = min(self._timestamps)
        return max(0.0, oldest + self.window_seconds - time.monotonic())

    async def acquire(self, block: bool = True, max_wait: float = 30.0) -> bool:
        """
        Acquire a rate limit token.

        Args:
            block: If True, wait until a token is available (up to max_wait).
            max_wait: Maximum seconds to wait if blocking.

        Returns:
            True if acquired, False if not (only when block=False).

        Raises:
            RateLimitExceededError: If block=True and max_wait is exceeded.
        """
        async with self._lock:
            self._prune_expired()

            if len(self._timestamps) < self.max_calls:
                self._timestamps.append(time.monotonic())
                logger.debug(
                    "Rate limit token acquired for %s (%d/%d)",
                    self.provider,
                    len(self._timestamps),
                    self.max_calls,
                )
                return True

            if not block:
                return False

        # Blocking mode — wait for a slot
        waited = 0.0
        poll_interval = 0.5

        while waited < max_wait:
            await asyncio.sleep(poll_interval)
            waited += poll_interval

            async with self._lock:
                self._prune_expired()
                if len(self._timestamps) < self.max_calls:
                    self._timestamps.append(time.monotonic())
                    logger.debug(
                        "Rate limit token acquired after %.1fs wait for %s",
                        waited,
                        self.provider,
                    )
                    return True

        raise RateLimitExceededError(
            provider=self.provider,
            limit=self.max_calls,
        )

    def reset(self) -> None:
        """Reset all tracked timestamps. Use with caution."""
        self._timestamps.clear()


# ---------------------------------------------------------------------------
# Provider-specific limiters (singleton instances)
# ---------------------------------------------------------------------------
class RateLimiterRegistry:
    """
    Central registry of rate limiters, one per provider.
    Isolated from framework — swappable per provider without touching /framework.
    """

    def __init__(self) -> None:
        self._limiters: dict[str, RateLimitBucket] = {}

    def register(self, provider: str, max_calls: int, window_seconds: float) -> None:
        """Register a rate limiter for a provider."""
        self._limiters[provider] = RateLimitBucket(
            provider=provider,
            max_calls=max_calls,
            window_seconds=window_seconds,
        )
        logger.info(
            "Rate limiter registered: %s — %d calls per %ds",
            provider,
            max_calls,
            int(window_seconds),
        )

    def get(self, provider: str) -> RateLimitBucket:
        """Get the rate limiter for a provider."""
        if provider not in self._limiters:
            raise ValueError(f"No rate limiter registered for provider: {provider}")
        return self._limiters[provider]

    async def acquire(self, provider: str, block: bool = True) -> bool:
        """Convenience: acquire a token for a provider."""
        return await self.get(provider).acquire(block=block)

    def status(self) -> dict[str, dict[str, int | float | bool]]:
        """Get status of all registered limiters."""
        result = {}
        for name, bucket in self._limiters.items():
            result[name] = {
                "max_calls": bucket.max_calls,
                "remaining": bucket.remaining_calls,
                "is_exhausted": bucket.is_exhausted,
                "retry_after_seconds": bucket.retry_after_seconds or 0,
            }
        return result


# Module-level singleton
rate_limiter_registry = RateLimiterRegistry()


def init_rate_limiters() -> None:
    """Initialize rate limiters from config. Called during app startup."""
    from app.core.config import get_settings

    settings = get_settings()
    rate_limiter_registry.register(
        provider="finnhub",
        max_calls=settings.market_data.finnhub_rate_limit,
        window_seconds=60.0,  # per minute
    )
    rate_limiter_registry.register(
        provider="alpha_vantage",
        max_calls=settings.market_data.alpha_vantage_rate_limit,
        window_seconds=86400.0,  # per day
    )
    rate_limiter_registry.register(
        provider="sec_edgar",
        max_calls=10,
        window_seconds=1.0,  # 10 req/s per SEC EDGAR policy
    )
