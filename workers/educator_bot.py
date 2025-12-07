"""
Educator Bot - Live Futures Trading Course Integration

Auto-posts trading lessons, market insights, and correlation alerts
to Slack channels for Pro tier subscribers and futures trading courses.
"""
import asyncio
import json
import os
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiohttp
import redis.asyncio as redis

# Environment config
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
SLACK_EDUCATOR_WEBHOOK_URL = os.getenv("SLACK_EDUCATOR_WEBHOOK_URL", "")
SLACK_ALERTS_WEBHOOK_URL = os.getenv("ALERTS_SLACK_WEBHOOK", "")

# Course content intervals
LESSON_INTERVAL_SECONDS = 3600  # Post a lesson tip every hour
CORRELATION_CHECK_INTERVAL = 300  # Check correlations every 5 min

# Thresholds for alerts
CORRELATION_ALERT_THRESHOLD = 0.7  # Alert on strong correlations
CORRELATION_BREAKDOWN_THRESHOLD = 0.3  # Alert when correlation breaks down


# =============================================================================
# FUTURES TRADING COURSE CONTENT
# =============================================================================

COURSE_LESSONS = [
    {
        "topic": "Order Flow Basics",
        "title": "📚 Understanding Order Book Imbalance",
        "content": "Order book imbalance measures the ratio of bid vs ask volume. "
                   "An imbalance >0.3 suggests strong directional pressure. "
                   "HFT firms use this to front-run large orders.",
        "pro_tip": "Watch for imbalance spikes coinciding with low latency - indicates algo activity.",
    },
    {
        "topic": "HFT Detection",
        "title": "⚡ Identifying HFT Patterns",
        "content": "Sub-50ms latency typically indicates high-frequency trading. "
                   "Look for consistent timing patterns - HFT algos operate on microsecond precision. "
                   "Signature matching can identify specific firms.",
        "pro_tip": "Citadel patterns often show 5-15ms latency with rapid order cancellations.",
    },
    {
        "topic": "Spoofing Detection",
        "title": "🎭 Recognizing Spoofing Behavior",
        "content": "Spoofing involves placing large orders with intent to cancel. "
                   "Watch for high cancellation rates (>80%) on large orders. "
                   "Often precedes significant price moves.",
        "pro_tip": "Combine cancellation rate with order book depth changes for confirmation.",
    },
    {
        "topic": "Cross-Market Correlation",
        "title": "🔗 Trading Correlated Assets",
        "content": "XRP shows moderate correlation with SPY/ES (0.35-0.45). "
                   "When correlation breaks down, expect mean reversion. "
                   "BTC/ETH correlation >0.8 means they move together.",
        "pro_tip": "Trade the spread when correlation temporarily diverges.",
    },
    {
        "topic": "Futures Basics",
        "title": "📈 ES Futures for Crypto Traders",
        "content": "ES (S&P 500 futures) trades nearly 24/7. "
                   "1 ES point = $50. Use micro contracts (MES) for smaller positions. "
                   "ES often leads crypto during risk-on/risk-off shifts.",
        "pro_tip": "Watch ES overnight sessions for clues on crypto direction.",
    },
    {
        "topic": "Risk Management",
        "title": "🛡️ Position Sizing with Correlations",
        "content": "Highly correlated positions compound risk. "
                   "If XRP/BTC correlation is 0.7, they share 70% of variance. "
                   "Reduce position sizes when holding correlated assets.",
        "pro_tip": "Use the heatmap to identify uncorrelated pairs for diversification.",
    },
    {
        "topic": "Latency Arbitrage",
        "title": "⏱️ Understanding Latency Edge",
        "content": "HFT firms pay millions for microsecond advantages. "
                   "Retail can't compete on speed but can detect their activity. "
                   "Use latency spikes as leading indicators for moves.",
        "pro_tip": "Sudden latency drops often precede large institutional orders.",
    },
    {
        "topic": "XRPL Settlement",
        "title": "💎 XRPL as Settlement Layer",
        "content": "XRPL settles in 3-5 seconds vs minutes for other chains. "
                   "Watch for correlation between latency anomalies and XRPL settlements. "
                   "Institutional flow often routes through XRPL for efficiency.",
        "pro_tip": "High XRPL volume during equity volatility = institutional migration.",
    },
]

MARKET_INSIGHTS = [
    "🔔 *Market Insight*: When VIX spikes >25, crypto correlations typically increase as risk assets move together.",
    "🔔 *Market Insight*: ES futures lead SPY by seconds - watch ES for early signals.",
    "🔔 *Market Insight*: Gold/XRP correlation strengthening could indicate institutional hedging via XRPL.",
    "🔔 *Market Insight*: BTC dominance rising often precedes alt weakness - check BTC/ETH ratio.",
    "🔔 *Market Insight*: Low latency + high cancellation rate = likely spoofing. Stay cautious.",
]


async def post_to_slack(webhook_url: str, message: dict) -> bool:
    """Post a message to Slack via webhook."""
    if not webhook_url:
        return False
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message, timeout=10) as resp:
                return resp.status == 200
    except Exception as e:
        print(f"[EducatorBot] Webhook error: {e}")
        return False


def format_lesson_message(lesson: dict) -> dict:
    """Format a course lesson as a Slack message."""
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": lesson["title"],
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": lesson["content"]
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"💡 *Pro Tip*: {lesson['pro_tip']}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📖 Topic: {lesson['topic']} | <https://zkalphaflow.com/analytics|View Live Dashboard>"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "🎓 _Part of the ZK Alpha Flow Futures Trading Course_"
                }
            }
        ]
    }


def format_correlation_alert(correlations: Dict[str, float], alert_type: str) -> dict:
    """Format a correlation alert as a Slack message."""
    emoji = "🔥" if alert_type == "spike" else "⚠️" if alert_type == "breakdown" else "📊"
    title = {
        "spike": "Strong Correlation Detected",
        "breakdown": "Correlation Breakdown Alert",
        "insight": "Cross-Market Update"
    }.get(alert_type, "Correlation Update")
    
    # Build correlation list
    corr_text = "\n".join([
        f"• *{pair}*: {value:+.2f} {'🟢' if abs(value) > 0.7 else '🟡' if abs(value) > 0.4 else '⚪'}"
        for pair, value in correlations.items()
    ])
    
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": corr_text
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Updated {datetime.now(timezone.utc).strftime('%H:%M UTC')} | <https://zkalphaflow.com/analytics?tab=correlations|View Heatmap>"
                    }
                ]
            }
        ]
    }


def format_market_regime_alert(regime: str, details: dict) -> dict:
    """Format a market regime change alert."""
    emoji = "🟢" if regime == "risk_on" else "🔴" if regime == "risk_off" else "🟡"
    
    return {
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Market Regime: {regime.replace('_', ' ').title()}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*SPY/VIX*: {details.get('spy_vix', 0):+.2f}"},
                    {"type": "mrkdwn", "text": f"*BTC/ETH*: {details.get('btc_eth', 0):+.2f}"},
                    {"type": "mrkdwn", "text": f"*XRP/SPY*: {details.get('xrp_spy', 0):+.2f}"},
                    {"type": "mrkdwn", "text": f"*Confidence*: {details.get('confidence', 0):.0%}"},
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📈 *Implication*: {details.get('implication', 'Monitor positions')}"
                }
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "View Dashboard", "emoji": True},
                        "url": "https://zkalphaflow.com/analytics"
                    }
                ]
            }
        ]
    }


async def fetch_correlations() -> Optional[Dict[str, Any]]:
    """Fetch current correlations from API."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "http://localhost:8010/analytics/heatmap?assets=xrp,btc,eth,spy,gold",
                timeout=10
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        print(f"[EducatorBot] Failed to fetch correlations: {e}")
    return None


def analyze_correlations(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze correlations and determine market regime."""
    matrix = data.get("matrix", {})
    
    # Extract key correlations
    xrp_btc = matrix.get("XRP", {}).get("BTC", 0)
    xrp_spy = matrix.get("XRP", {}).get("SPY", 0)
    btc_eth = matrix.get("BTC", {}).get("ETH", 0)
    spy_gold = matrix.get("SPY", {}).get("GOLD", 0)
    
    # Determine regime
    if btc_eth > 0.7 and xrp_spy > 0.3:
        regime = "risk_on"
        implication = "Crypto and equities moving together. Consider long positions on high-confidence signals."
    elif btc_eth > 0.7 and xrp_spy < -0.2:
        regime = "divergence"
        implication = "Crypto decoupling from equities. Watch for independent crypto moves."
    elif spy_gold < -0.3:
        regime = "risk_off"
        implication = "Flight to safety detected. Reduce exposure, watch for reversals."
    else:
        regime = "neutral"
        implication = "Mixed signals. Focus on high-confidence setups only."
    
    return {
        "regime": regime,
        "details": {
            "xrp_btc": xrp_btc,
            "xrp_spy": xrp_spy,
            "btc_eth": btc_eth,
            "spy_gold": spy_gold,
            "confidence": abs(btc_eth) * 0.5 + abs(xrp_spy) * 0.3 + 0.2,
            "implication": implication,
        },
        "key_correlations": {
            "XRP/BTC": xrp_btc,
            "XRP/SPY": xrp_spy,
            "BTC/ETH": btc_eth,
            "SPY/GOLD": spy_gold,
        }
    }


# Track last regime for change detection
_last_regime = None
_lesson_index = 0


async def lesson_poster():
    """Post course lessons periodically."""
    global _lesson_index
    
    print("[EducatorBot] Starting lesson poster...")
    
    while True:
        try:
            await asyncio.sleep(LESSON_INTERVAL_SECONDS)
            
            if not SLACK_EDUCATOR_WEBHOOK_URL:
                continue
            
            # Post next lesson
            lesson = COURSE_LESSONS[_lesson_index % len(COURSE_LESSONS)]
            message = format_lesson_message(lesson)
            
            sent = await post_to_slack(SLACK_EDUCATOR_WEBHOOK_URL, message)
            if sent:
                print(f"[EducatorBot] Posted lesson: {lesson['topic']}")
            
            _lesson_index += 1
            
            # Occasionally post a market insight
            if random.random() < 0.3:
                insight = random.choice(MARKET_INSIGHTS)
                await post_to_slack(SLACK_EDUCATOR_WEBHOOK_URL, {"text": insight})
                
        except Exception as e:
            print(f"[EducatorBot] Lesson poster error: {e}")
            await asyncio.sleep(60)


async def correlation_monitor():
    """Monitor correlations and post alerts on significant changes."""
    global _last_regime
    
    print("[EducatorBot] Starting correlation monitor...")
    
    while True:
        try:
            await asyncio.sleep(CORRELATION_CHECK_INTERVAL)
            
            # Fetch correlations
            data = await fetch_correlations()
            if not data:
                continue
            
            # Analyze
            analysis = analyze_correlations(data)
            regime = analysis["regime"]
            
            # Check for regime change
            if _last_regime and regime != _last_regime:
                print(f"[EducatorBot] Regime change: {_last_regime} -> {regime}")
                
                # Post regime change alert
                message = format_market_regime_alert(regime, analysis["details"])
                await post_to_slack(SLACK_EDUCATOR_WEBHOOK_URL or SLACK_ALERTS_WEBHOOK_URL, message)
            
            _last_regime = regime
            
            # Check for strong correlations worth alerting
            key_corrs = analysis["key_correlations"]
            strong = {k: v for k, v in key_corrs.items() if abs(v) > CORRELATION_ALERT_THRESHOLD}
            
            if strong and random.random() < 0.1:  # Don't spam, 10% chance
                message = format_correlation_alert(strong, "spike")
                await post_to_slack(SLACK_EDUCATOR_WEBHOOK_URL, message)
                
        except Exception as e:
            print(f"[EducatorBot] Correlation monitor error: {e}")
            await asyncio.sleep(60)


async def start_educator_bot():
    """Start the educator bot with lesson posting and correlation monitoring."""
    print("[EducatorBot] Initializing educator bot...")
    
    if not SLACK_EDUCATOR_WEBHOOK_URL and not SLACK_ALERTS_WEBHOOK_URL:
        print("[EducatorBot] No Slack webhooks configured, bot disabled")
        return
    
    # Run both workers
    await asyncio.gather(
        lesson_poster(),
        correlation_monitor(),
    )


if __name__ == "__main__":
    asyncio.run(start_educator_bot())
