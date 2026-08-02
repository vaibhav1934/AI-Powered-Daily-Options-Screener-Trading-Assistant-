"""
Framework-aligned F1-F39 definitions.
====================================
These factors map to the canonical 50-factor specification supplied by the user.
When required data inputs are not yet available in ScanContext, factors are
explicitly marked UNCONFIGURED (never silently treated as implemented).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.framework.factors.base import BaseFactor, FactorAction, FactorResult, FactorStatus, ScanContext


Evaluator = Callable[[ScanContext], FactorResult]


class SpecFactor(BaseFactor):
    def __init__(
        self,
        factor_id: str,
        name: str,
        layer: int,
        description: str,
        evaluator: Evaluator | None = None,
    ) -> None:
        self.factor_id = factor_id
        self.name = name
        self.layer = layer
        self.description = description
        self._evaluator = evaluator
        self.status = FactorStatus.LIVE if evaluator is not None else FactorStatus.UNCONFIGURED

    def evaluate(self, ctx: ScanContext) -> FactorResult:
        if self._evaluator is None:
            return FactorResult(
                factor_id=self.factor_id,
                factor_name=self.name,
                layer_number=self.layer,
                status=FactorStatus.UNCONFIGURED,
                triggered=False,
                action=FactorAction.PASS,
                stubbed=True,
                detail=f"{self.name} is defined in the framework but not yet wired to live inputs.",
                metadata={"reason": "missing_live_inputs"},
            )
        return self._evaluator(ctx)


def _unconfigured_result(factor_id: str, factor_name: str, layer: int, detail: str, reason: str) -> FactorResult:
    return FactorResult(
        factor_id=factor_id,
        factor_name=factor_name,
        layer_number=layer,
        status=FactorStatus.UNCONFIGURED,
        triggered=False,
        action=FactorAction.PASS,
        stubbed=True,
        detail=detail,
        metadata={"reason": reason},
    )


def _f06_asian_close(ctx: ScanContext) -> FactorResult:
    if ctx.kospi_change_percent <= -2.0:
        return FactorResult(
            factor_id="F06",
            factor_name="Asian close direction and magnitude",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"KOSPI weak close detected ({ctx.kospi_change_percent:+.2f}%).",
            metadata={"kospi_change_percent": ctx.kospi_change_percent},
        )
    return FactorResult(
        factor_id="F06",
        factor_name="Asian close direction and magnitude",
        layer_number=2,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"KOSPI close not in stress range ({ctx.kospi_change_percent:+.2f}%).",
        metadata={"kospi_change_percent": ctx.kospi_change_percent},
    )


def _f07_europe_followthrough(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.dax_change_percent, (int, float)) or not isinstance(ctx.ftse_change_percent, (int, float)):
        return _unconfigured_result(
            "F07",
            "European open follow-through",
            2,
            "European index inputs missing.",
            "missing_europe_inputs",
        )

    dax = float(ctx.dax_change_percent)
    ftse = float(ctx.ftse_change_percent)
    if dax <= -0.75 and ftse <= -0.75:
        return FactorResult(
            factor_id="F07",
            factor_name="European open follow-through",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"European tape is weak into the US session (DAX {dax:+.2f}%, FTSE {ftse:+.2f}%).",
            metadata={"dax_change_percent": dax, "ftse_change_percent": ftse},
        )
    if dax >= 0.75 and ftse >= 0.50:
        return FactorResult(
            factor_id="F07",
            factor_name="European open follow-through",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"European tape is supportive into the US session (DAX {dax:+.2f}%, FTSE {ftse:+.2f}%).",
            metadata={"dax_change_percent": dax, "ftse_change_percent": ftse},
        )
    return FactorResult(
        factor_id="F07",
        factor_name="European open follow-through",
        layer_number=2,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"European tape is mixed (DAX {dax:+.2f}%, FTSE {ftse:+.2f}%).",
        metadata={"dax_change_percent": dax, "ftse_change_percent": ftse},
    )


def _f10_vix_term_structure(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.vix_spot, (int, float)) or not isinstance(ctx.vix9d, (int, float)) or not isinstance(ctx.vix3m, (int, float)):
        return _unconfigured_result(
            "F10",
            "VIX term structure regime",
            2,
            "VIX term-structure inputs missing.",
            "missing_vix_term_inputs",
        )

    spot = float(ctx.vix_spot)
    vix9d = float(ctx.vix9d)
    vix3m = float(ctx.vix3m)
    slope = float(ctx.vix_term_slope) if isinstance(ctx.vix_term_slope, (int, float)) else vix3m - vix9d
    if vix9d >= vix3m or spot >= 25.0:
        return FactorResult(
            factor_id="F10",
            factor_name="VIX term structure regime",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Volatility curve is stressed (VIX {spot:.1f}, 9D {vix9d:.1f}, 3M {vix3m:.1f}).",
            metadata={"vix_spot": spot, "vix9d": vix9d, "vix3m": vix3m, "vix_term_slope": slope},
        )
    if slope >= 1.0 and spot < 20.0:
        return FactorResult(
            factor_id="F10",
            factor_name="VIX term structure regime",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Volatility curve is in constructive contango (VIX {spot:.1f}, slope {slope:+.2f}).",
            metadata={"vix_spot": spot, "vix9d": vix9d, "vix3m": vix3m, "vix_term_slope": slope},
        )
    return FactorResult(
        factor_id="F10",
        factor_name="VIX term structure regime",
        layer_number=2,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Volatility curve is neutral (VIX {spot:.1f}, slope {slope:+.2f}).",
        metadata={"vix_spot": spot, "vix9d": vix9d, "vix3m": vix3m, "vix_term_slope": slope},
    )


def _f09_overnight_futures_gap(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.overnight_futures_gap_pct, (int, float)) or ctx.overnight_outside_prior_range is None:
        return _unconfigured_result(
            "F09",
            "Overnight futures gap vs prior RTH range",
            2,
            "Overnight futures gap inputs missing.",
            "missing_overnight_gap_inputs",
        )

    gap_pct = float(ctx.overnight_futures_gap_pct)
    outside = bool(ctx.overnight_outside_prior_range)
    if outside and gap_pct <= -0.005:
        return FactorResult(
            factor_id="F09",
            factor_name="Overnight futures gap vs prior RTH range",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Futures opened below the prior RTH range with a negative overnight gap ({gap_pct:+.2%}).",
            metadata={"overnight_futures_gap_pct": gap_pct, "overnight_outside_prior_range": outside},
        )
    if outside and gap_pct >= 0.005:
        return FactorResult(
            factor_id="F09",
            factor_name="Overnight futures gap vs prior RTH range",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Futures opened above the prior RTH range with a positive overnight gap ({gap_pct:+.2%}).",
            metadata={"overnight_futures_gap_pct": gap_pct, "overnight_outside_prior_range": outside},
        )
    return FactorResult(
        factor_id="F09",
        factor_name="Overnight futures gap vs prior RTH range",
        layer_number=2,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Overnight futures gap is contained within prior RTH context ({gap_pct:+.2%}).",
        metadata={"overnight_futures_gap_pct": gap_pct, "overnight_outside_prior_range": outside},
    )


def _f02_ceasefire_headline(ctx: ScanContext) -> FactorResult:
    if ctx.ceasefire_headline:
        return FactorResult(
            factor_id="F02",
            factor_name="Conflict/ceasefire status and headline cadence",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail="Ceasefire/de-escalation headline detected; regime risk recalibration required.",
            metadata={"ceasefire_headline": True},
        )
    return FactorResult(
        factor_id="F02",
        factor_name="Conflict/ceasefire status and headline cadence",
        layer_number=1,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No ceasefire/de-escalation headline signal in current tape context.",
        metadata={"ceasefire_headline": False},
    )


def _f03_dxy_trend(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.dxy_change_5d, (int, float)):
        return _unconfigured_result(
            "F03",
            "DXY trend and sector read-through",
            1,
            "Dollar-index trend input missing.",
            "missing_dxy_change_5d",
        )

    dxy_change = float(ctx.dxy_change_5d)
    growth_sensitive = (
        "technology" in ctx.sector.lower()
        or "semiconductor" in ctx.sector.lower()
        or "communication" in ctx.sector.lower()
    )
    if dxy_change >= 0.015 and growth_sensitive:
        return FactorResult(
            factor_id="F03",
            factor_name="DXY trend and sector read-through",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Dollar trend is a headwind for the sector (5d DXY {dxy_change:+.2%}).",
            metadata={"dxy_change_5d": dxy_change, "sector": ctx.sector},
        )
    if dxy_change <= -0.01 and growth_sensitive:
        return FactorResult(
            factor_id="F03",
            factor_name="DXY trend and sector read-through",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Dollar trend is supportive for the sector (5d DXY {dxy_change:+.2%}).",
            metadata={"dxy_change_5d": dxy_change, "sector": ctx.sector},
        )
    return FactorResult(
        factor_id="F03",
        factor_name="DXY trend and sector read-through",
        layer_number=1,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Dollar trend is neutral for the sector (5d DXY {dxy_change:+.2%}).",
        metadata={"dxy_change_5d": dxy_change, "sector": ctx.sector},
    )


def _f04_curve_shape(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.curve_10y_2y_bps, (int, float)) or not isinstance(ctx.curve_change_5d_bps, (int, float)):
        return _unconfigured_result(
            "F04",
            "10Y/2Y curve shape and moves",
            1,
            "US curve inputs missing.",
            "missing_curve_inputs",
        )

    curve_bps = float(ctx.curve_10y_2y_bps)
    curve_delta = float(ctx.curve_change_5d_bps)
    if curve_bps < 0 or curve_delta <= -15.0:
        return FactorResult(
            factor_id="F04",
            factor_name="10Y/2Y curve shape and moves",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Curve regime is risk-off ({curve_bps:.1f} bps, 5d change {curve_delta:+.1f} bps).",
            metadata={"curve_10y_2y_bps": curve_bps, "curve_change_5d_bps": curve_delta},
        )
    if curve_bps >= 25.0 and curve_delta >= 5.0:
        return FactorResult(
            factor_id="F04",
            factor_name="10Y/2Y curve shape and moves",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Curve is steepening constructively ({curve_bps:.1f} bps, 5d change {curve_delta:+.1f} bps).",
            metadata={"curve_10y_2y_bps": curve_bps, "curve_change_5d_bps": curve_delta},
        )
    return FactorResult(
        factor_id="F04",
        factor_name="10Y/2Y curve shape and moves",
        layer_number=1,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Curve shape is neutral ({curve_bps:.1f} bps, 5d change {curve_delta:+.1f} bps).",
        metadata={"curve_10y_2y_bps": curve_bps, "curve_change_5d_bps": curve_delta},
    )


def _f05_cross_asset_risk(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.hyg_lqd_ratio_change_5d, (int, float)) or not isinstance(ctx.gld_change_5d, (int, float)) or not isinstance(ctx.vix_spot, (int, float)):
        return _unconfigured_result(
            "F05",
            "Cross-asset risk regime",
            1,
            "Cross-asset inputs missing.",
            "missing_cross_asset_inputs",
        )

    credit = float(ctx.hyg_lqd_ratio_change_5d)
    gold = float(ctx.gld_change_5d)
    vix = float(ctx.vix_spot)
    if credit <= -0.01 and gold >= 0.01 and vix >= 22.0:
        return FactorResult(
            factor_id="F05",
            factor_name="Cross-asset risk regime",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail="Credit, gold, and volatility are aligned in a risk-off regime.",
            metadata={"hyg_lqd_ratio_change_5d": credit, "gld_change_5d": gold, "vix_spot": vix},
        )
    if credit > 0 and vix < 18.0:
        return FactorResult(
            factor_id="F05",
            factor_name="Cross-asset risk regime",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Credit and volatility are consistent with a supportive risk backdrop.",
            metadata={"hyg_lqd_ratio_change_5d": credit, "gld_change_5d": gold, "vix_spot": vix},
        )
    return FactorResult(
        factor_id="F05",
        factor_name="Cross-asset risk regime",
        layer_number=1,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Cross-asset regime is mixed.",
        metadata={"hyg_lqd_ratio_change_5d": credit, "gld_change_5d": gold, "vix_spot": vix},
    )


def _f01_fed_rate_path_proxy(ctx: ScanContext) -> FactorResult:
    proxy = ctx.fed_policy_prob_proxy
    if not isinstance(proxy, (int, float)):
        return _unconfigured_result(
            "F01",
            "Fed policy stance / rate path",
            1,
            "Fed stance proxy inputs are missing.",
            "missing_fed_policy_proxy",
        )

    p = float(proxy)
    if p >= 0.65:
        return FactorResult(
            factor_id="F01",
            factor_name="Fed policy stance / rate path",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Fed path proxy is hawkish (score={p:.2f}); funding conditions likely tighter.",
            metadata={"fed_policy_prob_proxy": p, "source_tier": "FREE_PROXY"},
        )
    if p <= 0.35:
        return FactorResult(
            factor_id="F01",
            factor_name="Fed policy stance / rate path",
            layer_number=1,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Fed path proxy is dovish (score={p:.2f}); liquidity backdrop may be supportive.",
            metadata={"fed_policy_prob_proxy": p, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F01",
        factor_name="Fed policy stance / rate path",
        layer_number=1,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Fed path proxy is neutral (score={p:.2f}).",
        metadata={"fed_policy_prob_proxy": p, "source_tier": "FREE_PROXY"},
    )


def _f08_central_bank_surprise_proxy(ctx: ScanContext) -> FactorResult:
    if ctx.central_bank_surprise_score is None and not ctx.central_bank_surprise_proxy:
        return _unconfigured_result(
            "F08",
            "BOJ/ECB/PBOC policy surprise scan",
            2,
            "Central-bank surprise proxy inputs are missing.",
            "missing_central_bank_proxy",
        )

    score = float(ctx.central_bank_surprise_score or 0.0)
    if ctx.central_bank_surprise_proxy:
        return FactorResult(
            factor_id="F08",
            factor_name="BOJ/ECB/PBOC policy surprise scan",
            layer_number=2,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.REDUCE_SIZE,
            detail="Central-bank surprise/intervention proxy signal detected; reduce tactical size.",
            metadata={"central_bank_surprise_proxy": True, "central_bank_surprise_score": score, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F08",
        factor_name="BOJ/ECB/PBOC policy surprise scan",
        layer_number=2,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No central-bank surprise proxy signal detected.",
        metadata={"central_bank_surprise_proxy": False, "central_bank_surprise_score": score, "source_tier": "FREE_PROXY"},
    )


def _f11_earnings_calendar(ctx: ScanContext) -> FactorResult:
    if ctx.has_earnings_today:
        return FactorResult(
            factor_id="F11",
            factor_name="Full earnings calendar scan",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Ticker is in earnings calendar window.",
            metadata={"has_earnings_today": True},
        )
    return FactorResult(
        factor_id="F11",
        factor_name="Full earnings calendar scan",
        layer_number=3,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No same-day earnings event for ticker.",
        metadata={"has_earnings_today": False},
    )


def _f12_whisper_vs_consensus_proxy(ctx: ScanContext) -> FactorResult:
    proxy = ctx.whisper_eps_gap_proxy
    if not isinstance(proxy, (int, float)):
        return _unconfigured_result(
            "F12",
            "Whisper vs consensus gap",
            3,
            "Whisper proxy is unavailable outside earnings window or missing options/sentiment inputs.",
            "missing_whisper_proxy",
        )

    val = float(proxy)
    if val >= 0.25:
        return FactorResult(
            factor_id="F12",
            factor_name="Whisper vs consensus gap",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Whisper proxy indicates bullish pre-earnings bias (score={val:+.2f}).",
            metadata={"whisper_eps_gap_proxy": val, "source_tier": "FREE_PROXY"},
        )
    if val <= -0.25:
        return FactorResult(
            factor_id="F12",
            factor_name="Whisper vs consensus gap",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Whisper proxy indicates bearish pre-earnings bias (score={val:+.2f}).",
            metadata={"whisper_eps_gap_proxy": val, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F12",
        factor_name="Whisper vs consensus gap",
        layer_number=3,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Whisper proxy is neutral (score={val:+.2f}).",
        metadata={"whisper_eps_gap_proxy": val, "source_tier": "FREE_PROXY"},
    )


def _f13_guidance_trend_proxy(ctx: ScanContext) -> FactorResult:
    trend = ctx.guidance_revision_trend_4q
    if not isinstance(trend, (int, float)):
        return _unconfigured_result(
            "F13",
            "Guidance revision trend (4Q)",
            3,
            "Guidance-trend proxy missing due to insufficient quarterly earnings history.",
            "missing_guidance_trend_proxy",
        )

    t = float(trend)
    if t >= 2.0:
        return FactorResult(
            factor_id="F13",
            factor_name="Guidance revision trend (4Q)",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Guidance proxy trend is improving over recent quarters (delta surprise={t:+.2f}).",
            metadata={"guidance_revision_trend_4q": t, "source_tier": "FREE_PROXY"},
        )
    if t <= -2.0:
        return FactorResult(
            factor_id="F13",
            factor_name="Guidance revision trend (4Q)",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Guidance proxy trend is deteriorating over recent quarters (delta surprise={t:+.2f}).",
            metadata={"guidance_revision_trend_4q": t, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F13",
        factor_name="Guidance revision trend (4Q)",
        layer_number=3,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Guidance proxy trend is stable (delta surprise={t:+.2f}).",
        metadata={"guidance_revision_trend_4q": t, "source_tier": "FREE_PROXY"},
    )


def _f17_ecosystem_scan(ctx: ScanContext) -> FactorResult:
    if ctx.ecosystem_partner_10pct_move:
        return FactorResult(
            factor_id="F17",
            factor_name="Prior-day +10% movers ecosystem scan",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Ecosystem/supply-chain sympathy signal detected.",
            metadata={"ecosystem_partner_10pct_move": True},
        )
    return FactorResult(
        factor_id="F17",
        factor_name="Prior-day +10% movers ecosystem scan",
        layer_number=4,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No ecosystem +10% sympathy signal detected.",
        metadata={"ecosystem_partner_10pct_move": False},
    )


def _f18_intrasector_corr(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.ticker_sector_corr_20d, (int, float)) or not isinstance(ctx.idiosyncratic_alpha_20d, (int, float)):
        return _unconfigured_result(
            "F18",
            "Intra-sector correlation structure",
            4,
            "Ticker-vs-sector correlation inputs missing.",
            "missing_sector_corr_inputs",
        )

    corr = float(ctx.ticker_sector_corr_20d)
    alpha = float(ctx.idiosyncratic_alpha_20d)
    if corr <= 0.55 and alpha >= 0.03:
        return FactorResult(
            factor_id="F18",
            factor_name="Intra-sector correlation structure",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Ticker is showing positive idiosyncratic leadership vs sector (corr {corr:.2f}, alpha {alpha:+.2%}).",
            metadata={"ticker_sector_corr_20d": corr, "idiosyncratic_alpha_20d": alpha},
        )
    if corr >= 0.85 and alpha <= 0.0:
        return FactorResult(
            factor_id="F18",
            factor_name="Intra-sector correlation structure",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Ticker is moving as a weak sector clone (corr {corr:.2f}, alpha {alpha:+.2%}).",
            metadata={"ticker_sector_corr_20d": corr, "idiosyncratic_alpha_20d": alpha},
        )
    return FactorResult(
        factor_id="F18",
        factor_name="Intra-sector correlation structure",
        layer_number=4,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Intra-sector correlation structure is neutral.",
        metadata={"ticker_sector_corr_20d": corr, "idiosyncratic_alpha_20d": alpha},
    )


def _f19_sector_rotation(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.sector_flow_score, (int, float)):
        return _unconfigured_result(
            "F19",
            "Sector rotation flow proxy",
            4,
            "Sector flow inputs missing.",
            "missing_sector_flow_score",
        )

    flow = float(ctx.sector_flow_score)
    if flow >= 0.02:
        return FactorResult(
            factor_id="F19",
            factor_name="Sector rotation flow proxy",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Sector rotation flow is supportive ({flow:+.2%} vs SPX composite).",
            metadata={"sector_flow_score": flow, "sector_etf_symbol": ctx.sector_etf_symbol},
        )
    if flow <= -0.02:
        return FactorResult(
            factor_id="F19",
            factor_name="Sector rotation flow proxy",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Sector rotation flow is unfavorable ({flow:+.2%} vs SPX composite).",
            metadata={"sector_flow_score": flow, "sector_etf_symbol": ctx.sector_etf_symbol},
        )
    return FactorResult(
        factor_id="F19",
        factor_name="Sector rotation flow proxy",
        layer_number=4,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Sector rotation flow is mixed.",
        metadata={"sector_flow_score": flow, "sector_etf_symbol": ctx.sector_etf_symbol},
    )


def _f14_investor_day(ctx: ScanContext) -> FactorResult:
    if ctx.analyst_day_catalyst or ctx.product_launch_catalyst:
        return FactorResult(
            factor_id="F14",
            factor_name="Investor day / conference catalysts",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Investor-day or product-launch catalyst signal is active.",
            metadata={
                "analyst_day_catalyst": bool(ctx.analyst_day_catalyst),
                "product_launch_catalyst": bool(ctx.product_launch_catalyst),
            },
        )
    return FactorResult(
        factor_id="F14",
        factor_name="Investor day / conference catalysts",
        layer_number=3,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No investor-day/product-launch catalyst signal detected.",
        metadata={
            "analyst_day_catalyst": bool(ctx.analyst_day_catalyst),
            "product_launch_catalyst": bool(ctx.product_launch_catalyst),
        },
    )


def _f15_regulatory_overlay(ctx: ScanContext) -> FactorResult:
    if ctx.fda_regulatory_catalyst:
        return FactorResult(
            factor_id="F15",
            factor_name="Regulatory/FDA/legal catalysts",
            layer_number=3,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Regulatory/FDA catalyst detected.",
            metadata={"fda_regulatory_catalyst": True},
        )
    return FactorResult(
        factor_id="F15",
        factor_name="Regulatory/FDA/legal catalysts",
        layer_number=3,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No regulatory/FDA catalyst detected.",
        metadata={"fda_regulatory_catalyst": False},
    )


def _f16_sector_relative_strength(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.sector_rs_5d, (int, float)) or not isinstance(ctx.sector_rs_20d, (int, float)):
        return _unconfigured_result(
            "F16",
            "Sector relative strength ranking",
            4,
            "Sector relative-strength inputs missing.",
            "missing_sector_rs_inputs",
        )

    rs_5d = float(ctx.sector_rs_5d)
    rs_20d = float(ctx.sector_rs_20d)
    if rs_5d >= 0.02 and rs_20d >= 0.02:
        return FactorResult(
            factor_id="F16",
            factor_name="Sector relative strength ranking",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Sector is outperforming SPX on both 5d and 20d windows ({rs_5d:+.2%}, {rs_20d:+.2%}).",
            metadata={"sector_rs_5d": rs_5d, "sector_rs_20d": rs_20d, "sector_etf_symbol": ctx.sector_etf_symbol},
        )
    if rs_5d <= -0.02 and rs_20d <= -0.02:
        return FactorResult(
            factor_id="F16",
            factor_name="Sector relative strength ranking",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Sector is underperforming SPX on both 5d and 20d windows ({rs_5d:+.2%}, {rs_20d:+.2%}).",
            metadata={"sector_rs_5d": rs_5d, "sector_rs_20d": rs_20d, "sector_etf_symbol": ctx.sector_etf_symbol},
        )
    return FactorResult(
        factor_id="F16",
        factor_name="Sector relative strength ranking",
        layer_number=4,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Sector relative strength is mixed.",
        metadata={"sector_rs_5d": rs_5d, "sector_rs_20d": rs_20d, "sector_etf_symbol": ctx.sector_etf_symbol},
    )


def _f20_portfolio_concentration(ctx: ScanContext) -> FactorResult:
    exposure = float(ctx.portfolio_sector_exposure or 0.0)
    if exposure > 0.30:
        return FactorResult(
            factor_id="F20",
            factor_name="Portfolio concentration check",
            layer_number=4,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Sector exposure already elevated ({exposure:.2%}); avoid correlated stacking.",
            metadata={"portfolio_sector_exposure": exposure},
        )
    return FactorResult(
        factor_id="F20",
        factor_name="Portfolio concentration check",
        layer_number=4,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Sector exposure acceptable ({exposure:.2%}).",
        metadata={"portfolio_sector_exposure": exposure},
    )


def _f21_mtf_alignment(ctx: ScanContext) -> FactorResult:
    if ctx.mtf_trend_aligned:
        return FactorResult(
            factor_id="F21",
            factor_name="Multi-timeframe trend alignment",
            layer_number=5,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Daily/60m trend alignment confirmed.",
            metadata={"mtf_trend_aligned": True},
        )
    return FactorResult(
        factor_id="F21",
        factor_name="Multi-timeframe trend alignment",
        layer_number=5,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Multi-timeframe trend alignment not confirmed.",
        metadata={"mtf_trend_aligned": False},
    )


def _f25_relative_volume(ctx: ScanContext) -> FactorResult:
    rv = ctx.relative_volume
    if isinstance(rv, (int, float)) and rv >= 1.2:
        return FactorResult(
            factor_id="F25",
            factor_name="Relative volume confirmation",
            layer_number=5,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Relative volume strong ({float(rv):.2f}x vs 20-day).",
            metadata={"relative_volume": float(rv)},
        )
    return FactorResult(
        factor_id="F25",
        factor_name="Relative volume confirmation",
        layer_number=5,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Relative volume confirmation not met.",
        metadata={"relative_volume": rv},
    )


def _f22_key_levels(ctx: ScanContext) -> FactorResult:
    if ctx.is_at_ath or (ctx.gap_present and ctx.gap_hold_valid):
        return FactorResult(
            factor_id="F22",
            factor_name="Key level map",
            layer_number=5,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Price is interacting with a key level (ATH proximity or validated gap-hold).",
            metadata={
                "is_at_ath": bool(ctx.is_at_ath),
                "gap_present": bool(ctx.gap_present),
                "gap_hold_valid": bool(ctx.gap_hold_valid),
            },
        )
    return FactorResult(
        factor_id="F22",
        factor_name="Key level map",
        layer_number=5,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No ATH/gap-hold key level trigger detected.",
        metadata={
            "is_at_ath": bool(ctx.is_at_ath),
            "gap_present": bool(ctx.gap_present),
            "gap_hold_valid": bool(ctx.gap_hold_valid),
        },
    )


def _f23_volume_profile(ctx: ScanContext) -> FactorResult:
    state = (ctx.volume_profile_state or "").upper()
    if not state:
        return _unconfigured_result(
            "F23",
            "Volume profile node test",
            5,
            "Volume-profile node inputs missing.",
            "missing_volume_profile_inputs",
        )

    if state in {"AT_HVN", "ABOVE_HVN"}:
        return FactorResult(
            factor_id="F23",
            factor_name="Volume profile node test",
            layer_number=5,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Price is trading constructively relative to the high-volume node ({state}).",
            metadata={"volume_profile_state": state, "volume_profile_hvn": ctx.volume_profile_hvn, "volume_profile_lvn": ctx.volume_profile_lvn},
        )
    if state in {"AT_LVN", "BELOW_LVN"}:
        return FactorResult(
            factor_id="F23",
            factor_name="Volume profile node test",
            layer_number=5,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Price is trading weakly relative to the low-volume node ({state}).",
            metadata={"volume_profile_state": state, "volume_profile_hvn": ctx.volume_profile_hvn, "volume_profile_lvn": ctx.volume_profile_lvn},
        )
    return FactorResult(
        factor_id="F23",
        factor_name="Volume profile node test",
        layer_number=5,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Price is between major volume-profile nodes.",
        metadata={"volume_profile_state": state, "volume_profile_hvn": ctx.volume_profile_hvn, "volume_profile_lvn": ctx.volume_profile_lvn},
    )


def _f24_ma_stack(ctx: ScanContext) -> FactorResult:
    if ctx.sma_50 is None or ctx.sma_200 is None or ctx.current_price <= 0:
        return FactorResult(
            factor_id="F24",
            factor_name="MA stack and slope",
            layer_number=5,
            status=FactorStatus.UNCONFIGURED,
            triggered=False,
            action=FactorAction.PASS,
            stubbed=True,
            detail="Insufficient moving-average inputs for MA stack check.",
            metadata={"reason": "missing_sma_inputs"},
        )

    bullish_stack = ctx.current_price > ctx.sma_50 > ctx.sma_200
    if bullish_stack:
        return FactorResult(
            factor_id="F24",
            factor_name="MA stack and slope",
            layer_number=5,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Bullish MA stack detected (price > SMA50 > SMA200).",
            metadata={"current_price": ctx.current_price, "sma_50": ctx.sma_50, "sma_200": ctx.sma_200},
        )
    return FactorResult(
        factor_id="F24",
        factor_name="MA stack and slope",
        layer_number=5,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.DOWNGRADE,
        detail="MA stack not aligned for bullish structure.",
        metadata={"current_price": ctx.current_price, "sma_50": ctx.sma_50, "sma_200": ctx.sma_200},
    )


def _f26_iv_rank(ctx: ScanContext) -> FactorResult:
    iv_rank = ctx.iv_rank_1y
    if not isinstance(iv_rank, (int, float)):
        return FactorResult(
            factor_id="F26",
            factor_name="IV rank vs 1-year range",
            layer_number=6,
            status=FactorStatus.UNCONFIGURED,
            triggered=False,
            action=FactorAction.PASS,
            stubbed=True,
            detail="IV rank input missing for ticker.",
            metadata={"reason": "missing_iv_rank_1y"},
        )
    if iv_rank >= 75.0:
        return FactorResult(
            factor_id="F26",
            factor_name="IV rank vs 1-year range",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Premium expensive (IV rank {float(iv_rank):.1f}).",
            metadata={"iv_rank_1y": float(iv_rank)},
        )
    return FactorResult(
        factor_id="F26",
        factor_name="IV rank vs 1-year range",
        layer_number=6,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.FLAG,
        detail=f"IV rank acceptable ({float(iv_rank):.1f}).",
        metadata={"iv_rank_1y": float(iv_rank)},
    )


def _f27_iv_crush(ctx: ScanContext) -> FactorResult:
    risk = (ctx.iv_crush_risk or "").upper()
    if risk == "HIGH":
        return FactorResult(
            factor_id="F27",
            factor_name="IV crush risk",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail="High IV crush risk detected.",
            metadata={"iv_crush_risk": risk},
        )
    if risk:
        return FactorResult(
            factor_id="F27",
            factor_name="IV crush risk",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=False,
            action=FactorAction.PASS,
            detail=f"IV crush risk tier: {risk}.",
            metadata={"iv_crush_risk": risk},
        )
    return FactorResult(
        factor_id="F27",
        factor_name="IV crush risk",
        layer_number=6,
        status=FactorStatus.UNCONFIGURED,
        triggered=False,
        action=FactorAction.PASS,
        stubbed=True,
        detail="IV crush risk input missing for ticker.",
        metadata={"reason": "missing_iv_crush_risk"},
    )


def _f28_delta_selection(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.option_delta, (int, float)) or not isinstance(ctx.option_dte, int):
        return _unconfigured_result(
            "F28",
            "Delta selection vs conviction",
            6,
            "Option delta inputs missing for selected contract.",
            "missing_option_delta_inputs",
        )

    from app.framework.scoring import calculate_conviction_score

    provisional_conviction = calculate_conviction_score(ctx)
    abs_delta = abs(float(ctx.option_delta))
    if provisional_conviction >= 7.0:
        lo, hi = 0.30, 0.55
    elif provisional_conviction >= 5.5:
        lo, hi = 0.25, 0.45
    else:
        lo, hi = 0.20, 0.35

    if lo <= abs_delta <= hi:
        return FactorResult(
            factor_id="F28",
            factor_name="Delta selection vs conviction",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Selected contract delta {abs_delta:.2f} is aligned with provisional conviction {provisional_conviction:.1f}.",
            metadata={"option_delta": float(ctx.option_delta), "option_dte": ctx.option_dte, "provisional_conviction": provisional_conviction},
        )
    return FactorResult(
        factor_id="F28",
        factor_name="Delta selection vs conviction",
        layer_number=6,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.DOWNGRADE,
        detail=f"Selected contract delta {abs_delta:.2f} is not aligned with provisional conviction {provisional_conviction:.1f}.",
        metadata={"option_delta": float(ctx.option_delta), "option_dte": ctx.option_dte, "provisional_conviction": provisional_conviction},
    )


def _f29_theta_burden(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.option_theta_daily, (int, float)) or not isinstance(ctx.option_mid_price, (int, float)) or not isinstance(ctx.option_dte, int):
        return _unconfigured_result(
            "F29",
            "Theta burden vs thesis horizon",
            6,
            "Option theta inputs missing for selected contract.",
            "missing_option_theta_inputs",
        )

    mid = float(ctx.option_mid_price)
    if mid <= 0:
        return _unconfigured_result(
            "F29",
            "Theta burden vs thesis horizon",
            6,
            "Option premium invalid for theta-burden evaluation.",
            "invalid_option_premium",
        )

    theta_burden = abs(float(ctx.option_theta_daily)) / mid
    if theta_burden > 0.03 or ctx.option_dte < 21:
        return FactorResult(
            factor_id="F29",
            factor_name="Theta burden vs thesis horizon",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Theta burden is elevated at {theta_burden:.2%} of premium per day with {ctx.option_dte} DTE.",
            metadata={"option_theta_daily": float(ctx.option_theta_daily), "option_mid_price": mid, "theta_burden": theta_burden, "option_dte": ctx.option_dte},
        )
    return FactorResult(
        factor_id="F29",
        factor_name="Theta burden vs thesis horizon",
        layer_number=6,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.FLAG,
        detail=f"Theta burden is acceptable at {theta_burden:.2%} of premium per day with {ctx.option_dte} DTE.",
        metadata={"option_theta_daily": float(ctx.option_theta_daily), "option_mid_price": mid, "theta_burden": theta_burden, "option_dte": ctx.option_dte},
    )


def _f30_skew(ctx: ScanContext) -> FactorResult:
    skew = (ctx.skew_signal or "").upper()
    if skew == "PUT_HEDGE_HEAVY":
        return FactorResult(
            factor_id="F30",
            factor_name="Put/call skew check",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail="Put-heavy skew indicates defensive hedging pressure.",
            metadata={"skew_signal": skew, "put_call_oi_ratio": ctx.put_call_oi_ratio},
        )
    if skew:
        return FactorResult(
            factor_id="F30",
            factor_name="Put/call skew check",
            layer_number=6,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Options skew signal: {skew}.",
            metadata={"skew_signal": skew, "put_call_oi_ratio": ctx.put_call_oi_ratio},
        )
    return FactorResult(
        factor_id="F30",
        factor_name="Put/call skew check",
        layer_number=6,
        status=FactorStatus.UNCONFIGURED,
        triggered=False,
        action=FactorAction.PASS,
        stubbed=True,
        detail="Options skew inputs missing for ticker.",
        metadata={"reason": "missing_skew_signal"},
    )


def _f31_option_open_interest(ctx: ScanContext) -> FactorResult:
    oi = ctx.option_open_interest
    if not isinstance(oi, (int, float)):
        return FactorResult(
            factor_id="F31",
            factor_name="Strike OI vs float gamma risk",
            layer_number=7,
            status=FactorStatus.UNCONFIGURED,
            triggered=False,
            action=FactorAction.PASS,
            stubbed=True,
            detail="Option open-interest input missing.",
            metadata={"reason": "missing_option_open_interest"},
        )
    if float(oi) < 100:
        return FactorResult(
            factor_id="F31",
            factor_name="Strike OI vs float gamma risk",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Low strike OI ({int(oi)}) indicates weak liquidity/gamma support.",
            metadata={"option_open_interest": float(oi)},
        )
    return FactorResult(
        factor_id="F31",
        factor_name="Strike OI vs float gamma risk",
        layer_number=7,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.FLAG,
        detail=f"Strike OI is adequate ({int(oi)}).",
        metadata={"option_open_interest": float(oi)},
    )


def _f32_spread_risk(ctx: ScanContext) -> FactorResult:
    bid = ctx.option_bid
    ask = ctx.option_ask
    if not isinstance(bid, (int, float)) or not isinstance(ask, (int, float)):
        return FactorResult(
            factor_id="F32",
            factor_name="Bid/ask spread slippage risk",
            layer_number=7,
            status=FactorStatus.UNCONFIGURED,
            triggered=False,
            action=FactorAction.PASS,
            stubbed=True,
            detail="Bid/ask inputs missing for spread risk evaluation.",
            metadata={"reason": "missing_bid_ask"},
        )

    mid = (float(bid) + float(ask)) / 2.0
    if mid <= 0:
        return FactorResult(
            factor_id="F32",
            factor_name="Bid/ask spread slippage risk",
            layer_number=7,
            status=FactorStatus.UNCONFIGURED,
            triggered=False,
            action=FactorAction.PASS,
            stubbed=True,
            detail="Invalid option premium inputs for spread risk evaluation.",
            metadata={"reason": "invalid_bid_ask"},
        )

    spread_pct = (float(ask) - float(bid)) / mid
    if spread_pct > 0.12:
        return FactorResult(
            factor_id="F32",
            factor_name="Bid/ask spread slippage risk",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Wide option spread ({spread_pct:.1%}) implies elevated slippage risk.",
            metadata={"spread_pct": spread_pct, "bid": float(bid), "ask": float(ask)},
        )
    return FactorResult(
        factor_id="F32",
        factor_name="Bid/ask spread slippage risk",
        layer_number=7,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.FLAG,
        detail=f"Spread is acceptable ({spread_pct:.1%}).",
        metadata={"spread_pct": spread_pct, "bid": float(bid), "ask": float(ask)},
    )


def _f33_options_volume_history_proxy(ctx: ScanContext) -> FactorResult:
    ratio = ctx.option_volume_oi_ratio
    if not isinstance(ratio, (int, float)):
        return _unconfigured_result(
            "F33",
            "Options volume vs 20-day",
            7,
            "Options volume-history proxy missing (requires live chain volume and OI).",
            "missing_option_volume_history_proxy",
        )

    r = float(ratio)
    if r >= 0.25:
        return FactorResult(
            factor_id="F33",
            factor_name="Options volume vs 20-day",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Options activity is elevated vs OI baseline (volume/OI={r:.2f}).",
            metadata={"option_volume_oi_ratio": r, "source_tier": "FREE_PROXY"},
        )
    if r <= 0.05:
        return FactorResult(
            factor_id="F33",
            factor_name="Options volume vs 20-day",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Options activity is thin vs OI baseline (volume/OI={r:.2f}).",
            metadata={"option_volume_oi_ratio": r, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F33",
        factor_name="Options volume vs 20-day",
        layer_number=7,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Options activity is neutral vs OI baseline (volume/OI={r:.2f}).",
        metadata={"option_volume_oi_ratio": r, "source_tier": "FREE_PROXY"},
    )


def _f35_dealer_gamma_proxy(ctx: ScanContext) -> FactorResult:
    regime = (ctx.dealer_gamma_regime_proxy or "").upper()
    if not regime:
        return _unconfigured_result(
            "F35",
            "Market-maker positioning proxy",
            7,
            "Dealer-gamma proxy inputs missing.",
            "missing_dealer_gamma_proxy",
        )

    if regime == "NEGATIVE_GAMMA_PROXY":
        return FactorResult(
            factor_id="F35",
            factor_name="Market-maker positioning proxy",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.REDUCE_SIZE,
            detail="Dealer gamma proxy indicates unstable/accelerating tape risk.",
            metadata={"dealer_gamma_regime_proxy": regime, "source_tier": "FREE_PROXY"},
        )
    if regime == "POSITIVE_GAMMA_PROXY":
        return FactorResult(
            factor_id="F35",
            factor_name="Market-maker positioning proxy",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Dealer gamma proxy indicates more stable liquidity regime.",
            metadata={"dealer_gamma_regime_proxy": regime, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F35",
        factor_name="Market-maker positioning proxy",
        layer_number=7,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Dealer gamma proxy is neutral.",
        metadata={"dealer_gamma_regime_proxy": regime, "source_tier": "FREE_PROXY"},
    )


def _f34_underlying_liquidity(ctx: ScanContext) -> FactorResult:
    if ctx.volume >= 1_000_000:
        return FactorResult(
            factor_id="F34",
            factor_name="Underlying share liquidity",
            layer_number=7,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Underlying liquidity is healthy ({ctx.volume} shares traded).",
            metadata={"volume": ctx.volume},
        )
    return FactorResult(
        factor_id="F34",
        factor_name="Underlying share liquidity",
        layer_number=7,
        status=FactorStatus.LIVE,
        triggered=True,
        action=FactorAction.DOWNGRADE,
        detail=f"Underlying liquidity is light ({ctx.volume} shares traded).",
        metadata={"volume": ctx.volume},
    )


def _f36_analyst_revision(ctx: ScanContext) -> FactorResult:
    if ctx.analyst_rating_change:
        return FactorResult(
            factor_id="F36",
            factor_name="Analyst rating and target revision",
            layer_number=8,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Analyst rating/target revision signal detected.",
            metadata={"analyst_rating_change": True, "analyst_firm_tier": ctx.analyst_firm_tier},
        )
    return FactorResult(
        factor_id="F36",
        factor_name="Analyst rating and target revision",
        layer_number=8,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="No analyst revision signal for ticker.",
        metadata={"analyst_rating_change": False},
    )


def _f37_short_interest(ctx: ScanContext) -> FactorResult:
    if not isinstance(ctx.short_ratio, (int, float)) and not isinstance(ctx.short_percent_float, (int, float)):
        return _unconfigured_result(
            "F37",
            "Short interest / days-to-cover",
            8,
            "Short-interest inputs missing.",
            "missing_short_interest_inputs",
        )

    short_ratio = float(ctx.short_ratio) if isinstance(ctx.short_ratio, (int, float)) else None
    short_float = float(ctx.short_percent_float) if isinstance(ctx.short_percent_float, (int, float)) else None
    if (short_ratio is not None and short_ratio >= 5.0) or (short_float is not None and short_float >= 0.10):
        return FactorResult(
            factor_id="F37",
            factor_name="Short interest / days-to-cover",
            layer_number=8,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail="Short-interest profile indicates squeeze potential or crowded positioning.",
            metadata={"short_ratio": short_ratio, "short_percent_float": short_float},
        )
    return FactorResult(
        factor_id="F37",
        factor_name="Short interest / days-to-cover",
        layer_number=8,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail="Short-interest profile is not elevated.",
        metadata={"short_ratio": short_ratio, "short_percent_float": short_float},
    )


def _f38_retail_sentiment_proxy(ctx: ScanContext) -> FactorResult:
    score = ctx.retail_sentiment_score
    if not isinstance(score, (int, float)):
        return _unconfigured_result(
            "F38",
            "Retail sentiment proxy",
            8,
            "Retail sentiment proxy input missing.",
            "missing_retail_sentiment_proxy",
        )

    s = float(score)
    if s >= 0.35:
        return FactorResult(
            factor_id="F38",
            factor_name="Retail sentiment proxy",
            layer_number=8,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.FLAG,
            detail=f"Retail sentiment proxy is bullish (score={s:+.2f}).",
            metadata={"retail_sentiment_score": s, "source_tier": "FREE_PROXY"},
        )
    if s <= -0.35:
        return FactorResult(
            factor_id="F38",
            factor_name="Retail sentiment proxy",
            layer_number=8,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail=f"Retail sentiment proxy is bearish (score={s:+.2f}).",
            metadata={"retail_sentiment_score": s, "source_tier": "FREE_PROXY"},
        )
    return FactorResult(
        factor_id="F38",
        factor_name="Retail sentiment proxy",
        layer_number=8,
        status=FactorStatus.LIVE,
        triggered=False,
        action=FactorAction.PASS,
        detail=f"Retail sentiment proxy is neutral (score={s:+.2f}).",
        metadata={"retail_sentiment_score": s, "source_tier": "FREE_PROXY"},
    )


def _f39_inst_insider(ctx: ScanContext) -> FactorResult:
    if isinstance(ctx.insider_ownership, (int, float)) and isinstance(ctx.institutional_ownership, (int, float)):
        if float(ctx.insider_ownership) >= 0.03 and float(ctx.institutional_ownership) >= 0.50:
            return FactorResult(
                factor_id="F39",
                factor_name="Institutional and insider trend",
                layer_number=8,
                status=FactorStatus.LIVE,
                triggered=True,
                action=FactorAction.FLAG,
                detail="Insider and institutional ownership profile supports positioning quality.",
                metadata={
                    "insider_ownership": float(ctx.insider_ownership),
                    "institutional_ownership": float(ctx.institutional_ownership),
                },
            )
        return FactorResult(
            factor_id="F39",
            factor_name="Institutional and insider trend",
            layer_number=8,
            status=FactorStatus.LIVE,
            triggered=True,
            action=FactorAction.DOWNGRADE,
            detail="Ownership profile is not strong for conviction support.",
            metadata={
                "insider_ownership": float(ctx.insider_ownership),
                "institutional_ownership": float(ctx.institutional_ownership),
            },
        )

    return FactorResult(
        factor_id="F39",
        factor_name="Institutional and insider trend",
        layer_number=8,
        status=FactorStatus.UNCONFIGURED,
        triggered=False,
        action=FactorAction.PASS,
        stubbed=True,
        detail="Institutional/insider ownership inputs are incomplete.",
        metadata={"reason": "missing_ownership_inputs"},
    )


def _factor(fid: str, name: str, layer: int, description: str, evaluator: Evaluator | None = None) -> SpecFactor:
    return SpecFactor(factor_id=fid, name=name, layer=layer, description=description, evaluator=evaluator)


def build_f1_to_f39() -> list[BaseFactor]:
    factors: list[BaseFactor] = [
        # Layer 1 — Macro & Geopolitical Regime
        _factor("F01", "Fed policy stance / rate path", 1, "F1 — Fed policy stance and next FOMC probability.", _f01_fed_rate_path_proxy),
        _factor("F02", "Conflict/ceasefire status and headline cadence", 1, "F2 — Active conflict/ceasefire status and headline risk cadence.", _f02_ceasefire_headline),
        _factor("F03", "DXY trend and sector read-through", 1, "F3 — Dollar Index trend and sector read-through.", _f03_dxy_trend),
        _factor("F04", "10Y/2Y curve shape and moves", 1, "F4 — 10Y/2Y yield move and curve-shape signal.", _f04_curve_shape),
        _factor("F05", "Cross-asset risk regime", 1, "F5 — Credit spreads + gold + VIX co-movement regime.", _f05_cross_asset_risk),

        # Layer 2 — Global Market Structure
        _factor("F06", "Asian close direction and magnitude", 2, "F6 — Nikkei/KOSPI/Hang Seng read-through.", _f06_asian_close),
        _factor("F07", "European open follow-through", 2, "F7 — DAX/FTSE reaction into US premarket.", _f07_europe_followthrough),
        _factor("F08", "BOJ/ECB/PBOC policy surprise scan", 2, "F8 — Central bank surprise/intervention signals.", _f08_central_bank_surprise_proxy),
        _factor("F09", "Overnight futures gap vs prior RTH range", 2, "F9 — Overnight futures gap-size context.", _f09_overnight_futures_gap),
        _factor("F10", "VIX term structure regime", 2, "F10 — Contango/backwardation stress signal.", _f10_vix_term_structure),

        # Layer 3 — Earnings & Catalyst Calendar
        _factor("F11", "Full earnings calendar scan", 3, "F11 — Full earnings calendar scan, no skipping.", _f11_earnings_calendar),
        _factor("F12", "Whisper vs consensus gap", 3, "F12 — Whisper number vs consensus and history.", _f12_whisper_vs_consensus_proxy),
        _factor("F13", "Guidance revision trend (4Q)", 3, "F13 — Guidance revision trend over trailing 4 quarters.", _f13_guidance_trend_proxy),
        _factor("F14", "Investor day / conference catalysts", 3, "F14 — Investor day/conference catalyst calendar.", _f14_investor_day),
        _factor("F15", "Regulatory/FDA/legal catalysts", 3, "F15 — Regulatory/FDA/legal catalyst overlay.", _f15_regulatory_overlay),

        # Layer 4 — Sector & Correlation Structure
        _factor("F16", "Sector relative strength ranking", 4, "F16 — Sector RS vs SPX (5/20-day).", _f16_sector_relative_strength),
        _factor("F17", "Ecosystem +10% mover scan", 4, "F17 — Supply-chain/partner sympathy scan.", _f17_ecosystem_scan),
        _factor("F18", "Intra-sector correlation structure", 4, "F18 — Intra-sector co-move vs idiosyncratic behavior.", _f18_intrasector_corr),
        _factor("F19", "Sector rotation flow proxy", 4, "F19 — Money flow into/out of sector proxy.", _f19_sector_rotation),
        _factor("F20", "Portfolio concentration check", 4, "F20 — Avoid stacking correlated portfolio exposure.", _f20_portfolio_concentration),

        # Layer 5 — Technical Structure
        _factor("F21", "Multi-timeframe trend alignment", 5, "F21 — Daily/60m/15m trend alignment.", _f21_mtf_alignment),
        _factor("F22", "Key level map", 5, "F22 — ATH, breakout/breakdown, and gap-fill levels.", _f22_key_levels),
        _factor("F23", "Volume profile node test", 5, "F23 — HVN/LVN placement validation.", _f23_volume_profile),
        _factor("F24", "MA stack and slope", 5, "F24 — 8/21/50/200 moving-average stack and slope.", _f24_ma_stack),
        _factor("F25", "Relative volume confirmation", 5, "F25 — Relative volume vs 20-day baseline.", _f25_relative_volume),

        # Layer 6 — Options-Specific: Greeks & IV
        _factor("F26", "IV rank vs 1-year range", 6, "F26 — IV rank/percentile valuation of premium.", _f26_iv_rank),
        _factor("F27", "IV crush risk", 6, "F27 — Term-structure/event IV crush risk.", _f27_iv_crush),
        _factor("F28", "Delta selection vs conviction", 6, "F28 — Delta selection by conviction tier.", _f28_delta_selection),
        _factor("F29", "Theta burden vs thesis horizon", 6, "F29 — Theta decay burden vs expected hold.", _f29_theta_burden),
        _factor("F30", "Put/call skew check", 6, "F30 — Skew signal for hedge/spec demand.", _f30_skew),

        # Layer 7 — Liquidity & Microstructure
        _factor("F31", "Strike OI vs float gamma risk", 7, "F31 — Open interest at strike vs underlying float.", _f31_option_open_interest),
        _factor("F32", "Bid/ask spread slippage risk", 7, "F32 — Bid/ask spread as % premium.", _f32_spread_risk),
        _factor("F33", "Options volume vs 20-day", 7, "F33 — Daily options volume confirmation.", _f33_options_volume_history_proxy),
        _factor("F34", "Underlying share liquidity", 7, "F34 — Avg dollar volume/liquidity check.", _f34_underlying_liquidity),
        _factor("F35", "Market-maker positioning proxy", 7, "F35 — Gamma flip/positioning proxy.", _f35_dealer_gamma_proxy),

        # Layer 8 — Sentiment & Positioning
        _factor("F36", "Analyst rating and target revision", 8, "F36 — Analyst change signals.", _f36_analyst_revision),
        _factor("F37", "Short interest / days-to-cover", 8, "F37 — Squeeze risk confirmation.", _f37_short_interest),
        _factor("F38", "Retail sentiment proxy", 8, "F38 — Social/options-flow sentiment.", _f38_retail_sentiment_proxy),
        _factor("F39", "Institutional and insider trend", 8, "F39 — 13F/insider transaction trend.", _f39_inst_insider),
    ]
    return factors
