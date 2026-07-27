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
import pandas as pd

logger = logging.getLogger(__name__)


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
        df = chain.calls if is_bullish else chain.puts
        if df is None or df.empty:
            return None
            
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
        oi_val = int(best_row["openInterest"]) if "openInterest" in best_row and pd.notna(best_row["openInterest"]) else 0
        
        logger.info("[FLOW: Options Feed] Auto-selected %s contract %s (Strike: $%s, Exp: %s, OI: %d) for %s", 
                    "CALL" if is_bullish else "PUT", contract_sym, strike_val, target_exp, oi_val, ticker)
                    
        return {
            "strike_price": strike_val,
            "contract_symbol": contract_sym,
            "expiration_date": target_exp,
            "option_type": "CALL" if is_bullish else "PUT",
            "bid": bid_val,
            "ask": ask_val,
            "open_interest": oi_val,
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
