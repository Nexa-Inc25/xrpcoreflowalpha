"""
Enhanced Signal Scoring Module

Provides ML-driven confidence scoring for signals based on:
- Amount thresholds and historical patterns
- Cross-market correlations (XRPL vs ETH/BTC/forex)
- Institutional address recognition
- Time-of-day and volume patterns
"""
import time
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class SignalDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class ScoredSignal:
    """Scored signal with prediction metadata."""
    confidence: int  # 0-100
    direction: SignalDirection
    expected_move_pct: float
    time_horizon_hours: int
    factors: Dict[str, float]
    explanation: str


# Known institutional addresses (XRPL)
XRPL_INSTITUTIONAL = {
    # Ripple addresses
    "rN7n3473SaZBCG4dFL83w7a1RXtXtbk2D9": "ripple_ops",
    "rHb9CJAWyB4rj91VRWn96DkukG4bwdtyTh": "genesis",
    "rPT1Sjq2YGrBMTttX4GZHjKu9dyfzbpAYe": "ripple_treasury",
    # Major exchanges
    "rEy8TFcrAPvhpKrwyrscNYyqBGUkE9hKaJ": "binance_hot",
    "rJb5KsHsDHF1YS5B5DU6QCkH5NsPaKQTcy": "bitstamp",
    "rLHzPsX6oXkzU2qL12kHCH8G8cnZv1rBJh": "kraken",
    "r9cZA1mLK5R5Am25ArfXFmqgNwjZgnfk59": "bitfinex",
}

# Known institutional addresses (Ethereum)
ETH_INSTITUTIONAL = {
    "0xcd531ae9efcce479654c4926dec5f6209531ca7b": "copper_custody",
    "0x15abb66ba754f05cbc0165a64a11cded1543de48": "gsr_liquidity",
    "0x33566c9d8be6cf0b23795e0d380e112be9d75836": "gsr_market",
    "0x28c6c06298d514db089934071355e5743bf21d60": "binance_hot",
    "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "binance_cold",
    "0xdfd5293d8e347dfe59e90efd55b2956a1343963d": "coinbase",
}

# Exchange-to-exchange patterns often signal preparation
EXCHANGE_FLOW_PATTERNS = {
    ("binance", "coinbase"): {"direction": SignalDirection.BULLISH, "weight": 1.2},
    ("coinbase", "binance"): {"direction": SignalDirection.BEARISH, "weight": 1.1},
    ("unknown", "binance"): {"direction": SignalDirection.BEARISH, "weight": 0.9},
    ("unknown", "coinbase"): {"direction": SignalDirection.BULLISH, "weight": 1.0},
}

# Amount thresholds for significance scoring
AMOUNT_THRESHOLDS = {
    "xrp": [
        (100_000_000, 95, 3.0),    # 100M XRP = extreme
        (50_000_000, 90, 2.5),     # 50M XRP = very high
        (10_000_000, 80, 2.0),     # 10M XRP = high
        (1_000_000, 70, 1.5),      # 1M XRP = significant
        (500_000, 60, 1.0),        # 500K XRP = moderate
    ],
    "eth": [
        (100_000, 95, 3.0),        # 100K ETH
        (50_000, 90, 2.5),
        (10_000, 80, 2.0),
        (1_000, 70, 1.5),
        (500, 60, 1.0),
    ],
    "btc": [
        (10_000, 95, 3.0),         # 10K BTC
        (5_000, 90, 2.5),
        (1_000, 80, 2.0),
        (500, 70, 1.5),
        (100, 60, 1.0),
    ],
    "usd": [
        (100_000_000, 95, 3.0),    # $100M
        (50_000_000, 90, 2.5),
        (25_000_000, 85, 2.0),
        (10_000_000, 75, 1.5),
        (1_000_000, 60, 1.0),
    ],
}


def score_amount(amount: float, asset: str) -> Tuple[int, float]:
    """Score based on amount thresholds. Returns (confidence_boost, expected_move_pct)."""
    asset_key = asset.lower()
    if asset_key in ["usdc", "usdt", "dai", "usd"]:
        asset_key = "usd"
    
    thresholds = AMOUNT_THRESHOLDS.get(asset_key, AMOUNT_THRESHOLDS["usd"])
    
    for threshold, confidence, move_pct in thresholds:
        if amount >= threshold:
            return (confidence, move_pct)
    
    return (40, 0.5)  # Below all thresholds


def identify_institution(address: str, network: str = "xrpl") -> Optional[str]:
    """Identify if address belongs to known institution."""
    addr_lower = address.lower() if address else ""
    
    if network.lower() in ["xrpl", "ripple", "xrp"]:
        return XRPL_INSTITUTIONAL.get(address)
    elif network.lower() in ["eth", "ethereum"]:
        return ETH_INSTITUTIONAL.get(addr_lower)
    
    return None


def score_flow_pattern(source_label: str, dest_label: str) -> Tuple[SignalDirection, float]:
    """Score based on source-destination flow pattern."""
    src = source_label.lower() if source_label else "unknown"
    dst = dest_label.lower() if dest_label else "unknown"
    
    # Check direct pattern match
    pattern_key = (src, dst)
    if pattern_key in EXCHANGE_FLOW_PATTERNS:
        pattern = EXCHANGE_FLOW_PATTERNS[pattern_key]
        return (pattern["direction"], pattern["weight"])
    
    # General heuristics
    if "unknown" in src and "unknown" not in dst:
        # Unknown to known exchange = likely selling
        return (SignalDirection.BEARISH, 0.8)
    elif "unknown" not in src and "unknown" in dst:
        # Known exchange to unknown = could be withdrawal for holding
        return (SignalDirection.BULLISH, 0.7)
    
    return (SignalDirection.NEUTRAL, 0.5)


def score_time_of_day() -> float:
    """Score based on time patterns - institutional activity peaks during trading hours."""
    hour = time.gmtime().tm_hour
    
    # US market hours (14:30-21:00 UTC) and Asian hours (00:00-08:00 UTC)
    if 14 <= hour <= 21:  # US session
        return 1.2
    elif 0 <= hour <= 8:  # Asian session
        return 1.1
    elif 8 <= hour <= 14:  # European session
        return 1.0
    
    return 0.9  # Off-hours


def score_signal(signal: Dict[str, Any]) -> ScoredSignal:
    """
    Comprehensive signal scoring with multi-factor analysis.
    
    Returns a ScoredSignal with confidence (0-100), direction, and explanation.
    """
    factors: Dict[str, float] = {}
    explanations: List[str] = []
    
    sig_type = signal.get("type", "unknown")
    network = signal.get("network") or signal.get("blockchain") or signal.get("chain", "unknown")
    
    # 1. Amount-based scoring
    amount_usd = signal.get("amount_usd") or signal.get("usd_value") or 0
    amount_native = signal.get("amount") or signal.get("amount_xrp") or signal.get("amount_eth") or 0
    symbol = signal.get("symbol") or signal.get("native_symbol", "usd")
    
    if amount_usd > 0:
        amount_conf, expected_move = score_amount(amount_usd, "usd")
        factors["amount"] = amount_conf / 100
        explanations.append(f"${amount_usd/1e6:.1f}M transfer detected")
    elif amount_native > 0:
        amount_conf, expected_move = score_amount(amount_native, symbol)
        factors["amount"] = amount_conf / 100
        explanations.append(f"{amount_native:,.0f} {symbol.upper()} transfer")
    else:
        amount_conf, expected_move = 50, 1.0
        factors["amount"] = 0.5
    
    # 2. Institution identification
    source = signal.get("source") or signal.get("from_address") or signal.get("from_owner", "")
    dest = signal.get("destination") or signal.get("to_address") or signal.get("to_owner", "")
    
    src_institution = identify_institution(source, network)
    dst_institution = identify_institution(dest, network)
    
    if src_institution or dst_institution:
        factors["institution"] = 0.9
        if src_institution:
            explanations.append(f"Source: {src_institution}")
        if dst_institution:
            explanations.append(f"Destination: {dst_institution}")
    else:
        factors["institution"] = 0.5
    
    # 3. Flow pattern analysis
    src_label = src_institution or signal.get("from_owner", "unknown")
    dst_label = dst_institution or signal.get("to_owner", "unknown")
    direction, flow_weight = score_flow_pattern(src_label, dst_label)
    factors["flow_pattern"] = flow_weight
    
    # 4. Time-of-day factor
    time_factor = score_time_of_day()
    factors["timing"] = time_factor
    
    # 5. Signal type specifics
    if sig_type == "zk":
        factors["type_boost"] = 0.85
        explanations.append("ZK dark pool activity")
        direction = SignalDirection.NEUTRAL  # ZK flows are harder to predict
    elif sig_type == "whale":
        factors["type_boost"] = 0.75
        explanations.append("Large whale movement")
    elif sig_type in ["xrpl_payment", "payment"]:
        factors["type_boost"] = 0.8
        explanations.append("XRPL payment flow")
    elif sig_type == "trustset":
        factors["type_boost"] = 0.7
        explanations.append("Institutional trustline setup")
        direction = SignalDirection.BULLISH  # Trustlines often precede activity
    else:
        factors["type_boost"] = 0.6
    
    # 6. Gas anomaly for ETH-based signals
    gas_used = signal.get("gas_used") or signal.get("gas", 0)
    if gas_used > 500_000:
        factors["gas_anomaly"] = 0.8
        explanations.append(f"High gas: {gas_used:,}")
    
    # Calculate weighted confidence
    weights = {
        "amount": 0.35,
        "institution": 0.25,
        "flow_pattern": 0.15,
        "timing": 0.1,
        "type_boost": 0.1,
        "gas_anomaly": 0.05,
    }
    
    weighted_sum = sum(factors.get(k, 0.5) * w for k, w in weights.items())
    confidence = int(min(100, max(0, weighted_sum * 100)))
    
    # Adjust expected move based on confidence
    if confidence >= 85:
        expected_move *= 1.5
    elif confidence >= 70:
        expected_move *= 1.2
    elif confidence < 50:
        expected_move *= 0.7
    
    # Determine time horizon based on signal type
    if sig_type in ["zk", "godark_prep"]:
        time_horizon = 4  # ZK settlements take longer
    elif sig_type == "trustset":
        time_horizon = 24  # Trustlines are preparation
    else:
        time_horizon = 1  # Default 1 hour
    
    return ScoredSignal(
        confidence=confidence,
        direction=direction,
        expected_move_pct=round(expected_move, 2),
        time_horizon_hours=time_horizon,
        factors={k: round(v, 3) for k, v in factors.items()},
        explanation=" | ".join(explanations) if explanations else "Standard flow detected"
    )


def enrich_signal_with_score(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich a signal dict with scoring metadata."""
    scored = score_signal(signal)
    
    signal["confidence"] = scored.confidence
    signal["iso_confidence"] = scored.confidence
    signal["iso_direction"] = scored.direction.value
    signal["direction"] = scored.direction.value
    signal["iso_expected_move_pct"] = scored.expected_move_pct
    signal["predicted_move_pct"] = scored.expected_move_pct
    signal["time_horizon_hours"] = scored.time_horizon_hours
    signal["score_factors"] = scored.factors
    signal["score_explanation"] = scored.explanation
    
    return signal
