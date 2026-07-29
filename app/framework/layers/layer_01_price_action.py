"""
Layer 1 - Price Action
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer01PriceAction(BaseLayer):
    layer_number = 1
    name = "Price Action"
    description = "Evaluates factors for Price Action"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
