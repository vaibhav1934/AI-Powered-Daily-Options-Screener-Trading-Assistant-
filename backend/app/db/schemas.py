"""
Pydantic v2 Schemas
====================
Request/response schemas for all API endpoints.
Mirrors ORM models but enforces the screenshot gate (FR-7):
  - Execution details (entry_price, strike_price, stop_loss) are EXCLUDED
    from response schemas when status == PENDING_CONFIRMATION.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


# ---------------------------------------------------------------------------
# Enums (mirror ORM enums for API contract)
# ---------------------------------------------------------------------------
class ScanStatusSchema(str, enum.Enum):
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    LOCKED = "LOCKED"


class RiskBucketSchema(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH_RISK_HALO = "HIGH_RISK_HALO"


class ListTypeSchema(str, enum.Enum):
    LIST_1 = "LIST_1"
    LIST_2 = "LIST_2"


# ---------------------------------------------------------------------------
# Factor schemas
# ---------------------------------------------------------------------------
class FactorResultSchema(BaseModel):
    """Result of evaluating a single factor for a ticker."""

    model_config = ConfigDict(from_attributes=True)

    factor_id: str = Field(description="Factor identifier (F01–F50)")
    factor_name: str
    layer_number: int = Field(ge=1, le=10)
    triggered: bool
    vetoed: bool
    stubbed: bool = Field(description="True if factor is not yet configured (F1–F39)")
    result_detail: Optional[dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Scan schemas
# ---------------------------------------------------------------------------
class ScanResultBase(BaseModel):
    """Base scan result — always visible regardless of confirmation status."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_date: datetime
    ticker: str
    score: float
    risk_bucket: Optional[RiskBucketSchema] = None
    status: ScanStatusSchema
    list_type: Optional[ListTypeSchema] = None
    veto_rule: Optional[str] = None
    veto_reason: Optional[str] = None
    created_at: datetime


class ScanResultPublic(ScanResultBase):
    """
    Public scan result — includes execution details ONLY when confirmed.
    FR-7: No strike price, entry price, or execution detail is displayed
    for any ticker until a screenshot is attached and user-confirmed.
    """

    # These fields are conditionally included based on status
    entry_price: Optional[float] = Field(default=None, exclude=True)
    strike_price: Optional[float] = Field(default=None, exclude=True)
    stop_loss: Optional[float] = Field(default=None, exclude=True)

    # Factor breakdown
    factor_results_json: Optional[dict[str, Any]] = None
    live_factors_count: int = 0
    stubbed_factors_count: int = 0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def execution_details(self) -> Optional[dict[str, Optional[float]]]:
        """Only expose execution details for CONFIRMED or LOCKED tickers."""
        if self.status == ScanStatusSchema.PENDING_CONFIRMATION:
            return None
        return {
            "entry_price": self.entry_price,
            "strike_price": self.strike_price,
            "stop_loss": self.stop_loss,
        }

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_actionable(self) -> bool:
        """Whether the ticker can be acted upon."""
        return self.status == ScanStatusSchema.CONFIRMED

    @computed_field  # type: ignore[prop-decorator]
    @property
    def price(self) -> Optional[str]:
        if self.factor_results_json and "market_data" in self.factor_results_json:
            val = self.factor_results_json["market_data"].get("price")
            if val is not None:
                return f"{val:.2f}"
        return None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gap(self) -> Optional[str]:
        if self.factor_results_json and "market_data" in self.factor_results_json:
            val = self.factor_results_json["market_data"].get("gap")
            if val is not None:
                sign = "+" if val > 0 else ""
                return f"{sign}{val:.2f}%"
        return None


class ScanTriggerRequest(BaseModel):
    """Request to manually trigger a scan."""

    scan_date: Optional[datetime] = Field(
        default=None, description="Defaults to today if not specified"
    )


class ScanTriggerResponse(BaseModel):
    """Response after triggering a scan."""

    job_id: str
    scan_date: datetime
    status: str = "STARTED"
    message: str = "Scan triggered successfully"


# ---------------------------------------------------------------------------
# Screenshot schemas
# ---------------------------------------------------------------------------
class ScreenshotUploadResponse(BaseModel):
    """Response after uploading a screenshot."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    scan_id: int
    storage_url: str
    file_name: str
    detected_price: Optional[float] = Field(
        default=None, description="FR-9 deferred — always None in v1"
    )
    user_confirmed: bool
    uploaded_at: datetime


class ScreenshotConfirmRequest(BaseModel):
    """Request to confirm a screenshot matches the expected chart."""

    confirmed: bool = Field(description="User confirms the screenshot matches")


class ScreenshotConfirmResponse(BaseModel):
    """Response after confirming a screenshot."""

    scan_id: int
    ticker: str
    previous_status: ScanStatusSchema
    new_status: ScanStatusSchema
    confirmed_at: datetime


# ---------------------------------------------------------------------------
# Watchlist schemas
# ---------------------------------------------------------------------------
class WatchlistFilterParams(BaseModel):
    """Query parameters for filtering the watchlist."""

    list_type: Optional[ListTypeSchema] = None
    risk_bucket: Optional[RiskBucketSchema] = None
    status: Optional[ScanStatusSchema] = None
    max_price: Optional[float] = None
    min_score: Optional[float] = None
    exclude_sectors: Optional[list[str]] = None
    ticker: Optional[str] = None


class WatchlistResponse(BaseModel):
    """Filtered watchlist response."""

    scan_date: datetime
    total_results: int
    live_factors: int
    stubbed_factors: int
    results: list[ScanResultPublic]
    applied_filters: dict[str, Any]
    cutoff_status: CutoffStatusSchema


# ---------------------------------------------------------------------------
# Cutoff schemas
# ---------------------------------------------------------------------------
class CutoffStatusSchema(BaseModel):
    """Current state of entry cutoff enforcement."""

    is_locked: bool = Field(description="Whether new entries are currently locked")
    cutoff_time: str = Field(description="Applicable cutoff time (CST)")
    current_time: str = Field(description="Current server time (CST)")
    is_fomc_day: bool = Field(default=False)
    is_friday: bool = Field(default=False)
    time_remaining_seconds: Optional[int] = Field(
        default=None, description="Seconds until cutoff, None if already locked"
    )


# ---------------------------------------------------------------------------
# Chat schemas
# ---------------------------------------------------------------------------
class ChatMessageRequest(BaseModel):
    """Incoming chat message from the user."""

    message: str = Field(min_length=1, max_length=2000)
    conversation_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """A single chat response chunk (for SSE streaming)."""

    content: str
    is_final: bool = False
    tool_calls: Optional[list[dict[str, Any]]] = None
    citations: Optional[list[dict[str, str]]] = None


# ---------------------------------------------------------------------------
# Audit schemas
# ---------------------------------------------------------------------------
class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    detail: Optional[dict[str, Any]] = None
    timestamp: datetime


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""

    total: int
    page: int
    page_size: int
    entries: list[AuditLogEntry]


# ---------------------------------------------------------------------------
# Scorecard schemas
# ---------------------------------------------------------------------------
class EODScorecardResponse(BaseModel):
    """End-of-day summary scorecard."""

    scan_date: datetime
    total_scanned: int
    total_confirmed: int
    total_locked: int
    total_vetoed: int
    risk_distribution: dict[str, int]  # bucket → count
    veto_summary: list[dict[str, str]]  # [{ticker, rule, reason}]
    factor_coverage: dict[str, int]  # {"live": N, "stubbed": M}


# ---------------------------------------------------------------------------
# StockGlass AI — API Contract (v1) Schemas
# ---------------------------------------------------------------------------
class IndexItemSchema(BaseModel):
    name: str
    value: str
    chg: float
    pct: float


class SupportResistanceLevels(BaseModel):
    support: float
    resistance: float


class StockListItemSchema(BaseModel):
    symbol: str
    name: str
    sector: str
    price: float
    chg: float
    pct: float
    volume: str
    score: float
    earningsSoon: bool
    hardFlags: list[str]
    sparkline: list[float]
    levels: SupportResistanceLevels


class StockListResponseSchema(BaseModel):
    count: int
    total: int
    page: int = 1
    page_size: int = 10
    total_pages: int = 1
    results: list[StockListItemSchema]


class LayerScoreItem(BaseModel):
    layer: str
    value: float


class ReasonItem(BaseModel):
    type: str  # "bull" or "bear"
    code: str  # e.g. "F44"
    text: str


class NewsItemSchema(BaseModel):
    headline: str
    source: str
    publishedAt: str
    url: str
    summary: Optional[str] = None


class StockDetailSchema(BaseModel):
    id: Optional[int] = None
    symbol: str
    name: str
    sector: str
    price: float
    chg: float
    pct: float
    score: float
    hardFlags: list[str]
    levels: SupportResistanceLevels
    layerScores: list[LayerScoreItem]
    reasons: list[ReasonItem]
    news: list[NewsItemSchema]
    newsSummary: Optional[str] = None
    execution_details: Optional[dict[str, Any]] = None


class FactorBreakdownItem(BaseModel):
    code: str
    status: str  # "pass", "neutral", "fail"
    detail: str


class LayerBreakdownItem(BaseModel):
    layer: str
    range: str  # e.g. "F1-F5"
    factors: list[FactorBreakdownItem]


class FactorSummarySchema(BaseModel):
    pass_: int = Field(alias="pass", default=0)
    neutral: int = 0
    fail: int = 0

    model_config = ConfigDict(populate_by_name=True)


class FullFactorBreakdownSchema(BaseModel):
    symbol: str
    summary: FactorSummarySchema
    layers: list[LayerBreakdownItem]


# Paper Trading Position Schemas
class PositionCreateSchema(BaseModel):
    symbol: str
    qty: float
    entryPrice: float


class PositionItemSchema(BaseModel):
    id: str
    symbol: str
    qty: float
    entryPrice: float
    currentPrice: Optional[float] = None
    unrealizedPnl: Optional[float] = None
    realizedPnl: Optional[float] = None
    exitPrice: Optional[float] = None
    status: str
    openedAt: Optional[str] = None
    closedAt: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PositionListResponseSchema(BaseModel):
    results: list[PositionItemSchema]
