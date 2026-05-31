-- Migration 015: SA Alpha Picks closed-event identity
--
-- Seeking Alpha can list the same (symbol, picked_date) multiple times in
-- Closed/Removed when the close date differs. Migration 014 preserved
-- current-vs-closed dual membership, but still collapsed distinct closed
-- events because closed_date was not part of the closed identity.

ALTER TABLE sa_alpha_picks
    ADD COLUMN IF NOT EXISTS closed_date DATE;

-- Backfill old closed rows where possible before changing the unique model.
UPDATE sa_alpha_picks
SET closed_date = CASE
    WHEN raw_data->'cells'->>2 ~ '^\d{1,2}/\d{1,2}/\d{4}$'
        THEN to_date(raw_data->'cells'->>2, 'MM/DD/YYYY')
    WHEN raw_data->'cells'->>2 ~ '^\d{4}-\d{2}-\d{2}$'
        THEN (raw_data->'cells'->>2)::date
    ELSE closed_date
END
WHERE portfolio_status = 'closed'
  AND closed_date IS NULL
  AND raw_data ? 'cells';

ALTER TABLE sa_alpha_picks
    DROP CONSTRAINT IF EXISTS sa_alpha_picks_symbol_picked_date_key;

ALTER TABLE sa_alpha_picks
    DROP CONSTRAINT IF EXISTS sa_alpha_picks_symbol_picked_date_status_key;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_picks_current_unique
    ON sa_alpha_picks(symbol, picked_date, portfolio_status)
    WHERE portfolio_status = 'current';

CREATE UNIQUE INDEX IF NOT EXISTS idx_sa_picks_closed_unique
    ON sa_alpha_picks(symbol, picked_date, portfolio_status, closed_date)
    WHERE portfolio_status = 'closed';
