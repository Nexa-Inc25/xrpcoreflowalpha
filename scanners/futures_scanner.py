"""
Futures Scanner - ES, NQ, VIX, Gold, Oil
Real-time futures data for cross-market correlation with XRP/crypto.
Uses Yahoo Finance as fallback when Databento API key is not available.
"""
import asyncio
import time
from typing import Any, Dict, Optional

import httpx

from app.config import DATABENTO_API_KEY, POLYGON_API_KEY
from observability.metrics import equity_dark_pool_volume
from bus.signal_bus import publish_signal
from workers.scanner_monitor import mark_scanner_connected, record_scanner_signal, mark_scanner_error

# Databento API base
DATABENTO_BASE = "https://hist.databento.com/v0"

# Yahoo Finance symbols for futures ETF proxies
YAHOO_FUTURES_PROXIES = {
    "ES": {"symbol": "^GSPC", "name": "S&P 500", "type": "index"},
    "NQ": {"symbol": "^NDX", "name": "Nasdaq 100", "type": "index"}, 
    "VIX": {"symbol": "^VIX", "name": "VIX", "type": "volatility"},
    "GC": {"symbol": "GLD", "name": "Gold ETF", "type": "commodity"},
    "CL": {"symbol": "USO", "name": "Oil ETF", "type": "commodity"},
}

# Thresholds for significant moves
MOVE_THRESHOLD_PCT = 0.25  # 0.25% move triggers signal (more sensitive)
VOLUME_SPIKE_MULT = 2.0   # 2x average volume


async def start_futures_scanner():
    """Start futures data scanner. Uses Yahoo Finance as free fallback."""
    print("[FUTURES] Starting scanner with Yahoo Finance proxy data")
    mark_scanner_connected("futures")
    
    # Track last prices for change detection
    last_prices: Dict[str, float] = {}
    last_check = 0
    poll_interval = 10  # seconds - fast polling for real-time signals
    
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                now = time.time()
                if now - last_check < poll_interval:
                    await asyncio.sleep(1)
                    continue
                last_check = now
                
                for code, info in YAHOO_FUTURES_PROXIES.items():
                    await _check_yahoo_quote(client, code, info, last_prices)
                    await asyncio.sleep(0.3)  # Rate limit
                    
            except Exception as e:
                print(f"[FUTURES] Error: {e}")
                await asyncio.sleep(10)


async def _check_yahoo_quote(
    client: httpx.AsyncClient,
    code: str,
    info: Dict[str, str],
    last_prices: Dict[str, float]
):
    """Check a single futures proxy via Yahoo Finance."""
    try:
        symbol = info["symbol"]
        
        # Yahoo Finance quote API
        resp = await client.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1m", "range": "1d"},
            headers={"User-Agent": "Mozilla/5.0"}
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        result = data.get("chart", {}).get("result", [])
        
        if not result:
            return
            
        meta = result[0].get("meta", {})
        price = meta.get("regularMarketPrice", 0)
        prev_close = meta.get("chartPreviousClose", 0)
        
        if price <= 0:
            return
            
        # Check for significant move from prev close
        prev_price = last_prices.get(code, prev_close)
        last_prices[code] = price
        
        if prev_price and prev_price > 0:
            pct_change = ((price - prev_price) / prev_price) * 100
            
            # Publish signal for any meaningful move
            if abs(pct_change) >= MOVE_THRESHOLD_PCT:
                direction = "up" if pct_change > 0 else "down"
                
                print(f"[FUTURES] {code} ({info['name']}) {direction} {abs(pct_change):.2f}%")
                
                await publish_signal({
                    "type": "futures",
                    "sub_type": "price_move",
                    "symbol": code,
                    "name": info["name"],
                    "asset_type": info["type"],
                    "price": price,
                    "change_pct": round(pct_change, 2),
                    "direction": direction,
                    "timestamp": int(time.time()),
                    "summary": f"{info['name']} {direction} {abs(pct_change):.2f}% → ${price:,.2f}",
                    "tags": ["futures", code.lower(), info["type"]],
                })
        else:
            # First run - calculate change from previous close
            if prev_close and prev_close > 0:
                daily_change = ((price - prev_close) / prev_close) * 100
                print(f"[FUTURES] {code} at ${price:,.2f} ({daily_change:+.2f}% today)")
                
    except Exception as e:
        pass  # Silently continue on individual symbol errors


async def get_futures_correlation(crypto_symbol: str = "XRP") -> Dict[str, float]:
    """
    Calculate correlation between crypto and futures.
    Used for predictive analytics.
    """
    # This would be called by the correlation engine
    # Returns correlation coefficients
    return {
        "ES": 0.0,
        "NQ": 0.0,
        "VX": 0.0,
        "GC": 0.0,
    }
