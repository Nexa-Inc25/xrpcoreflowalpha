"""
Slack Alert Worker - Sends high-confidence signals to Slack
"""
import asyncio
import json
import os
import aiohttp
from typing import Optional

SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")
MIN_CONFIDENCE_FOR_ALERT = 75  # Only alert on 75%+ confidence signals
MIN_USD_VALUE_FOR_ALERT = 100000  # Only alert on $100K+ transactions


async def send_slack_alert(signal: dict) -> bool:
    """Send a signal alert to Slack."""
    if not SLACK_WEBHOOK_URL:
        return False
    
    confidence = signal.get("confidence", 0)
    usd_value = signal.get("usd_value", 0)
    
    # Filter low-value or low-confidence signals
    if confidence < MIN_CONFIDENCE_FOR_ALERT:
        return False
    if usd_value < MIN_USD_VALUE_FOR_ALERT:
        return False
    
    # Build alert message
    emoji = "🔴" if confidence >= 90 else "🟠" if confidence >= 80 else "🟡"
    chain = signal.get("chain", "unknown").upper()
    signal_type = signal.get("type", "transfer")
    amount = signal.get("amount", 0)
    symbol = signal.get("symbol", "")
    tx_hash = signal.get("tx_hash", "")[:16]
    
    # Format USD value
    if usd_value >= 1_000_000:
        usd_str = f"${usd_value/1_000_000:.1f}M"
    else:
        usd_str = f"${usd_value/1_000:,.0f}K"
    
    message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{chain} Dark Flow Detected*\n\n"
                            f"*Type:* {signal_type}\n"
                            f"*Amount:* {amount:,.0f} {symbol} ({usd_str})\n"
                            f"*Confidence:* {confidence}%\n"
                            f"*TX:* `{tx_hash}...`"
                }
            }
        ]
    }
    
    # Add prediction if available
    prediction = signal.get("prediction", {})
    if prediction:
        expected_move = prediction.get("expected_move_pct", 0)
        direction = "📈" if expected_move > 0 else "📉"
        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{direction} *Predicted Move:* {expected_move:+.1f}% in 15min"
            }
        })
    
    # Add link to dashboard
    message["blocks"].append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Details"},
                "url": f"https://www.zkalphaflow.com/flow/{signal.get('tx_hash', '')}"
            }
        ]
    })
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SLACK_WEBHOOK_URL, json=message) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[SlackAlert] Error: {e}")
        return False


async def process_signal_for_alerts(signal: dict):
    """Process incoming signal and send alert if criteria met."""
    sent = await send_slack_alert(signal)
    if sent:
        print(f"[SlackAlert] Sent alert for {signal.get('tx_hash', '')[:16]}")
