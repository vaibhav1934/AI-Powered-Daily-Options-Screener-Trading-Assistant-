"""
Screenshot API Routes
=======================
Upload and confirm TradingView screenshots.
FR-7: Gate execution details behind confirmation.
FR-8: Per-ticker, per-day audit trail.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_api_key
from app.db.session import get_db
from app.services import screenshot_service

router = APIRouter(prefix="/screenshots", tags=["screenshots"])


@router.post("/{scan_id}")
async def upload_screenshot(
    scan_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """
    Upload a TradingView screenshot for a scan entry.
    FR-8: stored per-ticker, per-day.
    """
    # In production, upload to Supabase Storage and get URL
    # For now, we store a placeholder URL
    storage_url = f"/storage/screenshots/{scan_id}/{file.filename}"

    screenshot = await screenshot_service.upload_screenshot(
        session=session,
        scan_id=scan_id,
        storage_url=storage_url,
        file_name=file.filename or "screenshot.png",
        file_size_bytes=file.size,
        content_type=file.content_type or "image/png",
    )

    return {
        "id": screenshot.id,
        "scan_id": screenshot.scan_id,
        "storage_url": screenshot.storage_url,
        "file_name": screenshot.file_name,
        "user_confirmed": screenshot.user_confirmed,
        "uploaded_at": screenshot.uploaded_at,
    }


@router.post("/{screenshot_id}/confirm")
async def confirm_screenshot(
    screenshot_id: int,
    session: AsyncSession = Depends(get_db),
    _api_key: str = Depends(verify_api_key),
):
    """
    Confirm a screenshot matches the expected chart.
    FR-7: State transition PENDING_CONFIRMATION → CONFIRMED.
    Enforces entry cutoff — cannot confirm past cutoff time.
    """
    result = await screenshot_service.confirm_screenshot(session, screenshot_id)
    return result
