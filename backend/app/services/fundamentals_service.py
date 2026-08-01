"""
Fundamentals Service
====================
Fetches long-term fundamental metrics from live data feeds.
Returns None for missing fields rather than fabricating values.
"""

from __future__ import annotations

import asyncio
from typing import Any


def _to_float_or_none(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    return None


def _fetch_fundamentals_sync(ticker: str) -> dict[str, float | None]:
    import yfinance as yf

    info = yf.Ticker(ticker).info or {}

    return {
        "revenue_growth": _to_float_or_none(info.get("revenueGrowth")),
        "gross_margin": _to_float_or_none(info.get("grossMargins")),
        "operating_margin": _to_float_or_none(info.get("operatingMargins")),
        "free_cash_flow": _to_float_or_none(info.get("freeCashflow")),
        "debt_to_equity": _to_float_or_none(info.get("debtToEquity")),
        "interest_coverage": _to_float_or_none(info.get("interestCoverage")),
        "insider_ownership": _to_float_or_none(info.get("heldPercentInsiders")),
        "trailing_pe": _to_float_or_none(info.get("trailingPE")),
        "forward_pe": _to_float_or_none(info.get("forwardPE")),
        "peg_ratio": _to_float_or_none(info.get("pegRatio")),
    }


async def get_fundamentals(ticker: str) -> dict[str, float | None]:
    try:
        return await asyncio.to_thread(_fetch_fundamentals_sync, ticker)
    except Exception:
        return {
            "revenue_growth": None,
            "gross_margin": None,
            "operating_margin": None,
            "free_cash_flow": None,
            "debt_to_equity": None,
            "interest_coverage": None,
            "insider_ownership": None,
            "trailing_pe": None,
            "forward_pe": None,
            "peg_ratio": None,
        }
