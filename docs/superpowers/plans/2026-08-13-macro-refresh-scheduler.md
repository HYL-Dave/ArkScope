# Macro Refresh and Scheduler Integration Implementation Plan

> **Status:** PLAN GREEN AT `f9b69913`; TASKS 0-4 COMPLETE; TASK 5 FINAL
> PRODUCTION-EQUALITY GATE STOPPED; FOCUSED REVIEW REQUIRED; TASK 6 NOT
> AUTHORIZED
>
> **Date:** 2026-08-13
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-13-macro-refresh-scheduler-design.md`,
> user-approved at `bdd8fc30` and amended by the explicit user rulings recorded
> below. The amended design and this plan require one focused review together.
>
> **Product grounding base:**
> `bdd8fc30dd35ebcd9acc83efde3411b88ab18ed3` (docs-only over product tip
> `bea5890f`).
>
> **Roles:** Codex authors this plan and, after independent plan review,
> implements it RED-first. Fable independently reviews task evidence and
> product diffs. The user makes product and live-provider rulings.
>
> **2026-08-13 review amendment:** Fable's independent reconstruction found
> F1-F9 plus a shared-layout ownership gap. The user ruled that this line owns
> the layout fix, macro-writer occupancy defers before attempt creation, the SA
> line follows after this line, and Finnhub gains no new automation field. The
> corrected identities and exact owner deltas below supersede the initial plan
> values; Task 0 remains blocked on focused review of this amendment.
>
> **2026-08-13 focused-review amendment:** the first amendment omitted one
> deterministic post-PG Settings owner and left live FRED copy tied to the
> superseded no-schedule claim. This bounded correction owns that file, replaces
> its now-false calendar test ID, pins the exact value-only copy changes, and
> re-derives the affected frontend identities. Backend identities and the Task 3
> frontend stage remain unchanged.
>
> **2026-08-13 execution ruling:** focused re-review at `f9b69913` returned
> GREEN. The user then authorized Tasks 0-5 to run continuously on the happy
> path. Each task still requires its separate product/tests commit and
> evidence/docs commit, RED/GREEN artifacts, and exact staged identity. Every
> stop condition remains a hard stop requiring a bounded reviewed amendment.
> The per-task "stop for review" wording below is superseded only as to review
> timing: Task 5 remains the combined implementation-review gate, and Task 6,
> merge, push, and live-provider traffic remain unauthorized.
>
> **2026-08-13 Task 3 stop-and-amend:** implementation grounding proved that
> the macro-writer busy branch in `run_source()` does not distinguish automatic
> scheduler work from an attended `api`, `cli`, or `manual` invocation. The
> current branch gives every trigger a pure defer with no telemetry row and no
> `_LAST_RESULT`, contradicting the approved design's visible-busy contract for
> explicit actions. Automatic `scheduler` work keeps the existing pure-defer
> behavior. An attended busy invocation instead records exactly one failed
> canonical `fetch_*` row and publishes one transient `skipped` result with
> stable code/reason `macro_calendar_busy`, while leaving `_LAST_ATTEMPT` and
> durable scheduler state untouched so it cannot consume the automatic
> interval. The existing lock-busy owner gains this attended subcase; its node
> ID and every staged identity remain unchanged. Task 3 also strengthens its
> existing manual-run node so a successful run that completes before the first
> poll still invalidates exact macro cache keys by terminal revision rather
> than requiring an observed `running` frame. Product edits remain paused until
> this bounded amendment receives focused review.
>
> **2026-08-13 Task 3 resume:** focused review returned GREEN at `80e8498a`.
> Product/tests commit `9fea8f49` implements the trigger-scoped busy contract,
> shared frontend controller, exact cache invalidation, and fast-terminal
> revision handling. A final self-review also restored the pre-extraction
> cross-control busy boundary by passing provider-operation busy state into the
> shared schedule table; the existing Task 3 node caught the missing disabled
> state RED before the bounded fix. Backend and frontend staged identities
> remain exact. Task 4 is active under the existing batch ruling.
>
> **2026-08-13 Task 4 stop-and-amend:** the first Task 4 owner run reached the
> exact final collection but exposed one deterministic existing-node collateral.
> `renders English Macro Data status snapshot and table headings` selects every
> page-level `th`; after the reviewed schedule table mounts, it sees the five
> schedule headings before the five FRED headings and fails `1/14` while all six
> new Task 4 nodes and the post-PG replacement pass. The bounded correction may
> change only that assertion's selector from all `th` elements to
> `.settings-fred-table th`. Its expected five-heading array, node ID, body
> outside that selector, and every collection identity remain unchanged. Task 4
> product changes stay uncommitted and Tasks 4-5 are paused for focused review.

> **2026-08-13 Task 4 controller-ownership stop-and-amend:** after the reviewed
> heading selector correction, the final 109-node focused gate passed 104 and
> failed five deterministic existing `SettingsProviderConfig` nodes. The active
> `data_sync` tab mounts every section in its group, so `DataSourcesSection` and
> `MacroStorageSection` each instantiated `useDataScheduleControls`, installed
> independent timers/focus listeners, and produced two forced schedule GETs per
> poll. The prior `shares one schedule read across visible consumers` node saw
> only the initial in-flight cache coalescing and never advanced the polling
> clock, so it missed this ownership split. The same full-page fixture also saw
> ten Data Sources rows plus five Macro rows through an unscoped schedule-table
> selector. The bounded repair adds one `data_sync`-scoped controller provider,
> makes both sections consume that single owner, strengthens the existing shared
> read node across the first idle poll, and scopes the existing ten-row assertion
> to the `source_schedules` subsection. No node ID, count, or staged identity
> changes. Current product/test edits stay uncommitted; Tasks 4-5 are paused for
> focused review.

> **2026-08-14 Task 4 provider-fixture stop-and-amend:** the single-provider
> repair turned the authorized six discriminating nodes GREEN and the final
> focused gate passed `109/109`. The first full-suite run then exposed one
> deterministic collateral owner: `SettingsWorkspace.test.tsx` mocks every
> Settings loader with `{}`, so the newly real group provider receives no
> `sources` field and fails before eleven workspace nodes can exercise their
> own contracts. This is a stale fake, not a product DTO to tolerate. The
> bounded repair adds that test file as an owner and changes exactly its shared
> `getSchedule` fixture to `{ sources: {} }`; no test body, node ID, expected
> call count, or product behavior changes. The authorized shared-controller
> node also advances the 30-second clock synchronously and then flushes pending
> promises, avoiding a Vitest async-timer timeout without weakening its exact
> `1 -> 2` GET assertion. Current product/test edits stay uncommitted; Tasks 4-5
> remain paused for focused review.

> **2026-08-14 Task 4 browser-cascade stop-and-amend:** after the provider
> fixture correction, the focused `109/109`, post-PG `14/14`, typecheck,
> build, scanner, and one complete sequential full-suite `1172/1172` gate all
> passed. The required early real-browser check then found a deterministic
> rendered CSS defect: `.data-table td { white-space: nowrap; }` has greater
> specificity than `.settings-schedule-source-cell { white-space: normal; }`,
> so the latter rule is dead despite appearing later in the same stylesheet.
> Chrome reports `white-space: nowrap` on all five Macro source cells; the
> Finnhub economic and earnings rows have `scrollWidth 326/320` against
> `clientWidth 294`. The reviewed `30/11/12/12/35` columns, bounded table
> scroller, ten-source Data Sources registry, and five-source Macro filter are
> otherwise exact. The bounded repair changes only that selector to
> `.settings-schedule-table td.settings-schedule-source-cell`, preserving its
> declarations, and strengthens the already-added `wraps schedule source copy
> inside the source column` node to require this effective selector. No node
> ID, count, staged identity, or other product/test byte is authorized to
> change. Desktop and mobile computed-style replay must then prove normal
> wrapping with no cell overflow. Current product/test edits remain
> uncommitted; Tasks 4-5 stay paused for focused review. Partial packet:
> `/tmp/macro-refresh-scheduler-task4-stop4-83f881a0`, `12` payloads;
> `SHA256SUMS` SHA-256
> `f26131aa40557c89e39eb5dcbb8ade4645a5317c8d15d566ea463f29db9c5cf0`.

> **2026-08-14 Task 4 complete:** focused review returned GREEN at
> `6dc7b51c`. Product/tests commit `052c9134` implements the reviewed
> group-scoped controller, five Macro schedule rows, three-state automation
> truth, local-only status reload, bilingual copy, and bounded schedule-table
> layout. The specificity repair is exactly one selector replacement; its
> four declarations are unchanged. Desktop and mobile Chrome replay prove
> computed `white-space: normal`, wrapped long source descriptions, exact
> `30/11/12/12/35` columns, bounded table scrolling, zero page/main overflow,
> zero overlap, and GET-only fixture traffic. Final frontend identity is
> `101 files / 1,172 / d40a30d5...`; focused is `109/109`, the post-PG owner
> is `14/14`, and one sequential full command is `1,172/1,172`. Task 5 is
> active under the existing batch ruling. Task 6, merge, push, and live
> provider traffic remain unauthorized.

> **2026-08-14 Task 5 production-writer stop-and-amend:** M1-M9 restored
> their owners byte-for-byte, every backend/frontend identity and runtime gate
> matched, canonical native reached `4,347 passed / 12 skipped / 0 failed`, and
> the desktop/mobile browser matrix passed. Final whole-file production
> equality then stopped admission: `macro_calendar.db`, `config/.env`, and
> `config/user_profile.local.yaml` remained exact, while the active production
> `profile_state.db` gained rows during the run. Read-only evidence attributes
> the window to the already-running Desktop/sidecar: `job_runs` records the
> five-minute `sa_market_news_refresh` cadence plus one scheduled
> `collect.ibkr_news`, and their timestamps align with the production DB mtime.
> The native wrapper's own profile database is the separate file under its
> `/tmp/eir002-green-baseline/runtime/...` root. Attribution does not waive
> stop condition 15. Resume requires focused review, then a user-quiesced
> Desktop/sidecar writer window. Capture fresh full stat/SHA values for the
> four protected production assets, rerun the same canonical native command
> with the ignored `config/.env` visible only through a temporary symlink,
> remove that symlink, and require all four post values to equal the fresh pre
> values byte-for-byte. No product/test edit or frontend/browser rerun is
> authorized by this amendment. Any remaining writer process, production
> mismatch, or native identity drift is another stop. Partial Task 5 packet:
> `/tmp/macro-refresh-scheduler-task5-c286d504`, `140` payloads;
> `PARTIAL_SHA256SUMS` SHA-256
> `0d8127ec550b857b39a3164b796dc470e7a54696c33e2b17584cdae1efc01f23`.

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
apps/arkscope-web/src/Settings.tsx
new apps/arkscope-web/src/settings/dataScheduleControls.tsx
new apps/arkscope-web/src/settings/dataScheduleControls.test.tsx
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx
apps/arkscope-web/src/settings/settingsReadCache.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
apps/arkscope-web/src/SettingsWorkspace.test.tsx
apps/arkscope-web/src/SettingsCss.test.ts
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/i18n/resources.test.ts
apps/arkscope-web/src/settings/settings.css
apps/arkscope-web/src/styles.css
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

The plan author collected the backend suite with the pinned reporter and the
frontend suite with the pinned decoded normalizer. The focused suites and the
separate native control below were also executed:

| Stream | Baseline |
|---|---|
| backend full | `4,341 / 883b1148e8759ea8825ffd8b825db0339dc1e6ca5aefe4c04344b868b3ff1264` |
| backend focused, nine files in §2.5 | `375 / 1c3ce4accfe583b6c059d1c52414376cd1697f24ce8f968afbc844250bd9a1d5` |
| frontend full | `100 files / 1,159 / f19472dd04c73afd979d37f4c083ff8246a007816d58429a2c12295eaadc5e67` |
| frontend focused, six existing files in §2.6 | `96 / 9877be8adf0973c2b749f6460156ae86021cc4a91f3d4caab366bd9ce66da46f` |

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
`96 passed` frontend. Both are provider-free fixture suites.

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
   attempt time, do not write a success/skip row, and leave it due. That
   contract applies while a writer from an earlier tick or another process is
   still active, not only after selecting a writer in the current tick.
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
9. The schedule table inherits global cell `white-space: nowrap` and the old
   `22/10/16/16/36` fixed widths from `styles.css`. The Macro line owns the
   shared layout fix; the later SA line must inherit it rather than edit the
   same component/CSS in parallel.

---

## 1. Concrete implementation contract

### 1.1 Shared macro execution is telemetry-free

Create `src/macro_calendar/execution.py` with a closed dispatcher:

```text
MACRO_JOB_NAMES
execute_macro_job(job_name, dal, params, *, writer_lease=None) -> dict
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
MacroCalendarWriterLease
macro_calendar_writer(timeout_seconds=0.0) -> MacroCalendarWriterLease
```

The context manager acquires one process-local `threading.Lock` and one POSIX
`flock` at `ARKSCOPE_LOCK_DIR/macro_calendar_writer.lock` (falling back to the
directory returned by `src.ibkr_gateway_lock.lock_dir()` when the env override
is absent). It rejects symlinks, verifies a regular file, uses
close-on-exec/no-follow where available, and closes the descriptor on every
exit path. Failure to import `fcntl`, create or validate the lock file, or
acquire either layer raises the typed busy error; it never
logs-and-runs-unlocked.

`execute_macro_job()` normally acquires and holds this lock across the complete
provider read and SQLite write. The scheduler may instead pass the active lease
it acquired before attempt creation; the dispatcher validates that exact lease
and must not reacquire the non-reentrant lock. A missing, released, foreign, or
reused lease is rejected. No public unlocked execution function exists. All six
jobs therefore share one mutex even when invoked from different processes or
entry points, without a check-then-release race or a double-acquire deadlock.

### 1.3 Each entry point owns exactly one canonical row

`run_job()` remains the API/job telemetry owner. It creates one canonical
`fetch_*` row, calls `execute_macro_job()`, and finishes that same row. Lock
busy is a failed terminal row with stable error `macro_calendar_busy`; the
existing `JobState` vocabulary is not widened with a fake fourth status.

`SourceDef` gains a nullable canonical backend-job field and a
`writes_macro_db` flag. For a macro source, `run_source()`:

1. completes same-source process/file-lock gates; a busy gate is not an
   attempt and creates no row;
2. acquires/reserves the shared process-local and file macro-writer gate before
   advancing attempt time; for `trigger_source == "scheduler"`, an occupied
   gate is a pure defer with no row, no result, and no interval consumption,
   including when a writer from an earlier tick or another process is still
   running;
3. advances the source's attempt time and creates one row whose name is the
   source's canonical `fetch_*` name;
4. runs provider/config preflight inside that attempt; a missing configuration
   finishes the row failed, performs zero provider work, and waits its normal
   source interval before another automatic attempt;
5. calls `execute_macro_job()` directly under the reserved writer gate, never
   `run_job()`;
6. records successful/failed durable scheduler state; and
7. treats an unexpected post-reservation `MacroCalendarBusy` as a visible
   failed terminal attempt rather than fabricating success.

Direct API/job entry points still create one canonical row before attempting
the gate and may return typed `macro_calendar_busy`. An attended schedule
invocation (`api`, `cli`, or `manual`) that loses the shared writer race records
exactly one failed canonical row and one transient `_LAST_RESULT` with status
`skipped` and code/reason `macro_calendar_busy`; it performs no provider work
and does not update `_LAST_ATTEMPT` or durable scheduler state. The scheduler's
stronger pre-attempt deferral contract prevents a 30-second overlap from
consuming a daily or weekly source interval.

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
no `_LAST_ATTEMPT` update, and no job row. The selected source's worker thread
then acquires the shared writer lease inside `run_source()` before the attempt
boundary. If a writer from an earlier tick or another process still owns it,
that worker returns a pure scheduler defer, also without `_record_result`,
`_LAST_ATTEMPT`, or a row. Same-tick arbitration prevents a later source from
being launched in that pass; all remain due for the next tick. No lease crosses
from the supervisor thread into a worker thread.

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
- Finnhub's existing news health and DTO remain unchanged; this slice does not
  add `calendar_auto_refresh_enabled`; and
- a schedule read failure produces unknown, never enabled.

`macro_calendar_enabled` continues to gate the existing agent/job routes. This
task does not delete or rename the setting.

### 1.6 One frontend schedule controller and table

Create `dataScheduleControls.tsx` with one hook, one group-scoped provider, and
one presentational table:

```text
useDataScheduleControls(settingsReadCache)
DataScheduleControlsProvider({ settingsReadCache, children })
useSharedDataScheduleControls()
DataScheduleTable({ sourceIds, controller, ...copy })
```

The hook owns retained cache inspection, one GET load, active/idle polling,
focus revalidation, stale-response sequence rejection, mutation busy state,
draft intervals, and run-now lifecycle observation. The table owns the five
stable columns and accepts an ordered source-ID filter. Unknown requested IDs
render no fabricated row and produce a typed local error in developer evidence.
Macro invalidation classifies a future source from the schedule DTO's
`write_target == "macro_calendar.db"`; it does not hardcode the five current
source IDs as the domain boundary. The cache API therefore evolves to
`invalidateDataSource(source, writeTarget?)`. Existing callers may omit the
second argument and retain current behavior; the shared schedule controller
must pass the selected row's validated `write_target`.

The selected `data_sync` tab mounts all four sections in that group. `Settings`
therefore wraps those sections in exactly one `DataScheduleControlsProvider`;
the provider is absent while another Settings group is selected because `Tabs`
mounts only its selected panel. `DataSourcesSection` and `MacroStorageSection`
consume `useSharedDataScheduleControls()` and must not instantiate their own
hook, timer, focus listener, mutation guard, or draft state. Data Sources
continues to render every source and Macro passes the exact five macro IDs.
The cache may still coalesce overlapping non-controller reads, but cache
coalescing is not accepted as a substitute for single controller ownership.

Mutation rules:

- enable/interval: invalidate `data_schedule` and `provider_health`, then GET;
- run-now acceptance: invalidate only `data_schedule`, then poll;
- terminal success: invalidate the exact stored-data keys in §1.7;
- failed/skipped/busy: preserve stored macro status/snapshot truth; and
- unmount: cancel timers/listeners and reject late state writes.

The old test ID saying `all_four_schedule_rows` is replaced atomically by a
node that asserts every registered schedule row, including the existing
`sec_corporate_actions` row and the five new macro rows. Retaining a false name
or merely changing its string while preserving the four-row fixture is
forbidden.

### 1.7 Exact macro invalidation and copy

Extend `invalidateDataSource()`:

```text
fred_series                 -> macro_status + macro_snapshot
fred_release_dates          -> macro_status
finnhub_economic_calendar   -> macro_status
finnhub_earnings_calendar   -> macro_status
finnhub_ipo_calendar        -> macro_status
future source whose write_target is macro_calendar.db
                            -> macro_status + macro_snapshot (fail closed)
```

Existing price/news/SEC mappings remain unchanged. A wholly unknown non-macro
source retains the current broad fail-safe.

The extracted table adds a dedicated wrapping class to the source cell.
`styles.css` changes only the schedule-table source wrapping/alignment rules and
the five reviewed fixed widths from `22/10/16/16/36` to
`30/11/12/12/35`. The two new `SettingsCss` nodes own those static contracts;
desktop/mobile browser verification owns rendered overlap and horizontal
scroll behavior.

The Macro page shows the actual enabled count from the five schedule rows and
keeps `重新讀取狀態` visibly separate from `立即更新`. Traditional Chinese uses
`擷取` or `更新`, never `攝入`; English explicitly says `run manually` where
appropriate. Stored observation dates, fetch receipt times, scheduler outcomes,
and automation state remain distinct labels.

The reviewed `macroStorage.description` value is:

```text
zh-Hant
查看本地 FRED 序列快照、儲存量與事件資料覆蓋。可在下方設定五個資料來源的自動更新排程，或按「立即更新」手動執行；「重新讀取狀態」只會讀取本機資料，不會向資料供應商抓取資料。

en
Review local FRED series snapshots, stored volume, and event-data coverage. Configure automatic schedules for the five sources below or choose Run now for a manual update. Reload status reads local data only and does not contact a provider.
```

The live FRED provider-detail family is value-only and follows schedule truth:

```text
dataSources.fred.autoEnabled
  zh-Hant: App 自動更新已啟用
  en: App automatic updates enabled
dataSources.fred.autoDisabled
  zh-Hant: App 自動更新未啟用
  en: App automatic updates not enabled
dataSources.fred.autoUnknown
  zh-Hant: 無法確認 App 自動更新狀態
  en: App automatic update status unavailable
```

These four existing key paths change values only; they do not alter the i18n
key-count ledger. No Macro/FRED copy may retain `尚未接入 App 排程` after Task
2 makes the schedule rows authoritative; the independently true fundamentals
capability boundary is unchanged.

The bilingual schedule copy changes exactly these Settings paths:

```text
REMOVE macroStorage.snapshot.autoEnabled
REMOVE macroStorage.snapshot.autoDisabled
ADD    macroStorage.schedule.disabled
ADD    macroStorage.schedule.enabledCount_one
ADD    macroStorage.schedule.enabledCount_other
ADD    macroStorage.schedule.unknown
```

This is net `+2` keys per locale. The current Settings namespace count changes
`783 -> 785` and each locale total changes `1867 -> 1869`. The four additions
enter `postSliceSettingsPaths`; the two removals enter the reviewed retired-path
list so frozen pre-slice counts remain unchanged by formula rather than being
rewritten to current copy.

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

`test_scheduler_deferral_keeps_other_macro_sources_due_without_success` has
three parameterized phases under the same node ID: second due source in the
same tick, process-local writer still active on the next tick, and a file lock
held by a second real process. Every phase asserts no `_LAST_ATTEMPT` advance,
no job row, no result row, and continued due state. Replacing the file-lock
phase with a process-local fake is not equivalent.

### 2.2 Frontend additions and truthful rename

Task 3 adds eight `Data schedule controls` nodes plus the truthful replacement
for the existing `all_four_schedule_rows` node. Task 4 adds four
`MacroStorageSection` nodes, two CSS contract nodes, and a truthful replacement
for the post-PG macro-copy node. The old
`keeps_stored_data_neutral_when_ingestion_is_disabled` node also leaves because
the retired snapshot flag no longer owns automation truth. The final ledger is
`+16/-3`, net `+13`:

```text
ADD src/SettingsProviderConfig.test.ts
  Settings provider config authority > renders_disabled_providers_as_neutral_and_every_registered_schedule_row_as_controllable

REMOVE src/SettingsProviderConfig.test.ts
  Settings provider config authority > renders_disabled_providers_as_neutral_and_all_four_schedule_rows_as_controllable

ADD src/SettingsPostPgExitStorage.test.ts
  post-PG-exit storage panels > shows_macro_data_with_manual_and_scheduled_refresh_boundaries

REMOVE src/SettingsPostPgExitStorage.test.ts
  post-PG-exit storage panels > shows_total_macro_data_without_claiming_calendar_product

ADD src/SettingsCss.test.ts
  Settings workspace CSS contract > allocates reviewed schedule columns without overlapping controls
  Settings workspace CSS contract > wraps schedule source copy inside the source column

ADD src/settings/dataScheduleControls.test.tsx
  Data schedule controls > shares one schedule read across visible consumers
  Data schedule controls > filters rows without changing registry truth
  Data schedule controls > manual run sends exactly one POST and follows terminal state
  Data schedule controls > enable and interval mutations invalidate the shared schedule key
  Data schedule controls > successful macro sources invalidate exact stored data keys
  Data schedule controls > failed skipped and busy macro runs do not invalidate stored data keys
  Data schedule controls > classifies future macro sources by write target and fails closed to both macro keys
  Data schedule controls > mount idle focus visibility and local status reload send zero POSTs

ADD src/settings/MacroStorageSection.test.tsx
  MacroStorageSection > renders five macro schedule rows and all three automation states
  MacroStorageSection > labels local status reload separately from provider updates
  MacroStorageSection > keeps failed and busy runs visible without rewriting stored timestamps
  MacroStorageSection > renders bilingual manual update copy without ingestion wording

REMOVE src/settings/MacroStorageSection.test.tsx
  MacroStorageSection > keeps_stored_data_neutral_when_ingestion_is_disabled
```

The globally UTF-8 byte-sorted 16-row add stream SHA is
`1dddbb0c9fe7974ecc398c39c7450837105cf575b1fc58e48a5e285b6ab884b5`;
the globally byte-sorted three-row removal SHA is
`7aeca70cfcd804c65da64c2580eff845813ad1a7c3f7b133fe69cce5dfe50576`.
Each stream has exactly one trailing newline. Sorting each file group
independently and concatenating groups is not equivalent.

### 2.3 Staged identities

| Stage | Full backend | Focused backend | Full frontend | Focused frontend |
|---|---|---|---|---|
| base | `4,341 / 883b1148...` | `375 / 1c3ce4ac...` | `100 files / 1,159 / f19472dd...` | `96 / 9877be8a...` |
| Task 1 | `4,349 / 372fe6ab...` | `383 / de8eb8c4...` | unchanged | unchanged |
| Task 2 | `4,359 / c100ee5d...` | `393 / 0dd72ab8...` | unchanged | unchanged |
| Task 3 | unchanged | unchanged | `101 files / 1,167 / 461b3827...` | `104 / 8fd324f0...` |
| Task 4 final | `4,359 / c100ee5d...` | `393 / 0dd72ab8...` | `101 files / 1,172 / d40a30d5...` | `109 / da8590cf...` |

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
461b38278c8125f6995e35a883771789d83df6b641236a02bb44b269e039f9bf
Task 3 frontend focused
8fd324f07dbb75d53ce3629a94922ff4b50b244fea8ef0bd40777d36d82c327a
Task 4/final frontend full
d40a30d5e50690f79b644e0b25122da02441eb0cf54ab02793d02269419e23cb
Task 4/final frontend focused
da8590cf3cdf126487d80b2fcdb7c116e550bbaff6eef3530e84bbcaf4222b91
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
apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > does_not_request_or_render_the_detailed_fred_snapshot
apps/arkscope-web/src/SettingsProviderConfig.test.ts::Settings provider config authority > renders FRED as configured local snapshot with refresh off
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx::MacroStorageSection > renders English Macro Data status snapshot and table headings
apps/arkscope-web/src/i18n/resources.test.ts::i18n resources > contains the reviewed remaining-surface namespace inventory in both locales
apps/arkscope-web/src/i18n/resources.test.ts::i18n resources > preserves the reviewed pre-Slice-5 Settings-origin inventory across the Common move
```

The exact removals/replacements in §2.2 are separate. The first resources owner
changes only Settings count `783 -> 785` and locale total `1867 -> 1869`. The
second adds exactly the four `macroStorage.schedule.*` paths from §1.7 to
`postSliceSettingsPaths`, adds exactly the two retired
`macroStorage.snapshot.*` paths to the retired-path list, and generalizes no
other fixture. Frozen constants (`641`, `23`, `664`, locale `3`, workspace
`95`, and the per-subtree baseline table) remain byte-identical and continue to
hold through the existing delta formula.

The Macro heading owner may evolve by exactly one selector token: its existing
five-value heading assertion reads `.settings-fred-table th` instead of every
`th` in the page. This is a scope correction, not an expected-value change: the
node must still require exactly `Series ID`, `Name`, `Latest value`,
`Observation date`, and `Last fetch` in order. A second hunk, node-ID change, or
expected-heading change is a stop condition.

The second Task 4 stop adds one bounded ownership repair with zero identity
change:

- `Settings.tsx` may wrap only the selected `data_sync` group sections in one
  `DataScheduleControlsProvider`; no other Settings group or resource moves;
- `DataSourcesSection.tsx` and `MacroStorageSection.tsx` replace their local
  `useDataScheduleControls(settingsReadCache)` calls with the shared-context
  consumer and otherwise preserve their section behavior;
- direct-render test helpers in `SettingsProviderConfig.test.ts` and
  `MacroStorageSection.test.tsx` supply the real provider rather than a fake
  controller;
- `Data schedule controls > shares one schedule read across visible consumers`
  evolves in place to render one real provider with two consumers, assert one
  initial GET, advance the idle clock once, assert exactly one additional GET,
  and prove both consumers receive the same controller; and
- `Settings provider config authority > renders_disabled_providers_as_neutral_and_every_registered_schedule_row_as_controllable`
  changes only its two locale row selectors to begin at
  `[data-settings-location='source_schedules']`, keeping the expected ten rows
  and every per-row assertion unchanged.

The four existing Settings polling owners below are unedited GREEN gates for
the repair; changing their IDs, bodies, or expected call counts is a stop:

```text
Settings provider config authority > polls only schedule after thirty idle seconds without a live region
Settings provider config authority > detects a fast idle-to-idle completion and refreshes related state once
Settings provider config authority > switches to five second polling while running and back to idle after completion
Settings provider config authority > switches locale without resetting drafts polling cadence or progress
```

A new test node, a second controller instance in the mounted `data_sync` group,
or any production edit outside the provider/context handoff is a stop event.

The full-suite collateral repair is limited to one setup assignment in
`SettingsWorkspace.test.tsx`:

```text
mocks.getSchedule.mockResolvedValue({ sources: {} });
```

It follows the generic `{}` loader setup and supplies the minimum valid
`ScheduleResponse` for the real provider. All 33 workspace node IDs and bodies,
especially `unmounts_data_sources_polling_when_leaving_data_sync`, remain
byte-identical. A product fallback for a missing `sources` field, a changed
workspace assertion, or a second hunk in that file is a stop event.

Within the already authorized `shares one schedule read across visible
consumers` body, the idle-clock step may use synchronous fake-timer advancement
followed by an explicit promise flush. Its behavioral assertions remain one
initial GET, exactly one GET after the first 30-second interval, and object
identity equality for both consumers. Raising the timeout or weakening any of
those assertions is forbidden.

The Task 4 browser-cascade repair is limited to one selector replacement in
`styles.css`:

```css
.settings-schedule-table td.settings-schedule-source-cell {
  white-space: normal;
  overflow-wrap: anywhere;
  vertical-align: top;
  line-height: 1.45;
}
```

The declarations are unchanged. The existing Task 4 ADD node
`Settings workspace CSS contract > wraps schedule source copy inside the source
column` evolves in place to require this exact selector and remains the static
RED/GREEN owner; its ID does not move. The pre-fix real-browser RED must be
preserved, and the same desktop `1322 x 777` plus mobile `390 x 844` fixture
must prove computed `white-space: normal`, `overflow-wrap: anywhere`, source
cell `scrollWidth <= clientWidth`, at least one long source description
rendering on multiple line rectangles, exact reviewed column proportions,
bounded horizontal table scrolling, zero page/main overflow, and zero cell
overlap. A selector-only textual GREEN without that rendered replay is
rejected evidence. A second CSS declaration, selector broadening beyond the
schedule table, or any node-ID/count/identity change is a new stop event.

Task 4 has one additional bounded owner in
`SettingsPostPgExitStorage.test.ts`. Its `MacroSnapshot` fixture removes exactly
the retired `auto_refresh_enabled` field. The old
`shows_total_macro_data_without_claiming_calendar_product` ID is removed and
the §2.2 replacement asserts the exact reviewed description, the manual versus
scheduled refresh boundary, local-only `重新讀取狀態`, stored FRED evidence, and
no provider-freshness guarantee or `攝入` wording. The other 13 node IDs and
bodies in that file remain byte-identical. Run all 14 nodes in the file as a
separate Task 4 owner gate; it is intentionally outside the §2.6 focused
identity. Editing any other existing node body is a stop-and-amend event.

The Task 3 stop amendment permits one additional existing backend owner-body
evolution, with no node-ID change:

```text
tests/test_macro_scheduler_integration.py::test_macro_lock_busy_records_one_non_success_row_without_provider_work
```

Its added phase must hold the real shared macro writer, call
`run_source(..., trigger_source="api")`, and prove one failed canonical
`fetch_*` row, one transient `_LAST_RESULT` carrying `status="skipped"` plus
stable `macro_calendar_busy` code/reason, zero provider work, no
`_LAST_ATTEMPT`, and no durable attempt/outcome. The existing
`trigger_source="scheduler"` real-process phase remains pure defer and must stay
GREEN. The new Task 3 manual-run owner also gains the fast-terminal subcase
described in the amendment header; because that node is already in the Task 3
addition ledger, its strengthened body changes no identity.

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
  src/SettingsCss.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/settings/MacroStorageSection.test.tsx \
  src/settings/settingsReadCache.test.ts \
  src/settings/dataScheduleControls.test.tsx \
  src/i18n/resources.test.ts
```

Baseline identity excludes the new file and is
`96 / 9877be8adf0973c2b749f6460156ae86021cc4a91f3d4caab366bd9ce66da46f`;
Task 3 is `104 / 8fd324f07dbb75d53ce3629a94922ff4b50b244fea8ef0bd40777d36d82c327a`;
final is `109 / da8590cf3cdf126487d80b2fcdb7c116e550bbaff6eef3530e84bbcaf4222b91`.

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
   missing same-tick/cross-tick writer deferral, legacy snapshot flag, or absent
   no-create projection.
3. Add the five sources, canonical job names, provider maps, defaults, and
   independent macro tick group.
4. Remove the snapshot false-authority field and derive provider automation
   from no-create schedule reads.
5. Run final backend focused tests plus no-create filesystem snapshots.
6. Commit product/tests and evidence/docs; stop for review.

### Task 3 - Shared frontend controller

1. Add the eight controller nodes and atomic truthful replacement. Collect
   `101 files / 1,167 / 461b3827...`; the removed old ID must be absent exactly
   once and the replacement fixture must cover every registered schedule row.
2. Run RED: the new module is absent, Data Sources still owns the controller,
   immediate broad invalidation is observable, and the old false test name is
   gone.
3. Extract the hook/table; migrate Data Sources without changing its source set,
   polling cadence, provider controls, or SA owner.
4. Add exact macro cache mappings, detect successful terminal revisions even
   when no `running` frame was observed, and preserve all existing
   price/news/SEC mappings.
5. Run 104 focused nodes, typecheck, and i18n scanner; commit pair and stop for
   review.

### Task 4 - Macro page controls and copy

1. Add the four Macro page nodes plus two CSS contract nodes, replace the false
   post-PG macro-copy node, remove the false legacy snapshot-automation node,
   and collect final frontend identity.
2. Run them RED: no macro rows, absent three-state automation truth, ambiguous
   local refresh copy, or unbounded source-column layout must be the causes.
3. Mount the filtered shared table, derive enabled count, remove the legacy DTO
   field and the exact post-PG fixture field, add reviewed bilingual copy,
   apply the exact resources-test deltas in §2.4, and land the dedicated
   source-cell/column CSS contract. Mount one group-scoped schedule controller
   for the `data_sync` tab and pass it to both visible schedule tables.
4. Run 109 focused nodes, the separate 14-node post-PG owner file, full
   frontend, typecheck, build, scanner, and an early desktop/mobile browser
   check.
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
| M7 | send run-now POST on mount/idle/focus/visibility/local reload | frontend zero-POST node |
| M8 | remove the source-cell wrapping class so global nowrap wins | source-wrapping CSS node + browser geometry replay |
| M9 | restore the old `22/10/16/16/36` schedule widths | reviewed-column CSS node + browser geometry replay |

A mutation that edits dead code, is killed only by an unrelated source-string
assertion, or leaves its semantic owner GREEN is rejected evidence. M8/M9 must
also produce the expected computed-style/geometry violation in the hermetic
browser fixture; a textual CSS delta without rendered effect is rejected.

Final gates:

1. backend full collection `4,359 / c100ee5d...`;
2. backend focused `393` passing;
3. frontend full `101 files / 1,172 / d40a30d5...`;
4. frontend focused `109` passing;
5. frontend full runtime, typecheck, build, and i18n scanner;
6. canonical native backend target = `4,359 seen / 4,347 passed / 12 skipped /
   0 failed / exit 0` (the exact `4,329/12/0` baseline plus 18 passing nodes);
7. hermetic scratch `macro_calendar.db`: one representative success updates
   expected rows and a subsequent provider failure leaves them unchanged;
8. two-process lock and descriptor-release probes;
9. desktop `1322 x 777` and mobile `390 x 844` browser matrix: five macro rows,
   every Data Sources registry row, source text wrapped inside its cell,
   reviewed column proportions, bounded horizontal scrolling, zero overlap,
   zero POST across mount/idle/focus/visibility/local reload before explicit
   click, exactly one POST after click, and honest terminal state; and
10. artifact manifest, generated-file cleanup, production DB/config SHA and
    stat equality, and clean worktree.

Stop for full implementation review. No merge is authorized by Task 5.

The production-equality gate is measured only while the Desktop/sidecar writer
is quiesced. A timestamp-correlated external-writer explanation is useful stop
evidence but is never a substitute for the exact pre/post equality required to
complete Task 5.

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
2. any node outside the `+18/-0` backend or `+16/-3` frontend ledger changes;
3. a second telemetry row appears for one attempt;
4. any scheduled macro row uses a `collect.*` identity;
5. lock setup degrades to unlocked execution;
6. a lock descriptor survives any terminal path;
7. a due macro source is marked attempted, assigned a row, skipped-success, or
   no longer due merely because another macro writer fired in this or an
   earlier tick, or is active in another process;
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
17. a frozen Settings baseline/count block changes, or the resources owner
    differs from the exact §2.4 path/count delta;
18. an unowned path changes, including a schedule-table CSS edit outside the
    bounded `styles.css` rules;
19. a deterministic browser overlap, overflow, duplicate POST, or stale-state
    regression appears;
20. a test contacts FRED/Finnhub or a live sidecar;
21. a reviewer cannot rebuild an asserted identity from raw artifacts; or
22. the mounted `data_sync` group owns more than one schedule controller,
    polling timer, or focus listener.

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
