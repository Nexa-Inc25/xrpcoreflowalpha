from typing import Dict

# Linear regression coefficients trained on Polygon ETH/USD OHLCV
# Features: open, high, low, volume
COEFF_OPEN = -0.563
COEFF_HIGH = 0.886
COEFF_LOW = 0.671
COEFF_VOL = -0.0000226
INTERCEPT = 3.575


def predict_eth_close(open_price: float, high: float, low: float, volume: float) -> float:
    """Predict next close price given OHLCV features.

    This is a deterministic linear model; no sklearn dependency required.
    """
    return (
        COEFF_OPEN * open_price
        + COEFF_HIGH * high
        + COEFF_LOW * low
        + COEFF_VOL * volume
        + INTERCEPT
    )


def predict_eth_close_payload(features: Dict) -> Dict[str, float]:
    """Helper that accepts a dict of numeric features and returns a JSON-safe payload."""
    try:
        o = float(features.get("open", 0.0))
        h = float(features.get("high", 0.0))
        l = float(features.get("low", 0.0))
        v = float(features.get("volume", 0.0))
    except Exception:
        o = h = l = v = 0.0
    pred = float(predict_eth_close(o, h, l, v))
    return {"predicted_close": pred}
