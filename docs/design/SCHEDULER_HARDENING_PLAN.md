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
- **Locks (the safety boundary).** `_IBKR_LOCK` (in-proc `threading.Lock`) + `_IBKR_FLOCK`
  (`_FileLock("ibkr_gateway")`, cross-process) serialize Gateway work — but only inside
  `run_source()` when `SourceDef.ibkr=True`. A standalone `backfill_prices_direct` takes only
  `market_write_lock` (`local_refresh.lock`, the DB-write lock) and dials the Gateway in its
  preflight WITHOUT the Gateway flock. (Same gap the Intraday spec flagged — see Precursor.)
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

## Precursor (shared with Intraday Slice 3)

**Extract `ibkr_gateway_lock` into a shared module** (e.g. `src/ibkr_gateway_lock.py`): move
`_IBKR_FLOCK`/`_IBKR_LOCK` out of `data_scheduler.py`, expose an `ibkr_gateway_lock()` context
manager, and re-point the scheduler's `run_source`, standalone `backfill_prices_direct`, and the
future intraday operation at it. Pure refactor (no behavior change), fully testable
(cross-process serialize; standalone now holds it). Lands before any gap-aware backfill operation
so the new bounded ops can't overlap the Gateway with a manual backfill.

## Open questions (need the user's call before slicing)

1. **State store granularity.** A single `scheduler_state` table in `profile_state.db` (one row per
   source: last_attempt / last_status / last_error / continuation_json), OR a richer
   `scheduler_runs` + `scheduler_run_meta` pair mirroring `provider_sync_runs`/`_meta`? The former
   is smaller; the latter gives per-run history + aligns with the intraday `*_runs` model. Lean:
   start with the single table, add a runs log only if history is needed.
2. **Gap-aware trigger vs. interval.** Should gap-awareness REPLACE the interval (`_is_due` becomes
   "due if coverage shows fillable gaps"), or AUGMENT it (interval still bounds frequency, gaps
   decide scope within a run)? Lean: augment — keep the interval as a rate limit, use gaps for
   scope — but this changes scheduling semantics, so it's the user's call.
3. **Scope of hardening v1.** Just `price_backfill` (the one with a clean gap oracle today), or all
   IBKR sources (news/iv) too? Lean: price_backfill first (the coverage panel only models prices),
   generalize later.
4. **Auto-continue vs. attended.** After a `partial`, does the next tick auto-resume, or does it
   wait for an explicit "continue" (like the universe-backfill batch-gated run we did manually)?
   Lean: attended first (surface "N days still missing, [補抓]"), auto-resume once trusted — but
   this is a product/safety call.
5. **`enabled` default.** Stays default-OFF (current behavior) through v1 — hardening makes it
   SAFE to enable, but flipping the default on is a separate, later decision. (Assumed yes.)

## Slice plan (after the open questions are answered)

- **Slice 0 — `ibkr_gateway_lock` extraction** (the precursor; pure refactor + tests).
- **Slice 1 — local scheduler-state store** (recoverable + visible-failure): the table(s) per Q1,
  persist last-attempt/outcome/error locally, seed `_LAST_ATTEMPT` from it instead of PG, keep PG
  as optional archive. Hermetic tests; no scheduling-behavior change yet.
- **Slice 2 — gap-aware price_backfill scope** (gap-filling): the bounded operation consumes the
  coverage gaps + excludes known-unresolvable tickers; per Q2/Q3. Tests with a fake provider +
  the coverage oracle.
- **Slice 3 — bounded operation + continuation** (resumable): budget → `partial` + saved scope →
  resume per Q4. Tests: timeout marks partial (never stuck `running`), resume covers the remainder.
- **Slice 4 — Settings surface**: scheduler state + failure reasons + "still missing / 補抓" in the
  Data Storage / Data Sources area, reusing the coverage panel.

## Relation to the coverage panel + Intraday layer

This hardening is the consumer the coverage panel (Slice A/B) was built to enable, and it shares
the Intraday spec's operation model + the `ibkr_gateway_lock` precursor. The three efforts
converge on one pattern: **observe locally, operate within a budget, persist continuation, resume
safely** — with PG out of the runtime path.
