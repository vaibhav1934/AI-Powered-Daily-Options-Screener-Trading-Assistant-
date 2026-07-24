"""
Conviction Scoring & Risk Bucketing
=====================================
Pure, deterministic scoring logic.
FR-10: Auto-bucket into Low / Moderate / High-Risk-Halo.
FR-11: Halo trades hard-capped at max 6.5/10 conviction.
"""

from __future__ import annotations

from app.db.models import RiskBucket
from app.framework.factors.base import FactorAction, FactorResult, ScanContext


# ---------------------------------------------------------------------------
# Conviction Score Calculation
# ---------------------------------------------------------------------------
def calculate_conviction_score(ctx: ScanContext) -> float:
    """
    Calculate the conviction score (0–10) based on triggered factors.
    Pure, deterministic — no LLM involvement.

    Scoring approach:
    - Start with a base score
    - Add points for each triggered non-veto, non-stub factor
    - Apply analyst tier weighting
    - Apply bear case downgrade
    - Cap halo trades at 6.5/10
    """
    base_score = 5.0  # Neutral starting point
    score = base_score

    for result in ctx.factor_results:
        if result.stubbed:
            continue  # Skip unconfigured factors

        if not result.triggered:
            continue

        # Positive signals add to conviction
        if result.action == FactorAction.FLAG:
            score += 0.5

        # Downgrades reduce conviction
        elif result.action == FactorAction.DOWNGRADE:
            downgrade = result.metadata.get("downgrade_amount", 1.0)
            score -= downgrade

        # Analyst tier weighting adjusts conviction
        if result.factor_id == "F44" and result.triggered:
            weight = result.metadata.get("conviction_weight", 1.0)
            score += (weight - 1.0) * 0.5  # Adjust relative to baseline

    # Clamp to 0–10
    score = max(0.0, min(10.0, score))

    # FR-11: Halo trades hard-capped at 6.5/10
    if ctx.is_halo_trade:
        score = min(score, 6.5)

    return round(score, 1)


# ---------------------------------------------------------------------------
# Risk Bucket Assignment
# ---------------------------------------------------------------------------
def assign_risk_bucket(
    score: float,
    ctx: ScanContext,
) -> RiskBucket:
    """
    FR-10: Auto-bucket confirmed setups into Low / Moderate / High-Risk-Halo.

    Based on:
    - Conviction score
    - Presence of a defined catalyst
    - Distance to binary events
    - Halo trade status
    """
    # Halo trades are always HIGH_RISK_HALO regardless of score
    if ctx.is_halo_trade:
        return RiskBucket.HIGH_RISK_HALO

    # Check for binary event proximity (elevated risk)
    has_binary_risk = ctx.earnings_within_window or ctx.has_earnings_today

    # Check for catalyst presence
    has_catalyst = ctx.is_after_hours_beat or ctx.ecosystem_partner_10pct_move

    # Scoring thresholds
    if score >= 7.0 and has_catalyst and not has_binary_risk:
        return RiskBucket.LOW
    elif score >= 5.0 and not has_binary_risk:
        return RiskBucket.MODERATE
    else:
        return RiskBucket.HIGH_RISK_HALO


# ---------------------------------------------------------------------------
# List Assignment
# ---------------------------------------------------------------------------
def assign_list_type(ctx: ScanContext) -> str:
    """
    Assign to List 1 (daily) or List 2 (monthly accumulation).

    List 1: High-conviction daily setups with clear catalyst.
    List 2: Longer-term accumulation candidates.
    """
    has_catalyst = ctx.is_after_hours_beat or ctx.ecosystem_partner_10pct_move

    if has_catalyst and ctx.conviction_score >= 6.0:
        return "LIST_1"
    else:
        return "LIST_2"
