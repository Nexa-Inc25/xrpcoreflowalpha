import asyncio
import uuid
from typing import Union
from models.types import EquityDarkPool, XRPFlow, ZKFlow, CrossMarketSignal
from alerts.slack import send_slack_alert, build_rich_slack_payload

async def correlate_equity_crypto(equity_trade: EquityDarkPool, crypto_flow: Union[XRPFlow, ZKFlow]):
    time_delta = abs(equity_trade.timestamp - crypto_flow.timestamp)
    if time_delta < 900:
        confidence = calculate_cross_signal_confidence(equity_trade, crypto_flow)
        if confidence > 85:
            await trigger_cross_market_alert(equity_trade, crypto_flow, confidence)

def calculate_cross_signal_confidence(equity_trade: EquityDarkPool, crypto_flow: Union[XRPFlow, ZKFlow]) -> int:
    base = 70
    if isinstance(crypto_flow, XRPFlow) and crypto_flow.amount_xrp >= 5_000_000:
        base += 15
    if isinstance(crypto_flow, ZKFlow) and crypto_flow.gas_used >= 400_000:
        base += 15
    if equity_trade.shares >= 100_000:
        base += 10
    return min(base, 99)

async def trigger_cross_market_alert(equity_trade: EquityDarkPool, crypto_flow: Union[XRPFlow, ZKFlow], confidence: int):
    signal = CrossMarketSignal(
        id=str(uuid.uuid4()),
        equity_ticker=equity_trade.symbol,
        crypto_asset="XRP" if isinstance(crypto_flow, XRPFlow) else "ETH/ZK",
        confidence=confidence,
        forecast="Positive",
        equity_trade=equity_trade,
        crypto_flow=crypto_flow,
    )
    payload = build_rich_slack_payload({"type": "cross", "signal": signal})
    await send_slack_alert(payload)
