import asyncio
import time
from typing import Dict, Any, List, Optional

import redis.asyncio as redis

from app.config import REDIS_URL
from bus.signal_bus import fetch_recent_signals, fetch_recent_cross_signals

_redis: Optional[redis.Redis] = None


async def _r() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


def _norm_network(n: Optional[str]) -> str:
    s = (n or "").strip().lower()
    if s.startswith("eth"):
        return "ethereum"
    if s.startswith("sol"):
        return "solana"
    return s


async def _should_send(kind: str, sig: Dict[str, Any], min_usd: float) -> bool:
    try:
        if kind == "surge":
            # handled at batch level
            return True
        if kind == "zk":
            v = float(sig.get("usd_value") or 0.0)
            return v >= min_usd
        if kind == "solana_amm":
            v = float(sig.get("usd_value") or 0.0)
            return v >= min_usd
    except Exception:
        return False
    return False


async def _send_stub(token: str, platform: str, title: str, body: str, deep_link: str) -> None:
    r = await _r()
    ts = int(time.time())
    await r.hset(f"push:last:{token}", mapping={
        "platform": platform,
        "title": title,
        "body": body,
        "link": deep_link,
        "ts": str(ts),
    })
    await r.lpush("push:log", f"{ts}|{platform}|{token[:6]}|{title}|{body}")
    await r.ltrim("push:log", 0, 999)


async def start_push_worker() -> None:
    r = await _r()
    cooldown_s = 300
    while True:
        try:
            # Pull recent signals and cross-signals
            recent = await fetch_recent_signals(window_seconds=300)
            crosses = await fetch_recent_cross_signals(limit=20)
            # Determine triggers
            triggers: List[Dict[str, Any]] = []
            # Big single events
            for s in recent:
                t = (s.get("type") or "").lower()
                if t in ("zk", "solana_amm"):
                    triggers.append({"kind": t, "sig": s})
            # Surge-like cross signal
            for c in crosses:
                try:
                    conf = int(c.get("confidence", 0))
                    if conf >= 90:
                        triggers.append({"kind": "surge", "sig": c})
                        break
                except Exception:
                    continue
            if triggers:
                tokens = await r.smembers("push:tokens")
                for tkn in tokens or []:
                    dev = await r.hgetall(f"push:device:{tkn}")
                    if not dev:
                        continue
                    plat = dev.get("platform") or "ios"
                    prefs = set([p for p in (dev.get("preferences") or "").split(",") if p])
                    email = (dev.get("email") or "").strip().lower()
                    # Per-user preferences
                    min_usd = 25_000_000.0
                    allowed_networks: Optional[set] = None
                    allowed_types: Optional[set] = None
                    if email:
                        up = await r.hgetall(f"user:prefs:{email}")
                        try:
                            if up.get("alert_usd_min"):
                                min_usd = float(up.get("alert_usd_min"))
                        except Exception:
                            pass
                        if up.get("networks"):
                            allowed_networks = set([_norm_network(x) for x in up.get("networks", "").split(",") if x])
                        if up.get("event_types"):
                            allowed_types = set([x.strip().lower() for x in up.get("event_types", "").split(",") if x])
                    # cooldown per device
                    cd_key = f"push:cooldown:{tkn}"
                    if await r.exists(cd_key):
                        continue
                    # Choose the first applicable trigger per tick
                    trig = None
                    for tr in triggers:
                        k = tr["kind"]
                        # Device-level kind preference
                        if not ((k in prefs) or (k == "surge" and ("surge" in prefs or not prefs))):
                            continue
                        # User-level type/network/threshold preference
                        if k in ("zk", "solana_amm"):
                            if allowed_types and k not in allowed_types:
                                continue
                            # network filter
                            net = _norm_network(tr["sig"].get("network"))
                            if allowed_networks and net and net not in allowed_networks:
                                continue
                            if not await _should_send(k, tr["sig"], min_usd):
                                continue
                        trig = tr
                        break
                    if not trig:
                        continue
                    # Build payload
                    if trig["kind"] == "surge":
                        title = "ZK Alpha Flow Surge"
                        body = "Cross-chain flow spike detected"
                        link = "zkalphaflow://surge"
                    elif trig["kind"] == "zk":
                        v = float(trig["sig"].get("usd_value") or 0.0)
                        title = "Large ZK Event"
                        body = f"~${v/1e6:.1f}m inferred"
                        link = "zkalphaflow://event/zk"
                    else:
                        v = float(trig["sig"].get("usd_value") or 0.0)
                        title = "Solana HumidiFi Flow"
                        body = f"~${v/1e6:.1f}m swap"
                        link = "zkalphaflow://event/sol"
                    await _send_stub(tkn, plat, title, body, link)
                    await r.set(cd_key, "1", ex=cooldown_s)
        except Exception:
            pass
        await asyncio.sleep(5)
