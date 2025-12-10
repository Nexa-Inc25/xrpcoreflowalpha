import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from app.redis_utils import get_redis, REDIS_ENABLED

from app.config import (
    SOLANA_RPC_URL,
    HUMIDIFI_PROGRAM_IDS,
    REDIS_URL,
    SOLANA_POLL_SECONDS,
    SOLANA_BACKOFF_MAX,
    SOLANA_PAGE_MAX,
)
from bus.signal_bus import publish_signal

_redis: Optional[redis.Redis] = None
_client: Optional[httpx.AsyncClient] = None


async def _r() :
    global _redis
    if _redis is None:
        _redis = await get_redis()
    return _redis


async def _c() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=SOLANA_RPC_URL, timeout=10)
    return _client


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


def _mk_summary(sig: str, program: str, usd_value: Optional[float] = None) -> str:
    if usd_value and usd_value > 0:
        return f"HumidiFi AMM swap ~${usd_value/1e6:.1f}m ({sig[:8]}.. {program[:8]}..)"
    return f"HumidiFi AMM tx {sig[:8]}.. program {program[:8]}.."


def _estimate_usd_from_meta(meta: Optional[Dict[str, Any]]) -> float:
    try:
        if not isinstance(meta, dict):
            return 0.0
        pre = meta.get("preTokenBalances") or []
        post = meta.get("postTokenBalances") or []
        # Known Solana stablecoin mints (USDC, USDT)
        STABLE_MINTS = {
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
            "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11mcCe8BenwNYB",  # USDT
        }
        def _to_map(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], float]:
            out: Dict[Tuple[str, str], float] = {}
            for r in rows:
                try:
                    mint = r.get("mint") or ""
                    owner = (r.get("owner") or "").lower()
                    if mint not in STABLE_MINTS or not owner:
                        continue
                    amt = r.get("uiTokenAmount", {}).get("uiAmount")
                    if amt is None:
                        # fallback if uiAmount missing
                        dec = int(r.get("uiTokenAmount", {}).get("decimals") or 6)
                        raw = float(r.get("uiTokenAmount", {}).get("amount") or 0)
                        amt = raw / (10 ** dec)
                    out[(mint, owner)] = float(amt or 0.0)
                except Exception:
                    continue
            return out
        pre_m = _to_map(pre if isinstance(pre, list) else [])
        post_m = _to_map(post if isinstance(post, list) else [])
        keys = set(pre_m.keys()) | set(post_m.keys())
        total_abs = 0.0
        for k in keys:
            d = float(post_m.get(k, 0.0)) - float(pre_m.get(k, 0.0))
            total_abs += abs(d)
        # Each transfer appears as +X & -X across accounts; divide by 2 to approximate size
        return max(0.0, total_abs / 2.0)
    except Exception:
        return 0.0


def _confidence_from_tx(usd_est: float, tx: Optional[Dict[str, Any]]) -> int:
    base = 50
    try:
        if usd_est >= 50_000_000:
            base = 95
        elif usd_est >= 20_000_000:
            base = 85
        elif usd_est >= 5_000_000:
            base = 70
        # Heuristic bumps from logs/instructions
        logs = []
        if isinstance(tx, dict):
            meta = tx.get("meta") or {}
            logs = meta.get("logMessages") or []
            ins = (((tx.get("transaction") or {}).get("message") or {}).get("instructions") or [])
            logs_text = " ".join([str(x) for x in logs]) + " " + " ".join([str(x) for x in ins])
            for token in ("swap", "route", "Jupiter", "Raydium", "Orca"):
                if token.lower() in logs_text.lower():
                    base = min(99, base + 5)
    except Exception:
        pass
    return int(max(0, min(99, base)))


async def _publish_sig(entry: Dict[str, Any], program: str) -> None:
    sig = entry.get("signature") or ""
    if not sig:
        return
    ts = entry.get("blockTime")
    try:
        ts = int(ts)
    except Exception:
        ts = int(time.time())
    slot = entry.get("slot")

    # Try to enrich with transaction details (best-effort)
    tx = None
    try:
        tx = await _rpc("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    except Exception:
        tx = None
    meta = (tx or {}).get("meta") if isinstance(tx, dict) else None
    fee = None
    try:
        fee = int((meta or {}).get("fee"))
    except Exception:
        fee = None

    usd_est = _estimate_usd_from_meta(meta)
    confidence = _confidence_from_tx(usd_est, tx)

    signal: Dict[str, Any] = {
        "type": "solana_amm",
        "network": "solana",
        "program_id": program,
        "tx_sig": sig,
        "slot": slot,
        "timestamp": ts,
        "summary": _mk_summary(sig, program, usd_est if usd_est > 0 else None),
        "tags": ["HumidiFi", "Dark AMM"],
    }
    if fee is not None:
        signal["fee_lamports"] = fee
    if usd_est and usd_est > 0:
        signal["usd_value"] = float(usd_est)
    signal["confidence"] = confidence

    try:
        await publish_signal(signal)
    except Exception:
        pass


async def _scan_program(program: str, page_max: int = 1) -> None:
    r = await _r()
    before: Optional[str] = None
    for _ in range(max(1, int(page_max))):
        params: Dict[str, Any] = {"limit": 50}
        if before:
            params["before"] = before
        entries = await _rpc("getSignaturesForAddress", [program, params])
        if not isinstance(entries, list) or not entries:
            break
        # Process oldest -> newest for chronological order
        for e in reversed(entries):
            if not isinstance(e, dict):
                continue
            sig = e.get("signature")
            if not sig:
                continue
            dedup_key = f"solana:sig:{sig}"
            exists = await r.exists(dedup_key)
            if exists:
                continue
            await _publish_sig(e, program)
            # Keep dedupe ~7 days
            await r.set(dedup_key, "1", ex=7 * 24 * 3600)
        before = entries[-1].get("signature") or before


async def start_solana_humidifi_worker() -> None:
    if not SOLANA_RPC_URL or not HUMIDIFI_PROGRAM_IDS:
        return
    sleep_s = max(1, int(SOLANA_POLL_SECONDS))
    while True:
        try:
            for program in HUMIDIFI_PROGRAM_IDS:
                await _scan_program(program, page_max=SOLANA_PAGE_MAX)
                await asyncio.sleep(0)
            # success path resets backoff
            sleep_s = max(1, int(SOLANA_POLL_SECONDS))
        except Exception:
            # backoff on any RPC/HTTP error
            sleep_s = min(int(SOLANA_BACKOFF_MAX), max(sleep_s * 2, sleep_s + 1))
        await asyncio.sleep(sleep_s)
