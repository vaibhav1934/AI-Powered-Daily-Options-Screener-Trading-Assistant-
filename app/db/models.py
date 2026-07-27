"""
Database ORM Models
====================
PostgreSQL schema — 5 tables:
  1. daily_scans     — Per-ticker scan results with status lifecycle
  2. factor_logs     — Granular factor breakdown per scan (F1–F50)
  3. screenshots     — Screenshot audit trail, per ticker per day
  4. audit_logs      — All state changes, filter edits, confirmations
  5. market_data_cache — Postgres-backed cache for market data API responses

All times are server-authoritative, stored in UTC, evaluated in America/Chicago.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ScanStatus(str, enum.Enum):
    """Lifecycle of a scan entry."""

    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    LOCKED = "LOCKED"


class RiskBucket(str, enum.Enum):
    """Risk/reward categorization."""

    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH_RISK_HALO = "HIGH_RISK_HALO"


class ListType(str, enum.Enum):
    """Watchlist assignment."""

    LIST_1 = "LIST_1"  # Daily
    LIST_2 = "LIST_2"  # Monthly accumulation


class FactorStatus(str, enum.Enum):
    """Whether a factor is live or stubbed."""

    LIVE = "LIVE"
    UNCONFIGURED = "UNCONFIGURED"


class AuditAction(str, enum.Enum):
    """Types of auditable actions."""

    SCAN_TRIGGERED = "SCAN_TRIGGERED"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    SCREENSHOT_UPLOADED = "SCREENSHOT_UPLOADED"
    SCREENSHOT_CONFIRMED = "SCREENSHOT_CONFIRMED"
    STATUS_CHANGED = "STATUS_CHANGED"
    FILTER_APPLIED = "FILTER_APPLIED"
    FILTER_REMOVED = "FILTER_REMOVED"
    CUTOFF_ENFORCED = "CUTOFF_ENFORCED"
    VETO_APPLIED = "VETO_APPLIED"


# ---------------------------------------------------------------------------
# 1. daily_scans
# ---------------------------------------------------------------------------
class DailyScan(Base):
    """
    Per-ticker scan result for a given day.
    Status lifecycle: PENDING_CONFIRMATION → CONFIRMED → LOCKED
    Execution details (price/strike) are NOT returned for PENDING_CONFIRMATION status (FR-7).
    """

    __tablename__ = "daily_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_bucket: Mapped[Optional[RiskBucket]] = mapped_column(
        Enum(RiskBucket, name="risk_bucket_enum"), nullable=True
    )
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status_enum"),
        nullable=False,
        default=ScanStatus.PENDING_CONFIRMATION,
    )
    list_type: Mapped[Optional[ListType]] = mapped_column(
        Enum(ListType, name="list_type_enum"), nullable=True
    )
    factor_results_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    veto_rule: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    veto_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Execution details — ONLY returned when status != PENDING_CONFIRMATION
    entry_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    strike_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    factor_logs: Mapped[list["FactorLog"]] = relationship(
        "FactorLog", back_populates="scan", cascade="all, delete-orphan"
    )
    screenshots: Mapped[list["Screenshot"]] = relationship(
        "Screenshot", back_populates="scan", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_daily_scans_date_ticker", "scan_date", "ticker", unique=True),
        Index("ix_daily_scans_status", "status"),
        Index("ix_daily_scans_risk_bucket", "risk_bucket"),
    )


# ---------------------------------------------------------------------------
# 2. factor_logs
# ---------------------------------------------------------------------------
class FactorLog(Base):
    """
    Granular factor breakdown per scan entry.
    Maps factor IDs (F1–F50) to their evaluation result for a specific ticker/scan.
    Includes a stubbed flag for F1–F39 (unconfigured factors).
    """

    __tablename__ = "factor_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    factor_id: Mapped[str] = mapped_column(
        String(10), nullable=False
    )  # "F01" .. "F50"
    factor_name: Mapped[str] = mapped_column(String(100), nullable=False)
    layer_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1–10
    triggered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    vetoed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    stubbed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )  # True for F1–F39 until defined
    result_detail_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan: Mapped["DailyScan"] = relationship("DailyScan", back_populates="factor_logs")

    __table_args__ = (
        Index("ix_factor_logs_scan_factor", "scan_id", "factor_id", unique=True),
        Index("ix_factor_logs_factor_id", "factor_id"),
    )


# ---------------------------------------------------------------------------
# 3. screenshots
# ---------------------------------------------------------------------------
class Screenshot(Base):
    """
    Screenshot audit trail. Each upload is linked to a specific scan entry.
    Execution details are gated behind user_confirmed=True (FR-7, FR-8).
    detected_price is nullable — FR-9 (vision extraction) deferred to v1.1.
    """

    __tablename__ = "screenshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_scans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False, default="image/png")

    # FR-9 vision extraction — deferred, nullable
    detected_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    scan: Mapped["DailyScan"] = relationship("DailyScan", back_populates="screenshots")


# ---------------------------------------------------------------------------
# 4. audit_logs
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """
    Timestamped audit trail for all state changes, filter edits,
    screenshot confirmations, veto applications, and cutoff enforcements.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action_enum"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "scan", "screenshot", "filter"
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # Single-user v1, future-proofed
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )


# ---------------------------------------------------------------------------
# 5. market_data_cache
# ---------------------------------------------------------------------------
class MarketDataCache(Base):
    """
    Postgres-backed cache for market data API responses.
    Required to stay within Alpha Vantage's 25 calls/day free tier.
    Serves stale-but-labeled data rather than re-hitting the API.
    """

    __tablename__ = "market_data_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "finnhub" or "alpha_vantage"
    endpoint: Mapped[str] = mapped_column(String(200), nullable=False)
    params_hash: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # SHA-256 of serialized params
    response_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ttl_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        Index(
            "ix_market_data_cache_lookup",
            "provider",
            "endpoint",
            "params_hash",
            unique=True,
        ),
    )


# ---------------------------------------------------------------------------
# 6. positions (Paper Trading)
# ---------------------------------------------------------------------------
class PositionStatus(str, enum.Enum):
    """Lifecycle of a paper trading position."""

    OPEN = "open"
    CLOSED = "closed"


class Position(Base):
    """
    Paper trading positions for audit and performance tracking.
    Server-side P&L calculation ensures win rate and returns cannot drift.
    """

    __tablename__ = "positions"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[PositionStatus] = mapped_column(
        Enum(PositionStatus, name="position_status_enum"),
        nullable=False,
        default=PositionStatus.OPEN,
        index=True,
    )
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    realized_pnl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
