"""
Layer 8 - News/Catalyst
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer08NewsCatalyst(BaseLayer):
    layer_number = 8
    name = "News/Catalyst"
    description = "Evaluates factors for News/Catalyst"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
