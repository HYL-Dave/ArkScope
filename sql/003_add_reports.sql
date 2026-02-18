-- =============================================================================
-- Migration 003: Research Reports table
-- =============================================================================
-- Run: psql $DATABASE_URL -f sql/003_add_reports.sql
-- Stores metadata for agent-generated research reports.
-- Full report content lives in data/reports/*.md (Markdown files).

CREATE TABLE IF NOT EXISTS research_reports (
    id              BIGSERIAL PRIMARY KEY,
    title           TEXT NOT NULL,
    tickers         TEXT[],                         -- {"AFRM", "NVDA"}
    report_type     VARCHAR(50),                    -- entry_analysis, sector_review, earnings_review
    summary         TEXT,                           -- 1-2 sentence conclusion
    conclusion      VARCHAR(20),                    -- BUY, HOLD, SELL, WATCH, NEUTRAL
    confidence      DOUBLE PRECISION,               -- 0-1
    provider        VARCHAR(20),                    -- openai, anthropic
    model           VARCHAR(50),                    -- claude-opus-4-6, gpt-5.2
    file_path       TEXT,                           -- data/reports/2026-02-18_AFRM_a3810ae0.md
    tools_used      JSONB,                          -- ["get_ticker_news", "get_analyst_consensus"]
    tool_calls      INTEGER,
    duration_seconds DOUBLE PRECISION,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Search by tickers (GIN for array containment: WHERE tickers @> ARRAY['NVDA'])
CREATE INDEX IF NOT EXISTS idx_reports_tickers
    ON research_reports USING GIN (tickers);

-- Browse by date
CREATE INDEX IF NOT EXISTS idx_reports_date
    ON research_reports (created_at DESC);

-- Filter by type
CREATE INDEX IF NOT EXISTS idx_reports_type
    ON research_reports (report_type);