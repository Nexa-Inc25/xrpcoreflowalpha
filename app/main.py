import asyncio
from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY, SOLANA_RPC_URL, APP_VERSION
from app.config import CORS_ALLOW_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS
from api.sdui import router as sdui_router
from api.debug import router as debug_router
from api.health import router as health_router
from api.ui import router as ui_router
from api.billing import router as billing_router
from api.admin import router as admin_router
from fastapi.staticfiles import StaticFiles
from observability.impact import start_binance_depth_worker
from api.export import router as export_router
from middleware.api_key import api_key_middleware
from scanners.solana_humidifi import start_solana_humidifi_worker
from api.onchain import router as onchain_router
from billing.onchain_watchers import start_solana_onchain_watcher, start_eth_onchain_watcher, start_onchain_maintenance
from api.notify import router as notify_router
from notifications.push_worker import start_push_worker
from api.history import router as history_router
from api.qr import router as qr_router
from api.user import router as user_router
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS or ["*"],
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=CORS_ALLOW_METHODS or ["*"],
    allow_headers=CORS_ALLOW_HEADERS or ["*"],
)
app.include_router(ui_router)
app.include_router(sdui_router)
app.include_router(billing_router)
app.include_router(admin_router)
app.include_router(export_router)
app.include_router(onchain_router)
app.include_router(notify_router)
app.include_router(history_router)
app.include_router(qr_router)
app.include_router(user_router)
app.include_router(debug_router)
app.include_router(health_router)
app.mount("/static", StaticFiles(directory="clients"), name="static")
app.middleware("http")(api_key_middleware)

@app.on_event("startup")
async def _startup():
    # Launch Binance depth worker (non-blocking)
    asyncio.create_task(start_binance_depth_worker())
    if SOLANA_RPC_URL:
        asyncio.create_task(start_solana_humidifi_worker())
        asyncio.create_task(start_solana_onchain_watcher())
    asyncio.create_task(start_eth_onchain_watcher())
    asyncio.create_task(start_push_worker())
    asyncio.create_task(start_onchain_maintenance())

@app.get("/health")
async def health():
    chains = []
    if XRPL_WSS:
        chains.append("xrpl")
    if ALCHEMY_WS_URL:
        chains.append("ethereum")
    if SOLANA_RPC_URL:
        chains.append("solana")
    equities = bool(FINNHUB_API_KEY)
    scanner = "humidifi_proxy_active" if SOLANA_RPC_URL else ""
    status = "live"
    return {"status": status, "chains": chains, "scanner": scanner, "version": APP_VERSION, "equities": equities}

@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
