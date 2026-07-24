"""
Scan Service
==============
Orchestrates scan execution and database persistence.
Bridges the deterministic framework engine with the API/DB layer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time_gate import get_cst_now, get_cutoff_status, is_fomc_day, is_friday, is_past_cutoff
from app.db.models import AuditAction, AuditLog, DailyScan, FactorLog, ListType, RiskBucket, ScanStatus
from app.framework.engine import run_full_scan
from app.framework.factors.registry import factor_registry

logger = logging.getLogger(__name__)


async def trigger_scan(
    session: AsyncSession,
    scan_date: Optional[date] = None,
) -> dict[str, Any]:
    """
    Trigger a full-universe scan for the given date.
    Returns a job summary with scan results.
    """
    scan_date = scan_date or date.today()
    job_id = str(uuid.uuid4())

    logger.info("Scan triggered: job_id=%s, date=%s", job_id, scan_date)

    # Log audit
    audit = AuditLog(
        action=AuditAction.SCAN_TRIGGERED,
        entity_type="scan",
        detail_json={"job_id": job_id, "scan_date": scan_date.isoformat()},
    )
    session.add(audit)

    # Build macro context from server-authoritative time
    now = get_cst_now()
    macro_context = {
        "kospi_change_percent": 0.0,  # TODO: fetch from market data
        "ceasefire_headline": False,  # TODO: fetch from news API
        "is_fomc_day": is_fomc_day(now),
        "fomc_time_past_1245": is_fomc_day(now) and now.hour >= 12 and now.minute >= 45,
        "current_time_cst": now.strftime("%I:%M %p"),
        "is_past_cutoff": is_past_cutoff(now),
        "is_friday": is_friday(now),
    }

    # TODO: In production, fetch tickers from Finnhub earnings calendar
    # and enrich with quote data, technicals, etc.
    # For now, we run with an empty list — the engine handles it gracefully.
    tickers: list[dict[str, Any]] = []

    # Run deterministic scan
    scan_results = run_full_scan(tickers, macro_context, scan_date)

    # Persist results
    persisted_count = 0
    for ctx in scan_results:
        # Map risk bucket
        risk_bucket = _map_risk_bucket(ctx)
        list_type = _map_list_type(ctx)

        scan_entry = DailyScan(
            scan_date=datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc),
            ticker=ctx.ticker,
            score=ctx.conviction_score,
            risk_bucket=risk_bucket,
            status=ScanStatus.LOCKED if ctx.is_vetoed or macro_context["is_past_cutoff"] else ScanStatus.PENDING_CONFIRMATION,
            list_type=list_type,
            factor_results_json={
                "results": [r.model_dump() for r in ctx.factor_results],
                "coverage": factor_registry.coverage_report(),
            },
            veto_rule=ctx.veto_rule,
            veto_reason=ctx.veto_reason,
        )
        session.add(scan_entry)
        await session.flush()

        # Persist factor logs
        for fr in ctx.factor_results:
            factor_log = FactorLog(
                scan_id=scan_entry.id,
                factor_id=fr.factor_id,
                factor_name=fr.factor_name,
                layer_number=fr.layer_number,
                triggered=fr.triggered,
                vetoed=fr.vetoed,
                stubbed=fr.stubbed,
                result_detail_json=fr.model_dump(),
            )
            session.add(factor_log)

        persisted_count += 1

    # Audit completion
    audit_complete = AuditLog(
        action=AuditAction.SCAN_COMPLETED,
        entity_type="scan",
        detail_json={
            "job_id": job_id,
            "scan_date": scan_date.isoformat(),
            "tickers_scanned": persisted_count,
            "factor_coverage": factor_registry.coverage_report(),
        },
    )
    session.add(audit_complete)
    await session.flush()

    return {
        "job_id": job_id,
        "scan_date": scan_date.isoformat(),
        "tickers_scanned": persisted_count,
        "status": "COMPLETED",
        "factor_coverage": factor_registry.coverage_report(),
    }


async def get_scan_results(
    session: AsyncSession,
    scan_date: date,
    status_filter: Optional[ScanStatus] = None,
    risk_bucket_filter: Optional[RiskBucket] = None,
) -> list[DailyScan]:
    """Get scan results for a given date with optional filters."""
    stmt = select(DailyScan).where(
        DailyScan.scan_date >= datetime.combine(scan_date, datetime.min.time(), tzinfo=timezone.utc),
        DailyScan.scan_date < datetime.combine(
            scan_date.replace(day=scan_date.day + 1) if scan_date.day < 28 else scan_date,
            datetime.min.time(),
            tzinfo=timezone.utc,
        ),
    )

    if status_filter:
        stmt = stmt.where(DailyScan.status == status_filter)
    if risk_bucket_filter:
        stmt = stmt.where(DailyScan.risk_bucket == risk_bucket_filter)

    stmt = stmt.order_by(DailyScan.score.desc())
    result = await session.execute(stmt)
    return list(result.scalars().all())


def _map_risk_bucket(ctx: Any) -> Optional[RiskBucket]:
    """Map ScanContext to RiskBucket enum."""
    from app.framework.scoring import assign_risk_bucket
    bucket = assign_risk_bucket(ctx.conviction_score, ctx)
    return bucket


def _map_list_type(ctx: Any) -> Optional[ListType]:
    """Map ScanContext to ListType enum."""
    from app.framework.scoring import assign_list_type
    lt = assign_list_type(ctx)
    return ListType.LIST_1 if lt == "LIST_1" else ListType.LIST_2
