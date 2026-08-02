"""
Portfolio Management Service
============================
Computes deterministic portfolio scoring (0-100 composite) and optimization
advisories for paper-trading positions. Outputs are advisory-only.
"""

from __future__ import annotations

import asyncio
import copy
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.market_data.finnhub import FinnhubClient
from app.db.models import DailyScan, FactorLog, Position, PositionStatus, StockUniverse
from app.db.schemas import (
    PortfolioActionSchema,
    PortfolioComponentScoreSchema,
    PortfolioOptimizationResponseSchema,
    PortfolioScoreResponseSchema,
)


DEFAULT_WEIGHTS: dict[str, float] = {
    "concentration": 0.15,
    "risk_adjusted_return": 0.15,
    "diversification": 0.12,
    "drawdown": 0.12,
    "greeks": 0.12,
    "liquidity": 0.10,
    "conviction": 0.12,
    "tax_efficiency": 0.12,
}

SINGLE_NAME_CAP = 0.10
SECTOR_CAP = 0.30
CORR_TRIGGER = 0.75


_weekly_optimization_cache: dict[tuple[int, str], PortfolioOptimizationResponseSchema] = {}
_weekly_optimization_cache_lock = asyncio.Lock()


@dataclass
class PositionSnapshot:
    position: Position
    current_price: float
    market_value: float
    weight: float
    sector: str


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _resolve_weights(custom_weights: Optional[dict[str, float]] = None) -> dict[str, float]:
    settings = get_settings()
    configured = {
        "concentration": float(settings.app.portfolio_weight_concentration),
        "risk_adjusted_return": float(settings.app.portfolio_weight_risk_adjusted_return),
        "diversification": float(settings.app.portfolio_weight_diversification),
        "drawdown": float(settings.app.portfolio_weight_drawdown),
        "greeks": float(settings.app.portfolio_weight_greeks),
        "liquidity": float(settings.app.portfolio_weight_liquidity),
        "conviction": float(settings.app.portfolio_weight_conviction),
        "tax_efficiency": float(settings.app.portfolio_weight_tax_efficiency),
    }

    weights = dict(configured)
    if custom_weights:
        for key, value in custom_weights.items():
            if key not in weights:
                raise ValueError(f"Unknown portfolio weight key: {key}")
            weights[key] = float(value)

    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Portfolio weight sum must be > 0")

    if abs(total - 1.0) > 1e-6:
        raise ValueError(f"Portfolio weights must sum to 1.0; got {total:.6f}")

    if any(v < 0 for v in weights.values()):
        raise ValueError("Portfolio weights cannot be negative")

    return weights


def _score_band(score: Optional[float]) -> str:
    if score is None:
        return "DATA_NOT_AVAILABLE"
    if score >= 85:
        return "WELL_OPTIMIZED"
    if score >= 70:
        return "HEALTHY_WITH_FLAGS"
    if score >= 50:
        return "NEEDS_REBALANCING"
    return "URGENT"


def _parse_option_symbol(symbol: str) -> Optional[dict[str, Any]]:
    # OCC format: AAPL250117C00150000
    m = re.match(r"^([A-Z]{1,6})(\d{6})([CP])(\d{8})$", symbol or "")
    if not m:
        return None
    root, yymmdd, cp, strike_raw = m.groups()
    try:
        expiry = datetime.strptime(yymmdd, "%y%m%d").date()
        strike = int(strike_raw) / 1000.0
    except ValueError:
        return None
    return {
        "underlying": root,
        "expiry": expiry,
        "type": cp,
        "strike": strike,
        "contract_symbol": symbol,
    }


def _has_near_term_catalyst(scan_payload: dict[str, Any]) -> bool:
    """Detect near-term catalyst signals from stored dual-horizon scan payload."""
    if not isinstance(scan_payload, dict):
        return False

    dual = scan_payload.get("dual_horizon", {})
    tactical = dual.get("tactical", {}) if isinstance(dual, dict) else {}
    catalyst_signals = tactical.get("catalyst_signals", []) if isinstance(tactical, dict) else []
    if isinstance(catalyst_signals, list) and len(catalyst_signals) > 0:
        return True

    market_data = scan_payload.get("market_data", {})
    if isinstance(market_data, dict) and bool(market_data.get("has_earnings_today", False)):
        return True

    return False


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _black_scholes_greeks(
    s: float,
    k: float,
    t: float,
    r: float,
    sigma: float,
    option_type: str,
) -> tuple[float, float, float]:
    if s <= 0 or k <= 0 or t <= 0 or sigma <= 0:
        raise ValueError("Invalid Black-Scholes inputs")
    d1 = (math.log(s / k) + (r + 0.5 * sigma * sigma) * t) / (sigma * math.sqrt(t))
    d2 = d1 - sigma * math.sqrt(t)
    nd1 = (1.0 / math.sqrt(2.0 * math.pi)) * math.exp(-0.5 * d1 * d1)

    if option_type == "C":
        delta = _norm_cdf(d1)
        theta = (-(s * nd1 * sigma) / (2 * math.sqrt(t)) - r * k * math.exp(-r * t) * _norm_cdf(d2)) / 365.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (-(s * nd1 * sigma) / (2 * math.sqrt(t)) + r * k * math.exp(-r * t) * _norm_cdf(-d2)) / 365.0
    vega = s * nd1 * math.sqrt(t) / 100.0
    return delta, theta, vega


async def _fetch_yf_history(symbols: list[str], period: str = "6mo") -> dict[str, pd.Series]:
    def _load() -> dict[str, pd.Series]:
        import yfinance as yf

        out: dict[str, pd.Series] = {}
        for s in symbols:
            try:
                df = yf.Ticker(s).history(period=period)
                if df is not None and not df.empty and "Close" in df.columns:
                    out[s] = df["Close"].astype(float)
            except Exception:
                continue
        return out

    return await asyncio.to_thread(_load)


async def _get_position_snapshots(session: AsyncSession, user_id: int) -> tuple[list[PositionSnapshot], float]:
    rows = (
        await session.execute(
            select(Position)
            .where(Position.status == PositionStatus.OPEN, Position.user_id == user_id)
            .order_by(Position.opened_at.desc())
        )
    ).scalars().all()
    if not rows:
        return [], 0.0

    symbols = sorted({p.symbol.upper() for p in rows})

    client = FinnhubClient()
    price_map: dict[str, float] = {}
    try:
        quotes = await client.get_quotes_batch(symbols, session=session)
        for q in quotes:
            if q.current_price > 0:
                price_map[q.ticker.upper()] = q.current_price
    finally:
        await client.close()

    univ = (
        await session.execute(select(StockUniverse.ticker, StockUniverse.sector).where(StockUniverse.ticker.in_(symbols)))
    ).all()
    sector_map = {str(r.ticker).upper(): (r.sector or "Unknown") for r in univ}

    # Missing live prices are explicit failure points for score reliability.
    missing = [s for s in symbols if s not in price_map and _parse_option_symbol(s) is None]
    if missing:
        raise ValueError(f"Live quote unavailable for symbols: {', '.join(missing)}")

    provisional: list[tuple[Position, float, float, str]] = []
    total_value = 0.0
    for p in rows:
        sym = p.symbol.upper()
        opt = _parse_option_symbol(sym)
        if opt:
            # For option symbols, derive current mark via underlying approximation when direct quote is unavailable.
            # This keeps the pipeline deterministic while preserving explicit model assumptions.
            under = opt["underlying"]
            under_px = price_map.get(under)
            if under_px is None:
                continue
            current_price = p.entry_price
        else:
            current_price = price_map[sym]
        mv = max(0.0, float(p.qty) * float(current_price))
        provisional.append((p, current_price, mv, sector_map.get(sym, "Unknown")))
        total_value += mv

    if total_value <= 0:
        raise ValueError("Total portfolio market value is zero; cannot score portfolio")

    snapshots: list[PositionSnapshot] = []
    for p, px, mv, sector in provisional:
        snapshots.append(
            PositionSnapshot(
                position=p,
                current_price=px,
                market_value=mv,
                weight=mv / total_value,
                sector=sector,
            )
        )

    return snapshots, total_value


async def _get_conviction_scores(session: AsyncSession, symbols: list[str]) -> dict[str, float]:
    conv: dict[str, float] = {}
    for sym in symbols:
        stmt = (
            select(DailyScan)
            .where(DailyScan.ticker == sym)
            .order_by(DailyScan.scan_date.desc(), DailyScan.id.desc())
            .limit(1)
        )
        scan = (await session.execute(stmt)).scalar_one_or_none()
        if not scan:
            continue
        payload = scan.factor_results_json if isinstance(scan.factor_results_json, dict) else {}
        dual = payload.get("dual_horizon", {}) if isinstance(payload, dict) else {}
        tactical = dual.get("tactical", {}) if isinstance(dual, dict) else {}
        score = tactical.get("score") if isinstance(tactical, dict) else None
        if isinstance(score, (int, float)):
            conv[sym] = float(score)
        else:
            conv[sym] = float(scan.score)
    return conv


async def _get_latest_scan_payloads(session: AsyncSession, symbols: list[str]) -> dict[str, dict[str, Any]]:
    payloads: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        payload = (
            await session.execute(
                select(DailyScan.factor_results_json)
                .where(DailyScan.ticker == sym)
                .order_by(DailyScan.scan_date.desc(), DailyScan.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        payloads[sym] = payload if isinstance(payload, dict) else {}
    return payloads


async def _get_option_chain_liquidity(contract_symbol: str) -> Optional[dict[str, Any]]:
    """Load live option-chain row metrics (OI/volume) for a held OCC option symbol."""
    parsed = _parse_option_symbol(contract_symbol)
    if not parsed:
        return None

    def _load() -> Optional[dict[str, Any]]:
        import yfinance as yf

        ticker = parsed["underlying"]
        expiry = parsed["expiry"].isoformat()
        strike = float(parsed["strike"])
        cp = parsed["type"]

        chain = yf.Ticker(ticker).option_chain(expiry)
        df = chain.calls if cp == "C" else chain.puts
        if df is None or df.empty or "strike" not in df.columns:
            return None

        row = df.loc[(df["strike"] - strike).abs().idxmin()]
        oi = int(row.get("openInterest") or 0)
        volume = int(row.get("volume") or 0)
        bid = float(row.get("bid") or 0.0)
        ask = float(row.get("ask") or 0.0)
        return {
            "open_interest": oi,
            "volume": volume,
            "bid": bid,
            "ask": ask,
        }

    try:
        return await asyncio.to_thread(_load)
    except Exception:
        return None


async def get_portfolio_score(
    session: AsyncSession,
    user_id: int,
    custom_weights: Optional[dict[str, float]] = None,
) -> PortfolioScoreResponseSchema:
    as_of = datetime.now(timezone.utc).isoformat()
    weights = _resolve_weights(custom_weights)

    snapshots, total_value = await _get_position_snapshots(session, user_id)
    if not snapshots:
        return PortfolioScoreResponseSchema(
            asOf=as_of,
            compositeScore=None,
            band="DATA_NOT_AVAILABLE",
            components=[],
            missingComponents=["No open positions"],
            metrics={},
        )

    symbols = [s.position.symbol.upper() for s in snapshots]
    sectors = [s.sector for s in snapshots]

    components: list[PortfolioComponentScoreSchema] = []
    missing_components: list[str] = []
    metrics: dict[str, Any] = {}

    # 1) Concentration Risk
    max_weight = max(s.weight for s in snapshots)
    sector_weights: dict[str, float] = {}
    for s in snapshots:
        sector_weights[s.sector] = sector_weights.get(s.sector, 0.0) + s.weight
    max_sector_weight = max(sector_weights.values()) if sector_weights else 0.0
    single_over = max(0.0, max_weight - SINGLE_NAME_CAP)
    sector_over = max(0.0, max_sector_weight - SECTOR_CAP)
    conc_penalty = (single_over * 500.0) + (sector_over * 250.0)
    concentration_score = _clamp(100.0 - conc_penalty)
    components.append(
        PortfolioComponentScoreSchema(
            name="Concentration Risk",
            weight=weights["concentration"],
            score=round(concentration_score, 1),
            status="OK",
            detail="Penalizes single-name >10% and sector >30% overweight.",
        )
    )
    metrics["max_single_weight"] = round(max_weight, 4)
    metrics["max_sector_weight"] = round(max_sector_weight, 4)

    # Build price history for return/corr/drawdown/liquidity
    unique_symbols = sorted({s.position.symbol.upper() for s in snapshots if _parse_option_symbol(s.position.symbol.upper()) is None})
    history = await _fetch_yf_history(unique_symbols, period="1y")

    # 2) Risk-Adjusted Return
    risk_score: Optional[float] = None
    portfolio_returns = None
    if history:
        frames = []
        for sym in unique_symbols:
            series = history.get(sym)
            if series is None or series.empty:
                continue
            frames.append(series.rename(sym))
        if frames:
            px_df = pd.concat(frames, axis=1).dropna(how="all")
            ret_df = px_df.pct_change().dropna(how="all")
            if not ret_df.empty:
                w_map = {s.position.symbol.upper(): s.weight for s in snapshots if s.position.symbol.upper() in ret_df.columns}
                w = np.array([w_map.get(c, 0.0) for c in ret_df.columns], dtype=float)
                if w.sum() > 0:
                    w = w / w.sum()
                    portfolio_returns = ret_df.fillna(0.0).values @ w
                    window = portfolio_returns[-90:] if len(portfolio_returns) >= 30 else portfolio_returns
                    if len(window) >= 10:
                        mean_daily = float(np.mean(window))
                        std_daily = float(np.std(window, ddof=1)) if len(window) > 1 else 0.0
                        downside = np.array([r for r in window if r < 0.0], dtype=float)
                        downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
                        sharpe = (mean_daily / std_daily) * math.sqrt(252.0) if std_daily > 0 else 0.0
                        sortino = (mean_daily / downside_std) * math.sqrt(252.0) if downside_std > 0 else 0.0
                        sharpe_score = _clamp(50.0 + (sharpe / 1.5) * 50.0)
                        sortino_score = _clamp(50.0 + (sortino / 2.0) * 50.0)
                        risk_score = _clamp((sharpe_score + sortino_score) / 2.0)
                        metrics["sharpe_90d"] = round(sharpe, 3)
                        metrics["sortino_90d"] = round(sortino, 3)
    if risk_score is None:
        missing_components.append("Risk-Adjusted Return")
        components.append(
            PortfolioComponentScoreSchema(
                name="Risk-Adjusted Return",
                weight=weights["risk_adjusted_return"],
                score=None,
                status="DATA_NOT_AVAILABLE",
                detail="Insufficient 90-day return history across holdings.",
            )
        )
    else:
        components.append(
            PortfolioComponentScoreSchema(
                name="Risk-Adjusted Return",
                weight=weights["risk_adjusted_return"],
                score=round(risk_score, 1),
                status="OK",
                detail="Sharpe/Sortino normalized to score band.",
            )
        )

    # 3) Diversification / Correlation
    diversification_score: Optional[float] = None
    avg_corr = None
    if history and len(unique_symbols) >= 2:
        frames = [history[s].rename(s) for s in unique_symbols if s in history and not history[s].empty]
        if len(frames) >= 2:
            ret_df = pd.concat(frames, axis=1).pct_change().dropna(how="all")
            ret_60 = ret_df.tail(60)
            if ret_60.shape[0] >= 20 and ret_60.shape[1] >= 2:
                corr = ret_60.corr()
                upper_vals = corr.values[np.triu_indices_from(corr.values, k=1)]
                upper_vals = upper_vals[~np.isnan(upper_vals)]
                if len(upper_vals) > 0:
                    avg_corr = float(np.nanmean(upper_vals))
                    diversification_score = _clamp(100.0 - (avg_corr * 100.0))
    if diversification_score is None:
        missing_components.append("Diversification/Correlation")
        components.append(
            PortfolioComponentScoreSchema(
                name="Diversification/Correlation",
                weight=weights["diversification"],
                score=None,
                status="DATA_NOT_AVAILABLE",
                detail="Insufficient cross-holding return history for 60-day correlation.",
            )
        )
    else:
        metrics["avg_pairwise_corr_60d"] = round(avg_corr, 4) if avg_corr is not None else None
        components.append(
            PortfolioComponentScoreSchema(
                name="Diversification/Correlation",
                weight=weights["diversification"],
                score=round(diversification_score, 1),
                status="OK",
                detail="Average pairwise correlation penalty across holdings.",
            )
        )

    # 4) Drawdown Exposure
    drawdown_score: Optional[float] = None
    if portfolio_returns is not None and len(portfolio_returns) >= 20:
        series = pd.Series(portfolio_returns)
        equity_curve = (1.0 + series).cumprod()
        running_max = equity_curve.cummax()
        dd = (equity_curve / running_max) - 1.0
        current_dd = abs(float(dd.iloc[-1]))
        max_dd = abs(float(dd.min()))
        drawdown_score = _clamp(100.0 - ((current_dd * 120.0) + (max_dd * 100.0)))
        metrics["current_drawdown"] = round(current_dd, 4)
        metrics["max_drawdown_1y"] = round(max_dd, 4)
    if drawdown_score is None:
        missing_components.append("Drawdown Exposure")
        components.append(
            PortfolioComponentScoreSchema(
                name="Drawdown Exposure",
                weight=weights["drawdown"],
                score=None,
                status="DATA_NOT_AVAILABLE",
                detail="Insufficient portfolio return history for drawdown metrics.",
            )
        )
    else:
        components.append(
            PortfolioComponentScoreSchema(
                name="Drawdown Exposure",
                weight=weights["drawdown"],
                score=round(drawdown_score, 1),
                status="OK",
                detail="Penalizes current and historical drawdown severity.",
            )
        )

    # 5) Options Greek Exposure
    net_delta_notional = 0.0
    net_theta_daily = 0.0
    net_vega = 0.0
    greek_data_missing = False

    for snap in snapshots:
        sym = snap.position.symbol.upper()
        opt = _parse_option_symbol(sym)
        qty = float(snap.position.qty)
        if not opt:
            net_delta_notional += snap.current_price * qty
            continue

        # Attempt model-based Greeks for option symbols only.
        try:
            under = opt["underlying"]
            under_series = history.get(under)
            if under_series is None or under_series.empty:
                greek_data_missing = True
                continue
            s = float(under_series.iloc[-1])
            t_days = max(1, (opt["expiry"] - datetime.now(timezone.utc).date()).days)
            t = t_days / 365.0
            daily_ret = under_series.pct_change().dropna()
            if daily_ret.empty:
                greek_data_missing = True
                continue
            sigma = float(daily_ret.std(ddof=1) * math.sqrt(252.0))
            delta, theta, vega = _black_scholes_greeks(s, opt["strike"], t, 0.04, sigma, opt["type"])
            mult = 100.0
            net_delta_notional += delta * s * qty * mult
            net_theta_daily += theta * qty * mult
            net_vega += vega * qty * mult
        except Exception:
            greek_data_missing = True

    delta_ratio = abs(net_delta_notional) / total_value if total_value > 0 else 0.0
    theta_ratio = abs(net_theta_daily) / total_value if total_value > 0 else 0.0
    vega_ratio = abs(net_vega) / total_value if total_value > 0 else 0.0

    delta_over = max(0.0, delta_ratio - 0.65)
    theta_over = max(0.0, theta_ratio - 0.002)
    vega_over = max(0.0, vega_ratio - 0.015)
    greek_score = _clamp(100.0 - (delta_over * 160.0 + theta_over * 7000.0 + vega_over * 1800.0))

    components.append(
        PortfolioComponentScoreSchema(
            name="Options Greek Exposure",
            weight=weights["greeks"],
            score=round(greek_score, 1),
            status="OK" if not greek_data_missing else "PARTIAL",
            detail="Net delta/theta/vega concentration vs risk bands.",
        )
    )
    metrics["net_delta_ratio"] = round(delta_ratio, 4)
    metrics["net_theta_ratio_daily"] = round(theta_ratio, 5)
    metrics["net_vega_ratio"] = round(vega_ratio, 5)

    # 6) Liquidity Score
    liquid_notional = 0.0
    option_liquid_notional = 0.0
    option_illiquid_count = 0
    option_liquid_count = 0
    for snap in snapshots:
        sym = snap.position.symbol.upper()
        if _parse_option_symbol(sym):
            chain = await _get_option_chain_liquidity(sym)
            if chain is None:
                option_illiquid_count += 1
                continue
            contracts = abs(float(snap.position.qty))
            oi = float(chain.get("open_interest") or 0.0)
            vol = float(chain.get("volume") or 0.0)
            if oi > 0 and vol > 0 and contracts <= (oi * 0.20):
                option_liquid_notional += snap.market_value
                option_liquid_count += 1
            else:
                option_illiquid_count += 1
            continue
        h = history.get(sym)
        if h is None or h.empty:
            continue

        # Reload volume/close for ADV estimate.
        def _adv_load(symbol: str) -> tuple[float, float]:
            import yfinance as yf

            df = yf.Ticker(symbol).history(period="3mo")
            if df is None or df.empty or "Volume" not in df.columns or "Close" not in df.columns:
                return 0.0, 0.0
            adv = float(df["Volume"].tail(20).mean())
            px = float(df["Close"].iloc[-1])
            return adv, px

        adv, px = await asyncio.to_thread(_adv_load, sym)
        if adv <= 0 or px <= 0:
            continue

        position_shares = abs(float(snap.position.qty))
        days_to_exit = position_shares / max(1.0, adv * 0.1)
        slippage_proxy = min(0.05, (position_shares / max(1.0, adv * 0.25)) * 0.02)
        if days_to_exit <= 1.0 and slippage_proxy < 0.02:
            liquid_notional += snap.market_value

    liquidity_numerator = liquid_notional + option_liquid_notional
    liquidity_score = _clamp((liquidity_numerator / total_value) * 100.0 if total_value > 0 else 0.0)
    components.append(
        PortfolioComponentScoreSchema(
            name="Liquidity Score",
            weight=weights["liquidity"],
            score=round(liquidity_score, 1),
            status="OK",
            detail="Percent of book that can be exited within 1 day under slippage threshold.",
        )
    )
    metrics["option_liquid_positions"] = option_liquid_count
    metrics["option_illiquid_positions"] = option_illiquid_count

    # 7) Conviction Alignment
    conv_map = await _get_conviction_scores(session, symbols)

    def _max_weight_for_conviction(score: Optional[float]) -> float:
        if score is None:
            return 0.06
        if score >= 8.0:
            return 0.10
        if score >= 7.0:
            return 0.08
        if score >= 6.5:
            return 0.05
        return 0.03

    penalties = []
    for snap in snapshots:
        c = conv_map.get(snap.position.symbol.upper())
        max_w = _max_weight_for_conviction(c)
        penalties.append(max(0.0, snap.weight - max_w))
    conviction_score = _clamp(100.0 - (sum(penalties) * 800.0))
    components.append(
        PortfolioComponentScoreSchema(
            name="Conviction Alignment",
            weight=weights["conviction"],
            score=round(conviction_score, 1),
            status="OK",
            detail="Penalizes oversized positions relative to scan-derived conviction tiers.",
        )
    )

    # 8) Tax Efficiency
    short_term_gain = 0.0
    long_term_gain = 0.0
    unharvested_loss = 0.0
    now = datetime.now(timezone.utc)

    latest_scans = await _get_latest_scan_payloads(session, symbols)

    for snap in snapshots:
        p = snap.position
        pnl = (snap.current_price - float(p.entry_price)) * float(p.qty)
        hold_days = (now - p.opened_at).days if p.opened_at else 0

        if pnl > 0:
            if hold_days >= 365:
                long_term_gain += pnl
            else:
                short_term_gain += pnl
        elif pnl < 0:
            payload = latest_scans.get(p.symbol.upper())
            has_near_catalyst = _has_near_term_catalyst(payload)
            if hold_days > 30 and not has_near_catalyst:
                unharvested_loss += abs(pnl)

    loss_penalty = (unharvested_loss / total_value) * 60.0 if total_value > 0 else 0.0
    gain_mix_penalty = 0.0
    total_gains = short_term_gain + long_term_gain
    if total_gains > 0:
        short_ratio = short_term_gain / total_gains
        gain_mix_penalty = short_ratio * 30.0
    tax_eff_score = _clamp(100.0 - loss_penalty - gain_mix_penalty)

    components.append(
        PortfolioComponentScoreSchema(
            name="Tax Efficiency",
            weight=weights["tax_efficiency"],
            score=round(tax_eff_score, 1),
            status="OK",
            detail="Penalizes unharvested eligible losses and short-term-gain-heavy mix.",
        )
    )

    available = [c for c in components if c.score is not None]
    if not available:
        composite = None
    else:
        weighted = sum(float(c.score) * c.weight for c in available)
        weight_sum = sum(c.weight for c in available)
        composite = round(weighted / weight_sum, 1) if weight_sum > 0 else None

    return PortfolioScoreResponseSchema(
        asOf=as_of,
        compositeScore=composite,
        band=_score_band(composite),
        components=components,
        missingComponents=missing_components,
        metrics=metrics,
    )


async def get_portfolio_optimization(
    session: AsyncSession,
    user_id: int,
    cadence: str = "weekly",
    custom_weights: Optional[dict[str, float]] = None,
) -> PortfolioOptimizationResponseSchema:
    cadence_normalized = (cadence or "weekly").strip().lower()
    if cadence_normalized not in {"weekly", "regime_shift"}:
        cadence_normalized = "weekly"

    week_key = datetime.now(timezone.utc).strftime("%G-W%V")
    cache_key = (int(user_id), week_key)

    if cadence_normalized == "weekly":
        async with _weekly_optimization_cache_lock:
            cached = _weekly_optimization_cache.get(cache_key)
            if cached is not None:
                return copy.deepcopy(cached)

    score = await get_portfolio_score(session, user_id, custom_weights=custom_weights)

    snapshots, total_value = await _get_position_snapshots(session, user_id)
    symbols = [s.position.symbol.upper() for s in snapshots]
    conv_map = await _get_conviction_scores(session, symbols)
    latest_scan_payloads = await _get_latest_scan_payloads(session, symbols)

    actions: list[PortfolioActionSchema] = []
    triggered_steps: list[str] = []

    sector_weights: dict[str, float] = {}
    for s in snapshots:
        sector_weights[s.sector] = sector_weights.get(s.sector, 0.0) + s.weight

    # Step 1: Concentration rebalance
    over_single = [s for s in snapshots if s.weight > SINGLE_NAME_CAP]
    over_sector = {k: v for k, v in sector_weights.items() if v > SECTOR_CAP}
    if over_single or over_sector:
        triggered_steps.append("STEP_1_CONCENTRATION_REBALANCE")
        ranked = sorted(
            over_single,
            key=lambda x: (conv_map.get(x.position.symbol.upper(), 5.0), -(x.weight - SINGLE_NAME_CAP)),
        )
        for idx, snap in enumerate(ranked[:5], start=1):
            actions.append(
                PortfolioActionSchema(
                    priority=idx,
                    action="TRIM",
                    symbol=snap.position.symbol.upper(),
                    trigger="single_name_over_10pct",
                    reason="Overweight position exceeds concentration cap; trim weakest-conviction overweight first.",
                    metrics={
                        "weight": round(snap.weight, 4),
                        "cap": SINGLE_NAME_CAP,
                        "conviction": round(conv_map.get(snap.position.symbol.upper(), 5.0), 2),
                    },
                )
            )

    # Step 2: Correlation de-clustering
    history = await _fetch_yf_history([s for s in symbols if _parse_option_symbol(s) is None], period="6mo")
    if history and len(history) >= 2:
        frame = pd.concat([v.rename(k) for k, v in history.items() if not v.empty], axis=1).pct_change().dropna(how="all")
        top5 = sorted(snapshots, key=lambda x: x.weight, reverse=True)[:5]
        top_syms: list[str] = []
        for s in top5:
            sym = s.position.symbol.upper()
            if sym in frame.columns and sym not in top_syms:
                top_syms.append(sym)
        if len(top_syms) >= 2:
            corr = frame[top_syms].tail(60).corr().fillna(0.0)
            upper = corr.values[np.triu_indices_from(corr.values, k=1)]
            upper = upper[~np.isnan(upper)]
            if len(upper) > 0 and float(np.mean(upper)) > CORR_TRIGGER:
                triggered_steps.append("STEP_2_CORRELATION_DECLUSTER")
                weakest = min(top5, key=lambda x: conv_map.get(x.position.symbol.upper(), 5.0))
                actions.append(
                    PortfolioActionSchema(
                        priority=20,
                        action="TRIM_ROTATE",
                        symbol=weakest.position.symbol.upper(),
                        trigger="top5_avg_corr_gt_0_75",
                        reason="Top holding cluster is highly correlated; rotate weakest-conviction name toward underweight sector exposure.",
                        metrics={"top5_avg_corr": round(float(np.mean(upper)), 4)},
                    )
                )

                # Generate a concrete replacement candidate from latest scan universe
                dominant_sector = max(sector_weights.items(), key=lambda kv: kv[1])[0] if sector_weights else "Unknown"
                latest_scan_date = await session.scalar(select(func.max(DailyScan.scan_date)))
                if latest_scan_date is not None:
                    scan_rows = (
                        await session.execute(
                            select(DailyScan.ticker, DailyScan.score)
                            .where(DailyScan.scan_date == latest_scan_date)
                            .order_by(DailyScan.score.desc())
                            .limit(200)
                        )
                    ).all()
                    candidate_tickers = [str(r.ticker).upper() for r in scan_rows if str(r.ticker).upper() not in set(symbols)]
                    if candidate_tickers:
                        sectors_rows = (
                            await session.execute(
                                select(StockUniverse.ticker, StockUniverse.sector)
                                .where(StockUniverse.ticker.in_(candidate_tickers))
                            )
                        ).all()
                        sector_map = {str(r.ticker).upper(): (r.sector or "Unknown") for r in sectors_rows}
                        filtered = [t for t in candidate_tickers if sector_map.get(t, "Unknown") != dominant_sector]
                        if filtered and top_syms:
                            candidate_history = await _fetch_yf_history(filtered[:40], period="6mo")
                            best_candidate = None
                            best_corr = None
                            scan_score_map = {str(r.ticker).upper(): float(r.score) for r in scan_rows}
                            for ticker in filtered:
                                series = candidate_history.get(ticker)
                                if series is None or series.empty:
                                    continue
                                correlations = []
                                for held_sym in top_syms:
                                    held_series = history.get(held_sym)
                                    if held_series is None or held_series.empty:
                                        continue
                                    aligned = pd.concat([series.rename("a"), held_series.rename("b")], axis=1).dropna()
                                    if aligned.shape[0] < 20:
                                        continue
                                    c = float(aligned["a"].pct_change().corr(aligned["b"].pct_change()))
                                    if not math.isnan(c):
                                        correlations.append(abs(c))
                                if not correlations:
                                    continue
                                avg_abs_corr = float(np.mean(correlations))
                                if avg_abs_corr <= 0.35:
                                    if best_candidate is None or avg_abs_corr < float(best_corr):
                                        best_candidate = ticker
                                        best_corr = avg_abs_corr

                            if best_candidate is not None and best_corr is not None:
                                actions.append(
                                    PortfolioActionSchema(
                                        priority=21,
                                        action="ROTATE_IN",
                                        symbol=best_candidate,
                                        trigger="uncorrelated_replacement_candidate",
                                        reason="Concrete replacement candidate selected from latest scan universe to reduce cluster correlation.",
                                        metrics={
                                            "replace_symbol": weakest.position.symbol.upper(),
                                            "candidate_sector": sector_map.get(best_candidate, "Unknown"),
                                            "candidate_score": round(scan_score_map.get(best_candidate, 0.0), 2),
                                            "avg_abs_corr_to_top5": round(float(best_corr), 4),
                                        },
                                    )
                                )

    # Step 3: Tax-loss harvest pass
    now = datetime.now(timezone.utc)
    for snap in snapshots:
        hold_days = (now - snap.position.opened_at).days if snap.position.opened_at else 0
        pnl = (snap.current_price - float(snap.position.entry_price)) * float(snap.position.qty)
        scan_payload = latest_scan_payloads.get(snap.position.symbol.upper(), {})
        has_near_catalyst = _has_near_term_catalyst(scan_payload)
        if hold_days > 30 and pnl < 0 and not has_near_catalyst:
            triggered_steps.append("STEP_3_TAX_LOSS_HARVEST")
            actions.append(
                PortfolioActionSchema(
                    priority=30,
                    action="HARVEST",
                    symbol=snap.position.symbol.upper(),
                    trigger="loss_gt_30d_no_near_catalyst",
                    reason="Harvest eligible loss and redeploy into non-substantially-identical thesis peer.",
                    metrics={
                        "hold_days": hold_days,
                        "unrealized_pnl": round(pnl, 2),
                        "near_term_catalyst": False,
                    },
                )
            )

    # Step 4: Greek rebalance
    net_delta_ratio = float(score.metrics.get("net_delta_ratio", 0.0)) if score.metrics else 0.0
    net_vega_ratio = float(score.metrics.get("net_vega_ratio", 0.0)) if score.metrics else 0.0
    if net_delta_ratio > 0.65 or net_vega_ratio > 0.015:
        triggered_steps.append("STEP_4_GREEK_REBALANCE")
        actions.append(
            PortfolioActionSchema(
                priority=40,
                action="HEDGE",
                symbol=None,
                trigger="greek_band_exceeded",
                reason="Net delta/vega concentration exceeds comfort bands; apply hedge rather than full de-risk to preserve thesis exposure.",
                metrics={"net_delta_ratio": round(net_delta_ratio, 4), "net_vega_ratio": round(net_vega_ratio, 5)},
            )
        )

    # Step 5: Conviction-sizing correction
    for snap in snapshots:
        c = conv_map.get(snap.position.symbol.upper(), 5.0)
        cap = 0.10 if c >= 8.0 else (0.08 if c >= 7.0 else (0.05 if c >= 6.5 else 0.03))
        if snap.weight > cap:
            triggered_steps.append("STEP_5_CONVICTION_SIZING_CORRECTION")
            actions.append(
                PortfolioActionSchema(
                    priority=50,
                    action="RIGHT_SIZE",
                    symbol=snap.position.symbol.upper(),
                    trigger="position_weight_vs_conviction_cap",
                    reason="Position size exceeds conviction-tier cap.",
                    metrics={"weight": round(snap.weight, 4), "conviction": round(c, 2), "cap": cap},
                )
            )

    # Step 6: Liquidity sweep
    if score.components:
        liq = next((c for c in score.components if c.name == "Liquidity Score"), None)
        if liq and liq.score is not None and liq.score < 70:
            triggered_steps.append("STEP_6_LIQUIDITY_SWEEP")
            actions.append(
                PortfolioActionSchema(
                    priority=60,
                    action="SCALE_OUT",
                    symbol=None,
                    trigger="liquidity_score_below_70",
                    reason="Book contains positions with limited 1-day exit capacity; use staged scale-out.",
                    metrics={"liquidity_score": liq.score},
                )
            )

    # Options-specific OI / one-day exit check for held OCC contracts
    option_liquidity_flags: list[dict[str, Any]] = []
    for snap in snapshots:
        symbol = snap.position.symbol.upper()
        if not _parse_option_symbol(symbol):
            continue
        chain = await _get_option_chain_liquidity(symbol)
        if chain is None:
            continue
        contracts = abs(float(snap.position.qty))
        oi = float(chain.get("open_interest") or 0.0)
        vol = float(chain.get("volume") or 0.0)
        # One-day liquidity threshold: position should be <= 20% of OI and have non-zero volume.
        if oi <= 0 or vol <= 0 or contracts > (oi * 0.20):
            option_liquidity_flags.append(
                {
                    "symbol": symbol,
                    "contracts": contracts,
                    "open_interest": oi,
                    "volume": vol,
                }
            )

    if option_liquidity_flags:
        triggered_steps.append("STEP_6_LIQUIDITY_SWEEP")
        for idx, flag in enumerate(option_liquidity_flags[:5], start=1):
            actions.append(
                PortfolioActionSchema(
                    priority=61 + idx,
                    action="SCALE_OUT",
                    symbol=str(flag["symbol"]),
                    trigger="option_oi_volume_one_day_exit_failed",
                    reason="Option position size exceeds one-day OI/volume liquidity bounds; stage exits to reduce slippage risk.",
                    metrics={
                        "contracts": round(float(flag["contracts"]), 2),
                        "open_interest": int(flag["open_interest"]),
                        "volume": int(flag["volume"]),
                        "max_one_day_contracts": round(float(flag["open_interest"]) * 0.20, 2),
                    },
                )
            )

    # Step 7: Macro regime hard caps from F45/F49/F50
    regime_hit = False
    for sym in symbols:
        scan = (
            await session.execute(
                select(DailyScan.id)
                .where(DailyScan.ticker == sym)
                .order_by(DailyScan.scan_date.desc(), DailyScan.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if scan is None:
            continue
        trig = (
            await session.execute(
                select(FactorLog.factor_id).where(FactorLog.scan_id == scan, FactorLog.factor_id.in_(["F45", "F49", "F50"]), FactorLog.triggered == True)
            )
        ).all()
        if trig:
            regime_hit = True
            break

    if regime_hit:
        triggered_steps.append("STEP_7_MACRO_REGIME_CAP")
        actions.append(
            PortfolioActionSchema(
                priority=70,
                action="APPLY_CAPS",
                symbol=None,
                trigger="regime_shift_f45_f49_f50",
                reason="Macro regime shift active; enforce hard sizing caps before standard optimizer actions.",
                metrics={},
            )
        )

    # Step 8 output ranking
    actions = sorted(actions, key=lambda a: a.priority)

    acted_symbols = {a.symbol for a in actions if a.symbol}
    hold_priority = 900
    for snap in snapshots:
        symbol = snap.position.symbol.upper()
        if symbol in acted_symbols:
            continue
        actions.append(
            PortfolioActionSchema(
                priority=hold_priority,
                action="HOLD",
                symbol=symbol,
                trigger="no_rebalance_trigger",
                reason="No optimization trigger fired for this holding in the current pass.",
                metrics={
                    "weight": round(snap.weight, 4),
                    "conviction": round(conv_map.get(symbol, 5.0), 2),
                },
            )
        )
        hold_priority += 1

    result = PortfolioOptimizationResponseSchema(
        asOf=datetime.now(timezone.utc).isoformat(),
        cadence=cadence_normalized,
        triggeredSteps=sorted(set(triggered_steps)),
        actions=actions,
        score=score,
    )

    if cadence_normalized == "weekly":
        async with _weekly_optimization_cache_lock:
            _weekly_optimization_cache[cache_key] = copy.deepcopy(result)

    return result
