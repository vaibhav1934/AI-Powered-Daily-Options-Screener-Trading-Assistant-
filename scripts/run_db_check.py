import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as session:
        res = await session.execute(text('SELECT count(*) FROM daily_scans'))
        print(f'daily_scans: {res.scalar()}')
        res = await session.execute(text('SELECT count(*) FROM market_data_cache'))
        print(f'market_data_cache: {res.scalar()}')

asyncio.run(main())

