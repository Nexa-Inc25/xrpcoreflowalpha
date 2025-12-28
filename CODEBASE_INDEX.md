# xrpcoreflowalpha Codebase Index

## Overview
**Project Name**: xrpcoreflowalpha (also known as zkalphaflow)  
**Purpose**: Multi-asset correlation and dark flow detection platform for institutional trading  
**Architecture**: FastAPI backend + Next.js frontend + background workers  
**Deployment**: DigitalOcean App Platform (production) + Docker containers  

---

## 🏗️ System Architecture

### Core Components
- **Frontend**: Next.js web app (`apps/web/`) with Clerk authentication
- **Backend**: FastAPI application (`app/main.py`) with 25+ API endpoints
- **Database**: PostgreSQL with TimescaleDB extension for time-series data
- **Workers**: Background processing for data ingestion and ML training
- **Monitoring**: Prometheus metrics + Sentry error tracking

### Data Flow
```
Real-time Data Sources → Scanners → Redis Pub/Sub → FastAPI → PostgreSQL
                                           ↓
WebSocket/SSE → Next.js Frontend + Telegram Bot
                                           ↓
ML Models → Prediction Engine → Alerts & Signals
```

---

## 📁 Directory Structure

### Core Application (`app/`)
- `main.py`: FastAPI application entry point with startup event handlers
- `config.py`: Environment configuration and API key management
- `config_fixes.py`: Production configuration fixes
- `redis_utils.py`: Redis connection utilities

### API Endpoints (`api/`)
**74 total endpoints** organized by functionality:

#### Core APIs
- `health.py`: Health checks and system status
- `ui.py`: Main UI endpoints and WebSocket/SSE streams
- `dashboard.py`: Dashboard data and flow state
- `analytics.py`: Performance analytics and forecasting

#### Financial Data
- `flows.py`: Flow tracking and detection
- `correlations.py`: Multi-asset correlation analysis
- `latency.py`: Exchange latency monitoring and HFT detection
- `tuned_analytics.py`: Advanced analytics and forecasting

#### Wallet & Onchain
- `wallets.py`: Wallet balance and transaction tracking
- `wallet_analysis.py`: Institutional wallet analysis
- `onchain.py`: Blockchain data endpoints

#### Business Logic
- `billing.py`: Stripe subscription management
- `user.py`: User preferences and settings
- `notify.py`: Push notification management
- `qr.py`: QR code generation for payments

#### Administration
- `admin.py`: API key management
- `monitoring.py`: System monitoring and diagnostics
- `scanner_health.py`: Scanner status monitoring
- `db_health.py`: Database health checks

### Data Scanners (`scanners/`)
**19 scanner modules** for real-time data ingestion:

#### Blockchain Scanners
- `xrpl_scanner.py`: XRPL ledger monitoring via WebSocket
- `zk_scanner.py`: Ethereum GoDark detection via Alchemy
- `solana_humidifi.py`: Solana DEX monitoring
- `xrpl_trustline_watcher.py`: XRPL trustline changes
- `xrpl_orderbook_monitor.py`: XRPL orderbook depth
- `rwa_amm_liquidity_monitor.py`: RWA AMM liquidity tracking

#### Market Data Scanners
- `whale_alert_scanner.py`: Large transaction tracking ($1M+)
- `futures_scanner.py`: Futures market data (ES, NQ, VIX, Gold, Oil)
- `forex_scanner.py`: Forex data via Alpha Vantage
- `equities_scanner.py`: Equity market data
- `dune_scanner.py`: DEX volume and DeFi analytics
- `nansen_scanner.py`: Smart money labeling

#### Dark Pool Scanners
- `godark_eth_scanner.py`: Ethereum dark pool detection
- `secret_detector.py`: Secret network monitoring
- `renegade_detector.py`: Renegade DEX monitoring
- `penumbra_detector.py`: Penumbra shielded transactions

### ML & Prediction Systems (`ml/` + `predictors/`)
**21 ML modules** for advanced analytics:

#### Core ML Models (`ml/`)
- `fourier_flow_analyzer.py`: Fourier transform analysis for periodic patterns
- `prophet_flow_tuner.py`: Time-series forecasting with Prophet
- `hmm_flow_predictor.py`: Hidden Markov Models for regime detection
- `latency_xgboost.py`: XGBoost models for latency prediction
- `smart_flow_forecaster.py`: Ensemble forecasting models
- `flow_predictor.py`: GRU neural networks for flow prediction
- `impact_predictor.py`: Price impact modeling
- `fourier_markov_prophet.py`: Combined Fourier + Markov + Prophet

#### Predictors (`predictors/`)
- `frequency_fingerprinter.py`: Algorithm fingerprinting via frequency analysis
- `signal_scorer.py`: Signal confidence scoring
- `correlation_engine.py`: Cross-market correlation analysis
- `wavelet_urgency.py`: Wavelet transform for market urgency detection
- `latency_pinger.py`: Real-time latency monitoring
- `yahoo_macro_tracker.py`: Yahoo Finance equity data
- `polygon_macro_tracker.py`: Polygon.io market data
- `alpha_macro_tracker.py`: Alpha Vantage data integration
- `databento_macro_tracker.py`: High-frequency futures data
- `xrp_iso_predictor.py`: XRP isolation forest anomaly detection

### Background Workers (`workers/`)
**7 worker modules** for background processing:

- `outcome_checker.py`: Signal outcome validation
- `scanner_monitor.py`: Scanner health monitoring
- `ledger_monitor.py`: XRPL ledger drift monitoring
- `slack_latency_bot.py`: Latency anomaly alerts
- `educator_bot.py`: Trading education content
- `correlation_worker.py`: Cross-market correlation processing

### Database Layer (`db/`)
- `connection.py`: Async PostgreSQL connection management
- `schema.py`: Database schema and migrations
- `signals.py`: Signal data access layer

### Observability (`observability/`)
- `metrics.py`: Prometheus metrics definitions
- `tracing.py`: Distributed tracing
- `impact.py`: Market impact analysis

### Notifications (`notifications/`)
- `push_worker.py`: Push notification delivery
- `telegram_worker.py`: Telegram bot alerts

### Billing (`billing/`)
- `stripe_handler.py`: Stripe payment processing
- `onchain_watchers.py`: Onchain payment monitoring

### Utilities (`utils/`)
- `price.py`: Cryptocurrency price feeds
- `retry.py`: Async retry decorators
- `tx_validate.py`: Transaction validation
- `validate.py`: Data validation utilities

---

## 🔑 Key Features

### Real-Time Data Sources
- **XRPL**: Live ledger monitoring (wss://s1.ripple.com/)
- **Ethereum**: Alchemy WebSocket for mempool monitoring
- **Whale Alert**: Large transaction tracking ($1M+)
- **Alpha Vantage**: Futures, forex, equities (600 calls/min)
- **Polygon.io**: Equities and options data
- **Dune Analytics**: DEX volume analytics

### ML Capabilities
- **Frequency Analysis**: FFT-based algorithm fingerprinting
- **Time Series Forecasting**: Prophet models for price prediction
- **Anomaly Detection**: Isolation forests and statistical methods
- **Correlation Analysis**: Cross-market correlation detection
- **Latency Prediction**: XGBoost models for HFT detection

### Institutional Features
- **Wallet Analysis**: Institutional wallet tracking and labeling
- **Algo Fingerprinting**: Known trading algorithm signatures
- **Dark Pool Detection**: GoDark and other dark liquidity monitoring
- **Flow Analysis**: Large flow detection and impact prediction

### Business Features
- **Authentication**: Clerk-based user management
- **Billing**: Stripe subscription management
- **Notifications**: Push notifications and Telegram alerts
- **QR Payments**: Payment QR code generation

---

## 🚀 Deployment & Configuration

### Production Environment
- **Platform**: DigitalOcean App Platform
- **Region**: NYC
- **Containers**: 3 services (web, api, worker)
- **Database**: Managed PostgreSQL + Redis
- **Domains**: zkalphaflow.com, api.zkalphaflow.com

### Configuration Files
- `current_spec.yaml`: DigitalOcean app specification
- `docker-compose.prod.yml`: Production Docker compose
- `Dockerfile`: Multi-stage Python build
- `requirements.txt`: Python dependencies (40+ packages)

### Environment Variables
**Critical APIs** (required for functionality):
- `XRPL_WSS`: XRPL WebSocket URL
- `ALCHEMY_WS_URL`: Ethereum WebSocket
- `WHALE_ALERT_API_KEY`: Large transaction tracking
- `ALPHA_VANTAGE_API_KEY`: Market data
- `POLYGON_API_KEY`: Equities data

**Optional APIs** (enhance functionality):
- `FINNHUB_API_KEY`: Additional market data
- `COINGECKO_API_KEY`: Price feeds
- `DUNE_API_KEY`: DeFi analytics

---

## 📊 Database Schema

### Signals Table
```sql
signals (
    id, signal_id, type, sub_type, network, summary,
    confidence, predicted_direction, predicted_move_pct,
    amount_usd, amount_native, native_symbol,
    entry_price_xrp, entry_price_eth, entry_price_btc,
    source_address, dest_address, tx_hash, tags, features,
    detected_at, created_at
)
```

### Latency Events Table
```sql
latency_events (
    id, event_id, exchange, symbol, round_trip_ms,
    is_anomaly, anomaly_score, order_book_imbalance,
    bid_depth, ask_depth, spread_bps, cancellation_rate,
    matched_signature, is_hft, correlation_xrpl, features,
    detected_at
)
```

### Analytics Cache
- Performance metrics caching
- Cross-validation results
- ML model training logs

---

## 🔄 Data Processing Pipeline

### Signal Processing
1. **Data Ingestion**: Scanners collect real-time data
2. **Signal Generation**: Raw data → structured signals
3. **Enrichment**: ML scoring and fingerprinting
4. **Correlation**: Cross-market analysis
5. **Storage**: PostgreSQL with time-series optimization
6. **Distribution**: Redis Pub/Sub to frontend + alerts

### ML Training Pipeline
1. **Data Collection**: Historical signal outcomes
2. **Feature Engineering**: Frequency analysis, correlations
3. **Model Training**: XGBoost, Prophet, Fourier analysis
4. **Validation**: Cross-validation and backtesting
5. **Deployment**: Live prediction serving

---

## 🔧 Development Workflow

### Local Development
```bash
# Backend
python -m uvicorn app.main:app --reload --port 8000

# Frontend
cd apps/web && npm run dev

# Worker
python -m worker.run
```

### Testing
- Integration tests in `test_*.py` files
- API endpoint testing
- ML model validation
- Scanner health monitoring

### Monitoring
- **Prometheus**: `/metrics` endpoint
- **Health Checks**: `/health` endpoints
- **Logs**: Structured logging with correlation IDs
- **Alerts**: Slack integration for anomalies

---

## 📈 Performance Targets

- **Detection Rate**: >75% for flows >$25M
- **Price Impact Correlation**: >2% within 15min
- **SSE Latency**: <100ms
- **API Response Time**: <500ms p95
- **Uptime**: 99.9% availability

---

## 🚨 Important Notes

1. **NO MOCK DATA**: All components require real API data
2. **Secrets Management**: Never commit API keys
3. **Production Focus**: Optimized for DigitalOcean deployment
4. **Real-time Priority**: WebSocket/SSE for live updates
5. **Institutional Grade**: Designed for hedge fund usage
6. **Multi-Asset Support**: XRP, BTC, ETH, SPY, Gold correlations

---

## 📚 Key Technical Decisions

### Architecture Choices
- **FastAPI**: High-performance async API framework
- **PostgreSQL + TimescaleDB**: Time-series optimized database
- **Redis Pub/Sub**: Real-time event distribution
- **Docker**: Containerized deployment
- **Prometheus**: Metrics collection

### ML Stack
- **scikit-learn**: Traditional ML algorithms
- **XGBoost**: Gradient boosting for predictions
- **Prophet**: Time-series forecasting
- **scipy**: Signal processing and FFT analysis
- **pandas/numpy**: Data manipulation

### Real-time Features
- **WebSocket/SSE**: Live data streaming
- **Async/Await**: Non-blocking I/O throughout
- **Pub/Sub Pattern**: Decoupled event processing
- **Circuit Breakers**: Fault-tolerant API calls

---

*This index was generated by analyzing the xrpcoreflowalpha codebase, originally developed on Windsurf and now indexed for completion.*
