import os
import time
from typing import Optional, Dict, Any

import redis.asyncio as redis

from app.config import (
    XRPL_WSS,
    EXECUTION_ENABLED,
    EXECUTION_DRY_RUN,
    EXECUTION_MAX_SLIPPAGE_PCT,
    RISK_MAX_PCT_OF_SIGNAL,
    RISK_DAILY_PNL_USD,
    RISK_MAX_VOL_BPS,
    REDIS_URL,
    CIRCUIT_BREAKER_LOSSES,
    CIRCUIT_BREAKER_COOLDOWN_SECONDS,
)
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from utils.price import get_price_usd


class XRPFlowAlphaExecution:
    def __init__(self) -> None:
        self.enabled: bool = EXECUTION_ENABLED
        seed = os.getenv("EXECUTION_SEED") or ""
        self.wallet: Optional[Wallet] = Wallet.from_seed(seed) if (self.enabled and seed) else None
        self._redis = redis.from_url(REDIS_URL, decode_responses=True)

    # --- Circuit breaker helpers (Redis-backed) ---
    async def _breaker_until(self) -> float:
        try:
            v = await self._redis.get("exec:breaker_until")
            return float(v) if v else 0.0
        except Exception:
            return 0.0

    async def _is_breaker_open(self) -> bool:
        try:
            return time.time() < await self._breaker_until()
        except Exception:
            return False

    async def _trip_breaker(self) -> None:
        until = time.time() + float(CIRCUIT_BREAKER_COOLDOWN_SECONDS)
        try:
            await self._redis.set("exec:breaker_until", str(until), ex=CIRCUIT_BREAKER_COOLDOWN_SECONDS)
        except Exception:
            pass
        try:
            print(f"[CIRCUIT] Tripped – execution disabled for {CIRCUIT_BREAKER_COOLDOWN_SECONDS}s (until {int(until)})")
        except Exception:
            pass

    async def _inc_losses(self) -> int:
        try:
            n = await self._redis.incr("exec:consecutive_losses")
            return int(n or 0)
        except Exception:
            return 0

    async def _reset_losses(self) -> None:
        try:
            await self._redis.set("exec:consecutive_losses", "0", ex=7 * 24 * 3600)
        except Exception:
            pass

    async def counter_trade_xrp(self, amount_xrp: float, destination: str) -> dict:
        if not self.enabled:
            raise RuntimeError("Execution disabled in production")
        if not self.wallet:
            raise RuntimeError("Execution wallet not configured")
        drops = str(int(float(amount_xrp) * 1_000_000))
        tx = Payment(account=self.wallet.classic_address, destination=destination, amount=drops)
        async with AsyncWebsocketClient(XRPL_WSS) as client:
            # Lazy import to avoid ImportError at module import time
            try:
                from xrpl.asyncio.transaction import autofill as _autofill  # type: ignore
            except Exception:
                _autofill = None
            try:
                from xrpl.asyncio.transaction import send_reliable_submission as _send  # type: ignore
            except Exception:
                _send = None
            try:
                from xrpl.transaction import safe_sign_transaction as _sign  # type: ignore
            except Exception:
                _sign = None
            if not _autofill or not _send or not _sign:
                raise RuntimeError("XRPL transaction helpers unavailable in current xrpl-py version")
            filled_tx = await _autofill(tx, client)
            signed_tx = _sign(filled_tx, self.wallet)
            resp = await _send(signed_tx, client)
        return resp.result

    async def counter_trade(self, cross: Dict[str, Any]) -> Optional[str]:
        """Risk-managed trade based on a cross signal. Returns tx hash or markers, None if blocked.
        Honors EXECUTION_ENABLED and EXECUTION_DRY_RUN.
        """
        if not self.enabled:
            return None
        if not self.wallet:
            return None
        # Circuit breaker gate
        if await self._is_breaker_open():
            print("[CIRCUIT] Open – skipping execution")
            return "circuit_open" if EXECUTION_DRY_RUN else None
        # Basic risk sizing from signal USD
        try:
            sigs = cross.get("signals", [])
            usd_sum = 0.0
            for s in sigs:
                try:
                    usd_sum += float(s.get("usd_value") or 0.0)
                except Exception:
                    pass
            px = float(await get_price_usd("xrp")) or 0.0
            if px <= 0:
                return None
            max_pct = max(0.0, float(RISK_MAX_PCT_OF_SIGNAL))
            amount_xrp = max(1.0, (usd_sum * (max_pct / 100.0)) / px)
            # Hard caps
            amount_xrp = min(amount_xrp, 5_000_000.0)
        except Exception:
            return None
        # Determine counterparty from XRP signal in cross
        dest = None
        try:
            xs = [s for s in (cross.get("signals") or []) if s.get("type") == "xrp"]
            if xs:
                dest = xs[0].get("destination") or xs[0].get("source")
        except Exception:
            dest = None
        if not dest:
            return None
        # Risk gates placeholders (daily pnl / vol / circuit breaker could be stored in Redis)
        try:
            pnl = float(await self._redis.get("risk:daily_pnl_usd") or 0.0)
            if pnl <= -float(RISK_DAILY_PNL_USD):
                print("[RISK] Daily PnL limit reached – blocking trade")
                return None
        except Exception:
            pass
        # Dry run mode
        if EXECUTION_DRY_RUN:
            print(f"[DRY RUN] Would trade {amount_xrp:,.0f} XRP → {dest} (cross={cross.get('id')})")
            return "dry_run"
        # Submit on-ledger
        drops = str(int(float(amount_xrp) * 1_000_000))
        tx = Payment(account=self.wallet.classic_address, destination=dest, amount=drops)
        async with AsyncWebsocketClient(XRPL_WSS) as client:
            try:
                from xrpl.asyncio.transaction import autofill as _autofill  # type: ignore
                from xrpl.asyncio.transaction import send_reliable_submission as _send  # type: ignore
                from xrpl.transaction import safe_sign_transaction as _sign  # type: ignore
            except Exception:
                print("[EXECUTION] XRPL helpers unavailable – aborting trade")
                await self._trip_breaker()  # critical failure
                return None
            try:
                filled_tx = await _autofill(tx, client)
                signed_tx = _sign(filled_tx, self.wallet)
                resp = await _send(signed_tx, client)
            except Exception as e:
                print("[EXECUTION] Submission failed:", repr(e))
                await self._trip_breaker()  # critical failure
                return None
            # Post-trade loss tracking (placeholder)
            was_loss = await self._was_loss(resp)
            if was_loss:
                n = await self._inc_losses()
                if n >= int(CIRCUIT_BREAKER_LOSSES):
                    await self._trip_breaker()
                    await self._reset_losses()
            else:
                await self._reset_losses()
            try:
                h = resp.result.get("hash")
            except Exception:
                h = None
            print(f"[EXECUTION] Trade sent: {amount_xrp:,.0f} XRP → {dest} | tx={h}")
            return h

    async def _was_loss(self, resp: Any) -> bool:  # type: ignore[override]
        # Placeholder – integrate real PnL evaluation asynchronously
        try:
            _ = resp.result  # ensure shape
        except Exception:
            return True
        return False

    async def provide_amm_liquidity(self, pool_id: str, amount_a: str, amount_b: str) -> dict:
        if not self.enabled:
            raise RuntimeError("Execution disabled in production")
        raise NotImplementedError("AMMDeposit not implemented yet")

    async def withdraw_amm_liquidity(self, pool_id: str, lp_tokens: str) -> dict:
        if not self.enabled:
            raise RuntimeError("Execution disabled in production")
        raise NotImplementedError("AMMWithdraw not implemented yet")

    async def transfer_rwa_token(self, issuer: str, currency: str, amount: str, destination: str) -> dict:
        if not self.enabled:
            raise RuntimeError("Execution disabled in production")
        raise NotImplementedError("RWA transfer not implemented yet")
