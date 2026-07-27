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
import base64
import logging
import re

from app.db.session import get_db
from app.services import screenshot_service
from app.core.config import get_settings, AIProvider

logger = logging.getLogger(__name__)

async def extract_price_from_image(image_bytes: bytes, mime_type: str) -> float | None:
    settings = get_settings()
    
    # We only implement OCR for Anthropic in v1 per PRD architecture preference
    if settings.ai.resolved_provider != AIProvider.ANTHROPIC:
        return None
        
    try:
        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=settings.ai.anthropic_api_key)
        b64_data = base64.b64encode(image_bytes).decode('utf-8')
        
        # fallback to image/png if generic application/octet-stream
        valid_mime = mime_type if mime_type in ["image/jpeg", "image/png", "image/gif", "image/webp"] else "image/png"
        
        msg = await client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=50,
            temperature=0.0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract the current market price of the stock from this TradingView screenshot. Respond ONLY with the numerical value (e.g. 150.25). No other text or currency symbols."},
                        {"type": "image", "source": {"type": "base64", "media_type": valid_mime, "data": b64_data}}
                    ]
                }
            ]
        )
        text = msg.content[0].text.strip()
        match = re.search(r'\d+\.\d+', text)
        if match:
            return float(match.group())
        return float(text.replace('$', '').replace(',', ''))
    except Exception as e:
        logger.warning(f"Vision OCR failed: {e}")
        return None

router = APIRouter(prefix="/screenshots", tags=["screenshots"])


@router.post("/{scan_id}")
async def upload_screenshot(
    scan_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
):
    """
    Upload a TradingView screenshot for a scan entry.
    FR-8: stored per-ticker, per-day.
    """
    # In production, upload to Supabase Storage and get URL
    # For now, we store a placeholder URL
    storage_url = f"/storage/screenshots/{scan_id}/{file.filename}"
    
    content_bytes = await file.read()
    detected_price = await extract_price_from_image(content_bytes, file.content_type or "image/png")

    screenshot = await screenshot_service.upload_screenshot(
        session=session,
        scan_id=scan_id,
        storage_url=storage_url,
        file_name=file.filename or "screenshot.png",
        file_size_bytes=file.size,
        content_type=file.content_type or "image/png",
    )
    
    # Update the detected price if vision succeeded
    if detected_price is not None:
        screenshot.detected_price = detected_price
        await session.flush()

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
):
    """
    Confirm a screenshot matches the expected chart.
    FR-7: State transition PENDING_CONFIRMATION → CONFIRMED.
    Enforces entry cutoff — cannot confirm past cutoff time.
    """
    result = await screenshot_service.confirm_screenshot(session, screenshot_id)
    return result
