"""
Layer 3 — Macro/Tape Overlay
===============================
Purpose: War tape, BOJ/KOSPI, ceasefire headlines.
Factors: F49 (BOJ/KOSPI Rule), F50 (War Tape Rule)
"""

from __future__ import annotations

from app.framework.factors.base import BaseFactor
from app.framework.factors.f49_boj_kospi_rule import F49BOJKOSPIRule
from app.framework.factors.f50_war_tape_rule import F50WarTapeRule
from app.framework.layers.base import BaseLayer


class Layer03Macro(BaseLayer):
    layer_number = 3
    name = "Macro/Tape Overlay"
    description = (
        "Evaluate macro environment: war tape headlines, "
        "BOJ/KOSPI crash conditions, ceasefire/de-escalation."
    )

    def get_factors(self) -> list[BaseFactor]:
        """L3 uses F49 and F50 — both are live."""
        return [F49BOJKOSPIRule(), F50WarTapeRule()]
