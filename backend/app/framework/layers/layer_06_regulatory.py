"""
Layer 6 — Regulatory/Filing Check
====================================
Purpose: SEC EDGAR shelf/dilution check.
Factors: F46 (EDGAR Shelf Check)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f46_edgar_shelf_check import F46EDGARShelfCheck
from app.framework.layers.base import BaseLayer


class Layer06Regulatory(BaseLayer):
    layer_number = 6
    name = "Regulatory/Filing Check"
    description = "Mandatory SEC EDGAR shelf/dilution filing check."

    def get_factors(self) -> list[BaseFactor]:
        """L6 uses factors F26-F30 (Macro/Rates)."""
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
