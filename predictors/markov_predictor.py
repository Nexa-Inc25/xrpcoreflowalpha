import asyncio
from collections import deque
from typing import Any, Dict, List

import numpy as np


class ZKFlowHMM:
    def __init__(self, history: int = 30):
        self._obs_history: deque[int] = deque(maxlen=history)
        self._lock = asyncio.Lock()
        # Hidden states: 0=A Normal, 1=B Prep, 2=C Imminent
        # Observations: 0=Baseline, 1=Partner custody inflow, 2=ZK spike, 3=Large settlement outflow
        self._startprob = np.array([0.75, 0.2, 0.05], dtype=float)
        self._trans = np.array(
            [
                [0.88, 0.11, 0.01],  # A -> A/B/C
                [0.20, 0.60, 0.20],  # B -> A/B/C
                [0.05, 0.15, 0.80],  # C -> A/B/C
            ],
            dtype=float,
        )
        # P(observation | hidden)
        self._emiss = np.array(
            [
                [0.85, 0.12, 0.03, 0.00],  # A emits mostly baseline
                [0.25, 0.45, 0.25, 0.05],  # B emits partner + zk spikes
                [0.05, 0.15, 0.45, 0.35],  # C emits zk spikes + settlements
            ],
            dtype=float,
        )
        self._n_hidden = 3

    def _forward(self, obs_seq: List[int]) -> np.ndarray:
        if not obs_seq:
            p = self._startprob.copy()
            p /= p.sum()
            return p
        alpha = self._startprob * self._emiss[:, obs_seq[0]]
        s = float(alpha.sum())
        if s <= 0:
            alpha = np.full(self._n_hidden, 1.0 / self._n_hidden, dtype=float)
        else:
            alpha /= s
        for o in obs_seq[1:]:
            alpha = alpha @ self._trans
            alpha *= self._emiss[:, o]
            s = float(alpha.sum())
            if s <= 0:
                alpha = np.full(self._n_hidden, 1.0 / self._n_hidden, dtype=float)
            else:
                alpha /= s
        return alpha

    async def update(self, obs: int) -> float:
        o = int(max(0, min(3, obs)))
        async with self._lock:
            self._obs_history.append(o)
            if len(self._obs_history) < 5:
                return 0.0
            seq = list(self._obs_history)[-20:]
            post = self._forward(seq)
            return float(post[2])

    def update_and_score(self, obs: int) -> float:
        o = int(max(0, min(3, obs)))
        self._obs_history.append(o)
        if len(self._obs_history) < 5:
            return 0.0
        seq = list(self._obs_history)[-20:]
        post = self._forward(seq)
        return float(post[2])


def _get_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _lower_tags(sig: Dict[str, Any]) -> List[str]:
    try:
        return [str(t).lower() for t in (sig.get("tags") or [])]
    except Exception:
        return []


def classify_observation(sig: Dict[str, Any]) -> int:
    try:
        stype = str(sig.get("type") or "").lower()
        tags = _lower_tags(sig)
        usd = _get_float(sig.get("usd_value"), 0.0)
        if stype == "xrp" and ("godark xrpl settlement" in tags or "godark settlement" in tags) and usd >= 5_000_000:
            return 3
        if stype == "zk" or str(sig.get("sub_type") or "").lower() == "verifier_call":
            gas_used = int(sig.get("gas_used") or 0)
            input_len = int(sig.get("input_len") or 0)
            entropy = _get_float(sig.get("calldata_entropy"), 0.0)
            gas_price = int(sig.get("gas_price_wei") or 0)
            score = 0
            if gas_used >= 400_000:
                score += 1
            if input_len >= 512:
                score += 1
            if entropy >= 6.0:
                score += 1
            if gas_price >= 30_000_000_000:
                score += 1
            if score >= 2:
                return 2
        pf = int(sig.get("partner_from") or 0)
        pt = int(sig.get("partner_to") or 0)
        if pf or pt or ("godark partner" in tags):
            return 1
        return 0
    except Exception:
        return 0


zk_hmm = ZKFlowHMM()
