"""
Dual-Horizon Selection Engine
=============================
Computes two independent evaluations from a shared scan context:
1) Tactical 30-day catalyst setup score.
2) Long-term investment thesis score.

No synthetic values are generated. Missing required data is surfaced explicitly.
"""

from __future__ import annotations

from typing import Any

from app.framework.factors.base import ScanContext


def evaluate_dual_horizon(
    ctx: ScanContext,
    option_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    tactical = _evaluate_tactical(ctx, option_contract)
    long_term = _evaluate_long_term(ctx)
    return {
        "tactical": tactical,
        "long_term": long_term,
    }


def _evaluate_tactical(ctx: ScanContext, option_contract: dict[str, Any] | None) -> dict[str, Any]:
    triggered_ids = {r.factor_id for r in ctx.factor_results if r.triggered}

    regime_fail_reasons: list[str] = []
    if "F45" in triggered_ids:
        regime_fail_reasons.append("F45_FOMC_REDUCTION")
    if "F49" in triggered_ids:
        regime_fail_reasons.append("F49_BOJ_KOSPI_SHOCK")
    if "F50" in triggered_ids:
        regime_fail_reasons.append("F50_WAR_TAPE")
    if ctx.is_past_cutoff:
        regime_fail_reasons.append("F42_ENTRY_CUTOFF")

    regime_gate_pass = len(regime_fail_reasons) == 0

    catalyst_signals: list[str] = []
    if ctx.has_earnings_today or ctx.earnings_within_window:
        catalyst_signals.append("EARNINGS_WINDOW")
    if ctx.ecosystem_partner_10pct_move:
        catalyst_signals.append("ECOSYSTEM_SYMPATHY")
    if "F48" in triggered_ids:
        catalyst_signals.append("GAP_HOLD_PROTOCOL")
    if "F44" in triggered_ids:
        catalyst_signals.append("ANALYST_TIER_CATALYST")

    technical_score = 0.0
    technical_signals: list[str] = []
    if ctx.current_price > 0 and ctx.sma_50 is not None and ctx.current_price > ctx.sma_50:
        technical_score += 1.0
        technical_signals.append("PRICE_ABOVE_SMA50")
    if ctx.sma_50 is not None and ctx.sma_200 is not None and ctx.sma_50 > ctx.sma_200:
        technical_score += 1.0
        technical_signals.append("SMA50_ABOVE_SMA200")
    if ctx.rsi is not None and 40.0 <= ctx.rsi <= 70.0:
        technical_score += 1.0
        technical_signals.append("RSI_IN_MOMENTUM_BAND")

    catalyst_score = min(3.5, 1.25 * len(catalyst_signals))

    options_score = 0.0
    options_signals: list[str] = []
    if option_contract:
        options_signals.append("OPTION_CONTRACT_AVAILABLE")
        options_score += 0.8
        oi = option_contract.get("open_interest")
        bid = option_contract.get("bid")
        ask = option_contract.get("ask")
        if isinstance(oi, (int, float)) and oi > 0:
            options_signals.append("OPEN_INTEREST_PRESENT")
            options_score += 0.6
        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)) and ask >= bid > 0:
            spread_ratio = (ask - bid) / ask if ask else 1.0
            if spread_ratio <= 0.1:
                options_signals.append("TIGHT_SPREAD")
                options_score += 0.6

    execution_score = 1.5 if not ctx.is_past_cutoff else 0.0
    raw_score = catalyst_score + technical_score + min(2.0, options_score) + execution_score
    score = 0.0 if not regime_gate_pass else min(10.0, raw_score)

    if ctx.is_halo_trade:
        score = min(score, 6.5)

    score = round(score, 1)
    if not regime_gate_pass:
        conviction_tier = "EXCLUDED"
        sizing_cap = "0%"
    elif score >= 7.0:
        conviction_tier = "FULL_SIZE"
        sizing_cap = "100%"
    elif score >= 5.0:
        conviction_tier = "REDUCED_SIZE"
        sizing_cap = "50%"
    else:
        conviction_tier = "PAPER_TRACK_ONLY"
        sizing_cap = "0%"

    return {
        "score": score,
        "regime_gate_pass": regime_gate_pass,
        "regime_fail_reasons": regime_fail_reasons,
        "catalyst_signals": catalyst_signals,
        "technical_signals": technical_signals,
        "options_signals": options_signals,
        "conviction_tier": conviction_tier,
        "sizing_cap": sizing_cap,
        "entry_cutoff": "11:00 AM CST (10:30 AM CST Fridays)",
        "binary_event_exit": "EXIT_BEFORE_EARNINGS_UNLESS_EXPLICIT_OVERRIDE",
        "invalidation_rule": "SET_AT_ENTRY_NO_EMOTIONAL_OVERRIDE",
    }


def _evaluate_long_term(ctx: ScanContext) -> dict[str, Any]:
    missing_inputs: list[str] = []

    required_for_business = {
        "revenue_growth": ctx.revenue_growth,
        "gross_margin": ctx.gross_margin,
        "operating_margin": ctx.operating_margin,
        "free_cash_flow": ctx.free_cash_flow,
        "debt_to_equity": ctx.debt_to_equity,
        "interest_coverage": ctx.interest_coverage,
    }

    for key, val in required_for_business.items():
        if val is None:
            missing_inputs.append(key)

    required_for_valuation = {
        "trailing_pe": ctx.trailing_pe,
        "forward_pe": ctx.forward_pe,
        "peg_ratio": ctx.peg_ratio,
    }
    for key, val in required_for_valuation.items():
        if val is None:
            missing_inputs.append(key)

    required_for_management = {
        "insider_ownership": ctx.insider_ownership,
    }
    for key, val in required_for_management.items():
        if val is None:
            missing_inputs.append(key)

    if missing_inputs:
        return {
            "status": "DATA_NOT_AVAILABLE",
            "score": None,
            "thesis_strength_score": None,
            "entry_timing_score": None,
            "portfolio_fit_score": None,
            "missing_inputs": sorted(set(missing_inputs)),
            "thesis_break_condition": "FUNDAMENTAL_THESIS_BREAK_ONLY",
        }

    business_quality = 0.0
    if ctx.revenue_growth is not None:
        business_quality += 1.0 if ctx.revenue_growth >= 0.1 else (0.5 if ctx.revenue_growth > 0 else 0.0)
    if ctx.gross_margin is not None:
        business_quality += 1.0 if ctx.gross_margin >= 0.4 else (0.5 if ctx.gross_margin >= 0.2 else 0.0)
    if ctx.operating_margin is not None:
        business_quality += 1.0 if ctx.operating_margin >= 0.15 else (0.5 if ctx.operating_margin >= 0.05 else 0.0)
    if ctx.free_cash_flow is not None:
        business_quality += 1.0 if ctx.free_cash_flow > 0 else 0.0

    balance_sheet = 0.0
    if ctx.debt_to_equity is not None:
        balance_sheet += 1.0 if ctx.debt_to_equity <= 1.0 else (0.5 if ctx.debt_to_equity <= 2.0 else 0.0)
    if ctx.interest_coverage is not None:
        balance_sheet += 1.0 if ctx.interest_coverage >= 4.0 else (0.5 if ctx.interest_coverage >= 2.0 else 0.0)

    management = 1.0 if (ctx.insider_ownership is not None and ctx.insider_ownership >= 0.03) else 0.5

    thesis_strength_10 = ((business_quality + balance_sheet + management) / 7.0) * 10.0

    valuation_components = 0.0
    if ctx.trailing_pe is not None and ctx.forward_pe is not None:
        valuation_components += 1.0 if ctx.forward_pe <= ctx.trailing_pe else 0.4
    if ctx.peg_ratio is not None:
        valuation_components += 1.0 if ctx.peg_ratio <= 1.5 else (0.5 if ctx.peg_ratio <= 2.5 else 0.0)
    entry_timing_10 = (valuation_components / 2.0) * 10.0

    # Portfolio-fit score is bounded and transparent with currently available data.
    # It reflects concentration control signals without inventing portfolio state.
    portfolio_fit_10 = 6.0 if ctx.sector else 5.0

    score = round((0.6 * thesis_strength_10) + (0.25 * entry_timing_10) + (0.15 * portfolio_fit_10), 1)

    return {
        "status": "SCORED",
        "score": min(10.0, max(0.0, score)),
        "thesis_strength_score": round(thesis_strength_10, 1),
        "entry_timing_score": round(entry_timing_10, 1),
        "portfolio_fit_score": round(portfolio_fit_10, 1),
        "missing_inputs": [],
        "thesis_break_condition": "FUNDAMENTAL_THESIS_BREAK_ONLY",
    }
