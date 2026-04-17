-- =============================================================================
-- Migration 004: Agent Memories table (Episodic Memory — Phase 15)
-- =============================================================================
-- Run: psql $DATABASE_URL -f sql/004_add_memories.sql
-- Stores cross-session agent knowledge: analysis conclusions, insights,
-- user preferences, confirmed facts, and free-form notes.
-- Full content also written to data/agent_memory/*.md (Markdown files).

CREATE TABLE IF NOT EXISTS agent_memories (
    id              BIGSERIAL PRIMARY KEY,
    category        VARCHAR(30) NOT NULL,           -- analysis, insight, preference, fact, note
    title           TEXT NOT NULL,                   -- short descriptive title
    content         TEXT NOT NULL,                   -- full memory content (Markdown)
    tickers         TEXT[],                          -- related tickers {"AFRM", "NVDA"}
    tags            TEXT[],                          -- free-form tags {"earnings", "entry_strategy"}
    source          VARCHAR(30),                     -- agent_auto, user_manual, subagent
    provider        VARCHAR(20),                     -- anthropic, openai
    model           VARCHAR(50),                     -- claude-opus-4-7, gpt-5.4
    importance      SMALLINT DEFAULT 5,              -- 1-10 importance for ranking
    file_path       TEXT,                            -- data/agent_memory/2026-02-19_analysis_abc123.md
    expires_at      TIMESTAMPTZ,                     -- optional expiry (NULL = never expires)
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Full-text search on title + content
CREATE INDEX IF NOT EXISTS idx_memories_search
    ON agent_memories USING GIN (to_tsvector('english', title || ' ' || content));

-- Search by tickers (GIN for array overlap: WHERE tickers && ARRAY['NVDA'])
CREATE INDEX IF NOT EXISTS idx_memories_tickers
    ON agent_memories USING GIN (tickers);

-- Search by tags
CREATE INDEX IF NOT EXISTS idx_memories_tags
    ON agent_memories USING GIN (tags);

-- Browse by category + date
CREATE INDEX IF NOT EXISTS idx_memories_category_date
    ON agent_memories (category, created_at DESC);

-- Browse by date (general)
CREATE INDEX IF NOT EXISTS idx_memories_date
    ON agent_memories (created_at DESC);
