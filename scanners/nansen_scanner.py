"""
Nansen Scanner - Whale wallet labels and smart money attribution
Enriches ETH/Solana flows with institutional labels
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import NANSEN_API_KEY
from observability.metrics import equity_dark_pool_volume
from bus.signal_bus import publish_signal

# Nansen API base
NANSEN_BASE = "https://api.nansen.ai/v1"

# Wallet categories to track
SMART_MONEY_LABELS = [
    "Smart Money",
    "Fund",
    "Market Maker",
    "CEX",
    "Whale",
    "Institution",
    "VC",
]

# Minimum USD threshold for whale alerts
WHALE_MIN_USD = 1_000_000


async def start_nansen_scanner():
    """Start Nansen whale tracking scanner."""
    if not NANSEN_API_KEY:
        print("[NANSEN] No NANSEN_API_KEY configured, skipping")
        return
    
    print("[NANSEN] Starting whale wallet scanner")
    
    last_check = 0
    poll_interval = 120  # 2 minutes between checks
    
    headers = {
        "Authorization": f"Bearer {NANSEN_API_KEY}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=30, headers=headers) as client:
        while True:
            try:
                now = time.time()
                if now - last_check < poll_interval:
                    await asyncio.sleep(10)
                    continue
                last_check = now
                
                # Check smart money flows
                await _check_smart_money_flows(client)
                
                # Check whale movements
                await _check_whale_movements(client)
                    
            except Exception as e:
                print(f"[NANSEN] Error: {e}")
                await asyncio.sleep(60)


async def _check_smart_money_flows(client: httpx.AsyncClient):
    """Check for smart money token flows."""
    try:
        # Get recent smart money transactions
        resp = await client.get(
            f"{NANSEN_BASE}/smart-money/transactions",
            params={
                "chain": "ethereum",
                "limit": 20,
                "min_usd_value": WHALE_MIN_USD,
            }
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        transactions = data.get("data", [])
        
        for tx in transactions:
            await _process_smart_money_tx(tx)
                
    except Exception as e:
        pass


async def _process_smart_money_tx(tx: Dict[str, Any]):
    """Process a single smart money transaction."""
    try:
        from_addr = tx.get("from_address", "")
        to_addr = tx.get("to_address", "")
        from_label = tx.get("from_label", {})
        to_label = tx.get("to_label", {})
        usd_value = float(tx.get("usd_value", 0))
        token = tx.get("token_symbol", "")
        tx_hash = tx.get("transaction_hash", "")
        
        # Get entity names
        from_entity = from_label.get("name", "Unknown")
        to_entity = to_label.get("name", "Unknown")
        from_type = from_label.get("type", "")
        to_type = to_label.get("type", "")
        
        # Determine if this is significant
        is_smart_from = any(l in from_type for l in SMART_MONEY_LABELS)
        is_smart_to = any(l in to_type for l in SMART_MONEY_LABELS)
        
        if not (is_smart_from or is_smart_to):
            return
            
        if usd_value < WHALE_MIN_USD:
            return
            
        # Determine flow direction and significance
        if is_smart_from and to_type == "CEX":
            signal_type = "smart_money_to_cex"
            interpretation = "Potential sell pressure"
        elif from_type == "CEX" and is_smart_to:
            signal_type = "cex_to_smart_money"
            interpretation = "Accumulation signal"
        elif is_smart_from and is_smart_to:
            signal_type = "smart_money_transfer"
            interpretation = "Internal repositioning"
        else:
            signal_type = "whale_movement"
            interpretation = "Large holder activity"
            
        usd_str = f"${usd_value/1e6:.1f}M" if usd_value >= 1e6 else f"${usd_value:,.0f}"
        
        print(f"[NANSEN] {signal_type}: {usd_str} {token} ({from_entity} → {to_entity})")
        
        await publish_signal({
            "type": "whale",
            "sub_type": signal_type,
            "token": token,
            "usd_value": usd_value,
            "from_address": from_addr,
            "to_address": to_addr,
            "from_entity": from_entity,
            "to_entity": to_entity,
            "from_type": from_type,
            "to_type": to_type,
            "interpretation": interpretation,
            "tx_hash": tx_hash,
            "timestamp": int(time.time()),
            "summary": f"{usd_str} {token}: {from_entity} → {to_entity} ({interpretation})",
            "tags": ["whale", "nansen", token.lower(), signal_type],
        })
        
    except Exception as e:
        pass


async def _check_whale_movements(client: httpx.AsyncClient):
    """Check for general whale wallet movements."""
    try:
        # Get whale wallet activity
        resp = await client.get(
            f"{NANSEN_BASE}/wallet/activity",
            params={
                "chain": "ethereum",
                "labels": ",".join(["Whale", "Fund", "Market Maker"]),
                "min_usd": WHALE_MIN_USD,
                "limit": 10,
            }
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        activities = data.get("data", [])
        
        for activity in activities:
            action = activity.get("action", "")
            token = activity.get("token_symbol", "")
            usd_value = float(activity.get("usd_value", 0))
            wallet_label = activity.get("wallet_label", "Whale")
            
            if usd_value < WHALE_MIN_USD:
                continue
                
            usd_str = f"${usd_value/1e6:.1f}M" if usd_value >= 1e6 else f"${usd_value:,.0f}"
            
            await publish_signal({
                "type": "whale",
                "sub_type": f"whale_{action.lower()}",
                "token": token,
                "usd_value": usd_value,
                "action": action,
                "wallet_label": wallet_label,
                "timestamp": int(time.time()),
                "summary": f"{wallet_label} {action} {usd_str} {token}",
                "tags": ["whale", token.lower(), action.lower()],
            })
                
    except Exception as e:
        pass


async def get_wallet_label(address: str, chain: str = "ethereum") -> Optional[Dict[str, Any]]:
    """
    Get Nansen label for a wallet address.
    Used to enrich ZK/dark pool signals with entity attribution.
    """
    if not NANSEN_API_KEY:
        return None
        
    try:
        headers = {"Authorization": f"Bearer {NANSEN_API_KEY}"}
        async with httpx.AsyncClient(timeout=10, headers=headers) as client:
            resp = await client.get(
                f"{NANSEN_BASE}/wallet/label",
                params={"address": address, "chain": chain}
            )
            if resp.status_code == 200:
                return resp.json().get("data")
    except Exception:
        pass
    return None
