"""
F42 — 11:00 AM Entry Cutoff
=============================
Trigger: Time ≥ 11:00 AM CST (10:30 AM Fri)
Action:  Lock new entries.
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


class F42EntryCutoff(BaseFactor):
    factor_id = "F42"
    name = "11:00 AM Entry Cutoff"
    description = (
        "Lock new entries at 11:00 AM CST (10:30 AM on Fridays). "
        "Server-authoritative time check — never client-side."
    )
    layer = 7
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check if the entry cutoff has been reached.
        Uses server-authoritative CST time from the scan context.
        """
        if ctx.is_past_cutoff:
            cutoff_label = "10:30 AM" if ctx.is_friday else "11:00 AM"
            return self._trigger(
                action=FactorAction.LOCK,
                detail=(
                    f"Entry cutoff reached: {cutoff_label} CST "
                    f"({'Friday' if ctx.is_friday else 'standard'}). "
                    f"Current time: {ctx.current_time_cst}. "
                    f"New entries are locked."
                ),
                metadata={
                    "cutoff_time": cutoff_label,
                    "current_time": ctx.current_time_cst,
                    "is_friday": ctx.is_friday,
                    "rule": "F42",
                },
            )

        return self._pass(
            detail=f"Before entry cutoff. Current time: {ctx.current_time_cst}."
        )
