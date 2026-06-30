# PG-Exit Completion — Scoping + Audit

Date: 2026-06-25
Status: **Slice 1 DONE + live-migrated; Step 2 IN PROGRESS.** Polygon/Finnhub news direct-local
cutover completed and live-verified 2026-06-27. The all-source normalized-news N7 migration is
live-applied and validated (2026-06-29). N8a news PG-exit code and offline verification are
complete (2026-06-30), but the hard-gated live begin/finalize cutover has **not** run; `ibkr_news`
still uses the old PG/mirror runtime path until that cutover. IV, fundamentals, remaining price
ingest, broader mirror retirement, SEC/dead paths, and UI collapse remain.

## Progress

- **Step 1 — app-records → local-primary: COMPLETE (live, 2026-06-26).** reports / memories /
  agent_queries now live in `profile_state.db`. Built across 1a (store) · 1b (factory routing,
  default-off) · 1c-core + core-fix (id-preserving migrator, 5 gates, full-hash, atomic) ·
  1c-api + fix + fix-2 (preview/apply routes + Settings panel; no-create preview, atomic apply,
  no-clobber backup-before-DDL). **Live migration run 2026-06-26:** preview 2 reports / 1 memory /
  2 queries, 0 conflicts → apply (timestamped backup + atomic, id-preserved [2,3]) → flipped
  `use_local_records` → verified `list_reports`/`get_report`/`recall_memories` route local. PG
  copy retained as the pre-migration archive; manual + timestamped backups on disk.
  **This does NOT complete the PG-exit** — steps 2–5 below remain; the market mirror/fallback/
  strict UI stays load-bearing.
- **Step 2 — ingest collectors → direct-local: IN PROGRESS.** Polygon/Finnhub news now default to
  provider → local SQLite with app-managed keys, direct telemetry, FTS/hash invariants, explicit
  Settings rollback, and a real-profile idempotent smoke. This bypasses PG sync/mirror only for
  those two scheduler sources. `ibkr_news` intentionally remains collector → PG → mirror, and the
  mirror remains load-bearing for IV/fundamentals and other unfinished ingest paths.
  The all-source normalized-news migration is now live (`news_articles`/body/ticker/key tables
  populated beside unchanged legacy `news`), and N8a has a normalized writer plus atomic legacy
  projection, isolated normalized IBKR worker, audited cutover tooling, strict local news behavior
  after the exit marker, and news-only mirror/sync exclusion. This is still **not live cutover**:
  the `news_pg_exit_completed` marker is not set here, and Task 13 must run the begin/finalize
  sequence plus PG-unreachable smoke before claiming news is off PG.
  Scoring is deliberately outside PG-exit: the current scorer is a local Parquet/OpenAI CLI and is
  not a runtime PostgreSQL dependency.

## Why this exists

The app has local SQLite stores (`market_data.db`, `sa_capture.db`, `macro_calendar.db`) and a
local-first READ toggle, but it is **not off PostgreSQL**: most ingest still writes PG→mirror, and
several domains (reports, memories, agent queries, SEC filings) are **PG-only — read and write**.
The Settings dual-mode controls (local mirror, use_local toggles, "fallback 回 PG", strict
modifier) are therefore still load-bearing, not redundant. This plan maps the exact remaining PG
surface (verified 2026-06-25) and sequences the work so those controls can finally collapse —
**after** the data actually lives local, never before.

## The PG surface today (verified against code)

Local SQLite backend (`sqlite_backend.py`) exposes **10 read methods + 1 write** (financial_cache);
it is a read-mostly mirror. The PG backend (`db_backend.py`) exposes **24 reads + the app-record
writes**. The delta is the work.

### Two fundamentally different sub-problems

**(1) Ingest data — provider→PG→mirror (regenerable, not user-authored).**
Prices / news / IV / fundamentals. Read locally (from the mirror) when the toggle is on, but the
WRITE path is still `collector → PG → local_incremental mirror` for 5 of 7 scheduler sources
(`polygon_news`, `finnhub_news`, `ibkr_news`, `ibkr_prices`, `iv_history`). Only `price_backfill`
writes direct-local (the template). Losing PG here loses nothing permanent — it's re-fetchable from
providers; the fix is **direct-local collectors** (apply the price_backfill pattern) + retire the
mirror.

**(2) App-records — PG-only, read AND write, USER/AGENT-AUTHORED (NOT regenerable).**
This is the load-bearing one. Verified PG-only, with **no local store and no mirror**:
- `research_reports` (sql/003) — `insert_report` / `query_reports` / `get_report_metadata`
- `agent_memories` (sql/004) — `insert_memory` / `query_memories` / `list_memories_meta`
- `agent_queries` (sql/001) — `insert_agent_query` (query log)
- `signals` (sql/001) — legacy

These are written by the app at runtime (saving a report, the agent writing a memory) **straight to
PG**, independent of collectors and independent of `use_local_market`. **If PG vanished, this data
is gone** — it is not re-fetchable. This is the real reason the app still needs PG, and the most
important part to localize carefully (it needs a one-time migrate of existing rows, not just a
re-fetch).

### Other PG-only reads (smaller)

- `query_sec_filings` — SEC filing metadata, PG-only (no local).
- `query_news_scores` — already RETIRED (news_scores deferred, §4 decision 2026-06-23); dead path.
- SA methods on `db_backend` (`query_sa_articles`, `query_sa_picks`, `get_sa_pick_detail`,
  `get_sa_article_with_comments`, `query_sa_market_news*`, `get_sa_refresh_meta`) — **SA already
  hard-cut to `sa_capture.db`** (2026-06-13) via the SA-capture backend. **VERIFY these db_backend
  SA methods are now dead** (the live SA read path is the local store); if so they are code-removal,
  not migration. Flagged, not assumed.

## Per-domain state (the audit table)

| Domain | Read local? | Write local? | PG still needed for | Class |
|---|---|---|---|---|
| Prices | ✅ (mirror + direct) | ⚠️ direct only via price_backfill; scheduler default = PG→mirror | scheduler ingest | (1) ingest |
| News | ✅ local | ✅ Polygon/Finnhub direct; ⚠️ IBKR via mirror until N8a live cutover | `ibkr_news` ingest until Task 13 | (1) ingest — partial |
| IV | ✅ (mirror) | ❌ PG→mirror | ingest | (1) ingest |
| Fundamentals | ✅ (mirror) + SEC/FD live | ❌ PG→mirror | ingest | (1) ingest |
| financial_cache | ✅ | ✅ (local-primary) | — | done |
| SA capture | ✅ (sa_capture.db) | ✅ | verify db_backend SA dead | mostly done |
| macro/cal | ✅ (toggle) | ✅ | — | done |
| **Reports** | ✅ local (profile_state.db) | ✅ local | PG = pre-migration archive | **DONE (Slice 1)** |
| **Memories** | ✅ local (profile_state.db) | ✅ local | PG = pre-migration archive | **DONE (Slice 1)** |
| **agent_queries** | ✅ local (profile_state.db) | ✅ local | PG = pre-migration archive | **DONE (Slice 1)** |
| SEC filings | ❌ PG-only | (cache) | read | (1)-ish — step 4 |

## Locked direction (from prior PG-exit work)

- Local-first, **PG demoted to import/archive** once a domain is direct-local (not a live runtime
  dependency). Matches the strict-local market mode + SA cutover + macro/cal decisions.
- App-records get a **local-primary store** in `profile_state.db` (the local app-state DB), the same
  home as schedule settings + the planned scheduler state — they are app state, not market data.
- **Migrate existing rows** for app-records (reports/memories are precious + not re-fetchable) —
  unlike ingest data, which we re-fetch rather than migrate (cf. the macro/cal "PG empty → skip
  migration, re-ingest" decision; app-records are the opposite — PG has the only copy).
- UI collapse is the LAST step, gated on the data actually being local.

## Ordered plan (each step independently shippable + verifiable)

The order is chosen so the **most load-bearing / least-recoverable** thing (app-records) is secured
early, and the UI only simplifies once each domain is truly local.

1. **App-records → local-primary (HIGH — do first).** Reports + memories (+ agent_queries) get a
   local store in `profile_state.db`, local-primary read/write, with a **one-time PG→local migrate**
   of existing rows (these are the irreplaceable ones). This removes the runtime PG write that fires
   every time a report is saved / memory written — the biggest "still needs PG" surface.
2. **Ingest collectors → direct-local.** Apply the `price_backfill` direct-write pattern to
   news / IV / fundamentals collectors (provider→local, no PG), behind the same kind of toggle, then
   make local the default. Prices' scheduler source switches to the direct path too.
   **NEWS chosen first** (high-frequency, user-visible, recoverable) — scoped in
   `NEWS_DIRECT_LOCAL_PLAN.md` (5 open decisions + a 2a–2d slice plan; note: news is provider→
   Parquet→PG→mirror today, not provider→PG). IV deferred until its source strategy is clearer.
3. **Retire the PG mirror.** Once all ingest is direct-local, `local_incremental` (本地鏡像增量) and
   the per-collector `sync_flag` PG-sync become dead — remove them. This is where the scheduler
   simplifies (and connects to the scheduler-hardening plan, which assumed direct-local).
4. **SEC filings + dead-path cleanup.** Localize `query_sec_filings` (or confirm it's covered by the
   SEC/FD live path), and remove verified-dead paths (`query_news_scores`, db_backend SA methods).
5. **Collapse the dual-mode UI (LAST).** Remove/relabel the now-redundant controls: local mirror
   button, use_local_* toggles (or flip default-on + hide), "fallback 回 PG" / strict-mode copy.
   This is the redundancy the user noticed — real only after steps 1–4.

## PG-exit DONE criteria (locked 2026-06-26)

"PG exit" is complete only when ALL hold (not before — partial domain localization ≠ PG exit):
1. The app starts normally with PG unreachable / no `DATABASE_URL`.
2. Normal runtime read/write needs no PG.
3. The scheduler fetches provider→local DB directly — no PG mirror step.
4. PG is archive/import-only, never in the normal app path.
5. Settings no longer needs PG-fallback / local-mirror / strict dual-mode controls.
6. Tests include a "PG unreachable" scenario proving normal use doesn't stall or fall back.

## Resolved decisions (were open questions)

1. App-record home → tables in `profile_state.db` ✅ (shipped Slice 1).
2. Migration trigger → explicit Settings preview/apply ✅ (shipped 1c-api).
3. Toggle → per-domain through the migration; collapse to one in step 5.
4. Order → app-records FIRST ✅ done; then the remaining order below.
5. Scheduler hardening → after the shared `ibkr_gateway_lock` + local scheduler state, starting
   with gap-aware `price_backfill`; then ingest direct-local. (The lock extraction is next.)

## Relation to other plans

- **Scheduler hardening** (`SCHEDULER_HARDENING_PLAN.md`) assumed direct-local + the shared
  `ibkr_gateway_lock`; steps 2–3 here produce exactly that base. The lock-extraction precursor is
  shared.
- **Intraday behavior** + **coverage panel** already follow the local-first/metrics-first pattern;
  this plan brings the rest of the app to the same baseline.
- This supersedes nothing; it sequences the remaining PG-exit work the earlier slices started.
