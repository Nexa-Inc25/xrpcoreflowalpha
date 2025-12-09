-- Database setup for zkalphaflow
-- Creates tables for signals, flows, and analytics

-- Signals table for dark flow detection
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    type VARCHAR(50) NOT NULL,
    source VARCHAR(100),
    asset VARCHAR(50),
    value JSONB,
    confidence FLOAT,
    processed BOOLEAN DEFAULT FALSE
);

-- Flows table for tracking large transactions
CREATE TABLE IF NOT EXISTS flows (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    tx_hash VARCHAR(255) UNIQUE,
    from_address VARCHAR(255),
    to_address VARCHAR(255),
    asset VARCHAR(50),
    amount NUMERIC,
    value_usd NUMERIC,
    venue VARCHAR(100),
    flow_type VARCHAR(50),
    metadata JSONB
);

-- Analytics table for ML training data
CREATE TABLE IF NOT EXISTS analytics (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    asset VARCHAR(50),
    price NUMERIC,
    volume NUMERIC,
    volatility FLOAT,
    hmm_state VARCHAR(50),
    fourier_score FLOAT,
    prophet_prediction NUMERIC,
    actual_price NUMERIC,
    metadata JSONB
);

-- Correlations table for multi-asset tracking
CREATE TABLE IF NOT EXISTS correlations (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    asset1 VARCHAR(50),
    asset2 VARCHAR(50),
    correlation FLOAT,
    timeframe VARCHAR(20),
    method VARCHAR(50),
    metadata JSONB
);

-- User preferences (for Pro tier features)
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    preferences JSONB,
    subscription_tier VARCHAR(50) DEFAULT 'basic',
    slack_webhook VARCHAR(500),
    alerts_enabled BOOLEAN DEFAULT TRUE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(type);
CREATE INDEX IF NOT EXISTS idx_flows_timestamp ON flows(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_flows_asset ON flows(asset);
CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_analytics_asset ON analytics(asset);
CREATE INDEX IF NOT EXISTS idx_correlations_assets ON correlations(asset1, asset2);

-- Grant permissions (adjust user as needed)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mike;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mike;
