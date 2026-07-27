import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import logging
from app.db.session import async_session_factory
from sqlalchemy import select
from app.db.models import StockUniverse
from app.core.market_data.finnhub import FinnhubClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("enrich_top_sectors")

TOP_SYMBOLS = [
    "NVDA", "GOOGL", "AMZN", "META", "BRK-B", "ASML", "INTC", "CSCO", "COST", "UNH",
    "AAPL", "MSFT", "TSLA", "AMD", "NFLX", "PLTR", "WFC", "TXN", "GE", "MS"
]

async def main():
    client = FinnhubClient()
    try:
        async with async_session_factory() as session:
            stmt = select(StockUniverse).where(StockUniverse.ticker.in_(TOP_SYMBOLS))
            rows = (await session.execute(stmt)).scalars().all()
            logger.info("Found %d top symbols in StockUniverse to check/enrich...", len(rows))
            
            for u in rows:
                if u.sector in ("US Equities", "Unknown", None) or u.name == f"{u.ticker} Corp":
                    logger.info("Enriching %s from Finnhub...", u.ticker)
                    profile = await client.get_company_profile(u.ticker, session=session)
                    sec = profile.get("sector")
                    name = profile.get("name")
                    if sec and sec not in ("Unknown", "US Equities"):
                        u.sector = sec
                    if name and name != f"{u.ticker} Corp" and name != u.ticker:
                        u.name = name
            await session.commit()
            logger.info("Enrichment complete! Committed to DB.")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(main())
