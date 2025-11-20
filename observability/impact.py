import asyncio
import time
from statistics import mean
from typing import Dict, List, Tuple, Optional

import aiohttp

BINANCE_DEPTH_CACHE: Dict[str, Dict[str, object]] = {
    "ETHUSDT": {"bids": [], "asks": [], "mid": 0.0, "ts": 0.0},
    "BTCUSDT": {"bids": [], "asks": [], "mid": 0.0, "ts": 0.0},
}

DEPTH_CACHE_TTL = 8

async def start_binance_depth_worker(symbols: Optional[List[str]] = None) -> None:
    syms = symbols or ["ETHUSDT", "BTCUSDT"]
    async with aiohttp.ClientSession() as session:
        while True:
            for symbol in syms:
                try:
                    async with session.get(
                        f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit=1000",
                        timeout=10,
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            bids = [[float(p), float(q)] for p, q in data.get("bids", [])]
                            asks = [[float(p), float(q)] for p, q in data.get("asks", [])]
                            if bids and asks:
                                mid = (asks[0][0] + bids[0][0]) / 2.0
                            else:
                                mid = 0.0
                            BINANCE_DEPTH_CACHE[symbol] = {
                                "bids": bids,
                                "asks": asks,
                                "mid": mid,
                                "ts": time.time(),
                            }
                except Exception:
                    pass
            await asyncio.sleep(DEPTH_CACHE_TTL)


def get_cached_depth(symbol: str) -> Tuple[List[List[float]], List[List[float]], float, float]:
    d = BINANCE_DEPTH_CACHE.get(symbol) or {}
    bids = d.get("bids") or []
    asks = d.get("asks") or []
    mid = float(d.get("mid") or 0.0)
    ts = float(d.get("ts") or 0.0)
    return bids, asks, mid, ts


def _walk_depth(depth: List[List[float]], volume_usd: float) -> Tuple[float, float]:
    cum_usd = 0.0
    weighted_total = 0.0
    for price, qty in depth:
        usd_here = price * qty
        if cum_usd + usd_here >= volume_usd:
            frac = max(0.0, (volume_usd - cum_usd) / usd_here)
            weighted_total += price * qty * frac
            cum_usd = volume_usd
            break
        weighted_total += price * qty
        cum_usd += usd_here
    return cum_usd, weighted_total


def calculate_impact(depth: List[List[float]], side: str, volume_usd: float, mid_price: float) -> Dict[str, float]:
    filled_usd, weighted_total = _walk_depth(depth, volume_usd)
    avg_price = mid_price if filled_usd <= 0 else weighted_total / (filled_usd / mid_price)
    if side == "asks":
        impact_pct = (avg_price / mid_price - 1.0) * 100.0
    else:
        impact_pct = (1.0 - avg_price / mid_price) * 100.0
    out: Dict[str, float] = {"impact_pct": float(impact_pct), "max_filled_usd": float(filled_usd)}
    for t in (0.5, 1.0, 2.0):
        target = mid_price * (1 + t / 100.0) if side == "asks" else mid_price * (1 - t / 100.0)
        vol = 0.0
        for p, q in depth:
            if side == "asks" and p > target:
                break
            if side == "bids" and p < target:
                break
            vol += p * q
        out[f"{t}%_usd"] = float(vol)
    return out
