"""
Institutional Wallet Tracking API

Provides known institutional wallet addresses for monitoring.
All addresses are publicly verified via Etherscan, XRPSCAN, or official disclosures.
Holdings fetched LIVE from chain explorers - no stored/mock data.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Query

router = APIRouter()

ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Known institutional wallets - VERIFIED PUBLIC ADDRESSES ONLY
# Sources: Etherscan labels, XRPSCAN, official exchange disclosures
# NO fake/placeholder addresses - empty list if unknown
KNOWN_WALLETS: List[Dict[str, Any]] = [
    # ============ BINANCE (Ethereum) ============
    {
        "address": "0xdfd5293d8e347dfe59e90efd55b2956a1343963d",
        "label": "Binance 16",
        "entity": "binance",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "High-volume trading wallet, frequent institutional flows"
    },
    {
        "address": "0x28c6c06298d514db089934071355e5743bf21d60",
        "label": "Binance 14",
        "entity": "binance",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Major hot wallet, multi-billion dollar flows"
    },
    {
        "address": "0xf977814e90da44bfa03b6295a0616a897441acec",
        "label": "Binance 20",
        "entity": "binance",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "ETH + multi-token wallet"
    },
    {
        "address": "0x3f5ce5fbfe3e9af3971dd833d26ba9b5c936f0be",
        "label": "Binance",
        "entity": "binance",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "General purpose wallet, 17M+ transactions"
    },
    {
        "address": "0x5a52e96bacdabb82fd05763e25335261b270efcb",
        "label": "Binance Cold Wallet",
        "entity": "binance",
        "chain": "ethereum",
        "type": "cold_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Cold storage"
    },
    
    # ============ RIPPLE (XRPL) ============
    {
        "address": "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh",
        "label": "Ripple Genesis",
        "entity": "ripple",
        "chain": "xrpl",
        "type": "genesis",
        "verified": True,
        "source": "XRPL Foundation",
        "notes": "Genesis account - not active for transfers"
    },
    {
        "address": "rN7n3473SaZBCG4dFL83w7a1RXtXtbk2D",
        "label": "Ripple Escrow",
        "entity": "ripple",
        "chain": "xrpl",
        "type": "escrow",
        "verified": True,
        "source": "Ripple Quarterly Reports",
        "notes": "Monthly XRP escrow releases (~1B XRP/month)"
    },
    {
        "address": "rLNaPoKeeBjZe2qs6x52yVPZpZ8td4dc6w",
        "label": "Ripple Operations",
        "entity": "ripple",
        "chain": "xrpl",
        "type": "operations",
        "verified": True,
        "source": "XRPSCAN Labels",
        "notes": "ODL and operational treasury"
    },
    
    # ============ BITSTAMP (XRPL) ============
    {
        "address": "rDsbeomae4FXwgQTJp9Rs64Qg9vDiTCdBv",
        "label": "Bitstamp",
        "entity": "bitstamp",
        "chain": "xrpl",
        "type": "exchange",
        "verified": True,
        "source": "XRPSCAN Labels",
        "notes": "Primary Bitstamp XRP wallet"
    },
    
    # ============ GSR MARKETS (Ethereum) ============
    {
        "address": "0x15abb66ba754f05cbc0165a64a11cded1543de48",
        "label": "GSR Markets",
        "entity": "gsr",
        "chain": "ethereum",
        "type": "trading",
        "verified": True,
        "source": "Arkham Intelligence",
        "notes": "OTC and market making operations"
    },
    {
        "address": "0x33566c9d8be6cf0b23795e0d380e112be9d75836",
        "label": "GSR Markets 2",
        "entity": "gsr",
        "chain": "ethereum",
        "type": "trading",
        "verified": True,
        "source": "Arkham Intelligence",
        "notes": "Secondary trading wallet"
    },
    
    # ============ CUMBERLAND/DRW (Ethereum) ============
    {
        "address": "0xcd531ae9efcce479654c4926dec5f6209531ca7b",
        "label": "Cumberland (Copper Custody)",
        "entity": "cumberland",
        "chain": "ethereum",
        "type": "custody",
        "verified": True,
        "source": "Arkham Intelligence",
        "notes": "Institutional custody via Copper"
    },
    
    # ============ WINTERMUTE (Ethereum) ============
    {
        "address": "0x00000000ae347930bd1e7b0f35588b92280f9e75",
        "label": "Wintermute",
        "entity": "wintermute",
        "chain": "ethereum",
        "type": "trading",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Market maker main wallet"
    },
    {
        "address": "0x4f3a120E72C76c22ae802D129F599BFDbc31cb81",
        "label": "Wintermute 2",
        "entity": "wintermute",
        "chain": "ethereum",
        "type": "trading",
        "verified": True,
        "source": "Arkham Intelligence",
        "notes": "Secondary trading operations"
    },
    
    # ============ COINBASE (Ethereum) ============
    {
        "address": "0x71660c4005ba85c37ccec55d0c4493e66fe775d3",
        "label": "Coinbase 1",
        "entity": "coinbase",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Primary hot wallet"
    },
    {
        "address": "0x503828976d22510aad0201ac7ec88293211d23da",
        "label": "Coinbase 2",
        "entity": "coinbase",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Secondary hot wallet"
    },
    
    # ============ KRAKEN (Ethereum) ============
    {
        "address": "0x2910543af39aba0cd09dbb2d50200b3e800a63d2",
        "label": "Kraken",
        "entity": "kraken",
        "chain": "ethereum",
        "type": "hot_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Primary exchange wallet"
    },
    {
        "address": "0x53d284357ec70ce289d6d64134dfac8e511c8a3d",
        "label": "Kraken Cold",
        "entity": "kraken",
        "chain": "ethereum",
        "type": "cold_wallet",
        "verified": True,
        "source": "Etherscan Labels",
        "notes": "Cold storage"
    },
    
    # ============ CITADEL/INSTITUTIONAL ============
    # NOTE: Citadel Securities does NOT have publicly disclosed crypto wallet addresses
    # They operate through partners (EDX Markets, prime brokers)
    # Track via proxy: monitor flows TO/FROM exchanges they're known to use
    
    # ============ ALAMEDA (DEFUNCT - BANKRUPTCY) ============
    {
        "address": "0x0D2cB19c5D1D4B3f75218Fd6F93F02c2c06e2eFa",
        "label": "Alameda Research (Bankruptcy)",
        "entity": "alameda",
        "chain": "ethereum",
        "type": "bankruptcy",
        "verified": True,
        "source": "Court Filings / Arkham",
        "notes": "Under bankruptcy administration - monitor for liquidations"
    },
]


@router.get("/wallets")
async def list_wallets(
    entity: Optional[str] = Query(None, description="Filter by entity: binance, ripple, gsr, cumberland, wintermute, coinbase, kraken"),
    chain: Optional[str] = Query(None, description="Filter by chain: ethereum, xrpl"),
    wallet_type: Optional[str] = Query(None, description="Filter by type: hot_wallet, cold_wallet, escrow, trading"),
    verified_only: bool = Query(True, description="Only return verified addresses"),
) -> Dict[str, Any]:
    """
    List known institutional wallets.
    
    All addresses are publicly verified via Etherscan labels, XRPSCAN, 
    Arkham Intelligence, or official disclosures.
    
    NOTE: Holdings are NOT stored - use Etherscan/XRPSCAN APIs for live balances.
    """
    wallets = KNOWN_WALLETS.copy()
    
    # Apply filters
    if entity:
        entities = [e.strip().lower() for e in entity.split(",")]
        wallets = [w for w in wallets if w["entity"].lower() in entities]
    
    if chain:
        chains = [c.strip().lower() for c in chain.split(",")]
        wallets = [w for w in wallets if w["chain"].lower() in chains]
    
    if wallet_type:
        types = [t.strip().lower() for t in wallet_type.split(",")]
        wallets = [w for w in wallets if w["type"].lower() in types]
    
    if verified_only:
        wallets = [w for w in wallets if w.get("verified", False)]
    
    # Get unique entities for summary
    entities_summary = {}
    for w in KNOWN_WALLETS:
        ent = w["entity"]
        if ent not in entities_summary:
            entities_summary[ent] = {"count": 0, "chains": set()}
        entities_summary[ent]["count"] += 1
        entities_summary[ent]["chains"].add(w["chain"])
    
    # Convert sets to lists for JSON
    for ent in entities_summary:
        entities_summary[ent]["chains"] = list(entities_summary[ent]["chains"])
    
    return {
        "updated_at": _now_iso(),
        "total": len(wallets),
        "wallets": wallets,
        "entities_summary": entities_summary,
        "note": "Holdings not stored - use chain explorers for live balances. Citadel operates via partners, no direct addresses public."
    }


# NOTE: More specific routes MUST come before the generic /{address} route


@router.get("/wallets/entity/{entity_name}/balances")
async def get_entity_balances(entity_name: str) -> Dict[str, Any]:
    """
    Get LIVE balances for all wallets belonging to an entity.
    
    Example: /wallets/entity/binance/balances
    """
    entity_lower = entity_name.strip().lower()
    entity_wallets = [w for w in KNOWN_WALLETS if w["entity"] == entity_lower and w["chain"] == "ethereum"]
    
    if not entity_wallets:
        return {
            "entity": entity_name,
            "error": f"No Ethereum wallets found for entity '{entity_name}'",
            "available_entities": list(set(w["entity"] for w in KNOWN_WALLETS)),
            "updated_at": _now_iso()
        }
    
    if not ETHERSCAN_API_KEY:
        return {
            "entity": entity_name,
            "error": "ETHERSCAN_API_KEY not configured. Cannot fetch live balances.",
            "updated_at": _now_iso()
        }
    
    balances = []
    total_eth = 0.0
    
    async with httpx.AsyncClient(timeout=15) as client:
        for wallet in entity_wallets:
            try:
                url = f"https://api.etherscan.io/api?module=account&action=balance&address={wallet['address']}&tag=latest&apikey={ETHERSCAN_API_KEY}"
                resp = await client.get(url)
                data = resp.json()
                
                if data.get("status") == "1":
                    balance_wei = int(data.get("result", 0))
                    balance_eth = balance_wei / 1e18
                    total_eth += balance_eth
                    
                    balances.append({
                        "address": wallet["address"],
                        "label": wallet.get("label"),
                        "type": wallet.get("type"),
                        "balance_eth": balance_eth
                    })
                else:
                    balances.append({
                        "address": wallet["address"],
                        "label": wallet.get("label"),
                        "error": data.get("message", "API error")
                    })
            except Exception as e:
                balances.append({
                    "address": wallet["address"],
                    "label": wallet.get("label"),
                    "error": str(e)
                })
    
    return {
        "entity": entity_name,
        "chain": "ethereum",
        "wallet_count": len(entity_wallets),
        "total_eth": total_eth,
        "wallets": balances,
        "updated_at": _now_iso(),
        "source": "Etherscan API (live)"
    }


@router.get("/wallets/{address}/balance")
async def get_wallet_balance(address: str) -> Dict[str, Any]:
    """
    Get LIVE balance for an Ethereum wallet via Etherscan API.
    
    Returns real-time ETH balance. Requires ETHERSCAN_API_KEY.
    For XRPL addresses, returns error - use XRPSCAN directly.
    """
    addr_lower = address.lower()
    
    # Check if XRPL address
    if address.startswith("r") and len(address) > 25:
        return {
            "address": address,
            "chain": "xrpl",
            "error": "XRPL balance not supported via this endpoint. Use XRPSCAN API directly.",
            "xrpscan_url": f"https://xrpscan.com/account/{address}",
            "updated_at": _now_iso()
        }
    
    # Ethereum address - fetch from Etherscan
    if not ETHERSCAN_API_KEY:
        return {
            "address": address,
            "chain": "ethereum",
            "error": "ETHERSCAN_API_KEY not configured. Cannot fetch live balance.",
            "updated_at": _now_iso()
        }
    
    # Get wallet metadata if known
    wallet_meta = None
    for w in KNOWN_WALLETS:
        if w["address"].lower() == addr_lower:
            wallet_meta = w
            break
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # Fetch ETH balance
            url = f"https://api.etherscan.io/api?module=account&action=balance&address={address}&tag=latest&apikey={ETHERSCAN_API_KEY}"
            resp = await client.get(url)
            data = resp.json()
            
            if data.get("status") != "1":
                return {
                    "address": address,
                    "chain": "ethereum",
                    "error": f"Etherscan API error: {data.get('message', 'Unknown error')}",
                    "updated_at": _now_iso()
                }
            
            # Convert Wei to ETH
            balance_wei = int(data.get("result", 0))
            balance_eth = balance_wei / 1e18
            
            result = {
                "address": address,
                "chain": "ethereum",
                "balance_eth": balance_eth,
                "balance_wei": str(balance_wei),
                "updated_at": _now_iso(),
                "source": "Etherscan API (live)",
                "etherscan_url": f"https://etherscan.io/address/{address}"
            }
            
            if wallet_meta:
                result["label"] = wallet_meta.get("label")
                result["entity"] = wallet_meta.get("entity")
                result["type"] = wallet_meta.get("type")
            
            return result
            
    except Exception as e:
        return {
            "address": address,
            "chain": "ethereum",
            "error": f"Failed to fetch balance: {str(e)}",
            "updated_at": _now_iso()
        }


# Generic address lookup - MUST be last as it catches all /{address} patterns
@router.get("/wallets/{address}")
async def get_wallet_detail(address: str) -> Dict[str, Any]:
    """
    Get details for a specific wallet address.
    
    Returns cached metadata only - for live balances, use Etherscan/XRPSCAN APIs directly.
    """
    # Normalize address for comparison
    addr_lower = address.lower()
    
    for wallet in KNOWN_WALLETS:
        if wallet["address"].lower() == addr_lower:
            return {
                "found": True,
                "wallet": wallet,
                "updated_at": _now_iso(),
                "note": "For live balance, query Etherscan/XRPSCAN directly"
            }
    
    return {
        "found": False,
        "address": address,
        "updated_at": _now_iso(),
        "note": "Address not in known institutional wallet database. May still be institutional - check Arkham/Etherscan labels."
    }
