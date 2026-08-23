"""
Continuous Universe Scanner Service (Free-Tier Rate-Limit Optimized)
====================================================================
Automated background scanning worker that runs the 50-factor framework
across the active Stock Universe and Finnhub earnings calendar.

Free-Tier Optimization Specs:
1. Strict $1B Market Cap Filter (market_cap >= $1,000,000,000 USD).
2. Free-Tier Rate Limiting: 5 tickers per batch, 2.0s delay between calls (<= 30 req/min vs 60 limit).
3. 60s cooldown between batches to maintain zero 429 quota pressure.
4. 7-Day Rolling Window Persistence: Scans populate PostgreSQL daily_scans with multi-day deduplication.
5. Zero Mock / Zero Fallback rule: 100% live data fetched dynamically from Finnhub & SEC EDGAR.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import DailyScan, StockUniverse
from app.db.session import async_session_factory
from app.services.scan_service import evaluate_and_persist_on_demand, MIN_MARKET_CAP_USD

logger = logging.getLogger("continuous_scanner")

# Priority liquid tickers (> $1B market cap) prioritized for initial pre-scan
PRIORITY_TICKERS = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR",
    "JPM", "LLY", "V", "UNH", "XOM", "MA", "JNJ", "HD", "PG", "COST",
    "ABBV", "NFLX", "CRM", "ORCL", "INTC", "QCOM", "TXN", "AMAT", "MU", "PANW",
    "NOW", "COIN", "UBER", "DIS", "BA", "CAT", "GE", "IBM", "GS", "MS"
]

# Scanner control state
_scanner_task: Optional[asyncio.Task] = None
_scanner_running = False
_scanner_stop_event = asyncio.Event()


async def get_tickers_to_scan(session: AsyncSession, limit: int = 5) -> list[str]:
    """
    Retrieve candidate tickers to scan:
    1. Priority liquid tickers not scanned within the 7-day rolling window.
    2. Other active tickers from StockUniverse not yet scanned in the last 7 days.
    """
    rolling_7d_dt = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Get tickers scanned in the 7-day rolling window
    stmt_scanned = select(DailyScan.ticker).where(DailyScan.scan_date >= rolling_7d_dt)
    scanned_res = await session.execute(stmt_scanned)
    scanned_tickers = {row[0].upper() for row in scanned_res.fetchall()}
    
    candidates: list[str] = []
    
    # 1. Add priority tickers first if not scanned recently
    for ticker in PRIORITY_TICKERS:
        if ticker not in scanned_tickers and ticker not in candidates:
            candidates.append(ticker)
            if len(candidates) >= limit:
                return candidates

    # 2. Add remaining active universe tickers
    stmt_univ = (
        select(StockUniverse.ticker)
        .where(StockUniverse.is_active == True)
        .order_by(StockUniverse.ticker)
        .limit(limit * 4)
    )
    univ_res = await session.execute(stmt_univ)
    univ_tickers = [row[0].upper() for row in univ_res.fetchall()]
    
    for ticker in univ_tickers:
        if ticker not in scanned_tickers and ticker not in candidates:
            candidates.append(ticker)
            if len(candidates) >= limit:
                break
                
    return candidates


async def run_scanner_cycle(batch_size: int = 5, delay_between_calls_sec: float = 2.0) -> int:
    """
    Executes one free-tier compliant scanning cycle:
    - 5 tickers per batch.
    - 2.0s delay between calls (guarantees <= 30 calls/min against Finnhub's 60 req/min free limit).
    - Evaluates 50-factor framework for each ticker.
    - Persists results to DB with $1B market cap enforcement.
    """
    async with async_session_factory() as session:
        tickers = await get_tickers_to_scan(session, limit=batch_size)
        
    if not tickers:
        logger.info("[Continuous Scanner] All priority universe tickers scanned within 7-day window.")
        return 0
        
    logger.info("[Continuous Scanner] Starting free-tier scan batch for %d tickers: %s", len(tickers), tickers)
    scanned_count = 0
    
    for ticker in tickers:
        if _scanner_stop_event.is_set():
            logger.info("[Continuous Scanner] Stop signal received. Aborting cycle.")
            break
            
        try:
            async with async_session_factory() as session:
                scan_res = await evaluate_and_persist_on_demand(session, ticker)
                if scan_res:
                    scanned_count += 1
                    logger.info(
                        "[Continuous Scanner] Scanned %s: Score=%.1f | Risk=%s | List=%s",
                        ticker, scan_res.score, scan_res.risk_bucket, scan_res.list_type
                    )
        except Exception as e:
            logger.warning("[Continuous Scanner] Error scanning ticker %s: %s", ticker, str(e))
            
        # Free-tier rate limit delay (2.0s keeps request rate strictly at 30 req/min)
        try:
            await asyncio.sleep(delay_between_calls_sec)
        except asyncio.CancelledError:
            break
            
    logger.info("[Continuous Scanner] Finished batch. Scanned %d/%d tickers.", scanned_count, len(tickers))
    return scanned_count


async def _continuous_scanner_loop() -> None:
    """
    Background worker loop: runs 5-ticker scan batches with 60-second cooldowns
    to protect free-tier API quotas.
    """
    global _scanner_running
    _scanner_running = True
    logger.info("[Continuous Scanner] Background universe scanner daemon started (Free Tier Mode).")
    
    # 5s startup delay before first scan
    await asyncio.sleep(5.0)
    
    while not _scanner_stop_event.is_set():
        try:
            scanned = await run_scanner_cycle(batch_size=5, delay_between_calls_sec=2.0)
            # Free tier pacing: 60s cooldown between 5-ticker batches, or 5m if all scanned
            idle_seconds = 300.0 if scanned == 0 else 60.0
            
            try:
                await asyncio.wait_for(_scanner_stop_event.wait(), timeout=idle_seconds)
            except asyncio.TimeoutError:
                pass  # Cooldown finished, start next batch
        except asyncio.CancelledError:
            logger.info("[Continuous Scanner] Scanner loop cancelled.")
            break
        except Exception as e:
            logger.error("[Continuous Scanner] Error in scanner loop: %s", str(e))
            await asyncio.sleep(15.0)
            
    _scanner_running = False
    logger.info("[Continuous Scanner] Background universe scanner daemon stopped.")


def start_continuous_scanner() -> None:
    """Start the background continuous scanner task."""
    global _scanner_task, _scanner_stop_event
    _scanner_stop_event.clear()
    if _scanner_task is None or _scanner_task.done():
        _scanner_task = asyncio.create_task(_continuous_scanner_loop())
        logger.info("[Continuous Scanner] Spawned scanner task (Free Tier).")


def stop_continuous_scanner() -> None:
    """Signal the background continuous scanner task to stop."""
    global _scanner_task, _scanner_stop_event
    _scanner_stop_event.set()
    if _scanner_task and not _scanner_task.done():
        _scanner_task.cancel()
        logger.info("[Continuous Scanner] Cancelled scanner task.")
