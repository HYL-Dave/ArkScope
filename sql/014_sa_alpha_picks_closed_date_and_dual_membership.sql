-- Migration 014: SA Alpha Picks closed-date + dual open/closed membership
--
-- Seeking Alpha can show the same (symbol, picked_date) in both Open/Current
-- and Closed/Removed tabs. The original UNIQUE(symbol, picked_date) collapsed
-- those source rows into one DB row. Preserve the tab membership explicitly.

ALTER TABLE sa_alpha_picks
    ADD COLUMN IF NOT EXISTS closed_date DATE;

-- Existing DB rows only kept the closed date inside raw_data.cells[2].
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

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'sa_alpha_picks_symbol_picked_date_status_key'
    ) THEN
        ALTER TABLE sa_alpha_picks
            ADD CONSTRAINT sa_alpha_picks_symbol_picked_date_status_key
            UNIQUE (symbol, picked_date, portfolio_status);
    END IF;
END
$$;
