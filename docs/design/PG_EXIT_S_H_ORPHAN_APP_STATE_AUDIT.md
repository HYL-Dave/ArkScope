# PG-Exit S-H Orphan + App-State Audit

- **Date:** 2026-07-03
- **Status:** AUDIT COMPLETE / AWAITING DISPOSITION DECISIONS
- **Map check:** `PROJECT_PRIORITY_MAP.md` P0-B points here after S-G scorer cutover.
- **Scope:** read-only local SQLite inspection + static reader grep. No live DB writes, no PG writes, no runtime route changes.

This audit answers the S-H question from `PG_EXIT_REMAINDER_SCOPING.md` §6 item 8:

1. Which PG market-data tables are now true or likely orphans?
2. Which app-state tables already have a local home?
3. Which remaining PG tables still carry runtime semantics and need a relocation slice before N9?

## 1. Local Grounding

Read-only SQLite checks on the active local files:

| Local DB | `quick_check` | Relevant counts | Meaning |
|---|---:|---:|---|
| `data/sa_capture.db` | ok | `sa_alpha_picks=112`, `sa_articles=395`, `sa_article_comments=41,215`, `sa_market_news=22,086`, `sa_comment_signals=39,853`, `sa_market_news_tickers=21,689` | SA data is populated locally and larger than the old PG-freeze baseline. |
| `data/macro_calendar.db` | ok | `macro_series=11`, `macro_observations=29,571`, `macro_release_dates=4,659`, `cal_ipo_events=86`, `cal_economic_events=0`, `cal_earnings_events=0` | Macro/FRED data and IPO events are local; economic/earnings event local tables are empty and need an explicit decision before PG drop. |
| `data/profile_state.db` | ok | `research_reports=2`, `agent_memories=1`, `agent_queries=2`, `scheduler_state=5`, `profile_settings=15` | App-records have a local home; scheduler has local durable per-source state. |
| `data/market_data.db` | ok | `prices=2,324,172`, `news_articles=292,461`, `news_article_scores=491,808`, `financial_cache=20`, `fundamentals=130`, `iv_history=24` | S-G scores are local; fundamentals/IV legacy tables are tiny; prices remain the large pending migration. |

Active profile flags:

| Key | Value | Meaning |
|---|---:|---|
| `use_local_records` | `true` | `agent_queries` / `research_reports` / `agent_memories` route to `profile_state.db`. |
| `use_local_sa` | `true` | SA routes to `sa_capture.db`. |
| `use_local_macro` | `true` | macro/cal store factory selects `macro_calendar.db`. |
| `use_local_market` | `true` | market reads are local-primary. |
| `use_local_market_strict` | unset | some market-cache and IV fallback paths can still consult PG when local misses. |
| `news_pg_exit_completed` | `true` | news-domain PG exit finalized. |
| `use_normalized_news_writes` | `true` | normalized news writer is active. |

## 2. Orphan / Drop-Candidate Findings

| PG domain | Audit result | N9 status |
|---|---|---|
| `news` | News reads/writes are local after N8a; S-G does not require PG news. | **Drop candidate** after final reader grep and backup retention decision. |
| `news_scores` | S-G imported active score history into `news_article_scores`; active imports now use `scripts/scoring/import_news_scores_local.py`; PG `--scores` is archive-only. | **Drop candidate** after final reader grep. `DatabaseBackend.query_news_scores()` is a dead PG helper and belongs in N9 dead-path cleanup. |
| `fundamentals` | S-B retired the frozen mirror table as authority. Stored fundamentals read local annual SEC cache only; default analysis refetches/caches locally. | **Drop candidate**; keep only if needed as a short-term archive snapshot. |
| `iv_history` | 24 old rows, no meaningful historical series; IV reboot is design-gated and not a migration. | **Drop candidate** for old PG rows; future IV starts from a new local raw-retain schema if approved. |
| `sa_*` | Runtime SA authority is local `sa_capture.db` under `use_local_sa=true`. SA tools and digest paths read local data; old PG SA tables are frozen legacy state. | **Likely drop candidate**, but final N9 must grep for any migration/report/debug script still intentionally reading PG SA archives. |
| `signals` | Static grep found no runtime SQL reader/writer for a PG `signals` table (`FROM/INSERT/UPDATE/DELETE signals`). Current signal tools compute from current local sources. | **Drop/dead-path candidate** if table exists; no relocation proposed. |

## 3. Not Yet Drop-Safe

These are not failures. They are real remaining seams that should not be hidden under "orphan cleanup."

| PG domain | Why it is not drop-safe | Required next slice |
|---|---|---|
| `job_runs` | `JobRunsStore` still writes/reads PG `job_runs` best-effort. Provider health, jobs API/history, SA health, macro health, and scheduler continuity still use it as an operational log. Local `scheduler_state` covers durable per-source last status/continuation, but it is not a full job history replacement. | **S-H1: local job-runs/ops store.** Relocate job execution history to `profile_state.db` or a small `ops.db`; keep `scheduler_state` for per-source continuation. |
| `financial_data_cache` | `LocalMarketDatabaseBackend.get_financial_cache()` is local-first but, because `use_local_market_strict` is unset, still falls back to PG and read-through-promotes valid rows into local `financial_cache`. | **S-H2: financial-cache strict-local.** Either one-time promote wanted PG rows, then disable fallback, or accept local-only cold misses. |
| `macro_*` / `cal_*` | `use_local_macro=true` selects `macro_calendar.db`; however local `cal_economic_events` and `cal_earnings_events` are empty. PG may still contain rows or serve as a fallback when the toggle is off. | **S-H3: macro/cal final proof.** Confirm PG row counts and decide whether empty local economic/earnings tables are acceptable, re-fetchable, or need one-time local seed before drop. |
| `prices` | Large core domain, not an orphan. | Separate P0-C migration slice. |

## 4. App-State Disposition

Cut A from the scoping doc still holds: app-state does not belong in `market_data.db`.

| Table | Current local status | Recommendation |
|---|---|---|
| `agent_queries` | `profile_state.db` has rows and `use_local_records=true` selects `AppRecordsLocalStore`. | Treat PG as pre-migration archive; N9 drop after final reader grep. |
| `research_reports` | `profile_state.db` has rows; report tools use the app-record store. | Keep local profile authority. Future report files/export are product UX, not PG-exit blockers. |
| `agent_memories` | `profile_state.db` has rows; memory tools use the app-record store. | Keep local profile authority. Future FTS/vector memory can be designed separately. |
| `job_runs` | Still PG-backed operational log; local `scheduler_state` is partial continuity state only. | Relocate, do not retire. Prefer device-local store (`profile_state.db` if write volume is acceptable, otherwise `ops.db`). |
| `signals` | No runtime PG SQL reader/writer found. | Retire PG table/dead path. If product signal history returns, design a new local schema deliberately. |

## 5. Recommended Next Actions

1. **S-H1 local job-runs/ops store**
   Add a local `job_runs` store with the existing `JobRunsStore` method surface, redirect `src/service/jobs.py`, scheduler telemetry, provider health, SA health, and macro health. This is the highest-value remaining small PG-exit slice because it removes the active app-state seam.

2. **S-H2 financial-cache strict-local**
   Decide whether to promote existing PG `financial_data_cache` rows into local `financial_cache` first. Then remove the PG read-through path or require `use_local_market_strict=true` for desktop runtime.

3. **S-H3 macro/cal proof**
   Query PG `macro_*` / `cal_*` counts and compare against local `macro_calendar.db`. If PG has economic/earnings event data that local lacks, choose one of: re-fetch, one-time seed, or accept honest-empty. Only then mark macro/cal N9-safe.

4. **S-I/N9 first drop batch**
   After final reader grep, drop/archive the clearly localised market orphans: PG `news`, `news_scores`, `fundamentals`, `iv_history`, likely `sa_*`, and legacy PG `signals` if present. Keep prices, job_runs, financial cache, and unresolved macro/cal out of this first batch.

## 6. Open User Decisions

1. **Job runs home:** `profile_state.db` vs a new `ops.db`. `profile_state.db` is simpler and already device-local; `ops.db` gives cleaner write isolation for scheduler telemetry.
2. **Financial cache cold-start:** promote PG rows first, or accept cold local cache and remove fallback immediately.
3. **Macro/cal empty tables:** accept local empty economic/earnings events, re-fetch them, or seed from PG once.
4. **N9 archive policy:** whether to keep a PG dump / SQLite export for dropped orphan domains before destructive removal.
