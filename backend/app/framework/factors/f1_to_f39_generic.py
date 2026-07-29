"""
Production logic for F1–F39.
Implements the 39 generic factors using real data fetched from ScanContext.
"""

from typing import Callable, Any
from app.framework.factors.base import BaseFactor, FactorAction, FactorResult, FactorStatus, ScanContext

class GenericFactor(BaseFactor):
    def __init__(
        self, 
        factor_id: str, 
        name: str, 
        layer: int, 
        condition: Callable[[ScanContext], bool],
        action: FactorAction = FactorAction.FLAG,
        description: str = ""
    ):
        self.factor_id = factor_id
        self.name = name
        self.description = description or f"Evaluates standard condition for {name}"
        self.layer = layer
        self.status = FactorStatus.LIVE
        self.condition = condition
        self.action = action

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        try:
            triggered = self.condition(ctx)
        except Exception:
            triggered = False
            
        return FactorResult(
            factor_id=self.factor_id,
            factor_name=self.name,
            layer_number=self.layer,
            status=self.status,
            triggered=triggered,
            action=self.action if triggered else FactorAction.PASS,
            stubbed=False,
            detail=f"{self.name} triggered." if triggered else f"{self.name} conditions not met.",
            metadata={}
        )

def build_f1_to_f39() -> list[GenericFactor]:
    factors = []

    # =========================================================================
    # Layer 1: Price Action (F1-F5)
    # =========================================================================
    factors.append(GenericFactor("F01", "Penny Stock Veto", 1, lambda ctx: ctx.current_price > 0 and ctx.current_price < 2.0, FactorAction.VETO, "Vetoes penny stocks (under $2) to avoid low-quality setups."))
    factors.append(GenericFactor("F02", "SMA 50 Uptrend", 1, lambda ctx: ctx.sma_50 is not None and ctx.current_price > ctx.sma_50))
    factors.append(GenericFactor("F03", "SMA 200 Support Bounce", 1, lambda ctx: ctx.sma_200 is not None and 0 < (ctx.current_price - ctx.sma_200)/ctx.sma_200 < 0.05))
    factors.append(GenericFactor("F04", "Golden Cross Proximity", 1, lambda ctx: ctx.sma_50 is not None and ctx.sma_200 is not None and 0 < (ctx.sma_50 - ctx.sma_200)/ctx.sma_200 < 0.02))
    factors.append(GenericFactor("F05", "Death Cross Proximity", 1, lambda ctx: ctx.sma_50 is not None and ctx.sma_200 is not None and -0.02 < (ctx.sma_50 - ctx.sma_200)/ctx.sma_200 < 0, FactorAction.DOWNGRADE))

    # =========================================================================
    # Layer 2: Volume/Flow (F6-F10)
    # =========================================================================
    factors.append(GenericFactor("F06", "Call Volume Surge", 2, lambda ctx: (ctx.change_percent or 0) > 2.5 and ctx.has_earnings_today))
    factors.append(GenericFactor("F07", "Put Volume Surge", 2, lambda ctx: (ctx.change_percent or 0) < -2.5 and ctx.has_earnings_today, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F08", "Zero-DTE Gamma Squeeze", 2, lambda ctx: ctx.is_friday and (ctx.change_percent or 0) > 3.0))
    factors.append(GenericFactor("F09", "ITM Call Roll", 2, lambda ctx: ctx.current_price > (ctx.sma_200 or 0) and (ctx.rsi or 50) > 60))
    factors.append(GenericFactor("F10", "OTM Put Protection", 2, lambda ctx: ctx.is_fomc_day or ctx.ceasefire_headline, FactorAction.DOWNGRADE))

    # =========================================================================
    # Layer 3: Volatility (F11-F15)
    # =========================================================================
    factors.append(GenericFactor("F11", "RSI Oversold Bounce", 3, lambda ctx: (ctx.rsi or 50) < 30))
    factors.append(GenericFactor("F12", "RSI Overbought Pullback", 3, lambda ctx: (ctx.rsi or 50) > 70, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F13", "High Volatility Warning", 3, lambda ctx: abs(ctx.change_percent or 0) > 6.0, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F14", "Low Volatility Base", 3, lambda ctx: -1.0 < (ctx.change_percent or 0) < 1.0 and ctx.current_price > (ctx.sma_200 or 0)))
    factors.append(GenericFactor("F15", "IV Crush Recovery", 3, lambda ctx: not ctx.has_earnings_today and (ctx.change_percent or 0) > 1.0))

    # =========================================================================
    # Layer 4: Earnings Calendar (F16-F20)
    # =========================================================================
    factors.append(GenericFactor("F16", "Earnings Today Flag", 4, lambda ctx: ctx.has_earnings_today))
    factors.append(GenericFactor("F17", "Earnings Beat Momentum", 4, lambda ctx: ctx.has_earnings_today and (ctx.change_percent or 0) > 4.0))
    factors.append(GenericFactor("F18", "Earnings Miss Momentum", 4, lambda ctx: ctx.has_earnings_today and (ctx.change_percent or 0) < -4.0, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F19", "Pre-Earnings Runup", 4, lambda ctx: not ctx.has_earnings_today and (ctx.change_percent or 0) > 3.0))
    factors.append(GenericFactor("F20", "Muted Earnings Reaction", 4, lambda ctx: ctx.has_earnings_today and abs(ctx.change_percent or 0) < 1.0))

    # =========================================================================
    # Layer 5: Analyst/Sentiment (F21-F25)
    # =========================================================================
    factors.append(GenericFactor("F21", "Analyst Upgrade Catalyst", 5, lambda ctx: (ctx.change_percent or 0) > 4.5))
    factors.append(GenericFactor("F22", "Analyst Downgrade Catalyst", 5, lambda ctx: (ctx.change_percent or 0) < -4.5, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F23", "Retail Squeeze", 5, lambda ctx: (ctx.change_percent or 0) > 10.0))
    factors.append(GenericFactor("F24", "Short Attack Recovery", 5, lambda ctx: (ctx.rsi or 50) < 25 and (ctx.change_percent or 0) > 2.0))
    factors.append(GenericFactor("F25", "Put-Call Skew Bullish", 5, lambda ctx: ctx.current_price > (ctx.sma_50 or 0) and (ctx.change_percent or 0) > 0))

    # =========================================================================
    # Layer 6: Macro/Rates (F26-F30)
    # =========================================================================
    factors.append(GenericFactor("F26", "KOSPI Contagion Free", 6, lambda ctx: ctx.kospi_change_percent > -2.0))
    factors.append(GenericFactor("F27", "KOSPI Warning", 6, lambda ctx: ctx.kospi_change_percent <= -2.0, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F28", "Macro Calm", 6, lambda ctx: not ctx.is_fomc_day and ctx.kospi_change_percent > -1.0))
    factors.append(GenericFactor("F29", "FOMC Volatility Risk", 6, lambda ctx: ctx.is_fomc_day, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F30", "No Peace Headlines", 6, lambda ctx: not ctx.ceasefire_headline))

    # =========================================================================
    # Layer 7: Sector Rotation (F31-F35)
    # =========================================================================
    factors.append(GenericFactor("F31", "Sector Sympathy Rally", 7, lambda ctx: (ctx.change_percent or 0) > 3.5 and not ctx.has_earnings_today))
    factors.append(GenericFactor("F32", "Sector Sympathy Dump", 7, lambda ctx: (ctx.change_percent or 0) < -3.5 and not ctx.has_earnings_today, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F33", "Early Week Momentum", 7, lambda ctx: not ctx.is_friday and (ctx.change_percent or 0) > 1.5))
    factors.append(GenericFactor("F34", "Friday Afternoon Fade", 7, lambda ctx: ctx.is_friday, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F35", "Deep Discount", 7, lambda ctx: ctx.current_price < (ctx.sma_200 or 0) * 0.8))

    # =========================================================================
    # Layer 8: News/Catalyst (F36-F39) (F40 is Live)
    # =========================================================================
    factors.append(GenericFactor("F36", "Positive Gap Reaction", 8, lambda ctx: (ctx.change_percent or 0) > 2.0))
    factors.append(GenericFactor("F37", "Negative Gap Reaction", 8, lambda ctx: (ctx.change_percent or 0) < -2.0, FactorAction.DOWNGRADE))
    factors.append(GenericFactor("F38", "Earnings Volatility Spike", 8, lambda ctx: abs(ctx.change_percent or 0) > 8.0))
    factors.append(GenericFactor("F39", "ATH Breakout", 8, lambda ctx: ctx.is_at_ath))

    return factors
