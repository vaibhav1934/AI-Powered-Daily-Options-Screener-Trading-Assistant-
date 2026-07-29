"""
Layer 5 - Analyst/Sentiment
===========================
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor, ScanContext
from app.framework.layers.base import BaseLayer

class Layer05Analyst(BaseLayer):
    layer_number = 5
    name = "Analyst/Sentiment"
    description = "Evaluates factors for Analyst/Sentiment"

    def get_factors(self) -> list[BaseFactor]:
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
