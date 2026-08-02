"""
Technical Data Fetcher
======================
Fetches daily candle bars (via yfinance/Finnhub) and computes RSI and SMA locally using vectorization
to eliminate Alpha Vantage rate limits (F9-F15). Falls back to Alpha Vantage if local candles fail.
Returns None if all fail (No fallback mock data per user rule).
"""

import logging
import asyncio
from typing import Optional, Any
import pandas as pd
import numpy as np

from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.alpha_vantage import AlphaVantageClient

logger = logging.getLogger(__name__)


def _compute_local_rsi(closes: pd.Series, period: int = 14) -> Optional[float]:
    """Compute Wilder's Smoothed RSI(14) on price series."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    
    # Wilder's Exponential Smoothing (SMMA / RMA)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    
    rs = avg_gain.iloc[-1] / (avg_loss.iloc[-1] + 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(float(rsi), 2)


def _compute_local_sma(closes: pd.Series, period: int) -> Optional[float]:
    """Compute Simple Moving Average over period."""
    if len(closes) < period:
        return round(float(closes.mean()), 2) if len(closes) > 0 else None
    return round(float(closes.rolling(window=period).mean().iloc[-1]), 2)


def _fetch_yf_history_sync(ticker: str) -> pd.DataFrame:
    """Helper to fetch yfinance history synchronously in a thread pool."""
    import yfinance as yf
    return yf.Ticker(ticker).history(period="1y")


def _fetch_yf_intraday_60m_sync(ticker: str) -> pd.DataFrame:
    """Helper to fetch yfinance 60m bars for short-horizon trend checks."""
    import yfinance as yf
    return yf.Ticker(ticker).history(period="30d", interval="60m")


async def fetch_technicals(ticker: str, current_price: float, session: Any = None) -> dict:
    """
    Fetches live technicals by computing RSI and SMA locally on daily candles (yfinance / Finnhub).
    Falls back to Alpha Vantage if local candle calculation fails.
    """
    rsi: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    is_at_ath: bool = False
    mtf_trend_aligned: bool = False
    relative_volume: Optional[float] = None
    volume_profile_state: Optional[float | str] = None
    volume_profile_hvn: Optional[float] = None
    volume_profile_lvn: Optional[float] = None
    gap_present: bool = False
    gap_hold_valid: bool = False
    
    # 1. Try local calculation via yfinance daily candles (unthrottled, $0 cost, instant)
    try:
        df = await asyncio.to_thread(_fetch_yf_history_sync, ticker)
        if df is not None and not df.empty and len(df) >= 20 and "Close" in df.columns:
            closes = df["Close"].astype(float).reset_index(drop=True)
            if current_price > 0 and abs(closes.iloc[-1] - current_price) > 0.01:
                closes = pd.concat([closes, pd.Series([current_price])], ignore_index=True)
                
            rsi = _compute_local_rsi(closes, period=14)
            sma_50 = _compute_local_sma(closes, period=50)
            sma_200 = _compute_local_sma(closes, period=200)
            
            if "High" in df.columns and current_price > 0:
                max_high = float(df["High"].max())
                if current_price >= max_high * 0.98:  # Within 2% of 52-week/All-time high
                    is_at_ath = True

            if "Open" in df.columns and len(df) >= 2:
                prev_close = float(df["Close"].iloc[-2])
                today_open = float(df["Open"].iloc[-1])
                if prev_close > 0:
                    gap_pct = (today_open - prev_close) / prev_close
                    gap_present = abs(gap_pct) >= 0.01
                    if gap_present and current_price > 0:
                        if gap_pct > 0:
                            gap_hold_valid = current_price >= today_open
                        else:
                            gap_hold_valid = current_price <= today_open

            if "Volume" in df.columns and len(df) >= 20:
                avg_vol_20 = float(df["Volume"].tail(20).mean())
                latest_vol = float(df["Volume"].iloc[-1])
                if avg_vol_20 > 0:
                    relative_volume = round(latest_vol / avg_vol_20, 3)

            intraday_df = await asyncio.to_thread(_fetch_yf_intraday_60m_sync, ticker)
            if intraday_df is not None and not intraday_df.empty and "Close" in intraday_df.columns and len(intraday_df) >= 20:
                i_close = intraday_df["Close"].astype(float).reset_index(drop=True)
                i_sma_20 = i_close.rolling(window=20).mean().iloc[-1]
                i_last = float(i_close.iloc[-1])
                if not np.isnan(i_sma_20):
                    mtf_trend_aligned = bool(
                        (sma_50 is not None and current_price > sma_50)
                        and i_last > float(i_sma_20)
                    )
                if "Volume" in intraday_df.columns:
                    intraday_work = intraday_df[["Close", "Volume"]].dropna().copy()
                    if not intraday_work.empty:
                        closes_arr = intraday_work["Close"].astype(float).to_numpy()
                        vols_arr = intraday_work["Volume"].astype(float).to_numpy()
                        price_min = float(closes_arr.min())
                        price_max = float(closes_arr.max())
                        if price_max > price_min:
                            bins = np.linspace(price_min, price_max, num=13)
                            hist, edges = np.histogram(closes_arr, bins=bins, weights=vols_arr)
                            if len(hist) > 0:
                                hvn_idx = int(np.argmax(hist))
                                lvn_idx = int(np.argmin(hist))
                                volume_profile_hvn = round(float((edges[hvn_idx] + edges[hvn_idx + 1]) / 2.0), 2)
                                volume_profile_lvn = round(float((edges[lvn_idx] + edges[lvn_idx + 1]) / 2.0), 2)
                                if current_price >= volume_profile_hvn * 0.995 and current_price <= volume_profile_hvn * 1.005:
                                    volume_profile_state = "AT_HVN"
                                elif current_price >= volume_profile_lvn * 0.995 and current_price <= volume_profile_lvn * 1.005:
                                    volume_profile_state = "AT_LVN"
                                elif current_price > volume_profile_hvn:
                                    volume_profile_state = "ABOVE_HVN"
                                elif current_price < volume_profile_lvn:
                                    volume_profile_state = "BELOW_LVN"
                                else:
                                    volume_profile_state = "BETWEEN_NODES"
            logger.info("[FLOW: Technicals] Computed local RSI=%s, SMA50=%s, SMA200=%s for %s from yfinance candles (%d bars)", rsi, sma_50, sma_200, ticker, len(closes))
    except Exception as e:
        logger.debug("yfinance candle calculation failed for %s: %s", ticker, e)

    # 2. Try Finnhub candles if yfinance returned None
    if rsi is None or sma_50 is None:
        finnhub = FinnhubClient()
        try:
            candles = await finnhub.get_daily_candles(ticker, days=365, session=session)
            if candles and candles.get("c") and len(candles["c"]) >= 20:
                closes = pd.Series(candles["c"], dtype=float)
                if current_price > 0 and abs(closes.iloc[-1] - current_price) > 0.01:
                    closes = pd.concat([closes, pd.Series([current_price])], ignore_index=True)
                    
                rsi = _compute_local_rsi(closes, period=14)
                sma_50 = _compute_local_sma(closes, period=50)
                sma_200 = _compute_local_sma(closes, period=200)
                
                if candles.get("h") and current_price > 0:
                    max_high = max(candles["h"])
                    if current_price >= max_high * 0.98:
                        is_at_ath = True
                logger.info("[FLOW: Technicals] Computed local RSI=%s, SMA50=%s, SMA200=%s for %s from Finnhub candles (%d bars)", rsi, sma_50, sma_200, ticker, len(closes))
        except Exception as e:
            logger.debug("Finnhub candle calculation failed for %s: %s", ticker, e)
        finally:
            await finnhub.close()

    # 3. Fallback to Alpha Vantage if local calculation returned None
    if rsi is None or sma_50 is None:
        logger.info("[FLOW: Technicals] Falling back to Alpha Vantage API for %s indicators", ticker)
        av_client = AlphaVantageClient()
        try:
            if rsi is None:
                rsi = await av_client.get_rsi(ticker, session=session)
            if sma_50 is None:
                sma_50 = await av_client.get_sma(ticker, session=session, time_period=50)
            if sma_200 is None:
                sma_200 = await av_client.get_sma(ticker, session=session, time_period=200)
        except Exception as e:
            logger.warning("Alpha Vantage fallback failed for %s: %s", ticker, e)
        finally:
            await av_client.close()
            
    if not is_at_ath and sma_200 and current_price > sma_200 * 1.5:
        is_at_ath = True

    return {
        "rsi": rsi,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "is_at_ath": is_at_ath,
        "mtf_trend_aligned": mtf_trend_aligned,
        "relative_volume": relative_volume,
        "volume_profile_state": volume_profile_state,
        "volume_profile_hvn": volume_profile_hvn,
        "volume_profile_lvn": volume_profile_lvn,
        "gap_present": gap_present,
        "gap_hold_valid": gap_hold_valid,
    }
