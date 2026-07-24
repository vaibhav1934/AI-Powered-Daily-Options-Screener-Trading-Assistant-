"""
F46 — EDGAR Shelf Check
=========================
Trigger: Ticker near ATH proximity.
Action:  Mandatory SEC EDGAR shelf/dilution filing check before entry.
Layer:   6 (Regulatory/Filing Check)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F46EDGARShelfCheck(BaseFactor):
    factor_id = "F46"
    name = "EDGAR Shelf Check"
    description = (
        "When a ticker is near ATH proximity, mandatory SEC EDGAR "
        "shelf/dilution filing check before entry."
    )
    layer = 6
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check if ticker is near ATH and if there's a recent shelf filing.
        Near-ATH + recent shelf = potential dilution risk → flag/veto.
        """
        if not ctx.near_ath_proximity:
            return self._pass(
                detail="Ticker not near ATH — EDGAR shelf check not required."
            )

        # Near ATH — shelf check is mandatory
        if ctx.has_recent_shelf_filing:
            return self._trigger(
                action=FactorAction.VETO,
                detail=(
                    f"{ctx.ticker} is near ATH with a recent SEC shelf/dilution "
                    f"filing detected. Potential dilution risk — entry blocked. "
                    f"Verify the filing details before proceeding."
                ),
                metadata={
                    "near_ath": True,
                    "has_shelf_filing": True,
                    "risk": "dilution",
                },
            )

        # Near ATH but no shelf filing — flag for awareness
        return self._trigger(
            action=FactorAction.FLAG,
            detail=(
                f"{ctx.ticker} is near ATH — EDGAR shelf check performed, "
                f"no recent shelf/dilution filing found. Proceed with caution."
            ),
            metadata={
                "near_ath": True,
                "has_shelf_filing": False,
                "risk": "low",
            },
        )
