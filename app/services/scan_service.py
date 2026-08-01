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
from app.framework.dual_horizon import evaluate_dual_horizon
from app.framework.factors.registry import factor_registry
from app.core.market_data.technicals import fetch_technicals
from app.services.fundamentals_service import get_fundamentals
from app.services.options_service import get_automated_option_contract

logger = logging.getLogger(__name__)


async def trigger_scan(
    session: AsyncSession,
    scan_date: Optional[date] = None,
    batch_size: int = 20,
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

    from app.db.session import async_session_factory
    from datetime import timedelta

    # --- Phase 1: Quick DB read (short-lived session) ---
    # Write the audit log and read already-scanned tickers in one short transaction.
    _day_start = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)
    _day_end = _day_start + timedelta(days=1)

    async with async_session_factory() as read_session:
        audit = AuditLog(
            action=AuditAction.SCAN_TRIGGERED,
            entity_type="scan",
            detail_json={"job_id": job_id, "scan_date": scan_date.isoformat()},
        )
        read_session.add(audit)
        already_scanned_result = await read_session.execute(
            select(DailyScan.ticker).where(
                DailyScan.scan_date >= _day_start,
                DailyScan.scan_date < _day_end,
            )
        )
        already_scanned_tickers = {row[0] for row in already_scanned_result.fetchall()}
        await read_session.commit()

    # Build macro context from server-authoritative time
    now = get_cst_now()

    kospi_change = 0.0
    ceasefire = False

    # --- Phase 2: Finnhub data fetch (each subtask uses its own session) ---
    # This phase can take 30-90 seconds. We do NOT hold any DB session open here.
    tickers: list[dict[str, Any]] = []
    calendar: list[Any] = []

    try:
        from app.core.market_data.finnhub import FinnhubClient
        client = FinnhubClient()

        # 1. Fetch KOSPI proxy
        try:
            async with async_session_factory() as tmp:
                kospi_quote = await client.get_quote("EWY", session=tmp)
                kospi_change = kospi_quote.change_percent
        except Exception:
            pass

        # 2. Fetch general news for ceasefire keyword
        try:
            async with async_session_factory() as tmp:
                news_items = await client.get_news(category="general", session=tmp)
            for item in news_items:
                headline = item.headline.lower()
                if "ceasefire" in headline or "de-escalation" in headline or "peace" in headline:
                    ceasefire = True
                    break
        except Exception:
            pass

        logger.info("Fetching real earnings calendar from Finnhub for %s", scan_date)
        async with async_session_factory() as tmp:
            calendar = await client.get_earnings_calendar(from_date=scan_date, to_date=scan_date, session=tmp)

        logger.info(
            "Earnings calendar has %d tickers. Already scanned today: %d.",
            len(calendar), len(already_scanned_tickers)
        )

        if len(already_scanned_tickers) >= len(calendar) and len(calendar) > 0:
            logger.info("All %d tickers in today's earnings calendar have already been scanned.", len(calendar))
            return {
                "job_id": job_id,
                "scan_date": scan_date.isoformat(),
                "tickers_scanned": 0,
                "status": "ALL_SCANNED",
                "message": f"All {len(calendar)} tickers in today's earnings calendar have already been scanned.",
                "factor_coverage": factor_registry.coverage_report(),
            }

        # Slice the next batch, skipping already-scanned tickers
        remaining = [e for e in calendar if e.ticker not in already_scanned_tickers]
        calendar_subset = remaining[:batch_size]

        
        sem = asyncio.Semaphore(5)
        
        async def fetch_ticker_data(entry):
            async with sem:
                async with async_session_factory() as task_session:
                    try:
                        quote = await client.get_quote(entry.ticker, session=task_session)
                        gap = quote.change_percent
                        tech_data = await fetch_technicals(entry.ticker, quote.current_price, task_session)
                        fundamentals = await get_fundamentals(entry.ticker)
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
                            "revenue_growth": fundamentals.get("revenue_growth"),
                            "gross_margin": fundamentals.get("gross_margin"),
                            "operating_margin": fundamentals.get("operating_margin"),
                            "free_cash_flow": fundamentals.get("free_cash_flow"),
                            "debt_to_equity": fundamentals.get("debt_to_equity"),
                            "interest_coverage": fundamentals.get("interest_coverage"),
                            "insider_ownership": fundamentals.get("insider_ownership"),
                            "trailing_pe": fundamentals.get("trailing_pe"),
                            "forward_pe": fundamentals.get("forward_pe"),
                            "peg_ratio": fundamentals.get("peg_ratio"),
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

    macro_context = {
        "kospi_change_percent": kospi_change,
        "ceasefire_headline": ceasefire,
        "is_fomc_day": is_fomc_day(now),
        "fomc_time_past_1245": is_fomc_day(now) and now.hour >= 12 and now.minute >= 45,
        "current_time_cst": now.strftime("%I:%M %p"),
        "is_past_cutoff": is_past_cutoff(now),
        "is_friday": is_friday(now),
    }

    # Safety guard: abort if no data to avoid wiping existing DB records
    if not tickers:
        logger.warning("No real market data fetched. Aborting scan to preserve existing data.")
        return {
            "job_id": job_id,
            "scan_date": scan_date.isoformat(),
            "tickers_scanned": 0,
            "status": "ABORTED_NO_DATA",
            "factor_coverage": factor_registry.coverage_report(),
        }

    # Run deterministic scan (pure CPU work, no DB session needed)
    scan_results = run_full_scan(tickers, macro_context, scan_date)

    # --- Phase 3: Write results (fresh short-lived write session) ---
    # Open a brand-new connection for the write so we are not reusing a stale one.
    batch_tickers = [t["ticker"] for t in tickers]
    async with async_session_factory() as write_session:
        if batch_tickers:
            await write_session.execute(
                delete(DailyScan).where(
                    DailyScan.scan_date >= _day_start,
                    DailyScan.scan_date < _day_end,
                    DailyScan.ticker.in_(batch_tickers),
                )
            )
        await write_session.flush()

        # Persist results
        persisted_count = 0
        for ctx in scan_results:
            # Map risk bucket
            risk_bucket = _map_risk_bucket(ctx)

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
                    strike_target = None  # Requires live options chain feed
                    
                if is_bullish:
                    stop_target = round(ctx.sma_50 * 0.98, 2) if ctx.sma_50 else None
                else:
                    stop_target = round(ctx.sma_50 * 1.02, 2) if ctx.sma_50 else None

            dual_horizon = evaluate_dual_horizon(ctx, option_contract_res)
            resolved_list_type = _map_dual_list_type(dual_horizon)
            persisted_score = dual_horizon.get("tactical", {}).get("score")
            if not isinstance(persisted_score, (int, float)):
                persisted_score = ctx.conviction_score

            scan_entry = DailyScan(
                scan_date=datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc),
                ticker=ctx.ticker,
                score=float(persisted_score),
                risk_bucket=risk_bucket,
                status=ScanStatus.LOCKED if ctx.is_vetoed or macro_context["is_past_cutoff"] else ScanStatus.CONFIRMED,
                list_type=resolved_list_type,
                factor_results_json={
                    "results": [r.model_dump() for r in ctx.factor_results],
                    "coverage": factor_registry.coverage_report(),
                    "dual_horizon": dual_horizon,
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
            write_session.add(scan_entry)
            await write_session.flush()

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
                write_session.add(factor_log)

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
        write_session.add(audit_complete)
        await write_session.commit()

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


def _map_dual_list_type(dual_horizon: dict[str, Any]) -> Optional[ListType]:
    """Map dual-horizon evaluations to legacy LIST_1/LIST_2 storage column."""
    tactical = dual_horizon.get("tactical", {}) if isinstance(dual_horizon, dict) else {}
    long_term = dual_horizon.get("long_term", {}) if isinstance(dual_horizon, dict) else {}

    tactical_ok = (
        bool(tactical.get("regime_gate_pass"))
        and isinstance(tactical.get("score"), (int, float))
        and float(tactical.get("score")) >= 5.0
    )
    long_term_ok = (
        long_term.get("status") == "SCORED"
        and isinstance(long_term.get("score"), (int, float))
        and float(long_term.get("score")) >= 6.0
    )

    if tactical_ok:
        return ListType.LIST_1
    if long_term_ok:
        return ListType.LIST_2
    return None


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
        fundamentals = await get_fundamentals(symbol)
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
            "revenue_growth": fundamentals.get("revenue_growth"),
            "gross_margin": fundamentals.get("gross_margin"),
            "operating_margin": fundamentals.get("operating_margin"),
            "free_cash_flow": fundamentals.get("free_cash_flow"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "interest_coverage": fundamentals.get("interest_coverage"),
            "insider_ownership": fundamentals.get("insider_ownership"),
            "trailing_pe": fundamentals.get("trailing_pe"),
            "forward_pe": fundamentals.get("forward_pe"),
            "peg_ratio": fundamentals.get("peg_ratio"),
        }
        
        from app.framework.engine import run_full_scan
        from app.framework.factors.registry import factor_registry
        scan_results = run_full_scan([ticker_data], {}, date.today())
        if not scan_results:
            return None
        ctx = scan_results[0]
        
        risk_bucket = _map_risk_bucket(ctx)
        
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

        dual_horizon = evaluate_dual_horizon(ctx, option_contract_res)
        resolved_list_type = _map_dual_list_type(dual_horizon)
        persisted_score = dual_horizon.get("tactical", {}).get("score")
        if not isinstance(persisted_score, (int, float)):
            persisted_score = ctx.conviction_score
                
        today_dt = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
        await session.execute(
            delete(DailyScan).where(DailyScan.scan_date == today_dt, DailyScan.ticker == ctx.ticker)
        )
        await session.flush()

        scan_entry = DailyScan(
            scan_date=today_dt,
            ticker=ctx.ticker,
            score=float(persisted_score),
            risk_bucket=risk_bucket,
            status=ScanStatus.LOCKED if ctx.is_vetoed else ScanStatus.CONFIRMED,
            list_type=resolved_list_type,
            factor_results_json={
                "results": [r.model_dump() for r in ctx.factor_results],
                "coverage": factor_registry.coverage_report(),
                "dual_horizon": dual_horizon,
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
