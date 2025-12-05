"""
Dune Analytics Scanner - On-chain analytics queries
DEX volumes, whale tracking, protocol flows
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import DUNE_API_KEY
from observability.metrics import equity_dark_pool_volume
from bus.signal_bus import publish_signal

# Dune API base
DUNE_BASE = "https://api.dune.com/api/v1"

# Pre-built query IDs for key metrics
# These are example query IDs - replace with actual saved queries
DUNE_QUERIES = {
    "dex_volume_24h": 3374633,      # DEX volume last 24h
    "whale_transfers": 3374634,     # Large transfers
    "stablecoin_flows": 3374635,    # Stablecoin in/out of exchanges
    "eth_gas_tracker": 3374636,     # Gas prices and usage
    "defi_tvl_changes": 3374637,    # TVL changes in DeFi
}

# Thresholds
VOLUME_SPIKE_PCT = 50  # 50% volume increase
WHALE_MIN_USD = 5_000_000


async def start_dune_scanner():
    """Start Dune Analytics scanner."""
    if not DUNE_API_KEY:
        print("[DUNE] No DUNE_API_KEY configured, skipping")
        return
    
    print("[DUNE] Starting on-chain analytics scanner")
    
    last_check = 0
    poll_interval = 300  # 5 minutes (Dune queries can be slow)
    
    headers = {
        "X-Dune-API-Key": DUNE_API_KEY,
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        while True:
            try:
                now = time.time()
                if now - last_check < poll_interval:
                    await asyncio.sleep(30)
                    continue
                last_check = now
                
                # Run analytics queries
                await _check_dex_volume(client)
                await asyncio.sleep(5)
                
                await _check_whale_transfers(client)
                await asyncio.sleep(5)
                
                await _check_stablecoin_flows(client)
                    
            except Exception as e:
                print(f"[DUNE] Error: {e}")
                await asyncio.sleep(60)


async def _execute_query(client: httpx.AsyncClient, query_id: int) -> Optional[List[Dict]]:
    """Execute a Dune query and return results."""
    try:
        # Execute query
        exec_resp = await client.post(
            f"{DUNE_BASE}/query/{query_id}/execute"
        )
        
        if exec_resp.status_code != 200:
            return None
            
        execution_id = exec_resp.json().get("execution_id")
        if not execution_id:
            return None
            
        # Poll for results (max 30 seconds)
        for _ in range(6):
            await asyncio.sleep(5)
            
            status_resp = await client.get(
                f"{DUNE_BASE}/execution/{execution_id}/status"
            )
            
            if status_resp.status_code != 200:
                continue
                
            state = status_resp.json().get("state")
            if state == "QUERY_STATE_COMPLETED":
                break
            elif state in ["QUERY_STATE_FAILED", "QUERY_STATE_CANCELLED"]:
                return None
        
        # Get results
        results_resp = await client.get(
            f"{DUNE_BASE}/execution/{execution_id}/results"
        )
        
        if results_resp.status_code != 200:
            return None
            
        data = results_resp.json()
        return data.get("result", {}).get("rows", [])
        
    except Exception as e:
        return None


async def _check_dex_volume(client: httpx.AsyncClient):
    """Check DEX volume for anomalies."""
    try:
        # Get latest results from pre-built query
        resp = await client.get(
            f"{DUNE_BASE}/query/{DUNE_QUERIES['dex_volume_24h']}/results"
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        rows = data.get("result", {}).get("rows", [])
        
        if not rows:
            return
            
        for row in rows[:5]:  # Top 5 DEXs
            dex_name = row.get("dex_name", "Unknown")
            volume_24h = float(row.get("volume_usd", 0))
            volume_prev = float(row.get("volume_usd_prev", 0))
            
            if volume_prev > 0:
                change_pct = ((volume_24h - volume_prev) / volume_prev) * 100
                
                if abs(change_pct) >= VOLUME_SPIKE_PCT:
                    direction = "spike" if change_pct > 0 else "drop"
                    vol_str = f"${volume_24h/1e9:.2f}B" if volume_24h >= 1e9 else f"${volume_24h/1e6:.1f}M"
                    
                    print(f"[DUNE] DEX volume {direction}: {dex_name} {change_pct:+.0f}%")
                    
                    await publish_signal({
                        "type": "dex",
                        "sub_type": f"volume_{direction}",
                        "dex": dex_name,
                        "volume_24h": volume_24h,
                        "change_pct": round(change_pct, 1),
                        "timestamp": int(time.time()),
                        "summary": f"{dex_name} volume {direction} {abs(change_pct):.0f}% → {vol_str}",
                        "tags": ["dex", "volume", dex_name.lower()],
                    })
                    
    except Exception as e:
        pass


async def _check_whale_transfers(client: httpx.AsyncClient):
    """Check for large whale transfers."""
    try:
        resp = await client.get(
            f"{DUNE_BASE}/query/{DUNE_QUERIES['whale_transfers']}/results"
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        rows = data.get("result", {}).get("rows", [])
        
        for row in rows:
            usd_value = float(row.get("usd_value", 0))
            
            if usd_value < WHALE_MIN_USD:
                continue
                
            token = row.get("token_symbol", "ETH")
            from_label = row.get("from_label", "Unknown")
            to_label = row.get("to_label", "Unknown")
            tx_hash = row.get("tx_hash", "")
            
            usd_str = f"${usd_value/1e6:.1f}M"
            
            await publish_signal({
                "type": "whale",
                "sub_type": "large_transfer",
                "token": token,
                "usd_value": usd_value,
                "from_label": from_label,
                "to_label": to_label,
                "tx_hash": tx_hash,
                "timestamp": int(time.time()),
                "summary": f"Whale transfer {usd_str} {token}: {from_label} → {to_label}",
                "tags": ["whale", "dune", token.lower()],
            })
                    
    except Exception as e:
        pass


async def _check_stablecoin_flows(client: httpx.AsyncClient):
    """Check stablecoin flows in/out of exchanges."""
    try:
        resp = await client.get(
            f"{DUNE_BASE}/query/{DUNE_QUERIES['stablecoin_flows']}/results"
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        rows = data.get("result", {}).get("rows", [])
        
        if not rows:
            return
            
        # Aggregate net flow
        total_inflow = sum(float(r.get("inflow_usd", 0)) for r in rows)
        total_outflow = sum(float(r.get("outflow_usd", 0)) for r in rows)
        net_flow = total_inflow - total_outflow
        
        if abs(net_flow) >= 100_000_000:  # $100M+ net flow
            direction = "inflow" if net_flow > 0 else "outflow"
            interpretation = "Potential buying pressure" if net_flow > 0 else "Potential selling pressure"
            flow_str = f"${abs(net_flow)/1e9:.2f}B" if abs(net_flow) >= 1e9 else f"${abs(net_flow)/1e6:.0f}M"
            
            print(f"[DUNE] Stablecoin {direction}: {flow_str}")
            
            await publish_signal({
                "type": "stablecoin",
                "sub_type": f"exchange_{direction}",
                "net_flow_usd": net_flow,
                "inflow_usd": total_inflow,
                "outflow_usd": total_outflow,
                "interpretation": interpretation,
                "timestamp": int(time.time()),
                "summary": f"Exchange stablecoin net {direction} {flow_str} ({interpretation})",
                "tags": ["stablecoin", "exchange", direction],
            })
                    
    except Exception as e:
        pass


async def run_custom_query(query_id: int) -> Optional[List[Dict]]:
    """
    Run a custom Dune query by ID.
    Useful for ad-hoc analytics.
    """
    if not DUNE_API_KEY:
        return None
        
    headers = {"X-Dune-API-Key": DUNE_API_KEY}
    async with httpx.AsyncClient(timeout=60, headers=headers) as client:
        return await _execute_query(client, query_id)
