import asyncio
import json
import random
import time
from typing import Any, Dict, Optional, Tuple, List

from app.redis_utils import get_redis, REDIS_ENABLED
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import BookOffers, ServerInfo
from xrpl.models.currencies import XRP, IssuedCurrency
from utils.retry import async_retry

from app.config import XRPL_WSS, REDIS_URL, DEX_ORDERBOOK_PAIRS, TRUSTLINE_WATCHED_ISSUERS, GODARK_XRPL_PARTNERS
from bus.signal_bus import publish_signal
from alerts.slack import send_slack_alert, build_rich_slack_payload
from utils.price import get_price_usd

OB_STATE_KEY = "ob:state"
STABLE_CODES = {"USD", "USDC", "USDT"}


def _err_str(e: Exception) -> str:
    s = str(e)
    return f"{e.__class__.__name__}: {s}" if s else repr(e)


async def _get_redis() :
    return await get_redis()


def _parse_pair(pair: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], str]]:
    """Parse pair string like 'XRP/USD.rXYZ...' -> (base, quote, key). Require issuer for non-XRP quote/base."""
    try:
        base_raw, quote_raw = pair.split("/")
        def _tok(tok: str) -> Tuple[str, Optional[str]]:
            if "." in tok:
                cur, issuer = tok.split(".", 1)
                return cur.upper(), issuer
            return tok.upper(), None
        base_cur, base_iss = _tok(base_raw)
        quote_cur, quote_iss = _tok(quote_raw)
        # Require issuer for non-XRP currencies
        if base_cur != "XRP" and not base_iss:
            return None
        if quote_cur != "XRP" and not quote_iss:
            return None
        def _fmt(cur: str, iss: Optional[str]) -> Dict[str, Any]:
            return {"currency": cur} if cur == "XRP" else {"currency": cur, "issuer": iss}
        base = _fmt(base_cur, base_iss)
        quote = _fmt(quote_cur, quote_iss)
        key = f"{base_cur}/{quote_cur}.{quote_iss or ''}"
        return base, quote, key
    except Exception:
        return None


def _amt_to_float_xrp_or_value(amt: Any, cur_symbol: str) -> Optional[float]:
    try:
        if isinstance(amt, str):
            # drops for XRP
            if cur_symbol == "XRP" and amt.isdigit():
                return int(amt) / 1_000_000
            return None
        if isinstance(amt, dict):
            v = float(amt.get("value") or 0)
            return v
    except Exception:
        return None
    return None


def _offer_usd(offer: Dict[str, Any], xrp_usd: float) -> Optional[float]:
    tg = offer.get("TakerGets")
    tp = offer.get("TakerPays")
    def _cur(a: Any) -> Optional[str]:
        if isinstance(a, str):
            return "XRP"
        if isinstance(a, dict):
            return a.get("currency")
        return None
    candidates: List[float] = []
    for a in (tg, tp):
        cur = _cur(a)
        if cur == "XRP":
            v = _amt_to_float_xrp_or_value(a, "XRP")
            if v is not None:
                candidates.append(v * float(xrp_usd))
        elif cur in STABLE_CODES:
            v = _amt_to_float_xrp_or_value(a, cur)
            if v is not None:
                candidates.append(v)
    if candidates:
        return max(candidates)
    return None


async def start_xrpl_orderbook_monitor():
    if not XRPL_WSS:
        return
    assert ("xrplcluster.com" in XRPL_WSS) or ("ripple.com" in XRPL_WSS), "NON-MAINNET WSS – FATAL ABORT"
    r = await _get_redis()
    backoff = 5.0
    while True:
        keepalive_task: asyncio.Task | None = None
        try:
            async with AsyncWebsocketClient(XRPL_WSS) as client:
                @async_retry(max_attempts=5, delay=1, backoff=2)
                async def _req(payload):
                    return await client.request(payload)

                async def _keepalive():
                    while True:
                        try:
                            await _req(ServerInfo())
                        except Exception:
                            pass
                        await asyncio.sleep(20)

                keepalive_task = asyncio.create_task(_keepalive())

                while True:
                    try:
                        xrp_usd = 0.0
                        try:
                            xrp_usd = float(await get_price_usd("xrp"))
                        except Exception:
                            xrp_usd = 0.0

                        gd_partners = {a.lower() for a in GODARK_XRPL_PARTNERS}
                        try:
                            dyn = await r.smembers("godark:partners:xrpl")
                            gd_partners |= {x.lower() for x in (dyn or [])}
                        except Exception:
                            pass

                        def _asset_from_str(tok: str):
                            if "." in tok:
                                cur, iss = tok.split(".", 1)
                                if cur.upper() == "XRP":
                                    return XRP()
                                return IssuedCurrency(currency=cur.upper(), issuer=iss)
                            return XRP() if tok.upper() == "XRP" else IssuedCurrency(currency=tok.upper(), issuer="")

                        for pair in DEX_ORDERBOOK_PAIRS:
                            parsed = _parse_pair(pair)
                            if not parsed:
                                continue
                            base, quote, key = parsed
                            base_raw, quote_raw = pair.split("/")
                            if base.get("currency") != "XRP" and not base.get("issuer"):
                                continue
                            if quote.get("currency") != "XRP" and not quote.get("issuer"):
                                continue
                            asks_req = BookOffers(taker_gets=_asset_from_str(base_raw), taker_pays=_asset_from_str(quote_raw), limit=20, ledger_index="validated")
                            bids_req = BookOffers(taker_gets=_asset_from_str(quote_raw), taker_pays=_asset_from_str(base_raw), limit=20, ledger_index="validated")
                            asks_resp = await _req(asks_req)
                            bids_resp = await _req(bids_req)
                            asks: List[Dict[str, Any]] = asks_resp.result.get("offers", [])
                            bids: List[Dict[str, Any]] = bids_resp.result.get("offers", [])

                            ask_depth = 0.0
                            bid_depth = 0.0
                            whale_offer_usd = 0.0
                            for off in asks[:10]:
                                usd = _offer_usd(off, xrp_usd)
                                if usd is not None:
                                    ask_depth += usd
                                    whale_offer_usd = max(whale_offer_usd, usd)
                            for off in bids[:10]:
                                usd = _offer_usd(off, xrp_usd)
                                if usd is not None:
                                    bid_depth += usd
                                    whale_offer_usd = max(whale_offer_usd, usd)

                            def _best_quality(ofs: List[Dict[str, Any]]) -> Optional[float]:
                                try:
                                    if not ofs:
                                        return None
                                    q = ofs[0].get("quality")
                                    return float(q) if q is not None else None
                                except Exception:
                                    return None

                            best_ask_q = _best_quality(asks)
                            best_bid_q = _best_quality(bids)
                            spread_bps = None
                            try:
                                if best_ask_q and best_bid_q and best_bid_q > 0:
                                    spread_bps = max(0.0, (best_ask_q / best_bid_q - 1.0) * 10_000)
                            except Exception:
                                spread_bps = None

                            prev_raw = await r.hget(OB_STATE_KEY, key)
                            prev = json.loads(prev_raw) if prev_raw else {}

                            def _pct_change(prev_v: float, cur_v: float) -> float:
                                if prev_v <= 0:
                                    return 1.0 if cur_v > 0 else 0.0
                                return (cur_v - prev_v) / prev_v

                            change = {
                                "bid_change_pct": _pct_change(float(prev.get("bid_depth_usd") or 0.0), bid_depth),
                                "ask_change_pct": _pct_change(float(prev.get("ask_depth_usd") or 0.0), ask_depth),
                                "imbalance_ratio": (bid_depth / max(ask_depth, 1e-9)) if (bid_depth > 0 or ask_depth > 0) else 1.0,
                            }

                            tags: List[str] = ["OB Liquidity Shift"]
                            urgency = "MEDIUM"
                            if max(bid_depth, ask_depth) >= 10_000_000:
                                tags.append("OB Depth Surge")
                                urgency = "HIGH"
                            total_depth = bid_depth + ask_depth
                            if total_depth >= 5_000_000 and (change["imbalance_ratio"] > 3 or change["imbalance_ratio"] < (1/3)):
                                tags.append("OB Imbalance")
                                urgency = "CRITICAL"
                            if whale_offer_usd >= 5_000_000:
                                tags.append("OB Whale Move")
                                urgency = "CRITICAL"

                            issuers = set()
                            if base.get("currency") != "XRP":
                                issuers.add((base.get("issuer") or "").lower())
                            if quote.get("currency") != "XRP":
                                issuers.add((quote.get("issuer") or "").lower())
                            if any(i in {x.lower() for x in TRUSTLINE_WATCHED_ISSUERS} for i in issuers):
                                tags.append("RWA OB Event")
                            if any(i in gd_partners for i in issuers):
                                tags.append("GoDark OB Shift")
                                urgency = "CRITICAL"

                            if abs(change["bid_change_pct"]) < 0.2 and abs(change["ask_change_pct"]) < 0.2 and "OB Depth Surge" not in tags and "OB Imbalance" not in tags and "OB Whale Move" not in tags:
                                await r.hset(OB_STATE_KEY, key, json.dumps({
                                    "bid_depth_usd": bid_depth,
                                    "ask_depth_usd": ask_depth,
                                    "best_ask_q": best_ask_q,
                                    "best_bid_q": best_bid_q,
                                    "timestamp": int(time.time()),
                                }))
                                continue

                            signal: Dict[str, Any] = {
                                "type": "orderbook",
                                "pair": key,
                                "bid_depth_usd": round(bid_depth, 2),
                                "ask_depth_usd": round(ask_depth, 2),
                                "spread_bps": round(spread_bps, 2) if spread_bps is not None else None,
                                "change": {
                                    "bid_change_pct": round(change["bid_change_pct"], 4),
                                    "ask_change_pct": round(change["ask_change_pct"], 4),
                                    "imbalance_ratio": round(change["imbalance_ratio"], 2),
                                },
                                "tags": tags,
                                "urgency": urgency,
                                "timestamp": int(time.time()),
                                "summary": f"{key}: bid ${bid_depth:,.0f} | ask ${ask_depth:,.0f} | spread {round(spread_bps,2) if spread_bps is not None else 'n/a'} bps",
                            }

                            await r.hset(OB_STATE_KEY, key, json.dumps({
                                "bid_depth_usd": bid_depth,
                                "ask_depth_usd": ask_depth,
                                "best_ask_q": best_ask_q,
                                "best_bid_q": best_bid_q,
                                "timestamp": int(time.time()),
                            }))
                            await publish_signal(signal)
                            await send_slack_alert(build_rich_slack_payload(signal))
                            try:
                                print(f"[OB] {signal['summary']}")
                            except Exception:
                                pass

                        await asyncio.sleep(15)
                    except Exception:
                        await asyncio.sleep(1)

            backoff = 5.0
        except Exception as e:
            print(f"[XRPL] Orderbook monitor error: {_err_str(e)}")
            await asyncio.sleep(backoff + random.random() * 2.0)
            backoff = min(backoff * 1.7, 60.0)
        finally:
            if keepalive_task is not None:
                keepalive_task.cancel()
                try:
                    await keepalive_task
                except Exception:
                    pass
