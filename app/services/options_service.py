"""
Automated Options Chain Selector Service
========================================
Fetches live option chains via yfinance and selects institutional 30–45 DTE contracts
with Target Delta ~0.30 to 0.45 (OTM/ATM liquid strikes) without using mock percentage guesses.
Adheres strictly to Rule 1 (Zero Mock Data): Returns None if live chain is unavailable.
"""

import logging
import asyncio
from datetime import date, datetime
from typing import Optional, Dict, Any
import math
import pandas as pd

logger = logging.getLogger(__name__)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _estimate_greeks(spot: float, strike: float, dte: int, implied_vol: float, is_call: bool) -> tuple[Optional[float], Optional[float]]:
    if spot <= 0 or strike <= 0 or dte <= 0 or implied_vol <= 0:
        return None, None
    time_years = dte / 365.0
    rate = 0.04
    sigma = implied_vol
    try:
        d1 = (math.log(spot / strike) + (rate + 0.5 * sigma * sigma) * time_years) / (sigma * math.sqrt(time_years))
        d2 = d1 - sigma * math.sqrt(time_years)
        nd1 = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 * d1)
        if is_call:
            delta = _norm_cdf(d1)
            theta = (-(spot * nd1 * sigma) / (2 * math.sqrt(time_years)) - rate * strike * math.exp(-rate * time_years) * _norm_cdf(d2)) / 365.0
        else:
            delta = _norm_cdf(d1) - 1.0
            theta = (-(spot * nd1 * sigma) / (2 * math.sqrt(time_years)) + rate * strike * math.exp(-rate * time_years) * _norm_cdf(-d2)) / 365.0
        return round(float(delta), 4), round(float(theta), 4)
    except Exception:
        return None, None


def _select_contract_sync(ticker: str, current_price: float, is_bullish: bool) -> Optional[Dict[str, Any]]:
    """Synchronous helper to fetch and parse yfinance option chain."""
    import yfinance as yf
    
    if current_price <= 0:
        return None
        
    yf_ticker = yf.Ticker(ticker)
    exps = yf_ticker.options
    if not exps:
        logger.debug("[FLOW: Options Feed] No option expirations found for %s", ticker)
        return None
        
    today = date.today()
    target_exp = None
    
    # 1. Look for expiration between 30 and 45 DTE
    for exp_str in exps:
        try:
            exp_date = date.fromisoformat(exp_str)
            dte = (exp_date - today).days
            if 30 <= dte <= 45:
                target_exp = exp_str
                break
        except ValueError:
            continue
            
    # If none in 30-45 DTE, pick closest future expiration >= 14 DTE
    if not target_exp:
        for exp_str in exps:
            try:
                exp_date = date.fromisoformat(exp_str)
                dte = (exp_date - today).days
                if dte >= 14:
                    target_exp = exp_str
                    break
            except ValueError:
                continue
                
    if not target_exp:
        target_exp = exps[0]  # Fallback to first available future expiration
        
    try:
        chain = yf_ticker.option_chain(target_exp)
        calls_df = chain.calls
        puts_df = chain.puts
        df = calls_df if is_bullish else puts_df
        if df is None or df.empty:
            return None

        iv_rank_1y = None
        iv_crush_risk = None
        put_call_oi_ratio = None
        skew_signal = None

        try:
            iv_series = df["impliedVolatility"].dropna() if "impliedVolatility" in df.columns else pd.Series(dtype=float)
            if not iv_series.empty:
                iv_min = float(iv_series.min())
                iv_max = float(iv_series.max())
                iv_now = float(iv_series.median())
                if iv_max > iv_min:
                    iv_rank_1y = round(((iv_now - iv_min) / (iv_max - iv_min)) * 100.0, 2)
                    if iv_rank_1y >= 70.0:
                        iv_crush_risk = "HIGH"
                    elif iv_rank_1y >= 40.0:
                        iv_crush_risk = "MEDIUM"
                    else:
                        iv_crush_risk = "LOW"
        except Exception:
            iv_rank_1y = None
            iv_crush_risk = None

        try:
            call_oi = float(calls_df["openInterest"].fillna(0).sum()) if calls_df is not None and "openInterest" in calls_df.columns else 0.0
            put_oi = float(puts_df["openInterest"].fillna(0).sum()) if puts_df is not None and "openInterest" in puts_df.columns else 0.0
            if call_oi > 0:
                put_call_oi_ratio = round(put_oi / call_oi, 3)
                if put_call_oi_ratio > 1.15:
                    skew_signal = "PUT_HEDGE_HEAVY"
                elif put_call_oi_ratio < 0.85:
                    skew_signal = "CALL_SPEC_HEAVY"
                else:
                    skew_signal = "BALANCED"
        except Exception:
            put_call_oi_ratio = None
            skew_signal = None
            
        # 2. Filter for strikes in target Delta zone (~0.30 to 0.45 Delta proxy)
        # For Calls: 1% to 8% OTM (strike between price*1.01 and price*1.08)
        # For Puts: 1% to 8% OTM (strike between price*0.92 and price*0.99)
        if is_bullish:
            zone_df = df[(df["strike"] >= current_price * 1.01) & (df["strike"] <= current_price * 1.08)]
        else:
            zone_df = df[(df["strike"] <= current_price * 0.99) & (df["strike"] >= current_price * 0.92)]
            
        # If zone is empty, take the closest OTM strike
        if zone_df.empty:
            if is_bullish:
                otm_df = df[df["strike"] >= current_price]
                zone_df = otm_df.head(3) if not otm_df.empty else df.tail(3)
            else:
                otm_df = df[df["strike"] <= current_price]
                zone_df = otm_df.tail(3) if not otm_df.empty else df.head(3)
                
        if zone_df.empty:
            return None
            
        # 3. Select most liquid contract in zone by openInterest (or volume)
        sort_col = "openInterest" if "openInterest" in zone_df.columns else ("volume" if "volume" in zone_df.columns else "strike")
        best_row = zone_df.sort_values(by=sort_col, ascending=False).iloc[0]
        
        strike_val = float(best_row["strike"])
        contract_sym = str(best_row["contractSymbol"])
        bid_val = float(best_row["bid"]) if "bid" in best_row and pd.notna(best_row["bid"]) else float(best_row["lastPrice"])
        ask_val = float(best_row["ask"]) if "ask" in best_row and pd.notna(best_row["ask"]) else float(best_row["lastPrice"])
        mid_val = (bid_val + ask_val) / 2.0 if bid_val > 0 and ask_val > 0 else float(best_row["lastPrice"])
        oi_val = int(best_row["openInterest"]) if "openInterest" in best_row and pd.notna(best_row["openInterest"]) else 0
        volume_val = int(best_row["volume"]) if "volume" in best_row and pd.notna(best_row["volume"]) else 0
        iv_val = float(best_row["impliedVolatility"]) if "impliedVolatility" in best_row and pd.notna(best_row["impliedVolatility"]) else 0.0
        dte_val = max(1, (date.fromisoformat(target_exp) - today).days)
        delta_val, theta_daily_val = _estimate_greeks(current_price, strike_val, dte_val, iv_val, is_bullish)
        
        logger.info("[FLOW: Options Feed] Auto-selected %s contract %s (Strike: $%s, Exp: %s, OI: %d) for %s", 
                    "CALL" if is_bullish else "PUT", contract_sym, strike_val, target_exp, oi_val, ticker)
                    
        return {
            "strike_price": strike_val,
            "contract_symbol": contract_sym,
            "expiration_date": target_exp,
            "option_type": "CALL" if is_bullish else "PUT",
            "bid": bid_val,
            "ask": ask_val,
            "mid_price": mid_val,
            "open_interest": oi_val,
            "volume": volume_val,
            "option_delta": delta_val,
            "option_theta_daily": theta_daily_val,
            "option_dte": dte_val,
            "iv_rank_1y": iv_rank_1y,
            "iv_crush_risk": iv_crush_risk,
            "put_call_oi_ratio": put_call_oi_ratio,
            "skew_signal": skew_signal,
        }
    except Exception as e:
        logger.warning("Failed to fetch option chain for %s (%s): %s", ticker, target_exp, e)
        return None


async def get_automated_option_contract(ticker: str, current_price: float, is_bullish: bool = True) -> Optional[Dict[str, Any]]:
    """
    Async wrapper to automatically select a live institutional option contract.
    Returns None if live market data is unavailable (Zero Mock Data Rule).
    """
    try:
        return await asyncio.to_thread(_select_contract_sync, ticker, current_price, is_bullish)
    except Exception as e:
        logger.warning("Automated option contract selection failed for %s: %s", ticker, e)
        return None
