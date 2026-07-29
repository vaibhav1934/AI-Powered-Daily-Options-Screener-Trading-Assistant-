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
    layer = 10
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check if ticker is near ATH and if there's a recent shelf filing.
        Near-ATH + recent shelf = potential dilution risk → flag/veto.
        """
        if ctx.edgar_check_status == "UNAVAILABLE":
            return FactorResult(
                factor_id=self.factor_id,
                factor_name=self.name,
                layer_number=self.layer,
                status=FactorStatus.UNCONFIGURED,
                triggered=False,
                action=FactorAction.PASS,
                vetoed=False,
                stubbed=True,
                detail="SEC EDGAR shelf check UNAVAILABLE: API unreachable or rate limited. No fallback data provided.",
                metadata={"status": "UNAVAILABLE"},
            )

        if not ctx.near_ath_proximity:
            return self._pass(
                detail="Ticker not near ATH — EDGAR shelf check not required."
            )

        # Near ATH — shelf check is mandatory
        if ctx.has_recent_shelf_filing:
            form_str = ctx.shelf_form_type or "S-3/424B5"
            date_str = f" on {ctx.shelf_filing_date}" if ctx.shelf_filing_date else ""
            return self._trigger(
                action=FactorAction.VETO,
                detail=(
                    f"{ctx.ticker} is near ATH with a recent SEC {form_str} shelf/dilution "
                    f"filing detected{date_str}. Potential dilution risk — entry blocked. "
                    f"Verify the filing details before proceeding."
                ),
                metadata={
                    "near_ath": True,
                    "has_shelf_filing": True,
                    "form_type": ctx.shelf_form_type,
                    "filing_date": ctx.shelf_filing_date,
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
