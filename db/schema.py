"""
Database schema definitions and migrations for signal tracking.
"""
from db.connection import execute, fetchval

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Signals table: stores every detected signal with entry price
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(64) UNIQUE NOT NULL,  -- UUID or tx_hash
    type VARCHAR(32) NOT NULL,              -- xrp, zk, equity, futures, trustline
    sub_type VARCHAR(64),                   -- payment, ammdeposit, etc.
    network VARCHAR(16),                    -- eth, xrp, sol, etc.
    
    -- Signal data
    summary TEXT,
    confidence INTEGER,                     -- 0-100
    predicted_direction VARCHAR(8),         -- up, down, neutral
    predicted_move_pct REAL,                -- expected % move
    
    -- Value tracking
    amount_usd REAL,
    amount_native REAL,
    native_symbol VARCHAR(16),
    
    -- Entry price snapshot
    entry_price_xrp REAL,
    entry_price_eth REAL,
    entry_price_btc REAL,
    
    -- Metadata
    source_address VARCHAR(128),
    dest_address VARCHAR(128),
    tx_hash VARCHAR(128),
    tags TEXT[],
    features JSONB,
    
    -- Timestamps
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Outcomes table: tracks price at various intervals after signal
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(64) NOT NULL REFERENCES signals(signal_id) ON DELETE CASCADE,
    
    -- Interval tracking (1h, 4h, 12h, 24h)
    interval_hours INTEGER NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Actual prices at check time
    price_xrp REAL,
    price_eth REAL,
    price_btc REAL,
    
    -- Calculated outcomes
    xrp_change_pct REAL,
    eth_change_pct REAL,
    btc_change_pct REAL,
    
    -- Was the prediction correct?
    hit BOOLEAN,  -- NULL if not yet determined
    
    UNIQUE(signal_id, interval_hours)
);

-- Analytics cache table for pre-computed metrics
CREATE TABLE IF NOT EXISTS analytics_cache (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(64) UNIQUE NOT NULL,
    metric_value JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_signals_detected_at ON signals(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(type);
CREATE INDEX IF NOT EXISTS idx_signals_confidence ON signals(confidence);
CREATE INDEX IF NOT EXISTS idx_outcomes_signal_id ON signal_outcomes(signal_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_checked_at ON signal_outcomes(checked_at DESC);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


async def init_schema() -> bool:
    """Initialize the database schema. Returns True if successful."""
    try:
        # Check current schema version
        try:
            current = await fetchval("SELECT MAX(version) FROM schema_version")
        except Exception:
            current = None
        
        if current is not None and current >= SCHEMA_VERSION:
            print(f"[DB] Schema already at version {current}")
            return True
        
        # Apply schema
        await execute(SCHEMA_SQL)
        
        # Update version
        await execute(
            "INSERT INTO schema_version (version) VALUES ($1) ON CONFLICT (version) DO NOTHING",
            SCHEMA_VERSION
        )
        
        print(f"[DB] Schema initialized to version {SCHEMA_VERSION}")
        return True
        
    except Exception as e:
        print(f"[DB] Schema initialization failed: {e}")
        return False
