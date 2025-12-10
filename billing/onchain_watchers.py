import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.redis_utils import get_redis, REDIS_ENABLED
from web3 import Web3
from web3.types import LogReceipt

from app.config import (
    REDIS_URL,
    SOLANA_RPC_URL,
    SOL_TREASURY,
    SOL_USDC_MINT,
    ONCHAIN_POLL_SECONDS,
    ONCHAIN_BACKOFF_MAX,
    ETH_TREASURY,
    ETH_USDC_ADDRESS,
    ALCHEMY_WS_URL,
)
from observability.metrics import onchain_receipt_total


_redis = None  # Redis client instance
_http: Optional[httpx.AsyncClient] = None
_w3: Optional[Web3] = None


async def _r() :
    global _redis
    if _redis is None:
        _redis = await get_redis()
    return _redis


async def _c() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(base_url=SOLANA_RPC_URL, timeout=10)
    return _http


async def _rpc(method: str, params: List[Any]) -> Any:
    c = await _c()
    resp = await c.post("/", json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params,
    })
    resp.raise_for_status()
    data = resp.json()
    return data.get("result")


def _sol_estimate_sol_from_tx(tx: Dict[str, Any], treasury: str) -> float:
    # Estimate net SOL to treasury from pre/post balances
    try:
        meta = tx.get("meta") or {}
        message = (tx.get("transaction") or {}).get("message") or {}
        account_keys = (message.get("accountKeys") or [])
        pre_bal = meta.get("preBalances") or []
        post_bal = meta.get("postBalances") or []
        # locate treasury index
        idx = None
        for i, k in enumerate(account_keys):
            key = k.get("pubkey") if isinstance(k, dict) else k
            if str(key) == str(treasury):
                idx = i
                break
        if idx is None:
            return 0.0
        lamports = float(post_bal[idx] - pre_bal[idx])
        return max(0.0, lamports / 1_000_000_000.0)
    except Exception:
        return 0.0


def _sol_extract_memo(tx: Dict[str, Any]) -> Optional[str]:
    try:
        msg = (tx.get("transaction") or {}).get("message") or {}
        ins = msg.get("instructions") or []
        for i in ins:
            # jsonParsed carries program as string and parsed content
            program = i.get("program") or i.get("programId")
            if isinstance(program, dict):
                program = program.get("_id")
            data = i.get("parsed") or i.get("data")
            if isinstance(data, dict) and data.get("type") == "memo":
                m = data.get("info", {}).get("memo")
                if m:
                    return str(m)
            # fallback: raw data may be memo text
            if isinstance(data, str) and len(data) < 256:
                if data.startswith("pay_"):
                    return data
        logs = ((tx.get("meta") or {}).get("logMessages") or [])
        for l in logs:
            if isinstance(l, str) and "Memo" in l and "pay_" in l:
                # crude parse
                try:
                    start = l.find("pay_")
                    if start >= 0:
                        token = l[start: start + 80]
                        token = token.split(" ")[0]
                        return token
                except Exception:
                    continue
    except Exception:
        return None
    return None


async def _apply_onchain_payment(ref: str, asset: str, amount: float, txid: str, email_hint: Optional[str]) -> None:
    r = await _r()
    pending = await r.hgetall(f"onchain:pending:{ref}")
    if not pending:
        return
    if pending.get("status") != "pending":
        return
    # Validate asset match
    if (pending.get("asset") or "").lower() != asset.lower():
        return
    # Amount tolerance: accept >= 98% of expected (network fees, dust)
    try:
        expected = float(pending.get("amount") or 0.0)
    except Exception:
        expected = 0.0
    if expected <= 0:
        return
    if amount < expected * 0.98:
        return
    duration = (pending.get("duration") or "monthly").lower()
    tier = (pending.get("tier") or "pro").lower()
    email = (pending.get("email") or email_hint or "").strip().lower()
    # Mark receipt and upgrade if email available
    now = int(time.time())
    exp = now + (365 * 24 * 3600 if duration == "annual" else 30 * 24 * 3600)
    await r.hset(f"onchain:receipt:{txid}", mapping={
        "ref": ref,
        "asset": asset.lower(),
        "amount": str(amount),
        "tier": tier,
        "duration": duration,
        "email": email,
        "ts": str(now),
        "expires": str(exp),
    })
    await r.hset(f"onchain:pending:{ref}", mapping={"status": "paid", "txid": txid, "paid_at": str(now)})
    if email:
        await r.set(f"billing:user:{email}", tier)
        await r.set(f"billing:user_expiry:{email}", str(exp))
        await r.set(f"billing:user_source:{email}", f"onchain_{asset.lower()}")
    try:
        onchain_receipt_total.labels(asset=asset.lower(), tier=tier).inc()
    except Exception:
        pass


async def start_onchain_maintenance() -> None:
    # Purge stale pending payments older than 2 hours, run hourly
    r = await _r()
    while True:
        try:
            cutoff = int(time.time()) - 2 * 3600
            async for key in r.scan_iter(match="onchain:pending:*", count=500):
                try:
                    p = await r.hgetall(key)
                    if not p:
                        await r.delete(key)
                        continue
                    created = int(p.get("created_at") or 0)
                    status = (p.get("status") or "").lower()
                    if status != "pending":
                        continue
                    if created and created < cutoff:
                        await r.delete(key)
                except Exception:
                    continue
        except Exception:
            pass
        await asyncio.sleep(3600)


async def start_solana_onchain_watcher() -> None:
    if not SOLANA_RPC_URL or not SOL_TREASURY:
        return
    sleep_s = max(1, int(ONCHAIN_POLL_SECONDS))
    before: Optional[str] = None
    while True:
        try:
            params: Dict[str, Any] = {"limit": 50}
            if before:
                params["before"] = before
            entries = await _rpc("getSignaturesForAddress", [SOL_TREASURY, params])
            if isinstance(entries, list) and entries:
                for e in reversed(entries):
                    sig = e.get("signature") if isinstance(e, dict) else None
                    if not sig:
                        continue
                    r = await _r()
                    if await r.exists(f"onchain:sol:seen:{sig}"):
                        continue
                    tx = await _rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
                    if not isinstance(tx, dict):
                        continue
                    ref = _sol_extract_memo(tx)
                    amt_sol = _sol_estimate_sol_from_tx(tx, SOL_TREASURY)
                    # Try SPL USDC incoming value from token balances owned by treasury
                    usd_est = 0.0
                    try:
                        meta = tx.get("meta") or {}
                        pre = meta.get("preTokenBalances") or []
                        post = meta.get("postTokenBalances") or []
                        def _map(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], float]:
                            out: Dict[Tuple[str, str], float] = {}
                            for r in rows:
                                try:
                                    mint = r.get("mint") or ""
                                    owner = (r.get("owner") or "").strip()
                                    if owner != SOL_TREASURY:
                                        continue
                                    if mint != SOL_USDC_MINT:
                                        continue
                                    amt = r.get("uiTokenAmount", {}).get("uiAmount")
                                    if amt is None:
                                        dec = int(r.get("uiTokenAmount", {}).get("decimals") or 6)
                                        raw = float(r.get("uiTokenAmount", {}).get("amount") or 0)
                                        amt = raw / (10 ** dec)
                                    out[(mint, owner)] = float(amt or 0.0)
                                except Exception:
                                    continue
                            return out
                        pre_m = _map(pre if isinstance(pre, list) else [])
                        post_m = _map(post if isinstance(post, list) else [])
                        keys = set(pre_m.keys()) | set(post_m.keys())
                        for k in keys:
                            d = float(post_m.get(k, 0.0)) - float(pre_m.get(k, 0.0))
                            if d > 0:
                                usd_est += d
                    except Exception:
                        usd_est = 0.0
                    if ref and amt_sol > 0:
                        await _apply_onchain_payment(ref, "sol", amt_sol, sig, None)
                    if ref and usd_est > 0:
                        await _apply_onchain_payment(ref, "usdc", usd_est, sig, None)
                    await r.set(f"onchain:sol:seen:{sig}", "1", ex=7 * 24 * 3600)
                before = entries[-1].get("signature") or before
            sleep_s = max(1, int(ONCHAIN_POLL_SECONDS))
        except Exception:
            sleep_s = min(int(ONCHAIN_BACKOFF_MAX), max(sleep_s * 2, sleep_s + 1))
        await asyncio.sleep(sleep_s)


def _hex_to_ascii(input_hex: str) -> str:
    try:
        x = input_hex[2:] if input_hex.startswith("0x") else input_hex
        b = bytes.fromhex(x)
        return b.decode("utf-8", errors="ignore")
    except Exception:
        return ""


async def _match_pending_by_amount(asset: str, amount: float, window_s: int = 3600) -> Optional[str]:
    r = await _r()
    # Brute-force scan small set of pending refs
    async for key in r.scan_iter(match="onchain:pending:*", count=200):
        try:
            p = await r.hgetall(key)
            if not p:
                continue
            if (p.get("asset") or "").lower() != asset.lower():
                continue
            amt_expected = float(p.get("amount") or 0.0)
            created = int(p.get("created_at") or 0)
            if amt_expected <= 0 or abs(amount - amt_expected) > max(0.02 * amt_expected, 0.000001):
                continue
            if int(time.time()) - created > window_s:
                continue
            # return ref extracted from key
            if isinstance(key, str):
                return key.split(":", 2)[-1]
            else:
                k = key.decode() if hasattr(key, "decode") else str(key)
                return k.split(":", 2)[-1]
        except Exception:
            continue
    return None


_TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)").hex()  # type: ignore[attr-defined]


async def start_eth_onchain_watcher() -> None:
    if not ETH_TREASURY or not ALCHEMY_WS_URL:
        return
    global _w3
    try:
        _w3 = Web3(Web3.WebsocketProvider(ALCHEMY_WS_URL))  # type: ignore[attr-defined]
    except Exception:
        _w3 = None
    if _w3 is None:
        return
    r = await _r()
    last_block_key = "onchain:eth:last_block"
    sleep_s = max(1, int(ONCHAIN_POLL_SECONDS))
    while True:
        try:
            head = _w3.eth.block_number  # type: ignore[attr-defined]
            try:
                last = await r.get(last_block_key)
                start = int(last) + 1 if last else head
            except Exception:
                start = head
            if start > head:
                await asyncio.sleep(sleep_s)
                continue
            for num in range(start, head + 1):
                blk = _w3.eth.get_block(num, full_transactions=True)  # type: ignore[attr-defined]
                # Process ETH transfers
                for tx in blk.transactions:  # type: ignore[attr-defined]
                    try:
                        to_addr = (tx.to or "").lower()
                        if not to_addr or to_addr != ETH_TREASURY.lower():
                            continue
                        val_wei = int(tx.value)
                        if val_wei <= 0:
                            continue
                        txid = tx.hash.hex()
                        if await r.exists(f"onchain:eth:seen:{txid}"):
                            continue
                        try:
                            inp_hex = tx.input.hex() if hasattr(tx.input, "hex") else str(tx.input)
                        except Exception:
                            inp_hex = ""
                        memo = _hex_to_ascii(inp_hex)
                        ref = memo if memo.startswith("pay_") else (await _match_pending_by_amount("eth", val_wei / 1e18))
                        if ref:
                            await _apply_onchain_payment(ref, "eth", val_wei / 1e18, txid, None)
                        await r.set(f"onchain:eth:seen:{txid}", "1", ex=7 * 24 * 3600)
                    except Exception:
                        continue
                # Process USDC transfers
                for tx in blk.transactions:  # type: ignore[attr-defined]
                    try:
                        receipt = _w3.eth.get_transaction_receipt(tx.hash)  # type: ignore[attr-defined]
                    except Exception:
                        continue
                    try:
                        txid = tx.hash.hex()
                        if await r.exists(f"onchain:eth:seen_usdc:{txid}"):
                            continue
                        for lg in receipt.logs:
                            if lg.address.lower() != ETH_USDC_ADDRESS.lower():
                                continue
                            if not lg.topics or lg.topics[0].hex().lower() != _TRANSFER_TOPIC.lower():
                                continue
                            # topics[2] is 'to'
                            if len(lg.topics) < 3:
                                continue
                            to_addr = "0x" + lg.topics[2].hex()[-40:]
                            if to_addr.lower() != ETH_TREASURY.lower():
                                continue
                            # data is uint256 amount
                            amount_raw = int(lg.data, 16)
                            amount = amount_raw / 1_000_000.0  # USDC 6 decimals
                            try:
                                inp_hex2 = tx.input.hex() if hasattr(tx.input, "hex") else str(tx.input)
                            except Exception:
                                inp_hex2 = ""
                            memo = _hex_to_ascii(inp_hex2)
                            ref = memo if memo.startswith("pay_") else (await _match_pending_by_amount("usdc", amount))
                            if ref:
                                await _apply_onchain_payment(ref, "usdc", amount, txid, None)
                            await r.set(f"onchain:eth:seen_usdc:{txid}", "1", ex=7 * 24 * 3600)
                    except Exception:
                        continue
                await r.set(last_block_key, str(num))
            sleep_s = max(1, int(ONCHAIN_POLL_SECONDS))
        except Exception:
            sleep_s = min(int(ONCHAIN_BACKOFF_MAX), max(sleep_s * 2, sleep_s + 1))
        await asyncio.sleep(sleep_s)
