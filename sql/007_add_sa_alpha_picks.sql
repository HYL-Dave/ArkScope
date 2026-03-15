-- Migration 007: Seeking Alpha Alpha Picks tables
-- Phase 11c: SA Alpha Picks integration

-- Alpha Picks portfolio data
CREATE TABLE IF NOT EXISTS sa_alpha_picks (
    id                BIGSERIAL PRIMARY KEY,
    symbol            VARCHAR(20) NOT NULL,
    company           VARCHAR(200) NOT NULL,
    picked_date       DATE NOT NULL,
    portfolio_status  VARCHAR(20) NOT NULL DEFAULT 'current',  -- current/closed (SA business state)
    is_stale          BOOLEAN NOT NULL DEFAULT FALSE,           -- sync state: not seen in last refresh
    return_pct        NUMERIC(8,2),
    sector            VARCHAR(100),
    sa_rating         VARCHAR(30),
    holding_pct       NUMERIC(6,2),
    detail_report     TEXT,
    detail_fetched_at TIMESTAMPTZ,
    raw_data          JSONB,
    last_seen_snapshot TIMESTAMPTZ,
    fetched_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (symbol, picked_date)
);

CREATE INDEX IF NOT EXISTS idx_sa_picks_status ON sa_alpha_picks(portfolio_status);
CREATE INDEX IF NOT EXISTS idx_sa_picks_symbol ON sa_alpha_picks(symbol);
CREATE INDEX IF NOT EXISTS idx_sa_picks_snapshot ON sa_alpha_picks(last_seen_snapshot);
CREATE INDEX IF NOT EXISTS idx_sa_picks_stale ON sa_alpha_picks(is_stale) WHERE is_stale = TRUE;

-- Per-tab refresh metadata
CREATE TABLE IF NOT EXISTS sa_refresh_meta (
    scope             VARCHAR(20) PRIMARY KEY,  -- 'current' / 'closed'
    last_attempt_at   TIMESTAMPTZ,
    last_success_at   TIMESTAMPTZ,
    snapshot_ts       TIMESTAMPTZ,
    row_count         INTEGER DEFAULT 0,
    ok                BOOLEAN NOT NULL DEFAULT FALSE,
    last_error        TEXT,
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);
