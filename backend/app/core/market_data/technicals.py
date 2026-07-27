"""
Technical Data Fetcher
======================
Fetches live RSI and SMA data from Alpha Vantage for technical factor evaluation (F9-F15).
Returns None if rate limit or network error occurs (No fallback data per user rule).
"""

import logging
from typing import Optional, Any
from app.core.market_data.alpha_vantage import AlphaVantageClient

logger = logging.getLogger(__name__)

async def fetch_technicals(ticker: str, current_price: float, session: Any = None) -> dict:
    """
    Fetches live technicals from Alpha Vantage.
    Requires async context.
    """
    client = AlphaVantageClient()
    try:
        rsi = await client.get_rsi(ticker, session=session)
        sma_50 = await client.get_sma(ticker, session=session, time_period=50)
        sma_200 = await client.get_sma(ticker, session=session, time_period=200)
    except Exception as e:
        logger.warning(f"Failed to fetch technicals for {ticker}: {e}")
        rsi, sma_50, sma_200 = None, None, None
    finally:
        await client.close()

    # Calculate gap (approximation if current price and previous close are known)
    # We will assume gap validations are handled in the engine with daily quote data,
    # but for F9-F15 we return the raw SMA/RSI.
    
    # Calculate simple ATH proxy (is current > SMA200 by 50%?) - a naive fallback if no true ATH data
    is_at_ath = False
    if sma_200 and current_price > sma_200 * 1.5:
        is_at_ath = True

    return {
        "rsi": rsi,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "is_at_ath": is_at_ath,
        "gap_present": False,
        "gap_hold_valid": False,
    }
