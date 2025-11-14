import time
import json
import hashlib
import httpx
from typing import Any, Dict

import redis.asyncio as redis

from app.config import (
    ALERTS_SLACK_WEBHOOK,
    REDIS_URL,
    ALERTS_DEDUP_TTL_SECONDS,
    ALERTS_RATE_WINDOW_SECONDS,
    ALERTS_RATE_MAX_PER_WINDOW,
    ALERTS_RATE_LIMIT_PER_CATEGORY,
)

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
    # Dedup: skip if we've sent identical payload within TTL
    dedup_key = f"alerts:dedup:{fp}"
    added = await r.set(dedup_key, "1", ex=ALERTS_DEDUP_TTL_SECONDS, nx=True)
    if not added:
        return False
    # Rate limit: sliding window via fixed window counter
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
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(ALERTS_SLACK_WEBHOOK, json=payload)

def build_rich_slack_payload(flow: Dict[str, Any]) -> Dict[str, Any]:
    header_text = "CROSS-MARKET SIGNAL" if flow.get("type") == "cross" else "FLOW ALERT"
    detail_lines = []
    if flow.get("type") == "equity" and "trade" in flow:
        t = flow["trade"]
        detail_lines.append(f"Equity: {t.get('s')} {t.get('v')} @ {t.get('p')}")
    if flow.get("type") == "xrp" and "flow" in flow:
        xf = flow["flow"]
        detail_lines.append(f"XRPL: {getattr(xf,'amount_xrp',0):,.0f} XRP")
    if flow.get("type") == "zk" and "flow" in flow:
        zf = flow["flow"]
        detail_lines.append(f"ZK Proof: {getattr(zf,'tx_hash','')}")
    text_block = "\n".join(detail_lines) if detail_lines else ""
    return {
        "type": flow.get("type"),
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": header_text}},
            {"type": "section", "text": {"type": "mrkdwn", "text": text_block}},
        ]
    }


def build_cross_slack_payload(cross: Dict[str, Any]) -> Dict[str, Any]:
    confidence = int(cross.get("confidence", 0))
    impact = float(cross.get("predicted_impact_pct", 0.0))
    delta = int(cross.get("time_delta", 0))
    urgency = "HIGH" if impact >= 1.5 else "MEDIUM"
    color = "#ff0000" if urgency == "HIGH" else "#ffa500"

    s1 = cross.get("signals", [{}])[0]
    s2 = cross.get("signals", [{}])[1] if len(cross.get("signals", [])) > 1 else {}

    def _fmt(sig: Dict[str, Any]) -> str:
        t = sig.get("type", "?").upper()
        summ = sig.get("summary", "")
        val = sig.get("usd_value")
        val_str = f" | ${val:,.0f}" if isinstance(val, (int, float)) and val else ""
        return f"{t}: {summ}{val_str}"

    return {
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
