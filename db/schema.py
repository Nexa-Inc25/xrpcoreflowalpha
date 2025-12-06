"""
Database schema definitions and migrations for signal tracking.
Works with both PostgreSQL and SQLite.
"""
from db.connection import execute, fetchval, is_sqlite

# Schema version for migrations
SCHEMA_VERSION = 1

# PostgreSQL schema
SCHEMA_SQL_PG = """
-- Signals table: stores every detected signal with entry price
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(64) UNIQUE NOT NULL,
    type VARCHAR(32) NOT NULL,
    sub_type VARCHAR(64),
    network VARCHAR(16),
    summary TEXT,
    confidence INTEGER,
    predicted_direction VARCHAR(8),
    predicted_move_pct REAL,
    amount_usd REAL,
    amount_native REAL,
    native_symbol VARCHAR(16),
    entry_price_xrp REAL,
    entry_price_eth REAL,
    entry_price_btc REAL,
    source_address VARCHAR(128),
    dest_address VARCHAR(128),
    tx_hash VARCHAR(128),
    tags TEXT[],
    features JSONB,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signal_outcomes (
    id BIGSERIAL PRIMARY KEY,
    signal_id VARCHAR(64) NOT NULL REFERENCES signals(signal_id) ON DELETE CASCADE,
    interval_hours INTEGER NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price_xrp REAL,
    price_eth REAL,
    price_btc REAL,
    xrp_change_pct REAL,
    eth_change_pct REAL,
    btc_change_pct REAL,
    hit BOOLEAN,
    UNIQUE(signal_id, interval_hours)
);

CREATE TABLE IF NOT EXISTS analytics_cache (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(64) UNIQUE NOT NULL,
    metric_value JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_signals_detected_at ON signals(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(type);
CREATE INDEX IF NOT EXISTS idx_signals_confidence ON signals(confidence);
CREATE INDEX IF NOT EXISTS idx_outcomes_signal_id ON signal_outcomes(signal_id);
CREATE INDEX IF NOT EXISTS idx_outcomes_checked_at ON signal_outcomes(checked_at DESC);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

# SQLite schema (simpler, no arrays/jsonb)
SCHEMA_SQL_SQLITE = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL,
    sub_type TEXT,
    network TEXT,
    summary TEXT,
    confidence INTEGER,
    predicted_direction TEXT,
    predicted_move_pct REAL,
    amount_usd REAL,
    amount_native REAL,
    native_symbol TEXT,
    entry_price_xrp REAL,
    entry_price_eth REAL,
    entry_price_btc REAL,
    source_address TEXT,
    dest_address TEXT,
    tx_hash TEXT,
    tags TEXT,
    features TEXT,
    detected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signal_outcomes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT NOT NULL,
    interval_hours INTEGER NOT NULL,
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    price_xrp REAL,
    price_eth REAL,
    price_btc REAL,
    xrp_change_pct REAL,
    eth_change_pct REAL,
    btc_change_pct REAL,
    hit INTEGER,
    UNIQUE(signal_id, interval_hours),
    FOREIGN KEY (signal_id) REFERENCES signals(signal_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analytics_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_name TEXT UNIQUE NOT NULL,
    metric_value TEXT NOT NULL,
    computed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_detected_at ON signals(detected_at);
CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(type);
CREATE INDEX IF NOT EXISTS idx_signals_confidence ON signals(confidence);
CREATE INDEX IF NOT EXISTS idx_outcomes_signal_id ON signal_outcomes(signal_id);
"""


async def init_schema() -> bool:
    """Initialize the database schema. Returns True if successful."""
    try:
        # Ensure pool is initialized first (this sets _use_sqlite flag)
        from db.connection import get_pool
        await get_pool()
        
        # Now determine which schema to use
        use_sqlite = is_sqlite()
        schema_sql = SCHEMA_SQL_SQLITE if use_sqlite else SCHEMA_SQL_PG
        
        # Check current schema version
        try:
            current = await fetchval("SELECT MAX(version) FROM schema_version")
        except Exception:
            current = None
        
        if current is not None and current >= SCHEMA_VERSION:
            print(f"[DB] Schema already at version {current} ({'SQLite' if use_sqlite else 'PostgreSQL'})")
            return True
        
        # Apply schema - for SQLite, execute each statement separately
        if use_sqlite:
            for stmt in schema_sql.split(';'):
                stmt = stmt.strip()
                if stmt:
                    await execute(stmt)
        else:
            await execute(schema_sql)
        
        # Update version
        if use_sqlite:
            await execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                SCHEMA_VERSION
            )
        else:
            await execute(
                "INSERT INTO schema_version (version) VALUES ($1) ON CONFLICT (version) DO NOTHING",
                SCHEMA_VERSION
            )
        
        print(f"[DB] Schema initialized to version {SCHEMA_VERSION} ({'SQLite' if use_sqlite else 'PostgreSQL'})")
        return True
        
    except Exception as e:
        print(f"[DB] Schema initialization failed: {e}")
        return False
