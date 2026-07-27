"""
Layer 9 — Conviction Scoring
===============================
Purpose: Halo trade capping, "no clean setup" veto.
Factors: F40 (No Clean Setup)
FR-11: Halo trades hard-capped at max 6.5/10 conviction.
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f40_no_clean_setup import F40NoCleanSetup
from app.framework.layers.base import BaseLayer


class Layer09Conviction(BaseLayer):
    layer_number = 9
    name = "Conviction Scoring"
    description = (
        "Final conviction scoring: halo trade capping at 6.5/10, "
        "and 'no clean setup' veto when no coherent thesis exists."
    )

    def get_factors(self) -> list[BaseFactor]:
        """L9 uses factors F41-F45 (Risk Rules)."""
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
