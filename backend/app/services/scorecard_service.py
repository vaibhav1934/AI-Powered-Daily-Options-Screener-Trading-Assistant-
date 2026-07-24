"""
EOD Scorecard Service
=======================
End-of-day summary: what fired, what was taken, what was vetoed and why.
FR-7 context: scorecard respects screenshot gate.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailyScan, FactorLog, ScanStatus
from app.framework.factors.registry import factor_registry

logger = logging.getLogger(__name__)


async def generate_scorecard(
    session: AsyncSession,
    scan_date: date,
) -> dict[str, Any]:
    """Generate the end-of-day scorecard for a given date."""
    start_dt = datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc)

    # Get all scans for the date
    result = await session.execute(
        select(DailyScan).where(DailyScan.scan_date >= start_dt)
    )
    scans = list(result.scalars().all())

    total = len(scans)
    confirmed = sum(1 for s in scans if s.status == ScanStatus.CONFIRMED)
    locked = sum(1 for s in scans if s.status == ScanStatus.LOCKED)
    pending = sum(1 for s in scans if s.status == ScanStatus.PENDING_CONFIRMATION)
    vetoed = sum(1 for s in scans if s.veto_rule is not None)

    # Risk distribution
    risk_dist: dict[str, int] = {}
    for scan in scans:
        bucket = scan.risk_bucket.value if scan.risk_bucket else "UNASSIGNED"
        risk_dist[bucket] = risk_dist.get(bucket, 0) + 1

    # Veto summary
    veto_summary = [
        {
            "ticker": s.ticker,
            "rule": s.veto_rule or "unknown",
            "reason": s.veto_reason or "no reason recorded",
        }
        for s in scans
        if s.veto_rule
    ]

    # Factor coverage
    coverage = factor_registry.coverage_report()

    return {
        "scan_date": scan_date.isoformat(),
        "total_scanned": total,
        "total_confirmed": confirmed,
        "total_locked": locked,
        "total_pending": pending,
        "total_vetoed": vetoed,
        "risk_distribution": risk_dist,
        "veto_summary": veto_summary,
        "factor_coverage": coverage,
    }
