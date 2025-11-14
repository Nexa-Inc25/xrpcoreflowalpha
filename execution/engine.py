import os
from typing import Optional

from app.config import XRPL_WSS, EXECUTION_ENABLED
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.wallet import Wallet
from xrpl.models.transactions import Payment
from xrpl.asyncio.transaction import safe_sign_and_autofill_transaction, send_reliable_submission


class XRPFlowAlphaExecution:
    def __init__(self) -> None:
        self.enabled: bool = EXECUTION_ENABLED
        seed = os.getenv("EXECUTION_SEED") or ""
        self.wallet: Optional[Wallet] = Wallet.from_seed(seed) if (self.enabled and seed) else None

    async def counter_trade_xrp(self, amount_xrp: float, destination: str) -> dict:
        if not self.enabled:
            raise RuntimeError("Execution disabled in production")
        if not self.wallet:
            raise RuntimeError("Execution wallet not configured")
        drops = str(int(float(amount_xrp) * 1_000_000))
        tx = Payment(account=self.wallet.classic_address, destination=destination, amount=drops)
        async with AsyncWebsocketClient(XRPL_WSS) as client:
            signed = await safe_sign_and_autofill_transaction(tx, self.wallet, client)
            resp = await send_reliable_submission(signed, client)
        return resp.result

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
