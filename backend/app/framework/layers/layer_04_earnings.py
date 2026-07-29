"""
Layer 4 - Earnings Calendar
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer04Earnings(BaseLayer):
    layer_number = 4
    name = "Earnings Calendar"
    description = "Evaluates factors for Earnings Calendar"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
