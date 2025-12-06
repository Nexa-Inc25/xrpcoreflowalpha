"""
Scanner Health API

Provides endpoints for monitoring scanner status and health.
"""
from fastapi import APIRouter
from typing import Any, Dict

from workers.scanner_monitor import get_scanner_monitor

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
