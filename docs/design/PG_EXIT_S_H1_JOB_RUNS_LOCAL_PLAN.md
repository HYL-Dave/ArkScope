# PG-Exit S-H1 Local Job Runs Plan

- **Date:** 2026-07-03
- **Status:** PLAN FOR REVIEW / NO CODE YET — review fixups folded 2026-07-03
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

### LOCK #9 constraint

`sa_native_host.py` is an external ingest client. It must not write `profile_state.db`
directly, because `LOCAL_FIRST_RESEARCH_WORKBENCH_SPEC.md` LOCK #9 says the SA native
host writes its isolated SA cache only and never writes the app/workbench DB. Therefore
this slice must preserve app-DB single ownership:

- sidecar/app process writes `profile_state.db`;
- native host records extension job telemetry by best-effort POST to a sidecar endpoint;
- if the sidecar is down, the native host silently degrades, matching today's PG-best-effort behavior.

Do not implement a narrow "telemetry exception" to LOCK #9.

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

- `GET /jobs/status`, `GET /jobs/history`, `POST /jobs/run/{job_name}`, scheduler telemetry, provider health, SA health, and macro health use local `profile_state.db`.
- native-host extension job recording is sidecar-owned: the native host sends a best-effort localhost request; the sidecar writes the local `job_runs` row.
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
- explicit `false` -> PG-backed `JobRunsStore(dal)` rollback lever while PG `job_runs` still exists
- unset -> PG-backed `JobRunsStore(dal)` during this transition

Endgame:

- The unset default is transitional. After N9 drops PG `job_runs`, collapse the dual-mode path so a fresh install defaults to local job runs; otherwise unset would construct a dead PG store.

Tests:

- default unset preserves PG store before cutover.
- profile/env true selects local store.
- profile/env false selects PG rollback while the PG table exists.
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
- `scripts/collection/daily_update.py`

Tests:

- job status/history APIs read local rows when the toggle is true.
- `run_job()` writes local start/finish rows.
- provider health can compute latest success/error from local rows.
- SA/macro health still degrade independently when job history is unavailable.
- scheduler seed still prefers local `scheduler_state`; job_runs is only a supplementary history signal.

### Task 3b — Native-Host Recording Boundary

Replace `scripts/sa_native_host.py` direct `JobRunsStore(dal)` writes with a best-effort
POST to a new sidecar-owned endpoint.

Requirements:

- sidecar endpoint accepts the existing extension job payload shape (`job_name`,
  `status`, `started_at`, `finished_at`, `payload`, `result`, `message`, `error`,
  `duration_ms`, `trigger_source`);
- endpoint validates status and timestamps, then records via `get_job_runs_store(dal)`;
- endpoint response contains only sanitized status / run id / error code; no secrets or scraped
  content;
- native host keeps current best-effort behavior: sidecar unavailable, timeout, HTTP failure, or
  validation failure must not fail the SA capture operation;
- native host must not import or construct the local job-runs store, and must not open
  `profile_state.db`.

Tests:

- sidecar endpoint records an extension row through the factory.
- native host sends the expected sanitized JSON payload to the configured localhost endpoint.
- native host degrades cleanly when the sidecar is unreachable.
- storage-isolation grep/test: `scripts/sa_native_host.py` has no `JobRunsStore(` and no
  `profile_state.db` writer path.

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
- Preview should report whether any PG rows were created after the first preview timestamp; this is
  diagnostic only because the fingerprint gate is the authority.

### Task 5 — Apply on Copy

Apply command writes only `profile_state.db` copy in dry-run testing:

- require `--expected-fingerprint`
- require `--confirm-scheduler-paused` for live apply
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

Operational constraints:

- Scheduler and manual job runners must be paused for live apply. Otherwise PG `job_runs` can grow
  between preview and apply, correctly causing fingerprint drift.
- Browser extension/native-host syncs should be idle during the apply window for the same reason.
- `profile_state.db` is much smaller than `market_data.db`; backup cost is negligible, but still
  required and must use no-clobber semantics.

### Task 6 — Live Gate

Live apply requires explicit approval after:

1. preview x2 byte-identical,
2. independent review of counts/fingerprint,
3. copy dry-run apply + idempotence,
4. quiet window with scheduler/manual jobs/native-host sync paused,
5. `--confirm-scheduler-paused`,
6. O_EXCL backup path confirmed.

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

Resolved by review, now plan assumptions:

1. `profile_state.db` is acceptable for v1 job-run storage, provided native host never writes it
   directly.
2. Historical PG `job_runs` should be migrated in full because it is small and preserves health
   history for low-frequency jobs.
3. `use_local_job_runs=true` should be flipped only by the migration apply command after validation;
   explicit `false` remains the rollback lever until N9; unset default collapses to local after PG
   `job_runs` is dropped.
