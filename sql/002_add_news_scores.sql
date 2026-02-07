-- =============================================================================
-- MindfulRL-Intraday: Add news_scores table for multi-model scoring
-- =============================================================================
-- Separates scoring from news articles so each article can have multiple
-- scores from different models (haiku, gpt-5.2, gpt-6, ...).
--
-- Run: psql "$SUPABASE_DB_URL" -f sql/002_add_news_scores.sql
-- =============================================================================

-- =============================================================================
-- New table: news_scores
-- =============================================================================

CREATE TABLE IF NOT EXISTS news_scores (
    id               BIGSERIAL    PRIMARY KEY,
    news_id          BIGINT       NOT NULL REFERENCES news(id) ON DELETE CASCADE,
    score_type       VARCHAR(20)  NOT NULL,   -- 'sentiment' or 'risk'
    model            VARCHAR(50)  NOT NULL,   -- 'haiku', 'gpt_5_2', 'gpt_6', etc.
    reasoning_effort VARCHAR(20)  NOT NULL DEFAULT '',  -- 'xhigh', 'high', 'medium', '' for legacy
    score            SMALLINT     NOT NULL CHECK (score BETWEEN 1 AND 5),
    scored_at        TIMESTAMPTZ  DEFAULT NOW(),

    UNIQUE(news_id, score_type, model, reasoning_effort)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_scores_news_id
    ON news_scores(news_id);

CREATE INDEX IF NOT EXISTS idx_scores_model
    ON news_scores(model, score_type);

CREATE INDEX IF NOT EXISTS idx_scores_scored_at
    ON news_scores(scored_at DESC);

-- =============================================================================
-- View: news_latest_scores
-- Returns only the most recent score per (news_id, score_type)
-- =============================================================================

CREATE OR REPLACE VIEW news_latest_scores AS
WITH ranked AS (
    SELECT
        ns.news_id,
        ns.score_type,
        ns.model,
        ns.reasoning_effort,
        ns.score,
        ns.scored_at,
        ROW_NUMBER() OVER (
            PARTITION BY ns.news_id, ns.score_type
            ORDER BY ns.scored_at DESC
        ) AS rn
    FROM news_scores ns
)
SELECT news_id, score_type, model, reasoning_effort, score, scored_at
FROM ranked WHERE rn = 1;

-- =============================================================================
-- Migrate existing scores from news table into news_scores
-- =============================================================================

-- Sentiment scores
INSERT INTO news_scores (news_id, score_type, model, reasoning_effort, score, scored_at)
SELECT id, 'sentiment', COALESCE(scored_model, 'unknown'), '', sentiment_score, created_at
FROM news
WHERE sentiment_score IS NOT NULL
ON CONFLICT (news_id, score_type, model, reasoning_effort) DO NOTHING;

-- Risk scores
INSERT INTO news_scores (news_id, score_type, model, reasoning_effort, score, scored_at)
SELECT id, 'risk', COALESCE(scored_model, 'unknown'), '', risk_score, created_at
FROM news
WHERE risk_score IS NOT NULL
ON CONFLICT (news_id, score_type, model, reasoning_effort) DO NOTHING;

-- =============================================================================
-- Updated helper function: news_sentiment_summary (with optional model filter)
-- =============================================================================

-- Drop old 2-param version to avoid ambiguous function error
DROP FUNCTION IF EXISTS news_sentiment_summary(VARCHAR, INTEGER);

CREATE OR REPLACE FUNCTION news_sentiment_summary(
    p_ticker VARCHAR(10),
    p_days INTEGER DEFAULT 7,
    p_model VARCHAR(50) DEFAULT NULL  -- NULL = use latest score per article
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
    WITH article_scores AS (
        SELECT
            n.id,
            s_sent.score AS sentiment,
            s_risk.score AS risk
        FROM news n
        LEFT JOIN LATERAL (
            SELECT ns.score FROM news_scores ns
            WHERE ns.news_id = n.id
              AND ns.score_type = 'sentiment'
              AND (p_model IS NULL OR ns.model = p_model)
            ORDER BY ns.scored_at DESC
            LIMIT 1
        ) s_sent ON TRUE
        LEFT JOIN LATERAL (
            SELECT ns.score FROM news_scores ns
            WHERE ns.news_id = n.id
              AND ns.score_type = 'risk'
              AND (p_model IS NULL OR ns.model = p_model)
            ORDER BY ns.scored_at DESC
            LIMIT 1
        ) s_risk ON TRUE
        WHERE n.ticker = p_ticker
          AND n.published_at >= NOW() - (p_days || ' days')::INTERVAL
    )
    SELECT
        COUNT(*) AS total_articles,
        ROUND(AVG(sentiment)::NUMERIC, 2) AS avg_sentiment,
        ROUND(AVG(risk)::NUMERIC, 2) AS avg_risk,
        COUNT(*) FILTER (WHERE sentiment >= 4) AS bullish_count,
        COUNT(*) FILTER (WHERE sentiment <= 2) AS bearish_count
    FROM article_scores
    WHERE sentiment IS NOT NULL;
$$;

-- =============================================================================
-- NOTE: news.sentiment_score, risk_score, scored_model columns are RETAINED
-- for backward compatibility during the transition period.
-- =============================================================================