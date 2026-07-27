"""
Finnhub Market Data Client
============================
Primary source for quotes, news, and earnings calendar.
Rate limit: 60 calls/min (free tier).
Uses Postgres-backed cache + rate limiter from core/.
"""

from __future__ import annotations

import logging
from datetime import date
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
            cached = await get_cached_response(
                session=session,
                provider=self.provider_name,
                endpoint=endpoint,
                params=params,
            )
            if cached and not cached.get("_cache_stale", False):
                logger.debug("Cache hit for %s %s", endpoint, params)
                return cached

        # Acquire rate limit token
        await rate_limiter_registry.acquire(self.provider_name)

        # Make request
        response = await self._client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()

        # Store in cache
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

    async def get_quote(self, ticker: str, session: Any = None) -> QuoteData:
        """Get current quote for a ticker."""
        data = await self._request("/quote", {"symbol": ticker}, session)
        return QuoteData(
            ticker=ticker,
            current_price=data.get("c", 0.0),
            open_price=data.get("o", 0.0),
            high_price=data.get("h", 0.0),
            low_price=data.get("l", 0.0),
            previous_close=data.get("pc", 0.0),
            volume=int(data.get("v", 0)),
            change=data.get("d", 0.0),
            change_percent=data.get("dp", 0.0),
            timestamp=str(data.get("t", "")),
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
                    )
                )
        return items

    async def get_technical_indicator(
        self,
        ticker: str,
        indicator: str,
        session: Any = None,
        **kwargs: Any,
    ) -> list[TechnicalIndicator]:
        """Finnhub doesn't provide technicals — delegate to Alpha Vantage."""
        logger.warning(
            "Finnhub doesn't provide technical indicators. Use Alpha Vantage for %s/%s.",
            ticker,
            indicator,
        )
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
