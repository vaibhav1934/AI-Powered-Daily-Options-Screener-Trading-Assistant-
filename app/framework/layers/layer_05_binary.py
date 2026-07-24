"""
Layer 5 — Binary Event Filter
================================
Purpose: Pre-earnings exits, ATH+earnings put block.
Factors: F47 (Pre-Earnings Binary Exit), F43 (ATH + Record Earnings)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f43_ath_record_earnings import F43ATHRecordEarnings
from app.framework.factors.f47_pre_earnings_exit import F47PreEarningsBinaryExit
from app.framework.layers.base import BaseLayer


class Layer05Binary(BaseLayer):
    layer_number = 5
    name = "Binary Event Filter"
    description = (
        "Filter for binary events: pre-earnings exits, "
        "ATH + record earnings put block."
    )

    def get_factors(self) -> list[BaseFactor]:
        """L5 uses F43 and F47 — both live."""
        return [F47PreEarningsBinaryExit(), F43ATHRecordEarnings()]
