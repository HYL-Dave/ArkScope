-- =============================================================================
-- MindfulRL-Intraday: Supabase Schema Initialization
-- =============================================================================
-- Run this in Supabase Dashboard > SQL Editor
-- Or via: psql "$SUPABASE_DB_URL" -f sql/001_init_schema.sql
-- =============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;         -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- trigram for text search

-- =============================================================================
-- Core Tables
-- =============================================================================

-- News articles (scored by LLM)
CREATE TABLE IF NOT EXISTS news (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(10)   NOT NULL,
    title         TEXT          NOT NULL,
    description   TEXT,
    url           TEXT,
    publisher     VARCHAR(200),
    source        VARCHAR(50)   NOT NULL,         -- 'ibkr', 'polygon', 'finnhub'
    published_at  TIMESTAMPTZ   NOT NULL,
    sentiment_score SMALLINT,                     -- 1-5
    risk_score      SMALLINT,                     -- 1-5
    scored_model  VARCHAR(50),                    -- 'haiku', 'gpt_5', etc.
    embedding     VECTOR(1536),                   -- for future semantic search
    article_hash  VARCHAR(64)   UNIQUE NOT NULL,  -- dedup key (SHA-256 of title+ticker+date)
    created_at    TIMESTAMPTZ   DEFAULT NOW()
);

-- Intraday & daily prices
CREATE TABLE IF NOT EXISTS prices (
    id        BIGSERIAL PRIMARY KEY,
    ticker    VARCHAR(10)      NOT NULL,
    datetime  TIMESTAMPTZ      NOT NULL,
    interval  VARCHAR(10)      NOT NULL,  -- '15min', '1h', '1d'
    open      DOUBLE PRECISION,
    high      DOUBLE PRECISION,
    low       DOUBLE PRECISION,
    close     DOUBLE PRECISION,
    volume    BIGINT,
    UNIQUE(ticker, datetime, interval)
);

-- Implied volatility history
CREATE TABLE IF NOT EXISTS iv_history (
    id         BIGSERIAL PRIMARY KEY,
    ticker     VARCHAR(10)      NOT NULL,
    date       DATE             NOT NULL,
    atm_iv     DOUBLE PRECISION,
    hv_30d     DOUBLE PRECISION,
    vrp        DOUBLE PRECISION,  -- volatility risk premium = atm_iv - hv_30d
    spot_price DOUBLE PRECISION,
    num_quotes INTEGER,
    UNIQUE(ticker, date)
);

-- Fundamentals snapshots (JSONB for flexibility)
CREATE TABLE IF NOT EXISTS fundamentals (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(10) NOT NULL,
    snapshot_date DATE        NOT NULL,
    data          JSONB       NOT NULL,  -- full ReportSnapshot JSON
    UNIQUE(ticker, snapshot_date)
);

-- Generated trading signals (audit trail)
CREATE TABLE IF NOT EXISTS signals (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(10),
    sector          VARCHAR(50),
    action          VARCHAR(20),       -- 'BUY', 'SELL', 'HOLD', 'NEUTRAL'
    confidence      DOUBLE PRECISION,
    composite_score DOUBLE PRECISION,
    risk_level      SMALLINT,          -- 1-5
    reasoning       TEXT,
    factors         JSONB,
    strategy        VARCHAR(50),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Agent query log (for cost tracking + replay)
CREATE TABLE IF NOT EXISTS agent_queries (
    id          BIGSERIAL PRIMARY KEY,
    question    TEXT         NOT NULL,
    answer      TEXT,
    provider    VARCHAR(20),           -- 'openai', 'anthropic'
    model       VARCHAR(50),
    tools_used  JSONB,                 -- ["get_ticker_news", "get_iv_analysis"]
    duration_ms INTEGER,
    tokens_in   INTEGER,
    tokens_out  INTEGER,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- =============================================================================
-- Indexes
-- =============================================================================

-- News: primary query pattern is (ticker, date range)
CREATE INDEX IF NOT EXISTS idx_news_ticker_date
    ON news(ticker, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_news_source
    ON news(source);

-- Text search on title
CREATE INDEX IF NOT EXISTS idx_news_title_trgm
    ON news USING gin(title gin_trgm_ops);

-- Embedding similarity search (create after importing data, needs >= 100 rows)
-- CREATE INDEX idx_news_embedding ON news USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Prices: primary query pattern is (ticker, interval, datetime range)
CREATE INDEX IF NOT EXISTS idx_prices_ticker_interval_dt
    ON prices(ticker, interval, datetime DESC);

-- IV History
CREATE INDEX IF NOT EXISTS idx_iv_ticker_date
    ON iv_history(ticker, date DESC);

-- Signals
CREATE INDEX IF NOT EXISTS idx_signals_ticker_date
    ON signals(ticker, created_at DESC);

-- Agent queries
CREATE INDEX IF NOT EXISTS idx_queries_date
    ON agent_queries(created_at DESC);

-- =============================================================================
-- Row Level Security (optional, enable if exposing via Supabase client)
-- =============================================================================
-- By default, tables are accessible with service_role key.
-- Enable RLS only if you need anon/authenticated access control.

-- ALTER TABLE news ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE prices ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE iv_history ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE fundamentals ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE signals ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE agent_queries ENABLE ROW LEVEL SECURITY;

-- Read-only policy for anon users (uncomment if needed):
-- CREATE POLICY "anon_read_news" ON news FOR SELECT TO anon USING (true);
-- CREATE POLICY "anon_read_prices" ON prices FOR SELECT TO anon USING (true);

-- =============================================================================
-- Helper functions
-- =============================================================================

-- Get latest N news for a ticker
CREATE OR REPLACE FUNCTION get_recent_news(
    p_ticker VARCHAR(10),
    p_days INTEGER DEFAULT 30,
    p_limit INTEGER DEFAULT 100
)
RETURNS SETOF news
LANGUAGE sql STABLE
AS $$
    SELECT *
    FROM news
    WHERE ticker = p_ticker
      AND published_at >= NOW() - (p_days || ' days')::INTERVAL
    ORDER BY published_at DESC
    LIMIT p_limit;
$$;

-- Get latest price bars for a ticker
CREATE OR REPLACE FUNCTION get_recent_prices(
    p_ticker VARCHAR(10),
    p_interval VARCHAR(10) DEFAULT '15min',
    p_days INTEGER DEFAULT 30
)
RETURNS SETOF prices
LANGUAGE sql STABLE
AS $$
    SELECT *
    FROM prices
    WHERE ticker = p_ticker
      AND interval = p_interval
      AND datetime >= NOW() - (p_days || ' days')::INTERVAL
    ORDER BY datetime ASC;
$$;

-- Summary stats for a ticker's news sentiment
CREATE OR REPLACE FUNCTION news_sentiment_summary(
    p_ticker VARCHAR(10),
    p_days INTEGER DEFAULT 7
)
RETURNS TABLE(
    total_articles BIGINT,
    avg_sentiment NUMERIC,
    avg_risk NUMERIC,
    bullish_count BIGINT,
    bearish_count BIGINT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        COUNT(*) AS total_articles,
        ROUND(AVG(sentiment_score)::NUMERIC, 2) AS avg_sentiment,
        ROUND(AVG(risk_score)::NUMERIC, 2) AS avg_risk,
        COUNT(*) FILTER (WHERE sentiment_score >= 4) AS bullish_count,
        COUNT(*) FILTER (WHERE sentiment_score <= 2) AS bearish_count
    FROM news
    WHERE ticker = p_ticker
      AND published_at >= NOW() - (p_days || ' days')::INTERVAL
      AND sentiment_score IS NOT NULL;
$$;