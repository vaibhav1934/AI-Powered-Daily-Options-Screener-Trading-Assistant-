from __future__ import annotations

import asyncio
import csv
import io
import logging
from typing import Any, Optional

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

FRED_GRAPH_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SERIES_URL = "https://api.stlouisfed.org/fred/series/observations"

SECTOR_ETF_MAP: dict[str, str] = {
    "technology": "XLK",
    "semiconductor": "SOXX",
    "communication": "XLC",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "financial": "XLF",
    "healthcare": "XLV",
    "industrial": "XLI",
    "energy": "XLE",
    "materials": "XLB",
    "real estate": "XLRE",
    "utilities": "XLU",
    "aerospace": "ITA",
}


def _pct_change(values: list[float], lookback: int) -> Optional[float]:
    if len(values) <= lookback:
        return None
    base = values[-(lookback + 1)]
    latest = values[-1]
    if base == 0:
        return None
    return (latest - base) / base


def _safe_corr(lhs: list[float], rhs: list[float]) -> Optional[float]:
    if len(lhs) < 10 or len(rhs) < 10 or len(lhs) != len(rhs):
        return None
    mean_l = sum(lhs) / len(lhs)
    mean_r = sum(rhs) / len(rhs)
    cov = sum((a - mean_l) * (b - mean_r) for a, b in zip(lhs, rhs, strict=False))
    var_l = sum((a - mean_l) ** 2 for a in lhs)
    var_r = sum((b - mean_r) ** 2 for b in rhs)
    if var_l <= 0 or var_r <= 0:
        return None
    return cov / ((var_l ** 0.5) * (var_r ** 0.5))


def _resolve_sector_etf(sector: str) -> Optional[str]:
    sector_lower = (sector or "").strip().lower()
    if not sector_lower:
        return None
    for key, etf in SECTOR_ETF_MAP.items():
        if key in sector_lower:
            return etf
    return None


async def _fetch_fred_series(series_id: str) -> list[tuple[str, float]]:
    settings = get_settings()
    fred_api_key = (settings.market_data.fred_api_key or "").strip()

    if fred_api_key:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                FRED_SERIES_URL,
                params={
                    "series_id": series_id,
                    "api_key": fred_api_key,
                    "file_type": "json",
                    "sort_order": "asc",
                },
            )
            response.raise_for_status()

        payload = response.json()
        observations = payload.get("observations", []) if isinstance(payload, dict) else []
        parsed: list[tuple[str, float]] = []
        for row in observations:
            if not isinstance(row, dict):
                continue
            value = str(row.get("value", "")).strip()
            date_value = str(row.get("date", "")).strip()
            if not value or value == ".":
                continue
            try:
                parsed.append((date_value, float(value)))
            except ValueError:
                continue
        return parsed

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(FRED_GRAPH_URL, params={"id": series_id})
        response.raise_for_status()

    rows = csv.DictReader(io.StringIO(response.text))
    parsed: list[tuple[str, float]] = []
    for row in rows:
        value = (row.get(series_id) or "").strip()
        date_value = (row.get("DATE") or "").strip()
        if not value or value == ".":
            continue
        try:
            parsed.append((date_value, float(value)))
        except ValueError:
            continue
    return parsed


def _load_yfinance_closes(ticker: str, period: str = "3mo") -> list[float]:
    import yfinance as yf

    history = yf.Ticker(ticker).history(period=period)
    if history is None or history.empty or "Close" not in history.columns:
        return []
    return [float(v) for v in history["Close"].dropna().tolist()]


def _load_yfinance_intraday(ticker: str, period: str = "5d", interval: str = "5m"):
    import yfinance as yf

    return yf.Ticker(ticker).history(period=period, interval=interval)


def _compute_overnight_futures_gap() -> dict[str, Any]:
    import pandas as pd

    result = {
        "overnight_futures_gap_pct": None,
        "overnight_outside_prior_range": None,
    }
    df = _load_yfinance_intraday("ES=F", period="5d", interval="5m")
    if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
        return result

    df = df.copy()
    if df.index.tz is None:
        df.index = df.index.tz_localize("America/New_York")
    else:
        df.index = df.index.tz_convert("America/New_York")

    session_days = sorted({ts.date() for ts in df.index})
    if len(session_days) < 2:
        return result

    current_day = session_days[-1]
    prev_day = session_days[-2]
    prev_rth = df[(df.index.date == prev_day) & (df.index.time >= pd.Timestamp("09:30").time()) & (df.index.time <= pd.Timestamp("16:00").time())]
    current_overnight = df[(df.index.date == current_day) & (df.index.time < pd.Timestamp("09:30").time())]
    if prev_rth.empty or current_overnight.empty:
        return result

    prev_close = float(prev_rth["Close"].iloc[-1])
    overnight_open = float(current_overnight["Open"].iloc[0])
    prev_high = float(prev_rth["High"].max())
    prev_low = float(prev_rth["Low"].min())
    if prev_close > 0:
        result["overnight_futures_gap_pct"] = (overnight_open - prev_close) / prev_close
    result["overnight_outside_prior_range"] = bool(overnight_open > prev_high or overnight_open < prev_low)
    return result


async def fetch_free_macro_signals() -> dict[str, Any]:
    signals: dict[str, Any] = {
        "dxy_change_5d": None,
        "ust2y_yield": None,
        "ust10y_yield": None,
        "curve_10y_2y_bps": None,
        "curve_change_5d_bps": None,
        "hyg_lqd_ratio_change_5d": None,
        "gld_change_5d": None,
        "dax_change_percent": None,
        "ftse_change_percent": None,
        "vix_spot": None,
        "vix9d": None,
        "vix3m": None,
        "vix_term_slope": None,
        "overnight_futures_gap_pct": None,
        "overnight_outside_prior_range": None,
    }

    fred_2y_task = _fetch_fred_series("DGS2")
    fred_10y_task = _fetch_fred_series("DGS10")

    yfinance_tasks = {
        "dxy": asyncio.to_thread(_load_yfinance_closes, "DX-Y.NYB", "3mo"),
        "gld": asyncio.to_thread(_load_yfinance_closes, "GLD", "3mo"),
        "hyg": asyncio.to_thread(_load_yfinance_closes, "HYG", "3mo"),
        "lqd": asyncio.to_thread(_load_yfinance_closes, "LQD", "3mo"),
        "dax": asyncio.to_thread(_load_yfinance_closes, "^GDAXI", "1mo"),
        "ftse": asyncio.to_thread(_load_yfinance_closes, "^FTSE", "1mo"),
        "vix": asyncio.to_thread(_load_yfinance_closes, "^VIX", "1mo"),
        "vix9d": asyncio.to_thread(_load_yfinance_closes, "^VIX9D", "1mo"),
        "vix3m": asyncio.to_thread(_load_yfinance_closes, "^VIX3M", "1mo"),
        "overnight_gap": asyncio.to_thread(_compute_overnight_futures_gap),
    }

    try:
        fred_2y, fred_10y = await asyncio.gather(fred_2y_task, fred_10y_task)
        if fred_2y and fred_10y:
            signals["ust2y_yield"] = fred_2y[-1][1]
            signals["ust10y_yield"] = fred_10y[-1][1]
            signals["curve_10y_2y_bps"] = (fred_10y[-1][1] - fred_2y[-1][1]) * 100.0
            if len(fred_2y) >= 6 and len(fred_10y) >= 6:
                prior_curve = (fred_10y[-6][1] - fred_2y[-6][1]) * 100.0
                signals["curve_change_5d_bps"] = signals["curve_10y_2y_bps"] - prior_curve
    except Exception as exc:
        logger.warning("Free rates signal fetch failed: %s", exc)

    yf_results = await asyncio.gather(*yfinance_tasks.values(), return_exceptions=True)
    yf_map = dict(zip(yfinance_tasks.keys(), yf_results, strict=False))

    dxy = yf_map.get("dxy")
    if isinstance(dxy, list):
        signals["dxy_change_5d"] = _pct_change(dxy, 5)

    gld = yf_map.get("gld")
    if isinstance(gld, list):
        signals["gld_change_5d"] = _pct_change(gld, 5)

    hyg = yf_map.get("hyg")
    lqd = yf_map.get("lqd")
    if isinstance(hyg, list) and isinstance(lqd, list) and len(hyg) >= 6 and len(lqd) >= 6:
        ratio_now = hyg[-1] / lqd[-1] if lqd[-1] else None
        ratio_prev = hyg[-6] / lqd[-6] if lqd[-6] else None
        if ratio_now is not None and ratio_prev not in (None, 0):
            signals["hyg_lqd_ratio_change_5d"] = (ratio_now - ratio_prev) / ratio_prev

    dax = yf_map.get("dax")
    if isinstance(dax, list):
        change = _pct_change(dax, 1)
        signals["dax_change_percent"] = change * 100.0 if change is not None else None

    ftse = yf_map.get("ftse")
    if isinstance(ftse, list):
        change = _pct_change(ftse, 1)
        signals["ftse_change_percent"] = change * 100.0 if change is not None else None

    vix = yf_map.get("vix")
    if isinstance(vix, list) and vix:
        signals["vix_spot"] = vix[-1]

    vix9d = yf_map.get("vix9d")
    if isinstance(vix9d, list) and vix9d:
        signals["vix9d"] = vix9d[-1]

    vix3m = yf_map.get("vix3m")
    if isinstance(vix3m, list) and vix3m:
        signals["vix3m"] = vix3m[-1]

    if isinstance(signals["vix9d"], (int, float)) and isinstance(signals["vix3m"], (int, float)):
        signals["vix_term_slope"] = float(signals["vix3m"]) - float(signals["vix9d"])

    overnight_gap = yf_map.get("overnight_gap")
    if isinstance(overnight_gap, dict):
        signals["overnight_futures_gap_pct"] = overnight_gap.get("overnight_futures_gap_pct")
        signals["overnight_outside_prior_range"] = overnight_gap.get("overnight_outside_prior_range")

    return signals


async def fetch_free_sector_signals(ticker: str, sector: str) -> dict[str, Any]:
    etf = _resolve_sector_etf(sector)
    signals: dict[str, Any] = {
        "sector_etf_symbol": etf,
        "sector_rs_5d": None,
        "sector_rs_20d": None,
        "ticker_sector_corr_20d": None,
        "idiosyncratic_alpha_20d": None,
        "sector_flow_score": None,
    }
    if not etf:
        return signals

    try:
        ticker_hist_task = asyncio.to_thread(_load_yfinance_closes, ticker.upper(), "3mo")
        etf_hist_task = asyncio.to_thread(_load_yfinance_closes, etf, "3mo")
        spy_hist_task = asyncio.to_thread(_load_yfinance_closes, "SPY", "3mo")
        ticker_hist, etf_hist, spy_hist = await asyncio.gather(
            ticker_hist_task,
            etf_hist_task,
            spy_hist_task,
        )

        sector_ret_5d = _pct_change(etf_hist, 5)
        sector_ret_20d = _pct_change(etf_hist, 20)
        spy_ret_5d = _pct_change(spy_hist, 5)
        spy_ret_20d = _pct_change(spy_hist, 20)
        ticker_ret_20d = _pct_change(ticker_hist, 20)

        if sector_ret_5d is not None and spy_ret_5d is not None:
            signals["sector_rs_5d"] = sector_ret_5d - spy_ret_5d
        if sector_ret_20d is not None and spy_ret_20d is not None:
            signals["sector_rs_20d"] = sector_ret_20d - spy_ret_20d
        if sector_ret_20d is not None and ticker_ret_20d is not None:
            signals["idiosyncratic_alpha_20d"] = ticker_ret_20d - sector_ret_20d

        if signals["sector_rs_5d"] is not None and signals["sector_rs_20d"] is not None:
            signals["sector_flow_score"] = (signals["sector_rs_5d"] + signals["sector_rs_20d"]) / 2.0

        if len(ticker_hist) >= 21 and len(etf_hist) >= 21:
            ticker_returns = [
                (ticker_hist[idx] - ticker_hist[idx - 1]) / ticker_hist[idx - 1]
                for idx in range(len(ticker_hist) - 19, len(ticker_hist))
                if ticker_hist[idx - 1] != 0
            ]
            etf_returns = [
                (etf_hist[idx] - etf_hist[idx - 1]) / etf_hist[idx - 1]
                for idx in range(len(etf_hist) - 19, len(etf_hist))
                if etf_hist[idx - 1] != 0
            ]
            if len(ticker_returns) == len(etf_returns):
                signals["ticker_sector_corr_20d"] = _safe_corr(ticker_returns, etf_returns)
    except Exception as exc:
        logger.warning("Free sector signal fetch failed for %s: %s", ticker, exc)

    return signals