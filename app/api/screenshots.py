"""
Screenshot API Routes
=======================
Upload and confirm TradingView & Options Chain screenshots.
FR-7: Gate execution details behind confirmation.
FR-8: Per-ticker, per-day audit trail.
Vision AI Options Chain Scanner: Dual Gemini & Anthropic OCR/extraction.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
import base64
import logging
import re
import json
import httpx
from typing import Any, Optional

from app.db.session import get_db
from app.db.models import DailyScan
from app.services import screenshot_service
from app.core.config import get_settings, AIProvider

logger = logging.getLogger(__name__)

async def call_vision_model(prompt: str, image_bytes: bytes, mime_type: str, max_tokens: int = 500) -> str | None:
    settings = get_settings()
    provider = settings.ai.resolved_provider
    model_name = settings.ai.resolved_model_name
    b64_data = base64.b64encode(image_bytes).decode("utf-8")
    valid_mime = mime_type if mime_type in ["image/jpeg", "image/png", "image/gif", "image/webp"] else "image/png"

    if provider == AIProvider.GEMINI:
        api_key = settings.ai.gemini_api_key
        if not api_key:
            logger.warning("GEMINI_API_KEY is not set for Vision OCR.")
            return None
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": valid_mime, "data": b64_data}}
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens}
        }
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                if "candidates" in data and len(data["candidates"]) > 0:
                    parts = data["candidates"][0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
                return None
        except Exception as e:
            logger.warning(f"Gemini Vision call failed: {e}")
            return None
    else:
        # Anthropic direct format
        if not settings.ai.anthropic_api_key or settings.ai.anthropic_api_key == "your_anthropic_api_key_here":
            logger.warning("ANTHROPIC_API_KEY is placeholder or missing.")
            return None
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=settings.ai.anthropic_api_key)
            msg = await client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=max_tokens,
                temperature=0.0,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image", "source": {"type": "base64", "media_type": valid_mime, "data": b64_data}}
                        ]
                    }
                ]
            )
            return msg.content[0].text.strip()
        except Exception as e:
            logger.warning(f"Anthropic Vision call failed: {e}")
            return None


async def extract_price_from_image(image_bytes: bytes, mime_type: str) -> float | None:
    prompt = "Extract the current market price of the stock from this TradingView screenshot. Respond ONLY with the numerical value (e.g. 150.25). No other text or currency symbols."
    text = await call_vision_model(prompt, image_bytes, mime_type, max_tokens=50)
    if not text:
        return None
    match = re.search(r"\d+\.\d+", text)
    if match:
        return float(match.group())
    try:
        return float(text.replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


async def extract_options_chain_from_image(
    image_bytes: bytes, mime_type: str, ticker: str, current_price: float, is_bullish: bool
) -> dict[str, Any] | None:
    bias_str = "BULLISH CALL (Delta ~0.30 to 0.45, 30-45 DTE)" if is_bullish else "BEARISH PUT (Delta ~0.30 to 0.45, 30-45 DTE)"
    prompt = f"""You are an institutional options strategist for StockGlass AI.
Analyze this uploaded brokerage Options Chain screenshot for {ticker} (current price ~${current_price:.2f}).
Our directional bias for this setup is: {bias_str}.
Our framework rules require:
1. Target Delta between 0.30 and 0.45 (or nearest liquid OTM contract if delta column is not visible).
2. Expiration window around 30 to 45 Days to Expiration (DTE) if visible.
3. Liquid contracts with tight bid-ask spread and meaningful Open Interest (OI) / Volume.

Read the visible strikes and select the single best contract from the image.
Respond ONLY with a JSON object in this exact format (no markdown code blocks, no trailing text):
{{
  "selected_strike": 335.0,
  "contract_type": "CALL",
  "expiration": "2026-08-21 (35 DTE)",
  "delta": 0.38,
  "open_interest": "2,400",
  "bid_ask": "$5.20 / $5.35",
  "reasoning": "Selected the $335 Call expiring Aug 21 (35 DTE). It trades at a 0.38 Delta with 2,400 Open Interest and a tight $0.15 bid-ask spread, perfectly aligning with our Level 1 bullish momentum rules and avoiding illiquid wide spreads."
}}
If the image is not a valid options chain chart or cannot be read, respond with:
{{"error": "Could not read options chain from image. Please upload a clear screenshot of the strike chain."}}
"""
    text = await call_vision_model(prompt, image_bytes, mime_type, max_tokens=600)
    if not text:
        return None
    # Clean possible markdown block
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    try:
        data = json.loads(cleaned)
        return data
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse options chain JSON from Vision AI: {e}. Raw text: {text}")
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


@router.post("/{scan_id}/options-chain")
async def upload_options_chain_screenshot(
    scan_id: int,
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
):
    """
    Upload a brokerage Options Chain screenshot for AI Vision contract selection.
    Extracts target strike price and contract details based on 10-layer rules.
    """
    scan = await session.get(DailyScan, scan_id)
    if not scan:
        return {"error": f"Scan ID {scan_id} not found", "status": "error"}

    storage_url = f"/storage/screenshots/chain_{scan_id}/{file.filename}"
    content_bytes = await file.read()
    mime_type = file.content_type or "image/png"

    # Determine bias
    is_bullish = True
    if scan.factor_results_json and isinstance(scan.factor_results_json, dict):
        for f in scan.factor_results_json.get("results", []):
            if f.get("factor_id") in ("F43", "F49") and f.get("vetoed"):
                is_bullish = False

    current_price = scan.entry_price or 0.0
    if current_price == 0.0 and scan.factor_results_json and isinstance(scan.factor_results_json, dict):
        current_price = scan.factor_results_json.get("market_data", {}).get("price", 0.0)

    # Call Vision AI
    ai_result = await extract_options_chain_from_image(
        image_bytes=content_bytes,
        mime_type=mime_type,
        ticker=scan.ticker,
        current_price=current_price,
        is_bullish=is_bullish,
    )

    # Save screenshot record
    screenshot = await screenshot_service.upload_screenshot(
        session=session,
        scan_id=scan_id,
        storage_url=storage_url,
        file_name=file.filename or "options_chain.png",
        file_size_bytes=file.size,
        content_type=mime_type,
    )

    if ai_result and "selected_strike" in ai_result and not "error" in ai_result:
        try:
            scan.strike_price = float(ai_result["selected_strike"])
            if not scan.factor_results_json or not isinstance(scan.factor_results_json, dict):
                scan.factor_results_json = {}
            new_json = dict(scan.factor_results_json)
            new_json["options_chain_selection"] = ai_result
            scan.factor_results_json = new_json
            await session.flush()
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse selected_strike: {e}")

    return {
        "id": screenshot.id,
        "scan_id": screenshot.scan_id,
        "storage_url": screenshot.storage_url,
        "file_name": screenshot.file_name,
        "strike_price": scan.strike_price,
        "ai_selection": ai_result or {"error": "Vision AI could not extract contract details."},
        "status": "success" if (ai_result and "selected_strike" in ai_result) else "warning",
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
