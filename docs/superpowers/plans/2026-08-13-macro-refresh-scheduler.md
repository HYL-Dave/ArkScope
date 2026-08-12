# Macro Refresh and Scheduler Integration Implementation Plan

> **Status:** DRAFT; PLAN REVIEW REQUIRED; IMPLEMENTATION NOT AUTHORIZED
>
> **Date:** 2026-08-13
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-13-macro-refresh-scheduler-design.md`,
> user-approved at `bdd8fc30`; the status-only handoff in this docs change does
> not alter the approved body.
>
> **Product grounding base:**
> `bdd8fc30dd35ebcd9acc83efde3411b88ab18ed3` (docs-only over product tip
> `bea5890f`).
>
> **Roles:** Codex authors this plan and, after independent plan review,
> implements it RED-first. Fable independently reviews task evidence and
> product diffs. The user makes product and live-provider rulings.

**Goal:** connect the five existing recurring FRED/Finnhub macro collectors to
the app-owned per-source scheduler, serialize every `macro_calendar.db` writer,
show the same honest controls on Data Sources and Macro Data, and remove the
legacy feature flag from automation claims.

**Architecture:** move macro domain execution into one telemetry-free
dispatcher; wrap all six macro writers in one fail-closed process and file
lock; let `run_job()` and `run_source()` each own exactly one canonical
`fetch_*` job row; register five opt-in schedule sources; and extract the
frontend schedule controller/table so both Settings surfaces consume one
schedule truth. Local status reads remain provider-free.

**Stack:** Python 3.10, FastAPI, SQLite, React 18, TypeScript, Vitest 4.1.8,
Vite 5.4.21, Playwright 1.58.0, Chrome 150.0.7871.128.

---

## 0. Authority, boundaries, and grounding

### 0.1 Binding authority

This plan implements design LD 1 through LD 7 without changing their product
decisions. In particular:

- the recurring registry is exactly five source IDs;
- the historical economic backfill is not a schedule source;
- all recurring sources default disabled;
- normal FRED refresh is incremental;
- one macro writer may start per scheduler tick;
- `schedule.<source>.*` is the only app automation truth;
- `macro_calendar_enabled` remains only the existing agent/job capability gate;
- local reads, mount, idle, focus, visibility, and `重新讀取狀態` send zero
  provider requests; and
- provider traffic requires either a due enabled source or an explicit
  `立即更新` click.

No live provider request is authorized by this plan. A later bounded smoke may
be proposed only after canonical local admission and requires explicit user
authorization.

### 0.2 Owned files

Backend owners:

```text
new src/macro_calendar/execution.py
new src/macro_calendar/write_lock.py
src/service/jobs.py
src/service/data_scheduler.py
src/service/provider_health.py
src/api/routes/macro_calendar.py
src/api/routes/schedule.py
src/smoke/pg_unreachable_e2e.py
new tests/test_macro_scheduler_integration.py
tests/test_data_scheduler.py
tests/test_fred_ingestion.py
tests/test_finnhub_ingestion.py
tests/test_macro_calendar_health.py
tests/test_macro_calendar_read.py
tests/test_provider_health.py
tests/test_macro_calendar_settings_route.py
tests/test_job_runs.py
tests/test_service_api_slice.py
```

Frontend owners:

```text
new apps/arkscope-web/src/settings/dataScheduleControls.tsx
new apps/arkscope-web/src/settings/dataScheduleControls.test.tsx
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx
apps/arkscope-web/src/settings/settingsReadCache.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/i18n/resources.test.ts
apps/arkscope-web/src/settings/settings.css
```

Plan/evidence owners are this file, a new evidence file, and the newest-first
decision-log entry in `docs/design/PROJECT_PRIORITY_MAP.md`.

Any product or test path outside this list is a stop condition. Dependency
files, database schemas, provider request shapes, collector formulas, source
catalogs, live configuration, secrets, and production databases are protected.

### 0.3 Pinned tools

```text
package-lock.json
  5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
node_modules/.package-lock.json
  4dd5182f8111b54dd608344c45513f3b310f39321a3cc9832b60cefc2fa241ff
Node v22.14.0 / Vitest 4.1.8 / Vite 5.4.21
Chrome 150.0.7871.128 / Playwright 1.58.0
/tmp/eir006_vitest_list_normalizer.py
  955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac
/tmp/eir002-green-baseline/arkscope_eir002_reporter.py
  09d2bc52c7706b49e5f363fa2c6bcfc93523038f1c805fef08bb98a409301928
/tmp/eir002-green-baseline/run_native.sh
  e7c963f1bc97125b70b435fb3c41bf4e59d501f0da561f2ef6d921c12083c84f
```

Vitest identity is decoded
`relative_file<TAB>full_test_name`, UTF-8 byte sorted with one trailing newline.
Raw JSON-text extraction or a positional `--json <path>` invocation is not
equivalent and is forbidden; use `--json=<path>`.

### 0.4 Re-grounded baselines

The plan author collected, but did not execute, the backend suite with the
pinned reporter and collected the frontend with the pinned decoded normalizer:

| Stream | Baseline |
|---|---|
| backend full | `4,341 / 883b1148e8759ea8825ffd8b825db0339dc1e6ca5aefe4c04344b868b3ff1264` |
| backend focused, nine files in §2.5 | `375 / 1c3ce4accfe583b6c059d1c52414376cd1697f24ce8f968afbc844250bd9a1d5` |
| frontend full | `99 files / 1,159 / f19472dd04c73afd979d37f4c083ff8246a007816d58429a2c12295eaadc5e67` |
| frontend focused, five existing files in §2.6 | `88 / 9b9d488a9512cf22d60e5482da233b9d035a89b49d72807b00cfb7361461ba39` |

Backend raw collect report:

```text
/tmp/eir002-green-baseline/reports/macro-plan-base-bdd8fc30.json
SHA-256 6dcf0809dc4d3c4f1087a059eeb00c53775ccdeb4823332edab99f4202f6f22e
4,341 collected / 0 seen / 0 non-passing / exit 0
```

Plan-author native control on the same product bytes:

```text
/tmp/eir002-green-baseline/reports/macro-plan-native-bdd8fc30.json
report SHA-256 534cfe6f886c348d3b76bdcca2687bd5a7fefe019eef235f46a200b5f86e0f40
transcript SHA-256 0aaace4aaa8fc73d4f28ac2c96f43edb23cb539b781c8cabb63bec399ff882c3
4,341 collected = 4,329 passed / 12 skipped / 0 failed / exit 0
```

Focused runtime controls on the same tree are `375 passed` backend and
`88 passed` frontend. Both are provider-free fixture suites.

Task 0 must reproduce all four streams and run the focused baselines before a
RED commit. Task 0 may reuse this exact clean native control only while product
bytes remain unchanged; any product change before Task 1 RED invalidates that
reuse.

### 0.5 Grounded implementation constraints

1. `run_source()` currently creates `collect.<source>` telemetry itself.
   `run_job()` independently creates `fetch_*` telemetry. Calling one from the
   other would create two rows and is forbidden.
2. The existing private macro job functions in `src/service/jobs.py` own all
   date-window and parameter validation. That logic moves once into the shared
   execution module; compatibility wrappers may delegate but may not retain a
   second formula.
3. Existing `FileLock` and `market_write_lock` deliberately degrade to an
   unlocked run when `fcntl` or the lock path is unavailable. That behavior is
   not acceptable for the shared macro database. The new macro lock must fail
   closed.
4. `tick_once()` currently records market-writer deferrals as transient skips.
   Macro deferral has a different contract: do not start it, do not advance its
   attempt time, do not write a success/skip row, and leave it due.
5. `MacroSnapshot.auto_refresh_enabled` and FRED provider-health automation are
   currently derived from `macro_calendar_enabled`; both are false authorities.
6. `DataSourcesSection` currently owns schedule loading, polling, mutation, and
   rendering together. Copying that block into Macro Data would create a second
   controller. It must be extracted.
7. `settingsReadCache.invalidateDataSource()` currently clears every data-sync
   resource for an unknown source and has no macro mapping. Immediate run-click
   invalidation also cannot be reused as proof that data changed; macro storage
   keys invalidate only after terminal success.
8. Existing provider-config rejection occurs before `_LAST_ATTEMPT` advances.
   Reusing that ordering for a macro source would let the first misconfigured
   due source win every 30-second tick and starve later macro sources. A fired
   macro preflight is a canonical failed attempt and enters its own interval
   backoff; a source merely deferred because another macro writer fired does
   neither.

---

## 1. Concrete implementation contract

### 1.1 Shared macro execution is telemetry-free

Create `src/macro_calendar/execution.py` with a closed dispatcher:

```text
MACRO_JOB_NAMES
execute_macro_job(job_name, dal, params) -> dict
is_macro_job(job_name) -> bool
```

It owns the existing parameter parsing, date-window validation, watchlist
selection, ingestion calls, and `stats.to_dict()` conversion for exactly:

```text
fetch_fred_series
fetch_fred_release_dates
fetch_economic_calendar_recent
fetch_economic_calendar_backfill
fetch_earnings_calendar
fetch_ipo_calendar
```

It does not import `run_job`, `data_scheduler`, `job_runs_store`, FastAPI, or
frontend code and never creates or finishes telemetry. `src/service/jobs.py`
delegates these six branches to it. Existing private `_run_fetch_*` functions
may remain as thin compatibility delegates only where current tests/importers
require them; their bodies must contain no date/provider formula.

### 1.2 One fail-closed macro writer lock

Create `src/macro_calendar/write_lock.py`:

```text
MacroCalendarBusy(code="macro_calendar_busy")
macro_calendar_writer(timeout_seconds=0.0)
```

The context manager acquires one process-local `threading.Lock` and one POSIX
`flock` at `ARKSCOPE_LOCK_DIR/macro_calendar_writer.lock` (falling back to the
directory returned by `src.ibkr_gateway_lock.lock_dir()` when the env override
is absent). It rejects symlinks, verifies a regular file, uses
close-on-exec/no-follow where available, and closes the descriptor on every
exit path. Failure to import `fcntl`, create or validate the lock file, or
acquire either layer raises the typed busy error; it never
logs-and-runs-unlocked.

`execute_macro_job()` holds this lock across the complete provider read and
SQLite write, as required by the approved design. All six jobs therefore share
one mutex even when invoked from different processes or entry points.

### 1.3 Each entry point owns exactly one canonical row

`run_job()` remains the API/job telemetry owner. It creates one canonical
`fetch_*` row, calls `execute_macro_job()`, and finishes that same row. Lock
busy is a failed terminal row with stable error `macro_calendar_busy`; the
existing `JobState` vocabulary is not widened with a fake fourth status.

`SourceDef` gains a nullable canonical backend-job field and a
`writes_macro_db` flag. For a macro source, `run_source()`:

1. completes same-source process/file-lock gates; a busy gate is not an
   attempt and creates no row;
2. advances the source's attempt time and creates one row whose name is the
   source's canonical `fetch_*` name;
3. runs provider/config preflight inside that attempt; a missing configuration
   finishes the row failed, performs zero provider work, and waits its normal
   source interval before another automatic attempt;
4. calls `execute_macro_job()` directly, never `run_job()`;
5. records successful/failed durable scheduler state; and
6. maps `MacroCalendarBusy` to a visible scheduler `status="skipped"` result
   while finishing the already-created canonical job row as non-success.

No `collect.fred_*` or `collect.finnhub_*_calendar` job name may be emitted.
The existing news/price/SEC source names remain `collect.*` byte-for-behavior
unchanged.

### 1.4 Exact source registry and tick arbitration

Add these entries, in this order after existing sources:

| Source | Canonical job | Provider | Default | Group |
|---|---|---|---:|---|
| `fred_series` | `fetch_fred_series` | `fred` | 1,440 | macro writer |
| `fred_release_dates` | `fetch_fred_release_dates` | `fred` | 10,080 | macro writer |
| `finnhub_economic_calendar` | `fetch_economic_calendar_recent` | `finnhub` | 60 | macro writer |
| `finnhub_earnings_calendar` | `fetch_earnings_calendar` | `finnhub` | 240 | macro writer |
| `finnhub_ipo_calendar` | `fetch_ipo_calendar` | `finnhub` | 1,440 | macro writer |

Descriptions and badges state provider, destination `macro_calendar.db`, and
incremental/recent scope without promising provider publication freshness.
`provider_fetch` is true for all five.

`tick_once()` tracks market and macro writer groups independently. It may fire
one member of each group in one tick. After one macro writer is selected,
additional due macro sources are simply deferred: no thread, no `_record_result`,
no `_LAST_ATTEMPT` update, and no job row. Registry order supplies deterministic
fairness only within a single tick; subsequent due sources remain eligible.

The backfill job is absent from `SOURCES`, `/schedule`, Settings rows, and the
routine run-now path. Scheduled FRED series calls use default
`full_refresh=False`; no schedule payload may override it.

### 1.5 Automation truth comes from schedule rows

Remove `auto_refresh_enabled` from `/macro/snapshot` and from the frontend
`MacroSnapshot` DTO. The snapshot remains pure stored-data truth.

Add a no-create schedule projection that reads the two FRED and three Finnhub
calendar settings. Provider health uses it as follows:

- FRED `signals.auto_refresh_enabled` is true iff either FRED source is enabled;
- FRED detail reports the enabled source count, not the legacy flag;
- Finnhub's existing news health remains unchanged, but its signals may expose
  a separate `calendar_auto_refresh_enabled` boolean derived from its three
  schedule rows; and
- a schedule read failure produces unknown, never enabled.

`macro_calendar_enabled` continues to gate the existing agent/job routes. This
task does not delete or rename the setting.

### 1.6 One frontend schedule controller and table

Create `dataScheduleControls.tsx` with one hook and one presentational table:

```text
useDataScheduleControls(settingsReadCache)
DataScheduleTable({ sourceIds, controller, ...copy })
```

The hook owns retained cache inspection, one GET load, active/idle polling,
focus revalidation, stale-response sequence rejection, mutation busy state,
draft intervals, and run-now lifecycle observation. The table owns the five
stable columns and accepts an ordered source-ID filter. Unknown requested IDs
render no fabricated row and produce a typed local error in developer evidence.

`DataSourcesSection` delegates its existing schedule block to this owner and
continues to render every source. `MacroStorageSection` passes the exact five
macro IDs. Active-only Settings mounting means only the visible section owns a
polling subscription; the shared cache still coalesces any overlapping GET.

Mutation rules:

- enable/interval: invalidate `data_schedule` and `provider_health`, then GET;
- run-now acceptance: invalidate only `data_schedule`, then poll;
- terminal success: invalidate the exact stored-data keys in §1.7;
- failed/skipped/busy: preserve stored macro status/snapshot truth; and
- unmount: cancel timers/listeners and reject late state writes.

The old test ID saying `all_four_schedule_rows` is renamed atomically to
`all_schedule_rows`; retaining the false name to preserve a hash is forbidden.

### 1.7 Exact macro invalidation and copy

Extend `invalidateDataSource()`:

```text
fred_series                 -> macro_status + macro_snapshot
fred_release_dates          -> macro_status
finnhub_economic_calendar   -> macro_status
finnhub_earnings_calendar   -> macro_status
finnhub_ipo_calendar        -> macro_status
unknown future macro source -> macro_status + macro_snapshot (fail closed)
```

Existing price/news/SEC mappings remain unchanged. A wholly unknown non-macro
source retains the current broad fail-safe.

The Macro page shows the actual enabled count from the five schedule rows and
keeps `重新讀取狀態` visibly separate from `立即更新`. Traditional Chinese uses
`擷取` or `更新`, never `攝入`; English explicitly says `run manually` where
appropriate. Stored observation dates, fetch receipt times, scheduler outcomes,
and automation state remain distinct labels.

---

## 2. Test-node ledger

### 2.1 Backend additions

All 18 nodes are new in
`tests/test_macro_scheduler_integration.py`; none exists in the baseline.
Their sorted stream is
`f1d61ada812ddb731096e0203bfda02594c4c706dabb31e8ad7f669c71621843`.

Task 1 adds these eight lock/execution nodes:

```text
test_all_six_macro_jobs_share_one_writer_lock
test_direct_job_failure_records_one_failed_canonical_row
test_direct_job_uses_shared_execution_and_records_one_canonical_row
test_macro_lock_busy_records_one_non_success_row_without_provider_work
test_macro_writer_lock_releases_descriptors_after_success_and_failure
test_macro_writer_lock_serializes_two_real_processes
test_schedule_failure_records_one_failed_canonical_row
test_schedule_uses_shared_execution_and_records_one_canonical_row
```

Their full node IDs are prefixed by
`tests/test_macro_scheduler_integration.py::`; the sorted eight-row SHA is
`ac8cab8ee243e119202b1315aab8274b397b0e7c6739bf197cba2b23ab1e2855`.

Task 2 adds the remaining ten:

```text
test_backfill_job_is_not_a_recurring_schedule_source
test_fred_series_schedule_is_incremental_and_cannot_request_full_refresh
test_interrupted_macro_state_is_not_reconciled_as_success
test_macro_and_market_writer_groups_may_fire_in_the_same_tick
test_macro_source_registry_has_exact_ids_jobs_providers_and_defaults
test_macro_sources_default_disabled_while_manual_run_remains_available
test_missing_provider_config_fails_before_shared_execution
test_schedule_reads_do_not_create_macro_calendar_database
test_scheduler_deferral_keeps_other_macro_sources_due_without_success
test_scheduler_fires_at_most_one_due_macro_writer_per_tick
```

### 2.2 Frontend additions and truthful rename

Task 3 adds eight `Data schedule controls` nodes plus the truthful replacement
for the existing `all_four_schedule_rows` node. Task 4 adds four
`MacroStorageSection` nodes. The final ledger is `+13/-1`, net `+12`:

```text
ADD src/SettingsProviderConfig.test.ts
  Settings provider config authority > renders_disabled_providers_as_neutral_and_all_schedule_rows_as_controllable

REMOVE src/SettingsProviderConfig.test.ts
  Settings provider config authority > renders_disabled_providers_as_neutral_and_all_four_schedule_rows_as_controllable

ADD src/settings/dataScheduleControls.test.tsx
  Data schedule controls > shares one schedule read across visible consumers
  Data schedule controls > filters rows without changing registry truth
  Data schedule controls > manual run sends exactly one POST and follows terminal state
  Data schedule controls > enable and interval mutations invalidate the shared schedule key
  Data schedule controls > successful macro sources invalidate exact stored data keys
  Data schedule controls > failed skipped and busy macro runs do not invalidate stored data keys
  Data schedule controls > unknown macro source fails closed to both macro keys
  Data schedule controls > mount focus visibility and local status reload send zero POSTs

ADD src/settings/MacroStorageSection.test.tsx
  MacroStorageSection > renders five macro schedule rows with the actual enabled count
  MacroStorageSection > labels local status reload separately from provider updates
  MacroStorageSection > keeps failed and busy runs visible without rewriting stored timestamps
  MacroStorageSection > renders bilingual manual update copy without ingestion wording
```

The 13-row add stream SHA is
`cadebef997c772368887a12795abdd473471885513bcb2c73b702f6aa8bc1508`;
the one-row removal SHA is
`9d9b80d2292f444e63c6a5ec995357821e43591bfa73ef6f52d5f41f942f2110`.

### 2.3 Staged identities

| Stage | Full backend | Focused backend | Full frontend | Focused frontend |
|---|---|---|---|---|
| base | `4,341 / 883b1148...` | `375 / 1c3ce4ac...` | `99 files / 1,159 / f19472dd...` | `88 / 9b9d488a...` |
| Task 1 | `4,349 / 372fe6ab...` | `383 / de8eb8c4...` | unchanged | unchanged |
| Task 2 | `4,359 / c100ee5d...` | `393 / 0dd72ab8...` | unchanged | unchanged |
| Task 3 | unchanged | unchanged | `100 files / 1,167 / c13764c5...` | `96 / 969b26ef...` |
| Task 4 final | `4,359 / c100ee5d...` | `393 / 0dd72ab8...` | `100 files / 1,171 / 9b2691e6...` | `100 / 8d067ab7...` |

Full hashes:

```text
Task 1 backend full
372fe6ab268fabd0d0bbb66dd26f93fb7f684d63ad19885c3d587bfefa50c340
Task 1 backend focused
de8eb8c4e4549deb7a7b66e9a2dd6e51049106f9a76a8ddd4287c98f4050eeb0
Task 2/final backend full
c100ee5de4ad42c490e6048e4b7cf22540e417f579987c676796663608d17afd
Task 2/final backend focused
0dd72ab8e64fa0f8324c441b67ad65a10d886692dc41c0d2d487b403aac6a5d5
Task 3 frontend full
c13764c5e4a4eb12f927a2ad51d2223e1365ffc8e7bcf1373d686b2b87a0720b
Task 3 frontend focused
969b26efa0c4df47ec73db004c9a87547fe8f2320d404e4c4ef7b7dbbff2c843
Task 4/final frontend full
9b2691e6946921f8571ffa0a32efd4f908d1be9f8c549dbbbfc85aa63de4d4c1
Task 4/final frontend focused
8d067ab7142e8fe1e80933292818bf4a6e2fb023e3ae98343ad4b4caabac7a89
```

### 2.4 Existing-node evolution boundary

Only assertions required by the approved contract may evolve. Expected
owners include:

```text
tests/test_data_scheduler.py::test_defaults_everything_disabled
tests/test_data_scheduler.py::test_no_active_runtime_source_uses_migrate_to_supabase_sync
tests/test_data_scheduler.py::test_scheduler_source_defs_have_no_legacy_collector_plumbing
tests/test_data_scheduler.py::test_get_schedule_snapshot_shape
tests/test_data_scheduler.py::test_schedule_status_exposes_post_pg_exit_presentation_metadata
tests/test_provider_health.py::test_no_signal_when_nothing_recorded
tests/test_provider_health.py::test_fred_snapshot_available_when_refresh_is_off
tests/test_provider_health.py::test_fred_refresh_off_without_snapshot_is_no_signal
tests/test_macro_calendar_read.py::TestMacroSeriesRoute::test_snapshot_readable_when_refresh_disabled
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx::MacroStorageSection > keeps_stored_data_neutral_when_ingestion_is_disabled
apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > does_not_request_or_render_the_detailed_fred_snapshot
```

The exact `-1/+1` rename in §2.2 is separate. Editing a fourth existing backend
owner family or a second existing frontend node beyond grounded necessity is a
stop-and-amend event. Frozen Settings baseline blocks and unrelated count
fixtures are not updated to follow current copy.

### 2.5 Backend focused command

```bash
pytest -q \
  tests/test_data_scheduler.py \
  tests/test_job_runs.py \
  tests/test_service_api_slice.py \
  tests/test_fred_ingestion.py \
  tests/test_finnhub_ingestion.py \
  tests/test_macro_calendar_health.py \
  tests/test_macro_calendar_read.py \
  tests/test_provider_health.py \
  tests/test_macro_calendar_settings_route.py \
  tests/test_macro_scheduler_integration.py
```

Baseline focused identity excludes the new file and is `375`; final is `393`.

### 2.6 Frontend focused command

From `apps/arkscope-web`:

```bash
npx vitest run \
  src/SettingsProviderConfig.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/settings/MacroStorageSection.test.tsx \
  src/settings/settingsReadCache.test.ts \
  src/settings/dataScheduleControls.test.tsx \
  src/i18n/resources.test.ts
```

Baseline identity excludes the new file and is `88`; final is `100`.

---

## 3. RED-first task sequence

### Task 0 - Re-ground and protect

1. Verify the approved design bytes, this plan-gate commit, tool hashes, clean
   worktree, and no product drift from `bdd8fc30`.
2. Recollect the four base streams and compare exact bytes to §0.4.
3. Run both focused baselines with no network and record exact commands,
   transcripts, and environment.
4. Record the native baseline/control result and report SHA.
5. Build an owned-path manifest and a protected manifest for every tracked
   product/test path outside §0.2.
6. Create docs-only evidence and stop for review.

No RED test or product edit belongs in Task 0.

### Task 1 - Shared execution and lock

1. Add the eight Task 1 nodes and collect the exact stage identity.
2. Run only those nodes. Legal RED is missing module/symbol or observed double
   telemetry/unlocked concurrency. Collection error from importing a partially
   written existing module is wrong RED.
3. Add `write_lock.py` and `execution.py`, then delegate both entry points.
4. Run the eight nodes, existing FRED/Finnhub dispatcher owners, `test_job_runs`,
   and final Task 1 focused suite.
5. Prove two actual processes cannot enter the critical section together and
   `/proc/self/fd` returns to baseline after success and failure.
6. Commit product/tests, then evidence/docs; stop for review.

### Task 2 - Registry, tick arbitration, and automation truth

1. Add the ten Task 2 nodes and collect `4,359 / c100ee5d...` before product
   edits.
2. Run the ten nodes RED; exact expected causes are missing source definitions,
   missing macro-group arbitration/backoff, legacy snapshot flag, or absent
   no-create projection.
3. Add the five sources, canonical job names, provider maps, defaults, and
   independent macro tick group.
4. Remove the snapshot false-authority field and derive provider automation
   from no-create schedule reads.
5. Run final backend focused tests plus no-create filesystem snapshots.
6. Commit product/tests and evidence/docs; stop for review.

### Task 3 - Shared frontend controller

1. Add the eight controller nodes and atomic truthful test rename. Collect
   `1,167 / c13764c5...`; the removed old ID must be absent exactly once.
2. Run RED: the new module is absent, Data Sources still owns the controller,
   immediate broad invalidation is observable, and the old false test name is
   gone.
3. Extract the hook/table; migrate Data Sources without changing its source set,
   polling cadence, provider controls, or SA owner.
4. Add exact macro cache mappings and preserve all existing price/news/SEC
   mappings.
5. Run 96 focused nodes, typecheck, and i18n scanner; commit pair and stop for
   review.

### Task 4 - Macro page controls and copy

1. Add the four Macro page nodes and collect final frontend identity.
2. Run them RED: no macro rows, false legacy auto label, or ambiguous local
   refresh copy must be the causes.
3. Mount the filtered shared table, derive enabled count, remove the legacy DTO
   field, and add reviewed bilingual copy.
4. Run 100 focused nodes, full frontend, typecheck, build, scanner, and an early
   desktop/mobile browser check.
5. Commit pair and stop for review.

### Task 5 - Mutations and final admission

Run each mutation from the same clean Task 4 tip, require the named owner to
turn RED, and restore the entire owner file byte-for-byte before continuing:

| ID | Minimal live mutation | Owning evidence |
|---|---|---|
| M1 | call `run_job()` from scheduler macro branch | one canonical row nodes |
| M2 | bypass the macro file lock on one Finnhub job | real two-process lock node |
| M3 | mark a deferred second macro source as attempted/successful | due-without-success node |
| M4 | allow schedule FRED payload to set `full_refresh=True` | incremental-only node |
| M5 | derive FRED automation from `macro_calendar_enabled` | provider-health evolved owners |
| M6 | invalidate macro snapshot on failed/busy run | frontend failure-preservation node |
| M7 | send run-now POST on mount/focus/local reload | frontend zero-POST node |

A mutation that edits dead code, is killed only by a source-string assertion,
or leaves its semantic owner GREEN is rejected evidence.

Final gates:

1. backend full collection `4,359 / c100ee5d...`;
2. backend focused `393` passing;
3. frontend full `100 files / 1,171 / 9b2691e6...`;
4. frontend focused `100` passing;
5. frontend full runtime, typecheck, build, and i18n scanner;
6. canonical native backend target = `4,359 seen / 4,347 passed / 12 skipped /
   0 failed / exit 0` (the exact `4,329/12/0` baseline plus 18 passing nodes);
7. hermetic scratch `macro_calendar.db`: one representative success updates
   expected rows and a subsequent provider failure leaves them unchanged;
8. two-process lock and descriptor-release probes;
9. desktop `1322 x 777` and mobile `390 x 844` browser matrix: five rows,
   bounded layout, zero overlap, zero POST before explicit click, exactly one
   POST after click, and honest terminal state; and
10. artifact manifest, generated-file cleanup, production DB/config SHA and
    stat equality, and clean worktree.

Stop for full implementation review. No merge is authorized by Task 5.

### Task 6 - Merge and exact-master verification

After independent implementation GREEN:

1. prove the implementation base is an ancestor of current master;
2. fast-forward only, no push;
3. create a fresh exact-master worktree and rerun final collections, focused
   suites, frontend full/typecheck/build/scanner, native admission, lock probe,
   scratch DB proof, and browser matrix under new artifact names;
4. write docs-only closeout and stop for focused review.

---

## 4. Stop conditions

Stop before further product edits if any of the following occurs:

1. a staged collection count or SHA differs;
2. any node outside the `+18/-0` backend or `+13/-1` frontend ledger changes;
3. a second telemetry row appears for one attempt;
4. any scheduled macro row uses a `collect.*` identity;
5. lock setup degrades to unlocked execution;
6. a lock descriptor survives any terminal path;
7. the second due macro source is marked attempted, skipped-success, or no
   longer due merely because another macro source fired this tick;
8. a fired macro source with missing provider configuration remains due on the
   next 30-second tick or prevents another due macro source from being selected;
9. backfill becomes reachable from Settings or `SOURCES`;
10. Settings can request `full_refresh=True`;
11. `macro_calendar_enabled` still drives any automation label;
12. mount, focus, visibility, idle warmup, or local status refresh sends a POST;
13. failed/busy execution invalidates or rewrites stored freshness;
14. provider request shape, ingestion/upsert formula, catalog, or date window
    changes outside the moved shared body;
15. production `macro_calendar.db`, `profile_state.db`, provider config, secret,
    or schedule setting changes during ordinary tests;
16. a frontend copy introduces `攝入` or implies automatic/manual capability
    that the controls do not have;
17. a frozen Settings baseline/count block is updated to follow current copy;
18. an unowned path changes;
19. a deterministic browser overlap, overflow, duplicate POST, or stale-state
    regression appears;
20. a test contacts FRED/Finnhub or a live sidecar; or
21. a reviewer cannot rebuild an asserted identity from raw artifacts.

Any stop requires a bounded amendment and independent focused review. Do not
weaken a test, widen an allowlist, or preserve a false test name to keep the
original hash.

---

## 5. Commit shape

Each task uses two commits:

```text
test/feat: <bounded task product and RED-first tests>
docs: record macro scheduler task <n> evidence
```

Task 0 and final closeout are docs-only. Do not squash task commits before
review; the per-stage ancestry and RED/GREEN artifacts are part of the review
surface. No push occurs without a separate user instruction.
