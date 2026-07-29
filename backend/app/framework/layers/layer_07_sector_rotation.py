"""
Layer 7 - Sector Rotation
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer07SectorRotation(BaseLayer):
    layer_number = 7
    name = "Sector Rotation"
    description = "Evaluates factors for Sector Rotation"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
