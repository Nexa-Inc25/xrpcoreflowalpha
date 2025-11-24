import asyncio
import math
from typing import Dict, List

import aiohttp

from app.config import POLYGON_API_KEY
from predictors.frequency_fingerprinter import FrequencyFingerprinter


_TICKER_MAP: Dict[str, str] = {
    # Continuous futures tickers on Polygon
    "ES": "C:ES",
    "NQ": "C:NQ",
}


async def _poll_ticker(ticker: str, label: str, fp: FrequencyFingerprinter) -> None:
    if not POLYGON_API_KEY:
        return
    url = f"https://api.polygon.io/v3/trades/{ticker}?order=desc&limit=1&apiKey={POLYGON_API_KEY}"
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            try:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(1.0)
                        continue
                    data = await resp.json()
                    results = data.get("results") or []
                    if not results:
                        await asyncio.sleep(0.5)
                        continue
                    t = results[0]
                    # Polygon v3 trades fields: price, size, sip_timestamp (ns) — be defensive
                    price = float(t.get("price") or t.get("p") or 0.0)
                    size = float(t.get("size") or t.get("s") or 0.0)
                    ts_raw = float(t.get("sip_timestamp") or t.get("timestamp") or t.get("t") or 0.0)
                    # ns -> s, or ms -> s
                    ts = 0.0
                    if ts_raw > 0:
                        if ts_raw > 1e14:
                            ts = ts_raw / 1e9
                        elif ts_raw > 1e11:
                            ts = ts_raw / 1e3
                        else:
                            ts = ts_raw
                    notional = abs(price * size)
                    if ts > 0 and notional > 0 and math.isfinite(notional):
                        fp.add_event(timestamp=ts, value=notional)
                        fp.tick(source_label=label)
            except Exception:
                await asyncio.sleep(1.0)
            await asyncio.sleep(0.5)


async def start_polygon_macro_tracker(symbols: List[str] | None = None) -> None:
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
