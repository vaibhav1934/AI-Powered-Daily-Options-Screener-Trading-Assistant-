import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import select
from app.db.models import DailyScan

async def main():
    async with async_session_factory() as session:
        scans = (await session.execute(select(DailyScan))).scalars().all()
        print(f"Found {len(scans)} rows in daily_scans:")
        for s in scans:
            mdata = (s.factor_results_json or {}).get("market_data", {})
            print(f"Ticker: {s.ticker:<6} | ListType: {s.list_type} | Status: {s.status} | Score: {s.score} | Price: {mdata.get('price')} | Sector: {mdata.get('sector')}")

if __name__ == "__main__":
    asyncio.run(main())
