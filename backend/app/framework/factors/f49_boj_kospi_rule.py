"""
F49 — BOJ/KOSPI Rule
======================
Trigger: KOSPI -5%+ on the day.
Action:  Avoid semiconductor call recommendations.
Layer:   3 (Macro/Tape Overlay)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)

# Semiconductor-related sectors and industries
SEMICONDUCTOR_KEYWORDS = {
    "semiconductor",
    "semiconductors",
    "chip",
    "chips",
    "foundry",
    "memory",
    "nand",
    "dram",
    "wafer",
    "fabless",
    "eda",
    "semiconductor equipment",
}


class F49BOJKOSPIRule(BaseFactor):
    factor_id = "F49"
    name = "BOJ/KOSPI Rule"
    description = (
        "When KOSPI drops -5% or more on the day, avoid semiconductor "
        "call recommendations."
    )
    layer = 3
    status = FactorStatus.LIVE

    KOSPI_THRESHOLD = -5.0  # KOSPI percentage drop threshold

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check KOSPI performance and apply semiconductor call block if triggered.
        """
        if ctx.kospi_change_percent >= self.KOSPI_THRESHOLD:
            return self._pass(
                detail=(
                    f"KOSPI change: {ctx.kospi_change_percent:+.1f}% — "
                    f"above {self.KOSPI_THRESHOLD}% threshold. No restriction."
                )
            )

        # KOSPI dropped beyond threshold — check if this is a semiconductor name
        is_semi = self._is_semiconductor(ctx)

        if is_semi:
            return self._trigger(
                action=FactorAction.VETO,
                detail=(
                    f"BOJ/KOSPI Rule triggered: KOSPI {ctx.kospi_change_percent:+.1f}% "
                    f"(threshold: {self.KOSPI_THRESHOLD}%). "
                    f"{ctx.ticker} is in semiconductor sector — "
                    f"call recommendations blocked."
                ),
                metadata={
                    "kospi_change": ctx.kospi_change_percent,
                    "threshold": self.KOSPI_THRESHOLD,
                    "is_semiconductor": True,
                    "sector": ctx.sector,
                    "industry": ctx.industry,
                },
            )

        # KOSPI crashed but ticker isn't semiconductor — just flag
        return self._trigger(
            action=FactorAction.FLAG,
            detail=(
                f"BOJ/KOSPI Rule: KOSPI {ctx.kospi_change_percent:+.1f}% "
                f"(below {self.KOSPI_THRESHOLD}% threshold). "
                f"{ctx.ticker} is not semiconductor — no block, but macro caution flagged."
            ),
            metadata={
                "kospi_change": ctx.kospi_change_percent,
                "is_semiconductor": False,
            },
        )

    @staticmethod
    def _is_semiconductor(ctx: ScanContext) -> bool:
        """Check if the ticker belongs to semiconductor sector/industry."""
        sector_lower = ctx.sector.lower()
        industry_lower = ctx.industry.lower()
        combined = f"{sector_lower} {industry_lower}"
        return any(kw in combined for kw in SEMICONDUCTOR_KEYWORDS)
