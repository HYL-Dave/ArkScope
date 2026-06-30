# News Direct-Local — Scoping (PG-exit Step 2, first collector)

Date: 2026-06-26
Status: Step 2 (2a–2d) DONE; **Step 3 S3.0–S3.3 COMPLETE + live-verified 2026-06-27**;
**normalized all-source N1–N7 LIVE-MIGRATED and validated 2026-06-29; N8a code/offline gate
COMPLETE 2026-06-30, but the live begin/finalize cutover has NOT run**
(see the checkpoint near the end). Original Step 2 scoping is retained below as history. News chosen
first (over IV) — high
frequency, user-visible, more recoverable, and it can reuse the price_backfill direct-write +
provider_sync + scheduler-state + Settings pattern. IV waits until its data-source strategy
(provider-precomputed?) is clearer.

## Historical Step 2 news flow (pre-direct-local; retained for context)

At the original Step 2 baseline it was NOT provider→PG directly — it was
**provider → Parquet → PG → local mirror**:

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
per-ticker isolation, originally behind a default-OFF toggle and now default-ON with an explicit
rollback. Selectable via the scheduler like
price_backfill, so `local_incremental` + `--news` PG sync can eventually retire (Step 3, NOT now).

## Open design decisions (need the user's call before slicing)

1. **Dedup key / PK.** Local-direct has no PG `id` to preserve. Options: (a) `id` autoincrement +
   a UNIQUE index on `article_hash` (the collector already computes it) → `INSERT OR IGNORE`
   dedups on hash; (b) UNIQUE `(source, url)`; (c) UNIQUE `(source, ticker, published_at, title)`.
   Chosen: **(a) UNIQUE(article_hash)** (shipped in 2b). ⚠️ **CORRECTION (2026-06-27, refuted by a
   live duplicate):** `article_hash` is NOT one canonical identity. The PG/mirror path computes
   **SHA-256** (`migrate_to_supabase.article_hash`: `sha256(f"{ticker}|{title}|{published_at[:10]}")`,
   ticker/title VERBATIM); the direct path used the collector's **MD5** `dedup_hash`
   (`md5("{TICKER.upper()}|{title.strip().lower()}|{date[:10]}")`). Same article → different hash →
   `INSERT OR IGNORE` does NOT dedup direct-vs-mirror. The original "two rows only if hashes differ
   (acceptable v1)" assumption is WRONG for the *same* article and must not be relied on. Fixed in
   **Step 3 §S3.0** (direct path adopts the canonical SHA-256). Additive migration shipped in 2b:
   the UNIQUE index on `news.article_hash`.
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
5. **Scheduler wiring + toggle.** A `use_local_news` toggle (env + profile, initially default-OFF,
   `use_local_market`/`_macro`/`_records`); when on, the `polygon_news`/`finnhub_news` scheduler
   sources route to the direct-local writer (no `--news` PG sync, no mirror) instead of
   provider→Parquet→PG. News is timestamp-incremental (NOT gap-day-based like price), so it does
   NOT use the coverage planner — just the local-cursor incremental fetch. Step 3 subsequently
   made unset default to ON while preserving explicit false as the rollback.

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
- Step 2 stayed default-OFF; Step 3's reviewed cutover changes unset to ON and retains explicit
  profile/env false as the rollback.

## Relation to other plans

Reuses the `backfill_prices_direct` direct-write + `provider_sync_*` + `market_write_lock` +
scheduler-state/Settings machinery, and the shared `ibkr_gateway_lock` (for the eventual
`ibkr_news` direct path — out of scope here; polygon/finnhub first, no Gateway). This is
`PG_EXIT_COMPLETION_PLAN.md` Step 2's first collector; IV/fundamentals + mirror retirement follow.

---

## Step 2 — status (DONE 2026-06-27)

2a (`b347148`); 2a.1 + 2b (`b53e5ce`/`0796719`, incl. the live 371k DB migrated: `UNIQUE(article_hash)`
+ FTS triggers `news_ai/ad/au`); 2c (`3b782f2`, toggle + scheduler routing, default-OFF); Slice B
(`1469c43`, collectors' `load_env` reads os.environ FIRST so a DB-managed key wins). 2d live smoke
PASS (DB-key→news). Provider keys then migrated `config/.env`→`data_provider_config` + real-profile
smoke PASS — the **sidecar is DB-authoritative** for provider keys; `.env` kept as fallback
(CLI/standalone still read it — sidecar-only authority accepted, desktop-first; see
`project_provider_config_dbification` memory).

## Step 3 — COMPLETE (2026-06-27; provider-scoped mirror BYPASS, NOT a domain retirement)

Goal: make polygon/finnhub news ingest the default **direct-local** path (bypass `--news` PG sync +
the PG→local mirror), with an in-product rollback toggle and honest status — **without data loss or
duplicates**. Designed via an adversarial 5-reader pass; approved in principle by the user
(hash option A; default-ON + rollback lever + Settings toggle; persist-this-doc-first).

### Critical prerequisite — the `article_hash` divergence (S3.0 DONE, `59b0ebd`)
- **Canonical (mirror)**, `migrate_to_supabase.py:71` applied at `:230`:
  `sha256(f"{ticker}|{title}|{published_at[:10]}")[:64]` — ticker + title **VERBATIM** (no case/strip).
  All 371k existing rows use this (len 64).
- **Direct (before S3.0)**: `article.dedup_hash` =
  `md5(f"{TICKER.upper()}|{title.strip().lower()}|{date[:10]}")` (`collect_polygon_news.py:374`,
  `collect_finnhub_news.py:268`, mapped at `news_providers.py:66`) — len 32.
- ⇒ same article → different hash → `INSERT OR IGNORE` cannot dedup direct-vs-mirror.
  **VERIFIED LIVE:** the only 3 non-SHA rows among 371,675 are the 2d/real-profile smoke writes;
  id `519309779` (AAPL "Massive News…") is a TRUE duplicate of SHA id `517324858`; ids
  `519309780`/`519309781` are genuinely-new (legit content, wrong-scheme hash).
- The cursor does NOT mask it: `_latest_published` is hash-agnostic (correct), but its
  inclusive-boundary re-fetch leans on hash dedup, which the divergence defeats for mirror-origin
  boundary articles.
- **S3.0 result:** direct ingest now emits the canonical SHA-256, the three MD5 smoke rows were
  cleaned and re-fetched under SHA, coexistence/idempotency passed live, and the local table is
  100% 64-character SHA. A follow-up audit then found ticker-alias hash drift despite the valid
  SHA shape; that separate invariant is S3.0a below.

### Scope (narrower than "retire the news mirror")
- `ibkr_news` has **no direct writer** (`news_direct_source=None`) → it STAYS collector→PG→mirror.
  So the mirror's **news domain MUST STAY** (it still feeds ibkr_news). Step 3 only makes
  **polygon/finnhub bypass** the mirror; do **NOT** remove the `news` branch from
  `incremental_update`. IV/fundamentals/prices unchanged (no direct writer; stay on the mirror).

### Slices (each its own commit + gate; TDD)
- **S3.0 — hash unification (PREREQUISITE).** Direct path computes the **canonical SHA-256** from
  the row's own ticker/title/`published_at[:10]` (one shared `article_hash` source of truth — reuse
  `migrate_to_supabase.article_hash` or extract a util — with a test pinning direct-hash ==
  canonical for the same inputs, so they can't drift). Adopt the mirror's scheme (option A); do NOT
  rewrite the 371k. **Bundled live cleanup:** delete the 3 len-32 smoke rows (1 dup + 2 that
  re-fetch cleanly under SHA) → DB 100% SHA; verify `COUNT(*) WHERE length(article_hash)=32 == 0`
  and zero duplicate groups; re-run an idempotent smoke. **Coexistence test:** seed a SHA
  mirror-style row, run the direct writer over the same article → `articles_added==0`.
- **S3.0a — ticker/hash identity repair (LIVE COMPLETE 2026-06-27).** A ticker rename used
  to update `news.ticker` without recomputing the ticker-derived hash. The audited live DB has
  1,148 stale SHA rows (HAPN 369, BRK B 779), including 101 HAPN collisions where 93 stale rows
  carry descriptions missing from the canonical owner. Commits `4a2a55e`/`0da6ee2`/`90b9d74`/
  `e3a3f31` centralize the hash helper, add deterministic merge-not-delete reconciliation, route
  future news aliases through it, and provide preview → fingerprint → no-clobber WAL backup → one
  transaction → validation. The reviewed live plan (`15ccb2d…b09813b`) applied 1,047 updates,
  merged/deleted 101 collisions, and filled 93 missing descriptions. Independent post-checks found
  0 hash mismatches, hash/semantic duplicate groups, or FTS missing/orphan rowids;
  `news == news_fts == 371,574`; HAPN/BRK B stale counts are 0; a second preview is 0/0. The
  WAL-safe pre-state backup is
  `data/market_data.db.bak-pre-news-identity-20260627T141946625934Z` (371,675 rows,
  `PRAGMA quick_check=ok`) and remains until one subsequent normal news ingest is verified. Normal
  SQLite reads passed (`HAPN` and alias `LC` both resolve to the same 372-row corpus). See
  `docs/superpowers/specs/2026-06-27-news-identity-repair-design.md`.
- **S3.1 — COMPLETE (`c9b6945`), status/health repoint (gated, additive read-only).** New
  `read_news_sync_status()` combines `provider_sync_runs WHERE domain='news'` for aggregate run
  timing/status/rows with `provider_sync_meta WHERE interval='news'` for current per-ticker errors.
  The direct writer intentionally isolates a ticker failure and can still finish the aggregate run
  as `succeeded`, so run rows alone MUST NOT claim a clean source. Overlay ONLY the news slice in
  `market_data.py:81`, `data_coverage_tools.py:255`, `provider_health.py:356`; keep
  prices/iv/fundamentals on `read_sync_meta`. **Gate the overlay on `use_local_news_enabled()`** so
  status follows the active writer (ungated → shows "never run" while the mirror is still the
  default writer). Provider cards retain content freshness detail but use direct per-provider
  run success/attempt/error while the direct writer is active; an unrun provider is `no_signal`,
  not made healthy by old mirrored content.
- **S3.2 — COMPLETE (`f458669` backend, `1cc8a25` UI), official switch + Settings UI.** Flip
  `use_local_news` **default → ON**
  (distinguish unset→ON from explicit-false→OFF); keep env/profile as the rollback lever. Routing
  line unchanged (`news_direct = d.news_direct_source is not None and use_local_news_enabled()`).
  Add `PUT /news/settings` + `GET /news/status` on the **macro route template** (NO `cache_clear`
  — the scheduler re-reads the toggle live per fire and news *reads* are governed by
  `use_local_market`), `api.ts` `setUseLocalNews`/`getNewsStatus`, and a Settings 新聞 panel
  (clone the macro panel). Toggle OFF = rollback to collector→Parquet→PG→mirror.
- **S3.3 — COMPLETE, test + live gate.** G1 polygon/finnhub direct by DEFAULT (no `--news`, no `_local_refresh`) +
  explicit-OFF restores the mirror chain (rollback pin); G2 mirror UNAFFECTED — `incremental_update`
  still syncs prices/iv/fundamentals **and ibkr_news's news** (news domain NOT removed); G3 news
  status from provider telemetry, not stale `market_sync_meta`; G4/G5 confirm direct idempotency +
  FTS parity. The focused news/market/scheduler suite passed 249 tests; frontend passed 197 tests
  and a production build. The gated real-profile AAPL smoke resolved the Polygon key from the app
  DB, ran with direct routing and no PG telemetry/backend, added 1 legitimate provider-returned
  article, then added 0 on the second run. `market_sync_meta.news` was byte-for-byte unchanged,
  `news == news_fts == 371,575`, all hashes are 64-character canonical SHA, duplicate groups are
  zero, `PRAGMA quick_check=ok`, and a normal local feed read returned data. The AAPL cursor stayed
  at `2026-06-27T07:11:00+0000` because the newly returned article's canonical primary ticker was
  another ETF; this is the collector's established primary-ticker behavior, not a missed boundary.
  `ibkr_news` remains pinned by tests to collector + `--news`, and `local_incremental` still runs
  the mirror for news/IV/fundamentals.

### Rollback / invariants (locked)
Touches only routing + telemetry-read + the direct hash scheme + UI. **NEVER** deletes/drops: live
news rows (beyond the 3 own-smoke artifacts cleaned in S3.0), FTS triggers, `news_fts`,
`idx_news_article_hash`, `market_sync_meta`, the shared `local_refresh` lock, the `--news` migrate
flag, or the mirror's news branch. Rollback = toggle OFF (+ revert the additive slices); no DB
restore.

### Sequencing
Completed order: S3.0a gated live repair → S3.1 status repoint → S3.2 default-ON + UI → S3.3
tests + gated live smoke. The S3.0a backup and the older pre-2b backup have both met their stated
verification gates and are eligible for manual deletion, but remain on disk; this cutover does not
delete backups automatically.

---

## All-source normalization offline checkpoint (N1–N5, 2026-06-28)

The normalized `news_articles` model is now implemented and verified **beside** the active legacy
`news` path. This checkpoint deliberately made no scheduler/read routing change and no live schema
write. It is a foundation for retaining provider IDs, storing one body per article, modeling ticker
relations, and eventually retiring the remaining IBKR news mirror path; it is not that retirement.

### Commits and offline gate

- **N1 identity/schema/cleaner/store:** `0d48573`, `097314d`, `5cfd79b`, `4fc5cfc`, `f8cee5b`,
  `cff9d8a`.
- **N2 streaming inventory + read-only migration preview:** `8a0ea7d`, `9bef570`.
- **N3 bounded common writer + provider-ID continuation:** `a15161b`.
- **N4 Polygon/Finnhub normalized adapters:** `e387e4c` (also fixes the existing Finnhub Unix
  timestamp conversion so it emits real UTC instead of local time mislabeled `Z`).
- **N5 IBKR normalized adapter + sanitized, unrun N6 probe:** `d4fea9c`.
- **Pre-merge invariant hardening:** `74de01d` centralizes ticker canonicalization across the
  store/inventory/preview, compares provider reuse dates in UTC, and removes volatile observation
  and body fields from conflict fingerprints.
- Verification: 101 normalized focused tests and 130 legacy news/read/scheduler regressions passed;
  compile and diff checks passed. The live `market_data.db` still contains zero
  `news_article%` objects.

### Real read-only preview

The planner scanned the live legacy SQLite table and all three Parquet corpora without changing
their size/mtime/inode or creating normalized tables. A read of a WAL-mode database may create
benign `-wal`/`-shm` sidecars; they are not evidence of a main-database mutation. Fingerprint:
`55aa79c33ebed92658dc8af232d12ae465d4d19c8ef3bf4556f2e0ed6c5442cc`.
This supersedes the pre-alias fingerprint `451c8b58…c4c716`.

| Source | Legacy rows | Parquet rows | Planned articles | Provider-ID matched | Fallback-only | Body match |
|---|---:|---:|---:|---:|---:|---:|
| Finnhub | 150,276 | 153,879 | 85,674 | 85,025 | 0 | 144,926 (96.4399%) |
| IBKR | 103,239 | 322,033 | 83,853 | 76,859 | 761 | 101,920 (98.7224%) |
| Polygon | 118,060 | 118,291 | 118,348 | 117,983 | 67 | 116,137 (98.3712%) |

The preview plans 619,209 ticker links, 287,912 title observations, and collapses 90,880 legacy
cross-ticker rows. Shared alias canonicalization removed 1,151 duplicate relation candidates from
the prior plan. UTC-normalized comparison left the 35 provider-ID reuse conflicts unchanged, so
they are not date-offset-only false positives. It is correctly **not applicable yet**: 816 strong
blockers remain (718 body
variants, 63 multiple-provider strong-URL collisions, 35 provider-ID reuse cases), plus 924 weak
fallback ambiguities that stay separate rather than being silently merged. These need a reviewed
resolution policy in the separately gated N7 migration plan; the offline foundation does not guess.

### Explicit remaining gates

- **N6/N6.1 complete.** The sanitized five-case probe returned two bodies and three explicit 10172
  unavailable responses. N6.1 preserves 10172 as typed unavailable evidence; N7 owns bounded retry
  and terminal policy without inferring `expired` from age.
- **N7 live migration complete.** Normalized schema/data now exists beside unchanged legacy `news`;
  the N7 backup remains the rollback point through N8 validation.
- **N8a implementation complete, live cutover not started.** Runtime still follows the pre-exit
  profile state until Task 13 begin/finalize is run. Scoring is not a PG-exit gate; it remains a
  standalone local Parquet/OpenAI CLI until a separate scoring redesign exists.
- **N9 legacy deletion not started.** The legacy `news` table, FileBackend fallback, mirror code,
  and old collection/scoring scripts remain until replacement paths pass the PG-unreachable gate.

Parquet is no longer the intended authority for the normalized end state. For now it remains a
frozen migration/enrichment source **and** a local legacy input for standalone scoring. It can be
frozen/archived and obsolete scripts removed only after N8b/N9 prove replacement readers and
tooling; that is separate from news PG-exit.

---

## N7 resolved migration (live complete, 2026-06-29)

N7 now has a source-wide Polygon URL policy, deterministic body ranking with cold variants,
bounded IBKR 10172 retry state, an immutable resolved plan, a row-group-batched Parquet body
reader, an atomic transaction-local writer, and a CLI that requires three independently reviewed
fingerprints plus explicit confirmation that the scheduler is paused. The implementation remains
additive and unrouted; the normalized schema is now populated beside the unchanged legacy tables.

### Reproduced real-input gate

Two complete read-only previews produced identical values:

- input fingerprint:
  `55aa79c33ebed92658dc8af232d12ae465d4d19c8ef3bf4556f2e0ed6c5442cc`;
- resolved fingerprint:
  `0b6008b64afa1c97021738b3faee81ac6fccc13404c04a704ffe8f757895cce7`;
- rejection-evidence fingerprint:
  `79c290856dafa45b75357224fdb6cde6292e7507700718a343a5146bdd1b6a67`;
- unreviewed blockers: `0`;
- articles `287,016`; identity keys `659,737`; ticker relations `618,170`; titles `287,039`;
- legacy rows `371,575`: mapped `370,635`, reviewed-rejected `940`;
- reviewed rejections: IBKR `924`, Polygon `16`; unique ticker/sentiment evidence `0/0`;
- provider timestamp drifts `35`; Polygon URL merges `35`; URL demotions `13`;
- body states: fetched `281,765`, failed `133`, pending `5,118`;
- body variants: `721` groups and `731` cold bodies. The input audit had 718 groups
  (IBKR 709 + Polygon 9); three additional Polygon groups become variants only after exact-URL
  provider groups merge, yielding the resolved Polygon count of 12.

| Source | Articles | Provider-ID matched | Fallback-only | Bodies | Missing | Variant groups | Cold bodies |
|---|---:|---:|---:|---:|---:|---:|---:|
| Finnhub | 85,674 | 85,025 | 0 | 82,610 | 3,064 | 0 | 0 |
| IBKR | 83,092 | 76,859 | 0 | 82,771 | 321 | 709 | 719 |
| Polygon | 118,250 | 118,028 | 4 | 116,384 | 1,866 | 12 | 12 |

Input immutability was checked before and after both previews: `market_data.db` remained
808,534,016 bytes with the same mtime and inode; normalized object count remained zero; all 103
Parquet files retained the same size/mtime/inode snapshot. Verification passed 145 hermetic tests
with six configured live-IBKR tests skipped, and all touched modules compile.

### Live apply result

After an independently reviewed full apply on a throwaway copy, the live migration ran in a quiet
window from master commit `e969371`. It completed as `run_id=1`, `already_applied=false`, in
14m48s with 6.15 GiB peak RSS and zero swap. The three reviewed fingerprints matched before the
backup or transaction began, and all planned counts above landed exactly.

Independent read-only post-checks found `PRAGMA quick_check=ok`, all 371,575 legacy rows unchanged,
370,635 mapped plus 940 reviewed-rejected migration-map rows, no Polygon URL keys, no active/cold
digest overlap, and zero FTS missing/orphan rows. FTS returned 44,531 hits for a real `earnings`
query. The WAL-safe pre-write backup is
`data/market_data.db.bak-pre-news-normalized-n7-20260629T133540443098Z.db`; it contains 371,575
legacy rows, zero normalized objects, and passes `quick_check`. Retain it through N8 validation.

### Remaining hard gates

- **Polygon URL demotion remains source-wide in N8.** New Polygon URL reuse must never regain
  strong-key semantics.
- **N8a runtime work is implemented and offline-verified, but the live cutover has not occurred.**
  Scoring is intentionally **outside** PG-exit: the existing scorer is a local Parquet/OpenAI CLI,
  not a PostgreSQL dependency and not part of the live read path. N8a therefore targets PG-exit
  only: normalized writers + legacy projection, strict local news behavior after the exit marker,
  IBKR normalized subprocess routing, news-only mirror/sync retirement, and a PG-unreachable gate.
- N9 legacy table/Parquet/script deletion remains blocked until N8b/N9 prove normalized reads and
  replacement tooling. The N8a compatibility projection keeps current readers on legacy `news`.

## N8a PG-exit implementation checkpoint (code/offline gate complete, 2026-06-30)

N8a is implemented in code but **not live-enabled**. No live `news_pg_exit_runs` begin/finalize
transition has been executed by this checkpoint; `news_pg_exit_completed` is not asserted here.
The live cutover remains Task 13 and requires a fresh preview, explicit operator approval,
scheduler/manual ingest pause, backup, validation JSON, and final PG-unreachable smoke.

Implemented behavior:

- A three-state route resolver separates legacy PG, legacy local, normalized, and blocked states.
  After `news_pg_exit_completed=true`, normalized writes are the only allowed news write path;
  explicit attempts to disable normalized writes fail closed rather than routing to PG.
- Polygon/Finnhub adapters can write through the normalized common writer, which transactionally
  projects to the existing `news`/`news_fts` compatibility tables. Current readers therefore remain
  on legacy `news` until N8b.
- IBKR keeps subprocess isolation via `collect_ibkr_news_normalized.py`; it no longer needs the old
  IBKR collector → Parquet → `migrate_to_supabase --news` → mirror chain after the exit marker.
- News hard-local behavior is gated by the audited exit marker. With the marker set, news reads and
  Settings status fail closed without `DATABASE_URL`; without it, pre-cutover behavior is preserved.
- Scheduler and manual market-data update paths exclude only the `news` mirror domain after the
  audited exit. Prices/IV/fundamentals mirror behavior remains untouched.
- Guarded begin/finalize/rollback tooling writes one immutable audit row and profile-state markers.
  Begin only enables normalized writes after the preflight report, backup, and audit row exist;
  finalize only marks exit complete after all required validation gates are exactly `passed`;
  rollback is allowed only from `testing` and checks audit eligibility before profile cleanup.

Offline verification for this checkpoint:

- Backend gate:
  `398 passed` for `tests/test_news_normalized_*.py`, `tests/test_news_n8a_cutover.py`,
  `tests/test_normalized_ibkr_worker.py`, scheduler/admin/backend/SA/news-settings/no-PG suites.
- Frontend gate: `200 passed` in Vitest, `npm run typecheck` clean, and production build clean.
- Python compile gate: `compileall` over `src/news_normalized`, scheduler, normalized IBKR worker,
  and cutover CLI passed.
- Hygiene: `git diff --check` passed.

This checkpoint is intentionally not a PG-exit completion claim. The live Task 13 cutover remains
blocked on explicit approval and post-cutover validation.
