import time
import redis.asyncio as redis
from fastapi import APIRouter
from datetime import datetime, timezone
from typing import Dict, Any

from app.config import (
    REDIS_URL,
    APP_VERSION,
    APP_ENV
)

router = APIRouter()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint for DigitalOcean App Platform.
    Returns 200 OK if the service is running.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": APP_VERSION,
        "environment": APP_ENV,
        "service": "zkalphaflow-api"
    }


async def _get_redis() -> redis.Redis:
    return redis.from_url(REDIS_URL, decode_responses=True)


@router.get("/health/circuit")
async def circuit_status():
    r = await _get_redis()
    now = time.time()

    async def _get(key: str, default: str = "0") -> str:
        try:
            v = await r.get(key)
            return v if v is not None else default
        except Exception:
            return default

    exec_until_s = await _get("exec:breaker_until")
    ml_until_s = await _get("ml:breaker:open_until")
    losses_s = await _get("exec:consecutive_losses", "0")
    pnl_s = await _get("risk:daily_pnl_usd", "0")

    def _fmt(until_s: str) -> str:
        try:
            u = float(until_s)
        except Exception:
            u = 0.0
        return "OK" if now >= u else f"TRIPPED until {int(u)}"

    exec_status = _fmt(exec_until_s)
    ml_status = _fmt(ml_until_s)
    status = "healthy" if (exec_status == "OK" and ml_status == "OK") else "degraded"

    try:
        losses = int(losses_s)
    except Exception:
        losses = 0
    try:
        daily_pnl = float(pnl_s)
    except Exception:
        daily_pnl = 0.0

    return {
        "ml_circuit_breaker": ml_status,
        "execution_circuit_breaker": exec_status,
        "consecutive_losses": losses,
        "daily_pnl_usd": daily_pnl,
        "status": status,
    }


@router.get("/health/redis")
async def redis_stats():
    try:
        r = await _get_redis()
    except Exception:
        return {"status": "unreachable"}
    try:
        info = await r.info()  # type: ignore[no-untyped-call]
    except Exception:
        return {"status": "unreachable"}
    server = info or {}
    used_memory = server.get("used_memory") or server.get("used_memory_human")
    connected_clients = server.get("connected_clients")
    ops_per_sec = server.get("instantaneous_ops_per_sec")
    keyspace_hits = server.get("keyspace_hits")
    keyspace_misses = server.get("keyspace_misses")

    async def _zcard(key: str) -> int:
        try:
            return int(await r.zcard(key))
        except Exception:
            return 0

    godark_settlements = await _zcard("godark:settlements")
    penumbra_unshields = await _zcard("penumbra:unshields")
    secret_unshields = await _zcard("secret:unshields")

    return {
        "status": "ok",
        "used_memory": used_memory,
        "connected_clients": connected_clients,
        "ops_per_sec": ops_per_sec,
        "keyspace_hits": keyspace_hits,
        "keyspace_misses": keyspace_misses,
        "windows": {
            "godark:settlements": godark_settlements,
            "penumbra:unshields": penumbra_unshields,
            "secret:unshields": secret_unshields,
        },
    }
