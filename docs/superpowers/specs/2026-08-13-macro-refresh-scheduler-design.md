# Macro Data Refresh and Scheduler Integration Design

> **Status:** DRAFT; USER REVIEW REQUIRED; IMPLEMENTATION NOT AUTHORIZED
>
> **Date:** 2026-08-13
>
> **Grounding base:** `bea5890f`
>
> **Scope:** connect the existing FRED and Finnhub macro-calendar collectors to
> ArkScope's one app-owned scheduler, expose honest automatic/manual controls,
> and refresh the existing local `macro_calendar.db`. This unit does not add a
> provider, change research semantics, or perform an unbounded historical
> backfill.

## 1. Problem

The Macro Data page showed FRED rows last fetched on 2026-06-25. The page has a
button labeled `重新讀取狀態`, but that button only re-reads local status and
snapshot APIs. It intentionally makes no provider request.

The product already contains incremental collectors and backend jobs for FRED
series, FRED release dates, Finnhub economic events, earnings events, and IPO
events. None of those five recurring jobs is registered in
`src/service/data_scheduler.py::SOURCES`, and production `job_runs` contains no
FRED execution. `macro_calendar_enabled=false` is currently shown as if it
were an automatic-refresh state even though it is a feature gate, not proof
that any app schedule exists.

The supplied screenshot is:

| Screenshot | Size | SHA-256 |
|---|---:|---|
| `Screenshot from 2026-08-12 23-36-09.png` | 1132 x 361 | `9562687e04ca91bd971c4ca53790aee60c06c7253fea375fb7b300d39b0efd6e` |

## 2. Grounded capability

The current local database contains:

| Table | Rows | Latest fetch at observation time |
|---|---:|---|
| `macro_series` | 11 | 2026-06-25 |
| `macro_observations` | 29,571 | 2026-06-25 |
| `macro_release_dates` | 4,659 | 2026-06-24 |
| `cal_economic_events` | 0 | none |
| `cal_earnings_events` | 0 | none |
| `cal_ipo_events` | 86 | 2026-06-24 |

The existing implementations already provide:

- FRED series incremental refresh with a bounded recent window by default;
- FRED release-date refresh for the curated release catalog;
- recent Finnhub economic-calendar refresh;
- Finnhub earnings and IPO refresh;
- read-only local table coverage and curated FRED snapshot APIs; and
- job telemetry with expected cadences of hourly, four-hourly, daily, or
  weekly according to source.

All six tables live in the same `macro_calendar.db`. SQLite has a busy timeout,
but independent jobs can still contend or produce confusing concurrent run
states. Schedule integration must therefore serialize the shared write
resource across UI, scheduler, and backend-job entry points.

## 3. Alternatives

### A. Add manual provider buttons only

Call the existing `/jobs/run/*` routes from the Macro page and leave
automation disconnected.

Rejected. It fixes today's stale snapshot only when the user remembers to
click and leaves the existing cadence policy unenforced.

### B. Register macro sources in the existing app scheduler

Reuse the existing per-source enable/interval/run-now authority, share one
execution body with existing backend jobs, and serialize all
`macro_calendar.db` writers.

Selected. It gives one schedule state, one job record per attempt, and one
manual execution path.

### C. Add a macro-specific background loop or operating-system cron

Rejected. A second cadence owner would drift from Settings, duplicate locks
and telemetry, and make `auto refresh` impossible to state honestly.

## 4. Locked decisions

### LD 1 - One scheduler authority

Add these source IDs to the existing `SOURCES` registry:

| Source ID | Provider | Existing job authority | Default interval |
|---|---|---|---:|
| `fred_series` | FRED | `fetch_fred_series` | 1,440 min |
| `fred_release_dates` | FRED | `fetch_fred_release_dates` | 10,080 min |
| `finnhub_economic_calendar` | Finnhub | `fetch_economic_calendar_recent` | 60 min |
| `finnhub_earnings_calendar` | Finnhub | `fetch_earnings_calendar` | 240 min |
| `finnhub_ipo_calendar` | Finnhub | `fetch_ipo_calendar` | 1,440 min |

Every source is opt-in and disabled until the user enables it. Manual
`立即更新` remains available while automatic scheduling is disabled, provided
the provider configuration and write gate are valid.

The one-shot `fetch_economic_calendar_backfill` job is not a recurring source
and is not exposed as a routine Settings action.

### LD 2 - Existing collectors remain the domain owners

No ingestion formula, provider request shape, catalog, date window, upsert, or
revision rule is duplicated in the scheduler.

Refactor the existing job dispatch into one side-effect body callable by both:

- the generic backend job API; and
- `data_scheduler.run_source()` for a source whose registry entry names that
  backend job.

The wrapper owns schedule state and exactly one `job_runs` record. A scheduled
run uses the canonical existing job name (`fetch_fred_series`, etc.) so macro
health and history do not split between `fetch_*` and `collect.*` identities.
Nested telemetry rows are forbidden.

### LD 3 - `macro_calendar.db` has one cross-entry-point writer lock

All five recurring jobs and the existing one-shot economic backfill use one
named in-process plus cross-process lock for `macro_calendar.db`.

- The lock covers the complete provider-read/write operation.
- API, manual schedule, automatic schedule, and CLI/job entry points share it.
- Busy acquisition returns a typed `macro_calendar_busy` skip/failure result;
  it never silently runs unlocked.
- The scheduler starts at most one due macro writer per tick. Other due macro
  sources remain due and may run on a later tick; deferral is not recorded as
  a successful attempt.
- Lock release is proven on success, provider failure, validation failure, and
  cancellation/exception paths.

This lock is separate from the `market_data.db` writer group. A macro write and
a market-data write may run concurrently because they do not share a database.

### LD 4 - Per-source schedule settings are automation truth

`schedule.<source>.enabled` and `schedule.<source>.interval_minutes` are the
only App automation authority for these five sources.

`macro_calendar_enabled` remains a legacy capability gate for agent/job
surfaces until a separate configuration cleanup decides its final schema. It
must no longer be rendered or serialized as `auto_refresh_enabled`, and it
must not override a per-source schedule setting.

This correction applies to both current consumers of the misleading flag:

- `/macro/snapshot`; and
- the FRED row in provider health.

Provider health derives FRED automation from the `fred_series` and
`fred_release_dates` schedule rows, while stored coverage continues to come
from `macro_calendar.db`. Enabling either schedule may make the FRED row say
automatic updates are enabled; the legacy flag cannot. Finnhub provider health
likewise must not imply that its three calendar sources are scheduled merely
because the legacy macro capability flag is true.

The Macro page derives automatic status from the actual five schedule rows:

- all disabled -> `自動更新未啟用`;
- one or more enabled -> state the enabled count; and
- unavailable schedule read -> `自動更新狀態未知`.

Absence is never converted to enabled or successful.

### LD 5 - One reusable control surface

Extract the current schedule-row behavior into a reusable Settings component
or hook. The Data Sources page renders all source IDs; the Macro page renders
the five macro source IDs. Both surfaces use the same API calls, cache key,
validation, cooldown, progress, and invalidation logic.

Each macro row shows:

- source label and provider;
- automatic enable toggle;
- interval in minutes with the reviewed default;
- `立即更新` button;
- running state or last terminal result; and
- last attempt/success/error timestamps already supplied by schedule state.

`重新讀取狀態` remains a local-only GET action and is renamed or accompanied
by copy that says it does not contact a provider. It cannot masquerade as a
data update.

Traditional Chinese uses `擷取` or `更新`, not `攝入`. English manual-action
copy says `run manually` where that is the actual capability.

### LD 6 - Exact cache invalidation follows successful writes

On terminal success:

- `fred_series` invalidates `macro_status` and `macro_snapshot`;
- `fred_release_dates` invalidates `macro_status`;
- each Finnhub calendar source invalidates `macro_status`.

Failed, skipped, or busy runs update schedule status but do not claim that
stored macro data changed. Unknown future macro source IDs fail closed to both
macro keys until explicitly classified.

No provider request is made by page mount, idle warmup, focus, visibility, or
`重新讀取狀態`. Provider traffic occurs only when an enabled source becomes due
or the user presses `立即更新`.

### LD 7 - Cadence is policy, not freshness fabrication

The reviewed defaults are:

- economic events: hourly;
- earnings events: every four hours;
- IPO events: daily;
- FRED series: daily; and
- FRED release dates: weekly.

The displayed table timestamps remain provider/store receipt timestamps. A
recent scheduler success does not rewrite old FRED observation dates, and an
old observation date is not automatically a stale-fetch diagnosis. Health
uses `last_fetched_at` and job results for fetch freshness.

The normal FRED series action stays incremental. Full history/backfill remains
an explicit backend operation and is never triggered by the recurring
scheduler or routine UI button.

## 5. Failure and concurrency behavior

- Missing FRED/Finnhub configuration is a typed preflight failure with zero
  provider requests.
- A provider exception produces a failed terminal run and preserves existing
  rows.
- A partial provider result may be shown only if the underlying collector
  returns an authoritative partial result; the scheduler does not infer one.
- Concurrent clicks for the same source reuse existing same-source protection.
- Concurrent clicks for different macro sources are serialized by the shared
  database lock and return a visible busy outcome rather than queueing
  invisibly.
- Sidecar restart reconciliation must not convert an interrupted run into
  assumed success.

## 6. Verification contract

Backend tests must prove:

1. the five source definitions, provider mappings, canonical job names, and
   default cadences are exact;
2. all existing job and schedule entry points call the same execution body;
3. each attempt creates exactly one canonical telemetry row;
4. two real processes cannot write `macro_calendar.db` concurrently and the
   lock file descriptor is released on all terminal paths;
5. a scheduler tick fires at most one macro writer while preserving due state
   for the others;
6. disabled sources make zero automatic provider calls but still permit a
   manual run;
7. neither macro snapshot nor provider health reports
   `macro_calendar_enabled` as automatic schedule truth;
8. reads do not create or mutate `macro_calendar.db`; and
9. incremental FRED refresh remains the routine path while full refresh is not
   reachable from Settings.

Frontend tests must prove:

1. the Macro page distinguishes local status reload from provider update;
2. five schedule rows share the Data Sources control implementation;
3. mount, idle, focus, visibility, and local status refresh issue zero POSTs;
4. one explicit manual click issues exactly one POST for the selected source;
5. enabling a source updates the one shared schedule cache;
6. success invalidates only the required macro keys;
7. failed/busy runs remain visible and do not rewrite stored freshness; and
8. Traditional Chinese and English copy state automatic/manual capability
   without using `攝入`.

Browser verification uses desktop `1322 x 777` and mobile `390 x 844` and
checks that all controls fit, labels wrap without overlap, progress cannot
resize the table incoherently, and request ledgers contain no provider POST
before an explicit click or a controlled due-scheduler test.

A local fixture run must update representative rows in a scratch
`macro_calendar.db` and prove old rows survive a failed subsequent run. Any
live provider smoke is separately authorized, bounded, and redacted; it is not
part of ordinary canonical tests.

## 7. Out of scope

- provider selection or pricing evaluation;
- adding another FRED/Finnhub data product;
- unbounded FRED/ALFRED backfill;
- changing macro research calculations;
- deleting the legacy `macro_calendar_enabled` configuration field; and
- treating a schedule interval as proof that a provider published new data.
