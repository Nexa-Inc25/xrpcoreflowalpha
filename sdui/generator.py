from models.types import CrossMarketSignal

def generate_cross_market_card(signal: CrossMarketSignal) -> dict:
    return {
        "type": "cross_market_flow",
        "id": signal.id,
        "title": f"{signal.equity_ticker} ↔ {signal.crypto_asset}",
        "confidence": signal.confidence,
        "predicted_impact": signal.forecast,
        "auto_expand": signal.confidence > 90,
    }
