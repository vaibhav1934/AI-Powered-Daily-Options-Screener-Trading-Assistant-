import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from app.core.rate_limiter import init_rate_limiters
from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.technicals import fetch_technicals
from datetime import date
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout)

async def main():
    init_rate_limiters()
    client = FinnhubClient()
    scan_date = date.today()
    try:
        print('Fetching calendar...')
        async with async_session_factory() as macro_session:
            calendar = await client.get_earnings_calendar(from_date=scan_date, to_date=scan_date, session=macro_session)
        
        subset = calendar[:5]
        print(f'Calendar subset: {[entry.ticker for entry in subset]}')
        
        sem = asyncio.Semaphore(5)
        
        async def fetch_ticker(entry):
            print(f'Start fetching {entry.ticker}')
            async with sem:
                async with async_session_factory() as task_session:
                    try:
                        print(f'{entry.ticker}: get_quote')
                        quote = await client.get_quote(entry.ticker, session=task_session)
                        print(f'{entry.ticker}: fetch_technicals')
                        tech_data = await fetch_technicals(entry.ticker, quote.current_price, task_session)
                        print(f'{entry.ticker}: Done')
                        return entry.ticker
                    except Exception as e:
                        print(f'{entry.ticker}: Failed {e}')
                        return None
        
        tasks = [fetch_ticker(entry) for entry in subset]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        print(f'Results: {results}')
    finally:
        await client.close()

asyncio.run(main())

