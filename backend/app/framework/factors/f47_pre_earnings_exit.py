"""
F47 — Pre-Earnings Binary Exit
=================================
Trigger: Earnings within holding window.
Action:  Exit before binary event, no holding through.
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


class F47PreEarningsBinaryExit(BaseFactor):
    factor_id = "F47"
    name = "Pre-Earnings Binary Exit"
    description = (
        "When earnings are within the holding window, exit before "
        "the binary event. No holding through earnings."
    )
    layer = 10
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check if earnings are within the holding window.
        If so, flag for exit — no holding through binary events.
        """
        if not ctx.earnings_within_window:
            return self._pass(
                detail="No earnings within holding window."
            )

        return self._trigger(
            action=FactorAction.VETO,
            detail=(
                f"{ctx.ticker} has earnings within the holding window. "
                f"Framework rule: exit before binary event — "
                f"no holding through earnings. "
                f"Setup vetoed for new entry."
            ),
            metadata={
                "earnings_within_window": True,
                "has_earnings_today": ctx.has_earnings_today,
                "rule": "No holding through earnings",
            },
        )
