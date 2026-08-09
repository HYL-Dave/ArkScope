-- =============================================================================
-- ArkScope: PostgreSQL Schema Initialization
-- =============================================================================
-- Run via: psql "$DATABASE_URL" -f sql/001_init_schema.sql
-- Or auto-executed by Docker on first startup via /docker-entrypoint-initdb.d
-- =============================================================================

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS vector;         -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS pg_trgm;        -- trigram for text search

-- =============================================================================
-- Core Tables
-- =============================================================================

-- Raw news articles
CREATE TABLE IF NOT EXISTS news (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(10)   NOT NULL,
    title         TEXT          NOT NULL,
    description   TEXT,
    url           TEXT,
    publisher     VARCHAR(200),
    source        VARCHAR(50)   NOT NULL,         -- 'ibkr', 'polygon', 'finnhub'
    published_at  TIMESTAMPTZ   NOT NULL,
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

-- Fundamentals snapshots (JSONB for flexibility)
CREATE TABLE IF NOT EXISTS fundamentals (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(10) NOT NULL,
    snapshot_date DATE        NOT NULL,
    data          JSONB       NOT NULL,  -- full ReportSnapshot JSON
    UNIQUE(ticker, snapshot_date)
);

-- Agent query log (for cost tracking + replay)
CREATE TABLE IF NOT EXISTS agent_queries (
    id          BIGSERIAL PRIMARY KEY,
    question    TEXT         NOT NULL,
    answer      TEXT,
    provider    VARCHAR(20),           -- 'openai', 'anthropic'
    model       VARCHAR(50),
    tools_used  JSONB,                 -- ["get_ticker_news", "calculate_greeks"]
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

-- Agent queries
CREATE INDEX IF NOT EXISTS idx_queries_date
    ON agent_queries(created_at DESC);

-- =============================================================================
-- Row Level Security (optional, enable if exposing via REST API)
-- =============================================================================
-- By default, tables are accessible with the database user.
-- Enable RLS only if you need fine-grained access control.

-- ALTER TABLE news ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE prices ENABLE ROW LEVEL SECURITY;
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
