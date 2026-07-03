# PG-Exit S-H1 Local Job Runs Plan

- **Date:** 2026-07-03
- **Status:** PLAN FOR REVIEW / NO CODE YET
- **Parent audit:** `PG_EXIT_S_H_ORPHAN_APP_STATE_AUDIT.md`
- **Map check:** P0-B follow-up after S-H audit.

## 1. Decision

Move `job_runs` from PG-backed best-effort telemetry into `profile_state.db`.

Rationale:

- `job_runs` is app-state / ops telemetry, not market data, so it must not go into `market_data.db`.
- `profile_state.db` already carries app-records, data-provider config, scheduler state, and other device-local app state.
- Volume is small enough for SQLite (`~13k` PG rows historically; future writes are job/scheduler cadence, not high-frequency market ticks).
- A separate `ops.db` can still be introduced later if write pressure appears, but starting with it now adds another store, another backup path, and another migration surface before there is evidence of contention.

This is a v1 storage decision, not an irreversible product claim. If later telemetry volume or lock contention justifies `ops.db`, the local `job_runs` table can be moved as a bounded app-state migration.

## 2. Non-goals

- Do not split `job_definitions` from `job_runs` in this slice. The schema split remains a workbench/ops UX project.
- Do not migrate prices, financial cache, macro/cal, or any market-data table.
- Do not drop PG `job_runs` in this slice. N9 drop waits for live local cutover + soak.
- Do not change job scheduling semantics.
- Do not keep a silent PG fallback after cutover.

## 3. Target Behavior

Before cutover:

- Existing `JobRunsStore(dal)` behavior remains available for tests and any not-yet-repointed caller.
- New local store and factory exist behind a toggle.
- No runtime route changes until tests and migration preview pass.

After cutover:

- `GET /jobs/status`, `GET /jobs/history`, `POST /jobs/run/{job_name}`, scheduler telemetry, provider health, SA health, macro health, and native-host extension job recording all use local `profile_state.db`.
- PG outage does not affect job history/status recording.
- New job-run rows continue from the migrated max id.
- PG `job_runs` becomes archive-only and an N9 drop candidate after soak.

## 4. Schema

Add a SQLite `job_runs` table in `profile_state.db` with the same public row shape as `sql/011_add_job_runs.sql`:

```sql
CREATE TABLE IF NOT EXISTS job_runs (
    id              INTEGER PRIMARY KEY,
    job_name        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('running', 'succeeded', 'failed')),
    trigger_source  TEXT NOT NULL DEFAULT 'api',
    payload         TEXT NOT NULL DEFAULT '{}',
    result          TEXT,
    message         TEXT,
    error           TEXT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    duration_ms     INTEGER,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_job_runs_name_started_at
    ON job_runs (job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_runs_status_started_at
    ON job_runs (status, started_at DESC);
```

JSON fields are stored as JSON text and returned as Python dicts/lists by the store, preserving the API shape.

## 5. Implementation Tasks

### Task 1 — Local Store TDD

Add `JobRunsLocalStore` in `src/service/job_runs_store.py` or a sibling module.

RED:

- local `create_run()` inserts `running` and returns id.
- local `finish_run()` transitions to terminal status.
- local `list_runs()` filters by job name, clamps limit/offset, and serializes datetimes/JSON like PG.
- local `latest_runs_by_name()` returns the latest row per job.
- invalid status behavior remains identical to PG store.
- store gracefully returns empty/false on SQLite operational errors without failing the job.

GREEN:

- Implement schema creation on write path.
- Preserve PG store class for migration preview and rollback until N9.

### Task 2 — Store Factory + Toggle

Add:

- profile key `use_local_job_runs`
- env override `ARKSCOPE_USE_LOCAL_JOB_RUNS`
- `get_job_runs_store(dal)` factory

Routing:

- `true` -> local `JobRunsLocalStore(profile_state.db)`
- `false` or unset -> existing PG-backed `JobRunsStore(dal)`

Tests:

- default unset preserves PG store before cutover.
- profile/env true selects local store.
- local factory works with a DAL that has no PG backend.
- no caller needs direct `JobRunsStore(dal)` after Task 3 except tests and migration utilities.

### Task 3 — Repoint Runtime Callers

Replace direct runtime construction with the factory:

- `src/service/jobs.py`
- `src/api/routes/jobs.py`
- `src/service/provider_health.py`
- `src/service/data_scheduler.py`
- `src/service/sa_market_news_health.py`
- `src/service/macro_calendar_health.py`
- `scripts/sa_native_host.py`
- `scripts/collection/daily_update.py`

Tests:

- job status/history APIs read local rows when the toggle is true.
- `run_job()` writes local start/finish rows.
- provider health can compute latest success/error from local rows.
- SA/macro health still degrade independently when job history is unavailable.
- scheduler seed still prefers local `scheduler_state`; job_runs is only a supplementary history signal.

### Task 4 — Migration Preview

Add a read-only preview command, likely under `scripts/migration/job_runs_local_cutover.py`.

Preview reads PG `job_runs` and local `profile_state.db` in read-only mode and emits:

- `pg_rows`
- `local_rows`
- `latest_started_at`
- `status_counts`
- `job_name_counts`
- row-level deterministic fingerprint over all PG rows to migrate
- `would_apply`
- blocker list

Rules:

- If local `job_runs` has rows and they are not already an exact migrated subset, block.
- If local table is absent or empty, preview may apply.
- Fingerprint must be stable across two runs.

### Task 5 — Apply on Copy

Apply command writes only `profile_state.db` copy in dry-run testing:

- require `--expected-fingerprint`
- create an O_EXCL backup of `profile_state.db`
- one SQLite transaction
- preserve PG ids into local `id`
- insert all rows
- set `use_local_job_runs=true` only after row validation passes
- reopen read-only and validate counts/fingerprint/idempotence

The copy dry-run must prove:

- migrated row count equals preview `pg_rows`
- max id preserved
- `list_runs()` and `latest_runs_by_name()` match PG preview aggregates
- second apply is idempotent
- rollback leaves the copy unchanged on injected failure

### Task 6 — Live Gate

Live apply requires explicit approval after:

1. preview x2 byte-identical,
2. independent review of counts/fingerprint,
3. copy dry-run apply + idempotence,
4. quiet window,
5. O_EXCL backup path confirmed.

After live apply:

- run `/jobs/status` and `/jobs/history` smoke.
- run one small API-triggered job smoke or a no-op/fake job test path.
- confirm provider health no longer depends on PG `job_runs`.
- keep PG table as archive through soak.

### Task 7 — Docs + N9 Marking

After live apply:

- update `PG_EXIT_REMAINDER_SCOPING.md` S-H1 status,
- update `PROJECT_PRIORITY_MAP.md` decision log,
- mark PG `job_runs` as N9 candidate after soak,
- record backup path and fingerprint,
- leave `scheduler_state` semantics unchanged.

## 6. Review Gates

Offline gate:

- focused job tests,
- provider-health tests,
- SA/macro health tests,
- scheduler-state tests,
- grep gate: no runtime direct `JobRunsStore(` construction outside factory/migration/test paths.

Live gate:

- same preview -> backup -> transaction -> validate -> read-only reopen pattern used by N7/N8a/S-G.

## 7. Open Review Points

1. Confirm `profile_state.db` is acceptable for v1 job-run storage.
2. Confirm historical PG `job_runs` should be migrated rather than starting fresh.
3. Confirm `use_local_job_runs` should be flipped only by the migration apply command, not Settings.
