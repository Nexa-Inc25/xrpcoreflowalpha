import os

APP_ENV = os.getenv("APP_ENV", "dev")
DISABLE_EQUITY_FALLBACK = os.getenv("DISABLE_EQUITY_FALLBACK", "false").lower() == "true"

XRPL_WSS = os.getenv("XRPL_WSS", "")
ALCHEMY_WS_URL = os.getenv("ALCHEMY_WS_URL", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
ALERTS_SLACK_WEBHOOK = os.getenv("ALERTS_SLACK_WEBHOOK", "")

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "xrpflow")
POSTGRES_USER = os.getenv("POSTGRES_USER", "xrpflow")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

EQUITY_TICKERS = [t.strip() for t in os.getenv("EQUITY_TICKERS", "AAPL,MSFT,TSLA").split(",") if t.strip()]
VERIFIER_ALLOWLIST = [a.strip().lower() for a in os.getenv("VERIFIER_ALLOWLIST", "").split(",") if a.strip()]

SENTRY_DSN = os.getenv("SENTRY_DSN", "")
