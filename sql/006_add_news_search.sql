-- =============================================================================
-- Migration 006: News full-text search (Smart Data Retrieval — Phase 1)
-- =============================================================================
-- Run: psql $DATABASE_URL -f sql/006_add_news_search.sql
-- Adds stored tsvector column + GIN index for efficient full-text search
-- on news articles. Pattern mirrors agent_memories (004_add_memories.sql).
-- The existing pg_trgm index (idx_news_title_trgm) provides ILIKE fallback.

-- 1. Add materialized tsvector column
ALTER TABLE news ADD COLUMN IF NOT EXISTS search_vector tsvector;

-- 2. Populate for existing rows
UPDATE news SET search_vector = to_tsvector('english',
    COALESCE(title, '') || ' ' || COALESCE(description, ''))
WHERE search_vector IS NULL;

-- 3. Auto-update trigger for new inserts/updates
CREATE OR REPLACE FUNCTION news_search_vector_update() RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('english',
        COALESCE(NEW.title, '') || ' ' || COALESCE(NEW.description, ''));
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_news_search_vector ON news;
CREATE TRIGGER trg_news_search_vector
    BEFORE INSERT OR UPDATE OF title, description ON news
    FOR EACH ROW EXECUTE FUNCTION news_search_vector_update();

-- 4. GIN index for fast full-text search
CREATE INDEX IF NOT EXISTS idx_news_search_vector
    ON news USING GIN (search_vector);
