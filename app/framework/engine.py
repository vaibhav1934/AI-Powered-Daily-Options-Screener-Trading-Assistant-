"""
Scan Engine — Main Orchestrator
=================================
Runs the full 10-layer scanning pipeline deterministically.
No LLM or AI agent involvement in scanning/scoring.

Pipeline: L1 → L2 → ... → L10, sequential.
Each layer evaluates its factors against the ScanContext.
All results persisted for audit/explainability.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from app.framework.factors.base import ScanContext
from app.framework.factors.registry import factor_registry
from app.framework.layers.layer_01_price_action import Layer01PriceAction
from app.framework.layers.layer_02_volume_flow import Layer02VolumeFlow
from app.framework.layers.layer_03_volatility import Layer03Volatility
from app.framework.layers.layer_04_earnings import Layer04Earnings
from app.framework.layers.layer_05_analyst import Layer05Analyst
from app.framework.layers.layer_06_macro_rates import Layer06MacroRates
from app.framework.layers.layer_07_sector_rotation import Layer07SectorRotation
from app.framework.layers.layer_08_news_catalyst import Layer08NewsCatalyst
from app.framework.layers.layer_09_risk_rules import Layer09RiskRules
from app.framework.layers.layer_10_position_fit import Layer10PositionFit
from app.framework.scoring import assign_list_type, assign_risk_bucket, calculate_conviction_score

logger = logging.getLogger(__name__)


# Ordered layer pipeline
LAYER_PIPELINE = [
    Layer01PriceAction(),
    Layer02VolumeFlow(),
    Layer03Volatility(),
    Layer04Earnings(),
    Layer05Analyst(),
    Layer06MacroRates(),
    Layer07SectorRotation(),
    Layer08NewsCatalyst(),
    Layer09RiskRules(),
    Layer10PositionFit(),
]


def run_scan_for_ticker(ctx: ScanContext) -> ScanContext:
    """
    Run the full 10-layer scanning pipeline for a single ticker.
    Pure, deterministic — no LLM calls, no network calls.
    All data must be pre-loaded into the ScanContext before calling this.

    Returns the updated ScanContext with all factor results,
    conviction score, risk bucket, and list assignment.
    """
    logger.info("Scanning ticker: %s (date: %s)", ctx.ticker, ctx.scan_date)

    # Run each layer sequentially
    for layer in LAYER_PIPELINE:
        logger.debug(
            "  Layer %d (%s): processing %s",
            layer.layer_number,
            layer.name,
            ctx.ticker,
        )
        # Calculate score BEFORE Layer 8 (News/Catalyst) so F40 No Clean Setup can use it
        if layer.layer_number == 8:
            ctx.conviction_score = calculate_conviction_score(ctx)
            
        ctx = layer.process(ctx)

    # Recalculate conviction score after all layers to include any final downgrades
    ctx.conviction_score = calculate_conviction_score(ctx)

    # Assign risk bucket
    risk_bucket = assign_risk_bucket(ctx.conviction_score, ctx)

    # Assign list type
    list_type = assign_list_type(ctx)

    # Log summary
    live_results = [r for r in ctx.factor_results if not r.stubbed]
    stubbed_results = [r for r in ctx.factor_results if r.stubbed]
    triggered = [r for r in live_results if r.triggered]

    logger.info(
        "Scan complete: %s — score=%.1f, bucket=%s, list=%s, "
        "vetoed=%s, triggered=%d/%d live factors, %d stubbed",
        ctx.ticker,
        ctx.conviction_score,
        risk_bucket.value,
        list_type,
        ctx.is_vetoed,
        len(triggered),
        len(live_results),
        len(stubbed_results),
    )

    return ctx


def run_full_scan(
    tickers: list[dict[str, Any]],
    macro_context: dict[str, Any],
    scan_date: date | None = None,
) -> list[ScanContext]:
    """
    Run the full-universe scan across all tickers.

    Args:
        tickers: List of ticker data dicts with pre-loaded market data.
        macro_context: Macro/tape overlay data (KOSPI, ceasefire headlines, etc.).
        scan_date: The scan date (defaults to today).

    Returns:
        List of fully-evaluated ScanContext objects, ranked by conviction score.
    """
    scan_date = scan_date or date.today()
    logger.info(
        "Starting full-universe scan: %d tickers, date=%s",
        len(tickers),
        scan_date.isoformat(),
    )

    # Log factor coverage
    coverage = factor_registry.coverage_report()
    logger.info(
        "Factor coverage: %d total (%d live, %d stubbed)",
        coverage["total"],
        coverage["live_count"],
        coverage["stubbed_count"],
    )

    results: list[ScanContext] = []

    for ticker_data in tickers:
        # Build scan context from ticker data + macro context
        ctx = _build_scan_context(ticker_data, macro_context, scan_date)

        # Run the pipeline
        ctx = run_scan_for_ticker(ctx)
        results.append(ctx)

    # Sort by conviction score (descending), vetoed items last
    results.sort(
        key=lambda c: (not c.is_vetoed, c.conviction_score),
        reverse=True,
    )

    logger.info(
        "Full scan complete: %d tickers processed, %d vetoed, %d actionable",
        len(results),
        sum(1 for r in results if r.is_vetoed),
        sum(1 for r in results if not r.is_vetoed),
    )

    return results


def _build_scan_context(
    ticker_data: dict[str, Any],
    macro_context: dict[str, Any],
    scan_date: date,
) -> ScanContext:
    """Build a ScanContext from raw ticker data and macro context."""
    return ScanContext(
        ticker=ticker_data.get("ticker", ""),
        scan_date=scan_date.isoformat(),
        # Quote data
        current_price=ticker_data.get("current_price", 0.0),
        open_price=ticker_data.get("open_price", 0.0),
        high_price=ticker_data.get("high_price", 0.0),
        low_price=ticker_data.get("low_price", 0.0),
        previous_close=ticker_data.get("previous_close", 0.0),
        volume=ticker_data.get("volume", 0),
        change_percent=ticker_data.get("change_percent", 0.0),
        # Earnings
        has_earnings_today=ticker_data.get("has_earnings_today", False),
        eps_estimate=ticker_data.get("eps_estimate"),
        eps_actual=ticker_data.get("eps_actual"),
        revenue_estimate=ticker_data.get("revenue_estimate"),
        revenue_actual=ticker_data.get("revenue_actual"),
        is_after_hours_beat=ticker_data.get("is_after_hours_beat", False),
        earnings_within_window=ticker_data.get("earnings_within_window", False),
        # Technicals
        rsi=ticker_data.get("rsi"),
        sma_50=ticker_data.get("sma_50"),
        sma_200=ticker_data.get("sma_200"),
        is_at_ath=ticker_data.get("is_at_ath", False),
        gap_present=ticker_data.get("gap_present", False),
        gap_hold_valid=ticker_data.get("gap_hold_valid", False),
        mtf_trend_aligned=ticker_data.get("mtf_trend_aligned", False),
        relative_volume=ticker_data.get("relative_volume"),
        volume_profile_state=ticker_data.get("volume_profile_state"),
        volume_profile_hvn=ticker_data.get("volume_profile_hvn"),
        volume_profile_lvn=ticker_data.get("volume_profile_lvn"),
        # Macro
        kospi_change_percent=macro_context.get("kospi_change_percent", 0.0),
        ceasefire_headline=macro_context.get("ceasefire_headline", False),
        is_fomc_day=macro_context.get("is_fomc_day", False),
        fomc_time_past_1245=macro_context.get("fomc_time_past_1245", False),
        dxy_change_5d=macro_context.get("dxy_change_5d"),
        ust2y_yield=macro_context.get("ust2y_yield"),
        ust10y_yield=macro_context.get("ust10y_yield"),
        curve_10y_2y_bps=macro_context.get("curve_10y_2y_bps"),
        curve_change_5d_bps=macro_context.get("curve_change_5d_bps"),
        hyg_lqd_ratio_change_5d=macro_context.get("hyg_lqd_ratio_change_5d"),
        gld_change_5d=macro_context.get("gld_change_5d"),
        dax_change_percent=macro_context.get("dax_change_percent"),
        ftse_change_percent=macro_context.get("ftse_change_percent"),
        vix_spot=macro_context.get("vix_spot"),
        vix9d=macro_context.get("vix9d"),
        vix3m=macro_context.get("vix3m"),
        vix_term_slope=macro_context.get("vix_term_slope"),
        overnight_futures_gap_pct=macro_context.get("overnight_futures_gap_pct"),
        overnight_outside_prior_range=macro_context.get("overnight_outside_prior_range"),
        fed_policy_prob_proxy=macro_context.get("fed_policy_prob_proxy"),
        central_bank_surprise_proxy=macro_context.get("central_bank_surprise_proxy", False),
        central_bank_surprise_score=macro_context.get("central_bank_surprise_score"),
        # Ecosystem
        ecosystem_partner_10pct_move=ticker_data.get("ecosystem_partner_10pct_move", False),
        analyst_day_catalyst=ticker_data.get("analyst_day_catalyst", False),
        product_launch_catalyst=ticker_data.get("product_launch_catalyst", False),
        fda_regulatory_catalyst=ticker_data.get("fda_regulatory_catalyst", False),
        index_reconstitution_catalyst=ticker_data.get("index_reconstitution_catalyst", False),
        sector_macro_catalyst=ticker_data.get("sector_macro_catalyst", False),
        # Sector
        sector=ticker_data.get("sector", ""),
        industry=ticker_data.get("industry", ""),
        name=ticker_data.get("name", ""),
        change=ticker_data.get("change", 0.0),
        volume_str=ticker_data.get("volume_str", ""),
        sector_etf_symbol=ticker_data.get("sector_etf_symbol"),
        sector_rs_5d=ticker_data.get("sector_rs_5d"),
        sector_rs_20d=ticker_data.get("sector_rs_20d"),
        ticker_sector_corr_20d=ticker_data.get("ticker_sector_corr_20d"),
        idiosyncratic_alpha_20d=ticker_data.get("idiosyncratic_alpha_20d"),
        sector_flow_score=ticker_data.get("sector_flow_score"),
        # Analyst
        analyst_rating_change=ticker_data.get("analyst_rating_change", False),
        analyst_firm_tier=ticker_data.get("analyst_firm_tier"),
        iv_rank_1y=ticker_data.get("iv_rank_1y"),
        iv_crush_risk=ticker_data.get("iv_crush_risk"),
        put_call_oi_ratio=ticker_data.get("put_call_oi_ratio"),
        skew_signal=ticker_data.get("skew_signal"),
        option_open_interest=ticker_data.get("option_open_interest"),
        option_volume=ticker_data.get("option_volume"),
        option_bid=ticker_data.get("option_bid"),
        option_ask=ticker_data.get("option_ask"),
        option_mid_price=ticker_data.get("option_mid_price"),
        option_delta=ticker_data.get("option_delta"),
        option_theta_daily=ticker_data.get("option_theta_daily"),
        option_dte=ticker_data.get("option_dte"),
        option_volume_oi_ratio=ticker_data.get("option_volume_oi_ratio"),
        dealer_gamma_regime_proxy=ticker_data.get("dealer_gamma_regime_proxy"),
        # Fundamentals
        revenue_growth=ticker_data.get("revenue_growth"),
        gross_margin=ticker_data.get("gross_margin"),
        operating_margin=ticker_data.get("operating_margin"),
        free_cash_flow=ticker_data.get("free_cash_flow"),
        debt_to_equity=ticker_data.get("debt_to_equity"),
        interest_coverage=ticker_data.get("interest_coverage"),
        insider_ownership=ticker_data.get("insider_ownership"),
        institutional_ownership=ticker_data.get("institutional_ownership"),
        return_on_equity=ticker_data.get("return_on_equity"),
        return_on_assets=ticker_data.get("return_on_assets"),
        shares_outstanding_change=ticker_data.get("shares_outstanding_change"),
        short_ratio=ticker_data.get("short_ratio"),
        short_percent_float=ticker_data.get("short_percent_float"),
        whisper_eps_gap_proxy=ticker_data.get("whisper_eps_gap_proxy"),
        guidance_revision_trend_4q=ticker_data.get("guidance_revision_trend_4q"),
        retail_sentiment_score=ticker_data.get("retail_sentiment_score"),
        trailing_pe=ticker_data.get("trailing_pe"),
        forward_pe=ticker_data.get("forward_pe"),
        peg_ratio=ticker_data.get("peg_ratio"),
        portfolio_sector_exposure=ticker_data.get("portfolio_sector_exposure"),
        portfolio_underweight_sector=ticker_data.get("portfolio_underweight_sector"),
        # SEC
        has_recent_shelf_filing=ticker_data.get("has_recent_shelf_filing", False),
        near_ath_proximity=ticker_data.get("near_ath_proximity", False),
        shelf_filing_date=ticker_data.get("shelf_filing_date"),
        shelf_form_type=ticker_data.get("shelf_form_type"),
        edgar_check_status=ticker_data.get("edgar_check_status"),
        # Time
        current_time_cst=macro_context.get("current_time_cst", ""),
        is_past_cutoff=macro_context.get("is_past_cutoff", False),
        is_friday=macro_context.get("is_friday", False),
        # Halo
        is_halo_trade=ticker_data.get("is_halo_trade", False),
    )
