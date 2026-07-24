"""
Layer 6 — Regulatory/Filing Check
====================================
Purpose: SEC EDGAR shelf/dilution check.
Factors: F46 (EDGAR Shelf Check)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f46_edgar_shelf_check import F46EDGARShelfCheck
from app.framework.layers.base import BaseLayer


class Layer06Regulatory(BaseLayer):
    layer_number = 6
    name = "Regulatory/Filing Check"
    description = "Mandatory SEC EDGAR shelf/dilution filing check."

    def get_factors(self) -> list[BaseFactor]:
        """L6 uses F46 — live."""
        return [F46EDGARShelfCheck()]
