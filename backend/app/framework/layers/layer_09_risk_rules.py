"""
Layer 9 - Risk Rules
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer09RiskRules(BaseLayer):
    layer_number = 9
    name = "Risk Rules"
    description = "Evaluates factors for Risk Rules"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)

    def process(self, ctx: ScanContext) -> ScanContext:
        """Calculate conviction score before F40 uses it."""
        from app.framework.scoring import calculate_conviction_score
        ctx.conviction_score = calculate_conviction_score(ctx)
        return super().process(ctx)
