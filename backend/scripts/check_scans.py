import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import select, func
from app.db.models import DailyScan

async def main():
    async with async_session_factory() as session:
        cnt = await session.scalar(select(func.count(DailyScan.id)))
        print("Total rows in DailyScan:", cnt)
        rows = (await session.execute(select(DailyScan).limit(10))).scalars().all()
        print("Sample tickers in DailyScan:", [r.ticker for r in rows])

if __name__ == "__main__":
    asyncio.run(main())
