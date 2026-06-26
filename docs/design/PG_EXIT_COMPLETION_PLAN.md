# PG-Exit Completion — Scoping + Audit

Date: 2026-06-25
Status: scoping → **Slice 1 (app-records) DONE + live-migrated 2026-06-26**; steps 2–5 pending.

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
| News | ✅ (mirror) | ❌ PG→mirror | ingest | (1) ingest |
| IV | ✅ (mirror) | ❌ PG→mirror | ingest | (1) ingest |
| Fundamentals | ✅ (mirror) + SEC/FD live | ❌ PG→mirror | ingest | (1) ingest |
| financial_cache | ✅ | ✅ (local-primary) | — | done |
| SA capture | ✅ (sa_capture.db) | ✅ | verify db_backend SA dead | mostly done |
| macro/cal | ✅ (toggle) | ✅ | — | done |
| **Reports** | ❌ **PG-only** | ❌ **PG-only** | **read+write+history** | **(2) app-records** |
| **Memories** | ❌ **PG-only** | ❌ **PG-only** | **read+write+history** | **(2) app-records** |
| **agent_queries** | ❌ PG-only | ❌ PG-only | query log | (2) app-records |
| SEC filings | ❌ PG-only | (cache) | read | (1)-ish |

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
3. **Retire the PG mirror.** Once all ingest is direct-local, `local_incremental` (本地鏡像增量) and
   the per-collector `sync_flag` PG-sync become dead — remove them. This is where the scheduler
   simplifies (and connects to the scheduler-hardening plan, which assumed direct-local).
4. **SEC filings + dead-path cleanup.** Localize `query_sec_filings` (or confirm it's covered by the
   SEC/FD live path), and remove verified-dead paths (`query_news_scores`, db_backend SA methods).
5. **Collapse the dual-mode UI (LAST).** Remove/relabel the now-redundant controls: local mirror
   button, use_local_* toggles (or flip default-on + hide), "fallback 回 PG" / strict-mode copy.
   This is the redundancy the user noticed — real only after steps 1–4.

## Open questions (need the user's call before slicing)

1. **App-record local home + schema.** One store per record type in `profile_state.db`
   (`reports` / `memories` / `agent_queries` tables) mirroring the PG schema, or a dedicated
   `app_records.db`? Lean: tables in `profile_state.db` (it's already the local app-state DB).
2. **App-record migration trigger.** A one-time Settings "migrate app-records from PG" action (like
   the market bootstrap), or automatic on first local-mode boot if PG reachable? Lean: explicit
   Settings action (precious data, user-visible).
3. **Toggle-per-domain vs. one master switch.** Keep per-domain toggles through the migration
   (use_local_market / _macro / _sa + a new use_local_records), or introduce ONE "local mode" master
   once enough domains are local? Lean: per-domain until step 5, then collapse.
4. **Does step 1 or step 2 go first?** App-records (least recoverable) vs. ingest (more sources,
   bigger). Lean: app-records first (this plan's order) — but if the user's priority is killing the
   visible mirror button fastest, ingest-first + retire-mirror reorders to 2→3→1.
5. **Scheduler hardening interleave.** It was deferred for this; but step 2/3 (direct-local ingest +
   mirror retire) overlap heavily with it. Do them as one combined arc, or finish PG-exit ingest
   then return to scheduler hardening? Lean: finish ingest localization, then scheduler hardening on
   the clean direct-local base.

## Relation to other plans

- **Scheduler hardening** (`SCHEDULER_HARDENING_PLAN.md`) assumed direct-local + the shared
  `ibkr_gateway_lock`; steps 2–3 here produce exactly that base. The lock-extraction precursor is
  shared.
- **Intraday behavior** + **coverage panel** already follow the local-first/metrics-first pattern;
  this plan brings the rest of the app to the same baseline.
- This supersedes nothing; it sequences the remaining PG-exit work the earlier slices started.
