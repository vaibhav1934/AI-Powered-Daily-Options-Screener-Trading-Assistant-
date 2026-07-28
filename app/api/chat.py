"""
Chat API Route
================
SSE streaming endpoint for GenAI chat panel.
FR-13–FR-16: grounded in scan data, enforces screenshot gate.
"""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.schemas import ChatMessageRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
@router.post("/")
@router.post("/query")
async def chat(
    request: ChatMessageRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Chat endpoint — processes a message and returns an SSE stream.
    FR-15: grounded in today's scan data + framework rule set.
    FR-16: cannot surface execution details for unconfirmed tickers.
    """
    from app.agents.chat_agent import process_chat_message

    async def event_stream():
        async for chunk in process_chat_message(
            message=request.message,
            conversation_id=request.conversation_id,
            session=session,
        ):
            data = json.dumps(chunk)
            yield f"data: {data}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
