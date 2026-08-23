import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
from app.services.continuous_scanner import run_scanner_cycle

async def main():
    print("[Runner] Running scanner cycle for priority liquid tickers...")
    scanned = await run_scanner_cycle(batch_size=5, delay_between_calls_sec=1.0)
    print(f"[Runner] Finished cycle. Scanned: {scanned}")

if __name__ == "__main__":
    asyncio.run(main())
