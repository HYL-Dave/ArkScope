# IBKR News Partial Status Hotfix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: IMPLEMENTED FOR REVIEW — 2026-07-15. NOT MERGED. DURABLE RETRY REMAINS PENDING.**

## Implementation Ledger

- Branch: `codex/ibkr-news-partial-hotfix`; plan base `3d3c835`; behavioral base `e5ccd12`; code head `de23f61`; review head is the docs commit containing this ledger.
- TDD RED: focused collection was `40`; all seven new cases failed for the intended existing output `部分完成（待補抓 0）`, while all 33 baseline cases passed. The mounted row received process-local count `99` and durable count `10` but rendered the old zero label.
- TDD GREEN: focused `2 files / 40 tests`; full frontend `44 files / 419 tests`, exactly `+7/-0` over `44/412`; typecheck passed; production build passed with only the existing `>500 kB` chunk warning.
- Boundaries: `src/`, `data_sources/`, and backend `tests/` are byte-identical to `e5ccd12`; the only frontend product/test paths are `api.ts`, `marketDataDisplay.ts`, `marketDataDisplay.test.ts`, and `SettingsProviderConfig.test.ts`; `Settings.tsx` is byte-identical. `api.ts` has interface/type-only hunks.
- Privacy/static gates: frontend has zero `deferred_body_ids` / provider-article-id matches and zero `待補抓 0` matches. The single production `schedulerStateLabel` consumer remains the generic existing Settings call.
- Live display gate used one scheduler-disabled branch sidecar and the real profile DB without triggering News or Gateway work. The natural durable row was still partial with `deferred_body_count=2`; all `1440x900`, `1024x768`, and `390x844` views rendered `2 篇內文待後續處理`, retained ordinary `Run`, exposed no `補抓`, had no cell overlap or page-level horizontal overflow, and used the existing table scroll owner at narrow widths.
- Restart gate: after the sidecar restarted, process-local `last_result` was `null`, while SQLite preserved the same `last_attempt`, `updated_at`, and body count `2`; reloading all three viewports rendered the same durable explanation. No profile row was manufactured or modified for this gate.
- Plan deviations: none. Canonical backend A/B was intentionally replaced by the stronger byte-identity proof approved in plan review.

**Goal:** Make the Data Sources schedule row describe IBKR News count-only partial work truthfully, without inventing `待補抓 0` or exposing a manual continuation action that the sanitized worker cannot honor.

**Architecture:** Widen only the frontend description of the schedule response the backend already returns, then make `schedulerStateLabel()` distinguish actionable persisted ticker continuation from non-actionable sanitized ticker/body/cursor counts. Durable `last_result` is the sole count authority because it survives restart; Hotfix A deliberately ignores process-local `last_result` because the two DTO branches share no run ID that could prove they represent the same attempt. The existing Settings call already supplies durable state, so no source-specific component branch or new runtime wiring is required.

**Tech Stack:** TypeScript 5.5, React 18, Vitest 4/jsdom, the existing `/schedule` response and Settings house harness.

## Global Constraints

- Authority: `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md`, especially §3.
- This is a frontend-only display hotfix. `src/`, `data_sources/`, and backend `tests/` must remain byte-identical to behavioral base `e5ccd12`.
- Do not change scheduler outcomes, continuation persistence, retry timing, attempt limits, worker sanitization, Gateway calls, profile DB, or market DB.
- Preserve the actionable price-backfill contract: non-empty durable `continuation.deferred[]` renders `部分完成（待補抓 N）` and `needsContinue=true`.
- Count-only normalized-news continuation is informational: it never sets `needsContinue=true` and never renders a `補抓` button.
- Durable `last_result.collect.continuation` is the only source of sanitized counts. When it is absent, invalid, or malformed, fail closed to exactly `部分完成`; do not infer same-run identity from process-local timestamps.
- Missing, zero, negative, non-finite, or malformed count values render no numeric promise.
- No provider article ID, `deferred_body_ids`, licensed body, or raw worker payload may enter frontend types, logs, fixtures, or DOM.
- Do not add a backend field, endpoint, API call, button, polling loop, CSS class, breakpoint, generic primitive, or Data Sources layout change.
- Hotfix A may merge independently. It does not claim durable body retry is fixed; that remains a separate reviewed plan.

---

## Grounded Baseline

- `apps/arkscope-web/src/marketDataDisplay.ts:105-124` currently computes `durable?.continuation?.deferred?.length ?? 0`, so a partial result with no actionable continuation becomes the false label `部分完成（待補抓 0）`.
- `src/news_normalized/ibkr_cli.py:67-78` already sanitizes continuation into only `deferred_ticker_count`, `deferred_body_count`, and `has_cursor`.
- `src/service/data_scheduler.py:544-556` preserves those three fields, and a completed run persists the result under durable `last_result.collect.continuation` before exposing it through `status_snapshot()`.
- `ScheduleSourceState.last_result` is currently typed too narrowly and `durable_state` omits the already-returned `last_result` field. Hotfix A only describes this existing additive response shape.
- Settings already calls `schedulerStateLabel(s.durable_state ?? null)` at `apps/arkscope-web/src/Settings.tsx:1625`. Once the durable nested result is typed and projected, the real mounted surface inherits the fix without an IBKR-specific branch.
- Process-local `s.last_result` has no shared run ID with `durable_state`; `at >= last_attempt` cannot prove same-run identity. It remains untouched and is intentionally not a Hotfix A input.
- Baseline frontend is `44 files / 412 tests`. The two touched suites collect `33` tests: `marketDataDisplay.test.ts` has `18`, and `SettingsProviderConfig.test.ts` has `15`.
- Behavioral base is `e5ccd12` (`docs: approve IBKR news retry design`). The implementation branch must be cut from the review-cleared plan tip, but product diffs are measured against `e5ccd12` because the intervening plan commit is docs-only.

## File Structure

- Modify `apps/arkscope-web/src/api.ts`: additive TypeScript interfaces for the already-returned sanitized schedule result.
- Modify `apps/arkscope-web/src/marketDataDisplay.ts`: pure precedence and count formatting.
- Modify `apps/arkscope-web/src/marketDataDisplay.test.ts`: projection contract and regression tests.
- Modify `apps/arkscope-web/src/SettingsProviderConfig.test.ts`: mounted Settings proof using conflicting process-local and durable observations.
- Do not modify `apps/arkscope-web/src/Settings.tsx`: its existing durable-state call is the intended generic wiring.
- Modify only after evidence exists: this plan, the authority spec status, and `docs/design/PROJECT_PRIORITY_MAP.md`.

---

### Task 1: Truthful Durable Partial-State Presentation

**Files:**
- Modify: `apps/arkscope-web/src/api.ts:2151-2186`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts:1,105-124`
- Test: `apps/arkscope-web/src/marketDataDisplay.test.ts:175-200`
- Test: `apps/arkscope-web/src/SettingsProviderConfig.test.ts:168-255,358-615`

**Interfaces:**
- Consumes: existing `ScheduleSourceState.durable_state` and the sanitized three-field continuation already returned by `/schedule`.
- Produces: `ScheduleContinuationCounts`, `ScheduleRunResult`, and the unchanged `schedulerStateLabel(durable)` result shape `{ label, tone, needsContinue }`.

- [x] **Step 1: Write the failing pure projection tests**

Keep the existing actionable ticker test. Replace the existing no-deferred test with the exact generic fallback, then add these six collected cases:

```ts
it("renders durable IBKR body counts without promising a manual retry", () => {
  const result = schedulerStateLabel({
    last_status: "partial",
    continuation: null,
    last_result: {
      source: "ibkr_news",
      status: "partial",
      collect: {
        status: "partial",
        continuation: {
          deferred_ticker_count: 0,
          deferred_body_count: 10,
          has_cursor: false,
        },
      },
    },
  });
  expect(result).toEqual({
    label: "部分完成（10 篇內文待後續處理）",
    tone: "warn",
    needsContinue: false,
  });
});

it.each([
  [
    { deferred_ticker_count: 3, deferred_body_count: 0, has_cursor: false },
    "部分完成（3 個標的待後續處理）",
  ],
  [
    { deferred_ticker_count: 3, deferred_body_count: 10, has_cursor: false },
    "部分完成（3 個標的、10 篇內文待後續處理）",
  ],
  [
    { deferred_ticker_count: 0, deferred_body_count: 0, has_cursor: true },
    "部分完成（尚有資料待後續處理）",
  ],
])("renders sanitized count/cursor state %j", (continuation, label) => {
  expect(schedulerStateLabel({
    last_status: "partial",
    continuation: null,
    last_result: {
      source: "ibkr_news",
      status: "partial",
      collect: { status: "partial", continuation },
    },
  })).toEqual({ label, tone: "warn", needsContinue: false });
});

it("keeps actionable ticker continuation ahead of informational counts", () => {
  const result = schedulerStateLabel({
    last_status: "partial",
    continuation: { deferred: ["NVDA", "TSLA"] },
    last_result: {
      source: "price_backfill",
      status: "partial",
      collect: {
        continuation: {
          deferred_ticker_count: 0,
          deferred_body_count: 10,
          has_cursor: false,
        },
      },
    },
  });
  expect(result).toEqual({
    label: "部分完成（待補抓 2）",
    tone: "warn",
    needsContinue: true,
  });
});

it("does not turn invalid observed counts into numeric promises", () => {
  for (const value of [0, -1, 1.5, Number.POSITIVE_INFINITY, Number.NaN]) {
    const result = schedulerStateLabel({
      last_status: "partial",
      continuation: null,
      last_result: {
        source: "ibkr_news",
        status: "partial",
        collect: {
          continuation: {
            deferred_ticker_count: value,
            deferred_body_count: value,
            has_cursor: false,
          },
        },
      },
    });
    expect(result).toEqual({ label: "部分完成", tone: "warn", needsContinue: false });
  }
});
```

Evolve the existing generic assertion to pin the exact label and the absence of zero:

```ts
it("partial without actionable or observed continuation is generic", () => {
  const result = schedulerStateLabel({
    last_status: "partial",
    continuation: { deferred: [] },
  });
  expect(result).toEqual({ label: "部分完成", tone: "warn", needsContinue: false });
  expect(result.label).not.toContain("0");
});
```

The test delta is exactly `+6`: body `+1`, the three `it.each` rows `+3`, precedence `+1`, and invalid values `+1`. The generic test replaces one existing test and contributes `+0`.

- [x] **Step 2: Add the failing mounted Settings fixture and test**

Add this `ibkr_news` source beside the existing schedule fixtures returned by mocked `getSchedule()`:

```ts
ibkr_news: {
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
  last_attempt_at: "2026-07-14T10:00:00Z",
  last_result: {
    source: "ibkr_news",
    status: "partial",
    at: "2026-07-14T10:01:00Z",
    collect: {
      status: "partial",
      continuation: {
        deferred_ticker_count: 0,
        deferred_body_count: 99,
        has_cursor: false,
      },
    },
  },
  gap_planned: false,
  durable_state: {
    last_status: "partial",
    last_error: null,
    continuation: null,
    last_result: {
      source: "ibkr_news",
      status: "partial",
      collect: {
        status: "partial",
        continuation: {
          deferred_ticker_count: 0,
          deferred_body_count: 10,
          has_cursor: false,
        },
      },
    },
    last_attempt: "2026-07-14T10:00:00Z",
    updated_at: "2026-07-14T10:01:00Z",
  },
  job_name: "collect.ibkr_news",
},
```

Add this test to the existing `Settings provider config authority` suite:

```ts
it("renders durable IBKR partial counts without a manual continuation action", async () => {
  await renderDataSources();
  const row = Array.from(host!.querySelectorAll("tr")).find((node) =>
    node.textContent?.includes("IBKR 新聞"));
  if (!row) throw new Error("missing IBKR news schedule row");

  expect(row.textContent).toContain("部分完成（10 篇內文待後續處理）");
  expect(row.textContent).not.toContain("待補抓");
  expect(Array.from(row.querySelectorAll("button")).some((button) =>
    button.textContent?.trim() === "補抓")).toBe(false);
  expect(Array.from(row.querySelectorAll("button")).some((button) =>
    button.textContent?.includes("Run"))).toBe(true);
});
```

The conflicting process-local count `99` and durable count `10` prove that the mounted surface uses restart-safe durable state. The `Run` assertion distinguishes the ordinary schedule command from the forbidden count-only continuation command.

- [x] **Step 3: Run both suites and verify RED for the intended reason**

Run:

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
```

Expected: the existing helper returns `部分完成（待補抓 0）`, ignores durable `last_result`, and therefore fails the new pure and mounted assertions. Existing non-scheduler tests remain green.

- [x] **Step 4: Add the existing response shape to `api.ts`**

Define these interfaces immediately before `ScheduleSourceState`:

```ts
export interface ScheduleContinuationCounts {
  deferred_ticker_count?: number;
  deferred_body_count?: number;
  has_cursor?: boolean;
}

export interface ScheduleRunResult {
  source: string;
  status: string;
  reason?: string;
  at?: string;
  collect?: {
    status?: string;
    continuation?: ScheduleContinuationCounts | null;
  } | null;
}
```

Change only these two response annotations; do not alter a request function or runtime expression:

```ts
last_result: ScheduleRunResult | null;
```

and inside `durable_state`:

```ts
last_result?: ScheduleRunResult | null;
```

The durable member stays optional so existing fixtures and an older sidecar remain compatible.

- [x] **Step 5: Implement the pure durable projection**

Extend the type import and replace only `schedulerStateLabel` plus its local count helper:

```ts
import type {
  CoverageStatus,
  MacroStatus,
  MarketDataStatus,
  NewsStatus,
  ScheduleSourceState,
  TradingDayRow,
} from "./api";

type SchedulerDurablePresentation = Pick<
  NonNullable<ScheduleSourceState["durable_state"]>,
  | "last_status"
  | "continuation"
  | "last_result"
  | "running_stale"
  | "running_stale_reason"
>;

function positiveCount(value: unknown): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value <= 0) return 0;
  return value;
}

export function schedulerStateLabel(
  durable: SchedulerDurablePresentation | null,
): { label: string; tone: "ok" | "warn" | "muted" | "bad"; needsContinue: boolean } {
  const st = durable?.last_status ?? null;
  switch (st) {
    case "succeeded":
      return { label: "上次成功", tone: "ok", needsContinue: false };
    case "partial": {
      const actionable = durable?.continuation?.deferred?.length ?? 0;
      if (actionable > 0) {
        return {
          label: `部分完成（待補抓 ${actionable}）`,
          tone: "warn",
          needsContinue: true,
        };
      }
      const observed = durable?.last_result?.collect?.continuation;
      const tickers = positiveCount(observed?.deferred_ticker_count);
      const bodies = positiveCount(observed?.deferred_body_count);
      if (tickers > 0 && bodies > 0) {
        return {
          label: `部分完成（${tickers} 個標的、${bodies} 篇內文待後續處理）`,
          tone: "warn",
          needsContinue: false,
        };
      }
      if (bodies > 0) {
        return {
          label: `部分完成（${bodies} 篇內文待後續處理）`,
          tone: "warn",
          needsContinue: false,
        };
      }
      if (tickers > 0) {
        return {
          label: `部分完成（${tickers} 個標的待後續處理）`,
          tone: "warn",
          needsContinue: false,
        };
      }
      if (observed?.has_cursor === true) {
        return {
          label: "部分完成（尚有資料待後續處理）",
          tone: "warn",
          needsContinue: false,
        };
      }
      return { label: "部分完成", tone: "warn", needsContinue: false };
    }
    case "failed":
      return { label: "上次失敗", tone: "bad", needsContinue: false };
    case "skipped":
      return { label: "上次已跳過", tone: "muted", needsContinue: false };
    case "running":
      if (durable?.running_stale) {
        return { label: "執行過久", tone: "warn", needsContinue: false };
      }
      return { label: "執行中", tone: "muted", needsContinue: false };
    default:
      return { label: "尚未執行", tone: "muted", needsContinue: false };
  }
}
```

Do not infer counts from errors, article totals, or process-local `last_result`. Actionable `deferred[]` must remain the first branch.

- [x] **Step 6: Run focused tests and typecheck**

Run:

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
npm run typecheck
```

Expected: `2 files / 40 tests` pass (`marketDataDisplay=24`, `SettingsProviderConfig=16`); typecheck passes.

- [x] **Step 7: Commit Task 1**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/marketDataDisplay.ts apps/arkscope-web/src/marketDataDisplay.test.ts apps/arkscope-web/src/SettingsProviderConfig.test.ts
git commit -m "fix: render truthful IBKR partial status"
```

---

### Task 2: Boundaries, Visual Gate, and Review Handoff

**Files:**
- Modify after evidence exists: `docs/superpowers/plans/2026-07-15-ibkr-news-partial-status-hotfix.md`
- Modify after evidence exists: `docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md`
- Modify after evidence exists: `docs/design/PROJECT_PRIORITY_MAP.md`
- Must not modify product behavior in this task.

**Interfaces:**
- Consumes: final Task 1 implementation.
- Produces: review-ready evidence only. No merge, durable-retry claim, or retry implementation.

- [x] **Step 1: Run focused and full frontend verification**

```bash
cd apps/arkscope-web
npm test -- --run src/marketDataDisplay.test.ts src/SettingsProviderConfig.test.ts
npm test
npm run typecheck
npm run build
```

Expected focused result: `2 files / 40 tests`. Expected full result: `44 files / 419 tests`, exactly `+7/-0` over `44/412`; typecheck and build pass with only the existing chunk-size warning.

- [x] **Step 2: Prove the frontend-only boundary and privacy ratchets**

Run from the repository root:

```bash
git diff --exit-code e5ccd12 -- src data_sources tests
git diff --name-only e5ccd12 -- apps/arkscope-web/src
git diff --word-diff=plain e5ccd12 -- apps/arkscope-web/src/api.ts
rg -n "deferred_body_ids|provider_article_id|provider_article_ids" apps/arkscope-web/src
```

Expected:

- backend diff is empty;
- the frontend name list is exactly `api.ts`, `marketDataDisplay.ts`, `marketDataDisplay.test.ts`, and `SettingsProviderConfig.test.ts`;
- the `api.ts` diff contains only interface/type declarations and no function body or runtime expression; and
- the privacy scan returns zero matches.

Also run:

```bash
rg -n "schedulerStateLabel\(" apps/arkscope-web/src
rg -n "待補抓 0|部分完成（待補抓 0）" apps/arkscope-web/src
git diff --exit-code e5ccd12 -- apps/arkscope-web/src/Settings.tsx
```

Expected:

- the helper scan shows only the function, its tests, and the existing Settings call;
- zero production code renders `待補抓 0`; and
- `Settings.tsx` is byte-identical, proving there is no source-specific branch or new runtime wiring.

- [x] **Step 3: Run one display-only real-state visual gate**

With exactly one sidecar, use the real profile DB but do not trigger a News or Gateway run. Open Settings -> Data Sources and inspect the persisted IBKR News row at `1440x900`, `1024x768`, and `390x844`:

1. the row never contains `待補抓 0`;
2. a durable body count renders `N 篇內文待後續處理`;
3. count-only continuation has no `補抓` button;
4. the ordinary `Run` command remains available under existing schedule rules;
5. the longer label wraps or scrolls inside its existing owner and does not overlap progress or the latest-run cell; and
6. restart the sidecar once and confirm the same durable explanation remains without running IBKR.

If the live durable row has naturally changed before this gate, use the exact mounted Settings fixture for screenshot evidence and record the real row's current truthful state separately. Do not mutate `profile_state.db` to manufacture a partial run.

- [x] **Step 4: Reconcile the exact implementation ledger and stop review-ready**

Under this plan header record:

- branch/base/head commits;
- each RED failure reason and GREEN command;
- focused/full frontend counts and exact `+7/-0` collection delta;
- backend byte-identity and API type-only proof;
- privacy/static gate results;
- the three-viewport and restart evidence; and
- any deviation from this reviewed plan.

Change the plan status to `IMPLEMENTED FOR REVIEW`. Change the authority spec only to `HOTFIX A IMPLEMENTED FOR REVIEW; DURABLE RETRY PENDING`, add a newest-first map decision-log entry, and commit the evidence:

```bash
git add docs/superpowers/plans/2026-07-15-ibkr-news-partial-status-hotfix.md docs/superpowers/specs/2026-07-14-ibkr-news-partial-retry-design.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark IBKR partial status hotfix review-ready"
```

Stop for implementation review. Do not merge Hotfix A or open the durable-retry implementation plan until review is GREEN.

---

## Exact Test Ledger

| Frontend owner | Baseline | Added | Final |
| --- | ---: | ---: | ---: |
| `marketDataDisplay.test.ts` | 18 | 6 | 24 |
| `SettingsProviderConfig.test.ts` | 15 | 1 | 16 |
| **Focused total** | **33** | **7** | **40** |
| **Full frontend** | **412** | **7** | **419** |
| **Frontend files** | **44** | **0** | **44** |

Backend product/tests delta is exactly `+0/-0` by byte identity against `e5ccd12`; no canonical backend A/B run is necessary for this frontend-only hotfix.

## Stop-Loss Conditions

Stop and report rather than widening scope if any of these occurs:

1. The durable schedule response does not contain `last_result.collect.continuation` on the real sidecar.
2. Showing the count requires a backend response change, DB query, worker change, or provider article ID.
3. Product behavior would need process-local `last_result`; without a shared run ID, Hotfix A must fail closed instead.
4. Count-only continuation would need to invoke `runNow`, resume a worker scope, or bypass `next_retry_at`.
5. The existing price-backfill `continuation.deferred[]` action changes or loses its button.
6. A source-specific Settings branch, new polling loop, CSS/layout rewrite, or generic UI primitive becomes necessary.
7. Any scheduler/retry/Gateway/storage behavior changes; those belong to the durable-retry follow-up.
8. The full frontend delta differs from `+7/-0` without a named review-approved reason.

## Reviewer Focus

1. Actionable `deferred[]` has absolute precedence and remains the only source of `needsContinue=true`.
2. Sanitized counts come only from durable `last_result`; process-local data is not guessed into the same run.
3. Body/ticker/cursor counts are finite positive observations, never inferred zeros or raw IDs.
4. All four sanitized presentation polarities, malformed values, and the generic fallback are pinned.
5. The existing generic Settings call inherits the fix; `Settings.tsx` remains byte-identical.
6. The mounted test proves count-only state has no `補抓` button while the ordinary Run control survives.
7. `api.ts` changes are additive typing only; backend and storage owners are byte-identical.
8. `44/412 -> 44/419`, typecheck/build, responsive visual evidence, and restart continuity reconcile before merge consideration.
