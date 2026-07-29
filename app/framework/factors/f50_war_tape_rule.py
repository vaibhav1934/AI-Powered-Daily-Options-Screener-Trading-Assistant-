"""
F50 — War Tape Rule
=====================
Trigger: Ceasefire/de-escalation headline.
Action:  Energy call setups treated as dead.
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

# Energy-related sectors and industries
ENERGY_KEYWORDS = {
    "energy",
    "oil",
    "gas",
    "petroleum",
    "crude",
    "natural gas",
    "lng",
    "refining",
    "pipeline",
    "upstream",
    "downstream",
    "midstream",
    "drilling",
    "exploration",
    "oilfield",
    "energy storage",
}


class F50WarTapeRule(BaseFactor):
    factor_id = "F50"
    name = "War Tape Rule"
    description = (
        "When ceasefire or de-escalation headlines appear, "
        "energy call setups are treated as dead."
    )
    layer = 10
    status = FactorStatus.LIVE

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Check for ceasefire/de-escalation headlines and block energy calls.
        """
        if not ctx.ceasefire_headline:
            return self._pass(
                detail="No ceasefire/de-escalation headlines detected."
            )

        # Ceasefire headline present — check if this is an energy name
        is_energy = self._is_energy(ctx)

        if is_energy:
            return self._trigger(
                action=FactorAction.VETO,
                detail=(
                    f"War Tape Rule triggered: ceasefire/de-escalation headline detected. "
                    f"{ctx.ticker} is in energy sector — "
                    f"call setups treated as dead."
                ),
                metadata={
                    "ceasefire_headline": True,
                    "is_energy": True,
                    "sector": ctx.sector,
                    "industry": ctx.industry,
                },
            )

        # Ceasefire headline but not energy — informational flag
        return self._trigger(
            action=FactorAction.FLAG,
            detail=(
                f"War Tape Rule: ceasefire/de-escalation headline detected. "
                f"{ctx.ticker} is not energy — no block, "
                f"but geopolitical shift flagged."
            ),
            metadata={
                "ceasefire_headline": True,
                "is_energy": False,
            },
        )

    @staticmethod
    def _is_energy(ctx: ScanContext) -> bool:
        """Check if the ticker belongs to energy sector/industry."""
        sector_lower = ctx.sector.lower()
        industry_lower = ctx.industry.lower()
        combined = f"{sector_lower} {industry_lower}"
        return any(kw in combined for kw in ENERGY_KEYWORDS)
