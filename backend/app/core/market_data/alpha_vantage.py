"""
Alpha Vantage Market Data Client
==================================
Primary source for technical indicators.
Rate limit: 25 calls/day (free tier) — this is the binding constraint.
Cache is REQUIRED — TTL of 24h for technicals. Serve stale-but-labeled data.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.cache import get_cached_response, set_cached_response
from app.core.config import get_settings
from app.core.market_data.base import TechnicalIndicator
from app.core.rate_limiter import rate_limiter_registry

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Mapping of indicator names to Alpha Vantage function names
INDICATOR_FUNCTION_MAP: dict[str, str] = {
    "RSI": "RSI",
    "SMA": "SMA",
    "EMA": "EMA",
    "MACD": "MACD",
    "BBANDS": "BBANDS",
    "STOCH": "STOCH",
    "ADX": "ADX",
    "CCI": "CCI",
    "AROON": "AROON",
    "OBV": "OBV",
    "VWAP": "VWAP",
}


class AlphaVantageClient:
    """
    Alpha Vantage market data client — technical indicators only.
    25 calls/day free tier: caching is mandatory, not optional.
    """

    provider_name: str = "alpha_vantage"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._api_key = self._settings.market_data.alpha_vantage_api_key
        self._cache_ttl = self._settings.market_data.cache_ttl_alpha_vantage
        self._client = httpx.AsyncClient(
            base_url=ALPHA_VANTAGE_BASE_URL,
            timeout=30.0,
        )

    async def _request(
        self,
        params: dict[str, Any],
        session: Any = None,
    ) -> dict[str, Any]:
        """
        Make a rate-limited, heavily-cached request to Alpha Vantage.
        Given the 25/day limit, cache aggressively — stale data is preferable
        to exhausting the quota.
        """
        endpoint = params.get("function", "unknown")

        # Check cache FIRST — critical for 25/day limit
        if session:
            cached = await get_cached_response(
                session=session,
                provider=self.provider_name,
                endpoint=endpoint,
                params=params,
            )
            if cached is not None:
                # Serve even stale data rather than burning API calls
                stale_flag = cached.get("_cache_stale", False)
                if stale_flag:
                    logger.info(
                        "Serving stale cached data for %s %s (preserving daily quota)",
                        endpoint,
                        params.get("symbol", "?"),
                    )
                return cached

        # Acquire rate limit token (25/day — may block for a LONG time or fail)
        limiter = rate_limiter_registry.get(self.provider_name)
        remaining = limiter.remaining_calls
        logger.info(
            "Alpha Vantage API call: %s (remaining today: %d/25)",
            endpoint,
            remaining,
        )

        await rate_limiter_registry.acquire(self.provider_name, block=False)

        # Make request
        full_params = {**params, "apikey": self._api_key}
        response = await self._client.get("", params=full_params)
        response.raise_for_status()
        data = response.json()

        # Check for API error responses
        if "Error Message" in data:
            logger.error("Alpha Vantage error: %s", data["Error Message"])
            raise ValueError(f"Alpha Vantage API error: {data['Error Message']}")

        if "Note" in data:
            # Rate limit hit on their side
            logger.warning("Alpha Vantage rate limit note: %s", data["Note"])

        # Cache with long TTL (24h default) — preserve daily quota
        if session:
            await set_cached_response(
                session=session,
                provider=self.provider_name,
                endpoint=endpoint,
                params=params,
                response_json=data,
                ttl_seconds=self._cache_ttl,
            )

        return data

    async def get_technical_indicator(
        self,
        ticker: str,
        indicator: str,
        session: Any = None,
        interval: str = "daily",
        time_period: int = 14,
        series_type: str = "close",
        **kwargs: Any,
    ) -> list[TechnicalIndicator]:
        """
        Get a technical indicator for a ticker.
        Uses the Alpha Vantage Technical Indicator API.
        """
        function = INDICATOR_FUNCTION_MAP.get(indicator.upper())
        if not function:
            logger.warning("Unsupported indicator: %s", indicator)
            return []

        params: dict[str, Any] = {
            "function": function,
            "symbol": ticker,
            "interval": interval,
            "time_period": time_period,
            "series_type": series_type,
        }
        params.update(kwargs)

        data = await self._request(params, session)

        # Parse the response — Alpha Vantage nests data under a dynamic key
        results: list[TechnicalIndicator] = []
        for key, value in data.items():
            if key.startswith("Technical Analysis"):
                # value is a dict of {date: {indicator_name: value}}
                for date_str, indicators in value.items():
                    for ind_name, ind_value in indicators.items():
                        try:
                            results.append(
                                TechnicalIndicator(
                                    ticker=ticker,
                                    indicator=f"{indicator.upper()}_{ind_name}",
                                    value=float(ind_value),
                                    timestamp=date_str,
                                )
                            )
                        except (ValueError, TypeError):
                            continue
                    # Only return the most recent data points
                    if len(results) >= 30:
                        break
                break

        return results

    async def get_rsi(
        self,
        ticker: str,
        session: Any = None,
        time_period: int = 14,
    ) -> Optional[float]:
        """Convenience: get the most recent RSI value for a ticker."""
        results = await self.get_technical_indicator(
            ticker=ticker,
            indicator="RSI",
            session=session,
            time_period=time_period,
        )
        if results:
            return results[0].value
        return None

    async def get_sma(
        self,
        ticker: str,
        session: Any = None,
        time_period: int = 50,
    ) -> Optional[float]:
        """Convenience: get the most recent SMA value for a ticker."""
        results = await self.get_technical_indicator(
            ticker=ticker,
            indicator="SMA",
            session=session,
            time_period=time_period,
        )
        if results:
            return results[0].value
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
