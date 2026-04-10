-- Migration 010: Seeking Alpha Market News detail body
-- PostgreSQL 17+ (self-hosted pgvector Docker)

ALTER TABLE sa_market_news
    ADD COLUMN IF NOT EXISTS body_markdown TEXT,
    ADD COLUMN IF NOT EXISTS detail_fetched_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_sa_market_news_detail_fetched
    ON sa_market_news(detail_fetched_at DESC NULLS LAST);
