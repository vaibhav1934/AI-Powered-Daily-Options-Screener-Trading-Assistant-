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
        # Macro
        kospi_change_percent=macro_context.get("kospi_change_percent", 0.0),
        ceasefire_headline=macro_context.get("ceasefire_headline", False),
        is_fomc_day=macro_context.get("is_fomc_day", False),
        fomc_time_past_1245=macro_context.get("fomc_time_past_1245", False),
        # Ecosystem
        ecosystem_partner_10pct_move=ticker_data.get("ecosystem_partner_10pct_move", False),
        # Sector
        sector=ticker_data.get("sector", ""),
        industry=ticker_data.get("industry", ""),
        name=ticker_data.get("name", ""),
        change=ticker_data.get("change", 0.0),
        volume_str=ticker_data.get("volume_str", ""),
        # Analyst
        analyst_rating_change=ticker_data.get("analyst_rating_change", False),
        analyst_firm_tier=ticker_data.get("analyst_firm_tier"),
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
