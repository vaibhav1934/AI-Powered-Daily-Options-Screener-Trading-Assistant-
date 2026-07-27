"""
Screenshot Service
====================
Upload, store, and confirm TradingView screenshots.
FR-7: No execution details until screenshot confirmed.
FR-8: Screenshots stored per-ticker, per-day (audit trail).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InvalidStateTransitionError,
    ScreenshotNotFoundError,
    ScreenshotRequiredError,
)
from app.core.time_gate import enforce_entry_cutoff
from app.db.models import AuditAction, AuditLog, DailyScan, ScanStatus, Screenshot

logger = logging.getLogger(__name__)


async def upload_screenshot(
    session: AsyncSession,
    scan_id: int,
    storage_url: str,
    file_name: str,
    file_size_bytes: Optional[int] = None,
    content_type: str = "image/png",
) -> Screenshot:
    """
    Upload a screenshot for a scan entry.
    FR-8: stored per-ticker, per-day.
    """
    # Verify scan exists
    scan = await session.get(DailyScan, scan_id)
    if not scan:
        raise ScreenshotNotFoundError(message=f"Scan ID {scan_id} not found")

    screenshot = Screenshot(
        scan_id=scan_id,
        storage_url=storage_url,
        file_name=file_name,
        file_size_bytes=file_size_bytes,
        content_type=content_type,
        detected_price=None,  # FR-9 deferred to v1.1
        user_confirmed=False,
    )
    session.add(screenshot)

    # Audit
    audit = AuditLog(
        action=AuditAction.SCREENSHOT_UPLOADED,
        entity_type="screenshot",
        entity_id=scan_id,
        detail_json={
            "ticker": scan.ticker,
            "file_name": file_name,
            "storage_url": storage_url,
        },
    )
    session.add(audit)
    await session.flush()

    logger.info("Screenshot uploaded: scan_id=%d, file=%s", scan_id, file_name)
    return screenshot


async def confirm_screenshot(
    session: AsyncSession,
    screenshot_id: int,
) -> dict[str, Any]:
    """
    Confirm a screenshot matches the expected chart.
    FR-7: State transitions from PENDING_CONFIRMATION → CONFIRMED.
    Also enforces entry cutoff — cannot confirm past cutoff time.
    """
    screenshot = await session.get(Screenshot, screenshot_id)
    if not screenshot:
        raise ScreenshotNotFoundError(message=f"Screenshot ID {screenshot_id} not found")

    scan = await session.get(DailyScan, screenshot.scan_id)
    if not scan:
        raise ScreenshotNotFoundError(message=f"Scan for screenshot not found")

    # Enforce cutoff — cannot confirm past entry cutoff
    enforce_entry_cutoff()

    # Validate state transition (allow confirming screenshots on already auto-confirmed scans)
    if scan.status not in (ScanStatus.PENDING_CONFIRMATION, ScanStatus.CONFIRMED):
        raise InvalidStateTransitionError(
            ticker=scan.ticker,
            current_status=scan.status.value,
            target_status=ScanStatus.CONFIRMED.value,
        )

    # Confirm
    previous_status = scan.status
    screenshot.user_confirmed = True
    screenshot.confirmed_at = datetime.now(timezone.utc)
    scan.status = ScanStatus.CONFIRMED

    # Audit
    audit = AuditLog(
        action=AuditAction.SCREENSHOT_CONFIRMED,
        entity_type="screenshot",
        entity_id=screenshot_id,
        detail_json={
            "ticker": scan.ticker,
            "previous_status": previous_status.value,
            "new_status": ScanStatus.CONFIRMED.value,
        },
    )
    session.add(audit)
    await session.flush()

    logger.info(
        "Screenshot confirmed: ticker=%s, status %s → %s",
        scan.ticker,
        previous_status.value,
        ScanStatus.CONFIRMED.value,
    )

    return {
        "scan_id": scan.id,
        "ticker": scan.ticker,
        "previous_status": previous_status.value,
        "new_status": ScanStatus.CONFIRMED.value,
        "confirmed_at": screenshot.confirmed_at.isoformat(),
    }


async def check_screenshot_gate(
    session: AsyncSession,
    scan_id: int,
) -> bool:
    """
    Check if a scan entry has a confirmed screenshot.
    FR-7: execution details are gated behind this check.
    """
    result = await session.execute(
        select(Screenshot).where(
            Screenshot.scan_id == scan_id,
            Screenshot.user_confirmed == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none() is not None
