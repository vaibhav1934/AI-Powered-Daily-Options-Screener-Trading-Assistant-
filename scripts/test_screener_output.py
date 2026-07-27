import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.db.session import async_session_factory
from app.services.stockglass_service import get_stock_list

async def main():
    async with async_session_factory() as session:
        res_p1 = await get_stock_list(session, list_param="list1", page=1, page_size=10)
        res_p2 = await get_stock_list(session, list_param="list1", page=2, page_size=10)
        print(f"Page 1: count={res_p1.count}, total={res_p1.total}, total_pages={res_p1.total_pages}")
        print("Page 1 symbols:", [r.symbol for r in res_p1.results])
        print(f"Page 2: count={res_p2.count}")
        print("Page 2 symbols:", [r.symbol for r in res_p2.results])

if __name__ == "__main__":
    asyncio.run(main())
