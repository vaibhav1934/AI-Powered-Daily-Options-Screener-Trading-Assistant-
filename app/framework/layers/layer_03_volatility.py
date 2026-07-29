"""
Layer 3 - Volatility
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer03Volatility(BaseLayer):
    layer_number = 3
    name = "Volatility"
    description = "Evaluates factors for Volatility"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
