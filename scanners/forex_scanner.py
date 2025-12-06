"""
Forex Scanner - DXY, EUR/USD, USD/JPY via Alpha Vantage
Real-time forex data + news sentiment for cross-market signals
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import ALPHA_VANTAGE_API_KEY
from observability.metrics import equity_dark_pool_volume
from bus.signal_bus import publish_signal
from workers.scanner_monitor import mark_scanner_connected, record_scanner_signal, mark_scanner_error

# Alpha Vantage API base
AV_BASE = "https://www.alphavantage.co/query"

# Forex pairs to track (correlated with crypto flows)
FOREX_PAIRS = [
    ("EUR", "USD"),  # Euro/Dollar
    ("USD", "JPY"),  # Dollar/Yen
    ("GBP", "USD"),  # Pound/Dollar
    ("USD", "CHF"),  # Dollar/Swiss Franc
]

# DXY components for dollar index proxy
DXY_WEIGHTS = {
    "EUR": 0.576,
    "JPY": 0.136,
    "GBP": 0.119,
    "CHF": 0.036,
}

# Thresholds
MOVE_THRESHOLD_PCT = 0.2  # 0.2% forex move is significant
SENTIMENT_THRESHOLD = 0.3  # Sentiment score threshold


async def start_forex_scanner():
    """Start forex data scanner using Alpha Vantage."""
    if not ALPHA_VANTAGE_API_KEY:
        print("[FOREX] No ALPHA_VANTAGE_API_KEY configured, skipping")
        return
    
    print(f"[FOREX] Starting scanner for {len(FOREX_PAIRS)} pairs")
    await mark_scanner_connected("forex")
    
    last_rates: Dict[str, float] = {}
    last_check = 0
    poll_interval = 60  # Alpha Vantage rate limit: 5 calls/min free tier
    
    async with httpx.AsyncClient(timeout=15) as client:
        while True:
            try:
                now = time.time()
                if now - last_check < poll_interval:
                    await asyncio.sleep(5)
                    continue
                last_check = now
                
                # Check forex rates
                for from_curr, to_curr in FOREX_PAIRS:
                    await _check_forex_rate(client, from_curr, to_curr, last_rates)
                    await asyncio.sleep(12)  # Rate limit spacing
                
                # Check news sentiment periodically
                await _check_market_sentiment(client)
                    
            except Exception as e:
                print(f"[FOREX] Error: {e}")
                await asyncio.sleep(30)


async def _check_forex_rate(
    client: httpx.AsyncClient,
    from_currency: str,
    to_currency: str,
    last_rates: Dict[str, float]
):
    """Check a forex pair for significant moves."""
    try:
        pair_key = f"{from_currency}/{to_currency}"
        
        resp = await client.get(
            AV_BASE,
            params={
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": from_currency,
                "to_currency": to_currency,
                "apikey": ALPHA_VANTAGE_API_KEY,
            }
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        rate_data = data.get("Realtime Currency Exchange Rate", {})
        
        if not rate_data:
            return
            
        rate = float(rate_data.get("5. Exchange Rate", 0))
        bid = float(rate_data.get("8. Bid Price", 0))
        ask = float(rate_data.get("9. Ask Price", 0))
        
        if rate <= 0:
            return
            
        # Check for significant move
        prev_rate = last_rates.get(pair_key)
        last_rates[pair_key] = rate
        
        if prev_rate and prev_rate > 0:
            pct_change = ((rate - prev_rate) / prev_rate) * 100
            
            if abs(pct_change) >= MOVE_THRESHOLD_PCT:
                direction = "strengthening" if pct_change > 0 else "weakening"
                
                # For USD pairs, interpret direction correctly
                if to_currency == "USD":
                    direction = "weakening" if pct_change > 0 else "strengthening"
                    usd_impact = "USD weak" if pct_change > 0 else "USD strong"
                else:
                    usd_impact = "USD strong" if pct_change > 0 else "USD weak"
                
                print(f"[FOREX] {pair_key} {direction} {abs(pct_change):.3f}%")
                
                await publish_signal({
                    "type": "forex",
                    "sub_type": "rate_move",
                    "pair": pair_key,
                    "rate": rate,
                    "bid": bid,
                    "ask": ask,
                    "change_pct": round(pct_change, 3),
                    "direction": direction,
                    "usd_impact": usd_impact,
                    "timestamp": int(time.time()),
                    "summary": f"{pair_key} {direction} {abs(pct_change):.2f}% → {usd_impact}",
                    "tags": ["forex", from_currency.lower(), to_currency.lower()],
                })
                
    except Exception as e:
        pass


async def _check_market_sentiment(client: httpx.AsyncClient):
    """Check market news sentiment via Alpha Vantage."""
    try:
        resp = await client.get(
            AV_BASE,
            params={
                "function": "NEWS_SENTIMENT",
                "tickers": "CRYPTO:XRP,CRYPTO:BTC,CRYPTO:ETH,FOREX:USD",
                "topics": "financial_markets,economy_monetary",
                "sort": "LATEST",
                "limit": 10,
                "apikey": ALPHA_VANTAGE_API_KEY,
            }
        )
        
        if resp.status_code != 200:
            return
            
        data = resp.json()
        feed = data.get("feed", [])
        
        if not feed:
            return
            
        # Aggregate sentiment
        sentiments = []
        for article in feed[:5]:
            score = float(article.get("overall_sentiment_score", 0))
            sentiments.append(score)
            
        if sentiments:
            avg_sentiment = sum(sentiments) / len(sentiments)
            
            if abs(avg_sentiment) >= SENTIMENT_THRESHOLD:
                sentiment_label = "bullish" if avg_sentiment > 0 else "bearish"
                
                print(f"[FOREX] Market sentiment: {sentiment_label} ({avg_sentiment:.2f})")
                
                await publish_signal({
                    "type": "sentiment",
                    "sub_type": "market_news",
                    "sentiment_score": round(avg_sentiment, 3),
                    "sentiment_label": sentiment_label,
                    "article_count": len(feed),
                    "timestamp": int(time.time()),
                    "summary": f"Market sentiment {sentiment_label} (score: {avg_sentiment:.2f})",
                    "tags": ["sentiment", "news", sentiment_label],
                })
                
    except Exception as e:
        pass


async def calculate_dxy_proxy() -> Optional[float]:
    """
    Calculate a DXY (Dollar Index) proxy from forex rates.
    DXY = weighted geometric mean of USD vs major currencies.
    """
    # Would be implemented to calculate real-time DXY approximation
    return None
