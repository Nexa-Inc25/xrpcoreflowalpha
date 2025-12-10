import asyncio
import math
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from predictors.frequency_fingerprinter import FrequencyFingerprinter


_TICKERS: Dict[str, Dict[str, object]] = {
    "ES": {"ticker": "SPY", "multiplier": 1.0, "label": "macro_es"},  # SPY ETF (S&P 500)
    "NQ": {"ticker": "QQQ", "multiplier": 1.0, "label": "macro_nq"},   # QQQ ETF (Nasdaq 100)
}


def _row_epoch(ts: pd.Timestamp) -> float:
    try:
        if ts is None:
            return 0.0
        if ts.tzinfo is not None:
            ts = ts.tz_convert(None)
        return float(ts.to_pydatetime().timestamp())
    except Exception:
        try:
            return float(pd.Timestamp(ts).to_pydatetime().timestamp())
        except Exception:
            return 0.0


async def _seed(fp: FrequencyFingerprinter, ticker: str, multiplier: float, label: str) -> Optional[pd.Timestamp]:
    try:
        def _load():
            t = yf.Ticker(ticker)
            # Try different periods if 2d fails
            for period in ["2d", "1d", "5d"]:
                try:
                    df = t.history(period=period, interval="1m", auto_adjust=False, actions=False)
                    if df is not None and not df.empty:
                        return df
                except Exception:
                    continue
            return pd.DataFrame()  # Return empty if all fail

        df: pd.DataFrame = await asyncio.to_thread(_load)
        if df is None or df.empty:
            return None
        # keep last ~120 bars to seed ~2h window
        tail = df.tail(120)
        last_index: Optional[pd.Timestamp] = None
        for idx, row in tail.iterrows():
            close = float(row.get("Close", 0.0))
            vol = float(row.get("Volume", 0.0))
            notional = abs(close * vol * float(multiplier))
            if notional > 0 and math.isfinite(notional):
                ts = _row_epoch(idx)
                if ts > 0:
                    fp.add_event(timestamp=ts, value=notional)
                last_index = idx
        fp.tick(source_label=label)
        return last_index
    except Exception:
        return None


async def _poll_symbol(symbol: str, fp: FrequencyFingerprinter) -> None:
    meta = _TICKERS.get(symbol.upper()) or {"ticker": symbol, "multiplier": 1.0, "label": symbol.lower()}
    ticker = str(meta["ticker"])  # type: ignore
    mult = float(meta["multiplier"])  # type: ignore
    label = str(meta["label"])  # type: ignore

    last_idx: Optional[pd.Timestamp] = await _seed(fp, ticker, mult, label)
    # main loop
    while True:
        try:
            def _load_latest():
                t = yf.Ticker(ticker)
                # Try to get latest data with fallbacks
                for period in ["1d", "2d", "5d"]:
                    try:
                        df = t.history(period=period, interval="1m", auto_adjust=False, actions=False)
                        if df is not None and not df.empty:
                            return df
                    except Exception:
                        continue
                return pd.DataFrame()

            df: pd.DataFrame = await asyncio.to_thread(_load_latest)
            if df is None or df.empty:
                print(f"[Yahoo] No data for {ticker}, retrying in 60s")
                await asyncio.sleep(60.0)
                continue
            if last_idx is not None:
                df = df[df.index > last_idx]
            else:
                df = df.tail(1)
            if df is not None and not df.empty:
                for idx, row in df.iterrows():
                    close = float(row.get("Close", 0.0))
                    vol = float(row.get("Volume", 0.0))
                    notional = abs(close * vol * float(mult))
                    if notional > 0 and math.isfinite(notional):
                        ts = _row_epoch(idx)
                        if ts > 0:
                            fp.add_event(timestamp=ts, value=notional)
                            fp.tick(source_label=label)
                last_idx = df.index[-1]
        except Exception:
            # soft backoff on errors
            await asyncio.sleep(30.0)
        # Yahoo cadence: 1 minute
        await asyncio.sleep(60.0)


async def start_yahoo_macro_tracker(symbols: Optional[List[str]] = None) -> None:
    syms = symbols or ["ES", "NQ"]
    tasks: List[asyncio.Task] = []
    for s in syms:
        fp = FrequencyFingerprinter(window_seconds=3600, sample_rate_hz=1.0 / 60.0)
        tasks.append(asyncio.create_task(_poll_symbol(s, fp)))
    if tasks:
        await asyncio.gather(*tasks)
