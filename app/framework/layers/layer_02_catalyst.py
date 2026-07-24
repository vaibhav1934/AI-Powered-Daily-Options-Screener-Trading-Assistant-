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
        """L2 maps to stub factors F9–F15 (Technical/Price Structure)."""
        from app.framework.factors.registry import factor_registry
        # Return stubs for this layer — will be activated when defined
        factors = factor_registry.get_factors_for_layer(0)
        return [f for f in factors if f.factor_id in {f"F{i:02d}" for i in range(9, 16)}]
