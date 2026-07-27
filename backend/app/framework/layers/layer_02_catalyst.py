"""
Layer 2 — Catalyst Detection
===============================
Purpose: AH beats, +10% ecosystem partner moves.
FR-3: Include prior-day +10% ecosystem partners and after-hours beats.
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.layers.base import BaseLayer


class Layer02Catalyst(BaseLayer):
    layer_number = 2
    name = "Catalyst Detection"
    description = (
        "Detect catalysts: after-hours earnings beats, "
        "+10% ecosystem partner moves."
    )

    def get_factors(self) -> list[BaseFactor]:
        """L2 uses factors F6-F10 (Volume/Flow)."""
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(self.layer_number)
