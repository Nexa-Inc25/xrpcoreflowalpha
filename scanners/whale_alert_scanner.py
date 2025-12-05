"""
Whale Alert Scanner - Real-time large transaction tracking across chains.

Uses Whale Alert API to detect large transfers and feed them into:
1. Live signal feed for the dashboard
2. Wallet tracking page data
3. Prediction model confidence scoring
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import WHALE_ALERT_API_KEY
from bus.signal_bus import publish_signal


# Whale Alert API base URL
WHALE_ALERT_API_BASE = "https://api.whale-alert.io/v1"

# Minimum transaction value to track (in USD)
MIN_VALUE_USD = 1_000_000  # $1M+

# Blockchains we care about
TRACKED_CHAINS = ["ethereum", "ripple", "bitcoin", "solana", "tron"]

# Known exchange/institution labels for confidence scoring
KNOWN_EXCHANGES = {
    "binance", "coinbase", "kraken", "bitfinex", "okex", "huobi", 
    "ftx", "kucoin", "gemini", "bitstamp", "bybit", "gate.io"
}

KNOWN_INSTITUTIONS = {
    "grayscale", "microstrategy", "tesla", "blockfi", "celsius",
    "genesis", "galaxy digital", "jump trading", "alameda"
}


async def fetch_recent_transactions(min_value: int = MIN_VALUE_USD, limit: int = 100) -> List[Dict[str, Any]]:
    """Fetch recent large transactions from Whale Alert API."""
    if not WHALE_ALERT_API_KEY:
        return []
    
    # Get transactions from last 10 minutes
    start_time = int(time.time()) - 600
    
    params = {
        "api_key": WHALE_ALERT_API_KEY,
        "min_value": min_value,
        "start": start_time,
        "limit": limit,
    }
    
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{WHALE_ALERT_API_BASE}/transactions", params=params)
            if resp.status_code != 200:
                print(f"[WhaleAlert] API error: {resp.status_code}")
                return []
            
            data = resp.json()
            if data.get("result") != "success":
                print(f"[WhaleAlert] API failed: {data.get('message', 'unknown')}")
                return []
            
            return data.get("transactions", [])
    except Exception as e:
        print(f"[WhaleAlert] Error fetching transactions: {e}")
        return []


def score_transaction_confidence(tx: Dict[str, Any]) -> int:
    """
    Score transaction confidence for predictions (0-100).
    
    Higher scores indicate more significant institutional activity.
    """
    confidence = 50  # Base confidence
    
    amount_usd = tx.get("amount_usd", 0)
    from_owner = (tx.get("from", {}).get("owner", "") or "").lower()
    to_owner = (tx.get("to", {}).get("owner", "") or "").lower()
    from_type = tx.get("from", {}).get("owner_type", "")
    to_type = tx.get("to", {}).get("owner_type", "")
    
    # Large amounts increase confidence
    if amount_usd >= 100_000_000:  # $100M+
        confidence += 30
    elif amount_usd >= 50_000_000:  # $50M+
        confidence += 20
    elif amount_usd >= 10_000_000:  # $10M+
        confidence += 10
    elif amount_usd >= 5_000_000:  # $5M+
        confidence += 5
    
    # Exchange to unknown wallet = potential accumulation
    if from_owner in KNOWN_EXCHANGES and to_type == "unknown":
        confidence += 15
    
    # Unknown to exchange = potential distribution/selling
    if from_type == "unknown" and to_owner in KNOWN_EXCHANGES:
        confidence += 10
    
    # Institutional transfers
    if from_owner in KNOWN_INSTITUTIONS or to_owner in KNOWN_INSTITUTIONS:
        confidence += 20
    
    # Exchange to exchange transfers (arbitrage/rebalancing)
    if from_owner in KNOWN_EXCHANGES and to_owner in KNOWN_EXCHANGES:
        confidence -= 10  # Less significant for predictions
    
    return max(0, min(100, confidence))


def infer_direction(tx: Dict[str, Any]) -> str:
    """
    Infer market direction from whale transfer patterns.
    
    Returns: BULLISH, BEARISH, or NEUTRAL
    """
    from_owner = (tx.get("from", {}).get("owner", "") or "").lower()
    to_owner = (tx.get("to", {}).get("owner", "") or "").lower()
    from_type = tx.get("from", {}).get("owner_type", "")
    to_type = tx.get("to", {}).get("owner_type", "")
    
    # Exchange outflow to unknown = accumulation = bullish
    if from_owner in KNOWN_EXCHANGES and to_type == "unknown":
        return "BULLISH"
    
    # Unknown to exchange = selling = bearish
    if from_type == "unknown" and to_owner in KNOWN_EXCHANGES:
        return "BEARISH"
    
    # Institutional accumulation
    if to_owner in KNOWN_INSTITUTIONS:
        return "BULLISH"
    
    return "NEUTRAL"


async def process_transaction(tx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process a single whale transaction and publish signal."""
    try:
        blockchain = tx.get("blockchain", "unknown")
        symbol = tx.get("symbol", "").upper()
        amount = tx.get("amount", 0)
        amount_usd = tx.get("amount_usd", 0)
        tx_hash = tx.get("hash", "")
        timestamp = tx.get("timestamp", int(time.time()))
        
        from_addr = tx.get("from", {}).get("address", "")
        to_addr = tx.get("to", {}).get("address", "")
        from_owner = tx.get("from", {}).get("owner", "unknown")
        to_owner = tx.get("to", {}).get("owner", "unknown")
        
        # Skip if below threshold
        if amount_usd < MIN_VALUE_USD:
            return None
        
        # Skip if not on tracked chain
        if blockchain not in TRACKED_CHAINS:
            return None
        
        confidence = score_transaction_confidence(tx)
        direction = infer_direction(tx)
        
        # Format amount for display
        if amount_usd >= 1_000_000_000:
            amount_str = f"${amount_usd / 1_000_000_000:.1f}B"
        elif amount_usd >= 1_000_000:
            amount_str = f"${amount_usd / 1_000_000:.1f}M"
        else:
            amount_str = f"${amount_usd:,.0f}"
        
        summary = f"{amount_str} {symbol} | {from_owner} → {to_owner}"
        
        signal = {
            "type": "whale",
            "sub_type": "transfer",
            "blockchain": blockchain,
            "symbol": symbol,
            "amount": amount,
            "amount_usd": amount_usd,
            "tx_hash": tx_hash,
            "timestamp": timestamp,
            "from_address": from_addr,
            "to_address": to_addr,
            "from_owner": from_owner,
            "to_owner": to_owner,
            "confidence": confidence,
            "direction": direction,
            "summary": summary,
            "tags": ["whale", blockchain, symbol.lower()],
        }
        
        await publish_signal(signal)
        print(f"[WhaleAlert] {summary} | conf={confidence}% | {direction}")
        return signal
        
    except Exception as e:
        print(f"[WhaleAlert] Error processing tx: {e}")
        return None


async def run_whale_alert_scanner():
    """Main scanner loop - polls Whale Alert API every 60 seconds."""
    if not WHALE_ALERT_API_KEY:
        print("[WhaleAlert] No API key configured, scanner disabled")
        return
    
    print("[WhaleAlert] Scanner started")
    seen_hashes: set = set()
    
    while True:
        try:
            transactions = await fetch_recent_transactions()
            
            new_count = 0
            for tx in transactions:
                tx_hash = tx.get("hash", "")
                if tx_hash and tx_hash not in seen_hashes:
                    seen_hashes.add(tx_hash)
                    result = await process_transaction(tx)
                    if result:
                        new_count += 1
            
            if new_count > 0:
                print(f"[WhaleAlert] Processed {new_count} new whale transactions")
            
            # Keep seen_hashes bounded (last 1000)
            if len(seen_hashes) > 1000:
                seen_hashes = set(list(seen_hashes)[-500:])
            
        except Exception as e:
            print(f"[WhaleAlert] Scanner error: {e}")
        
        # Poll every 60 seconds (API rate limit friendly)
        await asyncio.sleep(60)


# API endpoint for fetching whale data (for wallets page)
async def get_recent_whale_transfers(
    chain: Optional[str] = None,
    min_value: int = MIN_VALUE_USD,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Get recent whale transfers for the wallets page.
    
    Returns formatted data suitable for frontend display.
    """
    transactions = await fetch_recent_transactions(min_value=min_value, limit=limit)
    
    results = []
    for tx in transactions:
        blockchain = tx.get("blockchain", "unknown")
        
        # Filter by chain if specified
        if chain and blockchain != chain:
            continue
        
        confidence = score_transaction_confidence(tx)
        direction = infer_direction(tx)
        
        results.append({
            "id": tx.get("id", ""),
            "hash": tx.get("hash", ""),
            "blockchain": blockchain,
            "symbol": tx.get("symbol", ""),
            "amount": tx.get("amount", 0),
            "amount_usd": tx.get("amount_usd", 0),
            "timestamp": tx.get("timestamp", 0),
            "from": {
                "address": tx.get("from", {}).get("address", ""),
                "owner": tx.get("from", {}).get("owner", "unknown"),
                "owner_type": tx.get("from", {}).get("owner_type", "unknown"),
            },
            "to": {
                "address": tx.get("to", {}).get("address", ""),
                "owner": tx.get("to", {}).get("owner", "unknown"),
                "owner_type": tx.get("to", {}).get("owner_type", "unknown"),
            },
            "confidence": confidence,
            "direction": direction,
        })
    
    return results[:limit]
