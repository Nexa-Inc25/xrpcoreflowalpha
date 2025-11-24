import asyncio
import math
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.config import DATABENTO_API_KEY
from predictors.frequency_fingerprinter import FrequencyFingerprinter

try:
    import databento as db  # type: ignore
except Exception:  # pragma: no cover
    db = None  # type: ignore


_PARENT_SYMBOLS = {
    "ES": ("ES.FUT", 50.0, "macro_es"),
    "NQ": ("NQ.FUT", 20.0, "macro_nq"),
}


async def _poll_symbol_parent(symbol_key: str, fp: FrequencyFingerprinter) -> None:
    if not DATABENTO_API_KEY or db is None:
        return
    parent, multiplier, label = _PARENT_SYMBOLS.get(symbol_key.upper(), (symbol_key, 1.0, symbol_key.lower()))
    # Historical client for near-real-time polling. Live client requires long-lived socket; we keep this simple.
    client = db.Historical(DATABENTO_API_KEY)
    poll_seconds = 30
    while True:
        try:
            # Pull last 2 minutes of trades and aggregate notional
            end = datetime.now(tz=timezone.utc)
            start = end - timedelta(minutes=2)
            data = await asyncio.to_thread(
                client.timeseries.get_range,
                dataset="GLBX.MDP3",
                schema="trades",
                symbols=parent,
                stype_in="parent",
                start=start.isoformat(timespec="seconds"),
                end=end.isoformat(timespec="seconds"),
                limit=5000,
            )
            notional = 0.0
            try:
                # Prefer DataFrame if available
                df = data.to_df()  # type: ignore[attr-defined]
                if df is not None and not df.empty:
                    # Support common column names across versions
                    px = None
                    sz = None
                    for cand in ("price", "px"):
                        if cand in df.columns:
                            px = df[cand].astype(float)
                            break
                    for cand in ("size", "sz", "qty"):
                        if cand in df.columns:
                            sz = df[cand].astype(float)
                            break
                    if px is not None and sz is not None:
                        notional = float((px * sz).abs().sum()) * float(multiplier)
            except Exception:
                # Fallback to replay iteration if DataFrame export not available
                try:
                    acc = 0.0
                    def _accumulate(evt):  # type: ignore
                        nonlocal acc
                        # best-effort: event may expose .price/.size or .px/.sz
                        p = 0.0
                        s = 0.0
                        for name in ("price", "px"):
                            if hasattr(evt, name):
                                try:
                                    p = float(getattr(evt, name) or 0.0)
                                    break
                                except Exception:
                                    pass
                        for name in ("size", "sz", "qty"):
                            if hasattr(evt, name):
                                try:
                                    s = float(getattr(evt, name) or 0.0)
                                    break
                                except Exception:
                                    pass
                        if p > 0 and s > 0 and math.isfinite(p) and math.isfinite(s):
                            acc += abs(p * s)
                    data.replay(callback=_accumulate)  # type: ignore[attr-defined]
                    notional = float(acc) * float(multiplier)
                except Exception:
                    notional = 0.0
            if notional > 0 and math.isfinite(notional):
                ts = end.timestamp()
                fp.add_event(timestamp=ts, value=notional)
                fp.tick(source_label=label)
        except Exception:
            # soft backoff
            await asyncio.sleep(min(90, poll_seconds * 2))
        await asyncio.sleep(poll_seconds)


async def start_databento_macro_tracker(symbols: Optional[List[str]] = None) -> None:
    if not DATABENTO_API_KEY or db is None:
        return
    syms = symbols or ["ES", "NQ"]
    tasks: List[asyncio.Task] = []
    for s in syms:
        fp = FrequencyFingerprinter(window_seconds=3600, sample_rate_hz=1.0 / 60.0)
        tasks.append(asyncio.create_task(_poll_symbol_parent(s, fp)))
    if tasks:
        await asyncio.gather(*tasks)
