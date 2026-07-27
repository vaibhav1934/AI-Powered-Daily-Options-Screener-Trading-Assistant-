import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.services.scan_service import run_daily_scan
from app.db.session import async_session_factory
from app.core.rate_limiter import init_rate_limiters
from datetime import date

async def main():
    init_rate_limiters()
    async with async_session_factory() as session:
        res = await run_daily_scan(date.today(), session=session)
        print('Result:', res)

asyncio.run(main())

