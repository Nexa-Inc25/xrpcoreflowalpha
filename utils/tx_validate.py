import asyncio
from typing import Optional

import httpx

from app.config import ETHERSCAN_API_KEY

XRPL_LIVENET_TX_URL = "https://livenet.xrpl.org/transactions/"
ETHERSCAN_TX_URL = "https://api.etherscan.io/api"


async def validate_tx(chain: str, tx_hash: str, timeout_sec: int = 10) -> bool:
    try:
        async with httpx.AsyncClient(timeout=timeout_sec) as client:
            if chain.lower() == "xrpl":
                r = await client.get(f"{XRPL_LIVENET_TX_URL}{tx_hash}")
                return r.status_code == 200
            else:
                params = {
                    "module": "proxy",
                    "action": "eth_getTransactionByHash",
                    "txhash": tx_hash,
                    "apikey": ETHERSCAN_API_KEY or "",
                }
                r = await client.get(ETHERSCAN_TX_URL, params=params)
                if r.status_code != 200:
                    return False
                data = r.json()
                # Etherscan returns {"jsonrpc":"2.0","id":1,"result":null} if not found
                res: Optional[dict] = data.get("result") if isinstance(data, dict) else None
                return res is not None
    except Exception:
        return False
