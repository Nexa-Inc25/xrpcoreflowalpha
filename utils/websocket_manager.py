"""
Improved WebSocket connection manager with auto-reconnection
"""
import asyncio
import logging
from typing import Callable, Optional, Any
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import ServerInfo, Subscribe

logger = logging.getLogger(__name__)


class ResilientWebsocketClient:
    """
    A resilient WebSocket client that automatically reconnects on failure
    """
    
    def __init__(self, url: str, name: str = "WebSocket"):
        self.url = url
        self.name = name
        self.client: Optional[AsyncWebsocketClient] = None
        self.is_connected = False
        self.reconnect_count = 0
        self.max_reconnect_delay = 300  # 5 minutes max
        
    async def connect(self) -> bool:
        """Establish WebSocket connection"""
        try:
            self.client = AsyncWebsocketClient(self.url)
            await self.client.__aenter__()
            
            # Test connection
            info = await self.client.request(ServerInfo())
            if info and info.is_successful():
                self.is_connected = True
                self.reconnect_count = 0
                logger.info(f"[{self.name}] Connected successfully")
                return True
                
        except Exception as e:
            logger.error(f"[{self.name}] Connection failed: {e}")
            self.is_connected = False
            
        return False
    
    async def disconnect(self):
        """Clean disconnect"""
        if self.client:
            try:
                await self.client.__aexit__(None, None, None)
            except:
                pass
            self.client = None
        self.is_connected = False
    
    async def request(self, payload: Any) -> Any:
        """Make a request with automatic reconnection on failure"""
        max_attempts = 3
        
        for attempt in range(max_attempts):
            if not self.is_connected:
                if not await self.connect():
                    await asyncio.sleep(2 ** attempt)
                    continue
                    
            try:
                if self.client:
                    result = await self.client.request(payload)
                    return result
            except Exception as e:
                error_msg = str(e).lower()
                if "not open" in error_msg or "closed" in error_msg or "connection" in error_msg:
                    logger.warning(f"[{self.name}] Connection lost, reconnecting...")
                    self.is_connected = False
                    await self.disconnect()
                    
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                raise
                
        raise ConnectionError(f"[{self.name}] Failed after {max_attempts} attempts")
    
    async def subscribe(self, streams: list) -> bool:
        """Subscribe to streams with reconnection"""
        try:
            result = await self.request(Subscribe(streams=streams))
            return result is not None
        except Exception as e:
            logger.error(f"[{self.name}] Subscribe failed: {e}")
            return False
    
    async def run_with_reconnect(self, handler: Callable, streams: list = None):
        """
        Run a handler function with automatic reconnection
        
        Args:
            handler: Async function to handle messages
            streams: List of streams to subscribe to
        """
        while True:
            try:
                if not await self.connect():
                    # Exponential backoff
                    delay = min(self.max_reconnect_delay, 5 * (2 ** min(self.reconnect_count, 6)))
                    logger.info(f"[{self.name}] Reconnecting in {delay}s...")
                    self.reconnect_count += 1
                    await asyncio.sleep(delay)
                    continue
                
                # Subscribe to streams
                if streams and not await self.subscribe(streams):
                    logger.error(f"[{self.name}] Failed to subscribe to streams")
                    await self.disconnect()
                    continue
                
                # Start keepalive task
                keepalive_task = asyncio.create_task(self._keepalive())
                
                try:
                    # Process messages
                    async for message in self.client:
                        if not self.is_connected:
                            break
                        
                        try:
                            await handler(message)
                        except Exception as e:
                            logger.error(f"[{self.name}] Handler error: {e}")
                            
                except Exception as e:
                    logger.error(f"[{self.name}] Message loop error: {e}")
                finally:
                    keepalive_task.cancel()
                    
            except Exception as e:
                logger.error(f"[{self.name}] Fatal error: {e}")
                
            finally:
                await self.disconnect()
                
            # Wait before reconnecting
            delay = min(self.max_reconnect_delay, 5 * (2 ** min(self.reconnect_count, 6)))
            logger.info(f"[{self.name}] Reconnecting in {delay}s...")
            self.reconnect_count += 1
            await asyncio.sleep(delay)
    
    async def _keepalive(self):
        """Keepalive task to detect dead connections"""
        consecutive_fails = 0
        
        while self.is_connected:
            await asyncio.sleep(30)  # Check every 30 seconds
            
            try:
                if self.client:
                    result = await self.client.request(ServerInfo())
                    if result and result.is_successful():
                        consecutive_fails = 0
                        continue
                        
            except Exception as e:
                consecutive_fails += 1
                logger.warning(f"[{self.name}] Keepalive failed ({consecutive_fails}): {e}")
                
            if consecutive_fails >= 3:
                logger.error(f"[{self.name}] Keepalive detected dead connection")
                self.is_connected = False
                break
