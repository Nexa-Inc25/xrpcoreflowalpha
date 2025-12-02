import asyncio

from prometheus_client import start_http_server

from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY, ENABLE_GODARK_ETH_SCANNER
from scanners.xrpl_scanner import start_xrpl_scanner
from scanners.zk_scanner import start_zk_scanner
from scanners.equities_scanner import start_equities_scanner
from scanners.xrpl_trustline_watcher import start_trustline_watcher
from scanners.godark_eth_scanner import start_godark_eth_scanner
from scanners.rwa_amm_liquidity_monitor import start_rwa_amm_monitor
from scanners.xrpl_orderbook_monitor import start_xrpl_orderbook_monitor
from godark.dynamic_ingest import run_dynamic_ingest
from correlator.cross_market import run_correlation_loop
try:
    from ml.flow_predictor import live_gru_training
except Exception:
    async def live_gru_training() -> None:
        while True:
            print("[ML] Torch not available – GRU training disabled (import failed)")
            await asyncio.sleep(600)
from xrpl.asyncio.clients import AsyncJsonRpcClient
from xrpl.models.requests import Ledger


async def main():
    # Expose worker-local Prometheus metrics (ZK / GoDark / scanners) on a separate port.
    try:
        start_http_server(8012, addr="127.0.0.1")
        print("[Worker] Prometheus metrics server started on 127.0.0.1:8012")
    except Exception as e:
        print(f"[Worker] Failed to start Prometheus metrics server: {e}")

    print(f"[Worker] Starting. XRPL={'on' if XRPL_WSS else 'off'} | ZK={'on' if ALCHEMY_WS_URL else 'off'} | EQUITIES={'on' if FINNHUB_API_KEY else 'off'}")
    tasks = []

    async def _xrpl_mainnet_proof():
        try:
            # Use HTTP JSON-RPC to xrplcluster.com regardless of WSS
            client = AsyncJsonRpcClient("https://xrplcluster.com")
            resp = await client.request(Ledger(ledger_index="validated"))
            ledger = resp.result.get("ledger") or {}
            total_str = ledger.get("total_coins") or ""
            li = int((resp.result.get("ledger_index") or ledger.get("ledger_index") or 0))
            total = int(total_str) if total_str.isdigit() else 0
            # Mainnet invariants (Nov 2025):
            # - ledger index well above 100,000,000
            # - total_coins in drops within (90B*1e6, 100B*1e6]
            assert li > 100_000_000, f"ledger_index too low: {li}"
            assert 90_000_000_000 * 1_000_000 < total <= 100_000_000_000 * 1_000_000, f"total_coins out of range: {total_str}"
            print(f"[Worker] XRPL mainnet proof passed. ledger_index={li} total_coins={total_str}")
        except Exception as e:
            raise AssertionError(f"XRPL mainnet proof failed: {e}")

    async def supervise(coro, name: str):
        while True:
            try:
                print(f"[Worker] Starting {name} loop")
                await coro()
            except Exception as e:
                # Critical crash marker with class and message; keep running with backoff
                print(f"[CRASH] {name} crashed: {e.__class__.__name__}: {e}")
                await asyncio.sleep(5)

    if XRPL_WSS:
        await _xrpl_mainnet_proof()
        print("[Worker] Launching XRPL scanner")
        tasks.append(asyncio.create_task(supervise(start_xrpl_scanner, "XRPL")))
        print("[Worker] Launching XRPL RWA AMM monitor")
        tasks.append(asyncio.create_task(supervise(start_rwa_amm_monitor, "RWA_AMM")))
        print("[Worker] Launching XRPL orderbook monitor")
        tasks.append(asyncio.create_task(supervise(start_xrpl_orderbook_monitor, "ORDERBOOK")))
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
    # ML GRU trainer (no-op loop if torch unavailable)
    print("[Worker] Launching ML GRU trainer")
    tasks.append(asyncio.create_task(supervise(live_gru_training, "ML")))
    if not tasks:
        # Idle loop if no env configured
        while True:
            await asyncio.sleep(60)
    else:
        await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
