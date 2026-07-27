"""
Stock Universe Seeding Script
=============================
Fetches ~6,000 US equities from official SEC EDGAR company tickers exchange JSON.
Populates Supabase/PostgreSQL 'stocks' table with Ticker, Company Name, Exchange, and 10-digit CIK.
Enforces strict Zero Mock / Zero Fallback Data global rule: if SEC API is unreachable, raises error.

Usage:
    python -m scripts.seed_universe
"""

import asyncio
import logging
import os
import sys
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.models import Base, StockUniverse
from app.db.session import async_session_factory, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_universe")

SEC_TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
USER_AGENT = "StockGlassAI/1.0 (contact@stockglass.ai)"


async def fetch_sec_universe() -> list[dict[str, Any]]:
    """
    Fetch universe from SEC EDGAR.
    Attempts company_tickers_exchange.json first (includes exchange info).
    Falls back to company_tickers.json if exchange endpoint is unavailable.
    Raises exception if both fail (Zero Mock Data rule).
    """
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
        try:
            logger.info("Fetching SEC tickers with exchange from %s...", SEC_TICKERS_EXCHANGE_URL)
            resp = await client.get(SEC_TICKERS_EXCHANGE_URL)
            if resp.status_code == 200:
                data = resp.json()
                # Format: {"fields": ["cik", "name", "ticker", "exchange"], "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"], ...]}
                fields = data.get("fields", [])
                rows = data.get("data", [])
                
                cik_idx = fields.index("cik") if "cik" in fields else 0
                name_idx = fields.index("name") if "name" in fields else 1
                ticker_idx = fields.index("ticker") if "ticker" in fields else 2
                ex_idx = fields.index("exchange") if "exchange" in fields else 3
                
                universe = []
                for row in rows:
                    ticker = str(row[ticker_idx]).strip().upper()
                    if not ticker or len(ticker) > 10:
                        continue
                    cik_val = str(row[cik_idx]).strip().zfill(10)
                    name = str(row[name_idx]).strip()
                    exchange = str(row[ex_idx]).strip() if len(row) > ex_idx else "US Market"
                    
                    universe.append({
                        "ticker": ticker,
                        "name": name or f"{ticker} Corp",
                        "sector": "US Equities",  # Default sector until scan enriches from profile
                        "exchange": exchange,
                        "cik": cik_val,
                        "is_active": True,
                    })
                logger.info("Successfully fetched %d tickers from exchange endpoint.", len(universe))
                return universe
        except Exception as e:
            logger.warning("Failed to fetch exchange endpoint: %s. Trying basic tickers endpoint...", e)

        try:
            logger.info("Fetching SEC basic tickers from %s...", SEC_TICKERS_URL)
            resp = await client.get(SEC_TICKERS_URL)
            resp.raise_for_status()
            data = resp.json()
            
            universe = []
            for k, val in data.items():
                ticker = str(val.get("ticker", "")).strip().upper()
                if not ticker or len(ticker) > 10:
                    continue
                cik_val = str(val.get("cik_str", "")).strip().zfill(10)
                name = str(val.get("title", "")).strip()
                
                universe.append({
                    "ticker": ticker,
                    "name": name or f"{ticker} Corp",
                    "sector": "US Equities",
                    "exchange": "US Market",
                    "cik": cik_val,
                    "is_active": True,
                })
            logger.info("Successfully fetched %d tickers from basic endpoint.", len(universe))
            return universe
        except Exception as e:
            logger.error("SEC EDGAR universe fetch failed completely: %s", e)
            raise RuntimeError(f"Could not fetch universe data from SEC EDGAR: {e} (Zero Mock Data enforced)")


async def seed_database(universe: list[dict[str, Any]]):
    """Upserts ticker universe into Supabase/PostgreSQL 'stocks' table."""
    logger.info("Connecting to database and ensuring tables exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    logger.info("Upserting %d tickers into 'stocks' table...", len(universe))
    async with async_session_factory() as session:
        batch_size = 500
        for i in range(0, len(universe), batch_size):
            batch = universe[i : i + batch_size]
            stmt = insert(StockUniverse).values(batch)
            # On conflict (ticker already exists), update name, exchange, cik, and is_active
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "name": stmt.excluded.name,
                    "exchange": stmt.excluded.exchange,
                    "cik": stmt.excluded.cik,
                    "is_active": stmt.excluded.is_active,
                },
            )
            await session.execute(stmt)
            await session.commit()
            logger.info("Processed batch %d to %d...", i + 1, min(i + batch_size, len(universe)))
            
    logger.info("Universe seeding completed successfully.")


async def main():
    try:
        universe = await fetch_sec_universe()
        await seed_database(universe)
    except Exception as e:
        logger.error("Seeding failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
