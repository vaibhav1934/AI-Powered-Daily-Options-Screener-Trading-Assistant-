"""
Layer 7 — Time-of-Day Gate
=============================
Purpose: FOMC reduction, entry cutoffs.
Factors: F42 (Entry Cutoff), F45 (FOMC Reduction)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f42_entry_cutoff import F42EntryCutoff
from app.framework.factors.f45_fomc_reduction import F45FOMCReduction
from app.framework.layers.base import BaseLayer


class Layer07TimeGate(BaseLayer):
    layer_number = 7
    name = "Time-of-Day Gate"
    description = (
        "Server-authoritative time checks: entry cutoff enforcement "
        "and FOMC-day position reduction."
    )

    def get_factors(self) -> list[BaseFactor]:
        """L7 uses factors F31-F35 (Sector Rotation)."""
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
