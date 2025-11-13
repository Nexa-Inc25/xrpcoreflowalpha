import asyncio
from typing import Optional

from web3 import Web3

from app.config import ALCHEMY_WS_URL, VERIFIER_ALLOWLIST
from alerts.slack import send_slack_alert, build_rich_slack_payload
from models.types import ZKFlow
from observability.metrics import zk_proof_detected


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
    w3 = Web3(Web3.WebsocketProvider(ALCHEMY_WS_URL))
    # Poll pending tx filter in a thread to avoid blocking the event loop
    pending_filter = w3.eth.filter("pending")
    chain = "eth" if (w3.eth.chain_id == 1) else str(w3.eth.chain_id)

    async def poll_pending():
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
                    if _is_zk_proof(tx):
                        zk_proof_detected.labels(network=chain).inc()
                        flow = ZKFlow(
                            tx_hash=tx.get("hash").hex() if hasattr(tx.get("hash"), "hex") else str(tx.get("hash")),
                            gas_used=int(tx.get("gas", 0)),
                            to_address=(tx.get("to") or "").lower(),
                            timestamp=int(tx.get("nonce", 0)),
                            network=chain,
                        )
                        await send_slack_alert(build_rich_slack_payload({"type": "zk", "flow": flow}))
            except Exception:
                await asyncio.sleep(0.5)
            await asyncio.sleep(0.2)

    await poll_pending()
