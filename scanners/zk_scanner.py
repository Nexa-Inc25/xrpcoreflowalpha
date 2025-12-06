import asyncio
import time
from typing import Optional

from web3 import Web3

from app.config import ALCHEMY_WS_URL, VERIFIER_ALLOWLIST, RENEGADE_VERIFIER, RENEGADE_MANAGER, GODARK_ETH_PARTNERS
from alerts.slack import send_slack_alert, build_rich_slack_payload
from utils.tx_validate import validate_tx
from models.types import ZKFlow
from observability.metrics import zk_proof_detected
from bus.signal_bus import publish_signal
from utils.price import get_price_usd
from scanners.renegade_detector import is_renegade_proof, tag_renegade_settlement
from workers.scanner_monitor import mark_scanner_connected, record_scanner_signal, mark_scanner_error


def _is_zk_proof(tx) -> bool:
    try:
        to_addr: Optional[str] = tx.get("to")
        gas: int = int(tx.get("gas", 0))
        input_data: str = tx.get("input", "0x") or "0x"
        to_allowlisted = (to_addr or "").lower() in VERIFIER_ALLOWLIST if VERIFIER_ALLOWLIST else False
        heuristics = 400_000 <= gas <= 1_200_000 and len(input_data) > 512
        return to_allowlisted or heuristics
    except Exception:
        return False


async def start_zk_scanner():
    if not ALCHEMY_WS_URL:
        return
    assert "mainnet" in ALCHEMY_WS_URL.lower(), "NON-MAINNET ETHEREUM – FATAL ABORT"
    w3 = Web3(Web3.WebsocketProvider(ALCHEMY_WS_URL))
    # Poll pending tx filter in a thread to avoid blocking the event loop
    pending_filter = w3.eth.filter("pending")
    chain_id = w3.eth.chain_id
    chain = "eth" if (chain_id == 1) else str(chain_id)
    print(f"[ZK] Connected. chain_id={chain_id}")
    mark_scanner_connected("zk_ethereum")

    def _selector(inp: str) -> str:
        try:
            s = str(inp or "0x")
            return s[:10] if s.startswith("0x") and len(s) >= 10 else s
        except Exception:
            return "0x"

    def _calldata_len(inp: str) -> int:
        try:
            s = str(inp or "0x")
            if s.startswith("0x"):
                s = s[2:]
            return max(0, len(s) // 2)
        except Exception:
            return 0

    def _entropy(inp: str) -> float:
        try:
            s = str(inp or "0x")
            if s.startswith("0x"):
                s = s[2:]
            b = bytes.fromhex(s) if s else b""
            if not b:
                return 0.0
            counts = [0] * 256
            for by in b:
                counts[by] += 1
            n = float(len(b))
            import math
            e = 0.0
            for c in counts:
                if c:
                    p = c / n
                    e -= p * math.log2(p)
            return float(min(max(e, 0.0), 8.0))
        except Exception:
            return 0.0

    async def poll_pending():
        processed = 0
        while True:
            try:
                hashes = await asyncio.to_thread(pending_filter.get_new_entries)
                for h in hashes:
                    try:
                        tx = await asyncio.to_thread(w3.eth.get_transaction, h)
                    except Exception:
                        continue
                    if not tx:
                        continue
                    # Renegade-specific detection (verifier-based heuristics)
                    is_ren = is_renegade_proof(tx)
                    if not _is_zk_proof(tx) and not is_ren:
                        continue
                    zk_proof_detected.labels(network=chain).inc()
                    input_data: str = tx.get("input", "0x") or "0x"
                    from_addr: str = (tx.get("from") or "").lower()
                    to_addr: str = (tx.get("to") or "").lower()
                    gas_price_wei = int(tx.get("gasPrice") or tx.get("maxFeePerGas") or 0)
                    val_wei = int(tx.get("value") or 0)
                    flow = ZKFlow(
                        tx_hash=tx.get("hash").hex() if hasattr(tx.get("hash"), "hex") else str(tx.get("hash")),
                        gas_used=int(tx.get("gas", 0)),
                        to_address=(tx.get("to") or "").lower(),
                        timestamp=int(tx.get("nonce", 0)),
                        network=chain,
                    )
                    # Validate on Etherscan before publishing
                    ok = await validate_tx("ethereum", flow.tx_hash, timeout_sec=10)
                    if not ok:
                        continue
                    if is_ren:
                        print(f"[ZK] Renegade proof-like tx {flow.tx_hash[:10]}.. gas={flow.gas_used}")
                    else:
                        print(f"[ZK] Proof-like tx {flow.tx_hash[:10]}.. gas={flow.gas_used}")
                    await send_slack_alert(build_rich_slack_payload({"type": "zk", "flow": flow}))
                    # Estimate USD value via gas * (gas price) * ETH price
                    try:
                        eth_price = await get_price_usd("eth")
                        fee_eth = (int(gas_price_wei) * int(flow.gas_used)) / 1e18
                        usd_value = float(fee_eth) * float(eth_price)
                    except Exception:
                        usd_value = 0.0
                    signal: dict = {
                        "type": "zk",
                        "sub_type": "verifier_call",
                        "network": chain,
                        "tx_hash": flow.tx_hash,
                        "gas_used": flow.gas_used,
                        "to": to_addr,
                        "from": from_addr,
                        "gas_price_wei": gas_price_wei,
                        "value_wei": val_wei,
                        "input_len": _calldata_len(input_data),
                        "selector": _selector(input_data),
                        "calldata_entropy": _entropy(input_data),
                        "zero_value": int(val_wei == 0),
                        "partner_from": int(from_addr in (GODARK_ETH_PARTNERS or [])),
                        "partner_to": int(to_addr in (GODARK_ETH_PARTNERS or [])),
                        "usd_value": round(usd_value, 2),
                        "timestamp": int(time.time()),
                        "summary": f"ZK verify {flow.to_address[:6]}.. gas {flow.gas_used}",
                        "tags": [],
                    }
                    if is_ren:
                        signal["tags"].append("Renegade Proof")
                        try:
                            signal = await tag_renegade_settlement(signal, w3)
                        except Exception:
                            pass
                    await publish_signal(signal)
                    record_scanner_signal("zk_ethereum")
                    processed += 1
                    if processed % 100 == 0:
                        print(f"[ZK] Heartbeat. processed={processed} chain_id={chain_id}")
            except Exception:
                await asyncio.sleep(0.5)
            await asyncio.sleep(0.2)

    await poll_pending()
