"""
Slack Bot Integration for Fine-Tuned Forecast Alerts
Delivers real-time predictions and trading signals to Slack channels
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from slack_bolt.async_app import AsyncApp
from slack_sdk.webhook.async_client import AsyncWebhookClient
import pandas as pd
import numpy as np

# Import our predictors
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.fourier_markov_prophet import FourierMarkovProphetIntegrator, IntegratedPrediction
from app.config import (
    SLACK_BOT_TOKEN,
    SLACK_EDUCATOR_WEBHOOK_URL,
    SLACK_COURSE_WEBHOOK_URL,
    ALERTS_SLACK_WEBHOOK
)

logger = logging.getLogger(__name__)

# Initialize Slack app
app = AsyncApp(token=SLACK_BOT_TOKEN) if SLACK_BOT_TOKEN else None
webhook_client = AsyncWebhookClient(ALERTS_SLACK_WEBHOOK) if ALERTS_SLACK_WEBHOOK else None
educator_webhook = AsyncWebhookClient(SLACK_EDUCATOR_WEBHOOK_URL) if SLACK_EDUCATOR_WEBHOOK_URL else None
course_webhook = AsyncWebhookClient(SLACK_COURSE_WEBHOOK_URL) if SLACK_COURSE_WEBHOOK_URL else None


class TunedForecastAlertBot:
    """
    Slack bot for delivering tuned forecast alerts and educational content
    """
    
    def __init__(self):
        self.integrator = FourierMarkovProphetIntegrator()
        self.alert_history = []
        self.last_alert_time = {}
        self.min_alert_interval = timedelta(minutes=15)  # Rate limiting
        
        # Alert thresholds
        self.confidence_threshold = 0.75
        self.migration_threshold = 0.7
        self.manipulation_threshold = 0.6
        
        # Channel mappings
        self.channels = {
            'alerts': '#trading-alerts',
            'education': '#futures-trading-class',
            'vip': '#pro-tier-signals'
        }
    
    async def send_forecast_alert(self, predictions: List[IntegratedPrediction], channel: str = 'alerts'):
        """
        Send forecast alert to Slack with rich formatting
        """
        if not webhook_client:
            logger.warning("Slack webhook not configured")
            return
        
        # Filter high-confidence predictions
        high_conf_preds = [
            p for p in predictions 
            if p.confidence >= self.confidence_threshold
        ]
        
        if not high_conf_preds:
            return
        
        # Check rate limiting
        now = datetime.now()
        if channel in self.last_alert_time:
            if now - self.last_alert_time[channel] < self.min_alert_interval:
                return
        
        # Group by asset
        by_asset = {}
        for pred in high_conf_preds:
            if pred.asset not in by_asset:
                by_asset[pred.asset] = []
            by_asset[pred.asset].append(pred)
        
        # Build message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🎯 Fine-Tuned Forecast Alert"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Timestamp:* {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Model Accuracy:* {self.integrator.current_accuracy * 100:.1f}%"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]
        
        # Add predictions for each asset
        for asset, preds in by_asset.items():
            latest_pred = preds[0]  # Most recent
            
            # Determine emoji based on state
            state_emoji = {
                "Accumulation": "📊",
                "Distribution": "📉",
                "Manipulation": "⚠️",
                "Migration": "🚀"
            }.get(latest_pred.hmm_state, "📈")
            
            # Trend emoji
            trend_emoji = "🟢" if latest_pred.prophet_trend == "bullish" else "🔴"
            
            # Build asset section
            asset_section = {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{state_emoji} *{asset.upper()}* {trend_emoji}\n"
                            f"• *Price:* ${latest_pred.prediction:.4f}\n"
                            f"• *Confidence:* {latest_pred.confidence * 100:.1f}%\n"
                            f"• *HMM State:* {latest_pred.hmm_state}\n"
                            f"• *Fourier Cycle:* {latest_pred.fourier_cycle}\n"
                            f"• *Prophet Trend:* {latest_pred.prophet_trend}"
                }
            }
            
            # Add accessory if high migration probability
            if latest_pred.migration_probability > self.migration_threshold:
                asset_section["accessory"] = {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "🎯 XRP Migration Signal"
                    },
                    "style": "primary",
                    "value": f"migration_{asset}"
                }
            
            # Add warning if manipulation detected
            if latest_pred.manipulation_risk > self.manipulation_threshold:
                asset_section["text"]["text"] += f"\n⚠️ *Manipulation Risk:* {latest_pred.manipulation_risk * 100:.0f}%"
            
            blocks.append(asset_section)
        
        # Add correlation insights
        if 'XRP' in by_asset:
            xrp_pred = by_asset['XRP'][0]
            if xrp_pred.correlations:
                corr_text = "📊 *XRP Correlations:*\n"
                for asset, corr in xrp_pred.correlations.items():
                    corr_emoji = "🔗" if abs(corr) > 0.7 else "🔓" if abs(corr) < 0.3 else "🔄"
                    corr_text += f"  {corr_emoji} {asset}: {corr:.2f}\n"
                
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": corr_text
                    }
                })
        
        # Add footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "💡 _Generated by HMM + Fourier + Prophet Integration_"
                }
            ]
        })
        
        # Send message
        try:
            await webhook_client.send(
                text="New forecast alert available",
                blocks=blocks
            )
            
            # Update rate limiting
            self.last_alert_time[channel] = now
            
            # Log alert
            self.alert_history.append({
                'timestamp': now,
                'channel': channel,
                'assets': list(by_asset.keys()),
                'confidence': np.mean([p.confidence for p in high_conf_preds])
            })
            
            logger.info(f"Sent forecast alert to {channel}")
            
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    async def send_educational_content(self, predictions: List[IntegratedPrediction]):
        """
        Send educational content for futures trading classes
        """
        if not educator_webhook:
            logger.warning("Educator webhook not configured")
            return
        
        # Find interesting patterns for education
        educational_patterns = []
        
        for pred in predictions:
            # HMM state transition example
            if pred.hmm_state == "Migration" and pred.confidence > 0.8:
                educational_patterns.append({
                    'type': 'hmm_migration',
                    'asset': pred.asset,
                    'confidence': pred.confidence,
                    'explanation': (
                        f"Notice how {pred.asset} is in a 'Migration' state with {pred.confidence * 100:.0f}% confidence. "
                        "This pattern often precedes significant directional moves."
                    )
                })
            
            # Fourier harmonic detection
            if pred.fourier_cycle == "approaching_peak" and pred.manipulation_risk > 0.5:
                educational_patterns.append({
                    'type': 'fourier_harmonic',
                    'asset': pred.asset,
                    'cycle': pred.fourier_cycle,
                    'explanation': (
                        f"{pred.asset} shows harmonic patterns approaching a peak. "
                        "This frequency signature often indicates coordinated trading activity."
                    )
                })
            
            # Prophet trend divergence
            if pred.prophet_trend == "bullish" and pred.hmm_state == "Distribution":
                educational_patterns.append({
                    'type': 'divergence',
                    'asset': pred.asset,
                    'explanation': (
                        f"Interesting divergence in {pred.asset}: Prophet shows bullish trend but HMM indicates distribution. "
                        "This conflict often signals a potential reversal."
                    )
                })
        
        if not educational_patterns:
            return
        
        # Build educational message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📚 Futures Trading Class: Live Example"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Today's Lesson: Reading Fine-Tuned Predictive Models*"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add educational patterns
        for i, pattern in enumerate(educational_patterns[:3], 1):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Example {i}: {pattern['type'].replace('_', ' ').title()}*\n"
                            f"Asset: *{pattern['asset']}*\n\n"
                            f"{pattern['explanation']}"
                }
            })
        
        # Add trading tip
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "💡 *Trading Tip:*\n"
                        "When multiple models (HMM, Fourier, Prophet) align with high confidence, "
                        "the signal strength increases significantly. Always wait for confluence!"
            }
        })
        
        # Add call-to-action for Pro tier
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "🎯 *Want real-time signals like these?*\n"
                        "Upgrade to Pro tier for live alerts and exclusive trading classes."
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Upgrade to Pro"
                },
                "style": "primary",
                "url": "https://zkalphaflow.com/pricing"
            }
        })
        
        try:
            await educator_webhook.send(
                text="New educational content available",
                blocks=blocks
            )
            logger.info("Sent educational content to Slack")
        except Exception as e:
            logger.error(f"Failed to send educational content: {e}")
    
    async def send_migration_alert(self, xrp_migration_score: float, signals: List[Dict]):
        """
        Send special alert for XRP migration events
        """
        if xrp_migration_score < self.migration_threshold:
            return
        
        if not webhook_client:
            return
        
        # Build urgent alert
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🚨 XRP MIGRATION ALERT 🚨"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Migration Score:* {xrp_migration_score * 100:.1f}%\n"
                            f"*Confidence Level:* HIGH\n"
                            f"*Action Required:* Review positions immediately"
                },
                "accessory": {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Dashboard"
                    },
                    "style": "danger",
                    "url": "https://zkalphaflow.com/dashboard"
                }
            },
            {
                "type": "divider"
            }
        ]
        
        # Add top signals
        if signals:
            signal_text = "*Top Signals:*\n"
            for signal in signals[:3]:
                emoji = "🟢" if signal['action'] == 'BUY' else "🔴" if signal['action'] == 'SELL' else "👁"
                signal_text += f"{emoji} {signal['type']}: {signal['action']} {signal.get('asset', 'XRP')}\n"
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": signal_text
                }
            })
        
        # Add urgency footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "⏰ _Time-sensitive: Act within 15 minutes for optimal entry_"
                }
            ]
        })
        
        try:
            await webhook_client.send(
                text="URGENT: XRP Migration Detected",
                blocks=blocks
            )
            logger.info(f"Sent XRP migration alert (score: {xrp_migration_score:.2f})")
        except Exception as e:
            logger.error(f"Failed to send migration alert: {e}")
    
    async def send_manipulation_warning(self, asset: str, risk_score: float, pattern_type: str):
        """
        Send warning about detected manipulation
        """
        if risk_score < self.manipulation_threshold:
            return
        
        if not webhook_client:
            return
        
        risk_level = "HIGH" if risk_score > 0.8 else "MEDIUM"
        risk_color = "#ff0000" if risk_score > 0.8 else "#ff9900"
        
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚠️ Manipulation Warning: {asset.upper()}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Risk Level:* {risk_level}\n"
                            f"*Risk Score:* {risk_score * 100:.0f}%\n"
                            f"*Pattern Type:* {pattern_type}\n"
                            f"*Recommended Action:* Exercise caution, consider reducing exposure"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "📊 *Detection Method:*\n"
                            "• Fourier harmonics detected coordinated activity\n"
                            "• HMM shows abnormal state transitions\n"
                            "• Prophet confidence intervals widening"
                }
            }
        ]
        
        # Add color-coded attachment
        attachments = [
            {
                "color": risk_color,
                "text": f"Monitor {asset} closely for the next 2-4 hours"
            }
        ]
        
        try:
            await webhook_client.send(
                text=f"Manipulation warning for {asset}",
                blocks=blocks,
                attachments=attachments
            )
            logger.info(f"Sent manipulation warning for {asset} (risk: {risk_score:.2f})")
        except Exception as e:
            logger.error(f"Failed to send manipulation warning: {e}")


class SlackCommandHandler:
    """
    Handle Slack slash commands for tuned analytics
    """
    
    def __init__(self, alert_bot: TunedForecastAlertBot):
        self.alert_bot = alert_bot
        
        if app:
            self.register_commands()
    
    def register_commands(self):
        """Register slash commands with Slack app"""
        
        @app.command("/forecast")
        async def handle_forecast_command(ack, command, respond):
            """Handle /forecast [asset] command"""
            await ack()
            
            asset = command.get('text', 'xrp').strip().upper()
            
            # Get latest predictions
            # (In production, this would fetch from your API)
            await respond(
                text=f"Fetching forecast for {asset}...",
                response_type="ephemeral"
            )
        
        @app.command("/accuracy")
        async def handle_accuracy_command(ack, respond):
            """Handle /accuracy command"""
            await ack()
            
            accuracy = self.alert_bot.integrator.current_accuracy
            history = self.alert_bot.integrator.accuracy_history[-10:]
            
            response = f"*Current Model Accuracy:* {accuracy * 100:.1f}%\n"
            if history:
                response += f"*10-Period Average:* {np.mean(history) * 100:.1f}%\n"
                response += f"*Trend:* {'📈' if history[-1] > history[0] else '📉'}"
            
            await respond(
                text=response,
                response_type="ephemeral"
            )
        
        @app.command("/correlation")
        async def handle_correlation_command(ack, command, respond):
            """Handle /correlation [asset1] [asset2] command"""
            await ack()
            
            parts = command.get('text', 'xrp btc').strip().split()
            asset1 = parts[0].upper() if len(parts) > 0 else 'XRP'
            asset2 = parts[1].upper() if len(parts) > 1 else 'BTC'
            
            # (In production, fetch actual correlation)
            await respond(
                text=f"Calculating correlation between {asset1} and {asset2}...",
                response_type="ephemeral"
            )


async def start_slack_alert_service():
    """
    Start the Slack alert service
    """
    if not ALERTS_SLACK_WEBHOOK:
        logger.warning("Slack webhook not configured, alert service disabled")
        return
    
    logger.info("Starting Slack tuned alert service")
    
    alert_bot = TunedForecastAlertBot()
    command_handler = SlackCommandHandler(alert_bot)
    
    # Start event loop for periodic checks
    while True:
        try:
            # Fetch latest predictions (would connect to your API in production)
            # For now, we'll simulate with a delay
            await asyncio.sleep(300)  # Check every 5 minutes
            
            # In production, this would:
            # 1. Fetch latest predictions from API
            # 2. Check for significant changes
            # 3. Send appropriate alerts
            
            logger.debug("Checked for new alerts")
            
        except Exception as e:
            logger.error(f"Error in alert service loop: {e}")
            await asyncio.sleep(60)  # Wait before retrying


if __name__ == "__main__":
    # Run the alert service
    asyncio.run(start_slack_alert_service())
