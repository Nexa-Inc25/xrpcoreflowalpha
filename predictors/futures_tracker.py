import asyncio
import json
from typing import List

import websockets

from predictors.frequency_fingerprinter import FrequencyFingerprinter
from predictors.markov_predictor import zk_hmm


async def _stream_symbol(symbol: str, fp: FrequencyFingerprinter, threshold: float = 85.0) -> None:
    url = f"wss://fstream.binance.com/ws/{symbol}@aggTrade"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        ts = float(msg.get("T", 0)) / 1000.0
                        price = float(msg.get("p", 0.0))
                        qty = float(msg.get("q", 0.0))
                        usd = abs(qty) * price
                        if ts > 0 and usd > 0:
                            fp.add_event(timestamp=ts, value=usd)
                            res = fp.tick(source_label=f"futures_{symbol}")
                            conf = float(res.get("confidence") or 0.0)
                            freq = float(res.get("freq") or 0.0)
                            if conf >= threshold and freq > 0:
                                obs = 3 if freq >= 0.1 else 2
                                await zk_hmm.update(obs)
                    except Exception:
                        continue
        except Exception:
            await asyncio.sleep(2.0)


async def start_binance_futures_tracker(symbols: List[str] | None = None) -> None:
    syms = symbols or ["btcusdt", "ethusdt"]
    fps = {s: FrequencyFingerprinter(window_seconds=180, sample_rate_hz=1.0) for s in syms}
    tasks = [asyncio.create_task(_stream_symbol(s, fps[s])) for s in syms]
    await asyncio.gather(*tasks)
