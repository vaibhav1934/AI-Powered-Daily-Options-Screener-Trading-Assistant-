import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def main():
    async with async_session_factory() as session:
        await session.execute(text('DELETE FROM factor_logs WHERE daily_scan_id IN (SELECT id FROM daily_scans WHERE ticker = ''DUAL-HORIZON'');'))
        res = await session.execute(text('DELETE FROM daily_scans WHERE ticker = ''DUAL-HORIZON'';'))
        await session.commit()
        print(f'Deleted {res.rowcount} rows.')

asyncio.run(main())
