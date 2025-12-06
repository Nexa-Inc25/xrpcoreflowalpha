"""
Scanner Health Monitor

Tracks the health status of all chain scanners:
- Connection state (connected/disconnected/reconnecting)
- Last signal timestamp
- Signal throughput
- Error rates

Provides API endpoint for health dashboard and alerting.
"""
import asyncio
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class ScannerStatus(Enum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ScannerHealth:
    """Health metrics for a single scanner."""
    name: str
    status: ScannerStatus = ScannerStatus.STOPPED
    last_signal_time: Optional[float] = None
    signals_last_hour: int = 0
    errors_last_hour: int = 0
    connected_at: Optional[float] = None
    last_error: Optional[str] = None
    reconnect_count: int = 0
    _signal_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    _error_times: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_signal(self):
        """Record a signal was processed."""
        now = time.time()
        self.last_signal_time = now
        self._signal_times.append(now)
        self._update_hourly_counts()
    
    def record_error(self, error: str):
        """Record an error occurred."""
        now = time.time()
        self.last_error = error
        self._error_times.append(now)
        self._update_hourly_counts()
    
    def _update_hourly_counts(self):
        """Update hourly signal and error counts."""
        cutoff = time.time() - 3600
        self.signals_last_hour = sum(1 for t in self._signal_times if t > cutoff)
        self.errors_last_hour = sum(1 for t in self._error_times if t > cutoff)
    
    def set_connected(self):
        """Mark scanner as connected."""
        self.status = ScannerStatus.CONNECTED
        self.connected_at = time.time()
    
    def set_reconnecting(self):
        """Mark scanner as reconnecting."""
        self.status = ScannerStatus.RECONNECTING
        self.reconnect_count += 1
    
    def set_error(self, error: str):
        """Mark scanner in error state."""
        self.status = ScannerStatus.ERROR
        self.record_error(error)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        self._update_hourly_counts()
        uptime = None
        if self.connected_at and self.status == ScannerStatus.CONNECTED:
            uptime = int(time.time() - self.connected_at)
        
        return {
            "name": self.name,
            "status": self.status.value,
            "uptime_seconds": uptime,
            "last_signal": self.last_signal_time,
            "signals_per_hour": self.signals_last_hour,
            "errors_per_hour": self.errors_last_hour,
            "reconnect_count": self.reconnect_count,
            "last_error": self.last_error,
        }


class ScannerMonitor:
    """Central monitor for all scanners."""
    
    SCANNER_NAMES = [
        "xrpl",
        "zk_ethereum", 
        "godark_eth",
        "whale_alert",
        "futures",
        "forex",
        "solana_humidifi",
    ]
    
    def __init__(self):
        self.scanners: Dict[str, ScannerHealth] = {
            name: ScannerHealth(name=name) for name in self.SCANNER_NAMES
        }
        self._lock = asyncio.Lock()
    
    async def update_status(self, scanner_name: str, status: ScannerStatus):
        """Update scanner status."""
        async with self._lock:
            if scanner_name not in self.scanners:
                self.scanners[scanner_name] = ScannerHealth(name=scanner_name)
            
            scanner = self.scanners[scanner_name]
            scanner.status = status
            
            if status == ScannerStatus.CONNECTED:
                scanner.set_connected()
            elif status == ScannerStatus.RECONNECTING:
                scanner.set_reconnecting()
    
    async def record_signal(self, scanner_name: str):
        """Record that a scanner processed a signal."""
        async with self._lock:
            if scanner_name in self.scanners:
                self.scanners[scanner_name].record_signal()
    
    async def record_error(self, scanner_name: str, error: str):
        """Record a scanner error."""
        async with self._lock:
            if scanner_name in self.scanners:
                self.scanners[scanner_name].set_error(error)
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all scanners."""
        active = sum(1 for s in self.scanners.values() if s.status == ScannerStatus.CONNECTED)
        total_signals = sum(s.signals_last_hour for s in self.scanners.values())
        total_errors = sum(s.errors_last_hour for s in self.scanners.values())
        
        return {
            "timestamp": time.time(),
            "active_scanners": active,
            "total_scanners": len(self.scanners),
            "signals_per_hour": total_signals,
            "errors_per_hour": total_errors,
            "scanners": {
                name: scanner.to_dict() 
                for name, scanner in self.scanners.items()
            }
        }
    
    def is_healthy(self) -> bool:
        """Check if at least one scanner is active."""
        return any(s.status == ScannerStatus.CONNECTED for s in self.scanners.values())


# Global singleton
_scanner_monitor: Optional[ScannerMonitor] = None


def get_scanner_monitor() -> ScannerMonitor:
    """Get or create global scanner monitor."""
    global _scanner_monitor
    if _scanner_monitor is None:
        _scanner_monitor = ScannerMonitor()
    return _scanner_monitor


async def mark_scanner_connected(name: str):
    """Mark a scanner as connected."""
    monitor = get_scanner_monitor()
    await monitor.update_status(name, ScannerStatus.CONNECTED)


async def mark_scanner_reconnecting(name: str):
    """Mark a scanner as reconnecting."""
    monitor = get_scanner_monitor()
    await monitor.update_status(name, ScannerStatus.RECONNECTING)


async def mark_scanner_error(name: str, error: str):
    """Mark a scanner in error state."""
    monitor = get_scanner_monitor()
    await monitor.record_error(name, error)


async def record_scanner_signal(name: str):
    """Record a signal from a scanner."""
    monitor = get_scanner_monitor()
    await monitor.record_signal(name)
