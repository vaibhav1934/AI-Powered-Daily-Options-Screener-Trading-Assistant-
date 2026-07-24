"""
F45 — FOMC 50% Reduction
==========================
Trigger: FOMC day.
Action:  Reduce position sizing 50% by 12:45 PM CST.
Layer:   7 (Time-of-Day Gate)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F45FOMCReduction(BaseFactor):
    factor_id = "F45"
    name = "FOMC 50% Reduction"
    description = (
        "On FOMC days, reduce position sizing by 50% and hard-lock "
        "new entries at 12:45 PM CST."
    )
    layer = 7
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check if today is an FOMC day and apply appropriate restrictions.
        - FOMC day: reduce sizing 50%
        - Past 12:45 PM CST on FOMC day: hard lock
        """
        if not ctx.is_fomc_day:
            return self._pass(detail="Not an FOMC day.")

        # FOMC day — at minimum, reduce sizing
        if ctx.fomc_time_past_1245:
            return self._trigger(
                action=FactorAction.LOCK,
                detail=(
                    f"FOMC day hard lock: past 12:45 PM CST. "
                    f"Current time: {ctx.current_time_cst}. "
                    f"All new entries locked. Review open positions."
                ),
                metadata={
                    "is_fomc_day": True,
                    "past_1245": True,
                    "current_time": ctx.current_time_cst,
                    "action": "HARD_LOCK",
                },
            )

        return self._trigger(
            action=FactorAction.REDUCE_SIZE,
            detail=(
                f"FOMC day: position sizing reduced by 50%. "
                f"Hard lock at 12:45 PM CST. "
                f"Current time: {ctx.current_time_cst}."
            ),
            metadata={
                "is_fomc_day": True,
                "past_1245": False,
                "size_reduction": 0.5,
                "current_time": ctx.current_time_cst,
            },
        )
