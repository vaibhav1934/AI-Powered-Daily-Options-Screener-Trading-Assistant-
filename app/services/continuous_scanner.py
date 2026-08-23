"""
Continuous Universe Scanner Service (Anti-Deadlock & Free-Tier Rate-Limit Optimized)
=====================================================================================
Automated background scanning worker that runs the 50-factor framework
across the active Stock Universe and Finnhub earnings calendar.

Features & Defenses:
1. Strict $1B Market Cap Filter (market_cap >= $1,000,000,000 USD).
2. Anti-Deadlock Skip Tracking: Remembers evaluated & skipped tickers so skipped/sub-$1B names never trap the queue.
3. 100+ Liquid US Equities Priority Pipeline: Scans mega/large-caps first so screener is immediately populated with top names.
4. Free-Tier Rate Limiting: 5 tickers per batch, 1.5s delay between calls (<= 40 req/min vs 60 limit).
5. 7-Day Rolling Window Persistence: Scans populate PostgreSQL daily_scans with multi-day deduplication.
6. Zero Mock / Zero Fallback rule: 100% live data fetched dynamically from Finnhub & SEC EDGAR.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Set

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import DailyScan, StockUniverse
from app.db.session import async_session_factory
from app.services.scan_service import evaluate_and_persist_on_demand, MIN_MARKET_CAP_USD

logger = logging.getLogger("continuous_scanner")

# Top 100+ liquid US market leaders (> $1B market cap) prioritized for continuous screening
PRIORITY_TICKERS = [
    "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "PLTR",
    "JPM", "LLY", "V", "UNH", "XOM", "MA", "JNJ", "HD", "PG", "COST",
    "ABBV", "NFLX", "CRM", "ORCL", "INTC", "QCOM", "TXN", "AMAT", "MU", "PANW",
    "NOW", "COIN", "UBER", "DIS", "BA", "CAT", "GE", "IBM", "GS", "MS",
    "WMT", "BAC", "ADBE", "NKE", "MCD", "CSCO", "PEP", "KO", "TMO", "LIN",
    "ACN", "ABT", "MRK", "CVX", "WFC", "DHR", "PM", "NEE", "ISRG", "RTX",
    "LOW", "SPGI", "HON", "UNP", "INTU", "AMGN", "PFE", "BKNG", "DE", "SYK",
    "MDT", "LMT", "TJX", "BLK", "VRTX", "REGN", "ETN", "PGR", "BSX", "CI",
    "SCHW", "CB", "ADP", "FI", "MMC", "MDLZ", "ADI", "GILD", "BMY", "C",
    "SO", "DUK", "ZTS", "EOG", "BDX", "CL", "CME", "ITW", "WM", "SHW"
]

# Scanner control state
_scanner_task: Optional[asyncio.Task] = None
_scanner_running = False
_scanner_stop_event = asyncio.Event()

# In-memory track of attempted tickers (successful or skipped sub-$1B) to prevent deadlock loops
_attempted_tickers: Set[str] = set()
_universe_cursor_offset = 0


async def get_tickers_to_scan(session: AsyncSession, limit: int = 5) -> list[str]:
    """
    Retrieve candidate tickers to scan:
    1. Priority liquid tickers not scanned within 7-day window and not yet attempted in this session.
    2. Broader universe tickers rotating through cursor offset so skips never trap the scanner.
    """
    global _attempted_tickers, _universe_cursor_offset
    rolling_7d_dt = datetime.now(timezone.utc) - timedelta(days=7)
    
    # Get tickers scanned in the 7-day rolling window
    stmt_scanned = select(DailyScan.ticker).where(DailyScan.scan_date >= rolling_7d_dt)
    scanned_res = await session.execute(stmt_scanned)
    scanned_tickers = {row[0].upper() for row in scanned_res.fetchall()}
    
    candidates: list[str] = []
    
    # 1. First pass: Priority large-cap liquid tickers
    for ticker in PRIORITY_TICKERS:
        t_up = ticker.upper()
        if t_up not in scanned_tickers and t_up not in _attempted_tickers and t_up not in candidates:
            candidates.append(t_up)
            if len(candidates) >= limit:
                return candidates

    # 2. Second pass: Rotate through StockUniverse with advancing cursor offset
    stmt_univ = (
        select(StockUniverse.ticker)
        .where(StockUniverse.is_active == True)
        .order_by(StockUniverse.ticker)
        .offset(_universe_cursor_offset)
        .limit(limit * 8)
    )
    univ_res = await session.execute(stmt_univ)
    univ_tickers = [row[0].upper() for row in univ_res.fetchall()]
    
    if not univ_tickers:
        # Reset universe cursor offset when reaching the end
        _universe_cursor_offset = 0
        if not candidates:
            # If all attempted, clear session attempt cache to allow refreshing
            _attempted_tickers.clear()
            logger.info("[Continuous Scanner] Completed full universe cycle. Resetting sweep cursor.")
            return []

    for ticker in univ_tickers:
        _universe_cursor_offset += 1
        t_up = ticker.upper()
        if t_up not in scanned_tickers and t_up not in _attempted_tickers and t_up not in candidates:
            candidates.append(t_up)
            if len(candidates) >= limit:
                break
                
    return candidates


async def run_scanner_cycle(batch_size: int = 5, delay_between_calls_sec: float = 1.5) -> int:
    """
    Executes one free-tier compliant scanning cycle:
    - 5 tickers per batch.
    - 1.5s delay between calls (<= 40 calls/min against Finnhub's 60 req/min free limit).
    - Evaluates 50-factor framework for each ticker.
    - Persists results to DB with $1B market cap enforcement.
    """
    global _attempted_tickers
    async with async_session_factory() as session:
        tickers = await get_tickers_to_scan(session, limit=batch_size)
        
    if not tickers:
        logger.info("[Continuous Scanner] All priority candidates fresh in 7-day window.")
        return 0
        
    logger.info("[Continuous Scanner] Starting free-tier scan batch for %d tickers: %s", len(tickers), tickers)
    scanned_count = 0
    
    for ticker in tickers:
        _attempted_tickers.add(ticker)  # Mark attempted so it advances even if skipped
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
                else:
                    logger.info("[Continuous Scanner] Filtered/Skipped %s (<$1B cap or no quote)", ticker)
        except Exception as e:
            logger.warning("[Continuous Scanner] Error scanning ticker %s: %s", ticker, str(e))
            
        # Free-tier rate limit delay (1.5s keeps request rate strictly <= 40 req/min)
        try:
            await asyncio.sleep(delay_between_calls_sec)
        except asyncio.CancelledError:
            break
            
    logger.info("[Continuous Scanner] Finished batch. Successfully persisted %d/%d tickers.", scanned_count, len(tickers))
    return scanned_count


async def _continuous_scanner_loop() -> None:
    """
    Background worker loop: runs 5-ticker scan batches continuously.
    Uses short 5s intervals when actively scanning priority names,
    and 60s cooldown when resting.
    """
    global _scanner_running
    _scanner_running = True
    logger.info("[Continuous Scanner] Background universe scanner daemon started (Free Tier Mode).")
    
    # 2s startup delay before first scan
    await asyncio.sleep(2.0)
    
    while not _scanner_stop_event.is_set():
        try:
            scanned = await run_scanner_cycle(batch_size=5, delay_between_calls_sec=1.5)
            # Pacing: 5s pause while actively scanning candidates, 60s when all candidates evaluated
            idle_seconds = 60.0 if scanned == 0 else 5.0
            
            try:
                await asyncio.wait_for(_scanner_stop_event.wait(), timeout=idle_seconds)
            except asyncio.TimeoutError:
                pass  # Cooldown finished, start next batch
        except asyncio.CancelledError:
            logger.info("[Continuous Scanner] Scanner loop cancelled.")
            break
        except Exception as e:
            logger.error("[Continuous Scanner] Error in scanner loop: %s", str(e))
            await asyncio.sleep(10.0)
            
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
