import asyncio

from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY
from scanners.xrpl_scanner import start_xrpl_scanner
from scanners.zk_scanner import start_zk_scanner
from scanners.equities_scanner import start_equities_scanner


async def main():
    print(f"[Worker] Starting. XRPL={'on' if XRPL_WSS else 'off'} | ZK={'on' if ALCHEMY_WS_URL else 'off'} | EQUITIES={'on' if FINNHUB_API_KEY else 'off'}")
    tasks = []

    async def supervise(coro, name: str):
        while True:
            try:
                print(f"[Worker] Starting {name} loop")
                await coro()
            except Exception as e:
                print(f"[Worker] {name} crashed: {e.__class__.__name__}: {e}")
                await asyncio.sleep(2)

    if XRPL_WSS:
        print("[Worker] Launching XRPL scanner")
        tasks.append(asyncio.create_task(supervise(start_xrpl_scanner, "XRPL")))
    if ALCHEMY_WS_URL:
        print("[Worker] Launching ZK scanner")
        tasks.append(asyncio.create_task(supervise(start_zk_scanner, "ZK")))
    if FINNHUB_API_KEY:
        print("[Worker] Launching Equities scanner")
        tasks.append(asyncio.create_task(supervise(start_equities_scanner, "EQUITIES")))
    if not tasks:
        # Idle loop if no env configured
        while True:
            await asyncio.sleep(60)
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
