import os

APP_ENV = os.getenv("APP_ENV", "dev")
DISABLE_EQUITY_FALLBACK = os.getenv("DISABLE_EQUITY_FALLBACK", "false").lower() == "true"

XRPL_WSS = os.getenv("XRPL_WSS", "")
ALCHEMY_WS_URL = os.getenv("ALCHEMY_WS_URL", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
ALERTS_SLACK_WEBHOOK = os.getenv("ALERTS_SLACK_WEBHOOK", "")
ALERTS_DEDUP_TTL_SECONDS = int(os.getenv("ALERTS_DEDUP_TTL_SECONDS", "300"))
ALERTS_RATE_WINDOW_SECONDS = int(os.getenv("ALERTS_RATE_WINDOW_SECONDS", "60"))
ALERTS_RATE_MAX_PER_WINDOW = int(os.getenv("ALERTS_RATE_MAX_PER_WINDOW", "30"))
ALERTS_RATE_LIMIT_PER_CATEGORY = os.getenv("ALERTS_RATE_LIMIT_PER_CATEGORY", "false").lower() == "true"

POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "xrpflow")
POSTGRES_USER = os.getenv("POSTGRES_USER", "xrpflow")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

EQUITY_TICKERS = [t.strip() for t in os.getenv("EQUITY_TICKERS", "AAPL,MSFT,TSLA").split(",") if t.strip()]
VERIFIER_ALLOWLIST = [a.strip().lower() for a in os.getenv("VERIFIER_ALLOWLIST", "").split(",") if a.strip()]

SENTRY_DSN = os.getenv("SENTRY_DSN", "")

# Equities detection threshold (shares)
EQUITY_BLOCK_MIN_SHARES = int(os.getenv("EQUITY_BLOCK_MIN_SHARES", "100000"))

# Pricing (Coingecko)
COINGECKO_API_BASE = os.getenv("COINGECKO_API_BASE", "https://api.coingecko.com/api/v3")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")

# Correlation dedup
CROSS_SIGNAL_DEDUP_TTL = int(os.getenv("CROSS_SIGNAL_DEDUP_TTL", "21600"))  # 6h

# GoDark XRPL integration
GODARK_XRPL_PARTNERS = [a.strip().lower() for a in os.getenv("GODARK_XRPL_PARTNERS", "").split(",") if a.strip()]
GODARK_XRPL_DEST_TAGS = [int(x.strip()) for x in os.getenv("GODARK_XRPL_DEST_TAGS", "").split(",") if x.strip().isdigit()]
GODARK_ETH_PARTNERS = [a.strip().lower() for a in os.getenv("GODARK_ETH_PARTNERS", "").split(",") if a.strip()]
ARKHAM_API_KEY = os.getenv("ARKHAM_API_KEY", "")
GODARK_DYNAMIC_REFRESH_SECONDS = int(os.getenv("GODARK_DYNAMIC_REFRESH_SECONDS", "3600"))

# Trustline watcher configuration
TRUSTLINE_WATCHED_ISSUERS = [a.strip() for a in os.getenv("TRUSTLINE_WATCHED_ISSUERS", "").split(",") if a.strip()]
GODARK_TRUSTLINE_MIN_VALUE = float(os.getenv("GODARK_TRUSTLINE_MIN_VALUE", "10000000"))
MONSTER_TRUSTLINE_THRESHOLD = float(os.getenv("MONSTER_TRUSTLINE_THRESHOLD", "100000000"))

# Ethereum GoDark prep scanner
ENABLE_GODARK_ETH_SCANNER = os.getenv("ENABLE_GODARK_ETH_SCANNER", "true").lower() == "true"
