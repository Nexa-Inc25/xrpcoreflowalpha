import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse

from bus.signal_bus import fetch_recent_signals, fetch_recent_cross_signals
from app.config import (
    SURGE_WINDOW_SECONDS,
    SURGE_BURST_COUNT,
    SURGE_CONFIDENCE_THRESHOLD,
    DARKSCORE_TOP8_SELECTORS,
)
from observability.impact import get_cached_depth, calculate_impact, DEPTH_CACHE_TTL

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(ts: Any) -> str:
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()
        if isinstance(ts, str) and ts.isdigit():
            return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()
    except Exception:
        pass
    return _now_iso()


def _validate_tx_hash(tx_hash: str, network: str = "eth") -> bool:
    """Validate transaction hash format and ensure it's not fake/test data."""
    if not tx_hash or not isinstance(tx_hash, str):
        return False

    # Remove any fake/test prefixes
    if tx_hash.upper().startswith('0XTEST') or 'TEST' in tx_hash.upper():
        return False

    # Validate format based on network
    if network.lower() in ['eth', 'ethereum', 'zk']:
        # Ethereum: must start with 0x and be 66 characters (32 bytes + 0x)
        return tx_hash.startswith('0x') and len(tx_hash) == 66 and tx_hash[2:].replace('0', '').isalnum()
    elif network.lower() == 'xrpl':
        # XRPL: 64-character hex string
        return len(tx_hash) == 64 and tx_hash.replace('0', '').isalnum()

    # Unknown network - basic validation
    return len(tx_hash) >= 10 and tx_hash.replace('0', '').replace('x', '').isalnum()


def _confidence_bucket(v: Optional[int]) -> str:
    try:
        i = int(v or 0)
    except Exception:
        i = 0
    if i >= 90:
        return "high"
    if i >= 60:
        return "medium"
    return "low"


def _format_event(sig: Dict[str, Any]) -> Dict[str, Any]:
    stype = str(sig.get("type") or "event").lower()
    msg: str
    features: Dict[str, Any] = {}
    if stype == "cross":
        s1 = (sig.get("signals") or [{}])[0]
        s2 = (sig.get("signals") or [{}])[1] if len(sig.get("signals") or []) > 1 else {}
        conf = sig.get("confidence")
        imp = sig.get("predicted_impact_pct")
        msg = f"CROSS: {s1.get('summary','S1')} → {s2.get('summary','S2')} | conf {int(conf or 0)}% | impact {float(imp or 0):+.2f}%"
    elif stype == "trustline":
        val = sig.get("limit_value") or 0
        cur = sig.get("currency") or "IOU"
        issuer = sig.get("issuer") or ""
        account = sig.get("account") or ""
        raw_tx_hash = sig.get("tx_hash") or ""
        validated_tx_hash = raw_tx_hash if _validate_tx_hash(raw_tx_hash, "xrpl") else ""
        features = {
            "limit_value": float(val) if val else 0,
            "currency": cur,
            "issuer": issuer,
            "account": account,
            "tx_hash": validated_tx_hash,
        }
        # Format value for display
        fval = float(val) if val else 0
        if fval >= 1_000_000_000:
            val_str = f"{fval/1_000_000_000:.1f}B"
        elif fval >= 1_000_000:
            val_str = f"{fval/1_000_000:.1f}M"
        else:
            val_str = f"{fval:,.0f}"
        msg = f"TrustLine {val_str} {cur[:8]} → {account[:8]}..."
    elif stype == "rwa_amm":
        chg = (sig.get("amm_liquidity_change") or {}).get("lp_change_pct")
        msg = f"RWA AMM ΔLP {round(float(chg or 0)*100,2)}%"
    elif stype == "orderbook":
        pair = sig.get("pair") or "Pair"
        bid = sig.get("bid_depth_usd")
        ask = sig.get("ask_depth_usd")
        sp = sig.get("spread_bps")
        msg = f"OB {pair}: bid ${float(bid or 0):,.0f} | ask ${float(ask or 0):,.0f} | spread {sp if sp is not None else 'n/a'} bps"
    elif stype == "xrp":
        try:
            raw_tx_hash = sig.get("tx_hash") or ""
            validated_tx_hash = raw_tx_hash if _validate_tx_hash(raw_tx_hash, "xrpl") else ""
            features = {
                "amount_xrp": float(sig.get("amount_xrp") or 0.0),
                "usd_value": float(sig.get("usd_value") or 0.0),
                "tx_hash": validated_tx_hash,
                "source": sig.get("source") or "",
                "destination": sig.get("destination") or "",
                "destination_tag": sig.get("destination_tag"),
            }
        except Exception:
            features = {}
        base_msg = sig.get("summary") or "XRP flow"
        msg = base_msg
    elif stype == "zk":
        try:
            features = {
                "gas_used": int(sig.get("gas_used") or 0),
                "input_len": int(sig.get("input_len") or 0),
                "calldata_entropy": float(sig.get("calldata_entropy") or 0.0),
                "selector": sig.get("selector") or "0x00000000",
                "gas_price_wei": int(sig.get("gas_price_wei") or 0),
                "value_wei": int(sig.get("value_wei") or 0),
                "usd_value": float(sig.get("usd_value") or 0.0),
                "zero_value": bool(sig.get("zero_value") or False),
                "partner_from": bool(sig.get("partner_from") or False),
                "partner_to": bool(sig.get("partner_to") or False),
                "from": (sig.get("from") or ""),
                "to": (sig.get("to") or ""),
                "tx_hash": (sig.get("tx_hash") or "") if _validate_tx_hash(sig.get("tx_hash") or "", sig.get("network") or "eth") else "",
                "network": (sig.get("network") or ""),
            }
        except Exception:
            features = {}
        msg = sig.get("summary") or f"{stype.upper()} event"
        # Lightweight rule-based score (0-100) for hybrid client ensemble
        try:
            gas_norm = min(max(float(features.get("gas_used", 0)) / 1_200_000.0, 0.0), 1.0)
            ilen_norm = min(max(float(features.get("input_len", 0)) / 576.0, 0.0), 1.0)
            ent_norm = min(max(float(features.get("calldata_entropy", 0.0)) / 8.0, 0.0), 1.0)
            sel = str(features.get("selector") or "").lower()
            selector_hit = 1.0 if sel in set(DARKSCORE_TOP8_SELECTORS) else 0.0
            partner = 1.0 if (features.get("partner_from") or features.get("partner_to")) else 0.0
            zero_val = 1.0 if features.get("zero_value") else 0.0
            score = (
                0.25 * gas_norm +
                0.25 * ilen_norm +
                0.15 * ent_norm +
                0.20 * selector_hit +
                0.10 * partner +
                0.05 * zero_val
            ) * 100.0
            rule_score = float(max(0.0, min(score, 100.0)))
        except Exception:
            rule_score = 0.0
    elif stype == "solana_amm":
        try:
            features = {
                "program_id": (sig.get("program_id") or ""),
                "tx_sig": (sig.get("tx_sig") or ""),
                "slot": sig.get("slot"),
                "usd_value": float(sig.get("usd_value") or 0.0),
            }
        except Exception:
            features = {}
        msg = sig.get("summary") or f"SOLANA AMM activity tx {(sig.get('tx_sig') or '')[:8]}..."
    else:
        msg = sig.get("summary") or f"{stype.upper()} event"
    # Attach ISO / XRPL predictor fields when present
    try:
        iso_conf = sig.get("iso_confidence")
        if iso_conf is not None:
            features["iso_confidence"] = int(iso_conf)
        for k in ("iso_direction", "iso_timeframe", "iso_expected_move_pct", "iso_state", "iso_amount_usd"):
            v = sig.get(k)
            if v is not None:
                features[k] = v
    except Exception:
        pass
    out = {
        "timestamp": _iso(sig.get("timestamp")),
        "message": msg,
        "type": stype,
        "confidence": _confidence_bucket(sig.get("confidence")),
        "id": sig.get("id") or f"{stype}:{sig.get('timestamp','')}",
        **({"network": sig.get("network")} if sig.get("network") else {}),
        **({"features": features} if features else {}),
        **({"rule_score": rule_score} if stype == "zk" else {}),
    }
    return out


async def get_dashboard_json() -> Dict[str, Any]:
    # last 5 minutes signals and cross-signal high-confidence detection
    sigs_5m = await fetch_recent_signals(window_seconds=SURGE_WINDOW_SECONDS)
    # cross signals are stored in a separate stream; fetch recent and window-filter
    cross_recent = await fetch_recent_cross_signals(limit=50)
    now_s = int(time.time())
    high_conf_count = 0
    for s in cross_recent:
        try:
            ts = int(s.get("timestamp", 0))
            if now_s - ts <= SURGE_WINDOW_SECONDS and int(s.get("confidence", 0)) >= SURGE_CONFIDENCE_THRESHOLD:
                high_conf_count += 1
        except Exception:
            continue
    # Include Solana AMM dark venue signals in surge accumulation
    try:
        for s in sigs_5m:
            if (s.get("type") or "").lower() == "solana_amm" and "HumidiFi" in (s.get("tags") or []):
                high_conf_count += 1
    except Exception:
        pass
    surge_mode = high_conf_count >= SURGE_BURST_COUNT

    # recent events render (up to last 20 across the last hour), merging cross + other signals
    recent_signals = await fetch_recent_signals(window_seconds=3600)
    # attach a marker so we can identify source uniformly
    merged: List[Dict[str, Any]] = []
    merged.extend(recent_signals)
    merged.extend(cross_recent)
    try:
        merged.sort(key=lambda s: int(s.get("timestamp", 0)))
    except Exception:
        pass
    merged = merged[-20:] if len(merged) > 20 else merged
    events = [_format_event(s) for s in merged]

    children: List[Dict[str, Any]] = [
        {
            "type": "Header",
            "title": "DarkFlow Tracker",
            "subtitle": f"Surge Mode: {'🟥 ACTIVE' if surge_mode else '🟢 Normal'}",
        },
        {
            "type": "LiveCounter",
            "label": f"Events Last {SURGE_WINDOW_SECONDS//60}min",
            "value": len(sigs_5m),
        },
        {
            "type": "EventList",
            "events": events,
        },
        {
            "type": "PredictiveBanner",
            "visible": surge_mode,
            "text": "🔥 High-volume ZK flow detected – preparing market impact forecast",
        },
    ]

    # Attempt to append ImpactForecastCard during surge, using Binance depth cache
    if surge_mode:
        # Choose latest high-score zk event as proxy
        zk_events = [e for e in events if e.get("type") == "zk" and float(e.get("rule_score", 0)) >= 90.0]
        cand = zk_events[-1] if zk_events else None
        if cand and isinstance(cand.get("features"), dict):
            fea = cand["features"]  # type: ignore[index]
            inferred_usd = float(fea.get("inferred_usd") or fea.get("usd_value") or 0.0)
            bids, asks, mid, ts = get_cached_depth("ETHUSDT")
            fresh = (time.time() - ts) <= (DEPTH_CACHE_TTL * 2)
            if inferred_usd >= 10_000_000 and fresh and bids and asks and mid > 0:
                try:
                    buy = calculate_impact(asks, "asks", inferred_usd, mid)
                    sell = calculate_impact(bids, "bids", inferred_usd, mid)
                    depth_1pct_mm = ((float(buy.get("1.0%_usd", 0.0)) + float(sell.get("1.0%_usd", 0.0))) / 2.0) / 1e6
                    children.append({
                        "type": "ImpactForecastCard",
                        "symbol": "ETHUSDT",
                        "inferred_usd_m": round(inferred_usd / 1e6, 1),
                        "buy_impact": round(float(buy.get("impact_pct", 0.0)), 2),
                        "sell_impact": round(float(sell.get("impact_pct", 0.0)), 2),
                        "depth_1pct_mm": round(depth_1pct_mm, 1),
                        "visible": True,
                    })
                except Exception:
                    pass
        # Multi-chain fallback: if aggregated USD across window is large, show card
        try:
            agg_usd = 0.0
            for s in sigs_5m:
                if (s.get("type") or "").lower() in ("zk", "solana_amm"):
                    try:
                        agg_usd += float(s.get("usd_value") or 0.0)
                    except Exception:
                        continue
            if agg_usd >= 100_000_000:  # > $100m cluster
                bids, asks, mid, ts = get_cached_depth("ETHUSDT")
                fresh = (time.time() - ts) <= (DEPTH_CACHE_TTL * 2)
                if fresh and bids and asks and mid > 0 and not any(isinstance(c, dict) and c.get("type") == "ImpactForecastCard" for c in children):
                    try:
                        buy = calculate_impact(asks, "asks", agg_usd, mid)
                        sell = calculate_impact(bids, "bids", agg_usd, mid)
                        depth_1pct_mm = ((float(buy.get("1.0%_usd", 0.0)) + float(sell.get("1.0%_usd", 0.0))) / 2.0) / 1e6
                        children.append({
                            "type": "ImpactForecastCard",
                            "symbol": "ETHUSDT",
                            "inferred_usd_m": round(agg_usd / 1e6, 1),
                            "buy_impact": round(float(buy.get("impact_pct", 0.0)), 2),
                            "sell_impact": round(float(sell.get("impact_pct", 0.0)), 2),
                            "depth_1pct_mm": round(depth_1pct_mm, 1),
                            "visible": True,
                        })
                    except Exception:
                        pass
        except Exception:
            pass

    children.append({
        "type": "Footer",
        "text": f"Real-time • Public data only • {datetime.now(timezone.utc).strftime('%b %d %Y')}",
    })

    return {
        "type": "VStack",
        "spacing": 20,
        "children": children,
    }


@router.get("/ui")
async def ui_payload(request: Request):
    try:
        data = await get_dashboard_json()
    except Exception:
        # fail-safe minimal payload
        data = {
            "type": "VStack",
            "spacing": 20,
            "children": [
                {"type": "Header", "title": "DarkFlow Tracker", "subtitle": "Surge Mode: 🟢 Normal"},
                {"type": "LiveCounter", "label": "Events Last 5min", "value": 0},
                {"type": "EventList", "events": []},
                {"type": "Footer", "text": f"Real-time • Public data only • {_now_iso()[:10]}"},
            ],
        }
    # Server-side gating by tier resolved from middleware, fallback to plan header (defense in depth)
    plan = (getattr(request.state, "user_tier", None) or request.headers.get("X-Plan") or "").lower()
    if plan == "free":
        try:
            for child in data.get("children", []):
                if isinstance(child, dict) and child.get("type") == "ImpactForecastCard":
                    child["visible"] = False
                    child["blur"] = True
                    child["cta"] = "Upgrade to Pro →"
            data.get("children", []).append({
                "type": "UpgradeBanner",
                "text": "Unlock real-time Impact Forecasts • $49/mo",
                "action": "open_stripe",
            })
            data.get("children", []).append({
                "type": "SubscriptionCard",
                "title": "Unlock Real-Time Dark Flow Intelligence",
                "options": [
                    {"tier": "pro", "price": "$49/mo or 0.5 SOL", "action": "stripe_pro_monthly"},
                    {"tier": "pro", "price": "$490/yr or 5.4 SOL", "action": "stripe_pro_annual"},
                    {"tier": "institutional", "price": "$499/mo", "action": "contact_sales"}
                ],
                "crypto_qr": True,
            })
            data.get("children", []).append({
                "type": "ReplayButton",
                "text": "Replay Last 7 Days",
                "endpoint": "/history/replay?days=7",
            })
        except Exception:
            pass
    return JSONResponse(data)


@router.get("/events/sse")
async def event_stream(request: Request):
    last_id: Optional[str] = None

    async def generator():
        nonlocal last_id
        while True:
            if await request.is_disconnected():
                break
            try:
                recent_a = await fetch_recent_signals(window_seconds=SURGE_WINDOW_SECONDS)
            except Exception:
                recent_a = []
            try:
                recent_b = await fetch_recent_cross_signals(limit=50)
            except Exception:
                recent_b = []
            combined = (recent_a or []) + (recent_b or [])
            try:
                combined.sort(key=lambda s: int(s.get("timestamp", 0)))
            except Exception:
                pass
            item = combined[-1] if combined else None
            if item:
                cur_id = item.get("id") or f"{item.get('type','evt')}:{item.get('timestamp','')}"
                if cur_id != last_id:
                    last_id = cur_id
                    payload = _format_event(item)
                    yield f"data: {json.dumps(payload, separators=(',',':'))}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(generator(), media_type="text/event-stream")


@router.websocket("/events")
async def events_websocket(ws: WebSocket):
    await ws.accept()
    last_id: Optional[str] = None
    try:
        while True:
            try:
                recent_a = await fetch_recent_signals(window_seconds=SURGE_WINDOW_SECONDS)
            except Exception:
                recent_a = []
            try:
                recent_b = await fetch_recent_cross_signals(limit=50)
            except Exception:
                recent_b = []
            combined = (recent_a or []) + (recent_b or [])
            try:
                combined.sort(key=lambda s: int(s.get("timestamp", 0)))
            except Exception:
                pass
            item = combined[-1] if combined else None
            if item:
                cur_id = item.get("id") or f"{item.get('type','evt')}:{item.get('timestamp','')}"
                if cur_id != last_id:
                    last_id = cur_id
                    payload = _format_event(item)
                    await ws.send_text(json.dumps(payload, separators=(",", ":")))
            try:
                _ = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                pass
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
