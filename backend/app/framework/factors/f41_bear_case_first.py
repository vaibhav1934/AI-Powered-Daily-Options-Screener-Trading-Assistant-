"""
F41 — Bear Case First
======================
Trigger: Any bullish setup must survive a bear-case pass.
Action:  Downgrade conviction if bear case is strong.
Layer:   8 (Analyst/Conviction Weighting)
"""

from __future__ import annotations

from app.framework.factors.base import (
    BaseFactor,
    FactorAction,
    FactorResult,
    FactorStatus,
    ScanContext,
)


class F41BearCaseFirst(BaseFactor):
    factor_id = "F41"
    name = "Bear Case First"
    description = (
        "Any bullish setup must survive a bear-case pass. "
        "Downgrade conviction if the bear case is strong."
    )
    layer = 9
    status = FactorStatus.LIVE

    # Conviction reduction when bear case is strong
    DOWNGRADE_AMOUNT = 2.0

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Apply bear-case-first discipline.
        Checks for bearish signals that could undermine the bullish thesis:
        - RSI overbought (>70)
        - Price significantly above SMA-200
        - Negative change on the day with high volume
        - At ATH with earnings within window (extra risk)
        """
        bear_signals: list[str] = []

        # RSI overbought
        if ctx.rsi is not None and ctx.rsi > 70:
            bear_signals.append(f"RSI overbought at {ctx.rsi:.1f}")

        # Price far above SMA-200 (>20% above = extended)
        if ctx.sma_200 and ctx.current_price > 0:
            pct_above = ((ctx.current_price - ctx.sma_200) / ctx.sma_200) * 100
            if pct_above > 20:
                bear_signals.append(
                    f"Price {pct_above:.1f}% above SMA-200 (extended)"
                )

        # Negative day with high relative volume could indicate distribution
        if ctx.change_percent < -2.0:
            bear_signals.append(
                f"Negative day ({ctx.change_percent:.1f}%) — potential distribution"
            )

        # ATH + upcoming earnings = elevated binary risk
        if ctx.is_at_ath and ctx.earnings_within_window:
            bear_signals.append(
                "At ATH with earnings within window — elevated binary risk"
            )

        # Evaluate: strong bear case if 2+ signals
        if len(bear_signals) >= 2:
            return self._trigger(
                action=FactorAction.DOWNGRADE,
                detail=(
                    f"Bear case is strong ({len(bear_signals)} signals). "
                    f"Conviction downgraded by {self.DOWNGRADE_AMOUNT}. "
                    f"Signals: {'; '.join(bear_signals)}"
                ),
                metadata={
                    "bear_signals": bear_signals,
                    "signal_count": len(bear_signals),
                    "downgrade_amount": self.DOWNGRADE_AMOUNT,
                },
            )

        if len(bear_signals) == 1:
            return self._pass(
                detail=(
                    f"Bear case check: 1 minor signal noted ({bear_signals[0]}) "
                    f"— not strong enough to downgrade."
                )
            )

        return self._pass(detail="Bear case check passed — no significant bearish signals.")
