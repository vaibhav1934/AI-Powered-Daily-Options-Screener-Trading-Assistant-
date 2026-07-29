"""
Layer 2 - Volume/Flow
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer02VolumeFlow(BaseLayer):
    layer_number = 2
    name = "Volume/Flow"
    description = "Evaluates factors for Volume/Flow"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
