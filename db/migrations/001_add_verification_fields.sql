-- Migration 001: Add verification and explorer fields to signals table
-- Run this on PostgreSQL after initial schema creation

-- Add explorer URL fields
ALTER TABLE signals ADD COLUMN IF NOT EXISTS explorer_url TEXT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS explorer_urls JSONB DEFAULT '{}';

-- Add verification status
ALTER TABLE signals ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS verified_at TIMESTAMP;

-- Add ledger tracking for XRPL signals
ALTER TABLE signals ADD COLUMN IF NOT EXISTS ledger_index BIGINT;
ALTER TABLE signals ADD COLUMN IF NOT EXISTS ledger_drift INTEGER;

-- Add index for faster verification queries
CREATE INDEX IF NOT EXISTS idx_signals_verified ON signals(verified) WHERE verified = TRUE;
CREATE INDEX IF NOT EXISTS idx_signals_network ON signals(network);
CREATE INDEX IF NOT EXISTS idx_signals_type_confidence ON signals(type, confidence DESC);

-- Add analytics cache improvements
ALTER TABLE analytics_cache ADD COLUMN IF NOT EXISTS explorer_enabled BOOLEAN DEFAULT TRUE;

-- Insert schema version
INSERT INTO schema_version (version, applied_at) 
VALUES ('001_add_verification_fields', NOW())
ON CONFLICT DO NOTHING;

-- Verification complete
SELECT 'Migration 001 applied successfully' AS status;
