
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Any
from datetime import date
from pydantic import BaseModel
import uuid
import logging
from dataclasses import fields as dc_fields

from app.db.session import get_db, async_session_factory
from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.technicals import fetch_technicals
from app.framework.engine import run_full_scan, LAYER_PIPELINE, run_scan_for_ticker
from app.core.time_gate import get_cst_now, is_fomc_day, is_friday, is_past_cutoff
from app.framework.factors.base import ScanContext, FactorAction
from app.framework.factors.registry import factor_registry
from app.framework.scoring import calculate_conviction_score, assign_risk_bucket, assign_list_type
from app.services.stockglass_service import LAYER_DEFINITIONS

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

# ---------------------------------------------------------------------------
# Simulation Endpoints (Custom User Input Testing for F1-F50 & 10 Layers)
# ---------------------------------------------------------------------------

class SimulateContextSchema(BaseModel):
    ticker: str = "TEST"
    scan_date: str = str(date.today())
    current_price: float = 100.0
    open_price: float = 98.0
    high_price: float = 102.0
    low_price: float = 97.0
    previous_close: float = 98.0
    volume: int = 15000000
    change_percent: float = 2.04
    has_earnings_today: bool = False
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    is_after_hours_beat: bool = False
    earnings_within_window: bool = False
    rsi: Optional[float] = 55.0
    sma_50: Optional[float] = 95.0
    sma_200: Optional[float] = 90.0
    is_at_ath: bool = False
    gap_present: bool = False
    gap_hold_valid: bool = False
    kospi_change_percent: float = 0.5
    ceasefire_headline: bool = False
    is_fomc_day: bool = False
    fomc_time_past_1245: bool = False
    ecosystem_partner_10pct_move: bool = False
    sector: str = "Technology"
    industry: str = "Semiconductors"
    name: str = "Test Corp"
    change: float = 2.0
    volume_str: str = "15.0M"
    analyst_rating_change: bool = False
    analyst_firm_tier: Optional[int] = None
    has_recent_shelf_filing: bool = False
    near_ath_proximity: bool = False
    shelf_filing_date: Optional[str] = None
    shelf_form_type: Optional[str] = None
    edgar_check_status: Optional[str] = None
    current_time_cst: str = "10:30 AM"
    is_past_cutoff: bool = False
    is_friday: bool = False
    is_halo_trade: bool = False
    model_config = {"extra": "allow"}

class SimulateFactorRequest(BaseModel):
    factor_id: str = "F50"
    ctx: SimulateContextSchema = SimulateContextSchema()

class SimulateLayerRequest(BaseModel):
    layer_number: int = 10
    ctx: SimulateContextSchema = SimulateContextSchema()

class SimulateEngineRequest(BaseModel):
    ctx: SimulateContextSchema = SimulateContextSchema()

def to_scan_context(ctx_model: SimulateContextSchema) -> ScanContext:
    data = ctx_model.model_dump()
    valid_keys = {f.name for f in dc_fields(ScanContext)}
    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
    return ScanContext(**filtered_data)

@router.post("/simulate-factor")
async def debug_simulate_factor(req: SimulateFactorRequest):
    """
    Simulate and test any single factor (F01 - F50) against custom user input.
    Recommended for testing specific rule conditions, thresholds, and veto logic.
    """
    fid = req.factor_id.upper()
    if not fid.startswith("F") and fid.isdigit():
        fid = f"F{int(fid):02d}"
    factor = factor_registry.get(fid)
    if not factor:
        raise HTTPException(
            status_code=404,
            detail=f"Factor {req.factor_id} not found in registry. Valid IDs: F01-F50."
        )
    ctx = to_scan_context(req.ctx)
    result = factor.evaluate(ctx)
    return {
        "factor_id": result.factor_id,
        "name": result.factor_name,
        "layer": factor.layer,
        "status": result.status.value if hasattr(result.status, "value") else str(result.status),
        "triggered": result.triggered,
        "vetoed": result.vetoed,
        "action": result.action.value if hasattr(result.action, "value") else str(result.action),
        "detail": result.detail,
        "metadata": result.metadata,
        "stubbed": result.stubbed
    }

@router.post("/simulate-layer")
async def debug_simulate_layer(req: SimulateLayerRequest):
    """
    Simulate and test any single layer (1 - 10) against custom user input.
    Runs all 5 factors assigned to the specified layer and computes the 0-10 layer score.
    Recommended for testing layer-level aggregation and veto propagation.
    """
    if req.layer_number < 1 or req.layer_number > 10:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid layer_number {req.layer_number}. Must be between 1 and 10."
        )
    layer_obj = LAYER_PIPELINE[req.layer_number - 1]
    ctx = to_scan_context(req.ctx)
    
    ctx = layer_obj.process(ctx)
    
    layer_flogs = ctx.factor_results
    val = 0.0
    if any(f.vetoed for f in layer_flogs):
        val = 0.0
    elif layer_flogs:
        triggered = sum(1 for f in layer_flogs if f.triggered)
        if triggered > 0:
            val = round((triggered / len(layer_flogs)) * 10.0, 1)
        else:
            val = round(calculate_conviction_score(ctx), 1)
            
    factor_breakdown = [
        {
            "factor_id": r.factor_id,
            "name": r.factor_name,
            "status": r.status.value if hasattr(r.status, "value") else str(r.status),
            "triggered": r.triggered,
            "vetoed": r.vetoed,
            "action": r.action.value if hasattr(r.action, "value") else str(r.action),
            "detail": r.detail
        }
        for r in layer_flogs
    ]
    
    return {
        "layer_number": req.layer_number,
        "layer_name": layer_obj.name,
        "layer_score": val,
        "is_vetoed": ctx.is_vetoed,
        "veto_rule": ctx.veto_rule,
        "veto_reason": ctx.veto_reason,
        "factors_evaluated": len(layer_flogs),
        "factors_triggered": len([f for f in layer_flogs if f.triggered]),
        "factor_breakdown": factor_breakdown
    }

@router.post("/simulate-engine")
async def debug_simulate_engine(req: SimulateEngineRequest):
    """
    Simulate the entire 50-factor / 10-layer scanning engine on custom user input.
    Recommended for end-to-end testing of conviction score calculation, risk bucketing, list assignment, and full layer scores.
    """
    ctx = to_scan_context(req.ctx)
    
    ctx = run_scan_for_ticker(ctx)
    
    layer_scores = []
    for lnum, lname, fstart, fend, _ in LAYER_DEFINITIONS:
        val = 0.0
        layer_flogs = [r for r in ctx.factor_results if int(r.factor_id.replace("F", "")) in range(fstart, fend + 1)]
        if any(f.vetoed for f in layer_flogs):
            val = 0.0
        elif layer_flogs:
            triggered = sum(1 for f in layer_flogs if f.triggered)
            if triggered > 0:
                val = round((triggered / len(layer_flogs)) * 10.0, 1)
            else:
                val = round(ctx.conviction_score, 1)
        else:
            val = round(ctx.conviction_score, 1)
        layer_scores.append({"layer": lnum, "name": lname, "score": val})
        
    risk_bucket = assign_risk_bucket(ctx.conviction_score, ctx)
    list_type = assign_list_type(ctx)
    
    return {
        "ticker": ctx.ticker,
        "scan_date": ctx.scan_date,
        "conviction_score": ctx.conviction_score,
        "risk_bucket": risk_bucket.value if hasattr(risk_bucket, "value") else str(risk_bucket),
        "list_type": list_type,
        "is_vetoed": ctx.is_vetoed,
        "veto_rule": ctx.veto_rule,
        "veto_reason": ctx.veto_reason,
        "layer_scores": layer_scores,
        "factors_triggered": ctx.triggered_factors,
        "total_factors_evaluated": len(ctx.factor_results),
        "detailed_results": [
            {
                "factor_id": r.factor_id,
                "name": r.factor_name,
                "triggered": r.triggered,
                "vetoed": r.vetoed,
                "action": r.action.value if hasattr(r.action, "value") else str(r.action),
                "detail": r.detail
            }
            for r in ctx.factor_results if r.triggered or r.vetoed
        ]
    }
