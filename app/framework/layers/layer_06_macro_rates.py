"""
Layer 6 - Macro/Rates
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer06MacroRates(BaseLayer):
    layer_number = 6
    name = "Macro/Rates"
    description = "Evaluates factors for Macro/Rates"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
