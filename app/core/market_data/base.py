"""
Market Data Provider Protocol
===============================
Base interface for all market data providers.
Decoupled from framework — providers are swappable without touching /framework.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional, Protocol

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Data models for market data responses
# ---------------------------------------------------------------------------
class QuoteData(BaseModel):
    """Stock quote data from a market data provider."""

    ticker: str
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    previous_close: float
    volume: int
    change: float
    change_percent: float
    timestamp: str
    is_estimate: bool = True  # NFR-3: mark as estimate unless screenshot-confirmed


class EarningsEntry(BaseModel):
    """Single entry from an earnings calendar."""

    ticker: str
    report_date: date
    fiscal_quarter: Optional[str] = None
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    is_after_hours: bool = False


class NewsItem(BaseModel):
    """Single news item from a market data provider."""

    headline: str
    source: str
    url: str
    published_at: str
    ticker: Optional[str] = None
    category: Optional[str] = None
    sentiment: Optional[str] = None
    summary: Optional[str] = None


class TechnicalIndicator(BaseModel):
    """Technical indicator data point."""

    ticker: str
    indicator: str  # e.g., "RSI", "SMA_50", "MACD"
    value: float
    timestamp: str
    metadata: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Provider protocol — all providers implement this
# ---------------------------------------------------------------------------
class MarketDataProvider(Protocol):
    """
    Protocol for market data providers.
    Each provider implements this interface. Providers are isolated in core/
    and swappable without touching /framework.
    """

    provider_name: str

    async def get_quote(self, ticker: str) -> QuoteData:
        """Get current quote for a ticker."""
        ...

    async def get_quotes_batch(self, tickers: list[str]) -> list[QuoteData]:
        """Get quotes for multiple tickers."""
        ...

    async def get_earnings_calendar(
        self, from_date: date, to_date: date
    ) -> list[EarningsEntry]:
        """Get earnings calendar for a date range."""
        ...

    async def get_news(
        self, ticker: Optional[str] = None, category: Optional[str] = None
    ) -> list[NewsItem]:
        """Get news, optionally filtered by ticker or category."""
        ...

    async def get_technical_indicator(
        self, ticker: str, indicator: str, **kwargs: Any
    ) -> list[TechnicalIndicator]:
        """Get technical indicator data for a ticker."""
        ...
