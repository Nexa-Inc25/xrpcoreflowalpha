import os
from pathlib import Path
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        try:
            with env_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip()
                    if key and key not in os.environ:
                        os.environ[key] = val
        except Exception:
            pass

APP_ENV = os.getenv("APP_ENV", "dev")
DISABLE_EQUITY_FALLBACK = os.getenv("DISABLE_EQUITY_FALLBACK", "false").lower() == "true"
APP_VERSION = os.getenv("APP_VERSION", "1.0.0")

XRPL_WSS = os.getenv("XRPL_WSS", "")
ALCHEMY_WS_URL = os.getenv("ALCHEMY_WS_URL", "")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
DATABENTO_API_KEY = os.getenv("DATABENTO_API_KEY", "")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY", "")
NANSEN_API_KEY = os.getenv("NANSEN_API_KEY", "")
DUNE_API_KEY = os.getenv("DUNE_API_KEY", "")
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
POSTGRES_SSLMODE = os.getenv("POSTGRES_SSLMODE", "require")
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

# Renegade ZK dark pool detection (Ethereum)
RENEGADE_VERIFIER = os.getenv("RENEGADE_VERIFIER", "").lower()
RENEGADE_MANAGER = os.getenv("RENEGADE_MANAGER", "").lower()

# Penumbra shielded pool detection (Cosmos)
PENUMBRA_UNSHIELD_MIN_USD = float(os.getenv("PENUMBRA_UNSHIELD_MIN_USD", "10000000"))

# Secret Network shielded pool detection (Cosmos)
SECRET_UNSHIELD_MIN_USD = float(os.getenv("SECRET_UNSHIELD_MIN_USD", "5000000"))

# Execution stubs (disabled by default)
EXECUTION_ENABLED = os.getenv("EXECUTION_ENABLED", "false").lower() == "true"
EXECUTION_DRY_RUN = os.getenv("EXECUTION_DRY_RUN", "true").lower() == "true"
EXECUTION_MAX_SLIPPAGE_PCT = float(os.getenv("EXECUTION_MAX_SLIPPAGE_PCT", "0.5"))

# Risk controls
RISK_MAX_PCT_OF_SIGNAL = float(os.getenv("RISK_MAX_PCT_OF_SIGNAL", "1.0"))
RISK_DAILY_PNL_USD = float(os.getenv("RISK_DAILY_PNL_USD", "100000"))
RISK_MAX_VOL_BPS = int(os.getenv("RISK_MAX_VOL_BPS", "300"))

# Execution circuit breaker
CIRCUIT_BREAKER_LOSSES = int(os.getenv("CIRCUIT_BREAKER_LOSSES", "3"))
CIRCUIT_BREAKER_COOLDOWN_SECONDS = int(os.getenv("CIRCUIT_BREAKER_COOLDOWN_SECONDS", "3600"))

# ML inference circuit breaker
ML_CIRCUIT_BREAKER_FAILURES = int(os.getenv("ML_CIRCUIT_BREAKER_FAILURES", "5"))
ML_CIRCUIT_BREAKER_COOLDOWN_SECONDS = int(os.getenv("ML_CIRCUIT_BREAKER_COOLDOWN_SECONDS", "1800"))
ML_CIRCUIT_BREAKER_ENABLED = os.getenv("ML_CIRCUIT_BREAKER_ENABLED", "true").lower() == "true"

# RWA AMM monitor
RWA_AMM_CHANGE_THRESHOLD_PCT = float(os.getenv("RWA_AMM_CHANGE_THRESHOLD_PCT", "5"))

# DEX orderbook pairs monitor
DEX_ORDERBOOK_PAIRS = [p.strip() for p in os.getenv("DEX_ORDERBOOK_PAIRS", "XRP/USD.rhub,XRP/USDC.rhub").split(",") if p.strip()]

# SDUI surge detection
SURGE_WINDOW_SECONDS = int(os.getenv("SURGE_WINDOW_SECONDS", "300"))
SURGE_BURST_COUNT = int(os.getenv("SURGE_BURST_COUNT", "3"))
SURGE_CONFIDENCE_THRESHOLD = int(os.getenv("SURGE_CONFIDENCE_THRESHOLD", "90"))

# Solana HumidiFi dark AMM scanner
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "")
HUMIDIFI_PROGRAM_IDS = [p.strip() for p in os.getenv("HUMIDIFI_PROGRAM_IDS", "").split(",") if p.strip()]
SOLANA_POLL_SECONDS = int(os.getenv("SOLANA_POLL_SECONDS", "12"))
SOLANA_BACKOFF_MAX = int(os.getenv("SOLANA_BACKOFF_MAX", "60"))
SOLANA_PAGE_MAX = int(os.getenv("SOLANA_PAGE_MAX", "3"))

# On-chain subscriptions (treasuries and prices)
SOL_TREASURY = os.getenv("SOL_TREASURY", "")
SOL_USDC_MINT = os.getenv("SOL_USDC_MINT", "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
ETH_TREASURY = os.getenv("ETH_TREASURY", "")
ETH_USDC_ADDRESS = os.getenv("ETH_USDC_ADDRESS", "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48")
ONCHAIN_PRO_SOL_MONTHLY = float(os.getenv("ONCHAIN_PRO_SOL_MONTHLY", "0.5"))
ONCHAIN_PRO_SOL_ANNUAL = float(os.getenv("ONCHAIN_PRO_SOL_ANNUAL", "5.4"))
ONCHAIN_INST_SOL_MONTHLY = float(os.getenv("ONCHAIN_INST_SOL_MONTHLY", "5.0"))
ONCHAIN_INST_SOL_ANNUAL = float(os.getenv("ONCHAIN_INST_SOL_ANNUAL", "54.0"))
ONCHAIN_PRO_ETH_MONTHLY = float(os.getenv("ONCHAIN_PRO_ETH_MONTHLY", "0.018"))
ONCHAIN_PRO_ETH_ANNUAL = float(os.getenv("ONCHAIN_PRO_ETH_ANNUAL", "0.194"))
ONCHAIN_INST_ETH_MONTHLY = float(os.getenv("ONCHAIN_INST_ETH_MONTHLY", "0.18"))
ONCHAIN_INST_ETH_ANNUAL = float(os.getenv("ONCHAIN_INST_ETH_ANNUAL", "1.94"))
ONCHAIN_PRO_USDC_MONTHLY = float(os.getenv("ONCHAIN_PRO_USDC_MONTHLY", "49.0"))
ONCHAIN_INST_USDC_MONTHLY = float(os.getenv("ONCHAIN_INST_USDC_MONTHLY", "499.0"))
ONCHAIN_POLL_SECONDS = int(os.getenv("ONCHAIN_POLL_SECONDS", "12"))
ONCHAIN_BACKOFF_MAX = int(os.getenv("ONCHAIN_BACKOFF_MAX", "60"))

# Push notifications (APNs/FCM)
APNS_KEY_ID = os.getenv("APNS_KEY_ID", "")
APNS_TEAM_ID = os.getenv("APNS_TEAM_ID", "")
APNS_AUTH_KEY_P8 = os.getenv("APNS_AUTH_KEY_P8", "")  # p8 contents or path
APNS_TOPIC = os.getenv("APNS_TOPIC", "")
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY", "")

# DarkScore selector set (top-8; index 7 is 'other' client-side)
DARKSCORE_TOP8_SELECTORS = [
    s.strip().lower() for s in os.getenv(
        "DARKSCORE_TOP8_SELECTORS",
        "0x010ffc9a,0x91d14854,0x637e89c7,0x2e16c2bc,0x7a2b6e7f,0x5f8a1e0a,0x4c6f6972"
    ).split(",") if s.strip()
]

# Billing (Stripe)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_PRO_MONTHLY = os.getenv("STRIPE_PRICE_PRO_MONTHLY", "")
STRIPE_PRICE_INSTITUTIONAL_MONTHLY = os.getenv("STRIPE_PRICE_INSTITUTIONAL_MONTHLY", "")
STRIPE_PRICE_PRO_ANNUAL = os.getenv("STRIPE_PRICE_PRO_ANNUAL", "")
STRIPE_PRICE_INSTITUTIONAL_ANNUAL = os.getenv("STRIPE_PRICE_INSTITUTIONAL_ANNUAL", "")
STRIPE_SUCCESS_URL = os.getenv("STRIPE_SUCCESS_URL", "")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL", "")

# Local dev convenience
LOCAL_LAN_IP = os.getenv("LOCAL_LAN_IP", "")

# Admin portal
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")

# CORS (for cross-domain web clients, e.g., www -> api)
_CORS_ORIGINS_RAW = [o.strip() for o in os.getenv("CORS_ALLOW_ORIGINS", "*").split(",") if o.strip()]
CORS_ALLOW_ORIGINS = ["*"] if _CORS_ORIGINS_RAW == ["*"] else _CORS_ORIGINS_RAW
CORS_ALLOW_CREDENTIALS = os.getenv("CORS_ALLOW_CREDENTIALS", "true").lower() == "true"
CORS_ALLOW_METHODS = [m.strip().upper() for m in os.getenv("CORS_ALLOW_METHODS", "*").split(",") if m.strip()]
CORS_ALLOW_HEADERS = [h.strip() for h in os.getenv("CORS_ALLOW_HEADERS", "*").split(",") if h.strip()]

# Telegram alerts (Redis -> Telegram worker)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_MIN_CONFIDENCE = int(os.getenv("TELEGRAM_MIN_CONFIDENCE", "85"))
