from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from bus.signal_bus import fetch_recent_signals
from api.ui import _format_event
from api.wallets import KNOWN_WALLETS

router = APIRouter()


# Build wallet address lookup sets for fast filtering
_ETH_WALLETS = {w["address"].lower() for w in KNOWN_WALLETS if w["chain"] == "ethereum"}
_XRPL_WALLETS = {w["address"].lower() for w in KNOWN_WALLETS if w["chain"] == "xrpl"}
_WALLET_LABELS = {w["address"].lower(): w["label"] for w in KNOWN_WALLETS}
_WALLET_ENTITIES = {w["address"].lower(): w["entity"] for w in KNOWN_WALLETS}


@router.get("/flows")
async def list_flows(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    window_seconds: int = Query(86400, ge=1),
    types: Optional[str] = None,
    min_confidence: Optional[int] = Query(None, ge=0, le=100),
    network: Optional[str] = None,
    tx_hash: Optional[str] = None,
    raw: bool = Query(False, description="Return raw unprocessed data for alpha extraction"),
    correlation_asset: Optional[str] = Query(None, description="Filter by correlated asset (e.g., SPY)"),
    wallet: Optional[str] = Query(None, description="Filter by wallet address or entity (e.g., binance, 0xdfd...)"),
    entity: Optional[str] = Query(None, description="Filter by entity name (e.g., binance, ripple, gsr)"),
    institutional_only: bool = Query(False, description="Only show flows involving known institutional wallets"),
) -> Dict[str, Any]:
    type_list: Optional[List[str]] = None
    if types:
        type_list = [t.strip().lower() for t in types.split(",") if t.strip()]
    signals = await fetch_recent_signals(window_seconds=window_seconds, types=type_list)
    filtered: List[Dict[str, Any]] = []
    net_norm = (network or "").strip().lower() if network else None
    tx_norm = (tx_hash or "").strip().lower() if tx_hash else None
    
    # Build wallet filter set
    wallet_filter_addrs: set = set()
    if wallet:
        wallet_lower = wallet.strip().lower()
        # Check if it's an entity name
        if wallet_lower in ["binance", "ripple", "gsr", "cumberland", "wintermute", "coinbase", "kraken", "alameda", "bitstamp"]:
            wallet_filter_addrs = {w["address"].lower() for w in KNOWN_WALLETS if w["entity"] == wallet_lower}
        else:
            wallet_filter_addrs = {wallet_lower}
    if entity:
        entity_addrs = {w["address"].lower() for w in KNOWN_WALLETS if w["entity"] == entity.strip().lower()}
        if wallet_filter_addrs:
            wallet_filter_addrs = wallet_filter_addrs.intersection(entity_addrs)
        else:
            wallet_filter_addrs = entity_addrs
    
    for s in signals:
        if net_norm:
            sn = str(s.get("network") or "").strip().lower()
            if sn != net_norm:
                continue
        if tx_norm:
            th = str(s.get("tx_hash") or "").strip().lower()
            if th != tx_norm:
                continue
        if min_confidence is not None:
            try:
                c = int(s.get("confidence", 0))
            except Exception:
                c = 0
            if c < min_confidence:
                continue
        
        # Wallet/entity filter
        if wallet_filter_addrs or institutional_only:
            from_addr = str(s.get("from") or s.get("source") or s.get("features", {}).get("from") or "").lower()
            to_addr = str(s.get("to") or s.get("destination") or s.get("features", {}).get("to") or "").lower()
            
            if wallet_filter_addrs:
                if from_addr not in wallet_filter_addrs and to_addr not in wallet_filter_addrs:
                    continue
            elif institutional_only:
                all_known = _ETH_WALLETS | _XRPL_WALLETS
                if from_addr not in all_known and to_addr not in all_known:
                    continue
            
            # Annotate with institutional labels
            if from_addr in _WALLET_LABELS:
                s["from_label"] = _WALLET_LABELS[from_addr]
                s["from_entity"] = _WALLET_ENTITIES.get(from_addr)
            if to_addr in _WALLET_LABELS:
                s["to_label"] = _WALLET_LABELS[to_addr]
                s["to_entity"] = _WALLET_ENTITIES.get(to_addr)
        
        filtered.append(s)
    try:
        filtered.sort(key=lambda x: int(x.get("timestamp", 0)), reverse=True)
    except Exception:
        pass
    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]
    
    # Raw mode: return unprocessed data for alpha extraction
    if raw:
        items = page_items  # No formatting/scoring
    else:
        items = [_format_event(s) for s in page_items]
    
    response = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": items,
        "raw_mode": raw,
    }
    
    if raw:
        response["alpha_note"] = "Raw data bypasses ML scoring. Use for custom alpha strategies."
    if correlation_asset:
        response["correlation_filter"] = correlation_asset.upper()
    if wallet or entity:
        response["wallet_filter"] = wallet or entity
    if institutional_only:
        response["institutional_only"] = True
    
    return response
