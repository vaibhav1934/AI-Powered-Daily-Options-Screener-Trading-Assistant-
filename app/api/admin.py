"""
Admin API Routes
==================
Audit logs, scorecard, and system status endpoints.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog
from app.db.session import get_db
from app.framework.factors.registry import factor_registry
from app.services import scorecard_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/scorecard/{scan_date}")
async def get_scorecard(
    scan_date: date,
    session: AsyncSession = Depends(get_db),
):
    """Get end-of-day scorecard for a given date."""
    return await scorecard_service.generate_scorecard(session, scan_date)


@router.get("/audit-logs")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    entity_type: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db),
):
    """Get paginated audit logs."""
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc())

    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(stmt)
    entries = list(result.scalars().all())

    return {
        "page": page,
        "page_size": page_size,
        "entries": entries,
    }


@router.get("/factor-coverage")
async def get_factor_coverage(
):
    """Get factor coverage report — live vs. stubbed factors."""
    return factor_registry.coverage_report()
