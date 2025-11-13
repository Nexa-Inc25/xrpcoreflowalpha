import asyncio

from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY
from scanners.xrpl_scanner import start_xrpl_scanner
from scanners.zk_scanner import start_zk_scanner
from scanners.equities_scanner import start_equities_scanner


async def main():
    tasks = []
    if XRPL_WSS:
        tasks.append(asyncio.create_task(start_xrpl_scanner()))
    if ALCHEMY_WS_URL:
        tasks.append(asyncio.create_task(start_zk_scanner()))
    if FINNHUB_API_KEY:
        tasks.append(asyncio.create_task(start_equities_scanner()))
    if not tasks:
        # Idle loop if no env configured
        while True:
            await asyncio.sleep(60)
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
