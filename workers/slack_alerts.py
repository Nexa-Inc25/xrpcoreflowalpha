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


# ============================================================
# LATENCY ANOMALY ALERTS
# ============================================================

MIN_LATENCY_ANOMALY_SCORE = 75  # Only alert on 75%+ anomaly score
MIN_LATENCY_IMPACT_USD = 25_000_000  # $25M+ impact events


async def send_latency_alert(event: dict) -> bool:
    """Send a latency anomaly alert to Slack."""
    if not SLACK_WEBHOOK_URL:
        return False
    
    anomaly_score = event.get("anomaly_score", 0)
    latency_ms = event.get("latency_ms", 0)
    
    # Filter low-score anomalies
    if anomaly_score < MIN_LATENCY_ANOMALY_SCORE:
        return False
    
    # Build alert message
    is_hft = event.get("is_hft", False) or latency_ms < 50
    emoji = "⚡" if is_hft else "🔶" if anomaly_score >= 90 else "🟡"
    
    exchange = event.get("exchange", "unknown").upper()
    symbol = event.get("symbol", "unknown")
    imbalance = event.get("order_book_imbalance", 0)
    spread = event.get("spread_bps", 0)
    signature = event.get("features", {}).get("matched_signature", "unknown")
    
    # Format imbalance direction
    imb_direction = "📈 Buy" if imbalance > 0 else "📉 Sell" if imbalance < 0 else "⚖️ Neutral"
    
    message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{exchange} Latency Anomaly Detected*\n\n"
                            f"*Symbol:* {symbol}\n"
                            f"*Latency:* {latency_ms:.1f}ms {'(HFT)' if is_hft else ''}\n"
                            f"*Anomaly Score:* {anomaly_score:.0f}%\n"
                            f"*Matched Algo:* {signature}\n"
                            f"*Order Book:* {imb_direction} ({abs(imbalance)*100:.1f}% imbalance)\n"
                            f"*Spread:* {spread:.1f} bps"
                }
            }
        ]
    }
    
    # Add XRPL correlation hint if present
    xrpl_hint = event.get("correlation_hint")
    if xrpl_hint:
        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🔗 *XRPL Correlation:* {xrpl_hint} - Watch for XRP flow impact"
            }
        })
    
    # Add spoofing warning if detected
    is_spoofing = event.get("features", {}).get("is_spoofing", False)
    spoof_conf = event.get("features", {}).get("spoof_confidence", 0)
    if is_spoofing and spoof_conf > 60:
        message["blocks"].append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚠️ *Spoofing Alert:* {spoof_conf:.0f}% confidence - Rapid cancellations detected"
            }
        })
    
    # Add link to dashboard
    message["blocks"].append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "View Latency Dashboard"},
                "url": "https://www.zkalphaflow.com/analytics?tab=latency"
            }
        ]
    })
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SLACK_WEBHOOK_URL, json=message) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[SlackAlert] Latency alert error: {e}")
        return False


async def process_latency_anomaly(event: dict):
    """Process latency anomaly and send alert if criteria met."""
    sent = await send_latency_alert(event)
    if sent:
        print(f"[SlackAlert] Sent latency alert: {event.get('exchange')}:{event.get('symbol')} "
              f"score={event.get('anomaly_score', 0):.0f}%")


# ============================================================
# EDUCATOR NOTIFICATIONS
# ============================================================

EDUCATOR_WEBHOOK_URL = os.getenv("SLACK_EDUCATOR_WEBHOOK_URL")


# ============================================================
# INSTITUTIONAL WALLET ALERTS
# ============================================================

MIN_WALLET_USD_VALUE = 10_000_000  # Only alert on $10M+ transfers involving tracked wallets

# Known institutional wallets - import from wallets module at runtime
_KNOWN_WALLET_ADDRESSES: set = set()
_WALLET_LABELS: dict = {}


def _load_wallet_data():
    """Lazy load wallet data from wallets module."""
    global _KNOWN_WALLET_ADDRESSES, _WALLET_LABELS
    if not _KNOWN_WALLET_ADDRESSES:
        try:
            from api.wallets import KNOWN_WALLETS
            _KNOWN_WALLET_ADDRESSES = {w["address"].lower() for w in KNOWN_WALLETS}
            _WALLET_LABELS = {w["address"].lower(): w["label"] for w in KNOWN_WALLETS}
        except Exception:
            pass


async def send_wallet_alert(signal: dict) -> bool:
    """Send alert when large transfer involves tracked institutional wallet."""
    if not SLACK_WEBHOOK_URL:
        return False
    
    _load_wallet_data()
    if not _KNOWN_WALLET_ADDRESSES:
        return False
    
    usd_value = signal.get("usd_value", 0) or signal.get("value_usd", 0)
    if usd_value < MIN_WALLET_USD_VALUE:
        return False
    
    # Check if from/to is a known institutional wallet
    from_addr = str(signal.get("from") or signal.get("source") or signal.get("features", {}).get("from") or "").lower()
    to_addr = str(signal.get("to") or signal.get("destination") or signal.get("features", {}).get("to") or "").lower()
    
    from_label = _WALLET_LABELS.get(from_addr)
    to_label = _WALLET_LABELS.get(to_addr)
    
    if not from_label and not to_label:
        return False  # Neither address is a tracked wallet
    
    # Build alert
    chain = signal.get("chain", signal.get("network", "ETH")).upper()
    symbol = signal.get("symbol", "ETH")
    amount = signal.get("amount", 0)
    tx_hash = signal.get("tx_hash", "")[:16]
    
    # Format USD
    if usd_value >= 1_000_000_000:
        usd_str = f"${usd_value/1_000_000_000:.2f}B"
    elif usd_value >= 1_000_000:
        usd_str = f"${usd_value/1_000_000:.1f}M"
    else:
        usd_str = f"${usd_value/1_000:,.0f}K"
    
    # Direction arrow
    if from_label and to_label:
        direction = f"*{from_label}* → *{to_label}*"
        emoji = "🔄"
    elif from_label:
        direction = f"*{from_label}* → External"
        emoji = "📤"
    else:
        direction = f"External → *{to_label}*"
        emoji = "📥"
    
    message = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *Institutional Wallet Alert*\n\n"
                            f"*Flow:* {direction}\n"
                            f"*Amount:* {amount:,.0f} {symbol} ({usd_str})\n"
                            f"*Chain:* {chain}\n"
                            f"*TX:* `{tx_hash}...`"
                }
            },
            {
                "type": "context",
                "elements": [
                    {"type": "mrkdwn", "text": "🏦 Tracked institutional wallet activity detected"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Details"},
                        "url": f"https://www.zkalphaflow.com/flow/{signal.get('tx_hash', '')}"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View on Etherscan"},
                        "url": f"https://etherscan.io/tx/{signal.get('tx_hash', '')}"
                    }
                ]
            }
        ]
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(SLACK_WEBHOOK_URL, json=message) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[SlackAlert] Wallet alert error: {e}")
        return False


async def process_wallet_alert(signal: dict):
    """Process signal and send wallet alert if it involves a tracked institutional wallet."""
    sent = await send_wallet_alert(signal)
    if sent:
        print(f"[SlackAlert] Sent wallet alert for {signal.get('tx_hash', '')[:16]}")


async def send_educator_notification(data: dict, event_type: str = "latency") -> bool:
    """Send notification to educator Slack channel for course content."""
    webhook = EDUCATOR_WEBHOOK_URL or SLACK_WEBHOOK_URL
    if not webhook:
        return False
    
    if event_type == "latency":
        message = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"📚 *Futures Course Content Available*\n\n"
                                f"New latency data export ready for teaching:\n"
                                f"• {data.get('count', 0)} events captured\n"
                                f"• HFT detections: {data.get('hft_count', 0)}\n"
                                f"• Time range: {data.get('time_range', '24h')}\n\n"
                                f"Use `/educator/export_latency` to download"
                    }
                }
            ]
        }
    else:
        message = {
            "text": f"Educator notification: {event_type}",
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"📚 *Update:* {data.get('message', 'New content available')}"}
                }
            ]
        }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook, json=message) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[SlackAlert] Educator notification error: {e}")
        return False
