# Data Collection & Local Storage Plan

> **Doc type:** Decision-first design record (load-bearing)
> **Status:** DRAFT — proposed, not yet locked. Architecture authority remains `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md`; this doc refines the data-collection + storage slice of that spec and must yield to it on any conflict.
> **Drafted:** 2026-06-07 (from the data-collection-audit workflow). Promote to **Adopted** only after the §10 open questions are locked.
> **Scope:** How ArkScope collects market/news/SA data, at what cadence, where it is stored (local-first SQLite vs remote PostgreSQL), how it migrates off remote PG, how price data is layered for charting, and how `daily_update.py` is repositioned. Companion to the three canon docs (Workbench Product Spec / Provider Catalog / Tool Catalog).

---

## 0. Status & decision summary

ArkScope collects data in **three distinct modes** that today are blurred together inside one batch script and one remote database. This doc separates them and pins down storage.

**Decision (summary):** Collection is split into (1) **manual backfill** (heavy, on-demand historical pulls), (2) **incremental-scheduled** (the protected news/price ingestion that keeps the cockpit fresh), and (3) **realtime-display** (ephemeral live quotes for the chart edge — *not yet implemented*, snapshot-only today). User state moves to a **three-way local SQLite split** — `profile_state.db` (precious user work), `market_data.db` (regenerable provider mirror, DuckDB candidate), `sa_capture.db` (isolated Seeking-Alpha capture) — while **remote PostgreSQL** (`<postgres-host>:<port>`) stays the source of truth until one verified cross-machine migration passes (the workbench resume gate). `daily_update.py` is reframed as a **manual/cron backfill runner** and three specific old-tier-model couplings are removed. Price data adopts a **3-tier granularity model** (ephemeral realtime / short-retention intraday / permanent adjusted daily) with all chart indicators computed **deterministically from OHLCV, never by the LLM**. The Seeking-Alpha extension → native-host path is a **protected ingestion pipeline** and must keep working byte-for-byte through the migration.

**What is explicitly NOT in scope here:** the RL-trading line (retired), continuous *user-state* sync (a separate desktop concern, must not be layered onto the batch runner), and v2 knowledge-graph / analysis-pipeline work (deferred per SPEC §11).

---

## 1. Three collection modes

| Mode | What it is | Providers / jobs | Trigger | Persistence target |
|---|---|---|---|---|
| **A. Backfill (manual / on-demand)** | Heavy historical pulls to seed or repair the data store. Expensive, Gateway/PG-dependent, run by hand or cron. | IBKR prices (full history), IV / options history, full-universe fundamentals, daily-adjusted history (`fetch_adjusted_prices`) | Explicit flag or operator action (never swept in automatically — see §7) | Parquet + remote PG today → `market_data.db` after migration |
| **B. Incremental-scheduled** | The protected freshness path: small `--incremental` deltas that keep cards/charts current. | **Polygon news**, **Finnhub news**, **IBKR news** (Gateway-gated), 15min IBKR price deltas; LLM sentiment/risk scoring (`news_scores`) | Scheduled (cron) or `daily_update.py --news`; cockpit-driven refresh | Parquet + remote PG (`news`, `news_scores`, `prices`) today → split DBs after migration |
| **C. Realtime-display (ephemeral)** | The live edge of the chart: forming candle, blinking last price, intraday % change. | IBKR live market data | Continuous while a symbol is open in the UI | **In-memory only** (no persist by default) |

**Status notes:**
- Modes A and B both exist today and run through `scripts/collection/daily_update.py` (subprocess orchestrator, 881 lines) → sibling `collect_*.py` → `scripts/migrate_to_supabase.py` → remote PG. All current DB writes are **remote PG only**; no local SQLite, no RL writeback (verified across the full file).
- **Mode C is NOT implemented.** Today the only "realtime" is a one-shot snapshot: `data_sources/ibkr_source.py:926` (`get_current_quote` → `reqMktData(contract, '', True, False)` with `snapshot=True`, then a blocking 2s sleep). **There is no `reqRealTimeBars`, no `reqTickByTick`, no `pendingTickersEvent` subscription anywhere** — a continuous live stream is new code to build.

---

## 2. Provider / job frequency model

Per-source cadence, retention, health surface, and cost gate. Provider-level data/latency/cost facts are authoritative in **`ARKSCOPE_PROVIDER_CATALOG.md`**; this table is the *collection-cadence* view.

| Source / job | Enabled | Refresh mode | Interval | Retention / downsample | Health fields | Cost gate |
|---|---|---|---|---|---|---|
| **Polygon news** | yes | scheduled (`--incremental`) | hourly–daily | Parquet raw, permanent | connected / stale / last_success / last_error | free (tiered) |
| **Finnhub news** | yes | scheduled (`--incremental`) | hourly–daily | Parquet raw, permanent | connected / stale / last_success / last_error | free (rate-limited; 429-prone → circuit breaker §9) |
| **IBKR news** | yes (Gateway-gated) | scheduled (`--incremental`) | daily | Parquet raw, permanent | connected / maintenance (Gateway down) / last_success / last_error | free (needs IB session); **known limitation:** `reqHistoricalNews` ignores time-range (`docs/data/IBKR_NEWS_API_LIMITATIONS.md`) |
| **IBKR prices — 15min (base)** | yes (Gateway-gated) | scheduled / backfill | daily delta; backfill on demand | base granularity, ~1–2y; live PG = **2.25M rows, 148 tickers, 2024-01-02→2026-06-05, `15min` only** | connected / maintenance / last_success / last_error | free (IB session) |
| **IBKR prices — 1m / 5m** | proposed | backfill | manual | 1m ~30–60d, 5m ~6–12m (§6) | as above | free; pacing ≤60 hist reqs/10min (`ibkr_source.py:223-229`) |
| **IBKR prices — 1d (adjusted)** | proposed | backfill | manual / periodic | **permanent** (`fetch_adjusted_prices`, `ADJUSTED_LAST`, `ibkr_source.py:1163`) | as above | free (IB session) |
| **IV / options history** | yes (Gateway-gated) | **opt-in backfill** (currently swept by `--all` — see §7) | manual | `iv_history`, permanent | connected / maintenance / last_success / last_error | free (IB session); heavy |
| **Fundamentals** | yes | manual / cached | on demand | TTL: annual 180d / quarterly 90d / ttm 30d | connected / stale / last_success / last_error | **fallback chain:** IBKR snapshot → SEC EDGAR (free) → Financial Datasets (**metered**, cached). Not wired into `daily_update.py` (absent, not stale). |
| **Macro / calendar (FRED + Finnhub)** | yes | scheduled | per release schedule | `macro_*`, `cal_*` tables, permanent | per-table count + last-fetched (`macro_calendar_health.py:449-459`) | free |
| **Analyst consensus (Finnhub)** | yes | scheduled cache | 24h TTL | daily cache | connected / stale / last_success | free |
| **LLM sentiment/risk scoring** | yes | scheduled (piggybacks news today — to decouple, §7) | with news | `news_scores`, permanent | n/a (compute job) | **metered** (LLM API cost) |
| **SA capture (extension)** | yes | **realtime push** (user browses) + extension-driven refresh | event-driven | `sa_*` tables, permanent | per-scope `sa_refresh_meta` (last_attempt/last_success/snapshot_ts/row_count/ok/last_error, `db_backend.py:1224-1234`) | free (user session); **protected path** §5 |
| **Realtime quote stream (Tier 0)** | **NO (to build)** | realtime | continuous while symbol open | none (memory) | connected / stale / maintenance | free (IB session) |

**Cost-gate vocabulary:** `free` (no marginal cost) · `metered` (per-call API cost, must show usage) · `manual-approval` (operator must explicitly enable per run — reserved for paid backfills, e.g. Financial Datasets bulk pulls).

**Provider-health vocabulary (surfaced in the ops view):** `connected` · `stale` (last_success older than TTL) · `maintenance` (provider/Gateway intentionally down or unreachable) + timestamps `last_success` / `last_error`. These map directly onto the DSA `ProviderRun` telemetry and `CircuitBreaker` state (§9).

---

## 3. Local DB split

Three SQLite files, each with a distinct durability/backup policy. Path resolution mirrors the existing pattern in `src/api/dependencies.py:30-79` (`_local_state_db_path`).

### 3a. `profile_state.db` — precious local-first user state (back up aggressively)
The "lose-this-and-you-lose-the-user's-work" DB. Three modules **already share this one file today** (`ARKSCOPE_PROFILE_DB`):
- `src/profile_state.py` (`:36-98`) — lists/memberships/notes/meta/tags/settings
- `src/card_runs.py` (`:13`, `:26-47`) — `ai_card_runs`
- `src/model_credentials.py` (`:81-94`) — `llm_credentials`

### 3b. `market_data.db` — regenerable provider mirror (**SQLite first**, DuckDB later)
High-volume, read-heavy in the cockpit, regenerable from providers. Folds in the
currently-standalone `data/cache/analyst_consensus.db` (`ARKSCOPE_CONSENSUS_DB`).
**Engine decision (2026-06-07): the first cut is SQLite (WAL + busy_timeout), NOT
DuckDB.** Reason: incremental jobs WRITE while the UI READS concurrently, and
SQLite's WAL + `busy_timeout` is the better-controlled story for mixed small
write + concurrent read (same hardening already used by the other stores). DuckDB
remains the long-term **analytic / read-heavy** engine — used as a batch /
materialized read model over the SQLite (or Parquet) market data, **not** as the
target for multi-process high-frequency small writes. Do not point the extension
or any high-write job directly at DuckDB.

### 3c. `sa_capture.db` — isolated Seeking-Alpha capture (regenerable by re-capture)
Written **exclusively** by the extension → native-host path, independent of the API server's request lifecycle. Isolated for lock-blast-radius and schema-evolution reasons (§5f below).

### Table → DB mapping

| Table(s) | Target DB | Source today | Citation |
|---|---|---|---|
| `watchlists`, `watchlist_memberships`, `ticker_notes`, `ticker_meta`, `ticker_tags`, `profile_settings` | **profile_state.db** | already local SQLite | `profile_state.py:36-98` |
| `ai_card_runs` | **profile_state.db** | already local SQLite (same file) | `card_runs.py:26-47` |
| `llm_credentials` | **profile_state.db** | already local SQLite (same file) | `model_credentials.py:81-94` |
| `prices` | **market_data.db** | remote PG | `db_backend.py:591` |
| `fundamentals` | **market_data.db** | remote PG | `db_backend.py:657` |
| `iv_history` | **market_data.db** | remote PG | `db_backend.py:635` |
| `financial_data_cache` | **market_data.db** | remote PG | `db_backend.py:1029,1053` |
| `analyst_consensus` | **market_data.db** | separate `data/cache/analyst_consensus.db` (fold in) | `analyst_consensus.py:27-39` |
| `macro_series`, `macro_observations`, `macro_release_dates` | **market_data.db** | remote PG | `store.py:457,528,598` |
| `cal_economic_events`, `cal_earnings_events`, `cal_ipo_events` + `*_revisions` | **market_data.db** | remote PG | `store.py:219/303/388` |
| `news`, `news_scores`, `news_latest_scores` | **market_data.db** | remote PG | `db_backend.py:334,354,398` |
| `sa_alpha_picks`, `sa_refresh_meta`, `sa_market_news`, `sa_articles`, `sa_article_comments`, `sa_comment_signals` | **sa_capture.db** | remote PG | `db_backend.py:1200,1226,1405,1624,1699`; `comment_signal_backfill.py:223` |
| `agent_queries`, `agent_memories`, `research_reports`, `job_runs` | **stays remote PG initially** (app records; revisit) | remote PG | `db_backend.py:1001,859/931,752/807`; `job_runs_store.py` |
| `symbol_catalog` (ticker→name) | **JSON file** (`data/cache/sec_company_tickers.json`, not a DB) | reference data | `symbol_catalog.py:10-12` |

**Backend mechanics:** introduce a `SqliteBackend`/`LocalBackend` implementing the existing `DataBackend` protocol (`db_backend.py:248`) alongside `DatabaseBackend`. The DAL already abstracts backend choice (`data_access.py:166-197`), so call sites in `sa_tools.py`, card/report tools, and the native host **do not change** — only the backend the DAL constructs.

### 3d. DAL domain routing (required for PG + local to coexist)
A single-backend DAL **cannot** express "market data → local SQLite, but SA + app
records → PG" — which is exactly the migration's intermediate state (and the
deliberate end state for SA until its quiet-window cutover). So slice 3 adds a
**composite / domain-routing backend**: the DAL dispatches each operation to a
backend by **data domain**, not one global backend.

| Domain | Backend (target state) |
|---|---|
| profile (lists/tags/priority/notes/cards/credentials) | `profile_state.db` (SQLite) — already local |
| market (prices/news/fundamentals/IV/macro/calendar/consensus) | `market_data.db` (SQLite) |
| SA capture (`sa_*`) | **PG for now** → `sa_capture.db` only at the §5g quiet-window cutover |
| app records (`agent_queries`/`agent_memories`/`research_reports`/`job_runs`) | **stays PG** (revisit later) |

This routing is what lets slice 3a (market → local) ship **without** touching SA,
and lets SA keep writing PG on weekdays. Each domain keeps its own
`DatabaseBackend`(PG) or `SqliteBackend`(local) instance behind the protocol.

---

## 4. PostgreSQL → local migration strategy (phased)

PG stays the source of truth until **one verified cross-machine migration passes** (matches the workbench resume gate). Cutover order = lowest blast radius first.

| Phase | Tables moving | Why this order | What stays in PG meanwhile |
|---|---|---|---|
| **Phase 0 — no-op** | none | `profile_state.db` is already local SQLite; nothing to migrate. | everything market/SA/app |
| **Phase 1 — market_data** | `prices`, `fundamentals`, `iv_history`, `financial_data_cache`, `analyst_consensus`, `macro_*`, `cal_*`, `news`/`news_scores`/`news_latest_scores` | **Regenerable** — safe to migrate and re-fetch on mismatch. Read PG via current backend → write local; validate by row counts + content checksum on a sample. The macro/calendar health query (`macro_calendar_health.py:449-459`) is a ready per-table count/last-fetched cross-check. | SA tables; agent/app records |
| **Phase 2 — sa_capture** | `sa_alpha_picks` (+ lifecycle), `sa_refresh_meta`, `sa_market_news`, `sa_articles`, `sa_article_comments`, `sa_comment_signals` | **Single-writer, re-capturable.** Must port the **partial-index `ON CONFLICT … WHERE` upserts** (`db_backend.py:1170-1196`) — SQLite supports partial-index upserts, but the index predicates must be recreated as real partial indexes in the new schema. | agent/app records |
| **Phase 3 — app records (revisit)** | `agent_queries`, `agent_memories`, `research_reports`, `job_runs` | Lower priority; decide local vs remote after the user-facing split is stable. | — |

**PG-ism translation checklist (apply during every port):** `NOW()` → `CURRENT_TIMESTAMP`; `psycopg2.extras.Json` → `json.dumps`; `%s` → `?`; `RealDictCursor` → `sqlite3.Row`; partial-index upserts recreated as real partial indexes.

**Path resolution:** env override (`ARKSCOPE_MARKET_DB`, `ARKSCOPE_SA_DB`, reuse `ARKSCOPE_PROFILE_DB`) → default under `data/`, resolved next to `_local_state_db_path` (`dependencies.py:76-79`). `DatabaseBackend` is kept as an optional/legacy backend behind the same protocol throughout, so PG remains a live fallback.

---

## 5. Seeking-Alpha capture isolation (protected ingestion path)

The SA capture pipeline is an **existing, protected ingestion path** — the migration must keep it working byte-for-byte. It must NOT be treated as a future feature.

### 5a. Write path (extension → native host → DAL → backend)
1. **Browser extension** `extensions/sa_alpha_picks/background.js` captures SA pages → `chrome.runtime.sendNativeMessage`.
2. **Native messaging host** `scripts/sa_native_host.py` (host id `com.mindfulrl.sa_alpha_picks` — **intentionally lowercase `mindfulrl`, do not "fix"**) — Chrome spawns a **fresh, short-lived process per message**, reads length-prefixed JSON, then `dal = DataAccessLayer(db_dsn="auto")` and dispatches by action (`sa_native_host.py:59-90`).
3. **All persistence flows through DAL → `DatabaseBackend` → PG today**, e.g. `refresh` → `dal.apply_sa_refresh(...)` (`sa_native_host.py:210`; `db_backend.py:1137-1234`), `refresh_failure` → `dal.record_sa_refresh_failure(...)` (`:236`/`:1257`), `save_detail[_by_symbol]` (`:320/350`), market news (`:387/423`), articles/comments (`:443/607/627`).

### 5b. Alpha Picks open → closed lifecycle (lives in `sa_alpha_picks`)
- `portfolio_status` ∈ {`current`, `closed`}; `closed_date`; `return_pct`; and an **`is_stale`** flag set when a row is absent from the latest snapshot.
- Upserts use **partial unique indexes per status** (`db_backend.py:1160-1220`) — this is the exact construct that needs careful porting in Phase 2.

### 5c. Capture-health DTO (`sa_refresh_meta`)
Per-scope capture health: `last_attempt` / `last_success` / `snapshot_ts` / `row_count` / `ok` / `last_error` (`db_backend.py:1224-1234`). This is the SA-specific health surface that feeds the ops view (§8) alongside the generic provider-health fields.

### 5d–5f. Why `sa_capture.db` is its own file
- **Separate process boundary:** Chrome spawns the native host fresh per message, outside the FastAPI server; a separate DB file means its connections never contend with the API server's connections.
- **Lock blast radius:** SQLite locks at the file level. A long SA refresh/backfill (bulk comment inserts `db_backend.py:1699`; `comment_signal_backfill.py:223`) holding a write lock would otherwise stall unrelated cockpit reads. Isolation confines any `database is locked` stall to SA reads.
- **Independently-evolving schema:** SA has the richest, fastest-changing schema (lifecycle, market news, threaded comments with parent re-parenting `db_backend.py:1764`, derived signals). Its own file lets that schema migrate without risking the user's hand-curated `profile_state.db`.

### 5g. Cutover window (the SA extension is always running)
The extension → native-host path writes continuously while the user browses SA. Re-pointing its DB target (PG → `sa_capture.db`) needs a **quiet window** so no capture lands mid-cutover. Decision (2026-06-07): do the `sa_capture` (Phase 2) cutover **on a Saturday with US markets closed (target 2026-06-13)** as a one-shot, *unless* the move is proven fast + clean enough to do safely in a weekday morning. Since the DB-split code (slice 3) is not built yet, Saturday is the realistic target; the dry run + validation (row-count + checksum) happen on a copy first. Phase 1 (`market_data`, regenerable) carries no such constraint and can cut over any time.

---

## 6. Price granularity & retention

### Current state (verified)
- **API exposes only 3 intervals:** `interval ∈ {15min, 1h, 1d}`, regex-pinned (`src/api/routes/prices.py:19`); same enum in `registry.py:277-278` and both agent bridges (`anthropic_agent/tools.py:184`, `openai_agent/tools.py:228`).
- **Only `15min` is STORED.** Live PG `prices` = **2,248,970 rows, 148 tickers, `15min` only, 2024-01-02 → 2026-06-05; zero `1h`/`1d` rows.** Schema `sql/001_init_schema.sql:35-46`, `UNIQUE(ticker, datetime, interval)`.
- **`1h`/`1d` are derived on read, never stored:** server-side `date_trunc` aggregation over `15min` (`db_backend.py:600-619`); FileBackend mirrors with a Python resample (`price_tools.py:23-59`).
- **Only `15min` is ingested to PG:** `migrate_to_supabase.py:490,521,545` (hardcoded `"15min"` literal). The collector *does* fetch `1 hour`/`1 day` into CSV/`data/prices/hourly/` (`collect_ibkr_prices.py:390,504`) but **those are never loaded into PG** — stray files at best.
- **IBKR source can do far more:** full bar ladder `1 secs … 1 month` (`ibkr_source.py:201-207`); fetch methods `fetch_prices` (`:633`), `fetch_intraday_prices` (`:717`), `fetch_historical_intraday` (auto-chunked: 1min≈10d, 5min≈30d, 15min≈60d per req, `:786,819-825`), `fetch_adjusted_prices` (`ADJUSTED_LAST`, `:1163`).

**Net gap:** UI can request `1d`/`1h`, but every non-`15min` bar is recomputed from `15min` each call → **no daily history older than the 15min floor (~Jan 2024), no sub-15min detail, no realtime stream.**

### Layered proposal (3 tiers)

| Tier | Interval(s) | Source method | Stored? | Retention | Derivation |
|---|---|---|---|---|---|
| **0 — Realtime display** | live ticks / 5s bars | **stream to build** (`reqRealTimeBars` / `reqTickByTick` / non-snapshot `reqMktData` + `pendingTickersEvent`) | no (memory) | session | roll up → 1m, then discard |
| **1 — Short-term intraday** | 1m, 5m | `fetch_historical_intraday` (auto-chunked) | yes | 1m ~30–60d, 5m ~6–12m | 1m→5m→15min rollup |
| *(base)* | 15min | `fetch_historical_intraday` | yes (live: 2.25M rows) | ~1–2y | base for 1h |
| **2 — derived hourly** | 1h | — | no (derive) | — | `date_trunc` from 15min (existing `db_backend.py:603-616`) |
| **2 — Long-term daily** | 1d | `fetch_adjusted_prices` (`ADJUSTED_LAST`) | **yes (NEW)** | permanent | native; store `adj_close` |

**Mechanics:**
- New interval values `'1m'`/`'5m'`/native `'1d'` reuse the existing `(ticker, datetime, interval)` key — **no migration needed**, just widen the `VARCHAR(10)` usage and the API regex/enum (`prices.py:19`, `registry.py:278`, both bridges).
- Promote the on-read `date_trunc` SQL (`db_backend.py:603-616`) to **one reusable rollup** so all intervals share the same first-open/last-close/max-high/min-low/sum-volume definition.
- For Tier 2, **store both unadjusted and adjusted close** (`adj_close` column for `1d`; the IBKR dataclass already carries it) so split discontinuities don't corrupt long charts or indicator math.
- Keep on-read aggregation as the **fallback** (a missing interval still renders) but prefer native stored `1d` so daily history isn't bounded by the 15min floor.
- **Session awareness:** carry RTH vs extended-hours (`useRTH`) so gaps render correctly. Volume sub-panel is free wherever bars exist (schema already has `volume`).

### Deterministic technical indicators (from OHLCV — NOT LLM)
All chart indicators are computed **deterministically from stored OHLCV, never produced by the LLM** (the LLM narrates; numbers come from the data). This enforces the signal-subsystem rule: *AI-card evidence stays pure-objective — clean OHLCV technicals, NO judgment.* Indicators the chart layer derives directly:
- **Trend/overlays:** SMA/EMA (20/50/200), VWAP (needs intraday volume, Tier 0/1), Bollinger Bands.
- **Momentum/oscillators:** RSI, MACD, stochastic, ROC.
- **Volatility/range:** ATR, realized/historical volatility, true range, range bands. (Compute from our own OHLCV, not IBKR's `HISTORICAL_VOLATILITY` `whatToShow`, for consistency.)
- **Volume-based:** OBV, volume MA, relative volume, accumulation/distribution.
- **Returns/change:** already deterministic — `get_price_change` (`price_tools.py`), `get_sector_performance` (`prices.py:28,38`).

Implement as a small pure-Python/pandas (or SQL-window) module in the FastAPI sidecar, computed server-side and shipped with the bars — reproducible, testable, LLM-free.

---

## 7. `daily_update.py` new positioning + old-model pollution to remove

> **✅ IMPLEMENTED 2026-06-08** (commits `a765c85` + follow-up `c70b83d`). All three
> couplings below are removed; the script is now a backfill runner with explicit
> `--scope active-universe` / `--tickers`, opt-in `--scores`, and dry-run that never
> touches DB/IBKR. **The `line NNN` references below are PRE-slice-2 (the audit
> snapshot); the code has since shifted — they document what *was* found, not current
> line numbers.**

**File:** `scripts/collection/daily_update.py` (was 881 lines). It is a **subprocess orchestrator** over sibling `collect_*.py` and `migrate_to_supabase.py`; it writes no DB itself, touches **remote PG only**, has **no SQLite/`profile_state.db` writes, and no RL/reward/PPO references anywhere** (verified full-file).

### New positioning
Reframe as a **manual / on-demand backfill runner** — explicitly *not* the desktop app's continuous-sync engine. The always-on workbench sidecar's continuous sync of *user state* is a separate concern and must not be layered onto this batch runner. Position it as: *"run by hand or by cron to backfill historical market/news data into Parquet + remote PG."*

Principles:
- **Keep the protected ingestion collectors LIVE and unchanged:** Polygon (`:546`), Finnhub (`:563`), IBKR news (`:580`) incremental fetches stay. This script remains a thin orchestrator over them.
- **Make heavy/stateful steps opt-in, not bundled under `--all`:** IV history (`:618`), full-universe IBKR prices (`:597`), and `--scores` DB push (`:668`) each require their own explicit flag.
- **Clarify the DB boundary:** all writes go to remote PG via `migrate_to_supabase.py` — correct for market/collection data, must stay out of local user-state DB.

### Old-model pollution to REMOVE (cited)

**(a) `user_profile.yaml → tickers_core.json` writeback — VERIFIED def `line 112`, unconditional call `line 784`.**
`sync_watchlist_tickers(dry_run=…)` runs on **every** non-`--status` invocation, before any flag branching: reads `user_profile.yaml` watchlists (`_extract_watchlist_tickers` `:80-98`), diffs against `tickers_core.json` (`:101-109`), and **writes new tickers into `tier3_user_watchlist.watchlist_auto_sync`** (`json.dump` `:177-179`). This couples the data-fill job to the **retired tier model** (`tier1_core`/`tier2_expanded`/`tier3_user_watchlist`) and to `user_profile.yaml`, both superseded by the SQLite active-universe + 2D-tags model. It silently mutates a tracked config file as a side effect. **Action:** remove the call at `:784` and the now-dead helpers `:80-182`.

**(b) `--tier all` IBKR price dependency — VERIFIED `line 597`.**
`cmd = [sys.executable, str(script), "--incremental", "--minute-only", "--tier", "all"]`. `--tier all` resolves in `collect_ibkr_prices.py` to **all three retired tiers** (`tier1_core` + `tier2_expanded` + `tier3_user_watchlist`, `:105-108`; argparse choices `:557-559`), forcing a full legacy-universe pull in one Gateway session. **Action (Q7 LOCKED):** drop `--tier all`; the scope must be **explicit** — either `--tickers <list>` or `--scope active-universe`, the latter **READING** the SQLite active universe (`profile_state.db`) **read-only** (it must never write back to `user_profile.yaml`/`tickers_core.json`). `--all` must NOT implicitly guess a scope.

**(c) `--sync-db` scores sync — VERIFIED `line 668` (real lines `666-672`).**
Comment `# Also sync multi-model scores` (`:666`) → `cmd = [… "--scores"]` (`:668`) → run (`:671`) → record (`:672`). It **piggybacks on the news-sync branch** (`if sync_news:` `:658`), so any news collection with `--sync-db` force-pushes LLM sentiment/risk `news_scores` into PG even when no new scoring was produced. This is **not RL writeback** (confirmed) but is an old-pipeline coupling. **Action:** make `--scores` a **separate, explicit step**, not an automatic tail of every news fill.

> **Note on fundamentals:** NOT wired into `daily_update.py`. `migrate_to_supabase.py` supports `--fundamentals` (argparse `:697`) but `daily_update` never builds that command — so fundamentals is **absent here, not stale**.

---

## 8. Settings / System UI controls to expose

Driven by the Provider Catalog (per-provider auth/limits) and the health vocabulary above.

**Provider configuration (Settings):**
- Per-provider enable/disable + credential entry (IBKR Gateway host/port — `data_sources/IBKR_GUIDE.md` already anticipates this; Polygon/Finnhub/FRED API keys; Financial Datasets paid toggle).
- Refresh-mode + interval selector per source (manual / scheduled / realtime), matching §2.
- Cost-gate acknowledgement for **metered** sources (Financial Datasets, LLM scoring): show estimated cost, require explicit enable for `manual-approval` backfills.
- Retention knobs per price tier (1m days, 5m months — §6).

**System / ops health view (small, *inside* the workbench — not the product surface):**
- Per-provider status chip: `connected` / `stale` / `maintenance` + `last_success` / `last_error` (from `ProviderRun` telemetry §9).
- SA capture health from `sa_refresh_meta`: per-scope last_attempt/last_success/snapshot_ts/row_count/ok/last_error.
- Circuit-breaker state per source (closed/open/half-open).
- Job-run log (`job_runs`) + last backfill summary.
- DB location + size per local file (`profile_state.db` / `market_data.db` / `sa_capture.db`); migration status (which phase, PG-fallback active?).

*(This ops view is the post-pivot repositioning of the P1.5 S3 spike — a small health view inside the workbench, not a standalone admin product.)*

---

## 9. Borrow from `daily_stock_analysis` (US-first)

Source repo confirmed at `<workspace>/daily_stock_analysis`. The provider/fallback design lives in code (no narrative doc). **Borrow these five; skip all A-share machinery.**

### BORROW

| Capability | File / location | Why it fits ArkScope |
|---|---|---|
| **Unified realtime-quote dataclass with quality metadata** | `data_provider/realtime_types.py` → `UnifiedRealtimeQuote` (L108-187), `RealtimeSource` enum (L94-105) | One provider-neutral quote struct with `fetched_at`/`provider_timestamp`/`is_stale`/`stale_seconds`/`fallback_from` layered on price+volume. Lets ArkScope merge IBKR/Polygon/Finnhub into one card-facing type and **show provenance + staleness** instead of a bare number. `to_dict()` drops `None`s (clean JSON for sidecar→React); `safe_float`/`safe_int` coercion helpers (L34-91) normalize messy payloads. Treat `code` as a US ticker; A-share idioms (`turnover_rate`/`amplitude`/`circ_mv`) stay `None`. |
| **Manager-side quote enrichment (centralized staleness)** | `data_provider/base.py` → `_enrich_realtime_quote` (L1470-1501), `_parse_realtime_timestamp` (L1436) | The **orchestrator** (not each fetcher) stamps `fetched_at`, computes `stale_seconds`, sets `is_stale = stale_seconds > ttl` (default 600s). Adapters stay "dumb" (raw → quote); the one tricky bit (tz-aware staleness) lives in one place — exactly ArkScope's sidecar contract. **Lesson to copy, not bug to inherit:** Finnhub's `t` epoch is dropped (`finnhub_fetcher.py` L132-147) so its quotes get `is_stale=None`. **Wire each adapter's native timestamp through** (Finnhub `t`, IBKR tick time, Polygon `t`). |
| **Circuit breaker (per-source failure cooldown)** | `data_provider/realtime_types.py` → `CircuitBreaker` (L279-433) + getters (L437-458) | Thread-safe CLOSED→OPEN→HALF_OPEN keyed by source: N failures (default 3) trip a cooldown (default 300s), one half-open probe decides recovery; `record_inconclusive` handles "returned None but didn't error." Stops ArkScope hammering a rate-limited/down provider (Finnhub 429s, IBKR Gateway drop). Run **separate tuned instances per workload** (realtime vs fundamentals). |
| **Provider-health telemetry: per-trace run records (fail-open)** | `src/services/run_diagnostics.py` → `ProviderRun` (L90-126), `RunDiagnosticContext` (L264-300, contextvar-scoped), `record_provider_run()` (L347), `sanitize_diagnostic_text` (L73-87) | Structured record of every provider attempt: provider/operation/success/latency_ms/error_type/fallback_from/fallback_to/cache_hit/stale_seconds/record_count. **Fail-open + contextvar-scoped** (no-ops when no context) → never breaks a request. This is the queryable history behind the §8 ops view; `card_runs`-style table is a natural sink. Built-in secret-redaction is a bonus given local credential storage. |
| **Duck-typed availability probe + capability filtering** | `data_provider/base.py` → `_is_fetcher_available`/`_call_availability_probe` (L646-673), `_filter_fetchers_by_capability` (L718-741), priority registry in `__init__.py` | Manager asks each provider in order `is_available_for_request(capability)` → `is_available()` → `_is_available()`, defaulting to available. With integer `priority` + per-capability pre-filtering, this is the clean **"IBKR if Gateway up → Polygon → Finnhub"** fallback model. **Lift the pattern, not the 133KB `base.py`.** |

### SKIP (A-share / CN-only, not US-relevant)
- All CN/HK fetchers: `efinance_fetcher.py`, `akshare_fetcher.py` (+ `is_hk_stock_code`), `tushare_fetcher.py`, `pytdx_fetcher.py`, `baostock_fetcher.py`, `longbridge_fetcher.py`.
- `prefetch_realtime_quotes` bulk-pull (`base.py` L1350-1429) — exists only for CN "全量" whole-market endpoints; irrelevant to US per-symbol APIs.
- `ChipDistribution` + `_chip_circuit_breaker` (`realtime_types.py` L190-276) — 筹码分布 is a CN-retail concept with no clean US source. (Keep only the *idea* of a second tuned breaker for a flakier endpoint.)
- `us_index_mapping.py` + market-routing branches (`_is_us_market`/`_is_hk_market`, `_filter_daily_fetchers_for_market`) — multi-market dispatch is dead weight; keep a flat US chain.
- CN exchange-prefix parsers `normalize_stock_code`/`is_bse_code`/`is_st_stock`/`canonical_stock_code` (`base.py` L68-271).
- `alphavantage_fetcher.py` — borderline (US-capable, last-resort supplement). SKIP unless a 4th free fallback is specifically wanted.

**Files to read when implementing:** `data_provider/realtime_types.py` (entire, ~460 lines, self-contained); `data_provider/base.py` L1456-1501 + L646-741 + L1503-1655 (fallback loop reference); `src/services/run_diagnostics.py` L90-300; clean US adapter reference `data_provider/finnhub_fetcher.py` L27-147.

---

## 10. Decisions on the open forks (2026-06-07)

**LOCKED (user):**
- **Q6 — LLM scoring decoupling: `--scores` is a FULLY separate opt-in step.** Not tied to `--news`/`--sync-db` at all. (Slice 2.)
- **Q7 — `--tier all` replacement: explicit scope, read-only.** The IBKR price scope is sourced from the SQLite active universe **only via an explicit `--scope active-universe`** flag (read-only: it READS `profile_state.db`, never writes config). The CLI also supports `--tickers`. **`--all` must NOT implicitly guess a scope**, and nothing here may write back to `user_profile.yaml`/`tickers_core.json`. (Slice 2.)

**RECOMMENDED defaults (gpt-5.5; lock before the dependent slice):**
- **Q1 — Realtime stream: DEFER.** v1 uses snapshot/poll (`get_current_quote`) with an explicit `is_stale` indicator; build `reqRealTimeBars` only after the chart shell is stable. (Slice 4.)
- **Q2 — `market_data` engine: SQLite-first acceptable for the low-risk first cut; DuckDB is the long-term target** for market/time-series OLAP. (Slice 3.)
- **Q3 — app records (`agent_queries`/`agent_memories`/`research_reports`/`job_runs`): STAY in PG / current** — do NOT migrate them in the same slice as market_data. (Phase 3, later.)
- **Q4 — Daily-history backfill depth: ≥ 5 years of adjusted `1d`, ACTIVE universe only** (not whole-market). (Slice 4.)
- **Q5 — Intraday retention: 1m ~30–60d, 5m ~6–12m, 15m ~1–2y.** (Slice 4.)

---

## 11. Implementation slices

| Slice | Scope | Depends on |
|---|---|---|
| **Slice 1 (this slice)** | This decision doc + the docs inventory it sits beside. Establishes the three modes, the DB split target, and the daily_update repositioning as the shared plan of record. No code change. | — |
| **Slice 2 — `daily_update.py` cleanup** ✅ DONE (`a765c85`+`c70b83d`) | Removed the three old-model couplings: `sync_watchlist_tickers` writeback (a); `--tier all` → explicit `--tickers` / `--scope active-universe` (physically read-only `mode=ro` read of `profile_state.db`, no config writeback) (b); `--scores` is a fully separate opt-in (c). Polygon/Finnhub/IBKR-news collectors unchanged. `--all` excludes IV + never guesses a price scope; dry-run never touches DB/IBKR. | Slice 1; **Q6/Q7 LOCKED ✓** |
| **Slice 3a — market_data local-first (NO SA)** | Add the **domain-routing** DAL (§3d) + `SqliteBackend`; migrate Phase 1 (`market_data` — regenerable) to `market_data.db` (SQLite, WAL) with row-count + checksum validation; keep PG fallback. **SA stays on PG; app records stay on PG.** Weekday-safe (no extension impact). **▸ PRICES landed `e95ebef`** (CompositeBackend + SqliteBackend + opt-in `ARKSCOPE_USE_LOCAL_MARKET`; 2.25M rows migrated + parity-verified). **Remaining 3a tables** (next cut): `news`/`news_scores`/`news_search`, `iv_history`, `fundamentals`, `financial_cache` → extend SqliteBackend + `_MARKET`-route them in CompositeBackend + add to the migration script. | Slice 2; Q2/Q3 |
| **Slice 3b — SA capture cutover** | Move `sa_*` PG → `sa_capture.db`. **Requires a quiet window (§5g): target Saturday US-closed (2026-06-13).** Dry-run on a DB copy first; port partial-index `ON CONFLICT` upserts; verify row-count + checksum + an extension→native-host smoke before flipping the SA domain route. | Slice 3a; §5g |
| **Slice 4 — Charting + price tiers** | Widen interval enum (`1m`/`5m`/native `1d`); persist adjusted `1d` (`adj_close`); reusable `date_trunc` rollup; deterministic-indicator module in the sidecar; (optional) Tier 0 realtime stream. | Slice 3a; Q1/Q4/Q5 |
| **Slice 5 — Provider health + signals surface** | Borrow the DSA quote dataclass / enrichment / circuit breaker / `ProviderRun` telemetry / capability filtering (§9); wire the §8 ops health view; integrate with the multi-factor signals subsystem (kept-but-adapt). | Slice 3a; §9 |

---

*End of plan. On any architecture conflict, `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` wins; per-provider facts defer to `ARKSCOPE_PROVIDER_CATALOG.md`; tool facts defer to `ARKSCOPE_TOOL_CATALOG.md`.*