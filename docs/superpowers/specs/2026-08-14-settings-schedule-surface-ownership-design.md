# Settings Schedule Surface Ownership Design

> **Status:** USER DIRECTION APPROVED; FABLE-REVIEWED GREEN;
> IMPLEMENTATION PLAN NEXT; IMPLEMENTATION NOT STARTED
>
> **Date:** 2026-08-14
>
> **Branch base:** `e2ead4378189d277a40a61f7130730513980794e`
> (SA diagnostics exact-master closeout tip)
>
> **Branch:** `codex/schedule-surface-ownership`

## 1. Problem

Settings currently renders the same five Macro schedule sources twice:

1. `DataSourcesSection` calls `DataScheduleTable` without `sourceIds`, so the
   table renders every key returned by `/schedule`.
2. `MacroStorageSection` calls the same table with five hard-coded Macro IDs.

The backend has one registry and one schedule record per source. Both tables
share the same React controller, timer, focus listener, drafts, busy state,
and mutations. There is no duplicate backend schedule and no duplicate
polling owner. The problem is presentation ownership: two editable tables use
the same title and expose the same Macro switches, intervals, and run-now
commands.

The reviewed Macro implementation explicitly accepted ten rows under Data
Sources plus five repeated rows under Macro. The user's post-merge inspection
rejects that information architecture. A source must have one editable home.

## 2. Grounded Baseline

At base `e2ead437`, the backend registry contains ten sources:

| UI scope | `write_target` | Sources |
|---|---|---|
| Data Sources | `market_data.db` | `polygon_news`, `finnhub_news`, `ibkr_news`, `ibkr_prices`, `sec_corporate_actions` |
| Macro Data | `macro_calendar.db` | `fred_series`, `fred_release_dates`, `finnhub_economic_calendar`, `finnhub_earnings_calendar`, `finnhub_ipo_calendar` |

`ScheduleSourceState.write_target` is a required backend-owned string. The
shared schedule controller already uses exact
`write_target === "macro_calendar.db"` classification for downstream cache
invalidation, including future Macro sources. This slice reuses that authority
instead of creating a second source-name registry.

Relevant baseline files:

| Path | Lines | SHA-256 |
|---|---:|---|
| `apps/arkscope-web/src/settings/dataScheduleControls.tsx` | 493 | `c5f4feb71a0e9894d943f0b58c1ad26336223905c5918426ecddb4f3838d35a7` |
| `apps/arkscope-web/src/settings/DataSourcesSection.tsx` | 913 | `fc97cbac7fae6b94fca9f9d747b2dc7cad55b044516d1073929a4a186946845c` |
| `apps/arkscope-web/src/settings/MacroStorageSection.tsx` | 288 | `16a8ceaa970da06f8c76535d7f9277129a3abaecfb85c6b84285e0ed77deed57` |
| `apps/arkscope-web/src/i18n/resources/en/settings.ts` | 1,143 | `7838eaeb71f849266f4a31be9937213012cd976f63ea6f9722bf14550579bcbb` |
| `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts` | 1,142 | `d7274dac087f1c9cacbd60229aa717f698123046eec4ab67c943cb468e53c0ed` |

The current visible difference between the repeated tables is also grounded:
Data Sources supplies provider-health `jobs` and a provider-operation busy
flag; Macro does not. The implementation plan must inventory the rendered
facts before removing duplicate rows. If Data Sources is the only visible
owner of a Macro fact that the approved Macro surface does not preserve, that
is a stop-and-amend event rather than permission to lose the fact silently.

## 3. Locked Decisions

### LD 1 - One editable owner per source

Every source returned by `/schedule` appears in exactly one editable schedule
table within the active Data and Sync tab.

- `write_target === "macro_calendar.db"` belongs to `MacroStorageSection`.
- Every other `write_target` belongs to `DataSourcesSection`.

The two sets must be disjoint and their union must equal every returned source
ID. No source may disappear and no source may have two switches, interval
inputs, or run-now buttons.

### LD 2 - Backend metadata, not names, classifies sources

The frontend must not maintain parallel lists of known Data Sources and Macro
source IDs. Classification uses only the required `write_target` field.

An unknown future target is intentionally routed to Data Sources. This is the
fail-visible fallback: a new source remains controllable while its product
placement is reviewed. It must not disappear from both tables.

### LD 3 - The shared controller remains the only controller

`DataScheduleControlsProvider` remains mounted once at the `data_sync` group.
This slice does not add a hook, timer, focus listener, cache key, scheduler
request, or mutation path. Both tables continue to consume the same controller
instance.

### LD 4 - Scope is a required table contract

Production callers must state whether a `DataScheduleTable` renders Macro or
non-Macro sources. An implicit all-sources production default would recreate
the defect and is forbidden.

Tests may use a purpose-built fixture helper, but production code cannot
render an editable global table.

### LD 5 - Titles describe distinct ownership

Traditional Chinese:

- Data Sources subsection and directory label: `資料來源排程`
- Macro card: `總經資料排程`

English:

- `Data source schedules`
- `Macro data schedules`

The generic table column labels remain shared. The phrase
`排程（每來源獨立）` retires from the current Settings UI because it does not
identify either owner.

### LD 6 - No global duplicate overview in this slice

This slice does not add a third scheduler page or a read-only all-source table.
If a global operations view is later justified, it must be read-only or link
to the owning section; it may not recreate duplicate editable controls.

### LD 7 - Ordering and behavior remain stable

Rows preserve backend `/schedule` insertion order within each partition.
Enable, interval, run-now, continuation, polling, focus refresh, lifecycle
invalidation, navigation guards, busy handling, and error handling retain
their current behavior.

## 4. Component Shape

`DataScheduleTable` owns one small classifier:

```text
macro      := state.write_target === "macro_calendar.db"
non-macro  := state.write_target !== "macro_calendar.db"
```

The table receives a required scope and filters `Object.entries(schedule)` in
place. `DataSourcesSection` passes the non-Macro scope.
`MacroStorageSection` passes the Macro scope and derives its enabled count from
the same filtered schedule records. The existing hard-coded
`MACRO_SCHEDULE_SOURCE_IDS` list is removed.

No backend DTO, API route, scheduler registry, persistence record, cache
policy, Settings group, anchor ID, CSS selector, or layout dimension changes.

## 5. User Experience

Under `資料來源排程`, the user sees five current market/news/company-event
sources. Under `總經資料排程`, the user sees five current FRED/Finnhub Macro
sources beside stored coverage and snapshots.

Changing a control updates the single shared state. Navigating between the two
locations never reveals a second control for the same source. Search and the
left directory retain the stable `source_schedules` and `macro_storage`
anchors, with the new owner-specific labels.

The existing `重新讀取狀態` button remains local-only for Macro status and
snapshot reads. It is not renamed into, or conflated with, a schedule run.

## 6. Verification Contract

RED-first implementation must prove:

1. a mixed schedule fixture renders each source in exactly one table;
2. the Macro and non-Macro row sets are disjoint and their union equals the
   backend fixture IDs;
3. an unknown future `macro_calendar.db` source appears only under Macro;
4. an unknown future non-Macro target appears only under Data Sources;
5. both consumers receive the exact same controller object and one idle poll
   still produces exactly one schedule GET;
6. the old all-source Data Sources behavior is RED before the fix;
7. each visible title and directory label uses the reviewed bilingual copy;
8. existing drafts, manual run, polling, focus, unmount, cache invalidation,
   navigation guard, and locale-switch owners remain GREEN;
9. no unique Macro status fact is lost when its duplicate Data Sources row is
   removed; and
10. a hermetic desktop/mobile browser replay sees ten total editable rows,
    ten unique source IDs, no duplicates, no POST without an explicit click,
    and no overlap or page overflow.

Resource inventory tests must use the established post-slice path mechanism;
frozen historical counts are not rewritten to follow current totals.

## 7. Scope Boundary

Allowed product surfaces are limited to:

- shared schedule table classification;
- the two schedule-table callers;
- owner-specific English and Traditional Chinese titles; and
- the exact tests and resource inventory rows needed to prove the contract.

The following are out of scope:

- backend scheduler, source registry, DTO, route, DB, or cadence changes;
- provider calls or live schedule runs;
- new polling, caching, controller, or state ownership;
- CSS/layout changes;
- moving Settings sections or anchors;
- a global scheduler page;
- SA diagnostics implementation changes; and
- Task 7 merge or push of the parent SA line.

## 8. Alternatives Considered

### A. `write_target` partition with one owner - selected

This reuses backend metadata, handles future Macro sources, removes duplicate
controls, and leaves the scheduler architecture unchanged.

### B. Two hard-coded source-ID lists - rejected

It is superficially smaller but creates a second registry. A future source can
be omitted or duplicated until the frontend list is updated.

### C. Keep all rows in Data Sources and make Macro rows read-only - rejected

This preserves a global overview but still duplicates information and leaves
ambiguous ownership. There is no current evidence that a second overview pays
for that complexity.

## 9. Sequencing

This branch is re-grounded on the reviewed SA diagnostics closeout tip
`e2ead437`. The schedule-surface slice runs before PG consumer inventory,
superseding the prior direct SA-to-PG ordering. Product implementation must
not start until an exact RED-first implementation plan is independently
reviewed and approved. The slice merges only after its own implementation
review.

## 10. Acceptance

The slice is complete only when:

1. the current ten sources render as five Data Sources rows plus five Macro
   rows, with no duplicate source ID;
2. future-source tests prove metadata-driven partitioning;
3. there is still one controller, one timer/focus owner, and one mutation path;
4. user-visible titles clearly distinguish the two owners;
5. focused/full/typecheck/build/i18n/browser gates pass; and
6. no backend, production data, provider, scheduler cadence, parent SA product
   byte, merge, or push changes.
