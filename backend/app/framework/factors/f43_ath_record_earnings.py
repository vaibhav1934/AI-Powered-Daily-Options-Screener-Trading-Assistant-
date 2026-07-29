"""
F43 — ATH + Record Earnings
=============================
Trigger: Stock at all-time high with beat-and-raise earnings.
Action:  Block put recommendations.
Layer:   5 (Binary Event Filter)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F43ATHRecordEarnings(BaseFactor):
    factor_id = "F43"
    name = "ATH + Record Earnings"
    description = (
        "When a stock is at an all-time high with beat-and-raise earnings, "
        "block put recommendations."
    )
    layer = 9
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check for ATH + beat-and-raise earnings scenario.
        If both conditions are met, block puts.
        """
        is_earnings_beat = (
            ctx.eps_actual is not None
            and ctx.eps_estimate is not None
            and ctx.eps_actual > ctx.eps_estimate
        )

        is_revenue_beat = (
            ctx.revenue_actual is not None
            and ctx.revenue_estimate is not None
            and ctx.revenue_actual > ctx.revenue_estimate
        )

        is_beat_and_raise = is_earnings_beat and is_revenue_beat

        if ctx.is_at_ath and is_beat_and_raise:
            eps_beat_pct = 0.0
            if ctx.eps_estimate and ctx.eps_estimate != 0:
                eps_beat_pct = ((ctx.eps_actual - ctx.eps_estimate) / abs(ctx.eps_estimate)) * 100  # type: ignore[operator]

            return self._trigger(
                action=FactorAction.BLOCK_PUTS,
                detail=(
                    f"{ctx.ticker} at all-time high with beat-and-raise earnings "
                    f"(EPS beat by {eps_beat_pct:.1f}%). "
                    f"Put recommendations blocked."
                ),
                metadata={
                    "is_at_ath": True,
                    "eps_actual": ctx.eps_actual,
                    "eps_estimate": ctx.eps_estimate,
                    "eps_beat_pct": eps_beat_pct,
                    "revenue_actual": ctx.revenue_actual,
                    "revenue_estimate": ctx.revenue_estimate,
                },
            )

        return self._pass(
            detail=(
                f"ATH check: is_ath={ctx.is_at_ath}, "
                f"earnings_beat={is_earnings_beat}, "
                f"revenue_beat={is_revenue_beat}. "
                f"No put block applied."
            )
        )
