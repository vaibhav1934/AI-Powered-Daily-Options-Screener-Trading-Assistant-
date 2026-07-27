import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import select
from app.db.models import StockUniverse

async def main():
    async with async_session_factory() as session:
        for symbol in ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN"]:
            u = (await session.execute(select(StockUniverse).where(StockUniverse.ticker == symbol))).scalar_one_or_none()
            if u:
                print(f"{symbol} => Name: {repr(u.name)} | Sector: {repr(u.sector)} | Exchange: {repr(u.exchange)}")

if __name__ == "__main__":
    asyncio.run(main())
