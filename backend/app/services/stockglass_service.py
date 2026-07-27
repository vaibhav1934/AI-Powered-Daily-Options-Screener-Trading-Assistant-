"""
StockGlass AI — Service Layer (v1 Contract)
=============================================
Assembles data for indices, screener list, stock details, and factor breakdowns.
Maps internal 10-layer / 50-factor scanning engine output to the drop-in v1 API contract.
"""

from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.edgar import EdgarClient
from app.db.models import DailyScan, FactorLog, ListType, RiskBucket, ScanStatus, StockUniverse
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
from app.framework.factors.base import ScanContext
from app.framework.factors.f46_edgar_shelf_check import F46EDGARShelfCheck
from app.framework.factors.registry import factor_registry
from app.services.synthesis_service import synthesize_reasons, synthesize_news_summary
from app.services.options_service import get_automated_option_contract

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
    Uses Finnhub to fetch quotes for proxy ETFs (SPY, QQQ, DIA) and scales to index values.
    Returns 0/N/A if API call fails (Zero Mock Data rule).
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
    page: int = 1,
    page_size: int = 10,
) -> StockListResponseSchema:
    """
    Get screener table stock list matching API Contract v1 with pagination.
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
    
    ticker_symbols = [s.ticker for s in scans]
    univ_stmt = select(StockUniverse).where(StockUniverse.is_active == True)
    if ticker_symbols:
        univ_stmt = univ_stmt.where(StockUniverse.ticker.in_(ticker_symbols))
    else:
        univ_stmt = univ_stmt.limit(100)
        
    univ_rows = (await session.execute(univ_stmt)).scalars().all()
    univ_map = {u.ticker: u for u in univ_rows}

    results: list[StockListItemSchema] = []
    
    # 1. Add scanned stocks from DailyScan
    for scan in scans:
        mdata = (scan.factor_results_json or {}).get("market_data", {})
        univ_item = univ_map.get(scan.ticker)
        
        real_name = mdata.get("name") or (univ_item.name if univ_item else f"{scan.ticker} Corp")
        real_sector = mdata.get("sector") or (univ_item.sector if univ_item else "Unknown")
        if real_sector == "Unknown" and univ_item and univ_item.sector:
            real_sector = univ_item.sector
        
        if sector and sector.lower() not in real_sector.lower():
            continue
            
        price = float(mdata.get("price") or 0.0)
        chg = float(mdata.get("change") or 0.0)
        pct = float(mdata.get("gap") or 0.0)
        vol = str(mdata.get("volume") or "N/A")
        
        if direction == "gainers" and chg < 0:
            continue
        if direction == "losers" and chg > 0:
            continue
            
        ticker_has_earnings = bool(mdata.get("has_earnings_today", False))
        if earnings_soon is True and not ticker_has_earnings:
            continue
        if earnings_soon is False and ticker_has_earnings:
            continue
            
        hard_flags = []
        if scan.veto_rule:
            hard_flags.append(scan.veto_rule)
        for flog in scan.factor_logs:
            if flog.vetoed and flog.factor_id not in hard_flags:
                hard_flags.append(flog.factor_id)
                
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
        
    # 2. Supplement from StockUniverse DB table across the entire universe with efficient DB pagination
    scans_count = len(results)
    supp_total = 0
    supp_items: list[StockListItemSchema] = []
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    
    if not direction and not earnings_soon and not risk_bucket:
        if min_score is None or min_score <= 5.0:
            existing_symbols = {r.symbol for r in results}
            supp_base_stmt = select(StockUniverse).where(
                StockUniverse.is_active == True,
                ~StockUniverse.ticker.in_(existing_symbols) if existing_symbols else True
            )
            if sector:
                supp_base_stmt = supp_base_stmt.where(StockUniverse.sector.ilike(f"%{sector}%"))
            if query_str:
                supp_base_stmt = supp_base_stmt.where(
                    (StockUniverse.ticker.ilike(f"%{query_str}%")) | (StockUniverse.name.ilike(f"%{query_str}%"))
                )
            
            # Efficient count query instead of fetching all objects
            count_stmt = select(func.count()).select_from(supp_base_stmt.subquery())
            raw_supp_total = (await session.execute(count_stmt)).scalar() or 0
            
            is_list_filtered = list_param and list_param.lower() in ("list1", "list_1", "list2", "list_2")
            target_list = "list1" if (list_param and list_param.lower() in ("list1", "list_1")) else "list2"
            
            supp_total = (raw_supp_total + 1) // 2 if is_list_filtered else raw_supp_total
            
            # Only query database rows if the requested page slice requires universe items
            if end_idx > scans_count and supp_total > 0:
                needed_from_supp = end_idx - max(start_idx, scans_count)
                supp_offset = max(0, start_idx - scans_count)
                
                # If list filtered (taking every other row), double offset and limit
                db_offset = supp_offset * 2 if is_list_filtered else supp_offset
                if is_list_filtered and target_list == "list2":
                    db_offset += 1
                db_limit = needed_from_supp * 2 if is_list_filtered else needed_from_supp
                
                supp_stmt = supp_base_stmt.order_by(StockUniverse.ticker).offset(db_offset).limit(db_limit)
                supp_rows = (await session.execute(supp_stmt)).scalars().all()
                
                for idx, u in enumerate(supp_rows):
                    if is_list_filtered and idx % 2 != 0:
                        continue
                    supp_items.append(
                        StockListItemSchema(
                            symbol=u.ticker,
                            name=u.name,
                            sector=u.sector or "US Equities",
                            price=0.0,
                            chg=0.0,
                            pct=0.0,
                            volume="N/A",
                            score=5.0,  # Baseline score until live evaluated on click
                            earningsSoon=False,
                            hardFlags=[],
                            sparkline=[0.0, 0.0, 0.0],
                            levels=SupportResistanceLevels(support=0.0, resistance=0.0),
                        )
                    )
                    if len(supp_items) >= needed_from_supp:
                        break

    total = scans_count + supp_total
    total_pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    # Construct final paginated slice for this page
    if start_idx < scans_count:
        paginated_results = results[start_idx:min(end_idx, scans_count)] + supp_items
    else:
        paginated_results = supp_items

    logger.info("[FLOW: Service Layer] <── get_stock_list: Returning page %d/%d (%d items, total %d) from DB", page, total_pages, len(paginated_results), total)
    return StockListResponseSchema(
        count=len(paginated_results),
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        results=paginated_results,
    )


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
        .order_by(DailyScan.id.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    scan = result.scalar_one_or_none()
    
    # Real name and sector from market_data stored at scan time or StockUniverse
    mdata = (scan.factor_results_json or {}).get("market_data", {}) if scan else {}
    real_name = mdata.get("name") or f"{symbol} Corp"
    real_sector = mdata.get("sector") or "Unknown"
    
    u = (await session.execute(select(StockUniverse).where(StockUniverse.ticker == symbol))).scalar_one_or_none()
    if u:
        if not real_name or real_name == f"{symbol} Corp":
            real_name = u.name or f"{symbol} Corp"
        if not real_sector or real_sector == "Unknown":
            real_sector = u.sector or "Unknown"

    # Fetch live quotes and news from Finnhub (No fallback data per user rule)
    client = FinnhubClient()
    price = scan.entry_price if (scan and scan.entry_price) else 0.0
    chg = 0.0
    pct = 0.0
    news_items = []
    quote = None
    try:
        quote = await client.get_quote(symbol, session=session)
        if quote and quote.current_price > 0:
            price = quote.current_price
            chg = quote.change
            pct = quote.change_percent
            
        if not real_sector or real_sector in ("Unknown", "US Equities"):
            profile = await client.get_company_profile(symbol, session=session)
            if profile.get("sector"):
                real_sector = profile["sector"]
            if profile.get("name") and (not real_name or real_name == f"{symbol} Corp" or real_name == symbol):
                real_name = profile["name"]
            if u and real_sector and real_sector not in ("Unknown", "US Equities"):
                u.sector = real_sector
                if real_name and real_name != f"{symbol} Corp" and real_name != symbol:
                    u.name = real_name
                await session.commit()
                logger.info("[FLOW: Service Layer] Enriched %s in StockUniverse with sector='%s' and name='%s'", symbol, real_sector, real_name)
            
        raw_news = await client.get_news(ticker=symbol, session=session)
        for n in raw_news[:5]:
            news_items.append(
                NewsItemSchema(
                    headline=n.headline,
                    source=n.source or "Market News",
                    publishedAt=n.published_at or datetime.now(timezone.utc).isoformat(),
                    url=n.url or "#",
                    summary=getattr(n, "summary", ""),
                )
            )
    except Exception as e:
        logger.warning("Failed to fetch Finnhub data for %s detail: %s", symbol, e)
    finally:
        await client.close()
        
    if not scan or not scan.factor_logs or len(scan.factor_logs) < 50:
        from app.services.scan_service import evaluate_and_persist_on_demand
        logger.info("[FLOW: Service Layer] Incomplete or missing scan for %s today (logs=%d). Triggering on-demand 50-factor evaluation...", symbol, len(scan.factor_logs) if scan and scan.factor_logs else 0)
        scan = await evaluate_and_persist_on_demand(session, symbol, quote, real_name, real_sector)
        if scan and scan.entry_price and price == 0.0:
            price = scan.entry_price

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
                if triggered > 0:
                    val = round((triggered / len(layer_flogs)) * 10.0, 1)
                else:
                    val = round(scan.score, 1)
            else:
                val = round(scan.score, 1)
        layer_scores.append(LayerScoreItem(layer=lname, value=val))
        
    # Generate bull / bear reasons and news summary via AI Synthesis Agent (with compliance filter and zero-mock fallback)
    reasons: list[ReasonItem] = []
    news_summary: Optional[str] = None
    if scan and scan.factor_logs:
        reasons, news_summary = await asyncio.gather(
            synthesize_reasons(
                symbol=symbol,
                score=score,
                factor_logs=list(scan.factor_logs),
                news=news_items,
            ),
            synthesize_news_summary(
                symbol=symbol,
                news=news_items,
            ),
        )
    elif news_items:
        news_summary = await synthesize_news_summary(symbol=symbol, news=news_items)
        
    if scan and scan.strike_price is None and scan.entry_price is not None:
        is_bullish = True
        if scan.veto_rule in ("F43", "F49"):
            is_bullish = False
        opt_res = await get_automated_option_contract(symbol, price, is_bullish)
        if opt_res:
            scan.strike_price = opt_res["strike_price"]
            try:
                session.add(scan)
                await session.commit()
            except Exception as e:
                logger.debug("Failed to commit automated strike price for %s: %s", symbol, e)

    return StockDetailSchema(
        id=scan.id if scan else None,
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
        newsSummary=news_summary,
        execution_details={
            "entry_price": scan.entry_price,
            "strike_price": scan.strike_price,
            "stop_loss": scan.stop_loss,
        } if scan else None,
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


async def get_stock_live_evaluation(session: AsyncSession, symbol: str) -> StockDetailSchema:
    """
    Step 3: On-demand live evaluation with Same-Day DB Caching Protocol.
    Triggered when a user clicks a stock row. Checks if live evaluation was already performed today.
    If cached, serves instantly from DB without external API calls.
    If not cached, queries SEC EDGAR for shelf registrations (F46), updates factor breakdown,
    records live_evaluated_at timestamp in Supabase, and returns refreshed details.
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

    if not scan:
        logger.warning("[FLOW: Lazy Live Eval] No daily scan found for %s on %s. Returning standard detail.", symbol, target_date)
        return await get_stock_detail(session, symbol)

    # Check Same-Day Cache
    today_date = datetime.now(timezone.utc).date()
    cached_date = scan.live_evaluated_at.date() if scan.live_evaluated_at else None
    if not cached_date and scan.factor_results_json:
        cached_str = scan.factor_results_json.get("live_evaluated_at")
        if cached_str:
            try:
                cached_date = datetime.fromisoformat(cached_str).date()
            except Exception:
                pass

    if cached_date == today_date:
        logger.info("[FLOW: Lazy Live Eval] ──> Same-Day Cache HIT for %s (evaluated at %s). Serving instantly from DB without API calls.", symbol, scan.live_evaluated_at or cached_date)
        return await get_stock_detail(session, symbol)

    logger.info("[FLOW: Lazy Live Eval] ──> Same-Day Cache MISS for %s. Triggering live on-demand SEC EDGAR & Technical evaluation...", symbol)

    # 1. Query StockUniverse for SEC CIK
    univ_stmt = select(StockUniverse).where(StockUniverse.ticker == symbol)
    univ_item = (await session.execute(univ_stmt)).scalar_one_or_none()
    cik = univ_item.cik if univ_item else None

    # 2. Query SEC EDGAR for Dilution / Shelf Registrations (F46)
    edgar_client = EdgarClient()
    try:
        edgar_res = await edgar_client.check_shelf_registration(cik=cik, session=session)
    finally:
        await edgar_client.close()

    # 3. Evaluate F46 factor with live EDGAR data
    mdata = (scan.factor_results_json or {}).get("market_data", {})
    is_near_ath = mdata.get("is_at_ath", False)

    ctx = ScanContext(
        ticker=symbol,
        scan_date=target_date.isoformat(),
        near_ath_proximity=is_near_ath,
        has_recent_shelf_filing=bool(edgar_res.get("has_shelf_filing")),
        shelf_filing_date=edgar_res.get("recent_filing_date"),
        shelf_form_type=edgar_res.get("form_type"),
        edgar_check_status=edgar_res.get("status"),
    )
    f46_checker = F46EDGARShelfCheck()
    new_fr = f46_checker.evaluate(ctx)

    # 4. Update FactorLog for F46 in DB
    for flog in scan.factor_logs:
        if flog.factor_id == "F46":
            flog.triggered = new_fr.triggered
            flog.vetoed = new_fr.vetoed
            flog.stubbed = new_fr.stubbed
            flog.result_detail_json = new_fr.model_dump()
            break

    # If F46 vetoed, lock the scan
    if new_fr.vetoed:
        scan.veto_rule = "F46"
        scan.veto_reason = new_fr.detail
        scan.status = ScanStatus.LOCKED

    # 5. Stamp Same-Day Cache timestamp
    now_utc = datetime.now(timezone.utc)
    scan.live_evaluated_at = now_utc
    if scan.factor_results_json is None:
        scan.factor_results_json = {}
    updated_json = dict(scan.factor_results_json)
    updated_json["live_evaluated_at"] = now_utc.isoformat()
    scan.factor_results_json = updated_json

    await session.commit()
    logger.info("[FLOW: Lazy Live Eval] <── Successfully evaluated and cached live EDGAR factors for %s at %s.", symbol, now_utc)

    # Return updated detail view
    return await get_stock_detail(session, symbol)

