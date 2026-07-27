import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from app.services.scan_service import trigger_scan
from app.core.rate_limiter import init_rate_limiters
import logging
import sys

logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

async def main():
    init_rate_limiters()
    async with async_session_factory() as session:
        result = await trigger_scan(session)
        print(f'Result: {result}')

asyncio.run(main())

