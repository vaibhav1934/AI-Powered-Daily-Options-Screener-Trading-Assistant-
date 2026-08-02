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
    if ctx.analyst_day_catalyst:
        catalyst_signals.append("ANALYST_DAY")
    if ctx.product_launch_catalyst:
        catalyst_signals.append("PRODUCT_LAUNCH")
    if ctx.fda_regulatory_catalyst:
        catalyst_signals.append("FDA_REGULATORY")
    if ctx.index_reconstitution_catalyst:
        catalyst_signals.append("INDEX_RECONSTITUTION")
    if ctx.sector_macro_catalyst:
        catalyst_signals.append("SECTOR_MACRO_EVENT")
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
    if ctx.mtf_trend_aligned:
        technical_score += 1.0
        technical_signals.append("MTF_DAILY_60M_ALIGNMENT")
    if isinstance(ctx.relative_volume, (int, float)) and ctx.relative_volume >= 1.2:
        technical_score += 0.8
        technical_signals.append("RELATIVE_VOLUME_CONFIRMED")
    if ctx.gap_present and ctx.gap_hold_valid:
        technical_score += 0.5
        technical_signals.append("KEY_LEVEL_GAP_HOLD")

    catalyst_score = min(4.0, 1.0 * len(catalyst_signals))

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

        iv_rank = option_contract.get("iv_rank_1y")
        if isinstance(iv_rank, (int, float)):
            if iv_rank <= 35.0:
                options_signals.append("IV_RANK_FAVORABLE")
                options_score += 0.6
            elif iv_rank >= 75.0:
                options_signals.append("IV_RANK_ELEVATED")
                options_score -= 0.3

        iv_crush = option_contract.get("iv_crush_risk")
        if isinstance(iv_crush, str) and iv_crush.upper() == "HIGH":
            options_signals.append("IV_CRUSH_RISK_HIGH")
            options_score -= 0.4

        skew = option_contract.get("skew_signal")
        if isinstance(skew, str):
            if skew == "PUT_HEDGE_HEAVY":
                options_signals.append("PUT_SKEW_HEDGE_WARNING")
                options_score -= 0.2
            elif skew == "CALL_SPEC_HEAVY":
                options_signals.append("CALL_SKEW_MOMENTUM")
                options_score += 0.2

    execution_score = 1.5 if not ctx.is_past_cutoff else 0.0
    raw_score = catalyst_score + min(4.0, technical_score) + min(2.5, options_score) + execution_score
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
        "return_on_equity": ctx.return_on_equity,
        "return_on_assets": ctx.return_on_assets,
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
            "target_valuation_band": None,
            "moat_signals": [],
            "secular_signals": [],
            "management_signals": [],
            "thesis_change_event_detected": False,
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

    moat_signals: list[str] = []
    moat_score = 0.0
    if ctx.gross_margin is not None and ctx.gross_margin >= 0.45:
        moat_signals.append("HIGH_GROSS_MARGIN_MOAT")
        moat_score += 1.0
    if ctx.operating_margin is not None and ctx.operating_margin >= 0.18:
        moat_signals.append("OPERATING_LEVERAGE_MOAT")
        moat_score += 1.0
    if ctx.return_on_equity is not None and ctx.return_on_equity >= 0.15:
        moat_signals.append("ROE_STRENGTH")
        moat_score += 1.0

    secular_signals: list[str] = []
    secular_score = 0.0
    if ctx.revenue_growth is not None and ctx.revenue_growth >= 0.1:
        secular_signals.append("STRUCTURAL_REVENUE_GROWTH")
        secular_score += 1.0
    if ctx.sector in {
        "Semiconductors",
        "Technology",
        "Healthcare",
        "Aerospace & Defense",
        "Industrials",
        "Energy",
    }:
        secular_signals.append("SECTOR_SEcular_TAILWIND")
        secular_score += 1.0

    management_signals: list[str] = []
    mgmt_score = 0.0
    if ctx.insider_ownership is not None and ctx.insider_ownership >= 0.03:
        management_signals.append("INSIDER_OWNERSHIP_ALIGNED")
        mgmt_score += 1.0
    if ctx.return_on_assets is not None and ctx.return_on_assets >= 0.05:
        management_signals.append("ROA_CAPITAL_DISCIPLINE")
        mgmt_score += 1.0
    if ctx.shares_outstanding_change is not None and ctx.shares_outstanding_change <= 0.0:
        management_signals.append("NO_DILUTIVE_SHARE_GROWTH")
        mgmt_score += 1.0

    thesis_components = business_quality + balance_sheet + management + moat_score + secular_score + mgmt_score
    thesis_strength_10 = (thesis_components / 14.0) * 10.0

    valuation_components = 0.0
    if ctx.trailing_pe is not None and ctx.forward_pe is not None:
        valuation_components += 1.0 if ctx.forward_pe <= ctx.trailing_pe else 0.4
    if ctx.peg_ratio is not None:
        valuation_components += 1.0 if ctx.peg_ratio <= 1.5 else (0.5 if ctx.peg_ratio <= 2.5 else 0.0)

    target_valuation_band = None
    if ctx.forward_pe is not None:
        low_band = max(1.0, ctx.forward_pe * 0.85)
        high_band = max(low_band, ctx.forward_pe * 1.05)
        target_valuation_band = f"{low_band:.1f}x-{high_band:.1f}x fwd PE"
    entry_timing_10 = (valuation_components / 2.0) * 10.0

    portfolio_fit_10 = 5.0
    if isinstance(ctx.portfolio_sector_exposure, (int, float)):
        if ctx.portfolio_sector_exposure < 0.15:
            portfolio_fit_10 += 2.0
        elif ctx.portfolio_sector_exposure < 0.25:
            portfolio_fit_10 += 1.0
        else:
            portfolio_fit_10 -= 0.5
    if ctx.portfolio_underweight_sector:
        portfolio_fit_10 += 1.5
    if ctx.sector:
        portfolio_fit_10 += 0.5
    portfolio_fit_10 = min(10.0, max(0.0, portfolio_fit_10))

    score = round((0.6 * thesis_strength_10) + (0.25 * entry_timing_10) + (0.15 * portfolio_fit_10), 1)

    thesis_change_event_detected = bool(
        (ctx.revenue_growth is not None and ctx.revenue_growth < 0)
        or (ctx.operating_margin is not None and ctx.operating_margin < 0)
        or (ctx.debt_to_equity is not None and ctx.debt_to_equity > 2.5)
        or (ctx.interest_coverage is not None and ctx.interest_coverage < 1.5)
    )

    return {
        "status": "SCORED",
        "score": min(10.0, max(0.0, score)),
        "thesis_strength_score": round(thesis_strength_10, 1),
        "entry_timing_score": round(entry_timing_10, 1),
        "portfolio_fit_score": round(portfolio_fit_10, 1),
        "target_valuation_band": target_valuation_band,
        "moat_signals": moat_signals,
        "secular_signals": secular_signals,
        "management_signals": management_signals,
        "thesis_change_event_detected": thesis_change_event_detected,
        "missing_inputs": [],
        "thesis_break_condition": "FUNDAMENTAL_THESIS_BREAK_ONLY",
    }
