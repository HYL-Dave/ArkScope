# Data Sources Schedule Polling Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** IMPLEMENTED FOR REVIEW — automated gates complete; not merged or LIVE.

**Goal:** Keep the mounted Settings > Data Sources schedule status current across background scheduler starts and completions without requiring a manual refresh or repeatedly fetching unrelated Settings data.

**Architecture:** Add a small pure policy module that owns the 30-second idle / 5-second active cadence and deterministic schedule-lifecycle comparison. `DataSourcesSection` keeps its existing full `load()` for initial, manual, and lifecycle-boundary refreshes, while a new coalesced `/schedule`-only poll updates schedule truth continuously; a detected start or completion triggers exactly one full `load()` so Provider health, configuration, and Macro state catch up at the same boundary. Request sequencing prevents an older full or lightweight schedule response from replacing newer schedule truth.

**Tech Stack:** React 18.3, TypeScript 5.5, Vitest 4/jsdom fake timers, the existing additive `GET /schedule` API, and the shipped Settings/Data Sources presentation components.

---

## Implementation Ledger

- **Branch / base:** `codex/data-sources-schedule-polling-hotfix`, plan base `8ee85f7`.
- **Grounded baseline:** `SettingsProviderConfig.test.ts` is `19/19`; the full frontend is `54 files / 517 tests`.
- **Reviewed target accounting:** add `3` pure policy tests and `7` mounted integration tests, for exactly `+10/-0`; expected focused total `29`, expected full total `55 files / 527 tests`.
- **Backend equivalence:** this is frontend-only. `src/`, `data_sources/`, and backend `tests/` remain byte-identical to `8ee85f7`; canonical backend A/B is replaced by that constructive byte-identity proof.
- **Runtime safety:** no Gateway call, scheduler mutation, profile/market database mutation, provider probe, SA native-host health poll, or new endpoint is part of this hotfix.

### Implementation Evidence (2026-07-17)

- **Commits:** `e555284` opened the reviewed plan; `178730b` added the pure
  policy after the required module-resolution RED; `8862485` added the mounted
  polling path after all seven integration tests failed on the old behavior.
- **RED evidence:** the pure suite failed only because
  `./dataSourceSchedulePolling` did not exist. Before the Settings edit, the
  seven mounted tests failed in order because idle polling made `0` schedule
  calls instead of `1`, fast completion made `0` instead of `2`, the running
  copy never appeared, focus made `0` instead of `1`, timer/focus coalescing
  made `0` instead of `1`, the overlapping old full refresh remained the only
  schedule call instead of the required three-call sequence, and the unmount
  test could not start a focus poll.
- **GREEN evidence:** focused policy/presentation/Settings is `3 files / 33
  tests`; full frontend is exactly `55 files / 527 tests`; typecheck passes;
  production build passes with only the pre-existing chunk-size warning.
- **Exact accounting:** the test diff contains exactly ten added `it(...)`
  nodes and zero removed/renamed nodes: three pure policy tests plus seven
  mounted integration tests (`+10/-0` over `54 / 517`).
- **Boundaries:** `src/`, `data_sources/`, backend `tests/`, and frontend
  `api.ts` are byte-identical to `8ee85f7`; the changed frontend path set is
  exactly the reviewed four files; production `Settings.tsx` and the policy
  module contain zero `aria-live` matches. No Gateway request, scheduler run,
  provider probe, database mutation, or live-state fixture was used.
- **Test-shape corrections:** the stale-response test initially asserted an
  IBKR timestamp that the compact partial row does not render; it now uses the
  visible `running` polarity to prove the old response cannot replace newer
  truth. The unmount test now clears all four initial full-load counters before
  asserting no post-unmount related read. The file also explicitly enables the
  React act environment so asynchronous timer tests finish without warnings.
- **Reviewer observations retained:** sequence protection intentionally applies
  only to schedule truth; overlapping health/config/macro full-load legs keep
  their existing last-writer-wins behavior. `enabled` remains outside the
  lifecycle fingerprint because in-UI mutations already await a full load;
  an external change is still reflected by the lightweight schedule poll.

### Reviewer verification ✅ (Fable, 2026-07-17) — all reviewer gates closed

Independent reviewer verification on tip `de1e27f`: frontend
`55 files / 527 tests` PASS + typecheck + production build re-run in the
branch worktree (exact `+10/-0` over `54/517`; focused node list is exactly
`29`); byte-identity boundary empty (`src`, `data_sources`, backend `tests`,
and `apps/arkscope-web/src/api.ts` — the constructive A/B replacement);
changed-file set is exactly the four reviewed paths; the `aria-live` gate is
zero in production `Settings.tsx` and the policy module. Implementation
spot-read confirms the reviewed shape: `acceptSchedule` sequence guard
(strict `<` on a monotonically increasing ref), one coalescing
`schedulePollInFlightRef` held through any lifecycle-triggered full load, and
the dual-cadence effect keyed only on `[pollSchedule, schedulePollIntervalMs]`
so progress/backlog updates never restart the timer. The two ledgered
test-shape corrections (stale test asserting visible running polarity instead
of a timestamp the compact partial row never renders; unmount counter clears
plus explicit act environment) are mechanical test-fidelity fixes, not
behavior deviations, and both reviewer observations from plan review are
faithfully retained. All reviewer gates are closed; merge remains the user's
decision, followed by the plan's natural-boundary live check and Unit 2's
`content_availability` mini-design.

## Root Cause and Locked Decisions

1. `DataSourcesSection` currently fetches all state once on mount and installs its five-second timer only when the already-rendered schedule contains `running=true`. An app-owned background run that starts while the mounted view believes all sources are idle has no polling path that can discover it. The scheduler and durable SQLite state update correctly; the DOM remains stale until the existing manual `重新整理` action or remount.
2. Idle discovery polls only `GET /schedule` every `30_000ms`. Active observation polls that same endpoint every `5_000ms`. These values follow the existing Portfolio and Research dual-cadence pattern; they are fixed constants, not user settings.
3. Window `focus` performs the same lightweight schedule refresh immediately. It does not probe SA extension health and does not fetch all Settings resources unless it discovers a lifecycle boundary.
4. A lifecycle boundary is any per-source start (`running false -> true`), stop (`true -> false`), durable completion revision (`durable_state.updated_at`, `last_attempt`, `last_status`, or source `last_attempt_at` changes), or source-set change. A progress-only or body-backlog-presentation-only change is not a boundary.
5. A lightweight poll always accepts fresh schedule data. If and only if that accepted data crosses a lifecycle boundary, it invokes the existing full `load()` once. This updates Provider health/jobs, Provider config, and Macro snapshot without turning the idle 30-second loop into four-endpoint polling.
6. The lifecycle comparison must catch a short run that starts and finishes entirely between idle polls: `running=false` can remain unchanged while `durable_state.updated_at` advances.
7. Only one lightweight schedule request may be in flight. Timer and focus triggers coalesce onto it. Full loads may overlap, but one monotonically increasing schedule-request sequence ensures an older response cannot overwrite newer schedule state.
8. A passive schedule-read failure preserves prior schedule truth and does not invent an empty state. Initial/manual/full-load failures retain the existing visible aggregate error behavior.
9. The existing `重新整理` button remains. No duplicate row-level refresh control is added.
10. Polling updates do not add `aria-live`; the stabilization rule against repeated polling announcements remains intact.
11. Unit 2 (`content_availability`) is excluded. It receives a separate mini-design and plan after this hotfix: derived-at-read content depth, additive NEWS DTO, legacy-projection mapping, old-sidecar compatibility, badge/filter UI, and the 19 normalized-vs-legacy gap all remain unchanged here.

## Non-Goals

- No scheduler cadence, due-time, retry, lock, continuation, or run-status behavior changes.
- No backend route/model/schema changes and no `/schedule` response-shape changes.
- No polling outside the mounted Data Sources section.
- No continuous polling of Provider health, Provider config, Macro, SA extension health, NEWS, or normalized-news body state.
- No new toast, notification, live region, progress UI, CSS, breakpoint, or Design Kit change.
- No NEWS `content_availability`, headline-only badge, filter, search behavior, or normalized/legacy projection repair.
- No forced IBKR News run for verification.

## Grounded Baseline

- `apps/arkscope-web/src/Settings.tsx:1383-1399` defines one full `load()` over `getSchedule()`, `getProvidersHealth()`, `getProvidersConfig()`, and `getMacroSnapshot()`.
- `apps/arkscope-web/src/Settings.tsx:1401-1403` performs the only unconditional fetch on mount.
- `apps/arkscope-web/src/Settings.tsx:1422-1428` installs a five-second interval only when `anyRunning` is already true. There is no idle timer or focus listener.
- `apps/arkscope-web/src/Settings.tsx:1711-1713` already renders a full manual `重新整理` control.
- `getSchedule()` has an eight-second client timeout and returns all durable schedule truth needed for transition detection; no backend addition is necessary.
- `PortfolioCapturePanel.tsx` already uses a 30-second idle / 2-second active loop and request ordering. `shell/researchWork.ts` already uses 30-second discovery / 5-second active timers, focus refresh, and in-flight coalescing. This hotfix uses the same operational shape without coupling those domains.
- SA extension health is intentionally fetched once on mount or by its own `重新檢查` action because it starts a native-host subprocess. It must remain outside both new poll cadences.
- `SettingsProviderConfig.test.ts` already supplies a mounted Settings harness and mutable `scheduleRunning`, `scheduleProgress`, and durable IBKR fixtures. It is the correct integration owner.

## File Structure

- Create `apps/arkscope-web/src/dataSourceSchedulePolling.ts`: pure cadence and lifecycle-boundary policy; no React and no network calls.
- Create `apps/arkscope-web/src/dataSourceSchedulePolling.test.ts`: exact policy pins for idle/active cadence, lifecycle transitions, and progress-only stability.
- Modify `apps/arkscope-web/src/Settings.tsx`: sequenced schedule acceptance, one coalesced lightweight poll, dual cadence, focus listener, and lifecycle-triggered full load.
- Modify `apps/arkscope-web/src/SettingsProviderConfig.test.ts`: mounted timer/focus/failure/sequencing/cleanup integration contracts.
- Modify after verification: this plan ledger/status and `docs/design/PROJECT_PRIORITY_MAP.md` review-ready entry.

---

### Task 1: Pure Schedule Polling Policy

**Files:**
- Create: `apps/arkscope-web/src/dataSourceSchedulePolling.ts`
- Create: `apps/arkscope-web/src/dataSourceSchedulePolling.test.ts`

**Interfaces:**
- Consumes: `Record<string, ScheduleSourceState> | null`.
- Produces: `DATA_SOURCE_SCHEDULE_IDLE_POLL_MS`, `DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS`, `dataSourceSchedulePollMs()`, and `dataSourceScheduleLifecycleChanged()`.
- Does not consume React, fetch, wall-clock time, DOM state, Provider health, or source-specific labels.

- [x] **Step 1: Write the three failing policy tests**

Create `apps/arkscope-web/src/dataSourceSchedulePolling.test.ts` exactly with a complete source factory:

```ts
import { describe, expect, it } from "vitest";

import type { ScheduleSourceState } from "./api";
import {
  DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS,
  DATA_SOURCE_SCHEDULE_IDLE_POLL_MS,
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
} from "./dataSourceSchedulePolling";

function source(over: Partial<ScheduleSourceState> = {}): ScheduleSourceState {
  return {
    label: "IBKR 新聞",
    description: "IBKR market-news collector",
    ibkr: true,
    provider_fetch: true,
    source_mode: "direct_local",
    write_target: "market_data.db",
    source_badges: [],
    retired: false,
    retired_reason: null,
    enabled: true,
    interval_minutes: 120,
    default_interval_minutes: 120,
    running: false,
    progress: null,
    last_attempt_at: "2026-07-17T10:00:00Z",
    last_result: null,
    gap_planned: false,
    durable_state: {
      last_status: "succeeded",
      last_error: null,
      continuation: null,
      last_attempt: "2026-07-17T10:00:00Z",
      updated_at: "2026-07-17T10:01:00Z",
    },
    job_name: "collect.ibkr_news",
    ...over,
  };
}

describe("Data Sources schedule polling policy", () => {
  it("uses a 30 second idle cadence and a 5 second active cadence", () => {
    expect(dataSourceSchedulePollMs(null)).toBe(DATA_SOURCE_SCHEDULE_IDLE_POLL_MS);
    expect(dataSourceSchedulePollMs({ ibkr_news: source() }))
      .toBe(DATA_SOURCE_SCHEDULE_IDLE_POLL_MS);
    expect(dataSourceSchedulePollMs({
      polygon_news: source({ label: "Polygon", running: false }),
      ibkr_news: source({ running: true }),
    })).toBe(DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS);
    expect(DATA_SOURCE_SCHEDULE_IDLE_POLL_MS).toBe(30_000);
    expect(DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS).toBe(5_000);
  });

  it("detects starts stops fast completions and source-set changes", () => {
    const idle = { ibkr_news: source() };
    const running = { ibkr_news: source({ running: true }) };
    const completedBetweenPolls = {
      ibkr_news: source({
        running: false,
        last_attempt_at: "2026-07-17T10:30:00Z",
        durable_state: {
          last_status: "partial",
          last_error: null,
          continuation: null,
          last_attempt: "2026-07-17T10:30:00Z",
          updated_at: "2026-07-17T10:31:00Z",
        },
      }),
    };

    expect(dataSourceScheduleLifecycleChanged(null, idle)).toBe(false);
    expect(dataSourceScheduleLifecycleChanged(idle, running)).toBe(true);
    expect(dataSourceScheduleLifecycleChanged(running, completedBetweenPolls)).toBe(true);
    expect(dataSourceScheduleLifecycleChanged(idle, completedBetweenPolls)).toBe(true);
    expect(dataSourceScheduleLifecycleChanged(idle, {
      ...idle,
      polygon_news: source({ label: "Polygon" }),
    })).toBe(true);
  });

  it("ignores progress and presentation-only changes within one lifecycle revision", () => {
    const before = { ibkr_news: source({ running: true }) };
    const after = {
      ibkr_news: source({
        running: true,
        progress: { done: 17, total: 149, current: "NVDA" },
        last_result: {
          source: "ibkr_news",
          status: "partial",
          collect: {
            status: "partial",
            body_backlog: { status: "ok", scheduled_later: 13 },
          },
        },
      }),
    };

    expect(dataSourceScheduleLifecycleChanged(before, after)).toBe(false);
    expect(dataSourceScheduleLifecycleChanged(
      { polygon_news: source({ label: "Polygon" }), ibkr_news: before.ibkr_news },
      { ibkr_news: after.ibkr_news, polygon_news: source({ label: "Polygon" }) },
    )).toBe(false);
  });
});
```

- [x] **Step 2: Run the policy test and verify RED**

Run from `apps/arkscope-web`:

```bash
npm test -- src/dataSourceSchedulePolling.test.ts
```

Expected: FAIL because `./dataSourceSchedulePolling` does not exist. The failure must be module resolution, not a malformed fixture or unrelated test error.

- [x] **Step 3: Implement the minimal pure policy**

Create `apps/arkscope-web/src/dataSourceSchedulePolling.ts`:

```ts
import type { ScheduleSourceState } from "./api";

export const DATA_SOURCE_SCHEDULE_IDLE_POLL_MS = 30_000;
export const DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS = 5_000;

export type DataSourceScheduleMap = Record<string, ScheduleSourceState>;

export function dataSourceSchedulePollMs(
  sources: DataSourceScheduleMap | null,
): number {
  return sources && Object.values(sources).some((source) => source.running)
    ? DATA_SOURCE_SCHEDULE_ACTIVE_POLL_MS
    : DATA_SOURCE_SCHEDULE_IDLE_POLL_MS;
}

function lifecycleFingerprint(sources: DataSourceScheduleMap): string {
  return JSON.stringify(Object.keys(sources).sort().map((sourceId) => {
    const source = sources[sourceId];
    return [
      sourceId,
      source.running,
      source.last_attempt_at ?? null,
      source.durable_state?.last_status ?? null,
      source.durable_state?.last_attempt ?? null,
      source.durable_state?.updated_at ?? null,
    ];
  }));
}

export function dataSourceScheduleLifecycleChanged(
  previous: DataSourceScheduleMap | null,
  next: DataSourceScheduleMap,
): boolean {
  if (previous === null) return false;
  return lifecycleFingerprint(previous) !== lifecycleFingerprint(next);
}
```

The fingerprint deliberately excludes progress, backlog counts, labels, descriptions, and UI presentation fields. Source IDs are sorted so response object insertion order cannot manufacture a transition.

- [x] **Step 4: Run the policy and existing presentation suites**

```bash
npm test -- src/dataSourceSchedulePolling.test.ts src/dataSourcesPresentation.test.ts
```

Expected: `2 files / 7 tests` pass (`3` new polling tests plus the existing `4` presentation tests).

- [x] **Step 5: Commit the pure policy**

```bash
git add apps/arkscope-web/src/dataSourceSchedulePolling.ts \
  apps/arkscope-web/src/dataSourceSchedulePolling.test.ts
git commit -m "test: define data source schedule polling policy"
```

---

### Task 2: Mount Dual-Cadence Polling in Data Sources

**Files:**
- Modify: `apps/arkscope-web/src/Settings.tsx:1-110,1372-1430,1460-1475,1702-1714`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts:1-110,175-420,423-765`
- Test: `apps/arkscope-web/src/dataSourceSchedulePolling.test.ts`

**Interfaces:**
- `load()` remains the full four-leg Settings refresh used by mount, manual refresh, mutations, and accepted lifecycle transitions.
- `pollSchedule()` calls only `getSchedule()`, coalesces concurrent timer/focus requests, accepts sequenced schedule truth, and calls `load()` after a detected boundary.
- The existing DOM, labels, row controls, API DTO, and schedule mutation paths remain unchanged.

- [x] **Step 1: Extend the mounted harness and add seven failing integration tests**

In `SettingsProviderConfig.test.ts`, import the mocked API functions as values:

```ts
import {
  getMacroSnapshot,
  getProvidersConfig,
  getProvidersHealth,
  getSchedule,
  type ModelCatalog,
  type ModelTask,
  type ProvidersHealthResponse,
  type TaskRoute,
} from "./api";
```

Keep the existing `scheduleRunning` / `scheduleProgress` fields (they already
drive the Polygon fixture) and add only the two missing IBKR lifecycle fields
to `mocked`:

```ts
scheduleLastAttemptAt: "2026-07-14T10:00:00Z",
scheduleUpdatedAt: "2026-07-14T10:01:00Z",
```

Use the two new fields in the `ibkr_news` schedule fixture. Replace the
`last_attempt` and `updated_at` literals in **all three** durable-state branches
(`succeeded|entitlement`, `partial`, and legacy), not only the branch used by
one test. Leave `running` / `progress` on the existing Polygon fixture so the
pre-existing progress test retains its exact owner:

```ts
last_attempt_at: mocked.scheduleLastAttemptAt,
// ...inside every durable_state branch...
last_attempt: mocked.scheduleLastAttemptAt,
updated_at: mocked.scheduleUpdatedAt,
```

Reset them and fake timers in `afterEach`:

```ts
mocked.scheduleRunning = false;
mocked.scheduleProgress = null;
mocked.scheduleLastAttemptAt = "2026-07-14T10:00:00Z";
mocked.scheduleUpdatedAt = "2026-07-14T10:01:00Z";
vi.useRealTimers();
```

Add this call-counter helper after `renderDataSources()`:

```ts
function clearDataSourceReadMocks() {
  vi.mocked(getSchedule).mockClear();
  vi.mocked(getProvidersHealth).mockClear();
  vi.mocked(getProvidersConfig).mockClear();
  vi.mocked(getMacroSnapshot).mockClear();
}
```

Append these seven tests to the existing `describe` block:

```ts
it("polls only schedule after thirty idle seconds without a live region", async () => {
  vi.useFakeTimers();
  await renderDataSources();
  clearDataSourceReadMocks();

  await act(async () => { await vi.advanceTimersByTimeAsync(29_999); });
  expect(getSchedule).not.toHaveBeenCalled();

  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(getSchedule).toHaveBeenCalledTimes(1);
  expect(getProvidersHealth).not.toHaveBeenCalled();
  expect(getProvidersConfig).not.toHaveBeenCalled();
  expect(getMacroSnapshot).not.toHaveBeenCalled();
  expect(host!.querySelector("[aria-live]")).toBeNull();
});

it("detects a fast idle-to-idle completion and refreshes related state once", async () => {
  vi.useFakeTimers();
  await renderDataSources();
  clearDataSourceReadMocks();
  mocked.ibkrBodyBacklogMode = "succeeded";
  mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
  mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";

  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });

  expect(getSchedule).toHaveBeenCalledTimes(2); // lightweight read + full load
  expect(getProvidersHealth).toHaveBeenCalledTimes(1);
  expect(getProvidersConfig).toHaveBeenCalledTimes(1);
  expect(getMacroSnapshot).toHaveBeenCalledTimes(1);
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("IBKR 新聞"));
  expect(row?.textContent).toContain("上次成功");
});

it("switches to five second polling while running and back to idle after completion", async () => {
  vi.useFakeTimers();
  await renderDataSources();
  clearDataSourceReadMocks();

  mocked.scheduleRunning = true;
  mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
  expect(host!.textContent).toContain("執行中，自動更新");

  clearDataSourceReadMocks();
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  expect(getSchedule).toHaveBeenCalledTimes(1);
  expect(getProvidersHealth).not.toHaveBeenCalled();

  mocked.scheduleRunning = false;
  mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";
  await act(async () => { await vi.advanceTimersByTimeAsync(5_000); });
  expect(getProvidersHealth).toHaveBeenCalledTimes(1);
  expect(host!.textContent).not.toContain("執行中，自動更新");

  clearDataSourceReadMocks();
  await act(async () => { await vi.advanceTimersByTimeAsync(29_999); });
  expect(getSchedule).not.toHaveBeenCalled();
  await act(async () => { await vi.advanceTimersByTimeAsync(1); });
  expect(getSchedule).toHaveBeenCalledTimes(1);
});

it("refreshes schedule on focus and full-loads only when lifecycle truth changes", async () => {
  await renderDataSources();
  clearDataSourceReadMocks();

  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(getSchedule).toHaveBeenCalledTimes(1);
  expect(getProvidersHealth).not.toHaveBeenCalled();

  clearDataSourceReadMocks();
  mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
  mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";
  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(getSchedule).toHaveBeenCalledTimes(2);
  expect(getProvidersHealth).toHaveBeenCalledTimes(1);
  expect(getProvidersConfig).toHaveBeenCalledTimes(1);
  expect(getMacroSnapshot).toHaveBeenCalledTimes(1);
});

it("coalesces timer and focus reads and preserves prior truth on poll failure", async () => {
  vi.useFakeTimers();
  await renderDataSources();
  const before = host!.textContent;
  clearDataSourceReadMocks();
  let rejectPoll: ((reason?: unknown) => void) | null = null;
  vi.mocked(getSchedule).mockImplementationOnce(() => new Promise((_, reject) => {
    rejectPoll = reject;
  }));

  await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(getSchedule).toHaveBeenCalledTimes(1);

  await act(async () => {
    rejectPoll!(new Error("temporary schedule read failure"));
    await Promise.resolve();
  });
  expect(host!.textContent).toBe(before);
  expect(getProvidersHealth).not.toHaveBeenCalled();
});

it("does not let an older full refresh replace newer schedule truth", async () => {
  await renderDataSources();
  const staleSchedule = await getSchedule();
  clearDataSourceReadMocks();
  let resolveOldFull!: (value: Awaited<ReturnType<typeof getSchedule>>) => void;
  vi.mocked(getSchedule).mockImplementationOnce(() => new Promise((resolve) => {
    resolveOldFull = resolve;
  }));

  const refresh = Array.from(host!.querySelectorAll("button")).find((button) =>
    button.textContent?.includes("重新整理"));
  if (!refresh) throw new Error("missing Data Sources refresh button");
  await act(async () => {
    refresh.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
    await Promise.resolve();
  });
  expect(getSchedule).toHaveBeenCalledTimes(1);

  mocked.scheduleLastAttemptAt = "2026-07-17T10:30:00Z";
  mocked.scheduleUpdatedAt = "2026-07-17T10:31:00Z";
  await act(async () => {
    window.dispatchEvent(new Event("focus"));
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(getSchedule).toHaveBeenCalledTimes(3); // old full + poll + lifecycle full

  await act(async () => {
    resolveOldFull(staleSchedule);
    await Promise.resolve();
  });
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("IBKR 新聞"));
  expect(row?.textContent).toContain(formatSystemTimestamp("2026-07-17T10:30:00Z"));
  expect(row?.textContent).not.toContain(formatSystemTimestamp("2026-07-14T10:00:00Z"));
});

it("removes idle timers and focus listeners and ignores a finishing poll after unmount", async () => {
  vi.useFakeTimers();
  await renderDataSources();
  let resolvePoll: ((value: Awaited<ReturnType<typeof getSchedule>>) => void) | null = null;
  vi.mocked(getSchedule).mockClear();
  vi.mocked(getSchedule).mockImplementationOnce(() => new Promise((resolve) => {
    resolvePoll = resolve;
  }));

  await act(async () => { window.dispatchEvent(new Event("focus")); });
  expect(getSchedule).toHaveBeenCalledTimes(1);

  act(() => root!.unmount());
  root = null;
  await act(async () => {
    resolvePoll!({ sources: {} });
    await Promise.resolve();
  });
  await act(async () => { await vi.advanceTimersByTimeAsync(60_000); });
  await act(async () => { window.dispatchEvent(new Event("focus")); });

  expect(getSchedule).toHaveBeenCalledTimes(1);
  expect(getProvidersHealth).not.toHaveBeenCalled();
});
```

The integration delta is exactly `+7`. Do not rename, delete, or weaken any of the existing 19 tests.

- [x] **Step 2: Run the focused tests and verify RED for behavior**

```bash
npm test -- src/dataSourceSchedulePolling.test.ts src/SettingsProviderConfig.test.ts
```

Expected collection: `29` tests. The `3` policy tests and existing `19` Settings tests pass; the `7` new mounted tests fail because idle/focus polling, coalescing, transition refresh, stale-response rejection, and cleanup do not yet exist. Failures must not come from timer leakage or malformed fixtures.

- [x] **Step 3: Wire sequenced schedule acceptance and the dual-cadence poll**

Import the policy in `Settings.tsx`:

```ts
import {
  dataSourceScheduleLifecycleChanged,
  dataSourceSchedulePollMs,
  type DataSourceScheduleMap,
} from "./dataSourceSchedulePolling";
```

Inside `DataSourcesSection`, directly after state declarations, add only the refs needed to preserve current truth and coalesce lightweight reads:

```ts
const scheduleRef = useRef<DataSourceScheduleMap | null>(null);
const scheduleRequestSequenceRef = useRef(0);
const acceptedScheduleSequenceRef = useRef(0);
const schedulePollInFlightRef = useRef<Promise<void> | null>(null);
const dataSourcesMountedRef = useRef(true);
```

Install one mount-lifetime guard before the initial `load()` effect. It is not
poll cadence state and must not be reset when `anyRunning` changes:

```ts
useEffect(() => {
  dataSourcesMountedRef.current = true;
  return () => {
    dataSourcesMountedRef.current = false;
  };
}, []);
```

Add one sequenced acceptance function before `load()`:

```ts
const acceptSchedule = useCallback((
  next: DataSourceScheduleMap,
  sequence: number,
): { accepted: boolean; lifecycleChanged: boolean } => {
  if (sequence < acceptedScheduleSequenceRef.current) {
    return { accepted: false, lifecycleChanged: false };
  }
  acceptedScheduleSequenceRef.current = sequence;
  const previous = scheduleRef.current;
  scheduleRef.current = next;
  setSchedule(next);
  return {
    accepted: true,
    lifecycleChanged: dataSourceScheduleLifecycleChanged(previous, next),
  };
}, []);
```

Evolve the existing full `load()` so its schedule leg receives a sequence at request start and uses `acceptSchedule`; keep the other three legs and aggregate error behavior unchanged:

```ts
const load = useCallback(async () => {
  const scheduleSequence = ++scheduleRequestSequenceRef.current;
  const [rs, rh, rc, rm] = await Promise.allSettled([
    getSchedule(), getProvidersHealth(), getProvidersConfig(), getMacroSnapshot(),
  ]);
  if (!dataSourcesMountedRef.current) return;
  if (rs.status === "fulfilled") {
    acceptSchedule(rs.value.sources, scheduleSequence);
  }
  if (rh.status === "fulfilled") setHealth(rh.value);
  if (rc.status === "fulfilled") {
    setCfg(rc.value.providers);
    setCfgSetup(rc.value.setup);
  }
  if (rm.status === "fulfilled") setMacroSnapshot(rm.value);
  const bad = [rs, rh, rc, rm].filter(
    (result): result is PromiseRejectedResult => result.status === "rejected",
  );
  setErr(bad.length
    ? bad.map((result) => (
      result.reason instanceof Error ? result.reason.message : String(result.reason)
    )).join("；")
    : null);
}, [acceptSchedule]);
```

Add the lightweight poll after `load()`:

```ts
const pollSchedule = useCallback((): Promise<void> => {
  if (schedulePollInFlightRef.current) return schedulePollInFlightRef.current;
  const sequence = ++scheduleRequestSequenceRef.current;
  const request = (async () => {
    try {
      const next = await getSchedule();
      if (!dataSourcesMountedRef.current) return;
      const accepted = acceptSchedule(next.sources, sequence);
      if (accepted.accepted && accepted.lifecycleChanged) {
        await load();
      }
    } catch {
      // Passive polling preserves the last accepted schedule truth.
    }
  })().finally(() => {
    if (schedulePollInFlightRef.current === request) {
      schedulePollInFlightRef.current = null;
    }
  });
  schedulePollInFlightRef.current = request;
  return request;
}, [acceptSchedule, load]);
```

Replace the current running-only polling effect with dual cadence plus focus refresh:

```ts
const anyRunning = !!schedule && Object.values(schedule).some((source) => source.running);
const schedulePollIntervalMs = dataSourceSchedulePollMs(schedule);
useEffect(() => {
  const timer = window.setInterval(
    () => { void pollSchedule(); },
    schedulePollIntervalMs,
  );
  const onFocus = () => { void pollSchedule(); };
  window.addEventListener("focus", onFocus);
  return () => {
    window.clearInterval(timer);
    window.removeEventListener("focus", onFocus);
  };
}, [pollSchedule, schedulePollIntervalMs]);
```

`schedulePollIntervalMs` has only the stable values `30_000` and `5_000`, so
the effect recreates the timer exactly when cadence changes. Do not add
`schedule` itself to the dependency array: progress/body-backlog updates must
not restart the timer. The mount guard prevents the new passive request path
from publishing schedule state or launching a lifecycle full-load after the
section has unmounted.

Keep the initial `void load()` effect, extension-health effect, all mutation `await load()` calls, and the existing refresh button unchanged. Do not add `aria-live` anywhere.

- [x] **Step 4: Run the focused tests and verify GREEN**

```bash
npm test -- src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/SettingsProviderConfig.test.ts
```

Expected: `3 files / 33 tests` pass (`3` polling + `4` presentation + `26` Settings). There must be no fake-timer leak warning, state-update-after-unmount warning, or unhandled rejected Promise.

- [x] **Step 5: Commit mounted polling**

```bash
git add apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "fix: refresh background schedule status"
```

---

### Task 3: Boundary and Regression Verification

**Files:**
- Verify only; no product-file edits.

- [x] **Step 1: Prove the backend and API contract are byte-identical**

```bash
git diff --exit-code 8ee85f7 -- src data_sources tests
git diff --exit-code 8ee85f7 -- apps/arkscope-web/src/api.ts
```

Expected: both commands produce no output and exit zero. This is the constructive backend-equivalence gate; do not run or claim canonical backend A/B for identical trees.

- [x] **Step 2: Run static scope and accessibility ratchets**

```bash
git diff --name-only 8ee85f7 -- apps/arkscope-web/src
if rg -n "aria-live" \
  apps/arkscope-web/src/Settings.tsx \
  apps/arkscope-web/src/dataSourceSchedulePolling.ts; then
  exit 1
fi
```

Expected product/test paths are exactly:

```text
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/dataSourceSchedulePolling.test.ts
apps/arkscope-web/src/dataSourceSchedulePolling.ts
```

The `aria-live` gate must produce no matches. No CSS, API DTO, backend, NEWS, scheduler, or Design Kit path may appear.

- [x] **Step 3: Run focused and full frontend verification**

From `apps/arkscope-web`:

```bash
npm test -- src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/SettingsProviderConfig.test.ts
npm test
npm run typecheck
npm run build
```

Expected:

- focused `3 files / 33 tests`;
- full `55 files / 527 tests`, exactly `+10/-0` over `54 / 517`;
- typecheck passes;
- build passes with no new warning family (the existing chunk-size warning is acceptable).

- [x] **Step 4: Reconcile exact test-node accounting**

```bash
npm test -- --reporter=verbose \
  src/dataSourceSchedulePolling.test.ts \
  src/SettingsProviderConfig.test.ts
```

Expected: all `29` named nodes pass. Compare the node list against base: `3` pure policy additions and `7` Settings additions, with zero removed/renamed nodes. Stop if the delta is not exactly `+10/-0`.

- [x] **Step 5: Commit no product changes**

No commit is created in this step. If any verification required a product edit, return to the owning RED test and produce a separate reviewed fix commit; do not hide it in closeout docs.

---

### Task 4: Review-Ready Ledger and Handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-07-17-data-sources-schedule-polling-hotfix.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Record implementation evidence without claiming merge or LIVE**

Change the plan status to `IMPLEMENTED FOR REVIEW` and record:

- code commit IDs;
- the exact RED failure reasons for all ten new tests;
- focused `33`, full `55 / 527`, typecheck, build, static, and byte-identity results;
- exact `+10/-0` node accounting;
- any deviation from the reviewed plan;
- confirmation that no Gateway request, profile DB mutation, or live scheduler trigger was used.

- [x] **Step 2: Insert the review-ready map entry at the top of the Decision Log**

The entry must say this bounded frontend hotfix is implemented for review, Unit 2 remains queued, and P2.8 Slice 3 remains paused until both units complete. It must not mark the hotfix merged/live.

- [x] **Step 3: Commit review-ready docs**

```bash
git add docs/superpowers/plans/2026-07-17-data-sources-schedule-polling-hotfix.md \
  docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark schedule polling hotfix review-ready"
```

- [x] **Step 4: Stop for independent review**

Report branch tip, commit list, exact test accounting, and the four product/test paths. Do not merge, mark LIVE, remove the worktree, begin Unit 2, or resume P2.8 Slice 3 before independent review and user approval.

## Reviewer Focus

1. The idle poll calls only `/schedule`; it does not turn `load()` into a 30-second four-leg poll.
2. A run that starts and finishes between idle polls is detected from durable revision fields.
3. Progress-only updates do not trigger repeated full loads.
4. A lifecycle transition triggers exactly one full load, including Provider health/config/Macro refresh.
5. Timer and focus triggers share one in-flight lightweight request.
6. The mounted stale-response test proves schedule sequencing across overlapping lightweight/full requests.
7. Passive failure preserves prior truth and creates no false empty/error reset.
8. Running cadence is five seconds; idle cadence is thirty seconds; unmount removes both timer and focus listener.
9. The existing manual refresh remains and no `aria-live` polling announcement is introduced.
10. Unit 2 content-depth/API/search/filter work is absent.

## Stop Conditions

Stop and report instead of widening scope if:

- `/schedule` lacks a stable durable field capable of identifying a fast completion;
- lifecycle detection requires a backend run ID or API addition;
- idle polling causes SA extension native-host probes or any provider/Gateway call;
- a stale response can still overwrite a newer mutation or schedule observation;
- the timer/focus tests require production-only timing sleeps instead of fake timers;
- any backend/API/CSS/NEWS/Design Kit file changes;
- test accounting is not exactly `+10/-0`; or
- the fix requires implementing `content_availability` before it can work.

## Post-Review Merge Closeout

After independent review returns GREEN and the user approves merge:

1. fast-forward `master` only;
2. rerun focused `33`, full frontend `55 / 527`, typecheck, build, byte-identity, and `aria-live` gates on the merged tree;
3. restart the desktop app so the new renderer code is loaded;
4. leave Data Sources mounted through one natural background scheduler boundary and verify the row updates within the 30-second idle discovery bound without clicking `重新整理`; do not force an IBKR News run for this gate;
5. mark this plan LIVE and add the merge/live decision-log entry;
6. open Unit 2's mini-design for derived `content_availability`; and
7. retain P2.8 Slice 3 behind Unit 2 as already sequenced.
