import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def main():
    print("Running schema migration to add missing columns...")
    async with async_session_factory() as session:
        await session.execute(text("ALTER TABLE daily_scans ADD COLUMN IF NOT EXISTS live_evaluated_at DATE;"))
        await session.commit()
    print("Migration completed successfully! Column 'live_evaluated_at' added to daily_scans.")

if __name__ == "__main__":
    asyncio.run(main())
