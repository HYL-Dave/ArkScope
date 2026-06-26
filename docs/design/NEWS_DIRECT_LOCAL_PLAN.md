# News Direct-Local — Scoping (PG-exit Step 2, first collector)

Date: 2026-06-26
Status: scoping (design-first; no runtime code in this doc). News chosen first (over IV) — high
frequency, user-visible, more recoverable, and it can reuse the price_backfill direct-write +
provider_sync + scheduler-state + Settings pattern. IV waits until its data-source strategy
(provider-precomputed?) is clearer.

## Current news flow (verified against code)

It is NOT provider→PG today — it's **provider → Parquet → PG → local mirror**:

- `scripts/collection/collect_polygon_news.run_incremental` (and the finnhub twin) fetch + parse
  articles and write **Parquet** under `data/news/raw/` (via `StorageManager.save_articles`),
  returning `{mode, new_articles}`. The incremental cursor is `storage.get_latest_timestamp()`
  (newest Parquet article) → fetch from +1s.
- The scheduler source (`polygon_news`/`finnhub_news`, `sync_flag="--news"`) then runs the PG sync
  subprocess (Parquet → PG), and `local_incremental` mirrors PG → the local `news` table.
- Local read authority is `market_data.db` `news` + `news_fts` (FTS5), read by
  `sqlite_backend.query_news` / `query_news_search` / `query_news_feed`.

Local `news` schema (target): `id INTEGER PK, ticker, title, description, url, publisher,
source('ibkr'|'polygon'|'finnhub'), published_at (UTC 'YYYY-MM-DDTHH:MM:SS+0000'), article_hash,
sentiment_* (optional, NULL until LLM scores)`. `news_fts` is an EXTERNAL-CONTENT FTS5
(`content='news', content_rowid='id'`) — inserts into `news` do NOT auto-populate it.

The mirror's local write (`market_data_admin`, the price-bootstrap sibling) inserts
`(id, ticker, title, description, url, publisher, source, published_at, article_hash)` preserving
PG ids, and (must) keep `news_fts` in sync.

## Goal

A **direct-local news writer**: provider → parse → local `news` table (+ FTS) directly, no PG, no
Parquet round-trip required for the local read path. Mirrors `backfill_prices_direct`: hold
`market_write_lock`, `INSERT OR IGNORE` for idempotence, `provider_sync_runs`/`_meta` telemetry,
per-ticker isolation, behind a default-OFF toggle. Selectable via the scheduler like
price_backfill, so `local_incremental` + `--news` PG sync can eventually retire (Step 3, NOT now).

## Open design decisions (need the user's call before slicing)

1. **Dedup key / PK.** Local-direct has no PG `id` to preserve. Options: (a) `id` autoincrement +
   a UNIQUE index on `article_hash` (the collector already computes it) → `INSERT OR IGNORE`
   dedups on hash; (b) UNIQUE `(source, url)`; (c) UNIQUE `(source, ticker, published_at, title)`.
   Lean: **(a) UNIQUE(article_hash)** — the hash is the existing identity; cheapest, and
   cross-provider dup of the same article is still two rows only if their hashes differ (acceptable
   v1). Needs an additive migration: a UNIQUE index on `news.article_hash` (tolerant of existing
   rows — verify no current dup hashes first; if dups exist, dedup-or-skip).
2. **FTS sync.** `news_fts` is external-content. Options: (a) AFTER INSERT/DELETE/UPDATE triggers
   on `news` (set-and-forget, also fixes the mirror path); (b) the writer manually
   `INSERT INTO news_fts(rowid,title,description)` after each row. Lean: **(a) triggers** —
   one-time schema add, makes EVERY writer (direct + mirror) correct, no per-writer duplication.
   Verify the existing mirror doesn't already populate FTS some other way (avoid double-index).
3. **Parquet: keep or bypass.** The collector writes Parquet today (history/backfill tooling +
   the incremental cursor reads it). Options: (a) direct-local writer ALSO keeps writing Parquet
   (archive parity, zero tooling loss); (b) local SQLite becomes the sole sink, Parquet retired
   with the mirror. Lean: **(a) keep Parquet for now** — the direct path is additive; retiring
   Parquet belongs with the mirror retirement (Step 3), not here.
4. **Incremental cursor.** Direct-local must fetch-from the newest LOCAL article, not the Parquet
   cursor. Add a "latest local `news.published_at` for (source[, ticker])" read; the writer fetches
   from +1s like the collector does off Parquet. (If we keep Parquet (3a), the two cursors could
   diverge — decision: the LOCAL cursor governs the direct-local writer.)
5. **Scheduler wiring + toggle.** A `use_local_news` toggle (env + profile, default-OFF, like
   `use_local_market`/`_macro`/`_records`); when on, the `polygon_news`/`finnhub_news` scheduler
   sources route to the direct-local writer (no `--news` PG sync, no mirror) instead of
   provider→Parquet→PG. News is timestamp-incremental (NOT gap-day-based like price), so it does
   NOT use the coverage planner — just the local-cursor incremental fetch. Default-OFF; flipping
   on is a later decision (like the records cutover).

## Slice plan (each its own commit + review gate; mirror the price/records cadence)

- **2a — direct-local news writer (core, hermetic).** `news_direct.backfill_news_direct(...)` (or
  similar): provider(parsed articles, injectable) → `market_write_lock` → ensure schema/FTS →
  `INSERT OR IGNORE` (dedup per decision 1) → FTS in sync (decision 2) → provider_sync telemetry;
  local-cursor incremental (decision 4). Pure-of-PG, fake-provider tests (dedup/idempotent/FTS
  populated/cursor). NO scheduler wiring, NO mirror change.
- **2b — schema migration: UNIQUE(article_hash) + FTS triggers.** Additive, idempotent, tolerant
  of existing rows (dedup-or-skip if current dups). Tests: existing DB upgrades cleanly; FTS stays
  consistent after insert/delete.
- **2c — toggle + scheduler routing (default-off).** `use_local_news`; route the news sources to
  the direct writer when on (no PG sync / mirror on that path), else current behavior. Mirror the
  records/market factory pattern. Tests: off → current path verbatim; on → direct writer, no PG.
- **2d — live smoke (gated).** One ticker / small window, toggle on, no PG: confirm articles land
  in local `news` + FTS search works + idempotent re-run. Outward-facing (provider API) → user go.
- (Finnhub twin folds into 2a/2c — same writer, `source='finnhub'`.)

## Guardrails (locked, from the user)

- Continuous slices OK, but EACH is its own commit + review gate; the first runtime-behavior /
  schema-touching slices (2b, 2c) are gated.
- Do NOT retire the mirror / `--news` sync until the direct-local writer is landed + trusted (Step
  3, separate). Do NOT remove any Settings local/mirror/strict UI yet (Step 5, last).
- Default-OFF throughout; flipping `use_local_news` on is a later, separate decision.

## Relation to other plans

Reuses the `backfill_prices_direct` direct-write + `provider_sync_*` + `market_write_lock` +
scheduler-state/Settings machinery, and the shared `ibkr_gateway_lock` (for the eventual
`ibkr_news` direct path — out of scope here; polygon/finnhub first, no Gateway). This is
`PG_EXIT_COMPLETION_PLAN.md` Step 2's first collector; IV/fundamentals + mirror retirement follow.
