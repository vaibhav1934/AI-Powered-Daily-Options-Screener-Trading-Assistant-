import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from app.services.stockglass_service import get_stock_detail

async def main():
    async with async_session_factory() as session:
        detail = await get_stock_detail(session, "NVDA")
        print(f"NVDA detail score: {detail.score}")
        print("Layer scores:")
        for ls in detail.layerScores:
            print(f"  {ls.layer}: {ls.value}")

if __name__ == "__main__":
    asyncio.run(main())
