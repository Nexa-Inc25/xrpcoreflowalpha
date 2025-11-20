from typing import Any, Dict

import asyncio
from web3 import Web3

from app.config import RENEGADE_VERIFIER, RENEGADE_MANAGER

# ERC20 Transfer topic
_TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"

# Stablecoin decimals (same as GoDark ETH scanner)
_USD_DECIMALS = {
    # USDC
    "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48": 6,
    # USDT
    "0xdac17f958d2ee523a2206206994597c13d831ec7": 6,
    # DAI
    "0x6b175474e89094c44da98b954eedeac495271d0f": 18,
}


def is_renegade_proof(tx: Any) -> bool:
    """Heuristic detector for Renegade verifier calls.

    Uses configured RENEGADE_VERIFIER plus gas/input length.
    Safe no-op if verifier is not configured.
    """
    if not RENEGADE_VERIFIER:
        return False
    try:
        to_addr = (tx.get("to") or "").lower()
        if to_addr != RENEGADE_VERIFIER:
            return False
        gas = int(tx.get("gas", 0))
        if gas < 500_000:
            return False
        input_data = tx.get("input", "0x") or "0x"
        # Proof calldata is typically large but bounded
        if len(input_data) < 600 or len(input_data) > 4000:
            return False
        return True
    except Exception:
        return False


async def tag_renegade_settlement(signal: Dict[str, Any], w3: Web3, usd_threshold: float = 10_000_000.0) -> Dict[str, Any]:
    """Best-effort tag for Renegade settlements based on post-proof ERC20 transfers.

    Inspects the transaction receipt for large stablecoin transfers shortly after
    the verifier call. Adds "Renegade Settlement Confirmed" tag when a transfer
    above usd_threshold is detected. On any error, returns the signal unchanged.
    """
    try:
        tx_hash = signal.get("tx_hash") or signal.get("hash")
        if not tx_hash:
            return signal
        try:
            rec = await asyncio.to_thread(w3.eth.get_transaction_receipt, tx_hash)
        except Exception:
            return signal
        logs = getattr(rec, "logs", None) or []
        if not logs:
            return signal
        has_large = False
        for log in logs:
            try:
                if (log.get("topics") or [None])[0] != _TRANSFER_TOPIC:
                    continue
                token = (log.get("address") or "").lower()
                dec = _USD_DECIMALS.get(token)
                if dec is None:
                    continue
                raw_val = int(log.get("data") or "0x0", 16)
                val = raw_val / (10 ** dec)
                # Treat these as USD amounts for stables
                if val >= usd_threshold:
                    has_large = True
                    break
            except Exception:
                continue
        if has_large:
            tags = list(signal.get("tags") or [])
            if "Renegade Settlement Confirmed" not in tags:
                tags.append("Renegade Settlement Confirmed")
            signal["tags"] = tags
        return signal
    except Exception:
        return signal
