-- Migration 008: SA Alpha Picks Articles + Comments (Phase 11c-v3)
-- PostgreSQL 17+ (self-hosted pgvector Docker)
--
-- Independent article storage with comment tree support.
-- Articles are the canonical source; sa_alpha_picks.detail_report
-- is auto-synced from matching analysis/removal articles.

-- ============================================================
-- Articles table
-- ============================================================

CREATE TABLE IF NOT EXISTS sa_articles (
    id BIGSERIAL PRIMARY KEY,
    article_id VARCHAR(20) NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    ticker VARCHAR(20),
    author VARCHAR(200),
    published_date DATE,
    article_type VARCHAR(30),
    body_markdown TEXT,
    comments_count INTEGER DEFAULT 0,
    detail_fetched_at TIMESTAMPTZ,
    comments_fetched_at TIMESTAMPTZ,
    raw_data JSONB,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id)
);

CREATE INDEX IF NOT EXISTS idx_sa_articles_ticker ON sa_articles(ticker);
CREATE INDEX IF NOT EXISTS idx_sa_articles_published ON sa_articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_sa_articles_type ON sa_articles(article_type);
CREATE INDEX IF NOT EXISTS idx_sa_articles_body_fts ON sa_articles
    USING GIN(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(body_markdown, '')));

-- ============================================================
-- Article comments table (with nesting support)
-- ============================================================

CREATE TABLE IF NOT EXISTS sa_article_comments (
    id BIGSERIAL PRIMARY KEY,
    article_id VARCHAR(20) NOT NULL REFERENCES sa_articles(article_id),
    comment_id VARCHAR(30) NOT NULL,
    parent_comment_id VARCHAR(30),
    commenter VARCHAR(200),
    comment_text TEXT NOT NULL,
    upvotes INTEGER DEFAULT 0,
    comment_date TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id, comment_id)
);

CREATE INDEX IF NOT EXISTS idx_sa_comments_article ON sa_article_comments(article_id);

-- ============================================================
-- Add canonical_article_id to existing sa_alpha_picks table
-- ============================================================

ALTER TABLE sa_alpha_picks ADD COLUMN IF NOT EXISTS canonical_article_id VARCHAR(20);
CREATE INDEX IF NOT EXISTS idx_sa_picks_canonical_article ON sa_alpha_picks(canonical_article_id);
