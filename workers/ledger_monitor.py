"""
Ledger Drift Monitor

Tracks XRPL ledger synchronization and alerts on drift.
Provides verification utilities for transaction hashes.
"""
import asyncio
import time
from typing import Any, Dict, Optional
from dataclasses import dataclass
import httpx


@dataclass
class LedgerState:
    """Current ledger synchronization state."""
    local_ledger: int = 0
    remote_ledger: int = 0
    drift: int = 0
    last_check: float = 0
    is_synced: bool = True
    

# Explorer URL templates for transaction verification
EXPLORER_URLS = {
    "xrpl": {
        "xrpscan": "https://xrpscan.com/tx/{hash}",
        "bithomp": "https://bithomp.com/explorer/{hash}",
        "livenet": "https://livenet.xrpl.org/transactions/{hash}",
    },
    "ethereum": {
        "etherscan": "https://etherscan.io/tx/{hash}",
        "blockscout": "https://eth.blockscout.com/tx/{hash}",
    },
    "bitcoin": {
        "blockstream": "https://blockstream.info/tx/{hash}",
        "mempool": "https://mempool.space/tx/{hash}",
    },
    "solana": {
        "solscan": "https://solscan.io/tx/{hash}",
        "explorer": "https://explorer.solana.com/tx/{hash}",
    },
}


class LedgerMonitor:
    """Monitors XRPL ledger drift and provides verification."""
    
    # Alert thresholds
    DRIFT_WARNING = 10  # ledgers
    DRIFT_CRITICAL = 30  # ledgers
    CHECK_INTERVAL = 30  # seconds
    
    def __init__(self):
        self.state = LedgerState()
        self._callbacks = []
        self._running = False
        self._last_alert_level = None  # Track to avoid spam
        self._alert_suppressed_until = 0  # Suppress repeated alerts
    
    def update_local_ledger(self, ledger_index: int):
        """Update local ledger index from scanner."""
        self.state.local_ledger = ledger_index
        self._check_drift()
    
    async def fetch_remote_ledger(self) -> Optional[int]:
        """Fetch current validated ledger from Ripple mainnet."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "https://s1.ripple.com:51234/",
                    json={"method": "server_info", "params": [{}]}
                )
                if resp.status_code == 200:
                    data = resp.json()
                    ledger = data.get("result", {}).get("info", {}).get("validated_ledger", {}).get("seq")
                    return ledger
        except Exception as e:
            print(f"[LedgerMonitor] Failed to fetch remote ledger: {e}")
        return None
    
    def _check_drift(self):
        """Check and update drift status."""
        if self.state.remote_ledger > 0 and self.state.local_ledger > 0:
            self.state.drift = self.state.remote_ledger - self.state.local_ledger
            self.state.is_synced = abs(self.state.drift) <= self.DRIFT_WARNING
            
            now = time.time()
            
            # Determine alert level
            if abs(self.state.drift) > self.DRIFT_CRITICAL:
                level = "critical"
            elif abs(self.state.drift) > self.DRIFT_WARNING:
                level = "warning"
            else:
                level = "ok"
                self._last_alert_level = None  # Reset when synced
                return
            
            # Only alert if level changed or suppression expired (5 min)
            if level != self._last_alert_level or now > self._alert_suppressed_until:
                if level == "critical":
                    print(f"[LedgerMonitor] CRITICAL: Ledger drift {self.state.drift} (reconnect needed)")
                else:
                    print(f"[LedgerMonitor] WARNING: Ledger drift {self.state.drift}")
                
                self._trigger_callbacks(level, self.state.drift)
                self._last_alert_level = level
                self._alert_suppressed_until = now + 300  # Suppress for 5 min
    
    def _trigger_callbacks(self, level: str, drift: int):
        """Trigger registered drift callbacks."""
        for callback in self._callbacks:
            try:
                callback(level, drift)
            except Exception:
                pass
    
    def on_drift(self, callback):
        """Register a callback for drift alerts."""
        self._callbacks.append(callback)
    
    async def run_monitor(self):
        """Background task to periodically check drift."""
        self._running = True
        print("[LedgerMonitor] Starting ledger drift monitor")
        
        while self._running:
            try:
                remote = await self.fetch_remote_ledger()
                if remote:
                    self.state.remote_ledger = remote
                    self.state.last_check = time.time()
                    self._check_drift()
            except Exception as e:
                print(f"[LedgerMonitor] Error: {e}")
            
            await asyncio.sleep(self.CHECK_INTERVAL)
    
    def stop(self):
        """Stop the monitor."""
        self._running = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current ledger status."""
        return {
            "local_ledger": self.state.local_ledger,
            "remote_ledger": self.state.remote_ledger,
            "drift": self.state.drift,
            "is_synced": self.state.is_synced,
            "last_check": self.state.last_check,
            "drift_seconds": abs(self.state.drift) * 4,  # ~4 sec per ledger
        }


def get_explorer_url(network: str, tx_hash: str, explorer: str = None) -> Optional[str]:
    """
    Get explorer URL for a transaction hash.
    
    Args:
        network: blockchain network (xrpl, ethereum, bitcoin, solana)
        tx_hash: transaction hash
        explorer: specific explorer (optional, uses first available)
    
    Returns:
        Explorer URL or None
    """
    network_lower = network.lower()
    
    # Normalize network names
    if network_lower in ["xrp", "ripple"]:
        network_lower = "xrpl"
    elif network_lower in ["eth"]:
        network_lower = "ethereum"
    elif network_lower in ["btc"]:
        network_lower = "bitcoin"
    elif network_lower in ["sol"]:
        network_lower = "solana"
    
    explorers = EXPLORER_URLS.get(network_lower, {})
    if not explorers:
        return None
    
    if explorer and explorer in explorers:
        return explorers[explorer].format(hash=tx_hash)
    
    # Return first available
    first_explorer = list(explorers.values())[0]
    return first_explorer.format(hash=tx_hash)


def get_all_explorer_urls(network: str, tx_hash: str) -> Dict[str, str]:
    """Get all explorer URLs for a transaction."""
    network_lower = network.lower()
    
    if network_lower in ["xrp", "ripple"]:
        network_lower = "xrpl"
    elif network_lower in ["eth"]:
        network_lower = "ethereum"
    elif network_lower in ["btc"]:
        network_lower = "bitcoin"
    elif network_lower in ["sol"]:
        network_lower = "solana"
    
    explorers = EXPLORER_URLS.get(network_lower, {})
    return {name: url.format(hash=tx_hash) for name, url in explorers.items()}


def enrich_signal_with_explorer_links(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Add explorer links to a signal."""
    tx_hash = signal.get("tx_hash", "")
    network = signal.get("network") or signal.get("blockchain") or signal.get("chain", "")
    
    if tx_hash and network:
        signal["explorer_url"] = get_explorer_url(network, tx_hash)
        signal["explorer_urls"] = get_all_explorer_urls(network, tx_hash)
    
    return signal


# Global singleton
_ledger_monitor: Optional[LedgerMonitor] = None


def get_ledger_monitor() -> LedgerMonitor:
    """Get or create global ledger monitor."""
    global _ledger_monitor
    if _ledger_monitor is None:
        _ledger_monitor = LedgerMonitor()
    return _ledger_monitor


async def start_ledger_monitor():
    """Start the ledger monitor as background task."""
    monitor = get_ledger_monitor()
    asyncio.create_task(monitor.run_monitor())


def update_local_ledger(ledger_index: int):
    """Update local ledger from XRPL scanner."""
    monitor = get_ledger_monitor()
    monitor.update_local_ledger(ledger_index)
