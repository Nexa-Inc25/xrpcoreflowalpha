import asyncio
import json
from typing import Any, Dict, List

import httpx
import websockets

from app.config import FINNHUB_API_KEY, POLYGON_API_KEY, EQUITY_TICKERS, DISABLE_EQUITY_FALLBACK, EQUITY_BLOCK_MIN_SHARES
from alerts.slack import send_slack_alert, build_rich_slack_payload
from observability.metrics import equity_dark_pool_volume
from bus.signal_bus import publish_signal


async def start_equities_scanner():
    if not FINNHUB_API_KEY:
        return
    url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
        for t in EQUITY_TICKERS:
            await ws.send(json.dumps({"type": "subscribe", "symbol": t}))
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("type") != "trade":
                continue
            trades: List[Dict[str, Any]] = data.get("data", [])
            for trade in trades:
                if await is_dark_pool_print(trade):
                    symbol = trade.get("s", "")
                    shares = int(trade.get("v", 0))
                    price = float(trade.get("p", 0.0))
                    if shares < EQUITY_BLOCK_MIN_SHARES:
                        continue
                    venue = trade.get("venue", "DARK")
                    equity_dark_pool_volume.labels(symbol=symbol, venue=venue).inc(shares)
                    await send_slack_alert(build_rich_slack_payload({"type": "equity", "trade": trade}))
                    usd_value = round(shares * price, 2)
                    summary = f"{symbol} dark {shares:,} @ {price:.2f} ({venue})"
                    await publish_signal({
                        "type": "equity",
                        "sub_type": "dark_pool",
                        "symbol": symbol,
                        "shares": shares,
                        "price": price,
                        "usd_value": usd_value,
                        "venue": venue,
                        "timestamp": int(trade.get("t", 0) // 1000) if trade.get("t") else None,
                        "summary": summary,
                    })


async def is_dark_pool_print(trade: Dict[str, Any]) -> bool:
    # Finnhub WS trade payload does not include venue; enrich with Polygon if available
    vol = int(trade.get("v", 0))
    if POLYGON_API_KEY:
        try:
            symbol = trade.get("s")
            ts = int(trade.get("t", 0))
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(
                    f"https://api.polygon.io/v3/trades/{symbol}",
                    params={
                        "limit": 1,
                        "order": "desc",
                        "timestamp_lt": ts + 1,
                        "apiKey": POLYGON_API_KEY,
                    },
                )
                if resp.status_code == 200:
                    r = resp.json()
                    results = r.get("results") or []
                    if results:
                        res = results[0]
                        conds = res.get("conditions") or []
                        # Heuristic: TRF/off-exchange conditions often include 12, 37, 38, 62, 63, 64
                        if any(c in conds for c in [12, 37, 38, 62, 63, 64]) and vol >= 100_000:
                            trade["venue"] = "TRF/DARK"
                            return True
        except Exception:
            pass
    # Fallback strictly volume-based if allowed
    if not DISABLE_EQUITY_FALLBACK and vol >= 100_000:
        trade["venue"] = "UNKNOWN"
        return True
    return False
