"""
Layer 10 - Position Fit
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer10PositionFit(BaseLayer):
    layer_number = 10
    name = "Position Fit"
    description = "Evaluates factors for Position Fit"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)

    def process(self, ctx: ScanContext) -> ScanContext:
        """Final output layer."""
        return super().process(ctx)
