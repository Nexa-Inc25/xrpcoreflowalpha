from fastapi import FastAPI, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.config import XRPL_WSS, ALCHEMY_WS_URL, FINNHUB_API_KEY
from api.sdui import router as sdui_router
from api.debug import router as debug_router
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.include_router(sdui_router)
app.include_router(debug_router)
app.mount("/static", StaticFiles(directory="clients"), name="static")

@app.get("/health")
async def health():
    chains = []
    if XRPL_WSS:
        chains.append("xrpl")
    if ALCHEMY_WS_URL:
        chains.append("ethereum")
    equities = bool(FINNHUB_API_KEY)
    status = "healthy" if XRPL_WSS and ALCHEMY_WS_URL and FINNHUB_API_KEY else "degraded"
    return {"status": status, "chains": chains, "equities": equities}

@app.get("/metrics")
async def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
