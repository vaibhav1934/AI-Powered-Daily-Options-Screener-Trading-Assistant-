import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.core.market_data.finnhub import FinnhubClient
from app.core.market_data.technicals import fetch_technicals
from app.core.rate_limiter import init_rate_limiters
from datetime import date

async def main():
    init_rate_limiters()
    client = FinnhubClient()
    try:
        cal = await client.get_earnings_calendar(date.today(), date.today())
        print(f'Calendar length: {len(cal)}')
        if cal:
            entry = cal[0]
            print(f'Fetching quote for {entry.ticker}')
            quote = await client.get_quote(entry.ticker)
            print(f'Quote: {quote}')
            print(f'Fetching technicals for {entry.ticker}')
            tech = await fetch_technicals(entry.ticker, quote.current_price)
            print(f'Tech: {tech}')
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        await client.close()

asyncio.run(main())

