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


def _compute_local_ema(closes: pd.Series, period: int) -> Optional[float]:
    """Compute Exponential Moving Average over period."""
    if len(closes) < period:
        return round(float(closes.mean()), 2) if len(closes) > 0 else None
    return round(float(closes.ewm(span=period, adjust=False).mean().iloc[-1]), 2)


def _compute_local_macd(closes: pd.Series) -> dict[str, Any]:
    """Compute MACD (12, 26, 9)."""
    if len(closes) < 26:
        return {"macd": None, "signal": None, "hist": None, "state": "Insufficient data"}
    ema_12 = closes.ewm(span=12, adjust=False).mean()
    ema_26 = closes.ewm(span=26, adjust=False).mean()
    macd_line = ema_12 - ema_26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal_line
    
    last_macd = round(float(macd_line.iloc[-1]), 2)
    last_sig = round(float(signal_line.iloc[-1]), 2)
    last_hist = round(float(hist.iloc[-1]), 2)
    
    state = "Bullish momentum" if last_macd > last_sig and last_hist > 0 else "Bearish momentum" if last_macd < last_sig else "Neutral"
    if len(hist) >= 2:
        if hist.iloc[-2] <= 0 and hist.iloc[-1] > 0:
            state = "Bullish crossover"
        elif hist.iloc[-2] >= 0 and hist.iloc[-1] < 0:
            state = "Bearish crossover"
            
    return {"macd": last_macd, "signal": last_sig, "hist": last_hist, "state": state}


def _compute_local_bollinger(closes: pd.Series, period: int = 20, num_std: float = 2.0) -> dict[str, Any]:
    """Compute Bollinger Bands (20, 2)."""
    if len(closes) < period:
        return {"upper": None, "middle": None, "lower": None, "state": "Insufficient data"}
    rolling_mean = closes.rolling(window=period).mean()
    rolling_std = closes.rolling(window=period).std()
    
    middle = round(float(rolling_mean.iloc[-1]), 2)
    upper = round(float((rolling_mean + (rolling_std * num_std)).iloc[-1]), 2)
    lower = round(float((rolling_mean - (rolling_std * num_std)).iloc[-1]), 2)
    last_close = float(closes.iloc[-1])
    
    if last_close >= upper * 0.99:
        state = "Upper band test (Overbought / Expansion)"
    elif last_close <= lower * 1.01:
        state = "Lower band test (Oversold / Support)"
    else:
        state = "Within normal envelope"
        
    return {"upper": upper, "middle": middle, "lower": lower, "state": state}


def _compute_local_stochastic(highs: pd.Series, lows: pd.Series, closes: pd.Series, k_period: int = 14, d_period: int = 3) -> dict[str, Any]:
    """Compute Stochastic Oscillator %K and %D."""
    if len(closes) < k_period:
        return {"k": None, "d": None, "state": "Insufficient data"}
    lowest_low = lows.rolling(window=k_period).min()
    highest_high = highs.rolling(window=k_period).max()
    denom = highest_high - lowest_low + 1e-9
    k_series = 100.0 * ((closes - lowest_low) / denom)
    d_series = k_series.rolling(window=d_period).mean()
    
    last_k = round(float(k_series.iloc[-1]), 1)
    last_d = round(float(d_series.iloc[-1]), 1) if not np.isnan(d_series.iloc[-1]) else last_k
    
    state = "Overbought zone (>80)" if last_k >= 80 else "Oversold zone (<20)" if last_k <= 20 else "Neutral zone (20-80)"
    return {"k": last_k, "d": last_d, "state": state}


def _compute_local_atr(highs: pd.Series, lows: pd.Series, closes: pd.Series, period: int = 14) -> dict[str, Any]:
    """Compute Average True Range (14)."""
    if len(closes) < period + 1:
        return {"atr": None, "atr_pct": None}
    tr1 = highs - lows
    tr2 = (highs - closes.shift(1)).abs()
    tr3 = (lows - closes.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean().iloc[-1]
    last_close = float(closes.iloc[-1])
    atr_val = round(float(atr), 2)
    atr_pct = round((atr_val / last_close) * 100.0, 2) if last_close > 0 else 0.0
    return {"atr": atr_val, "atr_pct": atr_pct}


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
    Fetches live technicals by computing RSI, moving averages, 52W & 6M highs/lows, MACD,
    Bollinger Bands, Stochastic, ATR, and volume profiles on daily candles (yfinance / Finnhub).
    """
    rsi: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    ema_9: Optional[float] = None
    ema_21: Optional[float] = None
    golden_cross: bool = False
    death_cross: bool = False
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    high_6m: Optional[float] = None
    low_6m: Optional[float] = None
    is_at_ath: bool = False
    mtf_trend_aligned: bool = False
    relative_volume: Optional[float] = None
    avg_volume_20d: Optional[float] = None
    volume_profile_state: Optional[float | str] = None
    volume_profile_hvn: Optional[float] = None
    volume_profile_lvn: Optional[float] = None
    gap_present: bool = False
    gap_hold_valid: bool = False
    macd_info: dict[str, Any] = {"macd": None, "signal": None, "hist": None, "state": "N/A"}
    bollinger_info: dict[str, Any] = {"upper": None, "middle": None, "lower": None, "state": "N/A"}
    stochastic_info: dict[str, Any] = {"k": None, "d": None, "state": "N/A"}
    atr_info: dict[str, Any] = {"atr": None, "atr_pct": None}
    beta: Optional[float] = None
    hist_vol_30d: Optional[float] = None
    
    # 1. Try local calculation via yfinance daily candles (unthrottled, $0 cost, instant)
    try:
        df = await asyncio.to_thread(_fetch_yf_history_sync, ticker)
        if df is not None and not df.empty and len(df) >= 20 and "Close" in df.columns:
            closes = df["Close"].astype(float).reset_index(drop=True)
            highs = df["High"].astype(float).reset_index(drop=True) if "High" in df.columns else closes
            lows = df["Low"].astype(float).reset_index(drop=True) if "Low" in df.columns else closes
            
            if current_price > 0 and abs(closes.iloc[-1] - current_price) > 0.01:
                closes = pd.concat([closes, pd.Series([current_price])], ignore_index=True)
                highs = pd.concat([highs, pd.Series([max(current_price, float(highs.iloc[-1]))])], ignore_index=True)
                lows = pd.concat([lows, pd.Series([min(current_price, float(lows.iloc[-1]))])], ignore_index=True)
                
            rsi = _compute_local_rsi(closes, period=14)
            sma_20 = _compute_local_sma(closes, period=20)
            sma_50 = _compute_local_sma(closes, period=50)
            sma_200 = _compute_local_sma(closes, period=200)
            ema_9 = _compute_local_ema(closes, period=9)
            ema_21 = _compute_local_ema(closes, period=21)
            
            if sma_50 is not None and sma_200 is not None:
                golden_cross = sma_50 >= sma_200
                death_cross = sma_50 < sma_200
                
            macd_info = _compute_local_macd(closes)
            bollinger_info = _compute_local_bollinger(closes, period=20, num_std=2.0)
            stochastic_info = _compute_local_stochastic(highs, lows, closes, k_period=14, d_period=3)
            atr_info = _compute_local_atr(highs, lows, closes, period=14)
            
            # 52-Week High / Low (up to 252 bars)
            bars_52w = min(len(highs), 252)
            high_52w = round(float(highs.tail(bars_52w).max()), 2)
            low_52w = round(float(lows.tail(bars_52w).min()), 2)
            
            # 6-Month High / Low (126 bars / 26 weeks)
            bars_6m = min(len(highs), 126)
            high_6m = round(float(highs.tail(bars_6m).max()), 2)
            low_6m = round(float(lows.tail(bars_6m).min()), 2)
            
            # 30-Day Historical Volatility (annualized)
            if len(closes) >= 30:
                log_returns = np.log(closes / closes.shift(1)).dropna()
                std_30 = log_returns.tail(30).std()
                if not np.isnan(std_30):
                    hist_vol_30d = round(float(std_30 * np.sqrt(252) * 100.0), 1)
            
            if current_price > 0 and high_52w is not None:
                if current_price >= high_52w * 0.98:  # Within 2% of 52-week high
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
                avg_volume_20d = round(avg_vol_20, 0)
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
            logger.info("[FLOW: Technicals] Computed local indicators for %s from yfinance candles: RSI=%s, SMA200=%s, 52W_H=%s, 52W_L=%s, 6M_H=%s, 6M_L=%s", ticker, rsi, sma_200, high_52w, low_52w, high_6m, low_6m)
    except Exception as e:
        logger.debug("yfinance candle calculation failed for %s: %s", ticker, e)

    # 2. Try Finnhub candles if yfinance returned None
    if rsi is None or sma_50 is None:
        finnhub = FinnhubClient()
        try:
            candles = await finnhub.get_daily_candles(ticker, days=365, session=session)
            if candles and candles.get("c") and len(candles["c"]) >= 20:
                closes = pd.Series(candles["c"], dtype=float)
                highs = pd.Series(candles.get("h", candles["c"]), dtype=float)
                lows = pd.Series(candles.get("l", candles["c"]), dtype=float)
                if current_price > 0 and abs(closes.iloc[-1] - current_price) > 0.01:
                    closes = pd.concat([closes, pd.Series([current_price])], ignore_index=True)
                    highs = pd.concat([highs, pd.Series([max(current_price, float(highs.iloc[-1]))])], ignore_index=True)
                    lows = pd.concat([lows, pd.Series([min(current_price, float(lows.iloc[-1]))])], ignore_index=True)
                    
                rsi = _compute_local_rsi(closes, period=14)
                sma_20 = _compute_local_sma(closes, period=20)
                sma_50 = _compute_local_sma(closes, period=50)
                sma_200 = _compute_local_sma(closes, period=200)
                ema_9 = _compute_local_ema(closes, period=9)
                ema_21 = _compute_local_ema(closes, period=21)
                
                if sma_50 is not None and sma_200 is not None:
                    golden_cross = sma_50 >= sma_200
                    death_cross = sma_50 < sma_200
                    
                macd_info = _compute_local_macd(closes)
                bollinger_info = _compute_local_bollinger(closes, period=20, num_std=2.0)
                stochastic_info = _compute_local_stochastic(highs, lows, closes, k_period=14, d_period=3)
                atr_info = _compute_local_atr(highs, lows, closes, period=14)
                
                bars_52w = min(len(highs), 252)
                high_52w = round(float(highs.tail(bars_52w).max()), 2)
                low_52w = round(float(lows.tail(bars_52w).min()), 2)
                
                bars_6m = min(len(highs), 126)
                high_6m = round(float(highs.tail(bars_6m).max()), 2)
                low_6m = round(float(lows.tail(bars_6m).min()), 2)
                
                if current_price > 0 and high_52w is not None and current_price >= high_52w * 0.98:
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
        "sma_20": sma_20,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "ema_9": ema_9,
        "ema_21": ema_21,
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "high_6m": high_6m,
        "low_6m": low_6m,
        "macd": macd_info,
        "bollinger": bollinger_info,
        "stochastic": stochastic_info,
        "atr": atr_info,
        "hist_vol_30d": hist_vol_30d,
        "beta": beta,
        "is_at_ath": is_at_ath,
        "mtf_trend_aligned": mtf_trend_aligned,
        "relative_volume": relative_volume,
        "avg_volume_20d": avg_volume_20d,
        "volume_profile_state": volume_profile_state,
        "volume_profile_hvn": volume_profile_hvn,
        "volume_profile_lvn": volume_profile_lvn,
        "gap_present": gap_present,
        "gap_hold_valid": gap_hold_valid,
    }
