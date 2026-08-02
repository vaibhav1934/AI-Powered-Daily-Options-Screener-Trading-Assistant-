"""
Factor Base Protocol & Data Models
====================================
Every factor (F1–F50) implements the FactorProtocol.
Pure, deterministic evaluation — no LLM calls.
"""

from __future__ import annotations

import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel


class FactorStatus(str, enum.Enum):
    """Whether a factor is live (implemented) or unconfigured (stubbed)."""

    LIVE = "LIVE"
    UNCONFIGURED = "UNCONFIGURED"


class FactorAction(str, enum.Enum):
    """Action a factor can take on a ticker."""

    PASS = "PASS"  # No effect
    FLAG = "FLAG"  # Informational flag
    DOWNGRADE = "DOWNGRADE"  # Reduce conviction score
    VETO = "VETO"  # Block the ticker entirely
    BLOCK_PUTS = "BLOCK_PUTS"  # Block put recommendations specifically
    REDUCE_SIZE = "REDUCE_SIZE"  # Reduce position sizing
    LOCK = "LOCK"  # Lock entries (time-based)


class FactorResult(BaseModel):
    """Result of evaluating a single factor for a single ticker."""

    factor_id: str  # "F01" .. "F50"
    factor_name: str
    layer_number: int  # Which layer this factor belongs to (1–10)
    status: FactorStatus
    triggered: bool  # Whether the factor's trigger condition was met
    action: FactorAction = FactorAction.PASS
    vetoed: bool = False  # Whether this factor vetoed the ticker
    stubbed: bool = False  # True for unconfigured factors (F1–F39)
    detail: str = ""  # Human-readable explanation
    metadata: dict[str, Any] = {}  # Additional structured data


@dataclass
class ScanContext:
    """
    Context passed through the scanning pipeline.
    Each layer and factor receives this to evaluate against.
    Contains all market data needed for deterministic evaluation.
    """

    ticker: str
    scan_date: str  # ISO format date

    # Quote data
    current_price: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    previous_close: float = 0.0
    volume: int = 0
    change_percent: float = 0.0

    # Earnings data
    has_earnings_today: bool = False
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    is_after_hours_beat: bool = False
    earnings_within_window: bool = False

    # Technical indicators
    rsi: Optional[float] = None
    sma_50: Optional[float] = None
    sma_200: Optional[float] = None
    is_at_ath: bool = False
    gap_present: bool = False
    gap_hold_valid: bool = False
    mtf_trend_aligned: bool = False
    relative_volume: Optional[float] = None
    volume_profile_state: Optional[str] = None
    volume_profile_hvn: Optional[float] = None
    volume_profile_lvn: Optional[float] = None

    # Macro/tape context
    kospi_change_percent: float = 0.0
    ceasefire_headline: bool = False
    is_fomc_day: bool = False
    fomc_time_past_1245: bool = False
    dxy_change_5d: Optional[float] = None
    ust2y_yield: Optional[float] = None
    ust10y_yield: Optional[float] = None
    curve_10y_2y_bps: Optional[float] = None
    curve_change_5d_bps: Optional[float] = None
    hyg_lqd_ratio_change_5d: Optional[float] = None
    gld_change_5d: Optional[float] = None
    dax_change_percent: Optional[float] = None
    ftse_change_percent: Optional[float] = None
    vix_spot: Optional[float] = None
    vix9d: Optional[float] = None
    vix3m: Optional[float] = None
    vix_term_slope: Optional[float] = None
    overnight_futures_gap_pct: Optional[float] = None
    overnight_outside_prior_range: Optional[bool] = None
    fed_policy_prob_proxy: Optional[float] = None
    central_bank_surprise_proxy: bool = False
    central_bank_surprise_score: Optional[float] = None

    # Ecosystem
    ecosystem_partner_10pct_move: bool = False
    analyst_day_catalyst: bool = False
    product_launch_catalyst: bool = False
    fda_regulatory_catalyst: bool = False
    index_reconstitution_catalyst: bool = False
    sector_macro_catalyst: bool = False

    # Sector info
    sector: str = ""
    industry: str = ""
    name: str = ""  # Company full name from profile
    change: float = 0.0  # Dollar change (not percent)
    volume_str: str = ""  # Pre-formatted volume string (e.g. "25.4M")
    sector_etf_symbol: Optional[str] = None
    sector_rs_5d: Optional[float] = None
    sector_rs_20d: Optional[float] = None
    ticker_sector_corr_20d: Optional[float] = None
    idiosyncratic_alpha_20d: Optional[float] = None
    sector_flow_score: Optional[float] = None

    # Analyst data
    analyst_rating_change: bool = False
    analyst_firm_tier: Optional[int] = None  # 1=top tier, 3=low tier

    # Options mechanics
    iv_rank_1y: Optional[float] = None
    iv_crush_risk: Optional[str] = None
    put_call_oi_ratio: Optional[float] = None
    skew_signal: Optional[str] = None
    option_open_interest: Optional[float] = None
    option_volume: Optional[float] = None
    option_bid: Optional[float] = None
    option_ask: Optional[float] = None
    option_mid_price: Optional[float] = None
    option_delta: Optional[float] = None
    option_theta_daily: Optional[float] = None
    option_dte: Optional[int] = None
    option_volume_oi_ratio: Optional[float] = None
    dealer_gamma_regime_proxy: Optional[str] = None

    # Fundamentals (long-term engine inputs)
    revenue_growth: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    free_cash_flow: Optional[float] = None
    debt_to_equity: Optional[float] = None
    interest_coverage: Optional[float] = None
    insider_ownership: Optional[float] = None
    institutional_ownership: Optional[float] = None
    return_on_equity: Optional[float] = None
    return_on_assets: Optional[float] = None
    shares_outstanding_change: Optional[float] = None
    short_ratio: Optional[float] = None
    short_percent_float: Optional[float] = None
    whisper_eps_gap_proxy: Optional[float] = None
    guidance_revision_trend_4q: Optional[float] = None
    retail_sentiment_score: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    peg_ratio: Optional[float] = None

    # Portfolio-fit context
    portfolio_sector_exposure: Optional[float] = None
    portfolio_underweight_sector: Optional[bool] = None

    # SEC filings
    has_recent_shelf_filing: bool = False
    near_ath_proximity: bool = False
    shelf_filing_date: Optional[str] = None
    shelf_form_type: Optional[str] = None
    edgar_check_status: Optional[str] = None

    # Time context
    current_time_cst: str = ""
    is_past_cutoff: bool = False
    is_friday: bool = False

    # Running state — accumulated by layers
    conviction_score: float = 0.0
    is_vetoed: bool = False
    veto_rule: Optional[str] = None
    veto_reason: Optional[str] = None
    triggered_factors: list[str] = field(default_factory=list)
    factor_results: list[FactorResult] = field(default_factory=list)
    is_halo_trade: bool = False


class BaseFactor(ABC):
    """
    Abstract base class for all factors.
    Subclasses must implement evaluate().
    All evaluation is pure and deterministic — no LLM, no network calls.
    """

    factor_id: str  # "F01" .. "F50"
    name: str
    description: str
    layer: int  # Which layer this belongs to (1–10)
    status: FactorStatus = FactorStatus.LIVE

    @abstractmethod
    def evaluate(self, ctx: ScanContext) -> FactorResult:
        """
        Evaluate this factor against the scan context.
        Must be pure, deterministic, side-effect-free.
        """
        ...

    def _pass(self, detail: str = "") -> FactorResult:
        """Convenience: return a PASS result."""
        return FactorResult(
            factor_id=self.factor_id,
            factor_name=self.name,
            layer_number=self.layer,
            status=self.status,
            triggered=False,
            action=FactorAction.PASS,
            detail=detail or f"{self.name}: no trigger condition met.",
        )

    def _trigger(
        self,
        action: FactorAction,
        detail: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> FactorResult:
        """Convenience: return a triggered result with the given action."""
        return FactorResult(
            factor_id=self.factor_id,
            factor_name=self.name,
            layer_number=self.layer,
            status=self.status,
            triggered=True,
            action=action,
            vetoed=action == FactorAction.VETO,
            detail=detail,
            metadata=metadata or {},
        )
