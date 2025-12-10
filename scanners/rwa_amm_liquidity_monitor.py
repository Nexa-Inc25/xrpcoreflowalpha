import asyncio
import time
from typing import Any, Dict, Optional

from app.redis_utils import get_redis, REDIS_ENABLED
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import Subscribe, ServerInfo
from utils.retry import async_retry

from app.config import XRPL_WSS, REDIS_URL, TRUSTLINE_WATCHED_ISSUERS, GODARK_XRPL_PARTNERS, RWA_AMM_CHANGE_THRESHOLD_PCT
from bus.signal_bus import publish_signal
from utils.tx_validate import validate_tx
from alerts.slack import send_slack_alert, build_rich_slack_payload

RWA_AMM_STATE_KEY = "rwa:amm:pools"


async def _get_redis() :
    return await get_redis()


def _is_rwa_pool(final_fields: Dict[str, Any]) -> bool:
    # AMM ledger object has Asset and Asset2 describing pool assets
    # IssuedCurrency looks like {"currency":"USD","issuer":"r..."}
    for key in ("Asset", "Asset2"):
        a = final_fields.get(key)
        if isinstance(a, dict):
            issuer = (a.get("issuer") or "").lower()
            if issuer and issuer in {x.lower() for x in TRUSTLINE_WATCHED_ISSUERS}:
                return True
    return False


def _pool_id(final_fields: Dict[str, Any]) -> str:
    # Prefer ledger index if present; else compose from assets
    idx = final_fields.get("LedgerIndex") or final_fields.get("index")
    if isinstance(idx, str) and idx:
        return idx
    a1 = final_fields.get("Asset")
    a2 = final_fields.get("Asset2")
    def _fmt(a: Any) -> str:
        if isinstance(a, dict):
            return f"{a.get('currency','')}:{a.get('issuer','')}"
        return str(a)
    return f"{_fmt(a1)}|{_fmt(a2)}"


def _lp_change_pct(prev: Optional[str], final: Optional[str]) -> Optional[float]:
    try:
        if prev is None or final is None:
            return None
        pv = float(prev)
        fv = float(final)
        if pv <= 0:
            return None
        return (fv - pv) / pv
    except Exception:
        return None


async def start_rwa_amm_monitor():
    if not XRPL_WSS:
        return
    assert ("xrplcluster.com" in XRPL_WSS) or ("ripple.com" in XRPL_WSS), "NON-MAINNET WSS – FATAL ABORT"
    r = await _get_redis()
    async with AsyncWebsocketClient(XRPL_WSS) as client:
        @async_retry(max_attempts=5, delay=1, backoff=2)
        async def _req(payload):
            return await client.request(payload)
        await _req(Subscribe(streams=["transactions"]))
        async def _keepalive():
            while True:
                try:
                    await _req(ServerInfo())
                except Exception:
                    pass
                await asyncio.sleep(20)
        asyncio.create_task(_keepalive())
        async for msg in client:
            try:
                tx = msg.get("transaction") or {}
                meta = msg.get("meta") or msg.get("metaData") or {}
                ttype = tx.get("TransactionType")
                if ttype not in {"AMMDeposit", "AMMWithdraw", "AMMVote"}:
                    continue
                tx_hash = tx.get("hash")
                # Validate tx exists on livenet
                ok = await validate_tx("xrpl", tx_hash, timeout_sec=10)
                if not ok:
                    continue
                nodes = meta.get("AffectedNodes") or []
                amm_node = None
                for n in nodes:
                    x = n.get("ModifiedNode") or n.get("CreatedNode") or n.get("DeletedNode")
                    if x and x.get("LedgerEntryType") == "AMM":
                        amm_node = x
                        break
                if not amm_node:
                    continue
                ff = amm_node.get("FinalFields") or {}
                pf = amm_node.get("PreviousFields") or {}
                if not ff:
                    continue
                pool = _pool_id(ff)
                if not _is_rwa_pool(ff):
                    # Only track RWA pools per spec
                    continue
                prev_lp = pf.get("LPTokenBalance")
                final_lp = ff.get("LPTokenBalance")
                change = _lp_change_pct(prev_lp, final_lp)
                tags = ["RWA AMM Liquidity Shift"]
                urgency = "MEDIUM"
                if ttype == "AMMVote":
                    # Check fee shift in bps
                    try:
                        prev_fee = int(pf.get("TradingFee")) if pf.get("TradingFee") is not None else None
                        new_fee = int(ff.get("TradingFee")) if ff.get("TradingFee") is not None else None
                        if prev_fee is not None and new_fee is not None:
                            if abs(new_fee - prev_fee) >= 100:
                                tags.append("RWA AMM Fee Shift")
                                urgency = "MEDIUM"
                    except Exception:
                        pass
                else:
                    if change is None or abs(change) < (RWA_AMM_CHANGE_THRESHOLD_PCT / 100.0):
                        continue
                    if change > 0:
                        tags.append("RWA AMM Deposit")
                        urgency = "HIGH"
                    else:
                        tags.append("RWA AMM Withdrawal")
                        urgency = "HIGH"
                # GoDark partner involvement
                # Include dynamic partners from Redis
                gd_partners = {a.lower() for a in GODARK_XRPL_PARTNERS}
                try:
                    dyn = await r.smembers("godark:partners:xrpl")
                    gd_partners |= {x.lower() for x in (dyn or [])}
                except Exception:
                    pass
                accs = set()
                accs.add((tx.get("Account") or "").lower())
                for n in nodes:
                    for k in ("CreatedNode", "ModifiedNode", "DeletedNode"):
                        x = n.get(k) or {}
                        try:
                            elem = x.get("FinalFields") or x.get("NewFields") or {}
                            a = (elem.get("Account") or "").lower()
                            if a:
                                accs.add(a)
                        except Exception:
                            pass
                if gd_partners.intersection(accs):
                    tags.append("GoDark RWA AMM")
                    urgency = "CRITICAL"
                # Build signal
                signal: Dict[str, Any] = {
                    "type": "rwa_amm",
                    "amm_id": pool,
                    "tx_hash": tx_hash,
                    "timestamp": int(time.time()),
                    "tags": tags,
                    "urgency": urgency,
                    "amm_liquidity_change": {"lp_change_pct": round(change, 4) if change is not None else None},
                    "summary": f"{ttype} {('+') if (change or 0)>0 else ''}{round((change or 0)*100,2)}% in RWA pool",
                }
                # Publish and store last LP
                await r.hset(RWA_AMM_STATE_KEY, pool, final_lp or "")
                await publish_signal(signal)
                await send_slack_alert(build_rich_slack_payload(signal))
            except Exception:
                await asyncio.sleep(0.05)
