"""
F1–F39 Stub Factory
=====================
Generates explicit stubs for unconfigured factors.
Each stub returns status: "unconfigured" and stubbed: True.
The scoring engine clearly reports which factors are live vs. stubbed
so scan output is never silently incomplete.

DO NOT wire these into live scoring until their trigger conditions are supplied.
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)

# Category assignments for organizational clarity
STUB_CATEGORIES: dict[str, range] = {
    "Earnings & Guidance": range(1, 9),      # F1–F8
    "Technical/Price Structure": range(9, 16),  # F9–F15
    "Sector Rotation / Macro": range(16, 23),   # F16–F22
    "Options-Specific": range(23, 30),           # F23–F29
    "News/Sentiment": range(30, 36),             # F30–F35
    "Position Sizing / Risk": range(36, 40),     # F36–F39
}


def _get_category(factor_num: int) -> str:
    """Get the suggested category for a stubbed factor number."""
    for category, num_range in STUB_CATEGORIES.items():
        if factor_num in num_range:
            return category
    return "Uncategorized"


class StubFactor(BaseFactor):
    """
    A stubbed factor that is not yet configured.
    Returns stubbed=True with status UNCONFIGURED.
    Raises no errors — it simply reports itself as inactive.
    """

    def __init__(self, factor_num: int) -> None:
        self.factor_id = f"F{factor_num:02d}"
        self.name = f"Unconfigured Factor {self.factor_id}"
        self.description = (
            f"{self.factor_id} ({_get_category(factor_num)}) — "
            f"not yet defined. Supply trigger conditions to activate."
        )
        self.layer = 0  # Stubs don't belong to a specific layer
        self.status = FactorStatus.UNCONFIGURED
        self._category = _get_category(factor_num)

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Stubbed evaluation — always returns unconfigured status.
        Never affects scoring. Never triggers or vetoes.
        """
        return FactorResult(
            factor_id=self.factor_id,
            factor_name=self.name,
            layer_number=self.layer,
            status=FactorStatus.UNCONFIGURED,
            triggered=False,
            action=FactorAction.PASS,
            stubbed=True,
            detail=(
                f"Factor {self.factor_id} is not yet defined. "
                f"Category: {self._category}. "
                f"Supply trigger conditions and actions to activate."
            ),
            metadata={
                "category": self._category,
                "status": "unconfigured",
            },
        )


def create_all_stubs() -> list[StubFactor]:
    """
    Create stub instances for all unconfigured factors (F1–F39).
    Returns a list of 39 StubFactor instances.
    """
    return [StubFactor(i) for i in range(1, 40)]


def create_stub(factor_num: int) -> StubFactor:
    """Create a single stub factor by number."""
    if not 1 <= factor_num <= 39:
        raise ValueError(f"Stub factors are F1–F39 only, got F{factor_num}")
    return StubFactor(factor_num)
