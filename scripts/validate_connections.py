#!/usr/bin/env python3
import asyncio
import os

import httpx
from web3 import Web3
from xrpl.asyncio.clients import AsyncWebsocketClient
from xrpl.models.requests import ServerInfo
from dotenv import load_dotenv


async def check_xrpl(url: str) -> bool:
    if not url:
        return False
    try:
        async with AsyncWebsocketClient(url) as client:
            resp = await client.request(ServerInfo())
            return bool(resp and getattr(resp, "status", None) == "success")
    except Exception:
        return False


def check_web3(url: str) -> bool:
    if not url:
        return False
    try:
        w3 = Web3(Web3.WebsocketProvider(url))
        _ = w3.eth.chain_id
        return True
    except Exception:
        return False


async def check_finnhub(key: str) -> bool:
    if not key:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("https://finnhub.io/api/v1/quote", params={"symbol": "AAPL", "token": key})
            return r.status_code == 200
    except Exception:
        return False


async def check_polygon(key: str) -> bool:
    if not key:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get("https://api.polygon.io/v2/reference/markets", params={"apiKey": key})
            return r.status_code == 200
    except Exception:
        return False


async def check_slack(webhook: str) -> bool:
    if not webhook:
        return False
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(webhook, json={"text": "XRP Flow Alpha: connectivity test"})
            return r.status_code in (200, 204)
    except Exception:
        return False


async def main():
    # Load .env if present
    load_dotenv(".env")
    xrpl = await check_xrpl(os.getenv("XRPL_WSS", ""))
    web3 = check_web3(os.getenv("ALCHEMY_WS_URL", ""))
    finnhub = await check_finnhub(os.getenv("FINNHUB_API_KEY", ""))
    polygon = await check_polygon(os.getenv("POLYGON_API_KEY", ""))
    slack = await check_slack(os.getenv("ALERTS_SLACK_WEBHOOK", ""))
    print({
        "XRPL_WSS": xrpl,
        "ALCHEMY_WS_URL": web3,
        "FINNHUB_API_KEY": finnhub,
        "POLYGON_API_KEY": polygon,
        "ALERTS_SLACK_WEBHOOK": slack,
    })


if __name__ == "__main__":
    asyncio.run(main())
