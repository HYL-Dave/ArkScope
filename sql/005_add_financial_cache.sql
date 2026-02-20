-- =============================================================================
-- Migration 005: Financial data cache table
-- =============================================================================
-- Run: psql $DATABASE_URL -f sql/005_add_financial_cache.sql
-- Caches API responses from paid data sources (Financial Datasets, etc.)
-- to avoid redundant API calls. Financial statements rarely change
-- (quarterly updates), so long TTLs are appropriate.

CREATE TABLE IF NOT EXISTS financial_data_cache (
    id          BIGSERIAL PRIMARY KEY,
    cache_key   VARCHAR(200) NOT NULL UNIQUE,  -- e.g. income_AAPL_quarterly
    source      VARCHAR(50) NOT NULL DEFAULT 'financial_datasets',
    ticker      VARCHAR(20) NOT NULL,
    data        JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ DEFAULT NOW(),
    expires_at  TIMESTAMPTZ NOT NULL
);

-- Primary lookup by cache key
CREATE INDEX IF NOT EXISTS idx_fin_cache_key
    ON financial_data_cache (cache_key);

-- Cleanup expired entries
CREATE INDEX IF NOT EXISTS idx_fin_cache_expires
    ON financial_data_cache (expires_at);

-- Browse by ticker
CREATE INDEX IF NOT EXISTS idx_fin_cache_ticker
    ON financial_data_cache (ticker);