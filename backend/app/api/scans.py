"""
Scan API Routes
=================
Endpoints for triggering scans and retrieving results.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import RiskBucket, ScanStatus
from app.services import scan_service

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("/trigger")
async def trigger_scan(
    scan_date: Optional[date] = None,
    session: AsyncSession = Depends(get_db),
):
    """Manually trigger a full-universe scan."""
    result = await scan_service.trigger_scan(session, scan_date)
    return result


@router.get("/{scan_date}")
async def get_scan_results(
    scan_date: date,
    status: Optional[ScanStatus] = Query(None),
    risk_bucket: Optional[RiskBucket] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """
    Get scan results for a specific date.
    FR-7: Execution details filtered out for unconfirmed tickers.
    """
    results = await scan_service.get_scan_results(
        session, scan_date, status, risk_bucket
    )
    # FR-7 enforcement is handled by the Pydantic schema's computed_field
    return {"scan_date": scan_date.isoformat(), "results": results}
