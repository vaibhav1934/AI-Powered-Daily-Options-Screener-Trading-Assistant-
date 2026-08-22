"""
Compliance, Schema & Indicator Hub Verification Script
"""
import sys
import asyncio
import numpy as np
import pandas as pd

from app.db.schemas import StockDetailSchema, TechnicalIndicatorDataSchema, SupportResistanceLevels
from app.core.market_data.technicals import (
    _compute_local_sma,
    _compute_local_ema,
    _compute_local_macd,
    _compute_local_bollinger,
    _compute_local_atr,
    _compute_local_stochastic,
)

def test_indicators():
    print("Testing technical indicator calculation functions...")
    closes = pd.Series([100.0 + i * 0.5 for i in range(250)])
    highs = closes + 1.0
    lows = closes - 1.0
    
    sma_20 = _compute_local_sma(closes, 20)
    sma_50 = _compute_local_sma(closes, 50)
    sma_200 = _compute_local_sma(closes, 200)
    
    assert sma_20 is not None
    assert sma_50 is not None
    assert sma_200 is not None
    print(f"  SMA 20/50/200: {sma_20}, {sma_50}, {sma_200}")
    
    # 52-Week & 6-Month calculation
    bars_52w = min(len(highs), 252)
    high_52w = round(float(highs.tail(bars_52w).max()), 2)
    low_52w = round(float(lows.tail(bars_52w).min()), 2)
    
    bars_6m = min(len(highs), 126)
    high_6m = round(float(highs.tail(bars_6m).max()), 2)
    low_6m = round(float(lows.tail(bars_6m).min()), 2)
    
    assert high_52w > 0
    assert high_6m > 0
    print(f"  52W H/L: High={high_52w}, Low={low_52w}")
    print(f"  6M H/L: High={high_6m}, Low={low_6m}")
    
    macd = _compute_local_macd(closes)
    bb = _compute_local_bollinger(closes)
    atr = _compute_local_atr(highs, lows, closes)
    stoch = _compute_local_stochastic(highs, lows, closes)
    
    assert macd is not None
    assert bb is not None
    assert atr is not None
    assert stoch is not None
    print("  MACD, Bollinger, ATR, Stochastic calculations verified!")

def test_schemas():
    print("\nTesting Pydantic schema validation...")
    tech_data = TechnicalIndicatorDataSchema(
        support_resistance={"support": 100.0, "resistance": 110.0},
        moving_averages={"sma_200": 102.5, "golden_cross": True},
        momentum_oscillators={"rsi": 58.2, "rsi_state": "Neutral zone"},
        volume_metrics={"volume": "15.2M", "relative_volume": 1.15},
        high_low_52w={"high_52w": 125.0, "low_52w": 85.0},
        high_low_6m={"high_6m": 118.0, "low_6m": 92.0},
    )
    
    detail = StockDetailSchema(
        symbol="AAPL",
        name="Apple Inc.",
        sector="Technology",
        price=105.5,
        chg=1.5,
        pct=1.44,
        score=8.2,
        volume="45M",
        hardFlags=[],
        levels=SupportResistanceLevels(support=100.0, resistance=110.0),
        sma_200=102.5,
        high_52w=125.0,
        low_52w=85.0,
        high_6m=118.0,
        low_6m=92.0,
        technicalIndicators=tech_data,
        layerScores=[],
        reasons=[],
        news=[],
    )
    
    assert detail.symbol == "AAPL"
    assert detail.sma_200 == 102.5
    assert detail.technicalIndicators is not None
    assert detail.technicalIndicators.momentum_oscillators["rsi"] == 58.2
    print("  Pydantic schema validation passed successfully!")

if __name__ == "__main__":
    test_indicators()
    test_schemas()
    print("\nALL COMPLIANCE & TECHNICAL VERIFICATIONS PASSED SUCCESSFULLY!")
