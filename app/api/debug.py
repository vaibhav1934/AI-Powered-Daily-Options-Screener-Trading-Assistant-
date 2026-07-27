
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any
from datetime import date
from pydantic import BaseModel
import uuid
import logging

from app.db.session import get_db, async_session_factory
from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.technicals import fetch_technicals
from app.framework.engine import run_full_scan
from app.core.time_gate import get_cst_now, is_fomc_day, is_friday, is_past_cutoff

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/debug", tags=["debug"])

class TickerScanRequest(BaseModel):
    ticker: str
    scan_date: Optional[date] = None

@router.post("/scan-ticker")
async def debug_scan_ticker(
    req: TickerScanRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Test the 50-factor pipeline on a SINGLE ticker.
    Bypasses the earnings calendar check and forces a scan.
    """
    scan_date = req.scan_date or date.today()
    now = get_cst_now()
    
    macro_context = {
        "kospi_change_percent": 0.0,
        "ceasefire_headline": False,
        "is_fomc_day": is_fomc_day(now),
        "fomc_time_past_1245": is_fomc_day(now) and now.hour >= 12 and now.minute >= 45,
        "current_time_cst": now.strftime("%I:%M %p"),
        "is_past_cutoff": False, # force false for debug
        "is_friday": is_friday(now),
    }

    client = FinnhubClient()
    try:
        quote = await client.get_quote(req.ticker, session=session)
        tech_data = await fetch_technicals(req.ticker, quote.current_price, session)
        
        ticker_data = {
            "ticker": req.ticker,
            "change_percent": quote.change_percent,
            "current_price": quote.current_price,
            "open_price": quote.open_price,
            "high_price": quote.high_price,
            "low_price": quote.low_price,
            "previous_close": quote.previous_close,
            "has_earnings_today": True, # assume true for debug
            "rsi": tech_data.get("rsi"),
            "sma_50": tech_data.get("sma_50"),
            "sma_200": tech_data.get("sma_200"),
            "is_at_ath": tech_data.get("is_at_ath", False),
        }
    finally:
        await client.close()

    # Run engine on this single ticker
    results = run_full_scan([ticker_data], macro_context)
    if not results:
        return {"error": "Ticker failed evaluation entirely (e.g. F01 Universe Filter dropped it)."}
        
    ctx = results[0]
    return {
        "ticker": ctx.ticker,
        "status": ctx.status,
        "conviction_score": ctx.conviction_score,
        "factors_triggered": [f.factor_id for f in ctx.factors_triggered],
        "factors_failed": [f.factor_id for f in ctx.factors_failed],
        "veto_rules": ctx.veto_rules_applied
    }

@router.get("/finnhub/quote/{ticker}")
async def debug_finnhub_quote(
    ticker: str,
    session: AsyncSession = Depends(get_db),
):
    client = FinnhubClient()
    try:
        quote = await client.get_quote(ticker, session=session)
        return {"ticker": ticker, "quote": quote}
    finally:
        await client.close()

@router.get("/alphavantage/technicals/{ticker}")
async def debug_alphavantage_technicals(
    ticker: str,
    price: float = 100.0,
    session: AsyncSession = Depends(get_db),
):
    tech_data = await fetch_technicals(ticker, price, session)
    return {"ticker": ticker, "tech_data": tech_data}

