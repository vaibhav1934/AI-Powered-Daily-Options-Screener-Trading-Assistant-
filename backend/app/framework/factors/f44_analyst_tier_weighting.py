"""
F44 — Analyst Tier Weighting
==============================
Trigger: Analyst rating change.
Action:  Weight by tier/reputation of issuing firm.
Layer:   8 (Analyst/Conviction Weighting)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F44AnalystTierWeighting(BaseFactor):
    factor_id = "F44"
    name = "Analyst Tier Weighting"
    description = (
        "When an analyst rating change occurs, weight the conviction "
        "adjustment by the tier/reputation of the issuing firm."
    )
    layer = 9
    status = FactorStatus.LIVE

    # Conviction adjustments by analyst tier
    TIER_WEIGHTS: dict[int, float] = {
        1: 1.5,   # Top tier (Goldman, Morgan Stanley, JP Morgan, etc.)
        2: 1.0,   # Mid tier
        3: 0.5,   # Low tier / less established
    }

    DEFAULT_WEIGHT = 0.5  # Unknown tier

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Apply analyst tier weighting to conviction score.
        Higher-tier firms produce larger conviction adjustments.
        """
        if not ctx.analyst_rating_change:
            return self._pass(
                detail="No analyst rating change detected."
            )

        tier = ctx.analyst_firm_tier or 3  # Default to low tier if unknown
        weight = self.TIER_WEIGHTS.get(tier, self.DEFAULT_WEIGHT)

        tier_labels = {1: "Top Tier", 2: "Mid Tier", 3: "Low Tier"}
        tier_label = tier_labels.get(tier, "Unknown Tier")

        return self._trigger(
            action=FactorAction.FLAG,
            detail=(
                f"Analyst rating change detected — firm tier: {tier_label} "
                f"(Tier {tier}). Conviction weight: {weight}x. "
                f"Higher-tier upgrades carry more weight."
            ),
            metadata={
                "analyst_tier": tier,
                "tier_label": tier_label,
                "conviction_weight": weight,
            },
        )
