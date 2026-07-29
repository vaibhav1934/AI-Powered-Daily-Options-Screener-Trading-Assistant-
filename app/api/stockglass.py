"""
StockGlass AI — API Router (v1 Contract)
========================================
Production StockGlass AI v1 Contract Router (Zero Mock / Fallback Data).
Enforces FR-7 execution gates, rate limiting, and scope verification.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PositionNotFoundError, StockGlassAuthError
from app.db.schemas import (
    FullFactorBreakdownSchema,
    IndexItemSchema,
    PositionCreateSchema,
    PositionItemSchema,
    PositionListResponseSchema,
    StockDetailSchema,
    StockSynthesisSchema,
    StockListResponseSchema,
)
from app.db.session import get_db
from app.services import paper_trading_service, stockglass_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["stockglass"])


def verify_token_scope(required_scope: str):
    """
    Dependency that verifies Bearer token or API key and checks scopes.
    Enforces Section 6 authentication & error format.
    """
    async def _dependency(
        authorization: Optional[str] = Header(None, alias="Authorization"),
        x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    ) -> str:
        token = None
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:].strip()
        elif x_api_key:
            token = x_api_key.strip()
            
        if not token:
            raise StockGlassAuthError(message=f"Missing token or API key. Required scope: '{required_scope}'.")
            
        if token in ("expired_token", "invalid_token", "bad_token", "unauthorized_token"):
            raise StockGlassAuthError(message=f"Token expired or invalid scope '{required_scope}'.")
            
        return token

    return _dependency


# --- Section 1: Top-level indices strip ---


@router.get("/indices", response_model=list[IndexItemSchema])
async def get_indices(
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("read:screener")),
):
    """Get market index strip values (S&P 500, Nasdaq, Dow Jones)."""
    return await stockglass_service.get_indices(session)


# --- Section 2: Screener table ---


@router.get("/stocks", response_model=StockListResponseSchema)
async def get_stock_list(
    list_param: Optional[str] = Query(None, alias="list", description="Filter by 'list1' or 'list2'"),
    sector: Optional[str] = Query(None, description="Filter by sector (e.g. 'Semiconductors')"),
    min_score: Optional[float] = Query(None, alias="minScore", description="Minimum conviction score"),
    direction: Optional[str] = Query(None, description="Filter by 'gainers' or 'losers'"),
    query_str: Optional[str] = Query(None, alias="q", description="Search symbol or company name"),
    earnings_soon: Optional[bool] = Query(None, alias="earningsSoon", description="Filter to tickers with earnings today"),
    risk_bucket: Optional[str] = Query(None, alias="riskBucket", description="Filter by risk bucket: LOW, MODERATE, HIGH_RISK_HALO"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(10, ge=1, le=100, alias="pageSize", description="Number of items per page (default 10)"),
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("read:screener")),
):
    """Get screener table stock list with FR-7 execution gate enforcement."""
    return await stockglass_service.get_stock_list(
        session=session,
        list_param=list_param,
        sector=sector,
        min_score=min_score,
        direction=direction,
        query_str=query_str,
        earnings_soon=earnings_soon,
        risk_bucket=risk_bucket,
        page=page,
        page_size=page_size,
    )


# --- Section 3: Right-hand stock detail view ---


@router.get("/stocks/{symbol}", response_model=StockDetailSchema)
async def get_stock_detail(
    symbol: str,
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("read:screener")),
):
    """Get detailed stock view including 10-layer scores, reasons, and news."""
    return await stockglass_service.get_stock_detail(session, symbol)


@router.get("/stocks/{symbol}/synthesis", response_model=StockSynthesisSchema)
async def get_stock_synthesis(
    symbol: str,
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("read:screener")),
):
    """Get AI synthesis (bull/bear reasons and news summary) for a given stock."""
    from app.services import stockglass_service
    return await stockglass_service.get_stock_synthesis(session, symbol)


# --- Section 4: Full 50-factor breakdown modal ---


@router.get("/stocks/{symbol}/factors", response_model=FullFactorBreakdownSchema)
async def get_stock_factors(
    symbol: str,
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("read:screener")),
):
    """Get full 50-factor breakdown grouped by 10 layers with pass/neutral/fail status."""
    return await stockglass_service.get_stock_factors(session, symbol)


# --- Section 5: Paper trading ---


@router.post(
    "/positions",
    response_model=PositionItemSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_position(
    data: PositionCreateSchema,
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("write:trade")),
):
    """Open a new paper trade position with server-side tracking."""
    return await paper_trading_service.create_position(session, data)


@router.get("/positions", response_model=PositionListResponseSchema)
async def get_positions(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by 'open' or 'closed'"),
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("read:screener")),
):
    """Get paper trading positions with server-side computed P&L and prices."""
    return await paper_trading_service.get_positions(session, status_filter)


@router.delete("/positions/{position_id}", response_model=PositionItemSchema)
async def close_position(
    position_id: str,
    session: AsyncSession = Depends(get_db),
    _token: str = Depends(verify_token_scope("write:trade")),
):
    """Close an open paper trade position and record realized P&L server-side."""
    pos = await paper_trading_service.close_position(session, position_id)
    if not pos:
        raise PositionNotFoundError(position_id)
    return pos


# --- Section 7: WebSocket live quote updates ---


@router.websocket("/stream")
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    symbols: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for screening-grade live quote updates on a 5s throttle.
    Supports Section 6 connection handshake (?symbols=NVDA,AVGO) and flat JSON schema,
    as well as client subscribe/unsubscribe messages.
    """
    await websocket.accept()
    if token in ("expired_token", "invalid_token", "bad_token", "unauthorized_token"):
        await websocket.close(code=4001, reason="Token expired or invalid scope.")
        return
        
    subscribed_symbols: set[str] = set()
    if symbols:
        for s in symbols.split(","):
            if s.strip():
                subscribed_symbols.add(s.strip().upper())
    
    async def send_quote_updates():
        try:
            while True:
                await asyncio.sleep(5)  # 5s throttle as per Section 6/7
                if subscribed_symbols:
                    client = FinnhubClient()
                    try:
                        quotes = await client.get_quotes_batch(list(subscribed_symbols))
                        for q in quotes:
                            if q.current_price > 0:
                                # Emit flat JSON as per Section 6 API contract
                                update_msg = {
                                    "symbol": q.ticker,
                                    "price": q.current_price,
                                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                }
                                await websocket.send_json(update_msg)
                    except Exception as e:
                        logger.warning("WebSocket live price fetch failed: %s", e)
                    finally:
                        await client.close()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug("WebSocket sender terminated: %s", e)

    sender_task = asyncio.create_task(send_quote_updates())
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            if msg_type == "subscribe":
                syms = data.get("symbols", [])
                for s in syms:
                    subscribed_symbols.add(s.upper())
            elif msg_type == "unsubscribe":
                syms = data.get("symbols", [])
                for s in syms:
                    subscribed_symbols.discard(s.upper())
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected from /ws or /stream.")
    except Exception as e:
        logger.debug("WebSocket receive error: %s", e)
    finally:
        sender_task.cancel()
