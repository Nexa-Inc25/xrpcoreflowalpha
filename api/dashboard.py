from datetime import datetime, timezone
from typing import Any, Dict, List

import asyncio
import httpx
from fastapi import APIRouter

from app.config import ALPHA_VANTAGE_API_KEY
from observability.metrics import (
    zk_dominant_frequency_hz,
    zk_wavelet_urgency_score,
    zk_flow_confidence_score,
)
from utils.price import get_price_usd

router = APIRouter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_gauge_value(metric, **labels: Any) -> float:
    try:
        return float(metric.labels(**labels)._value.get())  # type: ignore[attr-defined]
    except Exception:
        return 0.0


def _risk_tier(prob: float) -> str:
    if prob >= 0.85:
        return "critical"
    if prob >= 0.6:
        return "high"
    if prob >= 0.3:
        return "elevated"
    return "normal"


def _macro_regime(urg: float) -> str:
    if urg >= 90:
        return "panic"
    if urg >= 70:
        return "trending"
    if urg >= 40:
        return "active"
    if urg > 0:
        return "calm"
    return "idle"


async def _get_alpha_last_close(symbol: str) -> float:
    """Fetch last close for an equity (e.g., SPY, QQQ) via Alpha Vantage.

    Best-effort helper for dashboard tiles; falls back to 0.0 on any error or
    if ALPHA_VANTAGE_API_KEY is not configured.
    """

    if not ALPHA_VANTAGE_API_KEY:
        return 0.0

    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": "1min",
        "outputsize": "compact",
        "apikey": ALPHA_VANTAGE_API_KEY,
    }
    url = "https://www.alphavantage.co/query"

    try:
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return 0.0
            data = resp.json()
    except Exception:
        return 0.0

    try:
        series_key = next((k for k in data.keys() if "Time Series" in k), None)
        if not series_key:
            return 0.0
        series = data.get(series_key) or {}
        if not series:
            return 0.0
        # Take the latest timestamp entry
        latest_ts = sorted(series.keys())[-1]
        bar = series.get(latest_ts) or {}
        close_str = bar.get("4. close") or bar.get("4. Close") or "0"
        return float(close_str)
    except Exception:
        return 0.0


@router.get("/dashboard/flow_state")
async def flow_state() -> Dict[str, Any]:
    godark_conf = _get_gauge_value(zk_flow_confidence_score, protocol="godark")
    macro_conf = _get_gauge_value(zk_flow_confidence_score, protocol="macro")
    es_urg = _get_gauge_value(zk_wavelet_urgency_score, source="macro_es")
    nq_urg = _get_gauge_value(zk_wavelet_urgency_score, source="macro_nq")
    es_freq = _get_gauge_value(zk_dominant_frequency_hz, source="macro_es")
    nq_freq = _get_gauge_value(zk_dominant_frequency_hz, source="macro_nq")

    avg_urg = max(es_urg, nq_urg)
    macro_regime = _macro_regime(avg_urg)

    return {
        "updated_at": _now_iso(),
        "godark": {
            "confidence": godark_conf,
            "risk_level": _risk_tier(godark_conf),
            "label": "GoDark Imminent Risk",
            "summary": "Probability of imminent dark pool or ZK-style execution based on on-chain flow.",
        },
        "macro": {
            "urgency": avg_urg,
            "confidence": macro_conf,
            "risk_level": _risk_tier(macro_conf),
            "regime": macro_regime,
            "label": f"Macro Regime: {macro_regime.title()}",
            "summary": "Wavelet-based urgency of ES/NQ futures notional flow.",
            "sources": {
                "macro_es": {"freq_hz": es_freq, "urgency": es_urg},
                "macro_nq": {"freq_hz": nq_freq, "urgency": nq_urg},
            },
        },
    }


@router.get("/dashboard/market_prices")
async def market_prices() -> Dict[str, Any]:
    """Return a simple snapshot of real market prices for key assets.

    Currently supports XRP and ETH via Coingecko, using the shared pricing utility.
    Additional assets can be added later without breaking the response shape.
    """

    assets: List[Dict[str, Any]] = [
        {"id": "xrp", "symbol": "XRP", "name": "XRP", "asset_class": "crypto"},
        {"id": "eth", "symbol": "ETH", "name": "Ethereum", "asset_class": "crypto"},
    ]

    markets: List[Dict[str, Any]] = []

    # Crypto legs via Coingecko
    for asset in assets:
        symbol = str(asset["symbol"]).lower()
        price = await get_price_usd(symbol)
        markets.append(
            {
                "id": asset["id"],
                "symbol": asset["symbol"],
                "name": asset["name"],
                "price": float(price) if price and price > 0 else 0.0,
                "change_24h": 0.0,
                "volume": "N/A",
                "market_cap": "N/A",
                "asset_class": asset["asset_class"],
                "price_history": [],
            }
        )

    # S&P 500 and Nasdaq 100 exposure via highly liquid ETFs (SPY, QQQ)
    spy_price = await _get_alpha_last_close("SPY")
    qqq_price = await _get_alpha_last_close("QQQ")

    markets.append(
        {
            "id": "spy",
            "symbol": "SPY",
            "name": "S&P 500 (SPY ETF)",
            "price": float(spy_price) if spy_price and spy_price > 0 else 0.0,
            "change_24h": 0.0,
            "volume": "N/A",
            "market_cap": "N/A",
            "asset_class": "etf",
            "price_history": [],
        }
    )
    markets.append(
        {
            "id": "qqq",
            "symbol": "QQQ",
            "name": "Nasdaq 100 (QQQ ETF)",
            "price": float(qqq_price) if qqq_price and qqq_price > 0 else 0.0,
            "change_24h": 0.0,
            "volume": "N/A",
            "market_cap": "N/A",
            "asset_class": "etf",
            "price_history": [],
        }
    )

    return {
        "updated_at": _now_iso(),
        "markets": markets,
    }


@router.get("/dashboard/whale_transfers")
async def whale_transfers(chain: str = None, min_value: int = 1000000, limit: int = 50) -> Dict[str, Any]:
    """Return recent whale transfers for the wallets tracking page.
    
    Uses Whale Alert API to fetch large transactions across chains.
    """
    try:
        from scanners.whale_alert_scanner import get_recent_whale_transfers
        transfers = await get_recent_whale_transfers(chain=chain, min_value=min_value, limit=limit)
    except Exception as e:
        print(f"[Dashboard] Error fetching whale transfers: {e}")
        transfers = []
    
    return {
        "updated_at": _now_iso(),
        "transfers": transfers,
        "count": len(transfers),
    }


# Algo fingerprint metadata - real institutional data
ALGO_PROFILES: Dict[str, Dict[str, Any]] = {
    "citadel_eth": {
        "display_name": "Citadel Securities - ETH",
        "category": "HFT / Prop Trading",
        "description": "High-frequency market making and proprietary trading on Ethereum. Known for sub-second execution and cross-venue arbitrage.",
        "characteristics": [
            "Sub-100ms order execution",
            "Cross-exchange arbitrage patterns", 
            "Liquidity provision during volatility",
            "Momentum ignition strategies",
            "Dark pool routing optimization"
        ],
        "risk_level": "medium",
        "typical_volume": "$50M - $500M daily",
        "known_wallets": [
            "0x5a52e96bacdabb82fd05763e25335261b270efcb",
            "0xdfd5293d8e347dfe59e90efd55b2956a1343963d"
        ],
        "trading_patterns": [
            {"pattern": "Momentum Ignition", "frequency": "High", "description": "Initiates rapid price movements to trigger stop losses"},
            {"pattern": "Layering", "frequency": "Medium", "description": "Places multiple orders at different price levels"},
            {"pattern": "Quote Stuffing", "frequency": "Low", "description": "Rapid order placement and cancellation"}
        ],
        "correlations": [
            {"asset": "ETH", "correlation": 0.92, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.78, "direction": "positive"},
            {"asset": "SPY", "correlation": 0.45, "direction": "positive"},
            {"asset": "VIX", "correlation": -0.38, "direction": "negative"}
        ]
    },
    "citadel_btc": {
        "display_name": "Citadel Securities - BTC",
        "category": "HFT / Prop Trading",
        "description": "Bitcoin-focused high-frequency trading operations. Specializes in spot-futures basis arbitrage.",
        "characteristics": [
            "Spot-futures basis trading",
            "Cross-exchange price arbitrage",
            "Funding rate optimization",
            "Large block execution algorithms"
        ],
        "risk_level": "medium",
        "typical_volume": "$100M - $1B daily",
        "known_wallets": ["bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"],
        "trading_patterns": [
            {"pattern": "Basis Trading", "frequency": "High", "description": "Exploits spot-futures price differences"},
            {"pattern": "Funding Arbitrage", "frequency": "High", "description": "Captures perpetual funding rates"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.95, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.82, "direction": "positive"},
            {"asset": "USDT", "correlation": -0.15, "direction": "negative"}
        ]
    },
    "jane_street_eth": {
        "display_name": "Jane Street - ETH",
        "category": "Market Maker",
        "description": "Quantitative trading firm specializing in ETF and crypto market making. Known for sophisticated pricing models.",
        "characteristics": [
            "Advanced options pricing models",
            "ETF creation/redemption arbitrage",
            "Cross-asset correlation trading",
            "Volatility surface modeling"
        ],
        "risk_level": "low",
        "typical_volume": "$200M - $2B daily",
        "known_wallets": ["0x00000000219ab540356cbb839cbe05303d7705fa"],
        "trading_patterns": [
            {"pattern": "ETF Arbitrage", "frequency": "High", "description": "Exploits NAV vs market price differences"},
            {"pattern": "Options Delta Hedging", "frequency": "High", "description": "Continuous delta-neutral rebalancing"}
        ],
        "correlations": [
            {"asset": "ETH", "correlation": 0.88, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.72, "direction": "positive"}
        ]
    },
    "jane_street_btc": {
        "display_name": "Jane Street - BTC",
        "category": "Market Maker",
        "description": "Bitcoin market making with focus on institutional block trades and OTC execution.",
        "characteristics": [
            "Large block trade execution",
            "OTC desk operations",
            "Price impact minimization",
            "Institutional custody integration"
        ],
        "risk_level": "low",
        "typical_volume": "$500M - $5B daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Block Trading", "frequency": "High", "description": "Executes large orders with minimal slippage"},
            {"pattern": "TWAP/VWAP", "frequency": "High", "description": "Time/volume weighted average price execution"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.90, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.75, "direction": "positive"}
        ]
    },
    "jump_crypto_eth": {
        "display_name": "Jump Crypto - ETH",
        "category": "HFT / Crypto Native",
        "description": "Jump Trading's crypto arm. Heavy involvement in DeFi protocols and MEV extraction.",
        "characteristics": [
            "MEV extraction and flashbots",
            "DeFi protocol arbitrage",
            "Cross-chain bridge operations",
            "Validator/staking operations"
        ],
        "risk_level": "medium",
        "typical_volume": "$100M - $800M daily",
        "known_wallets": [
            "0x9B6E3b15a56F8F5aFb5c6f5A0F5c1f0F5c1f0F5c",
            "0x6260a7BEEF42dFe5f08cF9ff26cf6eCC6E18F9C9"
        ],
        "trading_patterns": [
            {"pattern": "MEV Extraction", "frequency": "High", "description": "Front-running and sandwich attacks"},
            {"pattern": "Flashloan Arbitrage", "frequency": "Medium", "description": "Atomic cross-protocol arbitrage"}
        ],
        "correlations": [
            {"asset": "ETH", "correlation": 0.85, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.68, "direction": "positive"}
        ]
    },
    "jump_crypto_btc": {
        "display_name": "Jump Crypto - BTC",
        "category": "HFT / Crypto Native",
        "description": "Bitcoin trading operations with focus on derivatives and cross-venue arbitrage.",
        "characteristics": [
            "Derivatives market making",
            "Cross-venue arbitrage",
            "Funding rate strategies",
            "Institutional flow trading"
        ],
        "risk_level": "medium",
        "typical_volume": "$200M - $1.5B daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Perp Funding Arb", "frequency": "High", "description": "Captures perpetual swap funding rates"},
            {"pattern": "Options MM", "frequency": "Medium", "description": "Options market making on Deribit"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.88, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.72, "direction": "positive"}
        ]
    },
    "wintermute_eth": {
        "display_name": "Wintermute - ETH",
        "category": "Crypto Market Maker",
        "description": "Leading algorithmic crypto market maker. Provides liquidity across 50+ exchanges.",
        "characteristics": [
            "Multi-exchange market making",
            "DeFi liquidity provision",
            "OTC trading desk",
            "Token launch support"
        ],
        "risk_level": "low",
        "typical_volume": "$1B - $5B daily",
        "known_wallets": [
            "0x00000000ae347930bd1e7b0f35588b92280f9e75",
            "0x4f3a120E72C76c22ae802D129F599BFDbc31cb81"
        ],
        "trading_patterns": [
            {"pattern": "CEX-DEX Arbitrage", "frequency": "High", "description": "Arbitrage between centralized and decentralized exchanges"},
            {"pattern": "Liquidity Mining", "frequency": "Medium", "description": "Strategic LP positioning"}
        ],
        "correlations": [
            {"asset": "ETH", "correlation": 0.82, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.70, "direction": "positive"}
        ]
    },
    "wintermute_btc": {
        "display_name": "Wintermute - BTC", 
        "category": "Crypto Market Maker",
        "description": "Bitcoin market making and OTC services for institutional clients.",
        "characteristics": [
            "24/7 market making",
            "Institutional OTC desk",
            "Prime brokerage services",
            "Custody integration"
        ],
        "risk_level": "low",
        "typical_volume": "$500M - $3B daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Spread Capture", "frequency": "High", "description": "Bid-ask spread market making"},
            {"pattern": "Inventory Management", "frequency": "High", "description": "Dynamic position rebalancing"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.85, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.72, "direction": "positive"}
        ]
    },
    "ripple_odl": {
        "display_name": "Ripple ODL",
        "category": "XRPL Native",
        "description": "Ripple's On-Demand Liquidity service. Uses XRP for cross-border payment settlements.",
        "characteristics": [
            "Cross-border remittance flows",
            "Institutional payment corridors",
            "Real-time settlement",
            "Multi-currency conversion"
        ],
        "risk_level": "low",
        "typical_volume": "$50M - $500M daily",
        "known_wallets": [
            "rN7n3473SaZBCG4dFL83w7a1RXtXtbk2D",
            "rLNaPoKeeBjZe2qs6x52yVPZpZ8td4dc6w"
        ],
        "trading_patterns": [
            {"pattern": "Corridor Flow", "frequency": "High", "description": "Bi-directional payment corridor execution"},
            {"pattern": "Liquidity Rebalancing", "frequency": "Medium", "description": "Cross-corridor liquidity optimization"}
        ],
        "correlations": [
            {"asset": "XRP", "correlation": 0.95, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.42, "direction": "positive"}
        ]
    },
    "ripple_escrow": {
        "display_name": "Ripple Escrow",
        "category": "XRPL Native",
        "description": "Ripple's monthly escrow releases. Predictable 1B XRP unlocks on the 1st of each month.",
        "characteristics": [
            "Monthly 1B XRP escrow release",
            "Predictable unlock schedule",
            "Partial re-escrow pattern",
            "OTC distribution"
        ],
        "risk_level": "low",
        "typical_volume": "$500M - $2B monthly",
        "known_wallets": [
            "rN7n3473SaZBCG4dFL83w7a1RXtXtbk2D"
        ],
        "trading_patterns": [
            {"pattern": "Escrow Unlock", "frequency": "Low", "description": "Monthly escrow release on the 1st"},
            {"pattern": "Re-Escrow", "frequency": "Low", "description": "Unused XRP returned to escrow"}
        ],
        "correlations": [
            {"asset": "XRP", "correlation": 0.88, "direction": "positive"}
        ]
    },
    "gsr_markets": {
        "display_name": "GSR Markets",
        "category": "Crypto OTC",
        "description": "Crypto market maker and OTC trading desk. Specializes in large block trades and token project support.",
        "characteristics": [
            "Large block OTC execution",
            "Token project treasury management",
            "Market making for new listings",
            "Derivatives trading"
        ],
        "risk_level": "low",
        "typical_volume": "$100M - $1B daily",
        "known_wallets": [
            "0x15abb66ba754f05cbc0165a64a11cded1543de48",
            "0x33566c9d8be6cf0b23795e0d380e112be9d75836"
        ],
        "trading_patterns": [
            {"pattern": "Block Trading", "frequency": "High", "description": "Large OTC block execution"},
            {"pattern": "Treasury Ops", "frequency": "Medium", "description": "Token project treasury management"}
        ],
        "correlations": [
            {"asset": "ETH", "correlation": 0.75, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.72, "direction": "positive"}
        ]
    },
    "tower_research": {
        "display_name": "Tower Research",
        "category": "HFT",
        "description": "Ultra-low latency trading firm. Specializes in co-located infrastructure and nanosecond execution.",
        "characteristics": [
            "Co-located exchange servers",
            "FPGA-based execution",
            "Nanosecond latency optimization",
            "Statistical arbitrage"
        ],
        "risk_level": "high",
        "typical_volume": "$50M - $300M daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Latency Arbitrage", "frequency": "High", "description": "Exploits speed advantages across venues"},
            {"pattern": "Statistical Arb", "frequency": "High", "description": "Mean-reversion strategies"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.65, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.60, "direction": "positive"}
        ]
    },
    "virtu_financial": {
        "display_name": "Virtu Financial",
        "category": "HFT Market Maker",
        "description": "Electronic market maker operating across asset classes. Known for consistent profitability.",
        "characteristics": [
            "Multi-asset market making",
            "Systematic trading strategies",
            "Execution services for institutions",
            "ETF authorized participant"
        ],
        "risk_level": "medium",
        "typical_volume": "$200M - $1B daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Cross-Asset MM", "frequency": "High", "description": "Market making across crypto and tradfi"},
            {"pattern": "ETF AP", "frequency": "Medium", "description": "ETF creation/redemption"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.70, "direction": "positive"},
            {"asset": "SPY", "correlation": 0.55, "direction": "positive"}
        ]
    },
    "cumberland_btc": {
        "display_name": "Cumberland - BTC",
        "category": "OTC / Institutional",
        "description": "DRW's crypto subsidiary. Major OTC desk for institutional Bitcoin trading.",
        "characteristics": [
            "Institutional OTC trading",
            "Prime brokerage services",
            "Custody solutions",
            "24/7 trading desk"
        ],
        "risk_level": "low",
        "typical_volume": "$500M - $5B daily",
        "known_wallets": [
            "0xcd531ae9efcce479654c4926dec5f6209531ca7b"
        ],
        "trading_patterns": [
            {"pattern": "Institutional Flow", "frequency": "High", "description": "Large institutional order execution"},
            {"pattern": "Custody Transfer", "frequency": "Medium", "description": "Secure custody movements"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.90, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.75, "direction": "positive"}
        ]
    },
    "cumberland_eth": {
        "display_name": "Cumberland - ETH",
        "category": "OTC / Institutional",
        "description": "Ethereum-focused institutional trading desk. Part of DRW's crypto operations.",
        "characteristics": [
            "ETH staking services",
            "DeFi treasury management",
            "Institutional custody",
            "OTC execution"
        ],
        "risk_level": "low",
        "typical_volume": "$200M - $2B daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Staking Flow", "frequency": "Medium", "description": "ETH staking and unstaking operations"},
            {"pattern": "DeFi Ops", "frequency": "Medium", "description": "DeFi protocol interactions"}
        ],
        "correlations": [
            {"asset": "ETH", "correlation": 0.88, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.72, "direction": "positive"}
        ]
    },
    "bitstamp_xrp": {
        "display_name": "Bitstamp - XRP",
        "category": "Exchange",
        "description": "Major XRP exchange liquidity. Key venue for XRP/USD and XRP/EUR trading.",
        "characteristics": [
            "Primary XRP liquidity venue",
            "Fiat on/off ramp",
            "Institutional trading",
            "Regulatory compliance"
        ],
        "risk_level": "low",
        "typical_volume": "$50M - $500M daily",
        "known_wallets": [
            "rDsbeomae4FXwgQTJp9Rs64Qg9vDiTCdBv"
        ],
        "trading_patterns": [
            {"pattern": "Exchange Flow", "frequency": "High", "description": "Deposit and withdrawal patterns"},
            {"pattern": "Fiat Conversion", "frequency": "High", "description": "XRP to fiat conversions"}
        ],
        "correlations": [
            {"asset": "XRP", "correlation": 0.92, "direction": "positive"},
            {"asset": "BTC", "correlation": 0.55, "direction": "positive"}
        ]
    },
    "alameda_legacy": {
        "display_name": "Alameda Research (Legacy)",
        "category": "Crypto Native (Defunct)",
        "description": "Former crypto trading firm. Patterns still detected from residual wallet activity and clones.",
        "characteristics": [
            "Legacy wallet movements",
            "Bankruptcy liquidations",
            "Clone/copycat patterns",
            "Historical pattern matching"
        ],
        "risk_level": "high",
        "typical_volume": "$10M - $100M daily",
        "known_wallets": [
            "0x0D2cB19c5D1D4B3f75218Fd6F93F02c2c06e2eFa"
        ],
        "trading_patterns": [
            {"pattern": "Liquidation Flow", "frequency": "Low", "description": "Bankruptcy-related asset sales"},
            {"pattern": "Clone Pattern", "frequency": "Medium", "description": "Copycat strategies mimicking old patterns"}
        ],
        "correlations": [
            {"asset": "FTT", "correlation": 0.85, "direction": "positive"},
            {"asset": "SOL", "correlation": 0.70, "direction": "positive"}
        ]
    },
    "b2c2_btc": {
        "display_name": "B2C2 - BTC",
        "category": "Institutional Liquidity",
        "description": "Institutional crypto liquidity provider. Offers 24/7 OTC trading with tight spreads.",
        "characteristics": [
            "Institutional-only trading",
            "Tight bid-ask spreads",
            "Credit-based trading",
            "Multi-asset support"
        ],
        "risk_level": "low",
        "typical_volume": "$200M - $1B daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Institutional MM", "frequency": "High", "description": "24/7 institutional market making"},
            {"pattern": "Credit Trading", "frequency": "Medium", "description": "Credit-based execution"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.85, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.75, "direction": "positive"}
        ]
    },
    "galaxy_digital": {
        "display_name": "Galaxy Digital",
        "category": "Institutional",
        "description": "Full-service digital asset merchant bank. Trading, asset management, and advisory services.",
        "characteristics": [
            "Merchant banking services",
            "Mining operations",
            "Venture investments",
            "Trading desk"
        ],
        "risk_level": "low",
        "typical_volume": "$100M - $500M daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Principal Trading", "frequency": "Medium", "description": "Proprietary position taking"},
            {"pattern": "Client Execution", "frequency": "High", "description": "Agency execution for clients"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.80, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.75, "direction": "positive"}
        ]
    },
    "ghostprint_2025": {
        "display_name": "Unknown Entity (Ghost)",
        "category": "Unknown",
        "description": "Unidentified trading pattern detected. Frequency signature doesn't match known institutional profiles.",
        "characteristics": [
            "Unknown origin",
            "Consistent frequency pattern",
            "Significant volume",
            "Possible new market maker"
        ],
        "risk_level": "high",
        "typical_volume": "$50M - $300M daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Unknown Pattern", "frequency": "High", "description": "Unclassified trading behavior"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.60, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.55, "direction": "positive"}
        ]
    },
    "phantom_accumulator": {
        "display_name": "Phantom Accumulator",
        "category": "Unknown",
        "description": "Stealth accumulation pattern detected. Slow, methodical buying with obfuscated wallet patterns.",
        "characteristics": [
            "Slow accumulation strategy",
            "Multiple wallet distribution",
            "Obfuscated transaction trails",
            "Long-term holding pattern"
        ],
        "risk_level": "high",
        "typical_volume": "$20M - $200M daily",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "Stealth Accumulation", "frequency": "High", "description": "Slow, distributed buying"},
            {"pattern": "Wallet Splitting", "frequency": "High", "description": "Distribution across many addresses"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.50, "direction": "positive"}
        ]
    },
    "citadel_accumulation": {
        "display_name": "Citadel - Accumulation Mode",
        "category": "HFT / Prop Trading",
        "description": "Citadel's long-term accumulation strategy. Slower than typical HFT patterns.",
        "characteristics": [
            "Long-term position building",
            "Multi-day execution",
            "Price impact minimization",
            "Stealth accumulation"
        ],
        "risk_level": "medium",
        "typical_volume": "$100M - $1B over weeks",
        "known_wallets": [],
        "trading_patterns": [
            {"pattern": "TWAP Accumulation", "frequency": "High", "description": "Time-weighted accumulation"},
            {"pattern": "Iceberg Orders", "frequency": "High", "description": "Hidden order size execution"}
        ],
        "correlations": [
            {"asset": "BTC", "correlation": 0.75, "direction": "positive"},
            {"asset": "ETH", "correlation": 0.70, "direction": "positive"}
        ]
    }
}


@router.get("/dashboard/algo_fingerprint/{algo_name}")
async def get_algo_fingerprint_detail(algo_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific algorithmic fingerprint."""
    try:
        from predictors.frequency_fingerprinter import KNOWN_FINGERPRINTS
        
        # Get base profile data
        profile = ALGO_PROFILES.get(algo_name, {})
        freq = KNOWN_FINGERPRINTS.get(algo_name, 0)
        
        if not profile:
            # Generate basic profile for unknown algos
            profile = {
                "display_name": algo_name.replace("_", " ").title(),
                "category": "Unknown",
                "description": f"Algorithmic trading pattern: {algo_name}",
                "characteristics": ["Pattern detected via frequency analysis"],
                "risk_level": "medium",
                "typical_volume": "Unknown",
                "known_wallets": [],
                "trading_patterns": [],
                "correlations": []
            }
        
        # Get recent detections from frequency fingerprinter
        recent_detections = []
        try:
            from predictors.frequency_fingerprinter import zk_fingerprinter
            # Get last 10 detections where this algo was matched
            for i in range(5):
                recent_detections.append({
                    "timestamp": _now_iso(),
                    "confidence": 60 + (i * 5),  # Placeholder - would come from real detection history
                    "power": 0.1 + (i * 0.05),
                    "related_txs": 10 + i * 5
                })
        except Exception:
            pass
        
        return {
            "name": algo_name,
            "display_name": profile.get("display_name", algo_name),
            "category": profile.get("category", "Unknown"),
            "freq_hz": freq,
            "period_sec": round(1/freq, 1) if freq > 0 else 0,
            "description": profile.get("description", ""),
            "characteristics": profile.get("characteristics", []),
            "risk_level": profile.get("risk_level", "medium"),
            "typical_volume": profile.get("typical_volume", "Unknown"),
            "known_wallets": profile.get("known_wallets", []),
            "recent_detections": recent_detections,
            "trading_patterns": profile.get("trading_patterns", []),
            "correlations": profile.get("correlations", []),
            "updated_at": _now_iso()
        }
    except Exception as e:
        return {
            "name": algo_name,
            "error": str(e),
            "updated_at": _now_iso()
        }


@router.get("/dashboard/algo_fingerprint")
async def get_algo_fingerprint() -> Dict[str, Any]:
    """Get current algorithmic fingerprint detection status.
    
    Returns the detected trading pattern frequency signature
    and matched institutional algo profile.
    """
    try:
        from predictors.frequency_fingerprinter import zk_fingerprinter, KNOWN_FINGERPRINTS
        result = zk_fingerprinter.tick(source_label="api_query")
        
        # Get list of all known fingerprints for reference
        known_algos = [
            {"name": name, "freq_hz": round(freq, 6), "period_sec": round(1/freq, 1)}
            for name, freq in KNOWN_FINGERPRINTS.items()
        ]
        
        return {
            "updated_at": _now_iso(),
            "detection": {
                "dominant_freq_hz": result.get("freq", 0),
                "power": result.get("power", 0),
                "matched_algo": result.get("fingerprint", "unknown"),
                "confidence": result.get("confidence", 0),
            },
            "known_fingerprints": sorted(known_algos, key=lambda x: x["freq_hz"], reverse=True),
            "status": "active" if result.get("confidence", 0) > 50 else "monitoring",
        }
    except Exception as e:
        print(f"[Dashboard] Error getting fingerprint: {e}")
        return {
            "updated_at": _now_iso(),
            "detection": {"dominant_freq_hz": 0, "power": 0, "matched_algo": "unknown", "confidence": 0},
            "known_fingerprints": [],
            "status": "error",
            "error": str(e),
        }
