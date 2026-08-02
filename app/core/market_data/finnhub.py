"""
Finnhub Market Data Client
============================
Primary source for quotes, news, and earnings calendar.
Rate limit: 60 calls/min (free tier).
Uses Postgres-backed cache + rate limiter from core/.
"""

from __future__ import annotations

from decimal import Decimal
import logging
import asyncio
import yfinance as yf
from datetime import date, timedelta
from typing import Any, Optional

import httpx

from app.core.cache import get_cached_response, set_cached_response
from app.core.config import get_settings
from app.core.market_data.base import (
    EarningsEntry,
    NewsItem,
    QuoteData,
    TechnicalIndicator,
)
from app.core.rate_limiter import rate_limiter_registry

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubClient:
    """
    Finnhub market data client.
    Implements MarketDataProvider protocol.
    All calls go through rate limiter + cache layer.
    """

    provider_name: str = "finnhub"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._api_key = self._settings.market_data.finnhub_api_key
        self._cache_ttl = self._settings.market_data.cache_ttl_finnhub
        self._client = httpx.AsyncClient(
            base_url=FINNHUB_BASE_URL,
            timeout=30.0,
            headers={"X-Finnhub-Token": self._api_key},
        )
        try:
            rate_limiter_registry.get(self.provider_name)
        except (KeyError, ValueError):
            from app.core.rate_limiter import init_rate_limiters
            init_rate_limiters()

    async def _request(
        self,
        endpoint: str,
        params: dict[str, Any],
        session: Any = None,  # AsyncSession, optional for caching
    ) -> dict[str, Any]:
        """
        Make a rate-limited, cached request to Finnhub.
        """
        # Check cache first
        if session:
            try:
                cached = await get_cached_response(
                    session=session,
                    provider=self.provider_name,
                    endpoint=endpoint,
                    params=params,
                )
                if cached is not None:
                    is_stale = cached.get("_cache_stale", False) if isinstance(cached, dict) else False
                    if not is_stale:
                        logger.debug("Cache hit for %s %s", endpoint, params)
                        return cached
            except Exception as e:
                logger.warning("Cache read bypass for %s %s due to DB/cache error: %s", endpoint, params, e)

        # Acquire rate limit token
        await rate_limiter_registry.acquire(self.provider_name)

        # Make request
        response = await self._client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

        # Store in cache
        if session:
            try:
                await set_cached_response(
                    session=session,
                    provider=self.provider_name,
                    endpoint=endpoint,
                    params=params,
                    response_json=data,
                    ttl_seconds=self._cache_ttl,
                )
            except Exception as e:
                logger.warning("Cache write bypass for %s %s due to DB/cache error: %s", endpoint, params, e)

        return data

    async def get_quote(self, ticker: str, session: Any = None) -> QuoteData:
        """Get current quote for a ticker. Fetches price from finnhub, volume from yfinance."""
        data = await self._request("/quote", {"symbol": ticker}, session)
        
        # Free Finnhub /quote does not return volume, fetch from yfinance in thread
        try:
            volume = await asyncio.to_thread(lambda t: int(yf.Ticker(t).fast_info.last_volume or 0), ticker)
        except Exception as e:
            logger.warning(f"Failed to fetch volume for {ticker} from yfinance: {e}")
            volume = int(data.get("v") or 0)

        return QuoteData(
            ticker=ticker,
            current_price=float(data.get("c") or 0.0),
            open_price=float(data.get("o") or 0.0),
            high_price=float(data.get("h") or 0.0),
            low_price=float(data.get("l") or 0.0),
            previous_close=float(data.get("pc") or 0.0),
            volume=volume,
            change=float(data.get("d") or 0.0),
            change_percent=float(data.get("dp") or 0.0),
            timestamp=str(data.get("t") or ""),
            is_estimate=True,  # NFR-3: always estimate unless screenshot-confirmed
        )

    async def get_quotes_batch(
        self, tickers: list[str], session: Any = None
    ) -> list[QuoteData]:
        """Get quotes for multiple tickers (sequential, rate-limited)."""
        results = []
        for ticker in tickers:
            try:
                quote = await self.get_quote(ticker, session)
                results.append(quote)
            except Exception as e:
                logger.warning("Failed to get quote for %s: %s", ticker, e)
        return results

    async def get_earnings_calendar(
        self,
        from_date: date,
        to_date: date,
        session: Any = None,
    ) -> list[EarningsEntry]:
        """
        Get earnings calendar for a date range.
        FR-2: Cover full earnings calendar — every name, no skipping.
        """
        data = await self._request(
            "/calendar/earnings",
            {"from": from_date.isoformat(), "to": to_date.isoformat()},
            session,
        )

        entries = []
        for item in data.get("earningsCalendar", []):
            entries.append(
                EarningsEntry(
                    ticker=item.get("symbol", ""),
                    report_date=date.fromisoformat(item.get("date", str(from_date))),
                    fiscal_quarter=f"Q{item.get('quarter', '?')}",
                    eps_estimate=item.get("epsEstimate"),
                    eps_actual=item.get("epsActual"),
                    revenue_estimate=item.get("revenueEstimate"),
                    revenue_actual=item.get("revenueActual"),
                    is_after_hours=item.get("hour", "") == "amc",
                )
            )
        return entries

    async def get_news(
        self,
        ticker: Optional[str] = None,
        category: Optional[str] = None,
        session: Any = None,
    ) -> list[NewsItem]:
        """Get news, optionally filtered by ticker or category."""
        if ticker:
            from datetime import timedelta
            news_from = (date.today() - timedelta(days=7)).isoformat()
            news_to = date.today().isoformat()
            data = await self._request(
                "/company-news",
                {
                    "symbol": ticker,
                    "from": news_from,
                    "to": news_to,
                },
                session,
            )
        else:
            data = await self._request(
                "/news",
                {"category": category or "general"},
                session,
            )

        items = []
        if isinstance(data, list):
            for item in data:
                items.append(
                    NewsItem(
                        headline=item.get("headline", ""),
                        source=item.get("source", ""),
                        url=item.get("url", ""),
                        published_at=str(item.get("datetime", "")),
                        ticker=ticker,
                        category=item.get("category", ""),
                        summary=item.get("summary", ""),
                    )
                )
        return items

    async def get_earnings_for_symbol_window(
        self,
        ticker: str,
        start_date: date,
        end_date: date,
        session: Any = None,
    ) -> list[EarningsEntry]:
        """Fetch earnings entries for a single symbol within a date window."""
        entries = await self.get_earnings_calendar(start_date, end_date, session=session)
        ticker_u = ticker.upper()
        return [e for e in entries if e.ticker.upper() == ticker_u]

    async def get_upgrade_downgrade_actions(
        self,
        ticker: str,
        days: int = 14,
        session: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch analyst upgrade/downgrade actions for a ticker.
        Returns an empty list when unavailable.
        """
        to_date = date.today()
        from_date = to_date - timedelta(days=max(1, days))
        try:
            data = await self._request(
                "/stock/upgrade-downgrade",
                {
                    "symbol": ticker,
                    "from": from_date.isoformat(),
                    "to": to_date.isoformat(),
                },
                session,
            )
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except Exception as e:
            logger.warning("Failed to fetch analyst actions for %s: %s", ticker, e)
        return []

    async def get_company_earnings_history(
        self,
        ticker: str,
        limit: int = 8,
        session: Any = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch historical quarterly earnings rows for a symbol.
        Used as a free proxy for guidance-revision trend modeling.
        """
        try:
            data = await self._request(
                "/stock/earnings",
                {"symbol": ticker, "limit": max(1, int(limit))},
                session,
            )
            if isinstance(data, list):
                rows = [r for r in data if isinstance(r, dict)]
                rows.sort(key=lambda r: str(r.get("period", "")), reverse=True)
                return rows
        except Exception as e:
            logger.warning("Failed to fetch earnings history for %s: %s", ticker, e)
        return []

    async def get_daily_candles(
        self,
        ticker: str,
        days: int = 365,
        session: Any = None,
    ) -> dict[str, Any]:
        """
        Get daily OHLCV candle bars from Finnhub for local technical analysis.
        Returns dict with keys: 'c', 'h', 'l', 'o', 't', 'v', 's'.
        """
        import time
        now_ts = int(time.time())
        from_ts = now_ts - (days * 86400)
        try:
            data = await self._request(
                "/stock/candle",
                {
                    "symbol": ticker,
                    "resolution": "D",
                    "from": from_ts,
                    "to": now_ts,
                },
                session,
            )
            if isinstance(data, dict) and data.get("s") == "ok" and data.get("c"):
                return data
        except Exception as e:
            logger.warning("Failed to fetch daily candles for %s from Finnhub: %s", ticker, e)
        return {}

    async def get_technical_indicator(
        self,
        ticker: str,
        indicator: str,
        session: Any = None,
        **kwargs: Any,
    ) -> list[TechnicalIndicator]:
        """Finnhub doesn't provide pre-computed technicals — use get_daily_candles + local math."""
        return []

    async def get_company_profile(
        self,
        ticker: str,
        session: Any = None,
    ) -> dict[str, str]:
        """
        Get company profile data: name, sector, industry, country.
        Returns a dict with 'name' and 'sector' keys (empty strings if unavailable).
        """
        try:
            data = await self._request(
                "/stock/profile2",
                {"symbol": ticker},
                session,
            )
            return {
                "name": data.get("name", ""),
                "sector": data.get("finnhubIndustry", ""),
                "country": data.get("country", ""),
                "market_cap": data.get("marketCapitalization", 0.0),
                "website": data.get("weburl", ""),
            }
        except Exception as e:
            logger.warning("Failed to get company profile for %s: %s", ticker, e)
            return {"name": "", "sector": "", "country": "", "market_cap": 0.0, "website": ""}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()
