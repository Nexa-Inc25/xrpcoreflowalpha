import asyncio
from fastapi import FastAPI, Response
from fastapi.responses import RedirectResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY, SOLANA_RPC_URL, APP_VERSION
from app.config import SENTRY_DSN, APP_ENV
from app.config import POLYGON_API_KEY, ALPHA_VANTAGE_API_KEY, DISABLE_EQUITY_FALLBACK
from app.config import DATABENTO_API_KEY
from app.config import CORS_ALLOW_ORIGINS, CORS_ALLOW_CREDENTIALS, CORS_ALLOW_METHODS, CORS_ALLOW_HEADERS
from api.sdui import router as sdui_router
from api.debug import router as debug_router
from api.health import router as health_router
from api.ui import router as ui_router
from api.billing import router as billing_router
from api.admin import router as admin_router
from api.db_health import router as db_health_router
from api.scanner_health import router as scanner_health_router
from api.dashboard import router as dashboard_router
from api.flows import router as flows_router
from api.analytics import router as analytics_router
from api.correlations import router as correlations_router
from api.latency import router as latency_router
from fastapi.staticfiles import StaticFiles
from observability.impact import start_binance_depth_worker
from api.export import router as export_router
from middleware.api_key import api_key_middleware
from scanners.solana_humidifi import start_solana_humidifi_worker
from api.onchain import router as onchain_router
from billing.onchain_watchers import start_solana_onchain_watcher, start_eth_onchain_watcher, start_onchain_maintenance
from api.notify import router as notify_router
from notifications.push_worker import start_push_worker
from notifications.telegram_worker import start_telegram_worker
from api.history import router as history_router
from api.qr import router as qr_router
from api.user import router as user_router
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.starlette import StarletteIntegration
from predictors.futures_tracker import start_binance_futures_tracker
from predictors.polygon_macro_tracker import start_polygon_macro_tracker
try:
    from predictors.databento_macro_tracker import start_databento_macro_tracker
except Exception:
    async def start_databento_macro_tracker(symbols=None):
        return
try:
    from predictors.alpha_macro_tracker import start_alpha_macro_tracker
except Exception:
    async def start_alpha_macro_tracker(symbols=None):
        return
try:
    from predictors.yahoo_macro_tracker import start_yahoo_macro_tracker
except Exception:
    async def start_yahoo_macro_tracker(symbols=None):
        return
from scanners.zk_scanner import start_zk_scanner
from scanners.xrpl_scanner import start_xrpl_scanner
from scanners.xrpl_trustline_watcher import start_trustline_watcher
from scanners.xrpl_orderbook_monitor import start_xrpl_orderbook_monitor
from scanners.futures_scanner import start_futures_scanner
from scanners.forex_scanner import start_forex_scanner
from scanners.nansen_scanner import start_nansen_scanner
from scanners.dune_scanner import start_dune_scanner
from scanners.whale_alert_scanner import run_whale_alert_scanner
from observability.metrics import (
    zk_dominant_frequency_hz,
    zk_frequency_confidence,
    zk_flow_confidence_score,
)

if SENTRY_DSN:
    try:
        _dsn = str(SENTRY_DSN).strip()
        if _dsn and _dsn.lower().startswith("http"):
            sentry_sdk.init(
                dsn=_dsn,
                environment=APP_ENV,
                integrations=[StarletteIntegration()],
                traces_sample_rate=0.1,
                profiles_sample_rate=0.1,
                release=APP_VERSION,
            )
    except Exception:
        pass

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
app.include_router(db_health_router)
app.include_router(scanner_health_router)
app.include_router(dashboard_router)
app.include_router(flows_router)
app.include_router(analytics_router)
app.include_router(correlations_router)
app.include_router(latency_router)
app.mount("/static", StaticFiles(directory="clients"), name="static")
app.middleware("http")(api_key_middleware)

@app.get("/", include_in_schema=False)
async def root_redirect():
    return RedirectResponse(url="/ui")

@app.head("/", include_in_schema=False)
async def root_redirect_head():
    return RedirectResponse(url="/ui")

@app.on_event("startup")
async def _startup():
    # Initialize database schema for signal tracking
    try:
        from db.schema import init_schema
        await init_schema()
        print("[STARTUP] Database schema initialized")
    except Exception as e:
        print(f"[STARTUP] Database initialization skipped: {e}")
    
    # Start outcome checker worker for analytics
    try:
        from workers.outcome_checker import start_outcome_checker
        await start_outcome_checker()
        print("[STARTUP] Outcome checker worker started")
    except Exception as e:
        print(f"[STARTUP] Outcome checker skipped: {e}")
    
    # Launch Binance depth worker (non-blocking)
    asyncio.create_task(start_binance_depth_worker())
    if SOLANA_RPC_URL:
        asyncio.create_task(start_solana_humidifi_worker())
        asyncio.create_task(start_solana_onchain_watcher())
    asyncio.create_task(start_eth_onchain_watcher())
    asyncio.create_task(start_push_worker())
    asyncio.create_task(start_onchain_maintenance())
    if ALCHEMY_WS_URL:
        asyncio.create_task(start_zk_scanner())
    # XRPL scanners for XRP flows, trustlines, and orderbook
    if XRPL_WSS:
        asyncio.create_task(start_xrpl_scanner())
        asyncio.create_task(start_trustline_watcher())
        asyncio.create_task(start_xrpl_orderbook_monitor())
        # Start ledger drift monitor
        try:
            from workers.ledger_monitor import start_ledger_monitor
            await start_ledger_monitor()
            print("[STARTUP] Ledger drift monitor started")
        except Exception as e:
            print(f"[STARTUP] Ledger monitor skipped: {e}")
    asyncio.create_task(start_binance_futures_tracker())
    
    # Multi-asset scanners for cross-market correlation
    asyncio.create_task(start_futures_scanner())   # Databento: ES, NQ, VIX, Gold, Oil
    asyncio.create_task(start_forex_scanner())     # Alpha Vantage: EUR/USD, DXY proxy, news
    asyncio.create_task(start_nansen_scanner())    # Nansen: Whale labels, smart money
    asyncio.create_task(start_dune_scanner())      # Dune: DEX volume, stablecoin flows
    asyncio.create_task(run_whale_alert_scanner()) # Whale Alert: Large transfers, confidence
    
    # Latency pinger for algo tracking
    try:
        from predictors.latency_pinger import start_latency_pinger_worker
        asyncio.create_task(start_latency_pinger_worker())
        print("[STARTUP] Latency pinger worker started")
    except Exception as e:
        print(f"[STARTUP] Latency pinger skipped: {e}")
    
    # XGBoost latency prediction model
    try:
        from ml.latency_xgboost import start_latency_prediction_worker
        asyncio.create_task(start_latency_prediction_worker())
        print("[STARTUP] XGBoost latency predictor started")
    except Exception as e:
        print(f"[STARTUP] XGBoost predictor skipped: {e}")
    
    # Slack latency bot for anomaly alerts
    try:
        from workers.slack_latency_bot import start_slack_latency_bot
        asyncio.create_task(start_slack_latency_bot())
        print("[STARTUP] Slack latency bot started")
    except Exception as e:
        print(f"[STARTUP] Slack latency bot skipped: {e}")
    
    if DATABENTO_API_KEY:
        asyncio.create_task(start_databento_macro_tracker())
    elif POLYGON_API_KEY:
        asyncio.create_task(start_polygon_macro_tracker())
    elif not DISABLE_EQUITY_FALLBACK:
        # Fallback to Yahoo Finance (no API key)
        asyncio.create_task(start_yahoo_macro_tracker())
    try:
        zk_dominant_frequency_hz.labels(source="futures_btcusdt").set(0.0)
        zk_dominant_frequency_hz.labels(source="futures_ethusdt").set(0.0)
        zk_dominant_frequency_hz.labels(source="zk_events").set(0.0)
        zk_dominant_frequency_hz.labels(source="xrpl_settlements").set(0.0)
        zk_dominant_frequency_hz.labels(source="macro_es").set(0.0)
        zk_dominant_frequency_hz.labels(source="macro_nq").set(0.0)
        zk_frequency_confidence.labels(algo_fingerprint="unknown").set(0.0)
        zk_flow_confidence_score.labels(protocol="godark").set(0.0)
    except Exception:
        pass
    # Telegram dark-flow alerts (optional)
    asyncio.create_task(start_telegram_worker())


@app.on_event("shutdown")
async def _shutdown():
    """Graceful shutdown - close database connections."""
    print("[SHUTDOWN] Closing database connections...")
    try:
        from db.connection import close_pool
        await close_pool()
    except Exception as e:
        print(f"[SHUTDOWN] Error closing DB pool: {e}")
    print("[SHUTDOWN] Complete")


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
