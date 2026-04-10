-- Migration 009: Seeking Alpha Market News (SA-R1)
-- PostgreSQL 17+ (self-hosted pgvector Docker)
--
-- Recent market-news feed storage. This is metadata-first and
-- intentionally separate from Alpha Picks article storage.

CREATE TABLE IF NOT EXISTS sa_market_news (
    id BIGSERIAL PRIMARY KEY,
    news_id VARCHAR(40) NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TIMESTAMPTZ,
    published_text TEXT,
    tickers TEXT[] DEFAULT '{}',
    category VARCHAR(80),
    summary TEXT,
    comments_count INTEGER DEFAULT 0,
    raw_data JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(news_id)
);

CREATE INDEX IF NOT EXISTS idx_sa_market_news_published ON sa_market_news(published_at DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_sa_market_news_tickers ON sa_market_news USING GIN(tickers);
CREATE INDEX IF NOT EXISTS idx_sa_market_news_fts ON sa_market_news
    USING GIN(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(summary, '')));
