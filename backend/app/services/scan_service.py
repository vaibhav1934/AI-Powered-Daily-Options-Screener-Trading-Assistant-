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
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.time_gate import get_cst_now, get_cutoff_status, is_fomc_day, is_friday, is_past_cutoff
from app.db.models import (
    AuditAction,
    AuditLog,
    DailyScan,
    FactorLog,
    ListType,
    Position,
    PositionStatus,
    RiskBucket,
    ScanStatus,
    StockUniverse,
)
from app.framework.engine import run_full_scan
from app.framework.dual_horizon import evaluate_dual_horizon
from app.framework.factors.registry import factor_registry
from app.core.market_data.free_signals import fetch_free_macro_signals, fetch_free_sector_signals
from app.core.market_data.edgar import EdgarClient
from app.core.market_data.technicals import fetch_technicals
from app.services.fundamentals_service import get_fundamentals
from app.services.options_service import get_automated_option_contract

logger = logging.getLogger(__name__)
_scan_lock = asyncio.Lock()
MIN_MARKET_CAP_USD = 1_000_000_000.0


_CATALYST_PATTERNS: dict[str, tuple[str, ...]] = {
    "analyst_day": (r"\banalyst day\b", r"\binvestor day\b"),
    "product_launch": (r"\bproduct launch\b", r"\bunveil\b", r"\blaunch event\b"),
    "fda_regulatory": (r"\bfda\b", r"\bapproval\b", r"\bphase [123]\b", r"\bregulatory\b"),
    "index_reconstitution": (r"\bindex\b", r"\brebalance\b", r"\breconstitution\b", r"\badd(ed)? to\b"),
}

_CB_SURPRISE_TOKENS: tuple[str, ...] = (
    "federal reserve",
    "fed",
    "ecb",
    "boj",
    "bank of japan",
    "pboc",
    "people's bank of china",
    "rate decision",
    "surprise",
    "unexpected",
    "hawkish",
    "dovish",
    "intervention",
)

_RETAIL_POSITIVE_TOKENS: tuple[str, ...] = (
    "to the moon",
    "breakout",
    "squeeze",
    "bullish",
    "calls",
    "momentum",
)

_RETAIL_NEGATIVE_TOKENS: tuple[str, ...] = (
    "rug",
    "dump",
    "bearish",
    "puts",
    "miss",
    "downgrade",
)


def _json_safe(value: Any) -> Any:
    """Convert mixed Python/Pydantic payloads into JSON-serializable structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        return _json_safe(model_dump())
    return str(value)


def _build_on_demand_api_audit(
    symbol: str,
    quote: Any,
    profile: dict[str, Any],
    earnings_entries: list[Any],
    analyst_actions: list[dict[str, Any]],
    earnings_history: list[dict[str, Any]],
    ticker_news: list[Any],
    general_news: list[Any],
    tech_data: dict[str, Any],
    sector_signals: dict[str, Any],
    macro_signals: dict[str, Any],
    fundamentals: dict[str, Any],
    option_contract_prefetch: Optional[dict[str, Any]],
    edgar_payload: Optional[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Capture live source calls and snapshots used to compute all 50 factors."""
    return [
        {
            "provider": "finnhub",
            "operation": "quote",
            "symbol": symbol,
            "output": _json_safe(quote),
        },
        {
            "provider": "finnhub",
            "operation": "company_profile",
            "symbol": symbol,
            "output": _json_safe(profile),
        },
        {
            "provider": "finnhub",
            "operation": "earnings_window_0_5d",
            "symbol": symbol,
            "output": _json_safe(earnings_entries),
        },
        {
            "provider": "finnhub",
            "operation": "upgrade_downgrade_actions_14d",
            "symbol": symbol,
            "output": _json_safe(analyst_actions),
        },
        {
            "provider": "finnhub",
            "operation": "company_earnings_history",
            "symbol": symbol,
            "output": _json_safe(earnings_history),
        },
        {
            "provider": "finnhub",
            "operation": "ticker_news",
            "symbol": symbol,
            "output": _json_safe(ticker_news[:20]),
        },
        {
            "provider": "finnhub",
            "operation": "general_news",
            "symbol": "MARKET",
            "output": _json_safe(general_news[:20]),
        },
        {
            "provider": "technicals",
            "operation": "fetch_technicals",
            "symbol": symbol,
            "output": _json_safe(tech_data),
        },
        {
            "provider": "free_signals",
            "operation": "fetch_free_sector_signals",
            "symbol": symbol,
            "output": _json_safe(sector_signals),
        },
        {
            "provider": "free_signals",
            "operation": "fetch_free_macro_signals",
            "symbol": "MARKET",
            "output": _json_safe(macro_signals),
        },
        {
            "provider": "fundamentals",
            "operation": "get_fundamentals",
            "symbol": symbol,
            "output": _json_safe(fundamentals),
        },
        {
            "provider": "options",
            "operation": "get_automated_option_contract_prefetch",
            "symbol": symbol,
            "output": _json_safe(option_contract_prefetch),
        },
        {
            "provider": "edgar",
            "operation": "check_shelf_registration",
            "symbol": symbol,
            "output": _json_safe(edgar_payload),
        },
    ]


def _extract_ticker_catalyst_flags(news_items: list[Any]) -> dict[str, bool]:
    """Derive catalyst booleans from live ticker news headlines/summaries."""
    text_blob = " ".join(
        f"{(n.headline or '').lower()} {(n.summary or '').lower()}"
        for n in news_items
    )
    return {
        "analyst_day_catalyst": any(re.search(p, text_blob) for p in _CATALYST_PATTERNS["analyst_day"]),
        "product_launch_catalyst": any(re.search(p, text_blob) for p in _CATALYST_PATTERNS["product_launch"]),
        "fda_regulatory_catalyst": any(re.search(p, text_blob) for p in _CATALYST_PATTERNS["fda_regulatory"]),
        "index_reconstitution_catalyst": any(re.search(p, text_blob) for p in _CATALYST_PATTERNS["index_reconstitution"]),
    }


def _extract_sector_macro_flags(news_items: list[Any]) -> dict[str, bool]:
    """Derive sector-wide macro catalysts from live general-news headlines/summaries."""
    text_blob = " ".join(
        f"{(n.headline or '').lower()} {(n.summary or '').lower()}"
        for n in news_items
    )
    return {
        "opec_event": bool(re.search(r"\bopec\b|\boil output\b|\bproduction cut\b", text_blob)),
        "macro_data_print_event": bool(re.search(r"\bcpi\b|\bppi\b|\bnfp\b|\bpayrolls\b|\bgdp\b|\bism\b", text_blob)),
    }


def _extract_central_bank_surprise_signal(news_items: list[Any]) -> tuple[bool, float]:
    """Return a boolean/score proxy for central-bank surprise context from headlines."""
    text_blob = " ".join(
        f"{(n.headline or '').lower()} {(n.summary or '').lower()}"
        for n in news_items
    )
    token_hits = sum(1 for tok in _CB_SURPRISE_TOKENS if tok in text_blob)
    surprise_hits = sum(1 for tok in ("surprise", "unexpected", "intervention") if tok in text_blob)
    score = min(1.0, (token_hits * 0.08) + (surprise_hits * 0.25))
    return score >= 0.35, round(score, 4)


def _score_retail_sentiment_proxy(news_items: list[Any]) -> Optional[float]:
    """Compute a bounded retail sentiment proxy score in [-1, 1] from free news text."""
    if not news_items:
        return None

    text_blob = " ".join(
        f"{(n.headline or '').lower()} {(n.summary or '').lower()}"
        for n in news_items
    )
    if not text_blob.strip():
        return None

    pos = sum(text_blob.count(tok) for tok in _RETAIL_POSITIVE_TOKENS)
    neg = sum(text_blob.count(tok) for tok in _RETAIL_NEGATIVE_TOKENS)
    total = pos + neg
    if total == 0:
        return 0.0
    raw = (pos - neg) / total
    return round(max(-1.0, min(1.0, raw)), 4)


def _compute_whisper_gap_proxy(
    earnings_within_window: bool,
    put_call_oi_ratio: Optional[float],
    analyst_rating_change: bool,
    retail_sentiment_score: Optional[float],
) -> Optional[float]:
    """
    Free proxy for whisper-vs-consensus bias in [-1, 1].
    Uses options crowding + analyst activity + retail tone near earnings.
    """
    if not earnings_within_window:
        return None

    score = 0.0
    used = False
    if isinstance(put_call_oi_ratio, (int, float)):
        used = True
        ratio = float(put_call_oi_ratio)
        if ratio <= 0.85:
            score += 0.45
        elif ratio >= 1.15:
            score -= 0.45

    if analyst_rating_change:
        used = True
        score += 0.2

    if isinstance(retail_sentiment_score, (int, float)):
        used = True
        score += max(-0.35, min(0.35, float(retail_sentiment_score) * 0.35))

    if not used:
        return None
    return round(max(-1.0, min(1.0, score)), 4)


def _compute_guidance_revision_trend_proxy(earnings_history_rows: list[dict[str, Any]]) -> Optional[float]:
    """
    Free proxy for guidance-trend quality using quarterly surprise trend.
    Positive means improving trajectory over trailing quarters.
    """
    surprises: list[float] = []
    for row in earnings_history_rows[:8]:
        val = row.get("surprisePercent")
        if isinstance(val, (int, float)):
            surprises.append(float(val))

    if len(surprises) < 4:
        return None

    recent = surprises[:2]
    prior = surprises[2:4]
    recent_avg = sum(recent) / len(recent)
    prior_avg = sum(prior) / len(prior)
    return round(recent_avg - prior_avg, 4)


def _compute_option_volume_oi_ratio(option_contract: Optional[dict[str, Any]]) -> Optional[float]:
    if not option_contract:
        return None
    vol = option_contract.get("volume")
    oi = option_contract.get("open_interest")
    if not isinstance(vol, (int, float)) or not isinstance(oi, (int, float)):
        return None
    if float(oi) <= 0:
        return None
    return round(float(vol) / float(oi), 4)


def _compute_dealer_gamma_proxy(
    put_call_oi_ratio: Optional[float],
    skew_signal: Optional[str],
    iv_rank_1y: Optional[float],
) -> Optional[str]:
    """Heuristic free proxy for dealer-gamma regime classification."""
    if not isinstance(put_call_oi_ratio, (int, float)) and not isinstance(iv_rank_1y, (int, float)) and not isinstance(skew_signal, str):
        return None

    score = 0.0
    if isinstance(put_call_oi_ratio, (int, float)):
        ratio = float(put_call_oi_ratio)
        if ratio < 0.9:
            score += 0.5
        elif ratio > 1.15:
            score -= 0.5

    if isinstance(iv_rank_1y, (int, float)):
        ivr = float(iv_rank_1y)
        if ivr <= 35.0:
            score += 0.3
        elif ivr >= 75.0:
            score -= 0.3

    if isinstance(skew_signal, str):
        sig = skew_signal.upper()
        if sig == "CALL_SPEC_HEAVY":
            score += 0.25
        elif sig == "PUT_HEDGE_HEAVY":
            score -= 0.25

    if score >= 0.35:
        return "POSITIVE_GAMMA_PROXY"
    if score <= -0.35:
        return "NEGATIVE_GAMMA_PROXY"
    return "NEUTRAL_GAMMA_PROXY"


def _derive_fed_policy_proxy(
    ust2y_yield: Optional[float],
    curve_change_5d_bps: Optional[float],
    dxy_change_5d: Optional[float],
    vix_spot: Optional[float],
) -> Optional[float]:
    """
    Free proxy for Fed path stance in [0, 1].
    0 = dovish-leaning, 1 = hawkish-leaning.
    """
    score = 0.5
    used = False
    if isinstance(ust2y_yield, (int, float)):
        used = True
        y2 = float(ust2y_yield)
        if y2 >= 4.5:
            score += 0.2
        elif y2 <= 3.25:
            score -= 0.2
    if isinstance(curve_change_5d_bps, (int, float)):
        used = True
        c = float(curve_change_5d_bps)
        if c <= -10.0:
            score += 0.15
        elif c >= 10.0:
            score -= 0.15
    if isinstance(dxy_change_5d, (int, float)):
        used = True
        d = float(dxy_change_5d)
        if d >= 0.01:
            score += 0.1
        elif d <= -0.01:
            score -= 0.1
    if isinstance(vix_spot, (int, float)):
        used = True
        v = float(vix_spot)
        if v >= 25.0:
            score -= 0.1

    if not used:
        return None
    return round(max(0.0, min(1.0, score)), 4)


async def _get_portfolio_sector_context(session: AsyncSession) -> tuple[dict[str, float], bool]:
    """Return sector exposure map and whether portfolio has any open positions."""
    open_pos_rows = (
        await session.execute(
            select(Position.symbol, Position.qty, Position.entry_price).where(
                Position.status == PositionStatus.OPEN
            )
        )
    ).all()
    if not open_pos_rows:
        return {}, False

    symbols = [str(r.symbol).upper() for r in open_pos_rows if r.symbol]
    univ_rows = (
        await session.execute(
            select(StockUniverse.ticker, StockUniverse.sector).where(StockUniverse.ticker.in_(symbols))
        )
    ).all()
    sector_by_ticker = {str(r.ticker).upper(): (r.sector or "Unknown") for r in univ_rows}

    total_notional = 0.0
    sector_notional: dict[str, float] = {}
    for row in open_pos_rows:
        sym = str(row.symbol).upper()
        sector = sector_by_ticker.get(sym, "Unknown")
        notional = float(row.qty or 0.0) * float(row.entry_price or 0.0)
        total_notional += notional
        sector_notional[sector] = sector_notional.get(sector, 0.0) + notional

    if total_notional <= 0:
        return {}, True

    exposure = {k: round(v / total_notional, 6) for k, v in sector_notional.items()}
    return exposure, True


def _parse_market_cap_to_usd(raw_market_cap: Any, numeric_unit: str = "usd") -> Optional[float]:
    """Parse market cap values into USD from numeric or T/B/M string forms."""
    if raw_market_cap is None:
        return None

    if isinstance(raw_market_cap, (int, float)):
        value = float(raw_market_cap)
        return value * 1_000_000.0 if numeric_unit == "millions" else value

    if isinstance(raw_market_cap, str):
        cap = raw_market_cap.strip().upper().replace(",", "")
        if not cap:
            return None

        multiplier = 1.0
        if cap.endswith("T"):
            multiplier = 1_000_000_000_000.0
            cap = cap[:-1]
        elif cap.endswith("B"):
            multiplier = 1_000_000_000.0
            cap = cap[:-1]
        elif cap.endswith("M"):
            multiplier = 1_000_000.0
            cap = cap[:-1]

        try:
            return float(cap) * multiplier
        except ValueError:
            return None

    return None


def _within_earnings_window(report_date: date, as_of_date: date, window_days: int = 5) -> bool:
    """Return True when earnings are within the configured holding window."""
    delta_days = (report_date - as_of_date).days
    return 0 <= delta_days <= window_days


def _infer_analyst_signal(actions: list[dict[str, Any]]) -> tuple[bool, Optional[int]]:
    """
    Infer whether there is a recent analyst rating action and approximate firm tier.
    Tiering is conservative and only applied when issuer name matches known top-tier firms.
    """
    if not actions:
        return False, None

    top_tier_tokens = (
        "goldman",
        "morgan stanley",
        "jp morgan",
        "jpmorgan",
        "bank of america",
        "ubs",
        "barclays",
        "citigroup",
        "deutsche bank",
        "wells fargo",
    )
    mid_tier_tokens = (
        "jefferies",
        "roth",
        "baird",
        "raymond james",
        "evercore",
        "piper",
    )

    best_tier: Optional[int] = None
    for action in actions:
        firm = str(action.get("company") or action.get("firm") or "").strip().lower()
        if not firm:
            continue
        if any(token in firm for token in top_tier_tokens):
            best_tier = 1
            break
        if best_tier is None and any(token in firm for token in mid_tier_tokens):
            best_tier = 2

    if best_tier is None:
        best_tier = 3
    return True, best_tier


def _apply_ecosystem_proxy_flags(tickers: list[dict[str, Any]]) -> None:
    """
    Apply a free-data ecosystem proxy: a ticker is flagged when another name in the
    same sector is up >=10% in the current scan cohort.
    """
    sector_movers: dict[str, list[str]] = {}
    for item in tickers:
        sector = str(item.get("sector") or "Unknown")
        change_percent = item.get("change_percent")
        if isinstance(change_percent, (int, float)) and float(change_percent) >= 10.0:
            sector_movers.setdefault(sector, []).append(str(item.get("ticker") or ""))

    for item in tickers:
        ticker = str(item.get("ticker") or "")
        sector = str(item.get("sector") or "Unknown")
        movers = [m for m in sector_movers.get(sector, []) if m and m != ticker]
        item["ecosystem_partner_10pct_move"] = len(movers) > 0


async def _enrich_edgar_batch(tickers: list[dict[str, Any]], cik_by_ticker: dict[str, str]) -> None:
    """Attach EDGAR shelf-check fields for near-ATH names during batch scan."""
    if not tickers:
        return

    sem = asyncio.Semaphore(5)
    edgar_client = EdgarClient()

    async def _enrich_one(item: dict[str, Any]) -> None:
        if not bool(item.get("near_ath_proximity", False)):
            item["edgar_check_status"] = "SKIPPED_NOT_NEAR_ATH"
            item["has_recent_shelf_filing"] = False
            item["shelf_filing_date"] = None
            item["shelf_form_type"] = None
            return

        ticker = str(item.get("ticker") or "").upper()
        cik = cik_by_ticker.get(ticker)
        if not cik:
            item["edgar_check_status"] = "UNCONFIGURED"
            item["has_recent_shelf_filing"] = False
            item["shelf_filing_date"] = None
            item["shelf_form_type"] = None
            return

        async with sem:
            result = await edgar_client.check_shelf_registration(cik=cik)
            item["edgar_check_status"] = result.get("status")
            item["has_recent_shelf_filing"] = bool(result.get("has_shelf_filing"))
            item["shelf_filing_date"] = result.get("recent_filing_date")
            item["shelf_form_type"] = result.get("form_type")

    try:
        await asyncio.gather(*[_enrich_one(item) for item in tickers])
    finally:
        await edgar_client.close()


async def trigger_scan(
    session: AsyncSession,
    scan_date: Optional[date] = None,
    batch_size: int = 20,
) -> dict[str, Any]:
    if _scan_lock.locked():
        return {
            "job_id": None,
            "scan_date": (scan_date or date.today()).isoformat(),
            "tickers_scanned": 0,
            "status": "SCAN_ALREADY_RUNNING",
            "message": "A scan is already in progress. Wait for completion before triggering another run.",
            "factor_coverage": factor_registry.coverage_report(),
        }

    async with _scan_lock:
        return await _trigger_scan_impl(session, scan_date=scan_date, batch_size=batch_size)


async def _trigger_scan_impl(
    session: AsyncSession,
    scan_date: Optional[date] = None,
    batch_size: int = 20,
) -> dict[str, Any]:
    """
    Internal scan implementation guarded by _scan_lock in trigger_scan().
    """
    if scan_date is None:
        scan_date = date.today()
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
        cik_rows = await read_session.execute(
            select(StockUniverse.ticker, StockUniverse.cik).where(StockUniverse.cik.is_not(None))
        )
        cik_by_ticker = {
            str(row.ticker).upper(): str(row.cik).zfill(10)
            for row in cik_rows.fetchall()
            if row.ticker and row.cik
        }
        portfolio_sector_exposure, has_open_positions = await _get_portfolio_sector_context(read_session)
        await read_session.commit()

    # Build macro context from server-authoritative time
    now = get_cst_now()

    kospi_change = 0.0
    ceasefire = False

    # --- Phase 2: Finnhub data fetch (each subtask uses its own session) ---
    # This phase can take 30-90 seconds. We do NOT hold any DB session open here.
    tickers: list[dict[str, Any]] = []
    market_cap_filtered_count = 0
    calendar: list[Any] = []
    sector_macro_flags = {"opec_event": False, "macro_data_print_event": False}
    central_bank_surprise = False
    central_bank_surprise_score = 0.0
    free_macro_signals = await fetch_free_macro_signals()

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
            sector_macro_flags = _extract_sector_macro_flags(news_items)
            central_bank_surprise, central_bank_surprise_score = _extract_central_bank_surprise_signal(news_items)
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
                "tickers_filtered_market_cap": 0,
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
                        profile = await client.get_company_profile(entry.ticker, session=task_session)
                        
                        # Finnhub company profile market cap is in millions USD.
                        market_cap_usd = _parse_market_cap_to_usd(profile.get("market_cap"), numeric_unit="millions")
                        if market_cap_usd is None or market_cap_usd < MIN_MARKET_CAP_USD:
                            logger.info(
                                "Skipping %s due to market cap filter. market_cap_usd=%s min_required=%s",
                                entry.ticker,
                                market_cap_usd,
                                MIN_MARKET_CAP_USD,
                            )
                            return {
                                "_skip_reason": "MARKET_CAP_BELOW_1B",
                                "ticker": entry.ticker,
                                "market_cap_usd": market_cap_usd,
                            }

                        quote = await client.get_quote(entry.ticker, session=task_session)
                        gap = quote.change_percent
                        tech_data = await fetch_technicals(entry.ticker, quote.current_price, task_session)
                        fundamentals = await get_fundamentals(entry.ticker)
                        ticker_news = await client.get_news(ticker=entry.ticker, session=task_session)
                        analyst_actions = await client.get_upgrade_downgrade_actions(entry.ticker, session=task_session)
                        earnings_history = await client.get_company_earnings_history(entry.ticker, session=task_session)
                        analyst_rating_change, analyst_firm_tier = _infer_analyst_signal(analyst_actions)
                        catalyst_flags = _extract_ticker_catalyst_flags(ticker_news)
                        sector_signals = await fetch_free_sector_signals(entry.ticker, profile.get("sector") or "Unknown")
                        
                        # Format volume as readable string
                        vol = quote.volume or 0
                        vol_str = f"{vol / 1_000_000:.1f}M" if vol >= 1_000_000 else f"{vol / 1_000:.1f}K" if vol >= 1_000 else str(vol)
                        is_bullish = not ((tech_data.get("rsi") and tech_data.get("rsi") > 70) or gap < -2.0)
                        option_contract_res = await get_automated_option_contract(entry.ticker, quote.current_price, is_bullish)
                        option_volume_oi_ratio = _compute_option_volume_oi_ratio(option_contract_res)
                        retail_sentiment_score = _score_retail_sentiment_proxy(ticker_news)
                        whisper_eps_gap_proxy = _compute_whisper_gap_proxy(
                            earnings_within_window=_within_earnings_window(entry.report_date, scan_date),
                            put_call_oi_ratio=(option_contract_res.get("put_call_oi_ratio") if option_contract_res else None),
                            analyst_rating_change=analyst_rating_change,
                            retail_sentiment_score=retail_sentiment_score,
                        )
                        guidance_revision_trend_4q = _compute_guidance_revision_trend_proxy(earnings_history)
                        dealer_gamma_regime_proxy = _compute_dealer_gamma_proxy(
                            put_call_oi_ratio=(option_contract_res.get("put_call_oi_ratio") if option_contract_res else None),
                            skew_signal=(option_contract_res.get("skew_signal") if option_contract_res else None),
                            iv_rank_1y=(option_contract_res.get("iv_rank_1y") if option_contract_res else None),
                        )
                        
                        return {
                            "ticker": entry.ticker,
                            "change_percent": gap,
                            "current_price": quote.current_price,
                            "open_price": quote.open_price,
                            "high_price": quote.high_price,
                            "low_price": quote.low_price,
                            "previous_close": quote.previous_close,
                            "has_earnings_today": True,
                            "earnings_within_window": _within_earnings_window(entry.report_date, scan_date),
                            "eps_estimate": entry.eps_estimate,
                            "eps_actual": entry.eps_actual,
                            "revenue_estimate": entry.revenue_estimate,
                            "revenue_actual": entry.revenue_actual,
                            "is_after_hours_beat": bool(entry.is_after_hours and entry.eps_actual is not None and entry.eps_estimate is not None and entry.eps_actual > entry.eps_estimate),
                            "rsi": tech_data.get("rsi"),
                            "sma_50": tech_data.get("sma_50"),
                            "sma_200": tech_data.get("sma_200"),
                            "is_at_ath": tech_data.get("is_at_ath", False),
                            "near_ath_proximity": tech_data.get("is_at_ath", False),
                            "gap_present": tech_data.get("gap_present", False),
                            "gap_hold_valid": tech_data.get("gap_hold_valid", False),
                            "mtf_trend_aligned": tech_data.get("mtf_trend_aligned", False),
                            "relative_volume": tech_data.get("relative_volume"),
                            "volume_profile_state": tech_data.get("volume_profile_state"),
                            "volume_profile_hvn": tech_data.get("volume_profile_hvn"),
                            "volume_profile_lvn": tech_data.get("volume_profile_lvn"),
                            "name": profile.get("name") or entry.ticker,
                            "sector": profile.get("sector") or "Unknown",
                            "sector_etf_symbol": sector_signals.get("sector_etf_symbol"),
                            "sector_rs_5d": sector_signals.get("sector_rs_5d"),
                            "sector_rs_20d": sector_signals.get("sector_rs_20d"),
                            "ticker_sector_corr_20d": sector_signals.get("ticker_sector_corr_20d"),
                            "idiosyncratic_alpha_20d": sector_signals.get("idiosyncratic_alpha_20d"),
                            "sector_flow_score": sector_signals.get("sector_flow_score"),
                            "market_cap_usd": market_cap_usd,
                            "portfolio_sector_exposure": portfolio_sector_exposure.get(profile.get("sector") or "Unknown"),
                            "portfolio_underweight_sector": (
                                has_open_positions
                                and (portfolio_sector_exposure.get(profile.get("sector") or "Unknown", 0.0) < 0.10)
                            ),
                            "sector_macro_catalyst": bool(
                                sector_macro_flags.get("opec_event")
                                or sector_macro_flags.get("macro_data_print_event")
                                or is_fomc_day(now)
                            ),
                            "analyst_day_catalyst": catalyst_flags.get("analyst_day_catalyst", False),
                            "product_launch_catalyst": catalyst_flags.get("product_launch_catalyst", False),
                            "fda_regulatory_catalyst": catalyst_flags.get("fda_regulatory_catalyst", False),
                            "index_reconstitution_catalyst": catalyst_flags.get("index_reconstitution_catalyst", False),
                            "analyst_rating_change": analyst_rating_change,
                            "analyst_firm_tier": analyst_firm_tier,
                            "change": quote.change,
                            "volume_str": vol_str,
                            "iv_rank_1y": option_contract_res.get("iv_rank_1y") if option_contract_res else None,
                            "iv_crush_risk": option_contract_res.get("iv_crush_risk") if option_contract_res else None,
                            "put_call_oi_ratio": option_contract_res.get("put_call_oi_ratio") if option_contract_res else None,
                            "skew_signal": option_contract_res.get("skew_signal") if option_contract_res else None,
                            "option_open_interest": option_contract_res.get("open_interest") if option_contract_res else None,
                            "option_volume": option_contract_res.get("volume") if option_contract_res else None,
                            "option_bid": option_contract_res.get("bid") if option_contract_res else None,
                            "option_ask": option_contract_res.get("ask") if option_contract_res else None,
                            "option_mid_price": option_contract_res.get("mid_price") if option_contract_res else None,
                            "option_delta": option_contract_res.get("option_delta") if option_contract_res else None,
                            "option_theta_daily": option_contract_res.get("option_theta_daily") if option_contract_res else None,
                            "option_dte": option_contract_res.get("option_dte") if option_contract_res else None,
                            "option_volume_oi_ratio": option_volume_oi_ratio,
                            "dealer_gamma_regime_proxy": dealer_gamma_regime_proxy,
                            "revenue_growth": fundamentals.get("revenue_growth"),
                            "gross_margin": fundamentals.get("gross_margin"),
                            "operating_margin": fundamentals.get("operating_margin"),
                            "free_cash_flow": fundamentals.get("free_cash_flow"),
                            "debt_to_equity": fundamentals.get("debt_to_equity"),
                            "interest_coverage": fundamentals.get("interest_coverage"),
                            "insider_ownership": fundamentals.get("insider_ownership"),
                            "institutional_ownership": fundamentals.get("institutional_ownership"),
                            "return_on_equity": fundamentals.get("return_on_equity"),
                            "return_on_assets": fundamentals.get("return_on_assets"),
                            "shares_outstanding_change": fundamentals.get("shares_outstanding_change"),
                            "short_ratio": fundamentals.get("short_ratio"),
                            "short_percent_float": fundamentals.get("short_percent_float"),
                            "whisper_eps_gap_proxy": whisper_eps_gap_proxy,
                            "guidance_revision_trend_4q": guidance_revision_trend_4q,
                            "retail_sentiment_score": retail_sentiment_score,
                            "trailing_pe": fundamentals.get("trailing_pe"),
                            "forward_pe": fundamentals.get("forward_pe"),
                            "peg_ratio": fundamentals.get("peg_ratio"),
                            "has_recent_shelf_filing": False,
                            "shelf_filing_date": None,
                            "shelf_form_type": None,
                            "edgar_check_status": None,
                        }
                    except Exception as e:
                        logger.warning("Skipping %s due to error: %s", entry.ticker, e)
                        return None
                
        # Run API calls concurrently to speed up the scan
        tasks = [fetch_ticker_data(entry) for entry in calendar_subset]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in results:
            if isinstance(res, dict):
                if res.get("_skip_reason") == "MARKET_CAP_BELOW_1B":
                    market_cap_filtered_count += 1
                    continue
                tickers.append(res)

        _apply_ecosystem_proxy_flags(tickers)
        await _enrich_edgar_batch(tickers, cik_by_ticker)
                
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
        "opec_event": bool(sector_macro_flags.get("opec_event", False)),
        "macro_data_print_event": bool(sector_macro_flags.get("macro_data_print_event", False)),
        "central_bank_surprise_proxy": central_bank_surprise,
        "central_bank_surprise_score": central_bank_surprise_score,
        "fed_policy_prob_proxy": _derive_fed_policy_proxy(
            free_macro_signals.get("ust2y_yield"),
            free_macro_signals.get("curve_change_5d_bps"),
            free_macro_signals.get("dxy_change_5d"),
            free_macro_signals.get("vix_spot"),
        ),
        **free_macro_signals,
    }

    # Safety guard: abort if no data to avoid wiping existing DB records
    if not tickers:
        logger.warning("No real market data fetched. Aborting scan to preserve existing data.")
        return {
            "job_id": job_id,
            "scan_date": scan_date.isoformat(),
            "tickers_scanned": 0,
            "tickers_filtered_market_cap": market_cap_filtered_count,
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
                    ctx.iv_rank_1y = option_contract_res.get("iv_rank_1y")
                    ctx.iv_crush_risk = option_contract_res.get("iv_crush_risk")
                    ctx.put_call_oi_ratio = option_contract_res.get("put_call_oi_ratio")
                    ctx.skew_signal = option_contract_res.get("skew_signal")
                    ctx.option_open_interest = option_contract_res.get("open_interest")
                    ctx.option_volume = option_contract_res.get("volume")
                    ctx.option_bid = option_contract_res.get("bid")
                    ctx.option_ask = option_contract_res.get("ask")
                    ctx.option_mid_price = option_contract_res.get("mid_price")
                    ctx.option_delta = option_contract_res.get("option_delta")
                    ctx.option_theta_daily = option_contract_res.get("option_theta_daily")
                    ctx.option_dte = option_contract_res.get("option_dte")
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
                "tickers_filtered_market_cap": market_cap_filtered_count,
                "factor_coverage": factor_registry.coverage_report(),
            },
        )
        write_session.add(audit_complete)
        await write_session.commit()

    return {
        "job_id": job_id,
        "scan_date": scan_date.isoformat(),
        "tickers_scanned": persisted_count,
        "tickers_filtered_market_cap": market_cap_filtered_count,
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
    quote: Any = None,
    name: str = "",
    sector: str = "",
) -> Optional[DailyScan]:
    """
    Run on-demand 50-factor evaluation for a single ticker that was missed by morning batch scan.
    Persists DailyScan and 50 FactorLog entries to Postgres for same-day caching.
    """
    if symbol.upper() in ("DUAL-HORIZON", "DUAL_HORIZON", "FAVORITES", "WATCHLIST"):
        logger.warning("evaluate_and_persist_on_demand explicitly blocking meta-ticker: %s", symbol)
        return None

    try:
        from app.core.market_data.technicals import fetch_technicals
        from app.core.market_data.finnhub import FinnhubClient

        portfolio_sector_exposure, has_open_positions = await _get_portfolio_sector_context(session)

        profile_client = FinnhubClient()
        try:
            if quote is None:
                quote = await profile_client.get_quote(symbol, session=session)
            profile = await profile_client.get_company_profile(symbol, session=session)
            if not name:
                name = profile.get("name") or symbol
            if not sector or sector in ("Unknown", "US Equities"):
                sector = profile.get("sector") or sector or "US Equities"
            earnings_entries = await profile_client.get_earnings_for_symbol_window(
                symbol,
                start_date=date.today(),
                end_date=date.today() + timedelta(days=5),
                session=session,
            )
            analyst_actions = await profile_client.get_upgrade_downgrade_actions(symbol, session=session)
            earnings_history = await profile_client.get_company_earnings_history(symbol, session=session)
            ticker_news = await profile_client.get_news(ticker=symbol, session=session)
            general_news = await profile_client.get_news(category="general", session=session)
        finally:
            await profile_client.close()

        analyst_rating_change, analyst_firm_tier = _infer_analyst_signal(analyst_actions)
        next_earnings = min(earnings_entries, key=lambda e: e.report_date) if earnings_entries else None
        has_earnings_today = bool(next_earnings and next_earnings.report_date == date.today())
        earnings_within_window = bool(next_earnings and _within_earnings_window(next_earnings.report_date, date.today()))

        cik_row = await session.execute(
            select(StockUniverse.cik).where(StockUniverse.ticker == symbol.upper())
        )
        cik_value = cik_row.scalar_one_or_none()
        edgar_status = None
        has_recent_shelf_filing = False
        shelf_filing_date = None
        shelf_form_type = None
        edgar_payload: Optional[dict[str, Any]] = None

        market_cap_usd = _parse_market_cap_to_usd(profile.get("market_cap"), numeric_unit="millions")
        if market_cap_usd is None or market_cap_usd < MIN_MARKET_CAP_USD:
            logger.info(
                "On-demand scan skipped for %s due to market cap filter. market_cap_usd=%s min_required=%s",
                symbol,
                market_cap_usd,
                MIN_MARKET_CAP_USD,
            )
            return None

        tech_data = await fetch_technicals(symbol, quote.current_price if quote else 0.0, session)

        if tech_data.get("is_at_ath", False):
            edgar_client = EdgarClient()
            try:
                edgar_res = await edgar_client.check_shelf_registration(cik=str(cik_value).zfill(10) if cik_value else None, session=session)
                edgar_payload = dict(edgar_res)
                edgar_status = edgar_res.get("status")
                has_recent_shelf_filing = bool(edgar_res.get("has_shelf_filing"))
                shelf_filing_date = edgar_res.get("recent_filing_date")
                shelf_form_type = edgar_res.get("form_type")
            finally:
                await edgar_client.close()
        else:
            edgar_status = "SKIPPED_NOT_NEAR_ATH"
            edgar_payload = {"status": edgar_status}
        fundamentals = await get_fundamentals(symbol)
        sector_signals = await fetch_free_sector_signals(symbol, sector or "Unknown")
        macro_signals = await fetch_free_macro_signals()
        central_bank_surprise, central_bank_surprise_score = _extract_central_bank_surprise_signal(general_news)
        macro_signals["central_bank_surprise_proxy"] = central_bank_surprise
        macro_signals["central_bank_surprise_score"] = central_bank_surprise_score
        macro_signals["fed_policy_prob_proxy"] = _derive_fed_policy_proxy(
            macro_signals.get("ust2y_yield"),
            macro_signals.get("curve_change_5d_bps"),
            macro_signals.get("dxy_change_5d"),
            macro_signals.get("vix_spot"),
        )
        vol = quote.volume if quote else 0
        vol_str = f"{vol / 1_000_000:.1f}M" if vol >= 1_000_000 else f"{vol / 1_000:.1f}K" if vol >= 1_000 else str(vol)
        is_bullish_prefetch = not ((tech_data.get("rsi") and tech_data.get("rsi") > 70) or ((quote.change_percent if quote else 0.0) < -2.0))
        option_contract_prefetch = await get_automated_option_contract(symbol, quote.current_price if quote else 0.0, is_bullish_prefetch) if quote else None
        option_volume_oi_ratio = _compute_option_volume_oi_ratio(option_contract_prefetch)
        retail_sentiment_score = _score_retail_sentiment_proxy(ticker_news)
        whisper_eps_gap_proxy = _compute_whisper_gap_proxy(
            earnings_within_window=earnings_within_window,
            put_call_oi_ratio=(option_contract_prefetch.get("put_call_oi_ratio") if option_contract_prefetch else None),
            analyst_rating_change=analyst_rating_change,
            retail_sentiment_score=retail_sentiment_score,
        )
        guidance_revision_trend_4q = _compute_guidance_revision_trend_proxy(earnings_history)
        dealer_gamma_regime_proxy = _compute_dealer_gamma_proxy(
            put_call_oi_ratio=(option_contract_prefetch.get("put_call_oi_ratio") if option_contract_prefetch else None),
            skew_signal=(option_contract_prefetch.get("skew_signal") if option_contract_prefetch else None),
            iv_rank_1y=(option_contract_prefetch.get("iv_rank_1y") if option_contract_prefetch else None),
        )
        api_call_audit = _build_on_demand_api_audit(
            symbol=symbol.upper(),
            quote=quote,
            profile=profile,
            earnings_entries=earnings_entries,
            analyst_actions=analyst_actions,
            earnings_history=earnings_history,
            ticker_news=ticker_news,
            general_news=general_news,
            tech_data=tech_data,
            sector_signals=sector_signals,
            macro_signals=macro_signals,
            fundamentals=fundamentals,
            option_contract_prefetch=option_contract_prefetch,
            edgar_payload=edgar_payload,
        )
        
        ticker_data = {
            "ticker": symbol.upper(),
            "change_percent": quote.change_percent if quote else 0.0,
            "current_price": quote.current_price if quote else 0.0,
            "open_price": quote.open_price if quote else 0.0,
            "high_price": quote.high_price if quote else 0.0,
            "low_price": quote.low_price if quote else 0.0,
            "previous_close": quote.previous_close if quote else 0.0,
            "has_earnings_today": has_earnings_today,
            "earnings_within_window": earnings_within_window,
            "eps_estimate": next_earnings.eps_estimate if next_earnings else None,
            "eps_actual": next_earnings.eps_actual if next_earnings else None,
            "revenue_estimate": next_earnings.revenue_estimate if next_earnings else None,
            "revenue_actual": next_earnings.revenue_actual if next_earnings else None,
            "is_after_hours_beat": bool(
                next_earnings
                and next_earnings.is_after_hours
                and next_earnings.eps_actual is not None
                and next_earnings.eps_estimate is not None
                and next_earnings.eps_actual > next_earnings.eps_estimate
            ),
            "rsi": tech_data.get("rsi"),
            "sma_50": tech_data.get("sma_50"),
            "sma_200": tech_data.get("sma_200"),
            "is_at_ath": tech_data.get("is_at_ath", False),
            "near_ath_proximity": tech_data.get("is_at_ath", False),
            "gap_present": tech_data.get("gap_present", False),
            "gap_hold_valid": tech_data.get("gap_hold_valid", False),
            "mtf_trend_aligned": tech_data.get("mtf_trend_aligned", False),
            "relative_volume": tech_data.get("relative_volume"),
            "volume_profile_state": tech_data.get("volume_profile_state"),
            "volume_profile_hvn": tech_data.get("volume_profile_hvn"),
            "volume_profile_lvn": tech_data.get("volume_profile_lvn"),
            "name": name or symbol,
            "sector": sector or "Unknown",
            "sector_etf_symbol": sector_signals.get("sector_etf_symbol"),
            "sector_rs_5d": sector_signals.get("sector_rs_5d"),
            "sector_rs_20d": sector_signals.get("sector_rs_20d"),
            "ticker_sector_corr_20d": sector_signals.get("ticker_sector_corr_20d"),
            "idiosyncratic_alpha_20d": sector_signals.get("idiosyncratic_alpha_20d"),
            "sector_flow_score": sector_signals.get("sector_flow_score"),
            "market_cap_usd": market_cap_usd,
            "portfolio_sector_exposure": portfolio_sector_exposure.get(sector or "Unknown"),
            "portfolio_underweight_sector": (
                has_open_positions
                and (portfolio_sector_exposure.get(sector or "Unknown", 0.0) < 0.10)
            ),
            "sector_macro_catalyst": False,
            "analyst_day_catalyst": False,
            "product_launch_catalyst": False,
            "fda_regulatory_catalyst": False,
            "index_reconstitution_catalyst": False,
            "ecosystem_partner_10pct_move": False,
            "analyst_rating_change": analyst_rating_change,
            "analyst_firm_tier": analyst_firm_tier,
            "change": quote.change if quote else 0.0,
            "volume_str": vol_str,
            "iv_rank_1y": option_contract_prefetch.get("iv_rank_1y") if option_contract_prefetch else None,
            "iv_crush_risk": option_contract_prefetch.get("iv_crush_risk") if option_contract_prefetch else None,
            "put_call_oi_ratio": option_contract_prefetch.get("put_call_oi_ratio") if option_contract_prefetch else None,
            "skew_signal": option_contract_prefetch.get("skew_signal") if option_contract_prefetch else None,
            "option_open_interest": option_contract_prefetch.get("open_interest") if option_contract_prefetch else None,
            "option_volume": option_contract_prefetch.get("volume") if option_contract_prefetch else None,
            "option_bid": option_contract_prefetch.get("bid") if option_contract_prefetch else None,
            "option_ask": option_contract_prefetch.get("ask") if option_contract_prefetch else None,
            "option_mid_price": option_contract_prefetch.get("mid_price") if option_contract_prefetch else None,
            "option_delta": option_contract_prefetch.get("option_delta") if option_contract_prefetch else None,
            "option_theta_daily": option_contract_prefetch.get("option_theta_daily") if option_contract_prefetch else None,
            "option_dte": option_contract_prefetch.get("option_dte") if option_contract_prefetch else None,
            "option_volume_oi_ratio": option_volume_oi_ratio,
            "dealer_gamma_regime_proxy": dealer_gamma_regime_proxy,
            "revenue_growth": fundamentals.get("revenue_growth"),
            "gross_margin": fundamentals.get("gross_margin"),
            "operating_margin": fundamentals.get("operating_margin"),
            "free_cash_flow": fundamentals.get("free_cash_flow"),
            "debt_to_equity": fundamentals.get("debt_to_equity"),
            "interest_coverage": fundamentals.get("interest_coverage"),
            "insider_ownership": fundamentals.get("insider_ownership"),
            "institutional_ownership": fundamentals.get("institutional_ownership"),
            "return_on_equity": fundamentals.get("return_on_equity"),
            "return_on_assets": fundamentals.get("return_on_assets"),
            "shares_outstanding_change": fundamentals.get("shares_outstanding_change"),
            "short_ratio": fundamentals.get("short_ratio"),
            "short_percent_float": fundamentals.get("short_percent_float"),
            "whisper_eps_gap_proxy": whisper_eps_gap_proxy,
            "guidance_revision_trend_4q": guidance_revision_trend_4q,
            "retail_sentiment_score": retail_sentiment_score,
            "trailing_pe": fundamentals.get("trailing_pe"),
            "forward_pe": fundamentals.get("forward_pe"),
            "peg_ratio": fundamentals.get("peg_ratio"),
            "has_recent_shelf_filing": has_recent_shelf_filing,
            "shelf_filing_date": shelf_filing_date,
            "shelf_form_type": shelf_form_type,
            "edgar_check_status": edgar_status,
        }
        
        from app.framework.engine import run_full_scan
        from app.framework.factors.registry import factor_registry
        scan_results = run_full_scan([ticker_data], macro_signals, date.today())
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
                ctx.iv_rank_1y = option_contract_res.get("iv_rank_1y")
                ctx.iv_crush_risk = option_contract_res.get("iv_crush_risk")
                ctx.put_call_oi_ratio = option_contract_res.get("put_call_oi_ratio")
                ctx.skew_signal = option_contract_res.get("skew_signal")
                ctx.option_open_interest = option_contract_res.get("open_interest")
                ctx.option_volume = option_contract_res.get("volume")
                ctx.option_bid = option_contract_res.get("bid")
                ctx.option_ask = option_contract_res.get("ask")
                ctx.option_mid_price = option_contract_res.get("mid_price")
                ctx.option_delta = option_contract_res.get("option_delta")
                ctx.option_theta_daily = option_contract_res.get("option_theta_daily")
                ctx.option_dte = option_contract_res.get("option_dte")
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
                "audit_api_calls": api_call_audit,
                "audit_context_snapshot": {
                    "ticker_data": _json_safe(ticker_data),
                    "macro_signals": _json_safe(macro_signals),
                },
                "market_data": {
                    "price": ctx.current_price,
                    "gap": ctx.change_percent,
                    "change": ctx.change,
                    "rsi": ctx.rsi,
                    "sma_50": ctx.sma_50,
                    "sma_200": ctx.sma_200,
                    "name": ctx.name,
                    "sector": ctx.sector,
                    "market_cap_usd": market_cap_usd,
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
