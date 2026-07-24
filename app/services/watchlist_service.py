"""
Watchlist Service
===================
Filtering, bucketing, and list assembly for the watchlist view.
FR-12: Buckets re-computed live if underlying data changes intraday.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyScan, ListType, RiskBucket, ScanStatus

logger = logging.getLogger(__name__)


async def get_watchlist(
    session: AsyncSession,
    scan_date: date,
    list_type: Optional[ListType] = None,
    risk_bucket: Optional[RiskBucket] = None,
    status: Optional[ScanStatus] = None,
    max_price: Optional[float] = None,
    min_score: Optional[float] = None,
    ticker: Optional[str] = None,
) -> list[DailyScan]:
    """Get filtered watchlist for a given date."""
    start_dt = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)

    stmt = select(DailyScan).where(DailyScan.scan_date >= start_dt)

    if list_type:
        stmt = stmt.where(DailyScan.list_type == list_type)
    if risk_bucket:
        stmt = stmt.where(DailyScan.risk_bucket == risk_bucket)
    if status:
        stmt = stmt.where(DailyScan.status == status)
    if min_score is not None:
        stmt = stmt.where(DailyScan.score >= min_score)
    if ticker:
        stmt = stmt.where(DailyScan.ticker.ilike(f"%{ticker}%"))

    # Price filter would need join to quote data — deferred to when
    # we have live price data stored alongside scans
    # if max_price is not None: ...

    stmt = stmt.order_by(DailyScan.score.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_risk_bucket_distribution(
    session: AsyncSession,
    scan_date: date,
) -> dict[str, int]:
    """Get count of tickers per risk bucket for a given date."""
    start_dt = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)

    stmt = (
        select(DailyScan.risk_bucket, func.count(DailyScan.id))
        .where(DailyScan.scan_date >= start_dt)
        .group_by(DailyScan.risk_bucket)
    )
    result = await session.execute(stmt)
    return {
        (row[0].value if row[0] else "UNASSIGNED"): row[1]
        for row in result.all()
    }


async def get_status_distribution(
    session: AsyncSession,
    scan_date: date,
) -> dict[str, int]:
    """Get count of tickers per status for a given date."""
    start_dt = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)

    stmt = (
        select(DailyScan.status, func.count(DailyScan.id))
        .where(DailyScan.scan_date >= start_dt)
        .group_by(DailyScan.status)
    )
    result = await session.execute(stmt)
    return {row[0].value: row[1] for row in result.all()}
