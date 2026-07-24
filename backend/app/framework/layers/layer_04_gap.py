"""
Layer 4 — Structural Gap Check
=================================
Purpose: Gap-hold validation, Day-2 gap skip rule.
Factors: F48 (Gap-Hold Protocol)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f48_gap_hold_protocol import F48GapHoldProtocol
from app.framework.layers.base import BaseLayer


class Layer04Gap(BaseLayer):
    layer_number = 4
    name = "Structural Gap Check"
    description = "Validate overnight gap-hold structure before entry."

    def get_factors(self) -> list[BaseFactor]:
        """L4 uses F48 — live."""
        return [F48GapHoldProtocol()]
