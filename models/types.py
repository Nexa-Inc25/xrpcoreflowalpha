from dataclasses import dataclass
from typing import Optional, Union

@dataclass
class XRPFlow:
    amount_xrp: float
    usd_value: float
    tx_hash: str
    timestamp: int
    destination: str
    source: str

@dataclass
class ZKFlow:
    tx_hash: str
    gas_used: int
    to_address: Optional[str]
    timestamp: int
    network: str

@dataclass
class EquityDarkPool:
    symbol: str
    shares: int
    price: float
    venue: str
    timestamp: int

@dataclass
class CrossMarketSignal:
    id: str
    equity_ticker: str
    crypto_asset: str
    confidence: int
    forecast: str
    equity_trade: EquityDarkPool
    crypto_flow: Union[XRPFlow, ZKFlow]
