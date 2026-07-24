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
        """L10 has no factors — it assembles the output."""
        return []

    def process(self, ctx: ScanContext) -> ScanContext:
        """
        Override process to perform ranking logic instead of factor evaluation.
        This layer doesn't evaluate factors — it assembles the final output.
        """
        # Ranking is handled by the scoring module — this layer is a pass-through
        # that marks the context as fully processed through all 10 layers.
        return ctx
