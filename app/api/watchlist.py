"""
Watchlist API Routes
======================
Filtered watchlist views with risk bucket and status filters.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.core.time_gate import get_cutoff_status
from app.db.models import ListType, RiskBucket, ScanStatus
from app.db.session import get_db
from app.services import watchlist_service

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/")
async def get_watchlist(
    scan_date: Optional[date] = Query(None, description="Defaults to today"),
    list_type: Optional[ListType] = Query(None),
    risk_bucket: Optional[RiskBucket] = Query(None),
    status: Optional[ScanStatus] = Query(None),
    min_score: Optional[float] = Query(None),
    ticker: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """Get filtered watchlist for a given date."""
    scan_date = scan_date or date.today()

    results = await watchlist_service.get_watchlist(
        session=session,
        scan_date=scan_date,
        list_type=list_type,
        risk_bucket=risk_bucket,
        status=status,
        min_score=min_score,
        ticker=ticker,
    )

    risk_dist = await watchlist_service.get_risk_bucket_distribution(session, scan_date)
    cutoff = get_cutoff_status()

    return {
        "scan_date": scan_date.isoformat(),
        "total_results": len(results),
        "risk_distribution": risk_dist,
        "cutoff_status": cutoff.model_dump(),
        "results": results,
    }


@router.get("/cutoff")
async def get_cutoff_status_endpoint(
    _api_key: str = Depends(verify_api_key),
):
    """Get the current cutoff status (server-authoritative CST)."""
    return get_cutoff_status().model_dump()
