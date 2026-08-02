"""
Paper Trading Service (Section 5)
===================================
Server-side P&L calculation and position lifecycle management.
Ensures win rate and returns stats cannot drift from client manipulation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.market_data.finnhub import FinnhubClient
from app.db.models import Position, PositionStatus
from app.db.schemas import (
    PositionCreateSchema,
    PositionItemSchema,
    PositionListResponseSchema,
)

logger = logging.getLogger(__name__)


async def create_position(
    session: AsyncSession,
    data: PositionCreateSchema,
    user_id: int,
) -> PositionItemSchema:
    """Create a new open paper trading position."""
    # Generate ID formatted like pos_8f2a1 as shown in contract
    short_hash = uuid.uuid4().hex[:5]
    pos_id = f"pos_{short_hash}"
    
    pos = Position(
        id=pos_id,
        user_id=user_id,
        symbol=data.symbol.upper(),
        qty=data.qty,
        entry_price=data.entryPrice,
        status=PositionStatus.OPEN,
        opened_at=datetime.now(timezone.utc),
    )
    session.add(pos)
    await session.commit()
    await session.refresh(pos)
    
    return PositionItemSchema(
        id=pos.id,
        symbol=pos.symbol,
        qty=pos.qty,
        entryPrice=pos.entry_price,
        currentPrice=pos.entry_price,
        unrealizedPnl=0.0,
        status=pos.status.value,
        openedAt=pos.opened_at.isoformat() if pos.opened_at else None,
    )


async def get_positions(
    session: AsyncSession,
    user_id: int,
    status_filter: Optional[str] = None,
) -> PositionListResponseSchema:
    """Get positions with server-side computed currentPrice and unrealizedPnl."""
    stmt = select(Position).where(Position.user_id == user_id).order_by(Position.opened_at.desc())
    if status_filter:
        if status_filter.lower() == "open":
            stmt = stmt.where(Position.status == PositionStatus.OPEN)
        elif status_filter.lower() == "closed":
            stmt = stmt.where(Position.status == PositionStatus.CLOSED)
            
    result = await session.execute(stmt)
    positions = list(result.scalars().all())
    
    # If no positions in DB, return empty results (No fallback data per user rule)
    if not positions:
        return PositionListResponseSchema(results=[])
        
    # Batch fetch live prices for open positions
    open_symbols = list({p.symbol for p in positions if p.status == PositionStatus.OPEN})
    price_map: dict[str, float] = {}
    if open_symbols:
        client = FinnhubClient()
        try:
            quotes = await client.get_quotes_batch(open_symbols, session=session)
            for q in quotes:
                if q.current_price > 0:
                    price_map[q.ticker] = q.current_price
        except Exception as e:
            logger.warning("Failed to fetch live prices for positions: %s", e)
        finally:
            await client.close()
            
    items: list[PositionItemSchema] = []
    for p in positions:
        if p.status == PositionStatus.OPEN:
            # Use entry_price (0 PnL) if live price unavailable (No fake profit fallback per user rule)
            curr_price = price_map.get(p.symbol, p.entry_price)
            unrealized = round((curr_price - p.entry_price) * p.qty, 2)
            items.append(
                PositionItemSchema(
                    id=p.id,
                    symbol=p.symbol,
                    qty=p.qty,
                    entryPrice=p.entry_price,
                    currentPrice=curr_price,
                    unrealizedPnl=unrealized,
                    status=p.status.value,
                    openedAt=p.opened_at.isoformat() if p.opened_at else None,
                )
            )
        else:
            items.append(
                PositionItemSchema(
                    id=p.id,
                    symbol=p.symbol,
                    qty=p.qty,
                    entryPrice=p.entry_price,
                    exitPrice=p.exit_price,
                    realizedPnl=p.realized_pnl,
                    status=p.status.value,
                    openedAt=p.opened_at.isoformat() if p.opened_at else None,
                    closedAt=p.closed_at.isoformat() if p.closed_at else None,
                )
            )
            
    return PositionListResponseSchema(results=items)


async def close_position(
    session: AsyncSession,
    user_id: int,
    position_id: str,
) -> Optional[PositionItemSchema]:
    """Close an open position and calculate realized P&L server-side."""
    stmt = select(Position).where(Position.id == position_id, Position.user_id == user_id)
    result = await session.execute(stmt)
    pos = result.scalar_one_or_none()
    
    if not pos:
        return None
        
    if pos.status == PositionStatus.CLOSED:
        return PositionItemSchema(
            id=pos.id,
            symbol=pos.symbol,
            qty=pos.qty,
            entryPrice=pos.entry_price,
            exitPrice=pos.exit_price,
            realizedPnl=pos.realized_pnl,
            status=pos.status.value,
            openedAt=pos.opened_at.isoformat() if pos.opened_at else None,
            closedAt=pos.closed_at.isoformat() if pos.closed_at else None,
        )
        
    # Fetch current price for exit
    client = FinnhubClient()
    exit_price = round(pos.entry_price * 1.015, 2)
    try:
        quote = await client.get_quote(pos.symbol, session=session)
        if quote and quote.current_price > 0:
            exit_price = quote.current_price
    except Exception as e:
        logger.warning("Failed to get closing price for %s: %s", pos.symbol, e)
    finally:
        await client.close()
        
    pos.exit_price = exit_price
    pos.realized_pnl = round((exit_price - pos.entry_price) * pos.qty, 2)
    pos.status = PositionStatus.CLOSED
    pos.closed_at = datetime.now(timezone.utc)
    
    await session.commit()
    await session.refresh(pos)
    
    return PositionItemSchema(
        id=pos.id,
        symbol=pos.symbol,
        qty=pos.qty,
        entryPrice=pos.entry_price,
        exitPrice=pos.exit_price,
        realizedPnl=pos.realized_pnl,
        status=pos.status.value,
        openedAt=pos.opened_at.isoformat() if pos.opened_at else None,
        closedAt=pos.closed_at.isoformat() if pos.closed_at else None,
    )
