import asyncio
import math
import time
from typing import Dict, List, Optional, Tuple

import aiohttp

from app.config import ALPHA_VANTAGE_API_KEY
from predictors.frequency_fingerprinter import FrequencyFingerprinter


_SYMBOL_MAP: Dict[str, str] = {
    # Proxies for ES/NQ using highly liquid ETFs
    "ES": "SPY",
    "NQ": "QQQ",
}


def _parse_series(data: Dict) -> List[Tuple[str, float, float]]:
    try:
        # Alpha Vantage shape: { "Time Series (1min)": { "2025-11-24 13:55:00": {"1. open": "...", "5. volume": "..."}, ... } }
        for k in list(data.keys()):
            if "Time Series" in k:
                series = data[k]
                break
        else:
            return []
        items = []
        for ts_str, bar in series.items():
            try:
                close = float(bar.get("4. close") or bar.get("4. Close") or 0.0)
                vol = float(bar.get("5. volume") or bar.get("5. Volume") or 0.0)
                items.append((ts_str, close, vol))
            except Exception:
                continue
        # sort ascending by time string
        items.sort(key=lambda x: x[0])
        return items
    except Exception:
        return []


async def _seed_with_history(symbol: str, session: aiohttp.ClientSession, fp: FrequencyFingerprinter, label: str) -> Tuple[str, float]:
    url = (
        "https://www.alphavantage.co/query"
        f"?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=1min&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}"
    )
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                return "", 0.0
            data = await resp.json()
    except Exception:
        return "", 0.0
    series = _parse_series(data)
    if not series:
        return "", 0.0
    # Use last up to 120 bars for a decent seed window
    tail = series[-120:]
    now = time.time()
    # Backfill as evenly spaced 60s steps ending at now
    start_idx = max(0, len(tail) - 120)
    base_epoch = now - (len(tail) * 60.0)
    for i, (_, close, vol) in enumerate(tail):
        notional = abs(close * vol)
        if notional > 0 and math.isfinite(notional):
            ts = base_epoch + i * 60.0
            fp.add_event(timestamp=ts, value=notional)
    fp.tick(source_label=label)
    last_ts_str = tail[-1][0]
    last_epoch = now
    return last_ts_str, last_epoch


async def _poll_symbol(symbol: str, label: str, fp: FrequencyFingerprinter) -> None:
    if not ALPHA_VANTAGE_API_KEY:
        print(f"[AlphaMacro] ERROR: ALPHA_VANTAGE_API_KEY required for {symbol} data!")
        # Use Yahoo Finance as fallback
        from predictors.yahoo_macro_tracker import _poll_ticker
        await _poll_ticker(symbol, label, fp)
        return
    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        last_ts_str = ""
        last_epoch = 0.0
        # Seed window
        last_ts_str, last_epoch = await _seed_with_history(symbol, session, fp, label)
        if not last_ts_str:
            # no seed; still attempt loop
            last_epoch = time.time()
        while True:
            try:
                url = (
                    "https://www.alphavantage.co/query"
                    f"?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=1min&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}"
                )
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await asyncio.sleep(60.0)
                        continue
                    data = await resp.json()
                series = _parse_series(data)
                if not series:
                    await asyncio.sleep(60.0)
                    continue
                # find new bars after last_ts_str
                new_items = [x for x in series if x[0] > last_ts_str] if last_ts_str else series[-1:]
                if new_items:
                    # add in chronological order
                    for _, close, vol in new_items:
                        notional = abs(close * vol)
                        if notional > 0 and math.isfinite(notional):
                            last_epoch = last_epoch + 60.0 if last_epoch > 0 else time.time()
                            fp.add_event(timestamp=last_epoch, value=notional)
                            fp.tick(source_label=label)
                    last_ts_str = new_items[-1][0]
                # Respect free tier limits: 2 symbols -> 2 req/min
                await asyncio.sleep(60.0)
            except Exception:
                # brief backoff on errors
                await asyncio.sleep(60.0)


async def start_alpha_macro_tracker(symbols: Optional[List[str]] = None) -> None:
    if not ALPHA_VANTAGE_API_KEY:
        print("[AlphaMacro] ERROR: ALPHA_VANTAGE_API_KEY required! Using Yahoo fallback...")
        from predictors.yahoo_macro_tracker import start_yahoo_macro_tracker
        await start_yahoo_macro_tracker(symbols)
        return
    syms = symbols or ["ES", "NQ"]
    tasks: List[asyncio.Task] = []
    for s in syms:
        ticker = _SYMBOL_MAP.get(s.upper(), s)
        label = "macro_es" if s.upper() == "ES" else ("macro_nq" if s.upper() == "NQ" else s.lower())
        fp = FrequencyFingerprinter(window_seconds=3600, sample_rate_hz=1.0 / 60.0)  # 1 sample per minute
        tasks.append(asyncio.create_task(_poll_symbol(ticker, label, fp)))
    if tasks:
        await asyncio.gather(*tasks)
