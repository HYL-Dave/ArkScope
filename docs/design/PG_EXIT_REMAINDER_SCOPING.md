# PG-Exit Remainder Scoping (design skeleton v0)

- **Date:** 2026-07-01
- **Status:** DRAFT / survey v5 — local/runtime audit + S-C IV provider survey + S-H orphan/app-state audit folded; S-A1/S-B/S-G/S-H1/S-H2/S-J Phase 0-1 implemented; still not an implementation plan
- **Context:** news-domain PG exit is LIVE-complete (`news_pg_exit_runs` id=1 completed, fail-closed). **Overall ArkScope PG exit is NOT complete.**
- **Purpose of this doc:** scope the *remainder* of the PG exit — enumerate residual PG domains, assign a destination strategy per domain, define the `scripts/` retirement rule with a runtime-coupling inventory as its gating input, produce the N9 drop list, and sequence the remaining slices. **This document implements nothing.**

Companion docs: `docs/design/PG_EXIT_COMPLETION_PLAN.md`, `docs/design/NEWS_DIRECT_LOCAL_PLAN.md`.

---

## 1. Goals & non-goals

**Goals**
- Enumerate every residual PG domain and assign a destination strategy.
- Define the `scripts/` retirement rule, gated on the current runtime→`scripts/` coupling inventory (§4).
- Produce the N9 real drop list.
- Sequence the remaining slices with dependencies.

**Non-goals**
- No IV collector implementation, no prices migration, no code committed from this doc.
- No paid-provider selection (that is the survey slice, §6 S-C).

---

## 2. Classification framework (two cuts)

- **Cut A — domain nature:** `market-data` (prices / iv / fundamentals / news_scores / macro / cal) vs `app-state` (agent_queries / research_reports / agent_memories / job_runs / signals). **Destinations differ:** market-data follows Cut B; app-state → a local state store or retirement, **never into `market_data.db`**.
- **Cut B — market-data strategy:** `re-fetchable? × volume × in-use?` →
  - not re-fetchable + large + core → **migrate**
  - re-fetchable + small / on-demand → **refetch/cache**
  - already localised / no longer read → **drop-orphan**
  - not re-fetchable but abandoned → **drop + forward-only rebuild**

---

## 3. PG domain inventory + destination

`reltuples` estimates from `pg_class` (2026-07-01). `?` = to be confirmed in the audit slice.

| PG table | ~rows | Cut A | Strategy | Notes |
|---|---|---|---|---|
| `prices` | 2.31M | market | **reconcile + direct-local cutover**（2026-07-03 改判,原 migrate） | LIVE MEASURED: local 2,324,172/149 tickers > PG 2,314,293/150（疑 LC→HAPN stitch）→ audit-first,無證明缺口不 bulk copy;主體=ingest 直寫本地+mirror 退役;PG drop=batch-3 |
| `news_scores` | 503k | market | **local cutover; PG archived/dropped in N9 batch-1** | S-G live-applied 2026-07-03 into local `news_article_scores` (491,808 rows; reviewed fingerprint `34607859293ae7ee20726448e1b733fe55b2cf9fc720a31f6c97a853dec76ab3`; PG rows skipped: 604 N7-rejected legacy rows + 14 missing legacy IDs); future active imports use `scripts/scoring/import_news_scores_local.py`; PG source rows are retained only in the batch-1 archive |
| `news` (PG) | 343k | market | **local cutover; PG archived/dropped in N9 batch-1** | app reads normalized local news post-N8a; PG source rows are retained only in the batch-1 archive |
| `sa_*` (comments/signals/market_news/articles/alpha_picks) | ~95k | market | **local authority; PG archived/dropped in N9 batch-1** | S-H confirmed active SA authority is local `sa_capture.db`; the old PG rollback-basis rule was replaced by the batch-1 archive |
| `fundamentals` | 130 | market | **refetch/cache; PG archived/dropped in N9 batch-1** | EDGAR base + paid supplement; period-aware TTL; PG snapshot rows were intentionally not promoted |
| `iv_history` | ~24 | market | **drop + forward reboot; PG archived/dropped in N9 batch-1** | abandon old data; rebuild capability; the old scheduler `iv_history` PG-mirror source is now fail-closed with an N9 retirement error, not a provider fetch |
| `macro_*` / `cal_*` | 0 | market | **empty-table proof folded into N9** | local `macro_calendar.db` is active under `use_local_macro=true`; reviewer verified PG macro/cal tables are empty, so N9 batch-1 needs grep + empty-table proof rather than a separate seed/refetch slice |
| `financial_data_cache` | 24 | market (cache) | **cold-start done; PG archived/dropped in N9 batch-1** | S-H2 removed the desktop runtime PG read-through/promotion path; local miss is an honest miss and callers refetch SEC/FD into local cache. PG table had only 24 rows / 7 unexpired / 0 paid FD rows and is retained only in the batch-1 archive |
| `job_runs` | 13k | app-state | **relocated; PG archive dropped in N9 batch-2** | S-H1 live-applied 2026-07-03 into local `profile_state.db` (`job_runs=13,652`, reviewed fingerprint `38cf152141aae4304344baeeb46c6476f9870ff0f86fb793469bed96b0cad447`, backup `data/profile_state.db.bak-pre-s-h1-job-runs-20260703T021241462312Z.db`); N9 batch-2 live drop 2026-07-05 removed PG `job_runs` after archive `data/pg_archive/n9_batch2_20260704T162352Z/`; local `scheduler_state` remains partial continuity state, not full history |
| `agent_queries` / `research_reports` / `agent_memories` / `signals` | ? | app-state | **mostly local/retire** | app-records are already in `profile_state.db`; legacy PG `signals` has no runtime SQL reader found in S-H |

---

## 4. `scripts/ → src/` runtime coupling inventory (gating input for retirement)

> Hard fact: **`scripts/` IS the current ingest runtime.** Retirement = extracting these into `src/` one domain at a time, not a cleanup pass.

### A. In-process imports (runtime imports `scripts/` directly)

| Caller | `scripts/` target | Domain |
|---|---|---|
| `src/news_providers.py:132/136` | `collect_polygon_news` / `collect_finnhub_news` | news |
| `src/service/data_scheduler.py:115/122/272/284` | `collect_polygon_news` / `collect_finnhub_news` (`run_incremental`) | news |

### B. Subprocess launches (`_COLLECT_DIR = scripts/collection`)

| Location | Target | Domain | State |
|---|---|---|---|
| `data_scheduler.py:827` | `python -m src.news_normalized.ibkr_cli` | news | **converted in S-A1**; old script retained as compatibility wrapper |
| `data_scheduler.py:128` → 938 | `collect_ibkr_news.py` | news | **likely dead** (post-exit routing never selects legacy) → confirm, then retire |
| `data_scheduler.py:135` → 938 | `collect_ibkr_prices.py` | prices | active |
| `data_scheduler.py:141` → 938 | `collect_iv_history.py` | iv | retired by N9 offline hardening; `run_source("iv_history")` fails before provider work/PG sync and points to the separate IV reboot path |
| `data_scheduler.py:958` | `migrate_to_supabase.py <sync_flag>` (`_MIGRATE`) | PG sync | retires per-domain as each leaves PG; fully gone at N9 |

### C. Parallel CLI path

`scripts/collection/daily_update.py` shares `run_source` with the scheduler; `job_runs` uses `daily_update.*` step aliases. → collapse into a thin `src/` entrypoint or retire.

### D. Docstring mentions only (not couplings; low priority)

`market_data_admin.py:22` (migrate_market_to_sqlite), `db_config.py:5` (migrate_to_supabase), `auth_drivers/chatgpt_oauth_probe.py:5`, `agents/shared/replay.py:4` (replay_run.py = companion CLI). → wording/classification only, non-blocking.

---

## 5. `scripts/` retirement rule (principle)

- **Provider clients stay in `data_sources/` unless deliberately migrated.** That is the existing
  provider layer (`data_sources/ibkr_source.py`, `sec_edgar_financials.py`,
  `financial_datasets_client.py`, `polygon_source.py`, ...). Runtime orchestration / domain logic
  moves into `src/<domain>/...` modules (`src/news_normalized/`, `src/iv/`,
  `src/fundamentals/`, ...). Do **not** accidentally create a second provider layer under
  `src/providers/`.
- **Runtime imports `src/` only.** Subprocess isolation may stay, but its **target becomes `python -m src.<module>`, never `scripts/*.py`**.
- **Retirement = definition-of-done of each domain's cutover**, riding along that domain's migration. **Not** a standalone mega-refactor (avoid stalling PG-exit momentum).
- **First conversion candidate = the N8a IBKR news worker:** `scripts/collection/collect_ibkr_news_normalized.py`
  is **not** a trivial shell. `src/news_normalized/ibkr_runtime.py` holds the Gateway adapter, but
  the script still owns worker orchestration, DB/write locking, provider config injection,
  `stderr` suppression, sanitized stdout JSON, sanitized error classes, and continuation-count
  redaction. S-A1 must move this whole worker boundary into `src/news_normalized/ibkr_cli.py` and
  repoint the scheduler to `python -m src.news_normalized.ibkr_cli` while preserving the
  sanitization contract.

---

## 6. Slice breakdown (each own spec/plan/gate, TDD)

1. **S-A | scripts/ retirement rule + coupling baseline** — §4/§5 landed as a contract; S-A1 converted the IBKR news worker runtime boundary to `python -m src.news_normalized.ibkr_cli`. Remaining S-A work applies the same definition-of-done per domain.
2. **S-B | fundamentals refetch/cache** — *fast win, may run first / in parallel with the survey.* Stop the PG mirror for the fundamentals domain, retire the frozen `fundamentals` table as an authority, make `stored=true` read only local positive SEC annual-analysis `financial_cache` rows (`fundamentals_analysis:sec_edgar:{TICKER}:annual:v1`) and otherwise return honest empty, keep default analysis on SEC EDGAR / Financial Datasets fallback, reuse the existing TTL semantics, **check for non-US tickers** (EDGAR is US-only). Extract `src/fundamentals/`.
3. **S-C | IV provider survey** (decision axes in §7) — **completed**; output is a narrowed proof-packet plan, not a provider selection.
4. **S-D | IV local schema reboot** (contract in §7): raw-retain + versioned-derive schema, provider-abstraction interface; no scheduling yet.
5. **S-E | IV IBKR small-scope computed-IV prototype** (10–30 tickers, near-month/ATM, fixed DTE-or-delta bucket, append-only, no gap-fill). Extract `src/iv/`.
6. **S-F | (optional) IV bulk provider backend** — only if the survey finds a fit; plugs into the same schema.
7. **S-G | scorer (news_scores) cutover** — **implemented and live-applied 2026-07-03**. Local `news_article_scores` now carries the reviewed PG score history, score-dependent local reads use SQLite-local scores, future active score imports use `scripts/scoring/import_news_scores_local.py`, and PG `--scores` is archive-only. Proof: fingerprint `34607859293ae7ee20726448e1b733fe55b2cf9fc720a31f6c97a853dec76ab3`, `pg_score_rows=503,226`, `inserted_or_updated=491,808`, `rejected_rows=604`, `missing_legacy_rows=14`, idempotent reapply `inserted_or_updated=0`.
8. **S-H | orphan/audit + app-state relocation** — **audit complete 2026-07-03** (`PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md`). Findings: PG `news`/`news_scores`/`fundamentals`/`iv_history`, `financial_data_cache`, and likely `sa_*` were N9 candidates after final grep/dump; app-records are local; macro/cal proof was folded into the N9 batch-1 evidence plan. **S-H1 job-runs local cutover live-applied 2026-07-03** from `PG_EXIT_S_H1_JOB_RUNS_LOCAL_PLAN.md`: fingerprint `38cf152141aae4304344baeeb46c6476f9870ff0f86fb793469bed96b0cad447`, `pg_rows=13,652`, local `job_runs=13,652`, idempotent reapply `already_applied=true`, `use_local_job_runs=true`, backup `data/profile_state.db.bak-pre-s-h1-job-runs-20260703T021241462312Z.db`. **S-H2 financial-cache cold-start implemented 2026-07-03**: `LocalMarketDatabaseBackend.get_financial_cache()` is local-only; no PG fallback/promotion remains. **N9 batch-2 live drop completed 2026-07-05**: PG `job_runs` and orphan `news_search_vector_update()` are gone after archive/restore proof; local-default routing collapse is live.
9. **S-I | N9 real drop** (§8).
10. **S-J | provider-config authority hardening (DB-first, fail-closed)** — orthogonal to the domain slices (provider *config*, not market data). Kill the two silent `config/.env` fallbacks (per-field overlay + whole-store startup degrade), surface per-field provenance with an explicit import affordance, then flip strict-by-default behind a tri-state. Contract in §13. **Phase 0–1 must land before S-E** so new IV provider keys are DB-native from day one.

---

## 7. IV reboot design contract (core of S-C/S-D)

- **Two layers:**
  - `iv raw/snapshot layer`: input-complete enough to **recompute** — quotes, greeks, open interest, **`snapshot_at` (fixed time-of-day)**, underlying price, rate/dividend assumptions, strike/DTE selection rule, `num_quotes`, spread, confidence, provider, method.
  - `iv research-metric layer`: ArkScope-computed (ATM IV / term structure / VRP / event IV), **method-versioned (`iv_method_version`)**, a deterministic function of the raw layer; improving the method **recomputes from stored raw, no re-fetch** (same pattern as news `cleaner_version`).
- **Build/buy line (driven by the "own the computation" value):**
  - **Buy RAW bulk** (Polygon-style chain/greeks/quotes/OI + historical) → feed your own compute; solves the IBKR rate-limit; does not compromise research autonomy.
  - **Pre-derived (ORATS surface / ex-earnings vol)** = reference only, or for metrics you won't build — not the backbone.
  - **Cross-check precondition:** comparing your IV vs a provider's is only meaningful when **inputs are comparable** (same time, quotes, assumptions); otherwise treat as two independent series, not validation.
- **Constraints:** no interpolation (a gap is a gap, marked explicitly); the series is **sparse/irregular**, so the research layer must not assume daily continuity; per-ticker failures must be attributable (attempted-no-data vs not-attempted, reusing the news honest-status discipline).
- **Monitoring (make-or-break for the reboot):** scheduling must be monitored — a missed day must alert. The old collector **died silently in March and went unnoticed for ~4 months**; a forward-only series is only as good as collector uptime.

---

## 8. N9 real drop list — **BATCH-1 + BATCH-2 LIVE-EXECUTED**

Authoritative batch-1 evidence/drop plan: `docs/design/PG_EXIT_N9_BATCH1_DROP_PLAN.md`.

**Batch-1 live record (2026-07-03):**

- Approved evidence fingerprint `fd995f7092ad9535499294506ec328836a44fe71e1370f2746fcef211bd14d21` (third approval package; two earlier packages were invalidated by the fingerprint's own repo-grep gate after reviewed tooling fixes — correct gate behavior, and the drop's first attempt was correctly rolled back by a rowtype dependency).
- Archive `data/pg_archive/n9_batch1_20260703T045919/` — dump sha256 `eb9fd854…`, `required_extensions=[pg_trgm, vector]`, two-phase DDL sidecars (trigger fns pre-restore / target fns post-restore), **restore proof ok:true against a disposable DB** (row fingerprints matched).
- Dropped in ONE transaction (4 statements, no CASCADE): 21 tables (`news` 371,672 / `news_scores` 503,226 / `fundamentals` 130 / `iv_history` 24 / `financial_data_cache` 24 / `signals` 0 / 6×`sa_*` / 9× empty `macro_*`+`cal_*`), view `news_latest_scores`, functions `news_sentiment_summary(...)` + `get_recent_news(...)` (dead day-one helper; its `news` rowtype dependency blocked drop attempt #1 → txn rollback → target amended + dependency scan widened to `pg_type` edges).
- `postcheck` ok (targets incl. functions absent; excluded present). App smoke pass: NVDA scored-news read (`days=9999`) returned 8,869 rows, exactly matching the S-G post-apply baseline (no score loss); FTS/stats/prices/IV/SA/macro/job_runs local reads all healthy.
- **After batch-1 remaining PG objects were `prices` (2,314,293, archive/rollback only after P0-C; batch-3 drop) + `job_runs` (13,652, frozen archive until batch-2) + app-record tables.**
- **Invalidated rollback levers** (per the plan's Post-Drop Rollback Semantics): toggle-off-to-PG is dead for all dropped domains; recovery = restore the archive first.
- Gate lessons banked: preflight the client toolchain (`pg_dump`/`pg_restore` ≥ server major; a real `ripgrep` binary — shell aliases don't reach subprocesses); repo freeze between evidence and drop (the fingerprint includes the repo grep); psql DDL applies always run with `ON_ERROR_STOP=1`.

**Batch-2 live record (2026-07-05 Asia/Taipei / 2026-07-04 UTC):**

- Approved evidence fingerprint `1bd083754c2e3c56fe93ea57c1b540c7c4c980117d737361509b451cc1963478`.
- Archive `data/pg_archive/n9_batch2_20260704T162352Z/` — dump sha256 `dba8eb51bb3249f88d299047b30492867b11bdb531bfbb6d4d2a812e926ef71c`, restore proof `ok:true`, `mismatches:[]`.
- Dropped in one transaction, no CASCADE: table `job_runs` (13,652) + function `news_search_vector_update()`.
- Postcheck ok: targets absent, `prices` and app-record archive tables still present. Post-drop poison smoke: `186 passed`.
- Two CLI lessons banked for batch-3: direct script entrypoints must be tested through real `sys.argv`, and read-only evidence prechecks must use a separate connection from the destructive transaction.
- verified-dead PG score helper: `src/tools/backends/db_backend.py::query_news_scores` + other dropped-domain `DatabaseBackend` methods are retired stubs.
- `migrate_to_supabase.py` retired-domain code is fail-closed, including `--prices` after P0-C.
- **Retain:** `prices` (P0-C reconcile + direct-local cutover live-complete; PG table is archive/rollback only. Physical drop is batch-3 with a fresh N9-style dump/restore/drop approval packet).

**Batch-3 queue:**

- PG `prices` destructive drop after P0-C has soaked. Requires a fresh targeted dump, restore proof,
  explicit approval, and conscious removal of `prices` from the N9 excluded-table protection.

---

## 9. Sequencing & dependencies

- **Parallel / can-go-first:** S-A (demonstrator conversion), S-B (fundamentals fast win), S-C (survey).
- **Dependency chain:** S-C → S-D → S-E → (optional) S-F → wire scheduler/UI/tool.
- **Independent:** S-H audit is complete; S-H1 job-runs local cutover is live; S-H2 financial-cache cold-start is implemented; remaining macro/cal proof was folded into N9 batch-1. S-J provider-config Phase 0–1 is complete and Phase 2 can be scheduled when convenient. S-G scorer cutover is complete. N9 batch-1 and batch-2 live drops are complete. P0-C prices direct-local cutover is complete; batch-3 is the future physical PG `prices` drop.
- **Endgame:** S-I (N9), after each domain is localised and confirmed reader-free.

---

## 10. Open questions / decisions needed

1. **IV forward strategy:** historical options backfill now looks plausible in principle, but only the proof packet can decide if it is usable. It must verify historical IV/greeks completeness/reliability, provider rate limits, tier/pricing gates, and timestamp/input comparability before switching from forward-only to "one-time backfill + forward".
2. **app-state homes:** resolved for `agent_queries` / `research_reports` / `agent_memories` and `job_runs` (local `profile_state.db`) and legacy `signals` (retire if present). `job_runs` may still move to a future `ops.db` only if real write contention or telemetry volume justifies that separate store.
3. **macro/cal:** resolved for sequencing 2026-07-03 — PG macro/cal tables were verified empty, so S-H3 is folded into N9 batch-1 evidence as grep + empty-table proof, not a separate implementation slice.
4. **scorer timing:** resolved 2026-07-03 — S-G cut over `news_scores` before N8b reads, so hard-local score degradation is removed before the normalized-read upgrade.
5. **prices:** resolved 2026-07-03 — audit-first reconcile + direct-local cutover; no bulk copy unless unexplained PG-only rows prove a real local gap; PG drop is batch-3.
6. **legacy `collect_ibkr_news.py`:** confirm it is dead post-exit → can it be retired directly?

---

## 11. Per-slice generic gate (reuse proven discipline)

- For slices that touch the live DB: preview (`mode=ro`) → fingerprint → backup (`O_EXCL`) → single txn → validate → rollback-able → reopen-RO verify; no `--force`.
- Before any retirement / drop: grep-confirm no runtime/script reader remains.
- Each slice: TDD + green offline gate + independent review (plus an independent re-check when touching the live DB).

---

## 12. Survey v1 evidence (2026-07-01)

This section records the first concrete survey pass. It is intentionally scoped to
evidence and ordering; it does not authorize any live schema change or code cutover.

### 12.1 Local stores already present

Read-only SQLite checks (`PRAGMA quick_check`) all passed:

| Local DB | Relevant tables / counts | Survey conclusion |
|---|---:|---|
| `data/market_data.db` | `prices=2,324,172`, `news_articles=292,461`, `news_article_scores=491,808`, `financial_cache=20`, `iv_history=24`, `fundamentals=130` | S-G scores are local; P0-C proved local prices authority and cut scheduled writes local; IV/fundamentals local rows are tiny legacy snapshots |
| `data/sa_capture.db` | `sa_alpha_picks=112`, `sa_articles=395`, `sa_article_comments=41,215`, `sa_market_news=22,086`, `sa_comment_signals=39,853`, `sa_market_news_tickers=21,689` | SA data is local and active; PG `sa_*` was archived/dropped in N9 batch-1 after the reader/script grep |
| `data/profile_state.db` | `agent_queries=2`, `research_reports=2`, `agent_memories=1`, `scheduler_state=5`, `profile_settings=15` | app-records already have a local app-state home; future app-state should not go into `market_data.db` |
| `data/macro_calendar.db` | `macro_series=11`, `macro_observations=29,571`, `macro_release_dates=4,659`, `cal_ipo_events=86`, `cal_economic_events=0`, `cal_earnings_events=0` | macro/FRED and IPO events are local; economic/earnings event emptiness must be decided before PG drop |

### 12.2 Runtime couplings that are still real

The `scripts/` retirement rule in §5 is not optional hygiene. Current runtime still
uses `scripts/` in these ways:

- Polygon/Finnhub news: `src/news_providers.py` and `src/service/data_scheduler.py`
  still lazily import `scripts.collection.collect_polygon_news` and
  `scripts.collection.collect_finnhub_news`.
- IBKR news: S-A1 moved the normalized worker boundary into
  `src/news_normalized/ibkr_cli.py` and scheduler now launches it with
  `python -m src.news_normalized.ibkr_cli`; the old
  `scripts/collection/collect_ibkr_news_normalized.py` file is only a compatibility
  wrapper until N9/scripts cleanup.
- IBKR prices and IV: scheduler subprocesses still target
  `scripts/collection/collect_ibkr_prices.py` and `scripts/collection/collect_iv_history.py`.
- PG sync: `scripts/migrate_to_supabase.py` remains the domain sync target for
  unfinished domains (`--prices`, `--iv`, and `--fundamentals`); `--scores`
  is retained only as an explicit archive path and requires `--archive-scores`.
- `scripts/collection/daily_update.py` remains a parallel CLI runtime path and writes
  `daily_update.*` job aliases that scheduler state still recognizes.

Therefore "scripts retirement" must be a per-domain definition-of-done:

1. extract runtime logic into a `src/<domain>/...` module,
2. keep subprocess isolation where it is technically valuable,
3. launch subprocesses with `python -m src.<domain>.<entrypoint>`, and
4. leave `scripts/` only for one-shot migration/backfill tools until they are retired.

### 12.3 Domain disposition after survey

| Domain | Current survey finding | Disposition |
|---|---|---|
| News | hard-local reads and normalized local writes are live; PG news is no longer the app authority | PG `news` was archived/dropped in N9 batch-1; keep legacy local projection until N8b/N9 |
| News scores | Local `news_article_scores` is live and bridges legacy rows through the normalized news maps. Active local score imports use `scripts/scoring/import_news_scores_local.py`; PG score table is gone | S-G removed the hard-local score degradation for migrated/imported scores. Live proof: reviewed fingerprint `34607859293ae7ee20726448e1b733fe55b2cf9fc720a31f6c97a853dec76ab3`, `pg_score_rows=503,226`, `inserted_or_updated=491,808`, `rejected_rows=604`, `missing_legacy_rows=14`, idempotent reapply `inserted_or_updated=0`; PG `news_scores` was archived/dropped in N9 batch-1 |
| SA | local `sa_capture.db` is populated and SA tools prefer hard-local backend; job telemetry now comes from local `job_runs` | PG `sa_*` was archived/dropped in N9 batch-1; job telemetry belongs to app-state/ops, not SA market data |
| Fundamentals | S-B retires the frozen `fundamentals` mirror table as an authority; `stored=true` reads only local positive SEC annual-analysis `financial_cache` rows (`fundamentals_analysis:sec_edgar:{TICKER}:annual:v1`) and otherwise returns honest empty; live cache may initially be cold; default analysis remains SEC EDGAR / Financial Datasets refetch with local cache | PG-free after S-B; old `fundamentals` table was archived/dropped in N9 batch-1 |
| IV | only 24 local rows; old scheduler `iv_history` PG-mirror source is fail-closed after N9 offline hardening; tools/UI read local and local misses are honest-empty | old PG `iv_history` was archived/dropped in N9 batch-1; preserve capability via rebooted local schema + provider abstraction |
| Prices | local table has 2.3M rows and price data is core | P0-C reconcile + direct-local cutover is live-complete: final fingerprint `61bbf613…`, local rows `2,324,487`, PG-only unexplained `0`, no bulk copy, scheduled `ibkr_prices` direct-local, price reads local-only. PG `prices` is archive/rollback only until batch-3 |
| Macro/cal | local macro/calendar store selects `macro_calendar.db`; local macro/FRED and IPO rows exist, but economic/earnings event tables are empty | PG macro/cal tables were verified empty and archived/dropped in N9 batch-1, with no seed/refetch slice |
| Financial cache | S-H2 made `LocalMarketDatabaseBackend.get_financial_cache()` local-only. Local miss is an honest miss; callers refetch SEC/FD and repopulate local cache | PG `financial_data_cache` was archived/dropped in N9 batch-1 |
| App state / ops | profile app-records are local and `use_local_records=true`; `job_runs` is local in `profile_state.db`; unset/false legacy job-runs flags no longer route to PG | PG `job_runs` was archived/dropped in N9 batch-2. PG app-record tables remain archive-only and need a separate decision before physical drop |

### 12.4 Fundamentals survey

The fundamentals direction is unchanged: refetch/cache, not PG migration.

- SEC EDGAR is the primary free source for US public-company filings and extracted
  XBRL; the SEC's developer guidance explicitly exposes data APIs and requires fair
  access discipline, currently no more than 10 requests per second across machines.
- Existing code already caches SEC-derived fundamentals into `financial_cache`, and
  negative SEC misses are short-cached to avoid hammering uncovered tickers.
- EODHD is a reasonable paid/global supplement candidate: its docs cover fundamentals
  for stocks/ETFs/funds/indices across US and non-US exchanges, with broad historical
  coverage and versioned fundamentals endpoint guidance.

Slice implication: fundamentals should be a small PG-exit slice, not an N7-style
migration. Required gates:

1. set stored-only fundamentals reads to local `financial_cache` only (no PG fallback, no provider fetch),
2. preserve default `get_fundamentals_analysis` provider fallback,
3. keep/verify SEC User-Agent + backoff/rate limit,
4. scan active universe for non-US / EDGAR-uncovered symbols,
5. optionally pre-warm active-universe fundamentals into local `financial_cache`, and
6. retire `migrate_to_supabase --fundamentals` only after the local-only smoke passes.

### 12.5 IV provider survey

**Status:** S-C survey completed 2026-07-02. The outcome is not a provider
selection yet; it is a narrowed proof-packet plan. The IV decision is not
"keep old rows vs drop old rows"; the old rows are too small and stale to
matter. The real decision is how to build a forward research-grade IV dataset
without making IBKR rate limits the backbone.

| Provider | Official evidence verified 2026-07-02 | Fit for ArkScope | S-C decision |
|---|---|---|---|
| IBKR TWS/Gateway | Legacy IBKR docs state that `reqContractDetails` can enumerate chains but is throttled and not recommended for all strikes/rights/expiries; `reqSecDefOptParams` returns expirations/strikes, not market quotes. Greeks/IV arrive through option market-data ticks and require the relevant option + underlying market data subscriptions. Source: `interactivebrokers.github.io/tws-api/options.html`, `option_computations.html`. | Good for a small-scope computed-IV prototype and live cross-checks. Poor as the 148-ticker daily backbone. | Keep as S-E prototype backend only: 10-30 tickers, near-ATM/near-term scope, fixed snapshot time, explicit no-data/error status. |
| Massive / Polygon Options | Current docs redirect Polygon options docs to Massive. Option Chain Snapshot returns pricing details, greeks, implied volatility, quotes/trades, open interest, and underlying data; it is delayed on Starter/Developer and real-time on Advanced, with no history on that endpoint. Historical options quotes provide bid/ask records with nanosecond timestamps, max limit 50k, history back to 2022-03-07, and Advanced-tier access. Sources: `massive.com/docs/rest/options/snapshots/option-chain-snapshot`, `massive.com/docs/rest/options/trades-quotes/quotes`. | Best raw/near-raw candidate for own-computation if the plan tier and history depth are acceptable. It is the only verified candidate here that clearly offers historical bid/ask quote records rather than only derived IV fields. | **Proof-packet candidate A.** Verify product naming/account migration (`Polygon` vs `Massive`), Advanced-tier access, 2022 history sufficiency, payload completeness, and whether chain snapshot + historical quote samples are enough for ArkScope-derived ATM IV / term buckets / VRP. |
| Alpha Vantage | Docs state realtime options return full chains and `require_greeks=true` enables greeks + IV; realtime options require the 600 or 1200 requests/min premium tiers. Historical options return full chains for a symbol/date, include IV + common greeks, accept dates later than 2008-01-01, and unlock under premium membership. Premium page lists 75-1200 requests/min tiers, with realtime options entitlement instructions. Sources: `alphavantage.co/documentation` Options Data APIs, `alphavantage.co/premium`. | Strong accessible historical backfill candidate, but not raw enough to be a pure own-computation backbone if only vendor IV/greeks are retained. Its value depends on whether bid/ask/last/OI fields are consistently populated and whether request limits make multi-ticker backfill tolerable. | **Proof-packet candidate B.** Test historical non-null coverage and rate-limit economics first. If fields are complete enough, use as the cheapest historical bootstrap; still compute ArkScope metrics from retained chain inputs where possible. |
| EODHD / Unicorn options | EODHD marketplace lists Unicorn Data Services' US Stock Options Data API: over 6,000 US stock symbols, two-plus years of history, daily EOD updates, over 1.5M bid/ask/trade events daily, bid/ask/OHLC/midpoint, volume/OI with day-over-day changes, all five greeks, implied volatility, DTE, 43 fields per trade, and January 2025 per-ticker + separate EOD bid/ask/trade endpoints. Source: `eodhd.com/marketplace/unicornbay/options`. | Credible cheap EOD-granularity chain-snapshot candidate that matches the fixed-time snapshot direction better than an intraday API would. It is less raw/timestamp-controllable than Massive historical quotes, and timestamp semantics (near-close vs vendor EOD aggregation), beta/product maturity, and tier gates must be verified. | **Proof-packet candidate C.** Test after A/B or alongside them if key access is easy. Do not select until timestamp semantics, endpoint shape, and historical non-null greeks/IV coverage are measured. |
| Tradier | Options chains endpoint is per underlying + expiration and includes greeks when requested; Tradier explicitly says Greek and IV data is courtesy of ORATS. Source: `docs.tradier.com/reference/brokerage-api-markets-get-options-chains`. | Useful broker-style live source and possible operational fallback. Not an independent ORATS cross-check and not a bulk historical backbone from the verified docs. | Do not use as backbone. Keep as optional live reference if account terms make it cheap. |
| ORATS | ORATS advertises live, delayed, historical EOD options data back to 2007, 5,000+ symbols, 500+ indicators, high-quality bid/ask quotes and greeks gathered near close, smoothed market values, IV rank/history, and intraday tiers. Sources: `orats.com/data-api`, `docs.orats.io`. | Excellent specialist/reference dataset and vendor-derived signal source. It conflicts with the "own the computation" backbone unless ArkScope explicitly chooses ORATS-derived surfaces as canonical. | Reference/enrichment only for now. Use to compare research outputs, not to validate raw-derived IV unless inputs/timestamps are comparable. |

Survey recommendation:

- **Backbone principle remains unchanged:** buy/access raw or near-raw chain/quote/OI
  snapshots and compute ArkScope metrics from retained inputs. Do not make
  pre-derived vendor surfaces canonical unless that is an explicit future product
  decision.
- **Run proof packet before S-D provider lock.** Test two candidates first:
  1. **Massive / Polygon** for raw quote-chain capability and forward snapshots.
  2. **Alpha Vantage** for historical backfill feasibility and cheap access.
  3. **EODHD / Unicorn** as the low-cost EOD-history fallback if A/B are too costly
     or incomplete.
- **IBKR role:** keep as bounded prototype/cross-check, not full-universe daily collector.
- **ORATS / Tradier role:** reference/enrichment only. Tradier greeks are ORATS-derived,
  so Tradier is not independent evidence against ORATS.
- **EODHD / Unicorn role:** candidate C, with timestamp semantics and beta/product
  maturity as the main proof-packet risks.

Proof-packet requirements:

- sample payloads for at least `SPY`, `AAPL`, `NVDA`, one event-heavy name, and one
  lower-liquidity optionable ticker;
- sample dates: latest session, 1 week back, 1 month back, 1 year back, and an old
  historical date (2017 if provider claims deep history);
- record non-null coverage for bid/ask/last/volume/OI/provider IV/provider greeks,
  quote timestamps, underlying price, and expiration/strike metadata;
- verify expiry enumeration completeness, especially weekly/0DTE vs monthly contracts,
  and compare any provider-supplied underlying price against the independent stock
  quote used for IV recomputation;
- quantify request math for `tickers × dates × expiries/contracts`, including the
  provider's actual request/minute or monthly cap and whether pagination multiplies
  cost;
- record timestamp semantics (EOD, near-close, delayed snapshot, realtime, SIP quote
  timestamp), because provider-to-provider IV comparison is invalid unless input time
  and assumptions are comparable;
- capture exact tier/pricing gates and account-entitlement requirements;
- decide whether historical backfill is viable; otherwise the reboot remains
  forward-only with visible gaps.

Recommendation after S-C:

- Proceed to **S-D schema design** with provider-neutral fields, not provider-specific
  tables.
- In parallel, run a small **proof-packet data collection** script/notebook outside the
  runtime path. It must be read-only with respect to ArkScope DBs and must not add new
  `.env` authority; any provider key selected for continued use goes straight into
  FieldDefs / DB-managed config per S-J. Plan: `docs/design/IV_PROVIDER_PROOF_PACKET_PLAN.md`.

### 12.6 IV reboot schema implications

The reboot schema should be designed before choosing the provider. It must support both
IBKR prototype and bulk provider backends:

- raw snapshot table: provider, snapshot_at, underlying price, contract identity, strike,
  expiry, call/put, bid/ask/last/mid, bid/ask sizes, volume, OI, quote/trade timestamps,
  provider greeks/IV if supplied, rate/dividend assumptions if available, raw payload
  hash/ref, and confidence inputs such as spread and `num_quotes`;
- derived metrics table: deterministic ArkScope outputs (`atm_iv`, term buckets, VRP,
  event-vol fields), `iv_method_version`, source snapshot id(s), selection rule, and
  confidence;
- status table: attempted/no-data/error/not-attempted per ticker/date/provider, so gaps
  are visible and never silently interpolated.

### 12.7 Immediate slice recommendation

Do not wait for the IV provider survey to do fundamentals. S-A1 is now complete and
serves as the scripts-retirement demonstrator.
Recommended next order:

1. **S-B fundamentals refetch/cache:** local-cache stored reads + provider fallback retained. **Status: implemented.**
2. **S-C IV provider survey:** **Status: completed.** Next proof packet should test
   Massive/Polygon and Alpha Vantage first, include EODHD/Unicorn as candidate C if
   key access is easy, keep IBKR as prototype/cross-check, and keep ORATS/Tradier as
   reference.
3. **S-D IV schema design:** provider-neutral schema and status model.
4. **S-E IV IBKR prototype:** small scope only (10-30 tickers), fixed snapshot time,
   no gap-fill, honest failures.

---

## 13. Provider-config authority hardening design contract (core of S-J) — decisions locked 2026-07-02

**Problem.** The desktop premise is DB-first, but provider config today is
"DB-overlays-.env". `apply_env` (`src/data_provider_config.py:162`) first loads
`config/.env` (`env_keys.ensure_env_loaded()`), then overwrites per-field with
app-stored values. Two silent-fallback modes result:

- **per-field:** a managed field with no DB row silently serves the `config/.env`
  value — no prompt, no provenance shown at the point of use;
- **whole-store:** sidecar startup wraps `apply_env` in try/except-warning
  (`src/api/app.py:43`) — an unreadable profile DB silently degrades the whole
  process tree to pure-.env mode.

Both violate the desktop model (DB required; missing config = visible
"not configured", never a silent substitute). The **real shell env > app**
precedence is a deliberate operator escape hatch and does **not** change.

**Why convergence is cheap.** `.env` ingestion has a single choke point
(`src/env_keys.py`: `ensure_env_loaded` / `keys_loaded_from_file` /
`reload_var_from_file`); per-var provenance already exists
(`effective_source()` → `app | env | config/.env | missing`); the sidecar is the
parent of every collector subprocess, so one injection covers the tree; the S-A1
worker already applies DB config explicitly
(`src/news_normalized/ibkr_cli.py:125`).

### 13.1 Consumer classes (hardening applies to the first class only)

| Class | Examples | Rule |
|---|---|---|
| sidecar process tree | FastAPI app, scheduler, collector subprocesses | DB-first, fail-closed; provider keys enter ONLY via `apply_env` |
| spawned workers (standalone-capable) | `python -m src.news_normalized.ibkr_cli` | must call `apply_env(DataProviderConfigStore())` at startup (S-A1 precedent) |
| CLI + `scripts/` (retiring) | `src/agents/cli.py::_load_env()`, `scripts/*` | no investment; legacy `.env` behavior until retirement |

**Out of scope:** LLM credentials (auth-driver/token-store thread — deliberately a
different design); `DATABASE_URL`/PG DSN (`src/tools/data_access.py:381` — it IS
the PG-exit retirement target; stays .env-transitional until PG-exit completes);
OS keyring (existing backlog item); unit tests (they keep fake backends —
fail-closed is a runtime policy, not a test-fixture requirement).

### 13.2 Phase 0 — audit (output = a classification table appended here)

Inventory every provider env var and classify:

- **managed** (already in FieldDefs): `POLYGON_API_KEY`, `FINNHUB_API_KEY`,
  `FRED_API_KEY`, `FINANCIAL_DATASETS_API_KEY`, `IBKR_HOST` / `IBKR_PORT` /
  `IBKR_CLIENT_ID`;
- **`legacy_env_only`** (known candidates: `SEC_CONTACT_EMAIL` /
  `ARKSCOPE_SEC_USER_AGENT` (UA contract — attach to the existing `sec_edgar`
  provider); alpha_vantage / tiingo / eodhd api_keys (live readers exist — this
  absorbs the old "Slice A optional" FieldDefs list, incl. its
  `_TESTABLE`/connection-test decision); Discord ops token; `REDDIT_*`/FMP have
  no live reader → defer/retire) → each is either promoted to FieldDefs or
  recorded as `legacy_env_only`-with-reason. Under strict these keep working
  with a rendered warning — never blocked; no runtime `getenv()` interception
  sweep;
- **retiring consumer** (CLI/scripts) → listed, not fixed.

Grep surface: `_load_env|load_dotenv|config/\.env|os\.environ` (provider-key
reads) + FieldDefs registry. Read-only; no code change in Phase 0.

#### Phase 0 classification result (2026-07-02)

| Env var / family | Class | Runtime owner | Decision |
|---|---|---|---|
| `POLYGON_API_KEY` | managed | `polygon.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `FINNHUB_API_KEY` | managed | `finnhub.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `FRED_API_KEY` | managed | `fred.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `FINANCIAL_DATASETS_API_KEY` | managed | `financial_datasets.api_key` | already FieldDef-managed; Phase 1 adds visible import when effective source is `config/.env`. |
| `IBKR_HOST` / `IBKR_PORT` | managed | `ibkr.host` / `ibkr.port` | already FieldDef-managed. |
| `IBKR_CLIENT_ID` | managed-with-default | `ibkr.client_id` | already FieldDef-managed; Phase 1 seeds explicit default `1` and guards edits. |
| `ARKSCOPE_SEC_USER_AGENT` | promote | `sec_edgar.user_agent` | canonical SEC User-Agent; promote to FieldDef in Phase 1. |
| `SEC_CONTACT_EMAIL` | legacy import alias | `sec_edgar.user_agent` | explicit per-field import only; imported value is normalized to `ArkScope <email>`. |
| `SEC_USER_AGENT` | legacy import alias | `sec_edgar.user_agent` | explicit per-field import only; imported value is treated as already full User-Agent. |
| `ALPHA_VANTAGE_API_KEY` | legacy_env_only | inactive desktop provider | live reader exists, but no active scheduler/API path uses it; keep warning-only until an Alpha Vantage feature is reintroduced DB-native. |
| `TIINGO_API_KEY` | legacy_env_only | inactive desktop provider | live reader exists, but no active scheduler/API path uses it; keep warning-only until a Tiingo feature is reintroduced DB-native. |
| `EODHD_API_KEY` | legacy_env_only | inactive desktop provider | live reader exists, but no active scheduler/API path uses it; keep warning-only until an EODHD feature is reintroduced DB-native. |
| `DISCORD_*` | legacy_env_only | ops monitor | not a data provider; keep out of provider FieldDefs. |
| `REDDIT_*` / `FMP*` | retiring/defer | no active reader | do not promote; revisit only if a real desktop feature is designed. |
| `DATABASE_URL` / `SUPABASE_DB_URL` | out of scope | PG-exit target | leave transitional until full PG exit removes the consumer. |
| LLM keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, OAuth tokens) | out of scope | auth-driver thread | do not mix with data-provider config. |

Phase 1 promotes only `sec_edgar.user_agent` plus the existing
`ibkr.client_id` default/guard. Alpha Vantage, Tiingo, and EODHD remain
`legacy_env_only` in this slice because they are not active desktop ingest paths;
any future S-C/S-F provider selected for IV or fundamentals must be added
DB-native instead of expanding `.env` fallback.

### 13.3 Phase 1 — visibility + hard startup (no default-behavior flip yet)

1. **Startup fail-closed = needs-setup mode, not process death:** unreadable
   profile DB at sidecar startup → boot into a setup-only state (replaces the
   `app.py:43` warn-and-continue): Settings/status surfaces stay up, but the
   scheduler loop is not started and provider fetch / collector subprocesses
   are disabled. The one forbidden outcome is today's behavior — silently
   continuing to collect on pure-.env config.
2. **Provenance surfaced:** status/Settings show `effective_source` per managed
   field; `config/.env` renders as "from config/.env — import suggested" with a
   **per-field** one-click import (Settings PUT exists; the 2026-06-27 .env→DB
   migration was one-shot, so this adds a first-class import affordance). No
   blind bulk import — any later batch action must be preview + selected-import.
3. **FieldDefs growth:** promote `SEC_CONTACT_EMAIL` / `ARKSCOPE_SEC_USER_AGENT`
   onto the existing `sec_edgar` provider (preserve the canonical-var-first
   precedence); promote the `legacy_env_only` candidates that pass the Phase-0
   promote/keep call.
4. **`IBKR_CLIENT_ID` seed + change guard** (already a FieldDef since Slice A —
   only the value was never seeded): if the DB row is missing, seed the explicit
   default `1`; Settings renders it app-managed (defaulted). Edits get a change
   guard (changing it disturbs IB Gateway sessions; the stored value is a *base*
   — `option_chain_tools` applies a +10 offset). The legacy `.env` name
   `IBKR_CLIENT` (never read by code) is not auto-ingested — explicit user
   import only.
5. **New-provider rule (effective immediately):** any provider added from now on
   (e.g. the S-F IV bulk backend) is DB-native only — no `.env` fallback is ever
   added for new keys.

### 13.4 Phase 2 — strict default (tri-state, news-S3.2 pattern)

- New setting `provider_env_fallback` (profile setting + env override),
  tri-state: **unset → strict** — FieldDefs-managed fields read DB-injected
  values only; a missing field is a structured
  `{code: "provider_config_missing", status: "not_configured", provider, field}`
  shared by provider-health, API routes, and agent tools (display layers may
  re-render it into their vocabulary, but consumers assert on the machine
  `code`, never on message text), and never a silent `.env` read.
  `legacy_env_only` vars keep working under strict with a rendered warning.
  Explicit `true` → legacy per-field fallback (migration/rescue). Explicit
  `false` → strict, pinned.
- Rollback = explicit `true`, mirroring the news S3.2 default-ON tri-state
  discipline (default is the new world; the old world needs an explicit flag).
- `config/.env` thereafter = import/export + migration material; real shell env
  remains the operator escape hatch (precedence unchanged).
- **Carried micro-fix, WIDENED per user review 2026-07-02 (email-first field
  UX; may land before Phase 2 as a standalone micro-slice):** the user-owned
  datum is a contact email — "ArkScope" is a program constant, and the field
  must not ask users to hand-compose a protocol string. (Found live: the field
  gave no hint an email was expected, and a hand-typed bare email was
  stored/injected un-prefixed because only `POST .../import-env` normalizes.)
  Scope: (a) FieldDef label → 聯絡 Email（SEC 自動化存取宣告用）— the UI input
  placeholder renders the label, so this alone fixes discoverability; (b) BOTH
  write paths (manual PUT + import-env) normalize with the heuristic: value
  contains `@` and no whitespace → bare email → store `ArkScope <email>`;
  contains whitespace → full custom UA → store as-is (power users keep full-UA
  passthrough; real-env escape hatch unchanged); (c) display keeps showing the
  composed full value. ~10-15 lines + tests (PUT-normalize, import-normalize
  unchanged, full-UA passthrough, label).

### 13.5 Gates / tests

- strict + DB value present → the file loader is not consulted for that var
  (assert via `keys_loaded_from_file` bookkeeping / monkeypatched loader).
- strict + missing → `provider_config_missing` at all three surfaces
  (provider-health, API route, agent tool), asserted on the machine `code` — no
  exception, no silent empty.
- explicit `true` → legacy fallback restored (rollback path proven).
- unreadable profile DB → boots needs-setup: Settings/status reachable,
  scheduler not started, collector subprocess launch refused (lifespan test).
- `IBKR_CLIENT_ID`: missing row → seeded `1`; edit → change guard; legacy
  `IBKR_CLIENT` env name never auto-ingested.
- `legacy_env_only` var under strict → still works + warning rendered, not
  blocked.
- worker entrypoints apply DB config before provider construction (extend the
  S-A1 worker tests).
- §11 generic gate applies; the only persistent-state growth is additive
  FieldDefs rows in `profile_state.db` (no live market-DB step in this slice).

### 13.6 Sequencing

- Does not block S-C (survey is doc work; run in parallel).
- **Phase 0–1 land before S-E**, so the IV prototype's provider wiring is born
  DB-first and never grows a `.env` dependency.
- Phase 0-1 implementation status: audit table recorded; SEC UA and IBKR
  client-id defaults are app-managed; `config/.env` fallback is still allowed but
  visible/importable; profile DB startup failure now enters setup-only mode.
  Phase 2 strict-by-default remains pending.
- Soak-gate status 2026-07-02: primary machine has no `config/.env`-sourced
  managed fields left (provider keys migrated 2026-06-27; `config/.env` never
  contained SEC UA keys, so SEC ran on the placeholder UA until the user set
  `sec_edgar.user_agent` manually in Settings today). Phase 2 can be scheduled;
  it should include the §13.4 carried micro-fix.
- Phase 2 flips only after Phase 1 has soaked: Settings shows no remaining
  "from config/.env" managed fields on the primary machine (or each is a
  conscious keep), then default-strict is turned on.

### 13.7 Decisions (locked at review, 2026-07-02)

1. **Strict scope:** FieldDefs-managed vars only. No runtime interception sweep
   of all `getenv()` (that becomes a house-cleaning project). Unmanaged provider
   keys are listed in the Phase-0 table as `legacy_env_only`; under strict they
   warn but never block. New providers never gain `.env` fallback.
2. **`not_configured` shape:** shared structured error —
   `code: "provider_config_missing"` / `status: "not_configured"` — one shape
   for provider-health, routes, and tools; display layers may re-render it, but
   the machine `code` is the contract (never a text-only status).
3. **Import affordance:** Phase 1 ships per-field import only. No blind bulk
   import as a mainline flow (it would re-bless `.env` as an authority); any
   later batch action must be preview + selected-import.
4. **`IBKR_CLIENT_ID`:** becomes managed-with-value, guarded: Phase 1 seeds the
   explicit default `1` when the DB row is missing, Settings shows
   app-managed/defaulted, edits warn (IB Gateway session impact), and the legacy
   `IBKR_CLIENT` `.env` name is imported only on explicit user action.
5. **Startup semantics (correction):** fail-closed means *boot to setup-only* —
   Settings/needs-setup surfaces stay available while the scheduler, provider
   fetch, and collector subprocesses are disabled. It does not mean the sidecar
   dies; it does mean no silent pure-.env collection.
