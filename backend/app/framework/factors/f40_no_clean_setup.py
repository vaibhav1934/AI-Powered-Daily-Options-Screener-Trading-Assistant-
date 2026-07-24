"""
F40 — No Clean Setup
=====================
Trigger: No factor combination produces a coherent thesis.
Action:  VETO — do not force a trade.
Layer:   9 (Conviction Scoring)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F40NoCleanSetup(BaseFactor):
    factor_id = "F40"
    name = "No Clean Setup"
    description = (
        "Veto — do not force a trade when no factor combination "
        "produces a coherent thesis."
    )
    layer = 9
    status = FactorStatus.LIVE

    # Minimum number of live factors that must trigger for a "clean" setup
    MIN_TRIGGERED_FACTORS = 3

    # Minimum conviction score threshold
    MIN_CONVICTION_THRESHOLD = 3.0

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check if there's a coherent thesis.
        A clean setup requires at least MIN_TRIGGERED_FACTORS live factors
        to have triggered AND a minimum conviction score.
        """
        # Count how many live (non-stubbed) factors have triggered
        live_triggered = [
            fr for fr in ctx.factor_results
            if fr.triggered and not fr.stubbed and fr.factor_id != self.factor_id
        ]
        live_count = len(live_triggered)

        # If too few factors fired, there's no coherent thesis
        if live_count < self.MIN_TRIGGERED_FACTORS and ctx.conviction_score < self.MIN_CONVICTION_THRESHOLD:
            return self._trigger(
                action=FactorAction.VETO,
                detail=(
                    f"No clean setup: only {live_count} live factors triggered "
                    f"(minimum {self.MIN_TRIGGERED_FACTORS}) and conviction "
                    f"score {ctx.conviction_score:.1f} is below {self.MIN_CONVICTION_THRESHOLD}. "
                    f"Do not force a trade."
                ),
                metadata={
                    "live_triggered_count": live_count,
                    "min_required": self.MIN_TRIGGERED_FACTORS,
                    "conviction_score": ctx.conviction_score,
                    "triggered_factor_ids": [fr.factor_id for fr in live_triggered],
                },
            )

        return self._pass(
            detail=(
                f"Clean setup present: {live_count} live factors triggered, "
                f"conviction score {ctx.conviction_score:.1f}."
            )
        )
