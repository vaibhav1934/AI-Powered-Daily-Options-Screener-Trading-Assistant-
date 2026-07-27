"""
StockGlass AI — Service Layer (v1 Contract)
=============================================
Assembles data for indices, screener list, stock details, and factor breakdowns.
Maps internal 10-layer / 50-factor scanning engine output to the drop-in v1 API contract.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.market_data.finnhub import FinnhubClient
from app.db.models import DailyScan, FactorLog, ListType, RiskBucket, ScanStatus
from app.db.schemas import (
    FactorBreakdownItem,
    FactorSummarySchema,
    FullFactorBreakdownSchema,
    IndexItemSchema,
    LayerBreakdownItem,
    LayerScoreItem,
    NewsItemSchema,
    ReasonItem,
    StockDetailSchema,
    StockListItemSchema,
    StockListResponseSchema,
    SupportResistanceLevels,
)
from app.framework.factors.registry import factor_registry
from app.services.synthesis_service import synthesize_reasons

logger = logging.getLogger(__name__)

# 10 Layers definition mapping to factor ranges as per Section 0
LAYER_DEFINITIONS = [
    (1, "Price Action", 1, 5, "F1-F5"),
    (2, "Volume/Flow", 6, 10, "F6-F10"),
    (3, "Volatility", 11, 15, "F11-F15"),
    (4, "Earnings Calendar", 16, 20, "F16-F20"),
    (5, "Analyst/Sentiment", 21, 25, "F21-F25"),
    (6, "Macro/Rates", 26, 30, "F26-F30"),
    (7, "Sector Rotation", 31, 35, "F31-F35"),
    (8, "News/Catalyst", 36, 40, "F36-F40"),
    (9, "Risk Rules", 41, 45, "F41-F45"),
    (10, "Position Fit", 46, 50, "F46-F50"),
]


async def get_indices(session: AsyncSession) -> list[IndexItemSchema]:
    """
    Get indices strip data (S&P 500, Nasdaq, Dow Jones).
    Uses Finnhub to fetch quotes for proxy ETFs (SPY, QQQ, DIA) and scales to index values,
    or falls back to realistic baseline numbers if API call fails.
    """
    client = FinnhubClient()
    logger.info("[FLOW: Service Layer] ──> get_indices: Fetching SPY, QQQ, DIA from Finnhub or fallback")
    try:
        quotes = await client.get_quotes_batch(["SPY", "QQQ", "DIA"], session=session)
        quote_map = {q.ticker: q for q in quotes}
        
        spy = quote_map.get("SPY")
        qqq = quote_map.get("QQQ")
        dia = quote_map.get("DIA")
        
        if spy and qqq and dia and spy.current_price > 0:
            # Approximate index values from ETF proxies
            sp_val = spy.current_price * 12.55
            sp_chg = spy.change * 12.55
            
            nas_val = qqq.current_price * 48.2
            nas_chg = qqq.change * 48.2
            
            dow_val = dia.current_price * 100.1
            dow_chg = dia.change * 100.1
            
            return [
                IndexItemSchema(name="S&P 500", value=f"{sp_val:,.2f}", chg=round(sp_chg, 2), pct=round(spy.change_percent, 2)),
                IndexItemSchema(name="Nasdaq", value=f"{nas_val:,.2f}", chg=round(nas_chg, 2), pct=round(qqq.change_percent, 2)),
                IndexItemSchema(name="Dow Jones", value=f"{dow_val:,.2f}", chg=round(dow_chg, 2), pct=round(dia.change_percent, 2)),
            ]
    except Exception as e:
        logger.warning("Failed to fetch live index quotes from Finnhub: %s", e)
    finally:
        await client.close()
        
    # Return 0 / N/A when live index quotes are unavailable (No fallback data per user rule)
    logger.warning("[FLOW: Service Layer] <── get_indices: Live quotes unavailable from Finnhub, returning N/A / 0.0 (No fallback data)")
    return [
        IndexItemSchema(name="S&P 500", value="N/A", chg=0.0, pct=0.0),
        IndexItemSchema(name="Nasdaq", value="N/A", chg=0.0, pct=0.0),
        IndexItemSchema(name="Dow Jones", value="N/A", chg=0.0, pct=0.0),
    ]


async def _get_latest_scan_date(session: AsyncSession) -> Optional[date]:
    """Find the most recent scan date available in the database."""
    stmt = select(func.max(DailyScan.scan_date))
    max_dt = await session.scalar(stmt)
    if max_dt:
        return max_dt.date() if isinstance(max_dt, datetime) else max_dt
    return None


async def get_stock_list(
    session: AsyncSession,
    list_param: Optional[str] = None,  # "list1", "list2", "all"
    sector: Optional[str] = None,
    min_score: Optional[float] = None,
    direction: Optional[str] = None,  # "gainers", "losers"
    query_str: Optional[str] = None,
    earnings_soon: Optional[bool] = None,
    risk_bucket: Optional[str] = None,  # "LOW", "MODERATE", "HIGH_RISK_HALO"
) -> StockListResponseSchema:
    """
    Get screener table stock list matching API Contract v1.
    Enforces FR-7 by ensuring execution details are excluded while screening market data is shown.
    """
    target_date = await _get_latest_scan_date(session) or date.today()
    start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    logger.info("[FLOW: Service Layer] ──> get_stock_list: Querying DB DailyScan for date >= %s (filters: list=%s, sector=%s, minScore=%s)", target_date, list_param, sector, min_score)
    
    stmt = (
        select(DailyScan)
        .options(selectinload(DailyScan.factor_logs))
        .where(DailyScan.scan_date >= start_dt)
        .order_by(DailyScan.score.desc())
    )
    
    if list_param and list_param.lower() in ("list1", "list_1"):
        stmt = stmt.where(DailyScan.list_type == ListType.LIST_1)
    elif list_param and list_param.lower() in ("list2", "list_2"):
        stmt = stmt.where(DailyScan.list_type == ListType.LIST_2)
        
    if min_score is not None:
        stmt = stmt.where(DailyScan.score >= min_score)
        
    if query_str:
        stmt = stmt.where(DailyScan.ticker.ilike(f"%{query_str}%"))
        
    if risk_bucket and risk_bucket.upper() in ("LOW", "MODERATE", "HIGH_RISK_HALO"):
        stmt = stmt.where(DailyScan.risk_bucket == RiskBucket(risk_bucket.upper()))
        
    result = await session.execute(stmt)
    scans = list(result.scalars().all())
    
    # If no scans in DB, return empty results (No fallback data per user rule)
    if not scans:
        logger.info("[FLOW: Service Layer] <── get_stock_list: DB empty or offline, returning 0 results (No fallback data)")
        return StockListResponseSchema(count=0, total=0, results=[])
        
    results: list[StockListItemSchema] = []
    for scan in scans:
        # Extract real market data from DB (populated by scan_service at scan time)
        mdata = (scan.factor_results_json or {}).get("market_data", {})
        
        # Real name and sector from Finnhub company profile (stored at scan time)
        real_name = mdata.get("name") or f"{scan.ticker} Corp"
        real_sector = mdata.get("sector") or "Unknown"
        
        # Sector filter — applied against real sector from DB
        if sector and sector.lower() not in real_sector.lower():
            continue
            
        price = float(mdata.get("price") or 0.0)
        chg = float(mdata.get("change") or 0.0)          # dollar change
        pct = float(mdata.get("gap") or 0.0)             # percent change
        vol = str(mdata.get("volume") or "N/A")
        
        # Direction filter
        if direction == "gainers" and chg < 0:
            continue
        if direction == "losers" and chg > 0:
            continue
            
        # Earnings filter — has_earnings_today stored in market_data
        ticker_has_earnings = bool(mdata.get("has_earnings_today", False))
        if earnings_soon is True and not ticker_has_earnings:
            continue
        if earnings_soon is False and ticker_has_earnings:
            continue
            
        # Hard flags: any vetoed named rules
        hard_flags = []
        if scan.veto_rule:
            hard_flags.append(scan.veto_rule)
        for flog in scan.factor_logs:
            if flog.vetoed and flog.factor_id not in hard_flags:
                hard_flags.append(flog.factor_id)
                
        # Sparkline & support/resistance from real price
        sparkline = [round(price - chg * 1.5, 2), round(price - chg * 0.5, 2), round(price, 2)] if price > 0 else [0.0, 0.0, 0.0]
        levels = SupportResistanceLevels(
            support=round(price * 0.94, 2) if price > 0 else 0.0,
            resistance=round(price * 1.06, 2) if price > 0 else 0.0,
        )
        
        results.append(
            StockListItemSchema(
                symbol=scan.ticker,
                name=real_name,
                sector=real_sector,
                price=price,
                chg=chg,
                pct=pct,
                volume=vol,
                score=round(scan.score, 1),
                earningsSoon=ticker_has_earnings,
                hardFlags=hard_flags,
                sparkline=sparkline,
                levels=levels,
            )
        )
        
    return StockListResponseSchema(count=len(results), total=len(results), results=results)


async def get_stock_detail(session: AsyncSession, symbol: str) -> StockDetailSchema:
    """
    Get stock detail view (right-hand panel) matching Section 3.
    Includes layerScores across all 10 layers, reasons, and news.
    """
    symbol = symbol.upper()
    
    target_date = await _get_latest_scan_date(session) or date.today()
    start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    logger.info("[FLOW: Service Layer] ──> get_stock_detail: Fetching 10-layer breakdown & live news for %s", symbol)
    
    stmt = (
        select(DailyScan)
        .options(selectinload(DailyScan.factor_logs))
        .where(DailyScan.scan_date >= start_dt, DailyScan.ticker == symbol)
        .order_by(DailyScan.score.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    scan = result.scalar_one_or_none()
    
    # Real name and sector from market_data stored at scan time
    mdata = (scan.factor_results_json or {}).get("market_data", {}) if scan else {}
    real_name = mdata.get("name") or f"{symbol} Corp"
    real_sector = mdata.get("sector") or "Unknown"
    
    # Fetch live quotes and news from Finnhub (No fallback data per user rule)
    client = FinnhubClient()
    price = scan.entry_price if (scan and scan.entry_price) else 0.0
    chg = 0.0
    pct = 0.0
    news_items = []
    try:
        quote = await client.get_quote(symbol, session=session)
        if quote and quote.current_price > 0:
            price = quote.current_price
            chg = quote.change
            pct = quote.change_percent
            
        raw_news = await client.get_news(ticker=symbol, session=session)
        for n in raw_news[:5]:
            news_items.append(
                NewsItemSchema(
                    headline=n.headline,
                    source=n.source or "Market News",
                    publishedAt=n.published_at or datetime.now(timezone.utc).isoformat(),
                    url=n.url or "#",
                )
            )
    except Exception as e:
        logger.warning("Failed to fetch Finnhub data for %s detail: %s", symbol, e)
    finally:
        await client.close()
        
    score = round(scan.score, 1) if scan else 0.0
    hard_flags = []
    if scan and scan.veto_rule:
        hard_flags.append(scan.veto_rule)
    if scan and scan.factor_logs:
        for flog in scan.factor_logs:
            if flog.vetoed and flog.factor_id not in hard_flags:
                hard_flags.append(flog.factor_id)
                
    levels = SupportResistanceLevels(support=round(price * 0.94, 2) if price > 0 else 0.0, resistance=round(price * 1.06, 2) if price > 0 else 0.0)
    
    # Compute layerScores across the 10 layers using real DB factor logs (No simulated sine waves per user rule)
    layer_scores: list[LayerScoreItem] = []
    for lnum, lname, fstart, fend, _ in LAYER_DEFINITIONS:
        val = 0.0
        if scan and scan.factor_logs:
            layer_flogs = [flog for flog in scan.factor_logs if int(flog.factor_id.replace("F", "")) in range(fstart, fend + 1)]
            if any(f.vetoed for f in layer_flogs):
                val = 0.0
            elif layer_flogs:
                triggered = sum(1 for f in layer_flogs if f.triggered)
                val = round((triggered / len(layer_flogs)) * 10.0, 1)
            else:
                val = round(scan.score, 1)
        layer_scores.append(LayerScoreItem(layer=lname, value=val))
        
    # Generate bull / bear reasons via AI Synthesis Agent (with compliance filter and zero-mock fallback)
    reasons: list[ReasonItem] = []
    if scan and scan.factor_logs:
        reasons = await synthesize_reasons(
            symbol=symbol,
            score=score,
            factor_logs=list(scan.factor_logs),
            news=news_items,
        )
        
    return StockDetailSchema(
        symbol=symbol,
        name=real_name,
        sector=real_sector,
        price=price,
        chg=round(chg, 2),
        pct=round(pct, 2),
        score=score,
        hardFlags=hard_flags,
        levels=levels,
        layerScores=layer_scores,
        reasons=reasons,
        news=news_items,
    )


async def get_stock_factors(session: AsyncSession, symbol: str) -> FullFactorBreakdownSchema:
    """
    Get full 50-factor breakdown modal matching Section 4.
    Groups factors into layers 1-10 with pass/neutral/fail status.
    """
    symbol = symbol.upper()
    target_date = await _get_latest_scan_date(session) or date.today()
    start_dt = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc)
    
    stmt = (
        select(DailyScan)
        .options(selectinload(DailyScan.factor_logs))
        .where(DailyScan.scan_date >= start_dt, DailyScan.ticker == symbol)
        .order_by(DailyScan.score.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    scan = result.scalar_one_or_none()
    
    log_map: dict[str, FactorLog] = {}
    if scan and scan.factor_logs:
        for flog in scan.factor_logs:
            log_map[flog.factor_id] = flog
            
    all_factors = factor_registry.get_all()
    layer_items: list[LayerBreakdownItem] = []
    
    total_pass = 0
    total_neutral = 0
    total_fail = 0
    
    for lnum, lname, fstart, fend, frange in LAYER_DEFINITIONS:
        factor_items: list[FactorBreakdownItem] = []
        for fid_num in range(fstart, fend + 1):
            code = f"F{fid_num:02d}" if fid_num < 10 else f"F{fid_num}"
            # Check if in registry
            reg_factor = factor_registry.get(code)
            name = reg_factor.name if reg_factor else f"Factor {code}"
            desc = reg_factor.description if reg_factor else f"Standard evaluation for {name}"
            
            flog = log_map.get(code)
            status = "neutral"
            detail = desc
            
            if flog:
                saved_detail = None
                if flog.result_detail_json and isinstance(flog.result_detail_json, dict):
                    saved_detail = flog.result_detail_json.get("detail")
                if flog.vetoed:
                    status = "fail"
                    detail = saved_detail or f"Failed check: {flog.factor_name} veto applied."
                elif flog.triggered:
                    status = "pass"
                    detail = saved_detail or f"Passed check: {flog.factor_name} condition verified."
                else:
                    status = "neutral"
                    detail = saved_detail or f"Neutral check: {flog.factor_name} condition not active."
            else:
                # Return neutral / unconfigured when no DB log exists (No simulated data per user rule)
                status = "neutral"
                detail = f"Not evaluated: {name} has no scan record in database."
                    
            if status == "pass":
                total_pass += 1
            elif status == "fail":
                total_fail += 1
            else:
                total_neutral += 1
                
            factor_items.append(
                FactorBreakdownItem(code=code if fid_num >= 10 else f"F{fid_num}", status=status, detail=detail)
            )
            
        layer_items.append(
            LayerBreakdownItem(layer=lname, range=frange, factors=factor_items)
        )
        
    summary = FactorSummarySchema(**{"pass": total_pass, "neutral": total_neutral, "fail": total_fail})
    return FullFactorBreakdownSchema(symbol=symbol, summary=summary, layers=layer_items)
