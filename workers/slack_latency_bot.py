"""
Slack Latency Bot - Auto-posts HFT anomalies for educator/trader alerts

Listens to Redis 'latency_flow' channel and posts high-confidence anomalies
to Slack channels for real-time monitoring and educational use.
"""
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import redis.asyncio as redis

# Environment config
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SLACK_WEBHOOK_URL = os.getenv("ALERTS_SLACK_WEBHOOK", "")
SLACK_EDUCATOR_WEBHOOK_URL = os.getenv("SLACK_EDUCATOR_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")

# Alert thresholds
MIN_ANOMALY_SCORE = 75  # Only alert on 75%+ anomaly score
HFT_LATENCY_THRESHOLD = 50  # ms - flag as HFT below this
SPOOFING_CONFIDENCE_THRESHOLD = 70  # % - flag spoofing above this

# Rate limiting
_last_alert_time = 0
ALERT_COOLDOWN_SECONDS = 30  # Minimum seconds between alerts


async def post_to_slack(webhook_url: str, message: dict) -> bool:
    """Post a message to Slack via webhook."""
    if not webhook_url:
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[SlackBot] Webhook error: {e}")
        return False


def format_anomaly_alert(event: dict, for_educator: bool = False) -> dict:
    """Format a latency anomaly event as a Slack message."""
    latency = event.get("latency_ms", 0)
    score = event.get("anomaly_score", 0)
    exchange = event.get("exchange", "unknown").upper()
    symbol = event.get("symbol", "unknown")
    imbalance = event.get("order_book_imbalance", 0)
    spread = event.get("spread_bps", 0)
    
    features = event.get("features", {})
    signature = features.get("matched_signature", "unknown")
    is_spoofing = features.get("is_spoofing", False)
    spoof_conf = features.get("spoof_confidence", 0)
    
    correlation = event.get("correlation_hint", "")
    is_hft = latency < HFT_LATENCY_THRESHOLD
    
    # Emoji based on severity
    emoji = "⚡" if is_hft else "🔶" if score >= 90 else "🟡"
    
    # Direction indicator
    imb_dir = "📈 Buy pressure" if imbalance > 0.1 else "📉 Sell pressure" if imbalance < -0.1 else "⚖️ Neutral"
    
    # Build message blocks
    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} {'HFT ' if is_hft else ''}Latency Anomaly Detected",
                "emoji": True
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Exchange:*\n{exchange}"},
                {"type": "mrkdwn", "text": f"*Symbol:*\n{symbol}"},
                {"type": "mrkdwn", "text": f"*Latency:*\n{latency:.1f}ms {'🚀' if is_hft else ''}"},
                {"type": "mrkdwn", "text": f"*Score:*\n{score:.0f}%"},
            ]
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Algo Signature:*\n{signature.replace('_', ' ').title()}"},
                {"type": "mrkdwn", "text": f"*Order Book:*\n{imb_dir}"},
                {"type": "mrkdwn", "text": f"*Spread:*\n{spread:.1f} bps"},
                {"type": "mrkdwn", "text": f"*Imbalance:*\n{abs(imbalance)*100:.1f}%"},
            ]
        },
    ]
    
    # Add correlation info if present
    if correlation:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔗 *XRPL Correlation:* {correlation.capitalize()} - Watch for XRP flow impact"
            }
        })
    
    # Add spoofing warning if detected
    if is_spoofing and spoof_conf > SPOOFING_CONFIDENCE_THRESHOLD:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *Spoofing Alert:* {spoof_conf:.0f}% confidence - Rapid order cancellations detected"
            }
        })
    
    # Add educator context if for educator channel
    if for_educator:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"📚 *Course Use:* Demonstrate {signature.replace('_', ' ')} pattern recognition in futures class. "
                            f"Note the {latency:.0f}ms latency vs. retail (~200-500ms)."
                }
            ]
        })
    
    # Add dashboard link
    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Dashboard", "emoji": True},
                "url": "https://www.zkalphaflow.com/analytics?tab=latency"
            }
        ]
    })
    
    # Add timestamp
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Detected at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            }
        ]
    })
    
    return {"blocks": blocks}


async def process_latency_event(event: dict) -> None:
    """Process a latency event and send alerts if criteria met."""
    global _last_alert_time
    
    score = event.get("anomaly_score", 0)
    latency = event.get("latency_ms", 0)
    
    # Filter by score threshold
    if score < MIN_ANOMALY_SCORE:
        return
    
    # Rate limiting
    now = asyncio.get_event_loop().time()
    if now - _last_alert_time < ALERT_COOLDOWN_SECONDS:
        return
    
    _last_alert_time = now
    
    # Format and send to main alerts channel
    message = format_anomaly_alert(event, for_educator=False)
    sent_main = await post_to_slack(SLACK_WEBHOOK_URL, message)
    
    # Also send to educator channel with additional context
    if SLACK_EDUCATOR_WEBHOOK_URL:
        edu_message = format_anomaly_alert(event, for_educator=True)
        sent_edu = await post_to_slack(SLACK_EDUCATOR_WEBHOOK_URL, edu_message)
    else:
        sent_edu = False
    
    exchange = event.get("exchange", "?")
    symbol = event.get("symbol", "?")
    print(f"[SlackBot] Alert sent: {exchange}:{symbol} score={score:.0f}% (main={sent_main}, edu={sent_edu})")


async def subscribe_to_latency_flow() -> None:
    """Subscribe to Redis latency_flow channel and process events."""
    print("[SlackBot] Starting latency flow subscriber...")
    
    while True:
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            pubsub = r.pubsub()
            await pubsub.subscribe("latency_flow")
            
            print("[SlackBot] Subscribed to 'latency_flow' channel")
            
            async for message in pubsub.listen():
                if message["type"] == "message":
                    try:
                        event = json.loads(message["data"])
                        await process_latency_event(event)
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        print(f"[SlackBot] Event processing error: {e}")
                        
        except Exception as e:
            print(f"[SlackBot] Redis connection error: {e}, reconnecting in 5s...")
            await asyncio.sleep(5)


async def poll_recent_anomalies(interval: int = 60) -> None:
    """Poll Redis for recent anomalies and alert on high-score events."""
    print(f"[SlackBot] Starting anomaly poller (interval={interval}s)...")
    
    seen_events = set()  # Track already-alerted events
    
    while True:
        try:
            r = redis.from_url(REDIS_URL, decode_responses=True)
            events_json = await r.lrange("recent_latency_events", 0, 50)
            
            for event_str in events_json:
                try:
                    event = json.loads(event_str)
                    
                    # Create unique key for deduplication
                    event_key = f"{event.get('exchange')}:{event.get('symbol')}:{event.get('timestamp', 0):.0f}"
                    
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        await process_latency_event(event)
                        
                except Exception:
                    continue
            
            # Cleanup old seen events (keep last 1000)
            if len(seen_events) > 1000:
                seen_events = set(list(seen_events)[-500:])
                
            await r.aclose()
            
        except Exception as e:
            print(f"[SlackBot] Poll error: {e}")
        
        await asyncio.sleep(interval)


async def start_slack_latency_bot() -> None:
    """Start the Slack latency bot with both pub/sub and polling."""
    print("[SlackBot] Initializing Slack latency bot...")
    
    if not SLACK_WEBHOOK_URL and not SLACK_EDUCATOR_WEBHOOK_URL:
        print("[SlackBot] No Slack webhooks configured, bot disabled")
        return
    
    # Run both subscription and polling
    await asyncio.gather(
        subscribe_to_latency_flow(),
        poll_recent_anomalies(interval=60),
    )


# For direct execution
if __name__ == "__main__":
    asyncio.run(start_slack_latency_bot())
