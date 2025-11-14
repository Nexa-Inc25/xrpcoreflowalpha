import asyncio
import json
import time
from typing import Dict, Any, List, Set

import websockets
import redis.asyncio as redis

from app.config import ALCHEMY_WS_URL, REDIS_URL, ENABLE_GODARK_ETH_SCANNER
from bus.signal_bus import publish_signal

# Ethereum mainnet token addresses
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
DAI  = "0x6b175474e89094c44da98b954eedeac495271d0f"

TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# token decimals
DECIMALS = {USDC: 6, USDT: 6, DAI: 18}


async def _get_eth_partners() -> Set[str]:
    r = redis.from_url(REDIS_URL, decode_responses=True)
    addrs = await r.smembers("godark:partners:ethereum")
    return {a.lower() for a in (addrs or [])}


def _hex_to_addr(topic_hex: str) -> str:
    if not topic_hex or not topic_hex.startswith("0x"):
        return ""
    # last 20 bytes
    return "0x" + topic_hex[-40:]


async def start_godark_eth_scanner():
    if not ENABLE_GODARK_ETH_SCANNER or not ALCHEMY_WS_URL:
        return
    assert "mainnet" in ALCHEMY_WS_URL.lower(), "NON-MAINNET ETHEREUM – FATAL ABORT"
    sub_params = {
        "address": [USDC, USDT, DAI]
    }
    print("[GODARK_ETH] Connecting to logs via Alchemy mainnet WS")
    async with websockets.connect(ALCHEMY_WS_URL, ping_interval=20, ping_timeout=20) as ws:
        await ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["logs", sub_params]}))
        partners = await _get_eth_partners()
        while True:
            try:
                msg = await ws.recv()
                data = json.loads(msg)
                if data.get("method") != "eth_subscription":
                    continue
                log = data.get("params", {}).get("result") or {}
                addr = (log.get("address") or "").lower()
                if addr not in DECIMALS:
                    continue
                topics: List[str] = log.get("topics") or []
                if not topics or topics[0].lower() != TRANSFER_TOPIC:
                    continue
                to_addr = _hex_to_addr(topics[2]).lower() if len(topics) > 2 else ""
                if not to_addr or to_addr not in partners:
                    # refresh partners occasionally
                    if (hash(log.get("transactionHash", "")) & 0x3F) == 0:
                        partners = await _get_eth_partners()
                    continue
                raw_val = int(log.get("data", "0x0"), 16)
                value = raw_val / (10 ** DECIMALS[addr])
                # threshold: $10M+
                if value < 10_000_000:
                    continue
                asset = "USDC" if addr == USDC else ("USDT" if addr == USDT else "DAI")
                signal: Dict[str, Any] = {
                    "type": "godark_prep",
                    "chain": "ethereum",
                    "asset": asset,
                    "usd_value": float(value),
                    "to": to_addr,
                    "token": addr,
                    "tx_hash": log.get("transactionHash"),
                    "timestamp": int(time.time()),
                    "summary": f"GoDark Prep: ${value:,.1f} {asset} → Partner",
                    "tags": ["GoDark Prep"],
                }
                await publish_signal(signal)
                print(f"[GODARK] Prep: ${value:,.1f} {asset} → {to_addr[:10]}...")
            except Exception as e:
                print("[GODARK] ETH scanner error:", repr(e))
                await asyncio.sleep(2)
