"""
F48 — Gap-Hold Protocol
=========================
Trigger: Overnight gap present.
Action:  Validate gap-hold structure before entry.
Layer:   4 (Structural Gap Check)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F48GapHoldProtocol(BaseFactor):
    factor_id = "F48"
    name = "Gap-Hold Protocol"
    description = (
        "When an overnight gap is present, validate gap-hold structure "
        "before entry. Gap must hold for setup to remain valid."
    )
    layer = 10
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check for overnight gap and validate gap-hold structure.
        - No gap → pass
        - Gap present + holds → flag (positive signal)
        - Gap present + fails to hold → veto
        """
        if not ctx.gap_present:
            return self._pass(detail="No overnight gap detected.")

        if ctx.gap_hold_valid:
            # Gap is present and holding — positive signal
            gap_pct = 0.0
            if ctx.previous_close > 0:
                gap_pct = ((ctx.open_price - ctx.previous_close) / ctx.previous_close) * 100

            return self._trigger(
                action=FactorAction.FLAG,
                detail=(
                    f"{ctx.ticker} has an overnight gap ({gap_pct:+.1f}%) "
                    f"that is holding. Gap-hold structure validated — "
                    f"setup remains valid."
                ),
                metadata={
                    "gap_present": True,
                    "gap_hold_valid": True,
                    "gap_percent": gap_pct,
                    "open_price": ctx.open_price,
                    "previous_close": ctx.previous_close,
                },
            )

        # Gap present but not holding — Day-2 gap skip rule
        return self._trigger(
            action=FactorAction.VETO,
            detail=(
                f"{ctx.ticker} has an overnight gap that is NOT holding. "
                f"Gap-hold structure invalid — Day-2 gap skip rule applied. "
                f"Entry vetoed."
            ),
            metadata={
                "gap_present": True,
                "gap_hold_valid": False,
                "rule": "Day-2 gap skip",
            },
        )
