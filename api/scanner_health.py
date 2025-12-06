"""
Scanner Health API

Provides endpoints for monitoring scanner status and health.
"""
from fastapi import APIRouter
from typing import Any, Dict

from workers.scanner_monitor import get_scanner_monitor
from workers.ledger_monitor import get_ledger_monitor, get_explorer_url, get_all_explorer_urls

router = APIRouter()


@router.get("/health/scanners")
async def get_scanner_health() -> Dict[str, Any]:
    """
    Get health status of all chain scanners.
    
    Returns:
        - active_scanners: Number of connected scanners
        - total_scanners: Total registered scanners
        - signals_per_hour: Combined signal throughput
        - errors_per_hour: Combined error rate
        - scanners: Detailed status per scanner
    """
    monitor = get_scanner_monitor()
    return monitor.get_health_summary()


@router.get("/health/scanners/{scanner_name}")
async def get_single_scanner_health(scanner_name: str) -> Dict[str, Any]:
    """Get health status of a specific scanner."""
    monitor = get_scanner_monitor()
    if scanner_name in monitor.scanners:
        return monitor.scanners[scanner_name].to_dict()
    return {"error": f"Scanner '{scanner_name}' not found"}


@router.get("/health/ledger")
async def get_ledger_status() -> Dict[str, Any]:
    """
    Get XRPL ledger synchronization status.
    
    Returns:
        - local_ledger: Scanner's current ledger
        - remote_ledger: Mainnet validated ledger
        - drift: Ledger difference
        - drift_seconds: Approximate time drift
        - is_synced: Whether within acceptable drift
    """
    monitor = get_ledger_monitor()
    status = monitor.get_status()
    
    # Add sync status interpretation
    if status["drift"] == 0 and status["local_ledger"] == 0:
        status["sync_status"] = "not_started"
    elif status["is_synced"]:
        status["sync_status"] = "synced"
    elif abs(status["drift"]) <= 30:
        status["sync_status"] = "slight_delay"
    else:
        status["sync_status"] = "out_of_sync"
    
    return status


@router.get("/verify/tx/{network}/{tx_hash}")
async def get_tx_explorer_links(network: str, tx_hash: str) -> Dict[str, Any]:
    """
    Get explorer verification links for a transaction.
    
    Args:
        network: Blockchain network (xrpl, ethereum, bitcoin, solana)
        tx_hash: Transaction hash
    
    Returns:
        - primary_url: Main explorer link
        - all_urls: All available explorer links
    """
    primary = get_explorer_url(network, tx_hash)
    all_urls = get_all_explorer_urls(network, tx_hash)
    
    return {
        "network": network,
        "tx_hash": tx_hash,
        "primary_url": primary,
        "all_urls": all_urls,
        "verified": primary is not None
    }
