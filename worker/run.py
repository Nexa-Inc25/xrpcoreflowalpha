import asyncio

from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY, ENABLE_GODARK_ETH_SCANNER
from scanners.xrpl_scanner import start_xrpl_scanner
from scanners.zk_scanner import start_zk_scanner
from scanners.equities_scanner import start_equities_scanner
from scanners.xrpl_trustline_watcher import start_trustline_watcher
from scanners.godark_eth_scanner import start_godark_eth_scanner
from godark.dynamic_ingest import run_dynamic_ingest
from correlator.cross_market import run_correlation_loop


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
    # XRPL trustline watcher (predictive)
    if XRPL_WSS:
        print("[Worker] Launching XRPL trustline watcher")
        tasks.append(asyncio.create_task(supervise(start_trustline_watcher, "TRUSTLINES")))
    # Ethereum GoDark prep scanner (USDC/USDT/DAI inflows)
    if ENABLE_GODARK_ETH_SCANNER and ALCHEMY_WS_URL:
        print("[Worker] Launching GoDark ETH prep scanner")
        tasks.append(asyncio.create_task(supervise(start_godark_eth_scanner, "GODARK_ETH")))
    # Dynamic partner ingestion (Arkham/env sync)
    print("[Worker] Launching GoDark dynamic ingestion")
    tasks.append(asyncio.create_task(supervise(run_dynamic_ingest, "GODARK_INGEST")))
    # Correlator always runs; it only acts on available signals
    tasks.append(asyncio.create_task(supervise(run_correlation_loop, "CROSS")))
    if not tasks:
        # Idle loop if no env configured
        while True:
            await asyncio.sleep(60)
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
