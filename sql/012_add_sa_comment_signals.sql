-- Migration 012: SA comment signal extraction (Stage 1, rule-based)
-- PostgreSQL 17+ (self-hosted pgvector Docker)
--
-- Persists rule-based signals derived from sa_article_comments. One row
-- per source comment, keyed by sa_article_comments.id (BIGINT) for
-- referential integrity. ON DELETE CASCADE so stale signals don't
-- linger when the underlying comment row is purged.
--
-- See src/sa/comment_signals.py for the extractor and
-- docs/design/SA_COMMENT_INTELLIGENCE_PLAN.md §5.1 for the rule set.

CREATE TABLE IF NOT EXISTS sa_comment_signals (
    comment_row_id      BIGINT       PRIMARY KEY
                                     REFERENCES sa_article_comments(id)
                                     ON DELETE CASCADE,
    article_id          VARCHAR      NOT NULL,    -- denormalized for fast joins
    comment_id          VARCHAR      NOT NULL,    -- denormalized for fast lookups
    ticker_mentions     TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    candidate_mentions  TEXT[]       NOT NULL DEFAULT ARRAY[]::TEXT[],
    keyword_buckets     JSONB        NOT NULL DEFAULT '{}'::jsonb,
    high_value_score    NUMERIC(4,2) NOT NULL DEFAULT 0.0,
    needs_verification  BOOLEAN      NOT NULL DEFAULT FALSE,
    rule_set_version    TEXT         NOT NULL,
    extracted_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_score
    ON sa_comment_signals (high_value_score DESC);

CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_tickers
    ON sa_comment_signals USING GIN (ticker_mentions);

CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_extracted
    ON sa_comment_signals (extracted_at DESC, rule_set_version);

CREATE INDEX IF NOT EXISTS idx_sa_comment_signals_article
    ON sa_comment_signals (article_id);