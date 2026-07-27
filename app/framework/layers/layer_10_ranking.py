"""
Layer 10 — Output Ranking
===========================
Purpose: Final List 1 / List 2 assembly with ranked output.
No factors of its own — this layer assembles the final ranked output.
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer


class Layer10Ranking(BaseLayer):
    layer_number = 10
    name = "Output Ranking"
    description = "Final List 1 (daily) + List 2 (monthly) assembly and rank sort."

    def get_factors(self) -> list[BaseFactor]:
        """L10 uses factors F46-F50 (Position Fit)."""
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)

    def process(self, ctx: ScanContext) -> ScanContext:
        """
        Evaluate L10 factors and perform ranking/assembly pass-through.
        """
        ctx = super().process(ctx)
        return ctx
