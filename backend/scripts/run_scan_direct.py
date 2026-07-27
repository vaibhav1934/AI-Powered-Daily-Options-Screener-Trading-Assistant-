import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.technicals import fetch_technicals
from app.db.session import async_session_factory
from app.core.rate_limiter import init_rate_limiters
from datetime import date

async def fetch_ticker_data(client, entry):
    async with async_session_factory() as task_session:
        try:
            print(f'Fetching {entry.ticker}')
            quote = await client.get_quote(entry.ticker, session=task_session)
            gap = quote.change_percent
            tech_data = await fetch_technicals(entry.ticker, quote.current_price, task_session)
            return {'ticker': entry.ticker, 'gap': gap}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None

async def main():
    init_rate_limiters()
    client = FinnhubClient()
    try:
        cal = await client.get_earnings_calendar(date.today(), date.today())
        print(f'Calendar length: {len(cal)}')
        if cal:
            subset = cal[:3]
            tasks = [fetch_ticker_data(client, entry) for entry in subset]
            results = await asyncio.gather(*tasks)
            print(results)
    finally:
        await client.close()

asyncio.run(main())

