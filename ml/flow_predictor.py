import asyncio
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from app.redis_utils import get_redis, REDIS_ENABLED
import redis as redis_sync

from app.config import (
    REDIS_URL,
    ML_CIRCUIT_BREAKER_FAILURES,
    ML_CIRCUIT_BREAKER_COOLDOWN_SECONDS,
    ML_CIRCUIT_BREAKER_ENABLED,
)
from utils.price import get_price_usd_at
from bus.signal_bus import fetch_recent_cross_signals

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
    try:
        import torch.backends.mkldnn as _mkldnn  # type: ignore
        _mkldnn.enabled = False
    except Exception:
        pass
except Exception:
    TORCH_AVAILABLE = False
    torch = None  # type: ignore
    nn = None  # type: ignore
    F = None  # type: ignore

if nn is None:
    class _DummyModule:
        pass

    class _DummyNN:
        Module = _DummyModule

    nn = _DummyNN()


_TAG_VOCAB = [
    "godark", "godark partner", "godark prep", "godark likely",
    "godark xrpl settlement", "godark cluster", "godark batch",
    "godark cross-chain", "godark equity rotation",
    "godark trustline", "monster trustline",
    "renegade", "renegade proof", "renegade settlement confirmed",
    "rwa prep", "rwa amm deposit", "rwa amm withdrawal", "rwa amm fee shift",
    "rwa ob event", "ob liquidity shift", "ob depth surge", "ob imbalance",
    "ob whale move",
]

_NUMERIC_KEYS = [
    "usd_value_sum", "time_delta", "imbalance_ratio", "bid_change_pct",
    "ask_change_pct", "amm_lp_change_pct", "spread_bps",
    "godark_cluster_size", "godark_is_batch",
    "godark_has_cross_chain", "godark_has_equity_rotation",
    "renegade_flag", "renegade_confirmed_flag",
]

_INPUT_DIM = len(_TAG_VOCAB) + len(_NUMERIC_KEYS)
_SEQ_LEN = 1  # per-cross sequence (can be extended later)


async def _get_redis() :
    return await get_redis()


def _tags_from_signal(sig: Dict[str, Any]) -> List[str]:
    ts = sig.get("tags") or []
    return [str(t).lower() for t in ts]


def _numeric_features(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, float]:
    out = {k: 0.0 for k in _NUMERIC_KEYS}
    try:
        av = float(a.get("usd_value") or 0.0)
    except Exception:
        av = 0.0
    try:
        bv = float(b.get("usd_value") or 0.0)
    except Exception:
        bv = 0.0
    out["usd_value_sum"] = av + bv
    try:
        dt = abs(int(a.get("timestamp", 0)) - int(b.get("timestamp", 0)))
    except Exception:
        dt = 0
    out["time_delta"] = float(dt)
    for s in (a, b):
        ch = s.get("change") or {}
        try:
            out["imbalance_ratio"] = max(out["imbalance_ratio"], float(ch.get("imbalance_ratio") or 0.0))
        except Exception:
            pass
        try:
            out["bid_change_pct"] = max(out["bid_change_pct"], float(ch.get("bid_change_pct") or 0.0))
        except Exception:
            pass
        try:
            out["ask_change_pct"] = max(out["ask_change_pct"], float(ch.get("ask_change_pct") or 0.0))
        except Exception:
            pass
        try:
            ob_spread = float(s.get("spread_bps") or 0.0)
            out["spread_bps"] = max(out["spread_bps"], ob_spread)
        except Exception:
            pass
        try:
            amm = (s.get("amm_liquidity_change") or {})
            out["amm_lp_change_pct"] = max(out["amm_lp_change_pct"], float(amm.get("lp_change_pct") or 0.0))
        except Exception:
            pass
    # GoDark and Renegade pattern metrics from underlying signals
    try:
        cluster = 0.0
        is_batch = 0.0
        has_cross = 0.0
        has_equity = 0.0
        ren_flag = 0.0
        ren_conf = 0.0
        for s in (a, b):
            try:
                pattern = s.get("godark_pattern") or {}
            except Exception:
                pattern = {}
            try:
                csize = float(pattern.get("cluster_size") or 0.0)
                if csize > cluster:
                    cluster = csize
            except Exception:
                pass
            try:
                tags = [str(t).lower() for t in (s.get("tags") or [])]
            except Exception:
                tags = []
            if any("godark batch" in t for t in tags):
                is_batch = 1.0
            if any("godark cross-chain" in t for t in tags):
                has_cross = 1.0
            if any("godark equity rotation" in t for t in tags):
                has_equity = 1.0
            if any("renegade" in t for t in tags):
                ren_flag = 1.0
            if any("renegade settlement confirmed" in t for t in tags):
                ren_conf = 1.0
        out["godark_cluster_size"] = cluster
        out["godark_is_batch"] = is_batch
        out["godark_has_cross_chain"] = has_cross
        out["godark_has_equity_rotation"] = has_equity
        out["renegade_flag"] = ren_flag
        out["renegade_confirmed_flag"] = ren_conf
    except Exception:
        pass
    return out


def _vectorize_cross(cross: Dict[str, Any]) -> List[float]:
    sigs = cross.get("signals") or []
    if len(sigs) < 2:
        return [0.0] * _INPUT_DIM
    a, b = sigs[0], sigs[1]
    tags = set(_tags_from_signal(a) + _tags_from_signal(b))
    vec: List[float] = []
    for t in _TAG_VOCAB:
        vec.append(1.0 if any(t in x for x in tags) else 0.0)
    nums = _numeric_features(a, b)
    for k in _NUMERIC_KEYS:
        v = float(nums.get(k) or 0.0)
        if k == "time_delta":
            v = v / 900.0
        elif k == "imbalance_ratio":
            v = max(min(v, 10.0), 0.0) / 10.0
        elif k in ("bid_change_pct", "ask_change_pct", "amm_lp_change_pct"):
            v = max(min(v, 5.0), -5.0) / 5.0
        elif k == "usd_value_sum":
            v = min(v / 50_000_000.0, 1.0)
        elif k == "spread_bps":
            v = min(v / 1000.0, 1.0)
        elif k == "godark_cluster_size":
            v = min(v, 10.0) / 10.0
        elif k in ("godark_is_batch", "godark_has_cross_chain", "godark_has_equity_rotation",
                   "renegade_flag", "renegade_confirmed_flag"):
            v = 1.0 if v > 0 else 0.0
        vec.append(v)
    return vec


async def _label_for_cross(cross: Dict[str, Any]) -> Optional[float]:
    try:
        ts = int(cross.get("timestamp", 0))
        if ts <= 0:
            return None
        p0 = await get_price_usd_at("xrp", ts)
        p1 = await get_price_usd_at("xrp", ts + 900)
        if p0 <= 0 or p1 <= 0:
            return None
        return (p1 - p0) / p0 * 100.0
    except Exception:
        return None


async def get_labeled_batch(limit: int = 64) -> List[Tuple[List[float], float]]:
    xs: List[Tuple[List[float], float]] = []
    crosses = await fetch_recent_cross_signals(limit=256)
    for c in crosses:
        y = await _label_for_cross(c)
        if y is None:
            continue
        x = _vectorize_cross(c)
        xs.append((x, y))
        if len(xs) >= limit:
            break
    return xs


if TORCH_AVAILABLE:
    class BiGRUFlowPredictor(nn.Module):  # type: ignore[misc]
        def __init__(self, input_size: int = _INPUT_DIM, hidden_size: int = 512, num_layers: int = 2):
            super().__init__()
            self.gru = nn.GRU(
                input_size,
                hidden_size,
                num_layers,
                batch_first=True,
                bidirectional=True,
                dropout=0.3,
            )
            self.fc = nn.Linear(hidden_size * 2, 1)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":  # type: ignore[name-defined]
            out, _ = self.gru(x)
            return self.fc(out[:, -1, :]).squeeze(-1)
else:
    class BiGRUFlowPredictor:  # type: ignore[misc]
        """Stub used when torch is unavailable.

        Live GRU training and ML inference are disabled via TORCH_AVAILABLE,
        so this class should never be instantiated in that mode.
        """

        def __init__(self, *args: object, **kwargs: object) -> None:  # pragma: no cover
            raise RuntimeError("Torch not available – BiGRUFlowPredictor is disabled")


_MODEL: Optional[BiGRUFlowPredictor] = None
_MODEL_DEVICE: Optional["torch.device"] = None  # type: ignore[name-defined]
_MODEL_PATH = "/app/ml/checkpoints/gru_latest.pt"
_LAST_ML_ERR_TS: float = 0.0

# ML inference circuit breaker (Redis-backed, sync client for use in sync function)
_ML_CB: Optional[redis_sync.Redis] = None
_ML_CB_OPEN_UNTIL = "ml:breaker:open_until"
_ML_CB_FAILURES = "ml:breaker:failures"


def _ml_cb_client() -> redis_sync.Redis:
    global _ML_CB
    if _ML_CB is None:
        _ML_CB = redis_sync.from_url(REDIS_URL, decode_responses=True)
    return _ML_CB


def _ml_is_breaker_open() -> bool:
    if not ML_CIRCUIT_BREAKER_ENABLED:
        return False
    try:
        r = _ml_cb_client()
        until_s = r.get(_ML_CB_OPEN_UNTIL)
        if until_s:
            try:
                return float(until_s) > time.time()
            except Exception:
                return False
        return False
    except Exception:
        return False


def _ml_record_failure() -> int:
    if not ML_CIRCUIT_BREAKER_ENABLED:
        return 0
    try:
        r = _ml_cb_client()
        n = r.incr(_ML_CB_FAILURES)
        # auto-reset counter after 1 hour of inactivity
        r.expire(_ML_CB_FAILURES, 3600)
        if int(n or 0) >= int(ML_CIRCUIT_BREAKER_FAILURES):
            open_until = time.time() + float(ML_CIRCUIT_BREAKER_COOLDOWN_SECONDS)
            r.set(_ML_CB_OPEN_UNTIL, str(open_until), ex=int(ML_CIRCUIT_BREAKER_COOLDOWN_SECONDS))
            try:
                print(f"[CIRCUIT_ML] Tripped after {n} failures – open for {ML_CIRCUIT_BREAKER_COOLDOWN_SECONDS}s")
            except Exception:
                pass
            # reset counter after trip
            try:
                r.delete(_ML_CB_FAILURES)
            except Exception:
                pass
        return int(n or 0)
    except Exception:
        return 0


def _ml_reset_failures() -> None:
    try:
        r = _ml_cb_client()
        r.delete(_ML_CB_FAILURES)
    except Exception:
        pass


def _heuristic_impact_from_cross(cross: Dict[str, Any]) -> float:
    try:
        sigs = cross.get("signals") or []
        a = sigs[0] if len(sigs) > 0 else {}
        b = sigs[1] if len(sigs) > 1 else {}
        nums = _numeric_features(a, b)
        usd = float(nums.get("usd_value_sum") or 0.0)
        imb = float(nums.get("imbalance_ratio") or 1.0)
        sp = float(nums.get("spread_bps") or 0.0)
        conf = float(cross.get("confidence") or 0.0) / 100.0
        base = (usd / 100_000_000.0) * 0.15  # 0.15% per $100M
        boost = min(max(imb - 1.0, 0.0), 1.0) * 0.5 + min(sp / 1000.0, 1.0) * 0.2
        conf_boost = conf * 0.3
        est = base + boost + conf_boost
        return float(max(0.05, min(est, 5.0)))
    except Exception:
        return 0.2


def _ensure_model_loaded() -> None:
    global _MODEL, _MODEL_DEVICE
    if not TORCH_AVAILABLE:
        return
    if _MODEL is None:
        device = (
            torch.device("mps") if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else
            torch.device("cuda") if torch.cuda.is_available() else
            torch.device("cpu")
        )
        model = BiGRUFlowPredictor().to(device)
        if os.path.exists(_MODEL_PATH):
            try:
                state = torch.load(_MODEL_PATH, map_location=device)
                model.load_state_dict(state)
            except Exception:
                pass
        # Optional: compile for speed (PyTorch 2.1+; best on 2.9.1+). Safe fallback on failure.
        try:
            compiled = torch.compile(model, mode="max-autotune", backend="inductor")  # type: ignore[attr-defined]
            model = compiled
        except Exception:
            pass
        model.eval()
        _MODEL = model
        _MODEL_DEVICE = device


async def live_gru_training() -> None:
    if not TORCH_AVAILABLE:
        while True:
            print("[ML] Torch not available – GRU training disabled")
            await asyncio.sleep(600)

    device = (
        torch.device("mps") if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else
        torch.device("cuda") if torch.cuda.is_available() else
        torch.device("cpu")
    )
    model = BiGRUFlowPredictor().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=1e-2)
    godark_cols = [i for i, t in enumerate(_TAG_VOCAB) if "godark" in t]
    batch_id = 0
    os.makedirs(os.path.dirname(_MODEL_PATH), exist_ok=True)
    print("[ML] GRU training loop started. device=", device)

    while True:
        batch = await get_labeled_batch(limit=64)
        if len(batch) < 32:
            await asyncio.sleep(300)
            continue
        xs, ys = zip(*batch)
        import numpy as np
        x_arr = np.array(xs, dtype="float32").reshape(len(xs), _SEQ_LEN, _INPUT_DIM)
        y_arr = np.array(ys, dtype="float32")
        x = torch.from_numpy(x_arr).to(device)
        y = torch.from_numpy(y_arr).to(device)
        optimizer.zero_grad()
        pred = model(x)
        loss_raw = F.mse_loss(pred, y, reduction="none")
        # Upweight GoDark-tagged samples to focus the model on GoDark flows
        try:
            if godark_cols:
                tag_feats = x[:, 0, :len(_TAG_VOCAB)]
                godark_mask = (tag_feats[:, godark_cols].max(dim=1).values > 0.5).float()
                weights = torch.where(
                    godark_mask > 0,
                    torch.tensor(5.0, device=device),
                    torch.tensor(1.0, device=device),
                )
                loss = (loss_raw * weights).mean()
            else:
                loss = loss_raw.mean()
        except Exception:
            loss = loss_raw.mean()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        batch_id += 1
        if batch_id % 50 == 0:
            torch.save(model.state_dict(), _MODEL_PATH)
            print(f"[ML] GRU loss={loss.item():.6f} batch={batch_id}")
        await asyncio.sleep(60)


def predict_impact_ml(cross: Dict[str, Any]) -> Optional[float]:
    try:
        # Reduce CPU threading to avoid oneDNN thread spam on small inference
        try:
            os.environ["OMP_NUM_THREADS"] = "1"
        except Exception:
            pass
        if TORCH_AVAILABLE:
            try:
                torch.set_num_threads(1)
            except Exception:
                pass
        if _ml_is_breaker_open():
            h = _heuristic_impact_from_cross(cross)
            try:
                print(f"[ML] Circuit open – using heuristic fallback: {h:.2f}%")
            except Exception:
                pass
            return h
        if not TORCH_AVAILABLE:
            return _heuristic_impact_from_cross(cross)
        _ensure_model_loaded()
        if _MODEL is None or _MODEL_DEVICE is None:
            return _heuristic_impact_from_cross(cross)
        import numpy as np
        vec = _vectorize_cross(cross)
        x_arr = np.array(vec, dtype="float32").reshape(1, _SEQ_LEN, _INPUT_DIM)
        x = torch.from_numpy(x_arr).to(_MODEL_DEVICE)
        with torch.no_grad():
            out = _MODEL(x)
        y = float(out.item())
        # GoDark-specific inference boost: amplify impact when any GoDark tags present
        try:
            sigs = cross.get("signals") or []
            tags: List[str] = []
            for s in sigs[:2]:
                for t in (s.get("tags") or []):
                    tags.append(str(t).lower())
            if any("godark" in t for t in tags):
                y = y * 1.2
        except Exception:
            pass
        _ml_reset_failures()
        return y
    except Exception as e:
        try:
            global _LAST_ML_ERR_TS
            now = time.time()
            if now - _LAST_ML_ERR_TS > 60:
                print(f"[ML] Inference failed: {e}")
                _LAST_ML_ERR_TS = now
        except Exception:
            pass
        _ml_record_failure()
        h = _heuristic_impact_from_cross(cross)
        try:
            print(f"[ML] Fallback heuristic impact: {h:.2f}%")
        except Exception:
            pass
        return h
