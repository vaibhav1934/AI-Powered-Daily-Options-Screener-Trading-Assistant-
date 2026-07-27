import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as session:
        res = await session.execute(text(
            "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE tablename IN ('stocks', 'daily_scans', 'factor_logs') ORDER BY tablename, indexname;"
        ))
        rows = res.fetchall()
        print("--- EXISTING DATABASE INDEXES ---")
        for r in rows:
            print(f"Table: {r.tablename:<15} | Index: {r.indexname:<35} | Def: {r.indexdef}")

if __name__ == "__main__":
    asyncio.run(main())
