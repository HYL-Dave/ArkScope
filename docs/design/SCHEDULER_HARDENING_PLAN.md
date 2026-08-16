# Scheduler Runtime Contract

- **Status:** current architecture authority
- **Updated:** 2026-08-16

## Purpose

The in-app scheduler turns provider-specific collection functions into bounded,
observable, restart-safe operations. It separates four concerns:

- cadence decides when a source may run;
- coverage and continuation decide what work remains;
- domain locks protect single-writer resources;
- local state and run telemetry explain the latest outcome.

## Source Registry

`src/service/data_scheduler.py` owns the closed `SourceDef` registry. Each source
declares its identifier, label, interval, execution adapter, provider key, and
write target. Settings reads this projection; it must not maintain a second source
list.

Automatic schedules are opt-in. An interval is both cadence and retry backoff. A
manual run does not silently consume the next scheduled interval when it cannot
start.

## Durable State

`SchedulerStateStore` owns one row per source in `data/profile_state.db`:

- `last_attempt` records a genuine run start;
- `last_status` records `running`, `succeeded`, `failed`, `skipped`, or `partial`;
- `last_error` is cleared by a later success;
- `continuation` holds bounded remaining work;
- `last_result` supports the Settings status projection.

Startup seeds cadence from this table, then fills only missing sources from the
local job-run history. It performs no network probe. Rows left `running` by a dead
process are terminalized before normal scheduling resumes.

Pure status reads use no-create helpers. They return honest empty state when the
file or table does not exist and never materialize storage as a side effect.

## Execution And Locks

Scheduled and attended runs share `run_source` and the same domain execution
functions. Provider calls are not duplicated in route handlers or UI adapters.

- IBKR consumers share the gateway lock.
- Macro sources share the fail-closed macro writer lease.
- A lease is exact-owner, single-use, and cannot be reused across a process or
  thread boundary.
- A scheduler collision is deferred before attempt state or run-row creation.
- An attended collision returns a visible typed terminal result without provider
  work and without advancing scheduled cadence.

Lock acquisition failures must remain visible. Running unlocked is not an
admitted fallback.

## Bounded Work And Continuation

Domains with a coverage oracle may shape a run around known gaps. A bounded run
that cannot finish stores `partial` plus a sanitized continuation. The scheduler
does not automatically consume attended continuations; Settings exposes an
explicit continuation action.

A retry preserves the prior continuation until replacement work succeeds. A
failed retry must not silently clear the remaining scope or leave the source stuck
as `running`.

## Settings Projection

The schedule endpoint projects registry truth, durable state, and admitted job
facts. One group-scoped frontend controller owns polling, focus revalidation,
single-flight reads, drafts, and explicit run commands. Multiple visible tables
filter that shared projection by `write_target`.

Mount, focus, visibility, idle warmup, and local reload are GET-only. Provider work
requires an explicit user action or an enabled scheduler tick.

## Verification Contract

Changes to scheduler ownership must prove:

1. startup with the scheduler enabled in an isolated local runtime;
2. dynamic route and source census rather than a hand-maintained allowlist;
3. restart continuity from local state and local job history;
4. one controller and one polling request for all visible schedule consumers;
5. true lock contention for scheduler and attended paths;
6. typed failure with no provider work when a lock or preflight gate rejects;
7. no production asset changes during hermetic admission.

New queues, background services, automatic continuation, or new product surfaces
require separate design approval.
