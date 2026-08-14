# Settings Schedule Surface Ownership Implementation Plan

> **Status:** PLAN REVIEW GREEN; TASKS 0-1 COMPLETE; TASK 2 ACTIVE UNDER BATCH RULING; TASK 3 IS THE COMBINED IMPLEMENTATION-REVIEW GATE
>
> **Date:** 2026-08-14
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-14-settings-schedule-surface-ownership-design.md`
> (user-approved and Fable-reviewed GREEN).
>
> **Product grounding base:**
> `e2ead4378189d277a40a61f7130730513980794e`
> (SA diagnostics exact-master closeout tip).
>
> **Required execution skills:** use `superpowers:test-driven-development`
> for every behavior change, `superpowers:verification-before-completion`
> before every GREEN/complete claim, and
> `superpowers:requesting-code-review` at the review gates.
>
> **Roles:** Codex authors and implements RED-first after independent plan
> review. Fable independently reconstructs identities and reviews evidence,
> product diffs, and merge readiness. The user owns product, batching, live,
> destructive-data, merge, and push rulings.

> **Process ruling (2026-08-14):** after independent plan review returned
> GREEN at `590ce355`, the user authorized Tasks 0-3 to run continuously.
> Every task still requires its own commits and evidence packet, and every
> Section 5 stop condition remains hard. Task 3 replaces the per-task review
> waits with one combined implementation-review gate. Task 4, merge, push,
> live traffic, provider calls, and production mutation remain unauthorized.

**Goal:** give every Settings schedule source exactly one editable home: five
current market/news/company-event rows under Data Sources and five current
Macro rows under Macro Data, while preserving every control and the latest-job
fact that the duplicate Data Sources rows currently expose.

**Architecture:** one required `write_target` scope predicate partitions the
existing shared schedule map. The existing group-scoped
`DataScheduleController` remains the sole schedule/timer/focus/mutation owner
and gains only a presentation projection of provider-health job facts. Data
Sources remains the sole visible provider-health consumer/state owner and
feeds those facts into the shared controller; the existing Settings idle
warmup may still prefill the same read cache. Both tables render the facts
without a second GET or a second state authority.

**Stack:** React 18, TypeScript 5.9.3, Vitest 4.1.8, Vite 5.4.21,
Playwright 1.58.0, Chrome 150.0.7871.128, Python 3.10 collect-only boundary.

---

## 0. Authority, boundaries, and grounding

### 0.1 Binding decisions

This plan implements design LD 1 through LD 7. The following implementation
decisions are locked:

1. A row is Macro if and only if
   `state.write_target === "macro_calendar.db"`.
2. Every other target, including an unknown future target, is non-Macro and
   remains visibly controllable under Data Sources.
3. `DataScheduleTable` receives a required `scope: "macro" | "non_macro"`.
   There is no all-source default and no source-ID allowlist.
4. `MACRO_SCHEDULE_SOURCE_IDS`, `sourceIds`, and
   `DataScheduleLocalError` retire in the same product commit. They are not
   retained as compatibility helpers or test-only tails.
5. `DataScheduleControlsProvider` remains mounted exactly once for the active
   `data_sync` group. No hook, timer, focus listener, cache key, API request,
   mutation path, or backend registry is added.
6. Provider-health `jobs` is preserved. It carries latest terminal status and
   `finished_at`, which the schedule durable state does not fully replace.
7. The existing `DataScheduleController` gains only
   `jobFacts: ProvidersHealthResponse["jobs"]` and a stable
   `replaceJobFacts(...)` method. This is an active-group presentation
   projection, not a second provider-health cache or fetch owner.
8. `DataSourcesSection`, already the sole visible provider-health consumer and
   local state owner, updates that projection after a successful visible or
   retained-cache read. The existing Settings idle warmup remains byte
   protected and may prefill that cache. A failed read retains the last
   admitted facts exactly as the current `health` state does.
9. `DataScheduleTable` reads job facts from its controller. Its `jobs` prop is
   removed. Macro therefore gains the same latest-job rendering without any
   extra request, timer, listener, cache subscription, or polling interval.
10. Macro's enabled-source count uses the same exported scope predicate as
    table rendering. It must not grow another source list.
11. Row order remains the insertion order of `Object.entries(schedule)` after
    filtering.
12. Reviewed copy is exact: `資料來源排程` / `Data source schedules` for the
    Data Sources subsection and directory; `總經資料排程` /
    `Macro data schedules` for the Macro card.
13. `重新讀取狀態` remains a local Macro status/snapshot read. It is not a
    schedule action and is not renamed.
14. No backend, scheduler cadence, DTO, route, persistence, cache policy,
    Settings registry/anchor, CSS, layout dimension, provider, or production
    data changes are authorized.
15. This UI slice runs after SA diagnostics and before PG consumer inventory,
    superseding the prior direct SA-to-PG ordering.

No live provider call, schedule POST outside a hermetic fixture, production DB
read/write, merge, push, or destructive operation is authorized by this plan.

### 0.2 Canonical base identities

All streams use tab-separated `path<TAB>fully normalized Vitest node ID` rows,
UTF-8 byte-sorted with exactly one final newline. The pinned normalizer is
`/tmp/eir006_vitest_list_normalizer.py`, SHA-256
`955dca592d243505ced622a84e88a35160a3fa787ffb954f38a6a43e1a72fcac`.
Task 0 must copy that normalizer into its packet and record the copied bytes;
the temporary path alone is not durable evidence.

| Identity | Count | SHA-256 | Runtime witness |
|---|---:|---|---|
| Frontend full | 1,177 / 101 files | `9530dcd91d8a7d684faa5e56f2986fbaeaa22e1d89f67818a12ed5d8ca77d1b1` | inherited SA exact-master full `1,177/1,177` |
| Schedule focused, 6 files | 127 | `83b8a5e4941aea52b5818d9fe9073407e69d559338c579d3f25fc930b514a735` | freshly run `127 passed` |
| Settings regression, 15 files | 249 | `a3a5e481cace86991db6d8ec5da56c2d973d224e1cb1de57f631c210a646a16e` | inherited SA exact-master `249/249` |
| Backend full | 4,394 | `b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb` | collect-only, zero test bodies |
| Backend native | 4,394 seen | reporter `0a58d493ab6b406a2a69fa4cc7b25670373d7a16fd74b85c2b60c9452e07c030` | inherited `4,382 passed / 12 skipped / 0 failed` |

The six-file focused projection is literal and sums to 127:

```text
src/SettingsPostPgExitStorage.test.ts                    14
src/SettingsProviderConfig.test.ts                        44
src/SettingsWorkspace.test.tsx                           33
src/i18n/resources.test.ts                               14
src/settings/MacroStorageSection.test.tsx                14
src/settings/dataScheduleControls.test.tsx                8
```

The Settings regression projection is literal and sums to 249:

```text
src/AppShell.test.tsx                                     22
src/ProviderSection.test.ts                               26
src/SettingsCss.test.ts                                   10
src/SettingsInvestorProfileIntegration.test.tsx            3
src/SettingsModelRouting.test.ts                          17
src/SettingsNewsStorage.test.ts                            7
src/SettingsPostPgExitStorage.test.ts                     14
src/SettingsProviderConfig.test.ts                        44
src/SettingsStabilizationCss.test.ts                       2
src/SettingsWorkspace.test.tsx                            33
src/settings/MacroStorageSection.test.tsx                 14
src/settings/settingsBackendCopy.test.ts                  12
src/settings/settingsCopy.test.ts                         10
src/settings/settingsReadCache.test.ts                    19
src/settings/settingsRegistry.test.ts                     16
```

Task 0 must reconstruct all four collection streams from the plan worktree at
the independently reviewed plan tip. A count-only match is insufficient; the
entire normalized stream must be byte-identical.

### 0.3 Pinned frontend toolchain

```text
Node                              v22.14.0
Vitest                            4.1.8
Vite                              5.4.21
TypeScript                        5.9.3
Playwright                        1.58.0
Chrome                            150.0.7871.128
package-lock.json SHA-256         5322cb03099b873066b7572c02db68a427ddc7509fdc9850cf9d8d3948a19f2c
apps/arkscope-web/package.json    dbaecc3792419d833af4ef6659cfee42977f6c43e4066c16d3cc8df9b9912ffa
```

An unpinned `npx` resolution, dependency install, lockfile rewrite, or test
run under a different Vitest version is rejected evidence.

### 0.4 Owned paths

Product owners:

```text
apps/arkscope-web/src/settings/dataScheduleControls.tsx
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.tsx
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
```

Test owners:

```text
apps/arkscope-web/src/settings/dataScheduleControls.test.tsx
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx
apps/arkscope-web/src/SettingsWorkspace.test.tsx
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
apps/arkscope-web/src/i18n/resources.test.ts
```

Baseline identities:

| Path | Lines | SHA-256 at `e2ead437` |
|---|---:|---|
| `apps/arkscope-web/src/settings/dataScheduleControls.tsx` | 493 | `c5f4feb71a0e9894d943f0b58c1ad26336223905c5918426ecddb4f3838d35a7` |
| `apps/arkscope-web/src/settings/DataSourcesSection.tsx` | 913 | `fc97cbac7fae6b94fca9f9d747b2dc7cad55b044516d1073929a4a186946845c` |
| `apps/arkscope-web/src/settings/MacroStorageSection.tsx` | 288 | `16a8ceaa970da06f8c76535d7f9277129a3abaecfb85c6b84285e0ed77deed57` |
| `apps/arkscope-web/src/i18n/resources/en/settings.ts` | 1,143 | `7838eaeb71f849266f4a31be9937213012cd976f63ea6f9722bf14550579bcbb` |
| `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts` | 1,142 | `d7274dac087f1c9cacbd60229aa717f698123046eec4ab67c943cb468e53c0ed` |
| `apps/arkscope-web/src/settings/dataScheduleControls.test.tsx` | 460 | `ec60440dfb3d437508ea9e2e73d939ee3b7d1892677497a623739f5a279279a7` |
| `apps/arkscope-web/src/SettingsProviderConfig.test.ts` | 1,865 | `07d78fdd68fcfd5c10efb9ad425651a813ac7e67573870e8b1acfd6eba4f4095` |
| `apps/arkscope-web/src/settings/MacroStorageSection.test.tsx` | 585 | `4a2a531ca5f137413518fb147e6a36ef6b301e45dfd934c85a6c105c502c971c` |
| `apps/arkscope-web/src/SettingsWorkspace.test.tsx` | 1,068 | `e4b2dc2c9b8c65bbc976fbe8dfa848ab0db5c7d6908808695d9068e2953f6972` |
| `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts` | 1,100 | `b6eadf370bb60b74816f27e6d9aaecfbae58606f31504e98acb1f9a27749e732` |
| `apps/arkscope-web/src/i18n/resources.test.ts` | 1,308 | `2cec9e89b1a2091cd4ebaf12b62eff86d6c23a147b245112e96784daafc420a1` |

Task evidence may evolve this plan, the design status/grounding section,
`docs/design/PROJECT_PRIORITY_MAP.md`, and one new evidence file:
`docs/superpowers/evidence/2026-08-14-settings-schedule-surface-ownership.md`.
Any other product/test path is a stop-and-amend event.

### 0.5 Byte-protected boundary

These 13 paths remain byte-identical:

```text
package-lock.json
apps/arkscope-web/package.json
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/styles.css
apps/arkscope-web/src/settings/settings.css
apps/arkscope-web/src/settings/settingsReadCache.ts
apps/arkscope-web/src/settings/settingsRegistry.ts
apps/arkscope-web/src/settings/SettingsDirectory.tsx
apps/arkscope-web/src/dataSourceSchedulePolling.ts
apps/arkscope-web/src/SettingsCss.test.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
apps/arkscope-web/src/settings/settingsRegistry.test.ts
```

The aggregate recipe is exact: UTF-8 byte-sort these literal paths, run GNU
`sha256sum` in that order, then SHA-256 the complete 13-row standard-output
byte stream including its final newline. The baseline aggregate is
`b3b3ac3f2151d34bf3ce0e15a772ebb0a655e46fe63a43eccae142d4208602a1`.
Task 0 records both individual rows and the aggregate. A changed protected byte
is a stop, not permission to widen the line.

### 0.6 Rendered-fact inventory and `jobs` disposition

The duplicate rows are not byte-equivalent presentations:

| Fact | Data Sources today | Macro today | Ruling |
|---|---|---|---|
| schedule state, drafts, busy, mutations | shared controller | shared controller | retain one shared owner |
| durable last status, continuation, backlog | schedule DTO | schedule DTO | retained automatically |
| latest `job_runs` status and `finished_at` | `health.jobs` prop | absent | preserve through shared controller |
| provider-operation external busy | local Data Sources action state | absent | remains Data Sources-only; it is not a Macro operation fact |

`jobFacts` must not be populated by `getProvidersHealth` inside the controller.
The only admitted flow is:

```text
DataSourcesSection existing visible/retained-cache provider-health read
  -> successful ProvidersHealthResponse.jobs
  -> stable controller.replaceJobFacts(jobs)
  -> either scoped DataScheduleTable reads controller.jobFacts
```

The retained provider-health cache, including a value prefetched by the
existing Settings idle warmup, follows the same path when Data Sources mounts.
Errors do not clear already admitted job facts. Group unmount destroys the
controller and its projection. This preserves current truth without a second
request or an independent persistence/cache owner.

---

## 1. Product contract

### 1.1 One scope predicate

`dataScheduleControls.tsx` exports:

```ts
export type DataScheduleScope = "macro" | "non_macro";

export function dataScheduleSourceMatchesScope(
  state: Pick<ScheduleSourceState, "write_target">,
  scope: DataScheduleScope,
): boolean {
  const macro = state.write_target === "macro_calendar.db";
  return scope === "macro" ? macro : !macro;
}
```

`DataScheduleTable` filters `Object.entries(schedule)` with this predicate.
It does not sort, regroup, or consult source names. The table cannot accept
`sourceIds`, an optional scope, or a global/all scope.

### 1.2 Shared presentation facts

`useDataScheduleControls` owns an initially empty job-fact state and a stable
`useCallback` replacement method. Both are returned through the existing
controller object. `LastRun` reads `controller.jobFacts`; `DataScheduleTable`
and `LastRun` no longer accept a `jobs` prop.

`DataSourcesSection` destructures the stable replacement method and uses one
effect to publish `health.jobs` after successful existing reads. The effect
must not depend on the entire recreated controller object and must not issue a
request. Tests prove a later successful provider-health read updates Macro's
visible timestamp and that a failed read cannot erase the last admitted fact.

### 1.3 Exact callers

`DataSourcesSection` renders:

```tsx
<DataScheduleTable
  controller={scheduleController}
  scope="non_macro"
  externalBusy={busy !== ""}
/>
```

`MacroStorageSection` renders:

```tsx
<DataScheduleTable controller={scheduleController} scope="macro" />
```

Macro's enabled count filters `Object.values(schedule)` with
`dataScheduleSourceMatchesScope(state, "macro")` and counts enabled rows.
The hard-coded list is physically deleted.

### 1.4 Exact copy and resource accounting

Value-only replacement:

| Key | Traditional Chinese | English |
|---|---|---|
| `dataSources.schedule.title` | `資料來源排程` | `Data source schedules` |

New path:

| Key | Traditional Chinese | English |
|---|---|---|
| `macroStorage.schedule.title` | `總經資料排程` | `Macro data schedules` |

The new path is appended to `postSliceSettingsPaths`. Current resource counts
change exactly:

```text
settings namespace per locale   827 -> 828
all namespaces per locale      1911 -> 1912
```

Frozen historical values remain byte-for-byte `641`, `23`, `664`, `95`, `3`,
and baseline `macroStorage: 31`; the post-slice subtraction mechanism absorbs
the new Macro path. No other key is added, removed, renamed, or reworded.

### 1.5 Browser contract

At desktop `1322 x 777` and mobile `390 x 844`, a hermetic fixture must prove:

1. `source_schedules` has exactly five current non-Macro rows;
2. `macro_storage` has exactly five current Macro rows;
3. the union has ten unique source IDs and the intersection is empty;
4. every row has one checkbox, one numeric interval input, and one run button;
5. the Macro `fred_series` row renders a fixture `fetch_fred_series`
   completion timestamp supplied by the existing provider-health GET;
6. Data Sources and Macro retain the existing source insertion order;
7. mount, idle, focus, visibility change, locale switch, and local status
   reload emit GET-only traffic and no schedule POST;
8. an explicit run click emits exactly one schedule POST;
9. one idle polling interval adds exactly one schedule GET for both tables;
10. reviewed owner-specific titles appear in the directory/card;
11. no duplicate control, overlap, page overflow, or horizontal regression is
    present; and
12. no real sidecar or provider endpoint is reachable from the harness.

---

## 2. Exact node ledger

### 2.1 Truthful replacements

The slice removes exactly two false IDs:

```text
src/SettingsProviderConfig.test.ts	Settings provider config authority > renders_disabled_providers_as_neutral_and_every_registered_schedule_row_as_controllable
src/settings/dataScheduleControls.test.tsx	Data schedule controls > filters rows without changing registry truth
```

Removal stream: `2` rows,
`9c8ca36c0ad5672e958988a1f937353ff775d9fb89f2db78dd17f7129deaa286`.

It adds exactly two truthful replacements:

```text
src/SettingsProviderConfig.test.ts	Settings provider config authority > renders_disabled_providers_as_neutral_and_partitions_every_registered_schedule_row_into_one_controllable_owner
src/settings/dataScheduleControls.test.tsx	Data schedule controls > partitions schedule rows by write target without changing registry truth
```

Addition stream: `2` rows,
`d35fbff9334d4e435ed85cbd780ed795f010a6be9df1092d083e3f8a88bc1037`.

Both removals exist exactly once in the base; both additions are absent. A
third add/remove/rename is a stop-and-amend event.

### 2.2 Staged identities

Task 1 performs the complete `-2/+2` semantic cutover. Task 2 changes only
existing test bodies and resource values, so identities remain stable.

| Stage | Frontend full | Focused, 6 files | Settings, 15 files |
|---|---|---|---|
| Base / Task 0 | `101 files / 1177 / 9530dcd91d8a7d684faa5e56f2986fbaeaa22e1d89f67818a12ed5d8ca77d1b1` | `127 / 83b8a5e4941aea52b5818d9fe9073407e69d559338c579d3f25fc930b514a735` | `249 / a3a5e481cace86991db6d8ec5da56c2d973d224e1cb1de57f631c210a646a16e` |
| Task 1 RED/final | `101 files / 1177 / 90f56093290c70a27369296ec8d8c7de99d084a091134994ae6451bc8e45743b` | `127 / 0d6eb25864d2c0a7a5ee76a9d05dacbc45e232106e62461a043b3d7196aac644` | `249 / ee6618dfc755f5ead79f6012967d3dda2c7a33f37ef87f62c5f98deff0f6c5cf` |
| Task 2/final | same as Task 1 | same as Task 1 | same as Task 1 |

The full and focused target streams are exactly `(base - removal + addition)`.
The Settings target applies only the Provider replacement because
`dataScheduleControls.test.tsx` is outside that 15-file projection.

### 2.3 Replacement behavior

The new `partitions schedule rows by write target...` node uses one real
controller and renders both required scopes against one mixed schedule fixture:

- current market and Macro rows;
- one future exact `macro_calendar.db` row; and
- one future unknown target such as `future_local.db`.

It asserts disjointness, complete union, insertion order, future Macro
placement, unknown-target fail-visible placement, shared controller identity,
and enabled controls. The base product renders all rows in both tables or lacks
the required scope, so the node must be RED before implementation.

The new Provider integration node retains the disabled-provider neutral
assertions, renders full Settings, and asserts:

- five current Data Sources rows under `source_schedules`;
- five current Macro rows under `macro_storage`;
- ten unique IDs with no duplicate;
- controls on every row in both locales; and
- `fred_series` displays the exact known `fetch_fred_series.finished_at`
  fixture fact after the existing provider-health read.

The same node has two bounded job-fact phases without changing its ID: a
successful refresh replaces an older cached completion timestamp, and a fresh
render with stale cached truth plus a rejected refresh keeps that cached
timestamp visible. It must use the real `SettingsReadCache`, shared controller,
and full Settings integration; a hand-written controller or direct state setter
is not equivalent.

The base product is RED because it renders ten plus five rows and Macro has no
job-fact handoff. The node must clean up its temporary health fixture.

### 2.4 Existing node-body evolution

Exactly these eight retained IDs may change their assertion bodies for reviewed
copy/resource expectations; their IDs remain byte-identical:

```text
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > lists_the_active_data_group_and_its_stable_subsections
src/SettingsPostPgExitStorage.test.ts	post-PG-exit storage panels > shows_macro_data_with_manual_and_scheduled_refresh_boundaries
src/SettingsProviderConfig.test.ts	Settings provider config authority > renders English data-source health config and schedule tables
src/SettingsWorkspace.test.tsx	Settings workspace > shows_only_the_active_group_directory_while_search_remains_cross_group
src/SettingsWorkspace.test.tsx	Settings workspace > tracks_the_visible_data_sync_location_while_the_workspace_scrolls
src/i18n/resources.test.ts	bundled i18n resources > contains the reviewed remaining-surface namespace inventory in both locales
src/i18n/resources.test.ts	bundled i18n resources > preserves the reviewed pre-Slice-5 Settings-origin inventory across the Common move
src/settings/MacroStorageSection.test.tsx	MacroStorageSection > renders five macro schedule rows and all three automation states
```

The UTF-8 byte-sorted eight-row stream SHA-256 is
`212646897e1a91212e719849066fb08ec21f3879ee86ac03e0d7bd96cbf17564`.
Task 0 must verify each full ID against the normalized base stream. A ninth
retained body edit or an edit to any frozen historical constant is a stop.

---

## 3. RED-first and evidence protocol

1. Every product task begins from a clean reviewed tip.
2. Add/rename the declared test nodes first and collect the exact staged stream.
3. Run the declared owners RED before editing product code. RED must fail on the
   missing reviewed behavior, not an import error in an existing module, stale
   fixture shape, missing dependency, timeout, network access, or test typo.
4. Keep RED changes uncommitted until the matching product implementation is
   GREEN; then commit tests and product atomically.
5. Each product commit is followed by a docs/evidence commit. Do not squash.
6. Each task packet contains raw list JSON, normalized streams, commands,
   versions, transcripts, owner pre/post SHA rows, changed-path projection,
   protected rows, and a root `SHA256SUMS` that covers every payload but itself.
7. Rejected commands/runs remain labelled rejected and cannot satisfy a gate.
8. Do not raise a timeout or weaken an assertion to manufacture GREEN.
9. No test may replace the real shared controller, scope predicate, cache, or
   section integration with a hand-written fake that bypasses the changed
   boundary. API responses may be hermetic fixtures.
10. Commit messages name the product behavior. Generic `cleanup` or `fix tests`
    subjects are rejected.

---

## 4. Execution tasks

### Task 0 - Re-ground and open evidence

1. Prove the reviewed plan tip has exact merge-base `e2ead437`, contains only
   docs changes, and leaves master clean/unmodified.
2. Record the design/plan/map full SHA-256 values and pinned tool versions.
3. Recollect frontend full, six-file focused, 15-file Settings, and backend
   collect-only streams. Require the exact Section 0.2 values.
4. Run the six focused frontend files sequentially and require `127 passed`.
5. Reconstruct the two-row removal/addition streams and all three Task 1 target
   streams using set subtraction/addition; do not trust the table prose.
6. Verify both removal IDs occur once and additions are absent.
7. Verify all 11 owned path identities and all 13 protected paths/aggregate.
8. Create
   `docs/superpowers/evidence/2026-08-14-settings-schedule-surface-ownership.md`
   with the base facts, exact commands, and explicit statement that no product
   byte or test body changed.
9. Update the plan/map status and commit one docs-only grounding commit.
10. Under the user-approved batch ruling, record Task 0 complete and continue
    to Task 1 without weakening any stop condition. Task 3 remains the combined
    independent implementation-review gate.

### Task 1 - Partition ownership and preserve latest-job facts

**Files:**

```text
apps/arkscope-web/src/settings/dataScheduleControls.test.tsx
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/settings/dataScheduleControls.tsx
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/settings/MacroStorageSection.tsx
```

1. Replace the two false IDs with the exact Section 2.1 additions; do not edit
   any other existing node body yet.
2. Collect exact Task 1 identities before running tests.
3. Run only both replacements. Require RED from duplicate/unscoped rows and
   absent Macro job facts; all pre-existing focused nodes must stay GREEN.
4. Add the required scope type/predicate and filter `Object.entries(schedule)`.
5. Remove `sourceIds`, `DataScheduleLocalError`, local missing-source markers,
   and `MACRO_SCHEDULE_SOURCE_IDS` completely.
6. Add stable controller `jobFacts`/`replaceJobFacts`, move `LastRun` to that
   source, and remove the table/row `jobs` prop.
7. Feed successful existing `health.jobs` reads from `DataSourcesSection` into
   that stable method without issuing or subscribing to another read.
8. Pass exact scopes from both callers and derive Macro enabled count with the
   same predicate.
9. Run the two replacement owners, six-file focused suite (`127 passed`), full
   collection identity, typecheck, and a structural request-owner census:
   exactly one provider, one schedule timer, one focus listener, and no new
   `getSchedule`/`getProvidersHealth` caller.
10. Commit atomically with subject similar to
    `refactor: assign one settings owner per schedule source`.
11. Append Task 1 evidence and commit docs-only. Under the batch ruling,
    continue to Task 2; Task 3 remains the combined review gate.

### Task 2 - Owner-specific copy and resource truth

**Files:**

```text
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/settings/MacroStorageSection.test.tsx
apps/arkscope-web/src/SettingsWorkspace.test.tsx
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
apps/arkscope-web/src/i18n/resources.test.ts
```

1. Change only the eight Section 2.4 retained node bodies to the reviewed
   owner-specific copy/resource expectations.
2. Run those eight owners RED against the generic current title and absent
   Macro title; a name mismatch or unrelated fixture failure is rejected RED.
3. Apply the exact Section 1.4 bilingual values and no others.
4. Add only `macroStorage.schedule.title` to `postSliceSettingsPaths`; update
   current counts `827 -> 828` and `1911 -> 1912`. Do not alter frozen values.
5. Require Task 1 identities to remain byte-identical.
6. Run six-file focused (`127 passed`), Settings (`249 passed`), frontend full
   sequential (`1177 passed`), typecheck, build, and i18n scanner
   (`36/20/0/20`).
7. Commit product/tests with subject similar to
   `fix: name settings schedule owners explicitly`.
8. Append Task 2 evidence, commit docs-only, and stop for review.

### Task 3 - Mutations and final admission

Run every mutation independently from the same clean Task 2 tip. The named
behavior owner must turn RED, then restore the complete changed owner file to
its exact pre-mutation SHA before proceeding:

| ID | Minimal live mutation | Required RED owner |
|---|---|---|
| M1 | make `scope` optional and render every source by default | partition replacement |
| M2 | classify Macro by current source IDs instead of `write_target` | future-source phases of partition replacement |
| M3 | drop an unknown non-Macro target from both tables | fail-visible union phase |
| M4 | restore `MACRO_SCHEDULE_SOURCE_IDS` for Macro rendering/count | future Macro source + hard-coded-tail census |
| M5 | remove the provider-health job-fact handoff | Provider replacement's Macro timestamp phase |
| M6 | issue another provider-health or schedule request from Macro | shared-controller/poll owner + browser request ledger |
| M7 | render the generic schedule title in either owner | exact bilingual copy owners |

A mutation against dead code, a source-string-only guard, a fake controller,
or an unrelated timeout is rejected. M6 must change the actual browser request
ledger; a textual request-count assertion without real fixture execution is
insufficient.

Final admission:

1. frontend collection `101 files / 1177 /
   90f56093290c70a27369296ec8d8c7de99d084a091134994ae6451bc8e45743b`;
2. six-file focused `127 /
   0d6eb25864d2c0a7a5ee76a9d05dacbc45e232106e62461a043b3d7196aac644`,
   all passing;
3. Settings projection `249 /
   ee6618dfc755f5ead79f6012967d3dda2c7a33f37ef87f62c5f98deff0f6c5cf`,
   all passing;
4. single-command sequential frontend full `1177/1177`;
5. typecheck, build, and i18n scanner `36/20/0/20`;
6. protected `13/13`, aggregate
   `b3b3ac3f2151d34bf3ce0e15a772ebb0a655e46fe63a43eccae142d4208602a1`;
7. backend collect-only `4394 /
   b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb`
   and zero `.py` byte change;
8. retired-tail census: zero `sourceIds`, `DataScheduleLocalError`,
   `MACRO_SCHEDULE_SOURCE_IDS`, optional/global schedule scope, or table-level
   `jobs` prop in product code;
9. one `DataScheduleControlsProvider`, one schedule timer/focus owner, the
   unchanged existing provider-health visible/warmup loader sites, and no new
   request owner;
10. the complete Section 1.5 desktop/mobile hermetic browser matrix;
11. branch changed paths are exactly the 11 owned product/test paths plus
    authorized governance/evidence files;
12. artifact manifest and generated-file cleanup leave the worktree clean.

Write the Task 3 evidence/admission docs commit and stop for complete
independent implementation review. Merge is not authorized by Task 3.

### Task 4 - Fast-forward merge and exact-master closeout

Only after independent implementation GREEN:

1. prove the reviewed implementation base is an ancestor of current master;
2. if master changed, stop and re-ground identities rather than merging through
   drift;
3. fast-forward only, with no push;
4. create a fresh exact-master worktree and rerun final full/focused/Settings
   collections and runtimes, typecheck, build, scanner, protected bytes,
   backend collect-only/no-Python boundary, structural censuses, and the full
   browser matrix under new artifact names;
5. verify exact product-byte equality between reviewed implementation tip and
   merged master;
6. write a docs-only closeout and stop for focused closeout review;
7. clean the implementation branch/worktree only after closeout GREEN.

---

## 5. Stop conditions

Stop before further product edits if any condition occurs:

1. any base/staged/final collection count, file count, or full SHA differs;
2. either removal is absent/duplicated, either addition already exists, or the
   ledger differs from exactly `-2/+2`;
3. a ninth retained existing node body or third node ID must change;
4. a product/test path outside Section 0.4 must change;
5. a protected byte or aggregate differs;
6. `write_target` is optional, inferred from source name, or replaced by a
   frontend registry;
7. any schedule source appears in both tables or neither table;
8. an unknown non-Macro target disappears instead of remaining visible;
9. a production all-source/optional scope, `sourceIds`, missing-source marker,
   or hard-coded Macro ID tail survives;
10. Macro enabled count and row rendering use different predicates;
11. preserving job facts requires another GET, cache key, controller, timer,
    listener, subscription, or polling interval;
12. a provider-health read failure clears previously admitted job facts;
13. removing duplicate rows loses latest status or completion-time facts;
14. any mount/idle/focus/visibility/local-read action emits a POST;
15. one idle interval produces other than one schedule GET;
16. a frozen i18n baseline count changes or the resource delta differs from
    one new path per locale;
17. CSS, layout, Settings registry/anchors, backend, DTO, route, scheduler,
    cadence, DB, provider, or production data must change;
18. RED comes from an existing-module import error, stale fixture, missing
    dependency, network access, timeout, or malformed test rather than the
    reviewed behavior;
19. a mutation leaves its semantic owner GREEN or restoration is not
    byte-exact;
20. browser fixture traffic escapes the hermetic sidecar or renders overlap,
    overflow, duplicate controls, or source loss;
21. full-suite failure occurs in an owned path or cannot be isolated as a
    pre-existing environment-specific failure without complete partitioned
    coverage;
22. master changes after implementation review, preventing a direct reviewed
    fast-forward; or
23. any merge, push, live call, production mutation, or destructive action is
    attempted before its explicit gate.

---

## 6. Review handoff

Independent plan review should mechanically rebuild:

1. all four base identities and all three target identities;
2. exact `-2/+2` set algebra and the Settings-projection exception;
3. all 11 owned identities and 13 protected identities/aggregate;
4. the eight retained body-evolution owners;
5. the `jobs` fact distinction and its one-request preservation design;
6. resource arithmetic and frozen-count behavior;
7. every mutation-to-owner binding; and
8. the sequence entry placing this slice before PG inventory.

Until that review returns GREEN, Task 0 and every product edit remain blocked.
