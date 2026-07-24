"""
Layer 1 — Universe Filter
===========================
Purpose: Full earnings calendar, all sectors, no skipping.
FR-2: Cover full earnings calendar — every name, no skipping.
FR-4: Cover all sectors including healthcare, energy storage, defense.
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.layers.base import BaseLayer


class Layer01Universe(BaseLayer):
    layer_number = 1
    name = "Universe Filter"
    description = (
        "Full earnings calendar, all sectors, no skipping. "
        "Every name is included regardless of sector or market cap."
    )

    def get_factors(self) -> list[BaseFactor]:
        """
        L1 uses stub factors F1–F8 (Earnings & Guidance category).
        These are unconfigured — the layer passes all tickers through.
        """
        from app.framework.factors.registry import factor_registry
        return factor_registry.get_factors_for_layer(0)[:8]  # F1–F8 stubs (layer=0)
