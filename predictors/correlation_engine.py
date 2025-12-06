"""
Multi-Asset Correlation Engine

Tracks correlations between XRPL flows and other markets:
- Forex (EUR/USD, GBP/USD impacts on XRP)
- Commodities (Gold as safe haven signal)
- Equities (SPY/QQQ risk-on/off indicators)
- Other crypto (BTC/ETH dark pool flows)

Used to score signals with cross-market context.
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import statistics


@dataclass
class PricePoint:
    """Single price observation."""
    symbol: str
    price: float
    timestamp: float
    volume: Optional[float] = None


@dataclass  
class CorrelationWindow:
    """Rolling window for correlation calculation."""
    symbol: str
    prices: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add(self, price: float, timestamp: float):
        self.prices.append(PricePoint(self.symbol, price, timestamp))
    
    def get_returns(self) -> List[float]:
        """Calculate percentage returns from price series."""
        if len(self.prices) < 2:
            return []
        returns = []
        prices = list(self.prices)
        for i in range(1, len(prices)):
            if prices[i-1].price > 0:
                ret = (prices[i].price - prices[i-1].price) / prices[i-1].price
                returns.append(ret)
        return returns
    
    def get_latest_change_pct(self, lookback_minutes: int = 60) -> Optional[float]:
        """Get price change % over last N minutes."""
        if len(self.prices) < 2:
            return None
        cutoff = time.time() - (lookback_minutes * 60)
        recent = [p for p in self.prices if p.timestamp >= cutoff]
        if len(recent) < 2:
            return None
        return ((recent[-1].price - recent[0].price) / recent[0].price) * 100


class CorrelationEngine:
    """Tracks cross-market correlations for signal enhancement."""
    
    # Asset symbols we track
    TRACKED_ASSETS = [
        "xrp", "btc", "eth",  # Crypto
        "gold", "silver",  # Commodities
        "spy", "qqq",  # Equities
        "eur_usd", "gbp_usd", "usd_jpy",  # Forex
    ]
    
    # Known correlation patterns (positive = move together, negative = inverse)
    KNOWN_CORRELATIONS = {
        ("xrp", "btc"): 0.7,  # XRP follows BTC generally
        ("xrp", "eth"): 0.6,
        ("xrp", "gold"): 0.3,  # Slight positive in risk-off
        ("xrp", "spy"): 0.4,  # Risk-on correlation
        ("btc", "gold"): -0.2,  # Generally inverse
        ("spy", "gold"): -0.3,  # Risk on/off
    }
    
    def __init__(self):
        self.windows: Dict[str, CorrelationWindow] = {
            symbol: CorrelationWindow(symbol) for symbol in self.TRACKED_ASSETS
        }
        self.last_update: Dict[str, float] = {}
        self._lock = asyncio.Lock()
    
    async def update_price(self, symbol: str, price: float, timestamp: Optional[float] = None):
        """Update price for an asset."""
        symbol = symbol.lower().replace("/", "_")
        if symbol not in self.windows:
            self.windows[symbol] = CorrelationWindow(symbol)
        
        ts = timestamp or time.time()
        async with self._lock:
            self.windows[symbol].add(price, ts)
            self.last_update[symbol] = ts
    
    def calculate_correlation(self, symbol1: str, symbol2: str) -> Optional[float]:
        """Calculate rolling correlation between two assets."""
        s1 = symbol1.lower().replace("/", "_")
        s2 = symbol2.lower().replace("/", "_")
        
        if s1 not in self.windows or s2 not in self.windows:
            # Return known correlation if available
            key = (s1, s2) if (s1, s2) in self.KNOWN_CORRELATIONS else (s2, s1)
            return self.KNOWN_CORRELATIONS.get(key)
        
        returns1 = self.windows[s1].get_returns()
        returns2 = self.windows[s2].get_returns()
        
        if len(returns1) < 10 or len(returns2) < 10:
            # Not enough data, use known correlation
            key = (s1, s2) if (s1, s2) in self.KNOWN_CORRELATIONS else (s2, s1)
            return self.KNOWN_CORRELATIONS.get(key)
        
        # Align lengths
        min_len = min(len(returns1), len(returns2))
        r1 = returns1[-min_len:]
        r2 = returns2[-min_len:]
        
        try:
            # Pearson correlation
            mean1 = statistics.mean(r1)
            mean2 = statistics.mean(r2)
            
            num = sum((a - mean1) * (b - mean2) for a, b in zip(r1, r2))
            den1 = sum((a - mean1) ** 2 for a in r1) ** 0.5
            den2 = sum((b - mean2) ** 2 for b in r2) ** 0.5
            
            if den1 * den2 == 0:
                return 0.0
            
            return num / (den1 * den2)
        except Exception:
            return None
    
    def get_market_context(self, target_asset: str = "xrp") -> Dict[str, Any]:
        """Get current market context for signal enhancement."""
        context = {
            "target": target_asset,
            "timestamp": time.time(),
            "correlations": {},
            "recent_moves": {},
            "risk_sentiment": "neutral",
        }
        
        # Calculate correlations with target
        for symbol in self.TRACKED_ASSETS:
            if symbol != target_asset:
                corr = self.calculate_correlation(target_asset, symbol)
                if corr is not None:
                    context["correlations"][symbol] = round(corr, 3)
        
        # Get recent price moves
        for symbol, window in self.windows.items():
            change = window.get_latest_change_pct(60)
            if change is not None:
                context["recent_moves"][symbol] = round(change, 2)
        
        # Determine risk sentiment from SPY/Gold moves
        spy_move = context["recent_moves"].get("spy", 0)
        gold_move = context["recent_moves"].get("gold", 0)
        
        if spy_move > 0.5 and gold_move < 0:
            context["risk_sentiment"] = "risk_on"
        elif spy_move < -0.5 and gold_move > 0:
            context["risk_sentiment"] = "risk_off"
        elif abs(spy_move) > 1:
            context["risk_sentiment"] = "volatile"
        
        return context
    
    def adjust_signal_confidence(
        self, 
        signal: Dict[str, Any], 
        base_confidence: int
    ) -> Tuple[int, str]:
        """
        Adjust signal confidence based on cross-market correlations.
        
        Returns (adjusted_confidence, explanation).
        """
        adjustments = []
        total_adjustment = 0
        
        network = signal.get("network", "").lower()
        sig_type = signal.get("type", "").lower()
        
        # Get market context
        target = "xrp" if "xrpl" in network or "xrp" in sig_type else "eth"
        context = self.get_market_context(target)
        
        # 1. Risk sentiment adjustment
        sentiment = context.get("risk_sentiment", "neutral")
        direction = signal.get("direction") or signal.get("iso_direction", "neutral")
        
        if sentiment == "risk_on" and direction == "bullish":
            total_adjustment += 5
            adjustments.append("Risk-on market +5%")
        elif sentiment == "risk_off" and direction == "bearish":
            total_adjustment += 5
            adjustments.append("Risk-off confirms +5%")
        elif sentiment == "volatile":
            total_adjustment -= 5
            adjustments.append("High volatility -5%")
        
        # 2. BTC correlation check
        btc_move = context.get("recent_moves", {}).get("btc", 0)
        btc_corr = context.get("correlations", {}).get("btc", 0.7)
        
        if abs(btc_move) > 2:
            if (btc_move > 0 and direction == "bullish") or (btc_move < 0 and direction == "bearish"):
                adjustment = int(abs(btc_move) * btc_corr)
                total_adjustment += adjustment
                adjustments.append(f"BTC {btc_move:+.1f}% aligned +{adjustment}%")
            elif (btc_move > 0 and direction == "bearish") or (btc_move < 0 and direction == "bullish"):
                total_adjustment -= 3
                adjustments.append("BTC divergence -3%")
        
        # 3. Gold safe-haven signal
        gold_move = context.get("recent_moves", {}).get("gold", 0)
        if gold_move > 1 and direction == "bearish":
            total_adjustment += 3
            adjustments.append("Gold flight confirms -3%")
        
        # Calculate final confidence
        adjusted = min(100, max(0, base_confidence + total_adjustment))
        explanation = " | ".join(adjustments) if adjustments else "No cross-market signals"
        
        return (adjusted, explanation)


# Global singleton
_correlation_engine: Optional[CorrelationEngine] = None


def get_correlation_engine() -> CorrelationEngine:
    """Get or create global correlation engine."""
    global _correlation_engine
    if _correlation_engine is None:
        _correlation_engine = CorrelationEngine()
    return _correlation_engine


async def update_market_price(symbol: str, price: float):
    """Update market price in correlation engine."""
    engine = get_correlation_engine()
    await engine.update_price(symbol, price)


def get_correlation_context(target: str = "xrp") -> Dict[str, Any]:
    """Get current correlation context."""
    engine = get_correlation_engine()
    return engine.get_market_context(target)
