"""
Scan Service
==============
Orchestrates scan execution and database persistence.
Bridges the deterministic framework engine with the API/DB layer.
"""

from __future__ import annotations

import logging
import uuid
import asyncio
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time_gate import get_cst_now, get_cutoff_status, is_fomc_day, is_friday, is_past_cutoff
from app.db.models import AuditAction, AuditLog, DailyScan, FactorLog, ListType, RiskBucket, ScanStatus
from app.framework.engine import run_full_scan
from app.framework.factors.registry import factor_registry
from app.core.market_data.technicals import fetch_technicals
from app.services.options_service import get_automated_option_contract

logger = logging.getLogger(__name__)


async def trigger_scan(
    session: AsyncSession,
    scan_date: Optional[date] = None,
) -> dict[str, Any]:
    """
    Trigger a full-universe scan for the given date.
    Returns a job summary with scan results.
    """
    if scan_date is None:
        scan_date = date.today()
        from datetime import timedelta
        # If Saturday (5), fallback to Friday (-1 day)
        if scan_date.weekday() == 5:
            scan_date -= timedelta(days=1)
        # If Sunday (6), fallback to Friday (-2 days)
        elif scan_date.weekday() == 6:
            scan_date -= timedelta(days=2)
    job_id = str(uuid.uuid4())

    logger.info("Scan triggered: job_id=%s, date=%s", job_id, scan_date)

    # Log audit
    audit = AuditLog(
        action=AuditAction.SCAN_TRIGGERED,
        entity_type="scan",
        detail_json={"job_id": job_id, "scan_date": scan_date.isoformat()},
    )
    session.add(audit)

    # Build macro context from server-authoritative time
    now = get_cst_now()
    
    kospi_change = 0.0
    ceasefire = False
    
    try:
        from app.core.market_data.finnhub import FinnhubClient
        client = FinnhubClient()
        
        # 1. Fetch KOSPI proxy (using EWY - iShares MSCI South Korea ETF as proxy if ^KS11 fails)
        try:
            kospi_quote = await client.get_quote("EWY", session=session)
            kospi_change = kospi_quote.change_percent
        except Exception:
            pass
            
        # 2. Fetch general news for ceasefire keyword
        try:
            news_items = await client.get_news(category="general", session=session)
            for item in news_items:
                headline = item.headline.lower()
                if "ceasefire" in headline or "de-escalation" in headline or "peace" in headline:
                    ceasefire = True
                    break
        except Exception:
            pass
            
    except Exception as e:
        logger.error("Failed to initialize Finnhub client for macro: %s", e)

    macro_context = {
        "kospi_change_percent": kospi_change,
        "ceasefire_headline": ceasefire,
        "is_fomc_day": is_fomc_day(now),
        "fomc_time_past_1245": is_fomc_day(now) and now.hour >= 12 and now.minute >= 45,
        "current_time_cst": now.strftime("%I:%M %p"),
        "is_past_cutoff": is_past_cutoff(now),
        "is_friday": is_friday(now),
    }

    # Attempt to fetch from Finnhub if API key is configured
    tickers: list[dict[str, Any]] = []
    
    try:
        logger.info("Fetching real earnings calendar from Finnhub for %s", scan_date)
        from app.db.session import async_session_factory
        async with async_session_factory() as macro_session:
            calendar = await client.get_earnings_calendar(from_date=scan_date, to_date=scan_date, session=macro_session)
        
        # Limit to 20 to avoid exhausting rate limits on free tier
        calendar_subset = calendar[:20] if len(calendar) > 20 else calendar
        
        sem = asyncio.Semaphore(5)
        
        async def fetch_ticker_data(entry):
            async with sem:
                async with async_session_factory() as task_session:
                    try:
                        quote = await client.get_quote(entry.ticker, session=task_session)
                        gap = quote.change_percent
                        tech_data = await fetch_technicals(entry.ticker, quote.current_price, task_session)
                        profile = await client.get_company_profile(entry.ticker, session=task_session)
                        
                        # Format volume as readable string
                        vol = quote.volume or 0
                        vol_str = f"{vol / 1_000_000:.1f}M" if vol >= 1_000_000 else f"{vol / 1_000:.1f}K" if vol >= 1_000 else str(vol)
                        
                        return {
                            "ticker": entry.ticker,
                            "change_percent": gap,
                            "current_price": quote.current_price,
                            "open_price": quote.open_price,
                            "high_price": quote.high_price,
                            "low_price": quote.low_price,
                            "previous_close": quote.previous_close,
                            "has_earnings_today": True,
                            "rsi": tech_data.get("rsi"),
                            "sma_50": tech_data.get("sma_50"),
                            "sma_200": tech_data.get("sma_200"),
                            "is_at_ath": tech_data.get("is_at_ath", False),
                            "name": profile.get("name") or entry.ticker,
                            "sector": profile.get("sector") or "Unknown",
                            "change": quote.change,
                            "volume_str": vol_str,
                        }
                    except Exception as e:
                        logger.warning("Skipping %s due to error: %s", entry.ticker, e)
                        return None
                
        # Run API calls concurrently to speed up the scan
        tasks = [fetch_ticker_data(entry) for entry in calendar_subset]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, dict):
                tickers.append(res)
                
        await client.close()
    except Exception as e:
        logger.error("Finnhub fetch failed. Is FINNHUB_API_KEY set? Error: %s", e)
    
    # Fallback to empty if Finnhub failed completely or returned nothing
    if not tickers:
        logger.warning("No real market data fetched. Ensure FINNHUB_API_KEY is valid.")

    # Run deterministic scan
    scan_results = run_full_scan(tickers, macro_context, scan_date)

    await session.execute(
        delete(DailyScan).where(
            DailyScan.scan_date == datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)
        )
    )
    await session.flush()

    # Persist results
    persisted_count = 0
    for ctx in scan_results:
        # Map risk bucket
        risk_bucket = _map_risk_bucket(ctx)
        list_type = _map_list_type(ctx)

        # Calculate target execution zones based on technicals and conviction
        entry_target = ctx.current_price if ctx.current_price > 0 else None
        strike_target = None
        stop_target = None
        
        option_contract_res = None
        if entry_target is not None:
            # Determine bias: Bullish if price > SMA50 or RSI < 30. Bearish if RSI > 70 or gap down.
            is_bullish = True
            if (ctx.rsi and ctx.rsi > 70) or (ctx.change_percent and ctx.change_percent < -2.0) or ctx.veto_rule == "F43" or ctx.veto_rule == "F49":
                is_bullish = False
                
            option_contract_res = await get_automated_option_contract(ctx.ticker, ctx.current_price, is_bullish)
            if option_contract_res:
                strike_target = option_contract_res["strike_price"]
            else:
                strike_target = None  # Requires live options chain feed (no mock 5% data per rule)
                
            if is_bullish:
                stop_target = round(ctx.sma_50 * 0.98, 2) if ctx.sma_50 else None
            else:
                stop_target = round(ctx.sma_50 * 1.02, 2) if ctx.sma_50 else None

        scan_entry = DailyScan(
            scan_date=datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc),
            ticker=ctx.ticker,
            score=ctx.conviction_score,
            risk_bucket=risk_bucket,
            status=ScanStatus.LOCKED if ctx.is_vetoed or macro_context["is_past_cutoff"] else ScanStatus.CONFIRMED,
            list_type=list_type,
            factor_results_json={
                "results": [r.model_dump() for r in ctx.factor_results],
                "coverage": factor_registry.coverage_report(),
                "market_data": {
                    "price": ctx.current_price,
                    "gap": ctx.change_percent,
                    "change": ctx.change,
                    "rsi": ctx.rsi,
                    "sma_50": ctx.sma_50,
                    "sma_200": ctx.sma_200,
                    "name": ctx.name,
                    "sector": ctx.sector,
                    "volume": ctx.volume_str,
                    "has_earnings_today": ctx.has_earnings_today,
                    "option_contract": option_contract_res,
                }
            },
            veto_rule=ctx.veto_rule,
            veto_reason=ctx.veto_reason,
            entry_price=entry_target,
            strike_price=strike_target,
            stop_loss=stop_target,
        )
        session.add(scan_entry)
        await session.flush()

        # Persist factor logs
        for fr in ctx.factor_results:
            factor_log = FactorLog(
                scan_id=scan_entry.id,
                factor_id=fr.factor_id,
                factor_name=fr.factor_name,
                layer_number=fr.layer_number,
                triggered=fr.triggered,
                vetoed=fr.vetoed,
                stubbed=fr.stubbed,
                result_detail_json=fr.model_dump(),
            )
            session.add(factor_log)

        persisted_count += 1

    # Audit completion
    audit_complete = AuditLog(
        action=AuditAction.SCAN_COMPLETED,
        entity_type="scan",
        detail_json={
            "job_id": job_id,
            "scan_date": scan_date.isoformat(),
            "tickers_scanned": persisted_count,
            "factor_coverage": factor_registry.coverage_report(),
        },
    )
    session.add(audit_complete)
    await session.flush()

    return {
        "job_id": job_id,
        "scan_date": scan_date.isoformat(),
        "tickers_scanned": persisted_count,
        "status": "COMPLETED",
        "factor_coverage": factor_registry.coverage_report(),
    }


async def get_scan_results(
    session: AsyncSession,
    scan_date: date,
    status_filter: Optional[ScanStatus] = None,
    risk_bucket_filter: Optional[RiskBucket] = None,
) -> list[DailyScan]:
    """Get scan results for a given date with optional filters."""
    from datetime import timedelta
    day_start = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)
    day_end = datetime.combine(scan_date + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
    stmt = select(DailyScan).where(
        DailyScan.scan_date >= day_start,
        DailyScan.scan_date < day_end,
    )

    if status_filter:
        stmt = stmt.where(DailyScan.status == status_filter)
    if risk_bucket_filter:
        stmt = stmt.where(DailyScan.risk_bucket == risk_bucket_filter)

    stmt = stmt.order_by(DailyScan.score.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _map_risk_bucket(ctx: Any) -> Optional[RiskBucket]:
    """Map ScanContext to RiskBucket enum."""
    from app.framework.scoring import assign_risk_bucket
    bucket = assign_risk_bucket(ctx.conviction_score, ctx)
    return bucket


def _map_list_type(ctx: Any) -> Optional[ListType]:
    """Map ScanContext to ListType enum."""
    from app.framework.scoring import assign_list_type
    lt = assign_list_type(ctx)
    return ListType.LIST_1 if lt == "LIST_1" else ListType.LIST_2


async def evaluate_and_persist_on_demand(
    session: AsyncSession,
    symbol: str,
    quote: Any,
    name: str,
    sector: str,
) -> Optional[DailyScan]:
    """
    Run on-demand 50-factor evaluation for a single ticker that was missed by morning batch scan.
    Persists DailyScan and 50 FactorLog entries to Postgres for same-day caching.
    """
    try:
        from app.core.market_data.technicals import fetch_technicals
        tech_data = await fetch_technicals(symbol, quote.current_price if quote else 0.0, session)
        vol = quote.volume if quote else 0
        vol_str = f"{vol / 1_000_000:.1f}M" if vol >= 1_000_000 else f"{vol / 1_000:.1f}K" if vol >= 1_000 else str(vol)
        
        ticker_data = {
            "ticker": symbol.upper(),
            "change_percent": quote.change_percent if quote else 0.0,
            "current_price": quote.current_price if quote else 0.0,
            "open_price": quote.open_price if quote else 0.0,
            "high_price": quote.high_price if quote else 0.0,
            "low_price": quote.low_price if quote else 0.0,
            "previous_close": quote.previous_close if quote else 0.0,
            "has_earnings_today": False,
            "rsi": tech_data.get("rsi"),
            "sma_50": tech_data.get("sma_50"),
            "sma_200": tech_data.get("sma_200"),
            "is_at_ath": tech_data.get("is_at_ath", False),
            "name": name or symbol,
            "sector": sector or "Unknown",
            "change": quote.change if quote else 0.0,
            "volume_str": vol_str,
        }
        
        from app.framework.engine import run_full_scan
        from app.framework.factors.registry import factor_registry
        scan_results = run_full_scan([ticker_data], {}, date.today())
        if not scan_results:
            return None
        ctx = scan_results[0]
        
        risk_bucket = _map_risk_bucket(ctx)
        list_type = _map_list_type(ctx)
        
        entry_target = ctx.current_price if ctx.current_price > 0 else None
        strike_target = None
        stop_target = None
        option_contract_res = None
        if entry_target is not None:
            is_bullish = not ((ctx.rsi and ctx.rsi > 70) or (ctx.change_percent and ctx.change_percent < -2.0) or ctx.veto_rule in ("F43", "F49"))
            option_contract_res = await get_automated_option_contract(ctx.ticker, ctx.current_price, is_bullish)
            if option_contract_res:
                strike_target = option_contract_res["strike_price"]
            else:
                strike_target = None  # Requires live options chain feed (no mock 5% data per rule)
                
            if is_bullish:
                stop_target = round(ctx.sma_50 * 0.98, 2) if ctx.sma_50 else None
            else:
                stop_target = round(ctx.sma_50 * 1.02, 2) if ctx.sma_50 else None
                
        today_dt = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
        await session.execute(
            delete(DailyScan).where(DailyScan.scan_date == today_dt, DailyScan.ticker == ctx.ticker)
        )
        await session.flush()

        scan_entry = DailyScan(
            scan_date=today_dt,
            ticker=ctx.ticker,
            score=ctx.conviction_score,
            risk_bucket=risk_bucket,
            status=ScanStatus.LOCKED if ctx.is_vetoed else ScanStatus.CONFIRMED,
            list_type=list_type,
            factor_results_json={
                "results": [r.model_dump() for r in ctx.factor_results],
                "coverage": factor_registry.coverage_report(),
                "market_data": {
                    "price": ctx.current_price,
                    "gap": ctx.change_percent,
                    "change": ctx.change,
                    "rsi": ctx.rsi,
                    "sma_50": ctx.sma_50,
                    "sma_200": ctx.sma_200,
                    "name": ctx.name,
                    "sector": ctx.sector,
                    "volume": ctx.volume_str,
                    "has_earnings_today": ctx.has_earnings_today,
                    "option_contract": option_contract_res,
                }
            },
            veto_rule=ctx.veto_rule,
            veto_reason=ctx.veto_reason,
            entry_price=entry_target,
            strike_price=strike_target,
            stop_loss=stop_target,
        )
        session.add(scan_entry)
        await session.flush()
        
        for fr in ctx.factor_results:
            flog = FactorLog(
                scan_id=scan_entry.id,
                factor_id=fr.factor_id,
                factor_name=fr.factor_name,
                layer_number=fr.layer_number,
                triggered=fr.triggered,
                vetoed=fr.vetoed,
                stubbed=fr.stubbed,
                result_detail_json=fr.model_dump(),
            )
            session.add(flog)
            
        await session.commit()
        
        stmt = select(DailyScan).options(selectinload(DailyScan.factor_logs)).where(DailyScan.id == scan_entry.id)
        res = await session.execute(stmt)
        return res.scalar_one_or_none()
    except Exception as e:
        logger.error("On-demand factor evaluation failed for %s: %s", symbol, e)
        return None
