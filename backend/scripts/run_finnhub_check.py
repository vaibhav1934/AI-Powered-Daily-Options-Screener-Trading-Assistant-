import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.core.market_data.finnhub import FinnhubClient
from app.core.rate_limiter import init_rate_limiters
from datetime import date

async def main():
    init_rate_limiters()
    client = FinnhubClient()
    try:
        cal = await client.get_earnings_calendar(date.today(), date.today())
        print(f'Calendar length: {len(cal)}')
    except Exception as e:
        print(f'Error: {e}')
    await client.close()

asyncio.run(main())

