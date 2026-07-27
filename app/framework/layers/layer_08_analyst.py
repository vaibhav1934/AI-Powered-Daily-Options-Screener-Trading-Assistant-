"""
Layer 8 — Analyst/Conviction Weighting
========================================
Purpose: Tier weighting, bear-case-first discipline.
Factors: F41 (Bear Case First), F44 (Analyst Tier Weighting)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f41_bear_case_first import F41BearCaseFirst
from app.framework.factors.f44_analyst_tier_weighting import F44AnalystTierWeighting
from app.framework.layers.base import BaseLayer


class Layer08Analyst(BaseLayer):
    layer_number = 8
    name = "Analyst/Conviction Weighting"
    description = (
        "Apply analyst tier weighting to conviction adjustments "
        "and enforce bear-case-first discipline."
    )

    def get_factors(self) -> list[BaseFactor]:
        """L8 uses factors F36-F40 (News/Catalyst)."""
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
