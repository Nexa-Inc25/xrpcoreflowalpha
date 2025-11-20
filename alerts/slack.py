import time
import json
import hashlib
import httpx
from typing import Any, Dict

import redis.asyncio as redis
from utils.retry import async_retry

from app.config import (
    ALERTS_SLACK_WEBHOOK,
    REDIS_URL,
    ALERTS_DEDUP_TTL_SECONDS,
    ALERTS_RATE_WINDOW_SECONDS,
    ALERTS_RATE_MAX_PER_WINDOW,
    ALERTS_RATE_LIMIT_PER_CATEGORY,
)
from app.config import EXECUTION_ENABLED

_redis: redis.Redis | None = None


def _fingerprint(payload: Dict[str, Any]) -> str:
    try:
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception:
        s = str(payload)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def _get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        _redis = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis


async def _allow_send(fp: str, category: str | None) -> bool:
    r = await _get_redis()
    try:
        dedup_key = f"alerts:dedup:{fp}"
        added = await r.set(dedup_key, "1", ex=ALERTS_DEDUP_TTL_SECONDS, nx=True)
        if not added:
            return False
        now = int(time.time())
        window = now // ALERTS_RATE_WINDOW_SECONDS
        suffix = f":{category}" if (ALERTS_RATE_LIMIT_PER_CATEGORY and category) else ""
        rate_key = f"alerts:rate{suffix}:{window}"
        count = await r.incr(rate_key)
        if count == 1:
            await r.expire(rate_key, ALERTS_RATE_WINDOW_SECONDS + 5)
        if count > ALERTS_RATE_MAX_PER_WINDOW:
            return False
        return True
    except Exception:
        return True


@async_retry(max_attempts=5, delay=1, backoff=2)
async def send_slack_alert(payload: Dict[str, Any]) -> None:
    if not ALERTS_SLACK_WEBHOOK:
        return
    fp = _fingerprint(payload)
    category = None
    try:
        category = (payload.get("type") or payload.get("signal", {}).get("type")).lower()
    except Exception:
        category = None
    if not await _allow_send(fp, category):
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(ALERTS_SLACK_WEBHOOK, json=payload)
    except Exception:
        pass

def build_rich_slack_payload(flow: Dict[str, Any]) -> Dict[str, Any]:
    ftype = flow.get("type")
    header_text = (
        "CROSS-MARKET SIGNAL" if ftype == "cross" else
        "TRUSTLINE ALERT" if ftype == "trustline" else
        "RWA AMM LIQUIDITY" if ftype == "rwa_amm" else
        "ORDERBOOK ALERT" if ftype == "orderbook" else
        "GODARK PREP" if ftype == "godark_prep" else
        "FLOW ALERT"
    )
    # unify source object
    payload_obj = flow.get("flow") or flow.get("signal") or flow
    detail_lines = []
    if ftype == "equity" and "trade" in flow:
        t = flow["trade"]
        detail_lines.append(f"Equity: {t.get('s')} {t.get('v')} @ {t.get('p')}")
    if ftype == "xrp" and "flow" in flow:
        xf = flow["flow"]
        detail_lines.append(f"XRPL: {getattr(xf,'amount_xrp',0):,.0f} XRP")
    if ftype == "zk" and "flow" in flow:
        zf = flow["flow"]
        detail_lines.append(f"ZK Proof: {getattr(zf,'tx_hash','')}")
    if ftype == "trustline":
        val = payload_obj.get("limit_value")
        cur = payload_obj.get("currency")
        issuer = (payload_obj.get("issuer") or "")
        tags = ", ".join(payload_obj.get("tags") or [])
        detail_lines.append(f"TrustSet {val:,.0f} {cur} issuer {issuer[:8]}...\nTags: {tags}")
    if ftype == "godark_prep":
        asset = payload_obj.get("asset")
        usd = payload_obj.get("usd_value")
        to = (payload_obj.get("to") or "")
        detail_lines.append(f"GoDark Prep: ${usd:,.1f} {asset} → {to[:10]}...")
    if ftype == "rwa_amm":
        tags = ", ".join(payload_obj.get("tags") or [])
        chg = payload_obj.get("amm_liquidity_change", {}).get("lp_change_pct")
        detail_lines.append(f"RWA AMM: Δ LP {round(chg*100,2) if chg is not None else 'n/a'}%\nTags: {tags}")
    if ftype == "orderbook":
        pair = payload_obj.get("pair")
        bid = payload_obj.get("bid_depth_usd")
        ask = payload_obj.get("ask_depth_usd")
        sp = payload_obj.get("spread_bps")
        tags = ", ".join(payload_obj.get("tags") or [])
        detail_lines.append(f"{pair}: bid ${bid:,.0f} | ask ${ask:,.0f} | spread {sp if sp is not None else 'n/a'} bps\nTags: {tags}")
    text_block = "\n".join(detail_lines) if detail_lines else ""
    payload = {
        "type": ftype,
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": header_text}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text_block}},
        ]
    }
    # Set color for non-cross types
    if ftype != "cross":
        color = None
        tsrc = []
        try:
            if isinstance(payload_obj, dict):
                tsrc = payload_obj.get("tags") or []
            else:
                # payload_obj may be a dataclass (e.g., XRPFlow). Fallback to top-level tags if present.
                tsrc = flow.get("tags") or []
        except Exception:
            tsrc = []
        tags = [str(t) for t in tsrc]
        if ftype == "rwa_amm":
            if any("GoDark" in t for t in tags):
                color = "#8b5cf6"
            elif any("Withdrawal" in t for t in tags):
                color = "#ff0000"
            elif any("Deposit" in t for t in tags):
                color = "#10b981"
        elif ftype == "orderbook":
            if any("GoDark" in t for t in tags):
                color = "#8b5cf6"
            elif any("Imbalance" in t for t in tags) or any("Whale" in t for t in tags):
                color = "#ff0000"
            elif any("Depth Surge" in t for t in tags):
                color = "#10b981"
        if color:
            payload["attachments"] = [{"color": color}]
    return payload


def build_cross_slack_payload(cross: Dict[str, Any]) -> Dict[str, Any]:
    confidence = int(cross.get("confidence", 0))
    impact = float(cross.get("predicted_impact_pct", 0.0))
    delta = int(cross.get("time_delta", 0))
    godark = bool(cross.get("godark"))
    urgency = "CRITICAL" if godark else ("HIGH" if impact >= 1.5 else "MEDIUM")
    color = "#8b5cf6" if godark else ("#ff0000" if urgency == "HIGH" else "#ffa500")

    s1 = cross.get("signals", [{}])[0]
    s2 = cross.get("signals", [{}])[1] if len(cross.get("signals", [])) > 1 else {}

    def _fmt(sig: Dict[str, Any]) -> str:
        t = sig.get("type", "?").upper()
        summ = sig.get("summary", "")
        val = sig.get("usd_value")
        val_str = f" | ${val:,.0f}" if isinstance(val, (int, float)) and val else ""
        return f"{t}: {summ}{val_str}"

    payload = {
        "type": "cross",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": f"CROSS-MARKET SIGNAL: {urgency}"}},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Signal 1*: {_fmt(s1)}\n*Signal 2*: {_fmt(s2)}\n*Time Delta*: {delta//60}m {delta%60}s",
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Confidence*: {confidence}%"},
                    {"type": "mrkdwn", "text": f"*Predicted XRP Move*: {impact:+.2f}% in 15m"},
                ],
            },
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Correlation ID: {cross.get('id','')}"}]},
        ],
        "attachments": [{"color": color}],
    }
    if godark:
        payload["blocks"].insert(1, {"type": "context", "elements": [{"type": "mrkdwn", "text": "*GoDark*"}]})
    # Execution action (disabled by default)
    if godark and confidence >= 95:
        if EXECUTION_ENABLED:
            payload["blocks"].append({
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "Execution: ENABLED (trigger gated by backend)"}],
            })
        else:
            payload["blocks"].append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Execute Counter-Trade"},
                        "style": "primary",
                        "disabled": True,
                    }
                ],
            })
    return payload
