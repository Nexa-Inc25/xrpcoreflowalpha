import asyncio
import math
from typing import Dict, List, Optional, Tuple

import aiohttp

from app.config import POLYGON_API_KEY
from predictors.frequency_fingerprinter import FrequencyFingerprinter
from predictors.wavelet_urgency import update_wavelet_urgency


_TICKER_MAP: Dict[str, str] = {
    # Popular options contracts on Polygon (SPY for S&P 500, QQQ for Nasdaq)
    # These use the most liquid at-the-money options
    "ES": "O:SPY",  # SPY options instead of ES futures
    "NQ": "O:QQQ",  # QQQ options instead of NQ futures
}


def _extract_trade_from_v3(data: Dict) -> Tuple[float, float, float]:
    try:
        results = data.get("results") or []
        if not results:
            return 0.0, 0.0, 0.0
        t = results[0]
        price = float(t.get("price") or t.get("p") or 0.0)
        size = float(t.get("size") or t.get("s") or 0.0)
        ts_raw = float(t.get("sip_timestamp") or t.get("timestamp") or t.get("t") or 0.0)
        return price, size, ts_raw
    except Exception:
        return 0.0, 0.0, 0.0


def _extract_trade_from_v2(data: Dict) -> Tuple[float, float, float]:
    try:
        last = data.get("results") or data.get("last") or {}
        # v2 can return in different shapes; try common fields
        price = float(last.get("price") or last.get("P") or last.get("p") or 0.0)
        size = float(last.get("size") or last.get("S") or last.get("s") or 0.0)
        ts_raw = float(last.get("sip_timestamp") or last.get("t") or last.get("timestamp") or 0.0)
        return price, size, ts_raw
    except Exception:
        return 0.0, 0.0, 0.0


def _ns_or_ms_to_seconds(ts_raw: float) -> float:
    if ts_raw <= 0:
        return 0.0
    if ts_raw > 1e14:
        return ts_raw / 1e9
    if ts_raw > 1e11:
        return ts_raw / 1e3
    return ts_raw


async def _poll_ticker(ticker: str, label: str, fp: FrequencyFingerprinter) -> None:
    if not POLYGON_API_KEY:
        return
    timeout = aiohttp.ClientTimeout(total=10)
    v3_url = f"https://api.polygon.io/v3/trades/{ticker}?order=desc&limit=1&apiKey={POLYGON_API_KEY}"
    v2_url = f"https://api.polygon.io/v2/last/trade/{ticker}?apiKey={POLYGON_API_KEY}"
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            handled = False
            try:
                # Try v3 first
                async with session.get(v3_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        price, size, ts_raw = _extract_trade_from_v3(data)
                        ts = _ns_or_ms_to_seconds(ts_raw)
                        notional = abs(price * size)
                        if ts > 0 and notional > 0 and math.isfinite(notional):
                            fp.add_event(timestamp=ts, value=notional)
                            fp.tick(source_label=label)
                            handled = True
            except Exception:
                pass
            if not handled:
                try:
                    async with session.get(v2_url) as resp2:
                        if resp2.status == 200:
                            data2 = await resp2.json()
                            price, size, ts_raw = _extract_trade_from_v2(data2)
                            ts = _ns_or_ms_to_seconds(ts_raw)
                            notional = abs(price * size)
                            if ts > 0 and notional > 0 and math.isfinite(notional):
                                fp.add_event(timestamp=ts, value=notional)
                                fp.tick(source_label=label)
                                try:
                                    update_wavelet_urgency(label, ts, notional)
                                except Exception:
                                    pass
                                handled = True
                except Exception:
                    pass
            # modest pace to respect rate limits
            await asyncio.sleep(1.0 if handled else 1.5)


async def start_polygon_macro_tracker(symbols: Optional[List[str]] = None) -> None:
    if not POLYGON_API_KEY:
        return
    syms = symbols or ["ES", "NQ"]
    tasks: List[asyncio.Task] = []
    for s in syms:
        tkr = _TICKER_MAP.get(s.upper(), s)
        label = "macro_es" if s.upper() == "ES" else ("macro_nq" if s.upper() == "NQ" else s.lower())
        fp = FrequencyFingerprinter(window_seconds=300, sample_rate_hz=1.0)
        tasks.append(asyncio.create_task(_poll_ticker(tkr, label, fp)))
    if tasks:
        await asyncio.gather(*tasks)
