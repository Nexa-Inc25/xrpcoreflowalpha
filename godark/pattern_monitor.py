import time
from typing import Any, Dict, List, Optional

from app.redis_utils import get_redis, REDIS_ENABLED

# REDIS_URL import removed - using redis_utils

_redis = None  # Redis client instance


async def _get_redis() :
    global _redis
    if _redis is None:
        _redis = await get_redis()
    return _redis


def _has_tag(signal: Dict[str, Any], needle: str) -> bool:
    tags = signal.get("tags") or []
    needle = needle.lower()
    try:
        return any(needle in str(t).lower() for t in tags)
    except Exception:
        return False


async def detect_godark_patterns(signal: Dict[str, Any]) -> Dict[str, Any]:
    """Annotate GoDark XRPL settlement signals with higher-order patterns.

    Tracks recent GoDark events in Redis sorted sets and, for qualifying
    XRPL settlements, adds pattern tags such as:
      - GoDark Cluster
      - GoDark Batch
      - GoDark Cross-Chain
      - GoDark Equity Rotation

    This function is safe to call on every signal; it is a no-op unless
    the signal is GoDark-related.
    """
    try:
        r = await _get_redis()
        ts = int(signal.get("timestamp") or int(time.time()))
        sid = str(signal.get("id") or "")
        if not sid:
            return signal
    except Exception:
        return signal

    stype = str(signal.get("type") or "")
    tags = list(signal.get("tags") or [])

    # Track GoDark prep (Ethereum) in a 30m window
    try:
        if stype == "godark_prep" and _has_tag(signal, "godark prep"):
            await r.zadd("godark:prep", {sid: ts})
            await r.zremrangebyscore("godark:prep", -float("inf"), ts - 1800)
    except Exception:
        pass

    # Track equity dark prints (used for equity rotation pattern)
    try:
        if stype == "equity" and str(signal.get("sub_type") or "").lower() == "dark_pool":
            await r.zadd("godark:equity_dark", {sid: ts})
            await r.zremrangebyscore("godark:equity_dark", -float("inf"), ts - 600)
    except Exception:
        pass

    # Only XRPL GoDark settlements participate in settlement patterns
    try:
        if stype != "xrp" or not _has_tag(signal, "godark xrpl settlement"):
            return signal

        # Maintain settlement window (last 5 minutes)
        await r.zadd("godark:settlements", {sid: ts})
        await r.zremrangebyscore("godark:settlements", -float("inf"), ts - 300)
        recent = await r.zrange("godark:settlements", 0, -1, withscores=True)
        cluster_size = len(recent)
        pattern_tags: List[str] = []

        # Cluster: 3+ settlements in 5 minutes
        if cluster_size >= 3:
            pattern_tags.append("GoDark Cluster")

        # Batch execution: 5+ settlements within 60 seconds
        if cluster_size >= 5:
            first_ts = float(recent[0][1])
            last_ts = float(recent[-1][1])
            if last_ts - first_ts <= 60.0:
                pattern_tags.append("GoDark Batch")

        # Cross-chain: ETH GoDark prep in last 30 minutes
        try:
            preps = await r.zrangebyscore("godark:prep", ts - 1800, ts)
            if preps:
                pattern_tags.append("GoDark Cross-Chain")
        except Exception:
            pass

        # Equity rotation: equity dark print in last 10 minutes
        try:
            eqs = await r.zrangebyscore("godark:equity_dark", ts - 600, ts)
            if eqs:
                pattern_tags.append("GoDark Equity Rotation")
        except Exception:
            pass

        if pattern_tags:
            existing = [str(t) for t in tags]
            for pt in pattern_tags:
                if pt not in existing:
                    tags.append(pt)
            signal["tags"] = tags
            signal["godark_pattern"] = {
                "types": pattern_tags,
                "cluster_size": cluster_size,
            }
    except Exception:
        # Do not interfere with main pipeline on any error
        return signal

    return signal
