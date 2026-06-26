# Scheduler Hardening — Scoping

Date: 2026-06-25
Status: scoping (design-first; no code in this doc)

## Purpose

Make the in-app data scheduler (`src/service/data_scheduler.py`) **resumable, gap-filling,
recoverable, and transparent about failures** — the four properties the user named. The new
read-only coverage panel (`/market-data/trading-days`, `summarize_trading_day_coverage`) gives us
the observation base; this effort turns "we can SEE the gaps" into "the scheduler ACTS on them
safely and survives restarts." It deliberately follows the operation model locked in the Intraday
Behavior spec (`docs/superpowers/specs/2026-06-25-intraday-behavior-layer-design.md`): observe →
bounded operation → persist continuation → resume.

This is scoping only — it records the verified current state, the target, locked decisions, open
questions for the user, and a slice plan. No runtime code changes here.

## Current state (verified against code, 2026-06-25)

`data_scheduler.py` is a single in-process asyncio supervisor (`scheduler_loop`) that ticks every
enabled+due `SourceDef` (`SOURCES`). Verified facts that shape the design:

- **Due-ness is interval-only.** `_is_due(source)` = `enabled AND (now - last_attempt) >=
  interval`. It does NOT consult actual data gaps — a source re-fires on a clock, whether or not
  anything is missing. `price_backfill` then does a **blind full-window top-up** every run (no
  bar-count/continuation model — `market_data_direct.py` docstrings confirm "day-presence only").
- **Scheduler state is in-memory + PG, not local-durable.**
  - `_LAST_ATTEMPT` (in-mem) is seeded ONCE on start from PG `job_runs` via `_seed_last_attempts`
    — and only if `_pg_reachable()` (TCP probe). PG unreachable → no continuity → every source may
    fire one interval early.
  - `_LAST_RESULT` (last outcome incl. skips) and `_PROGRESS` are **in-memory only** — lost on
    every restart.
  - The durable run record is PG `job_runs` (`JobRunsStore`, sql/011). In a PG-exit / strict-local
    world this is the wrong store: the desktop app's scheduler history vanishes when PG is absent.
- **Failure reasons are fragmented across three stores**, two of which don't survive a local
  restart: `_LAST_RESULT.error` (in-mem), `job_runs.error` (PG), `provider_sync_meta.last_error`
  (local SQLite, but per-ticker, not per-scheduler-run). No single local surface answers "why did
  the last price_backfill fail, and what's still missing."
- **Locks (the safety boundary).** ✅ RESOLVED by the precursor (2026-06-26). The Gateway mutex
  (`IBKR_THREAD_LOCK` + `IBKR_FILE_LOCK('ibkr_gateway')`) now lives in `src/ibkr_gateway_lock.py`;
  `run_source` AND standalone `backfill_prices_direct` both acquire it (scheduler passes
  `acquire_gateway_lock=False` since it already holds it — non-reentrant). _Was: the lock was
  scheduler-private, so a standalone backfill dialed the Gateway without it._ The bounded
  gap-aware ops below inherit this single-Gateway-session guarantee.
- **No operation continuation.** There is no persisted "this run did days X..Y, resume at Z" — a
  killed mid-run leaves only an in-mem `_PROGRESS` that's already gone, and (for scheduler runs) a
  PG `job_runs` row. price_backfill's idempotent full-window re-run is the current "recovery": safe
  but unbounded and gap-blind.

## Target properties → design response

1. **Recoverable (可恢復) — local-durable scheduler state.** Move the scheduler's own state off PG
   into a local SQLite store (`profile_state.db` is the natural home — it already holds
   `schedule.{source}.*` settings and is the local app-records DB). Persist last-attempt,
   last-outcome, and last-error per source so restart continuity no longer depends on PG. PG
   `job_runs` may remain as an optional archive mirror, not the source of truth.
2. **Visible failure (可看見失敗) — one local failure surface.** A single local table/view the UI
   reads: per source (and per operation) — last status, last_error, when, and (for price) what's
   still missing. Reconcile with the existing `provider_sync_meta.last_error` (per-ticker) so the
   LC-style "this symbol won't resolve, stop retrying it" signal is visible at the scheduler level,
   not just in the coverage panel.
3. **Gap-filling (可補齊) — gap-aware scheduling.** The scheduler consults
   `summarize_trading_day_coverage` (or a shared internal of it) to decide WHAT to fetch, not just
   WHEN. price_backfill targets the actually-missing complete trading days for the actually-missing
   tickers, instead of a blind full-window top-up. Non-trading days, in-progress today, and
   known-unresolvable tickers (LC) are excluded up front.
4. **Resumable (可續跑) — bounded operations + persisted continuation.** Adopt the Intraday spec's
   operation model for price repair: an operation has a bounded budget (max tickers / days /
   provider requests / timeout), finishes `partial` with saved continuation scope when it hits the
   budget, and a later tick (or restart) resumes from the saved scope. No unbounded loops; a
   killed operation is visible as `partial`/`failed`, never silently `running`.

## Locked decisions (carried from prior work)

- **Local-first, PG-optional.** Scheduler state and failure surface live in local SQLite; PG is
  archive-only (consistent with the PG-exit direction).
- **Observe → bounded op → persist → resume** is the operation pattern (shared with Intraday).
- **One Gateway lock for all IBKR consumers** via the shared `ibkr_gateway_lock` precursor (below)
  — scheduler, standalone price backfill, and intraday all serialize on it.
- **Read-only observation already shipped** — the coverage panel is the gap oracle; hardening
  consumes it, does not duplicate the trading-day/holiday/session logic.
- **No new product surface** — scheduler ops/health stays inside Settings (Data Storage / Data
  Sources), per the post-pivot "ops view inside the workbench" decision.

## Precursor (shared with Intraday Slice 3) — ✅ DONE 2026-06-26

**Extracted `ibkr_gateway_lock` into `src/ibkr_gateway_lock.py`** (commits `5014473` extract +
`bf9847c` wire): `IBKR_THREAD_LOCK` + `IBKR_FILE_LOCK('ibkr_gateway')` + `ibkr_gateway_lock()`
context manager; `FileLock`/`lock_dir` moved there too. `data_scheduler.run_source` imports the
same singletons (behavior-identical, two skip messages kept); standalone `backfill_prices_direct`
now acquires the shared lock across preflight+fetch, and the scheduler passes
`acquire_gateway_lock=False` (the lock is non-reentrant; scheduler already holds it). 97 tests
green. Every IBKR consumer now serializes on one Gateway session — the safe base the bounded
gap-aware ops below require.

## Locked decisions (user, 2026-06-26)

1. **State store** → a SINGLE `scheduler_state` table in `profile_state.db` (one row per source:
   last_attempt / last_status / last_error / continuation_json). Don't start heavy; add a per-run
   history log only if it proves needed.
2. **Gap vs. interval** → AUGMENT, not replace. The interval stays a **rate-limit / backoff** (how
   OFTEN a source may run); the trading-day coverage diagnostic decides the **SCOPE** within a run
   (which days/tickers to fetch). `_is_due` keeps gating frequency; the gap query shapes the work.
3. **v1 scope** → **`price_backfill` only** (the one domain with a clean gap oracle today). News /
   IV / fundamentals are NOT touched here — they generalize later (and overlap the ingest
   direct-local work in `PG_EXIT_COMPLETION_PLAN.md` step 2).
4. **Auto-continue** → **attended/manual continue first.** A `partial` run surfaces "N still
   missing → [補抓]" in Settings; the user triggers the continuation. Auto-resume-on-next-tick is
   deferred until the telemetry is trusted in practice.
5. **`enabled` default** → stays **OFF.** Hardening makes enabling SAFE; flipping the default is a
   separate later decision.

## v1 slice plan (read-only planner → local state → bounded run/resume → Settings UI)

Decisions above locked. Slice 0 (lock) is DONE. The order front-loads the **read-only planner**
(pure, no writes, fully testable) so the gap→scope logic is pinned before any runtime/state change.

- **Slice 0 — `ibkr_gateway_lock` extraction.** ✅ DONE (see Precursor).

- **v1.1 — read-only backfill PLANNER (pure function, no writes, no scheduler change).**
  **Planner/executor contract (locked):** the executor (`backfill_prices_direct`) is window-based
  top-up — it takes `tickers_arg` + `lookback_days` and `INSERT OR IGNORE`s a contiguous
  complete-day window (no per-day fetch entry point, and we are NOT adding one — the top-up's
  idempotence is the proven heal path). So the planner outputs a **bounded ticker set + a window
  depth**, NOT a (ticker, day-list): `plan_price_backfill(coverage, *, max_tickers, max_days,
  exclude_tickers) -> BackfillPlan` where `BackfillPlan = {tickers: list[str], lookback_days: int,
  excluded: list[{ticker, reason}], deferred: list[str], candidate_count: int}`. It consumes
  `summarize_trading_day_coverage`: select tickers that have ≥1 missing COMPLETE trading day,
  EXCLUDE non-trading/in-progress (not gaps) + known-unresolvable tickers (the `LC`-style
  provider-error / persistent-zero signal, via `exclude_tickers`); `lookback_days` = enough to
  reach the OLDEST selected gap (capped at `max_days`); cap the ticker set at `max_tickers` and
  put the rest in `deferred` (→ v1.3 continuation). Pure + deterministic → hermetic tests only;
  touches nothing live. This is the gap→scope core that decisions 2/3 depend on.

- **v1.2 — local scheduler-state store** (recoverable + visible-failure). Single `scheduler_state`
  table in `profile_state.db` (decision 1): per-source last_attempt / last_status / last_error /
  continuation_json. Seed `_LAST_ATTEMPT` from it instead of PG `job_runs`; record outcomes
  locally; PG `job_runs` becomes an optional archive mirror. Hermetic; no scheduling-behavior
  change yet (interval logic unchanged — just its state moves local).

- **v1.3 — wire the planner + bounded run + continuation** (gap-filling + resumable). `_is_due`
  still gates frequency (decision 2: interval = rate-limit); when due, `price_backfill` runs the
  PLANNER for scope (not a blind full-window), bounded by budget; on budget-exhaustion finishes
  `partial` and writes `continuation_json` (the remaining scope). **Attended** (decision 4): the
  next tick does NOT auto-resume — continuation waits for an explicit trigger. Tests: timeout/
  budget → `partial` (never stuck `running`); a manual continue covers the saved remainder; the
  gateway lock (precursor) serializes it. price_backfill only (decision 3). Default OFF (decision 5).

- **v1.4 — Settings surface.** Scheduler state + last failure reason + "N days/tickers still
  missing → [補抓]" (manual continue) in the Data Storage / Data Sources area, reusing the
  coverage panel + the local scheduler-state store. No new product surface.

## Relation to the coverage panel + Intraday layer

This hardening is the consumer the coverage panel (Slice A/B) was built to enable, and it shares
the Intraday spec's operation model + the `ibkr_gateway_lock` precursor. The three efforts
converge on one pattern: **observe locally, operate within a budget, persist continuation, resume
safely** — with PG out of the runtime path.
