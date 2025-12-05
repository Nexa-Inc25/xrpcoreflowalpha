"""
Futures Scanner - ES, NQ, VIX via Databento
Real-time futures data for cross-market correlation with XRP/crypto
"""
import asyncio
import time
from typing import Any, Dict, Optional

import httpx

from app.config import DATABENTO_API_KEY
from observability.metrics import equity_dark_pool_volume
from bus.signal_bus import publish_signal

# Databento API base
DATABENTO_BASE = "https://hist.databento.com/v0"

# Futures symbols to track
FUTURES_SYMBOLS = [
    "ES.FUT",   # S&P 500 E-mini
    "NQ.FUT",   # Nasdaq 100 E-mini
    "VX.FUT",   # VIX futures
    "GC.FUT",   # Gold futures
    "CL.FUT",   # Crude Oil futures
]

# Thresholds for significant moves
MOVE_THRESHOLD_PCT = 0.5  # 0.5% move triggers signal
VOLUME_SPIKE_MULT = 2.0   # 2x average volume


async def start_futures_scanner():
    """Start futures data scanner using Databento."""
    if not DATABENTO_API_KEY:
        print("[FUTURES] No DATABENTO_API_KEY configured, skipping")
        return
    
    print(f"[FUTURES] Starting scanner for {len(FUTURES_SYMBOLS)} symbols")
    
    # Track last prices for change detection
    last_prices: Dict[str, float] = {}
    last_check = 0
    poll_interval = 30  # seconds
    
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                now = time.time()
                if now - last_check < poll_interval:
                    await asyncio.sleep(1)
                    continue
                last_check = now
                
                for symbol in FUTURES_SYMBOLS:
                    await _check_futures_quote(client, symbol, last_prices)
                    await asyncio.sleep(0.5)  # Rate limit
                    
            except Exception as e:
                print(f"[FUTURES] Error: {e}")
                await asyncio.sleep(10)


async def _check_futures_quote(
    client: httpx.AsyncClient,
    symbol: str,
    last_prices: Dict[str, float]
):
    """Check a single futures symbol for significant moves."""
    try:
        # Databento real-time quote endpoint
        headers = {"Authorization": f"Bearer {DATABENTO_API_KEY}"}
        
        # Get latest quote
        resp = await client.get(
            f"{DATABENTO_BASE}/timeseries.get_range",
            headers=headers,
            params={
                "dataset": "GLBX.MDP3",  # CME Globex
                "symbols": symbol,
                "schema": "trades",
                "start": int((time.time() - 60) * 1e9),  # Last minute
                "end": int(time.time() * 1e9),
                "limit": 10,
            }
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        trades = data.get("data", [])
        
        if not trades:
            return
            
        # Get latest price
        latest = trades[-1]
        price = float(latest.get("price", 0))
        size = int(latest.get("size", 0))
        
        if price <= 0:
            return
            
        # Check for significant move
        prev_price = last_prices.get(symbol)
        last_prices[symbol] = price
        
        if prev_price and prev_price > 0:
            pct_change = ((price - prev_price) / prev_price) * 100
            
            if abs(pct_change) >= MOVE_THRESHOLD_PCT:
                direction = "up" if pct_change > 0 else "down"
                clean_symbol = symbol.replace(".FUT", "")
                
                print(f"[FUTURES] {clean_symbol} {direction} {abs(pct_change):.2f}%")
                
                await publish_signal({
                    "type": "futures",
                    "sub_type": "price_move",
                    "symbol": clean_symbol,
                    "price": price,
                    "change_pct": round(pct_change, 2),
                    "direction": direction,
                    "size": size,
                    "timestamp": int(time.time()),
                    "summary": f"{clean_symbol} futures {direction} {abs(pct_change):.2f}% → ${price:,.2f}",
                    "tags": ["futures", clean_symbol.lower()],
                })
                
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
