import asyncio
from typing import Optional

import httpx

RIPPLE_DATA_API = "https://data.ripple.com/v2/transactions/"


async def _fetch_tx(tx_hash: str) -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            r = await client.get(f"{RIPPLE_DATA_API}{tx_hash}", params={"binary": "false"})
            if r.status_code != 200:
                return None
            data = r.json()
            if not data or not data.get("success"):
                return None
            return data.get("transaction")
    except Exception:
        return None


async def verify_xrpl_payment(tx_hash: str, expected_drops: int, timeout_sec: int = 30) -> bool:
    """Poll Ripple Data API until the tx appears or timeout. Validate Amount in drops."""
    deadline = asyncio.get_event_loop().time() + timeout_sec
    while asyncio.get_event_loop().time() < deadline:
        tx = await _fetch_tx(tx_hash)
        if tx and isinstance(tx, dict):
            try:
                if tx.get("TransactionType") != "Payment":
                    return False
                amt = tx.get("Amount")
                if isinstance(amt, str) and amt.isdigit():
                    return int(amt) == int(expected_drops)
                # IssuedCurrency payments carry dict amount; treat as mismatch for this validator
                return False
            except Exception:
                return False
        await asyncio.sleep(2)
    return False


async def verify_xrpl_tx_exists(tx_hash: str, timeout_sec: int = 30) -> bool:
    """Poll Ripple Data API until the tx appears or timeout."""
    deadline = asyncio.get_event_loop().time() + timeout_sec
    while asyncio.get_event_loop().time() < deadline:
        tx = await _fetch_tx(tx_hash)
        if tx and isinstance(tx, dict):
            return True
        await asyncio.sleep(2)
    return False
