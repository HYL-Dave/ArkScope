-- Migration 011: job_runs persistence (P0.2 service-first S2)
-- PostgreSQL 17+ (self-hosted pgvector Docker)
--
-- Records every backend job execution. Replaces process-local state in
-- src/service/jobs.py as the source of truth for last_status / history.
-- See docs/design/PROJECT_PRIORITY_MAP.md §P0.2 for acceptance criteria.

CREATE TABLE IF NOT EXISTS job_runs (
    id              BIGSERIAL PRIMARY KEY,
    job_name        TEXT        NOT NULL,
    status          TEXT        NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    trigger_source  TEXT        NOT NULL DEFAULT 'api',
    payload         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    result          JSONB,
    message         TEXT,
    error           TEXT,
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    duration_ms     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_runs_name_started_at
    ON job_runs (job_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_job_runs_status_started_at
    ON job_runs (status, started_at DESC);