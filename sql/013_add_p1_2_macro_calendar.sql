-- Migration 013: P1.2 free calendar + macro layer
-- PostgreSQL 17+ (self-hosted)
--
-- See docs/design/P1_2_SPEC.md for the data model.
--
-- Revision-log semantic (cal_*_event_revisions): each row stores the state
-- OBSERVED at observed_at (NOT the prior canonical state). First insert of
-- a fingerprint also appends a baseline revision so as-of reads before any
-- mutation have a row to match. See spec §3.2-§3.3.
--
-- macro_observations.realtime_start is NOT NULL with no default sentinel.
-- If a `latest_only` series can't be joined to a release date, ingestion
-- skips the row rather than writing a sentinel that pretends to be queryable.

-- =========================================================================
-- Calendar — Economic events (Finnhub /calendar/economic)
-- =========================================================================

CREATE TABLE IF NOT EXISTS cal_economic_events (
    event_id     BIGSERIAL PRIMARY KEY,
    country      CHAR(2) NOT NULL,
    event_name   TEXT NOT NULL,
    event_time   TIMESTAMPTZ NOT NULL,
    impact       VARCHAR(8) NOT NULL DEFAULT ''
                 CHECK (impact IN ('low','medium','high','')),
    unit         TEXT,
    actual       NUMERIC,
    estimate     NUMERIC,
    prev         NUMERIC,
    fingerprint  TEXT NOT NULL UNIQUE,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_econ_event_time
    ON cal_economic_events (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_cal_econ_country_time
    ON cal_economic_events (country, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_cal_econ_high_impact
    ON cal_economic_events (impact, event_time DESC) WHERE impact = 'high';

CREATE TABLE IF NOT EXISTS cal_economic_event_revisions (
    revision_id     BIGSERIAL PRIMARY KEY,
    event_id        BIGINT NOT NULL
                    REFERENCES cal_economic_events(event_id) ON DELETE CASCADE,
    observed_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actual          NUMERIC,
    estimate        NUMERIC,
    prev            NUMERIC,
    source_payload  JSONB NOT NULL,
    UNIQUE (event_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_cal_econ_rev_event_obs
    ON cal_economic_event_revisions (event_id, observed_at DESC);


-- =========================================================================
-- Calendar — Earnings (Finnhub /calendar/earnings, per-symbol ingestion)
-- =========================================================================

CREATE TABLE IF NOT EXISTS cal_earnings_events (
    earnings_id      BIGSERIAL PRIMARY KEY,
    symbol           TEXT NOT NULL,
    report_date      DATE NOT NULL,
    year             INT NOT NULL,
    quarter          INT NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    hour             VARCHAR(4) NOT NULL DEFAULT ''
                     CHECK (hour IN ('bmo','amc','dmh','')),
    eps_estimate     NUMERIC,
    eps_actual       NUMERIC,
    revenue_estimate NUMERIC,
    revenue_actual   NUMERIC,
    fingerprint      TEXT NOT NULL UNIQUE,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_earn_symbol_date
    ON cal_earnings_events (symbol, report_date DESC);
CREATE INDEX IF NOT EXISTS idx_cal_earn_date
    ON cal_earnings_events (report_date DESC);

CREATE TABLE IF NOT EXISTS cal_earnings_event_revisions (
    revision_id      BIGSERIAL PRIMARY KEY,
    earnings_id      BIGINT NOT NULL
                     REFERENCES cal_earnings_events(earnings_id) ON DELETE CASCADE,
    observed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    eps_estimate     NUMERIC,
    eps_actual       NUMERIC,
    revenue_estimate NUMERIC,
    revenue_actual   NUMERIC,
    hour             VARCHAR(4) NOT NULL DEFAULT '',
    source_payload   JSONB NOT NULL,
    UNIQUE (earnings_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_cal_earn_rev_event_obs
    ON cal_earnings_event_revisions (earnings_id, observed_at DESC);


-- =========================================================================
-- Calendar — IPOs (Finnhub /calendar/ipo)
-- =========================================================================

CREATE TABLE IF NOT EXISTS cal_ipo_events (
    ipo_id              BIGSERIAL PRIMARY KEY,
    symbol              TEXT,                          -- can be null pre-listing
    name                TEXT NOT NULL,
    ipo_date            DATE NOT NULL,
    exchange            TEXT,                          -- ~56% null pre-priced
    status              VARCHAR(12) NOT NULL
                        CHECK (status IN ('priced','filed','expected','withdrawn')),
    number_of_shares    BIGINT,
    price               NUMERIC,
    total_shares_value  NUMERIC,
    fingerprint         TEXT NOT NULL UNIQUE,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cal_ipo_date
    ON cal_ipo_events (ipo_date DESC);
CREATE INDEX IF NOT EXISTS idx_cal_ipo_status_date
    ON cal_ipo_events (status, ipo_date DESC);

CREATE TABLE IF NOT EXISTS cal_ipo_event_revisions (
    revision_id         BIGSERIAL PRIMARY KEY,
    ipo_id              BIGINT NOT NULL
                        REFERENCES cal_ipo_events(ipo_id) ON DELETE CASCADE,
    observed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status              VARCHAR(12) NOT NULL,
    price               NUMERIC,
    exchange            TEXT,
    number_of_shares    BIGINT,
    total_shares_value  NUMERIC,
    source_payload      JSONB NOT NULL,
    UNIQUE (ipo_id, observed_at)
);

CREATE INDEX IF NOT EXISTS idx_cal_ipo_rev_event_obs
    ON cal_ipo_event_revisions (ipo_id, observed_at DESC);


-- =========================================================================
-- Macro — FRED series catalog
-- =========================================================================

CREATE TABLE IF NOT EXISTS macro_series (
    series_id            TEXT PRIMARY KEY,
    title                TEXT NOT NULL,
    frequency            VARCHAR(8) NOT NULL,
    units                TEXT NOT NULL,
    seasonal_adjustment  TEXT,
    last_updated         TIMESTAMPTZ,
    revision_strategy    VARCHAR(16) NOT NULL DEFAULT 'latest_only'
                         CHECK (revision_strategy IN ('latest_only','full_vintages')),
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================================
-- Macro — FRED observations (with vintage support)
-- =========================================================================

CREATE TABLE IF NOT EXISTS macro_observations (
    observation_id    BIGSERIAL PRIMARY KEY,
    series_id         TEXT NOT NULL
                      REFERENCES macro_series(series_id) ON DELETE CASCADE,
    observation_date  DATE NOT NULL,
    value             NUMERIC,                        -- nullable: FRED returns '.' for missing
    realtime_start    DATE NOT NULL,                  -- no default; ingestion error if unknown
    realtime_end      DATE NOT NULL DEFAULT '9999-12-31',
    fetched_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (series_id, observation_date, realtime_start)
);

CREATE INDEX IF NOT EXISTS idx_macro_obs_series_date
    ON macro_observations (series_id, observation_date DESC);
CREATE INDEX IF NOT EXISTS idx_macro_obs_series_realtime
    ON macro_observations (series_id, realtime_start DESC);


-- =========================================================================
-- Macro — FRED release schedule
-- =========================================================================

CREATE TABLE IF NOT EXISTS macro_release_dates (
    release_id    INT NOT NULL,
    release_name  TEXT NOT NULL,
    release_date  DATE NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, release_date)
);

CREATE INDEX IF NOT EXISTS idx_macro_release_date
    ON macro_release_dates (release_date DESC);