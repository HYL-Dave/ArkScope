# P2.8 Slice 2 Shell Convergence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** IMPLEMENTED FOR REVIEW — ALL IMPLEMENTER GATES CLOSED; NOT MERGED / NOT LIVE

**Goal:** Converge ArkScope on the approved workflow-grouped shell with an honest normal/Developer top bar, no planned placeholders or empty right rail, exact current-surface navigation, and a Research-only background-work notification drawer.

**Architecture:** A focused `src/shell/` package owns shipped navigation metadata, target resolution, shell preferences, top-bar presentation, and the Research work-notification registry. `App` remains the composition owner and consumes the existing `GET /research/threads` active-run summary plus `GET /research/runs/{id}` for terminal reconciliation; no backend schema, execution route, or second research-history authority is added. Existing `Drawer`, compact `BoundedProgress`, status, button, and 960px token primitives remain the presentation authorities.

**Tech Stack:** React 18.3, TypeScript 5.5, Vite 5, Vitest/jsdom, CSS custom properties, `lucide-react`, existing FastAPI Research APIs, and the shipped P2.8 UI primitives.

## Implementation Ledger (2026-07-17)

**Branch / base / code tip:** `codex/p2-8-slice-2-shell-convergence` / `29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb` / `90e953e`. The branch stops at review-ready; the final docs-only evidence commit is recorded by Task 7 Step 7.

**RED-first task commits:**

| Task | RED evidence | GREEN commit |
| --- | --- | --- |
| 0 — IA / target authority | 6 tests failed because `shell/navigation` did not exist | `165d86a` |
| 1 — grouped navigation | 6 component tests failed because `ShellNavigation` did not exist | `606bf2c` |
| 2 — normal / Developer top bar | 11 tests failed on missing preference/top-bar owners and legacy diagnostic leakage | `ca7b78e` |
| 3 — bounded Research registry | 12 tests failed on the missing registry/client helper/observer seams | `471c6be` |
| 4 — work indicator / Drawer | 10 tests failed because the notification surface did not exist | `22ec8ed` |
| 5 — exact App/Research/Settings targets | 13 mounted/integration tests failed on absent dispatcher and consumers | `8fb1bfa` |
| 6 — responsive shell / rail removal | 5 contracts failed on absent shell CSS and surviving legacy shell shape | `90e953e` |

**Exact frontend accounting:** clean base `46 files / 453 tests`; clean head `54 files / 516 tests`; collection delta **`+63 / -0`**, exactly the reviewed ledger. Final `npm test --workspace apps/arkscope-web`, typecheck, and production build pass. Build output has only the pre-existing `559.14 kB` chunk-size warning.

**Scope / privacy / backend gates:** `src/`, `data_sources/`, and backend `tests/` are byte-identical to base, so backend collection is constructively **`+0 / -0`** and canonical backend A/B is intentionally not claimed. Legacy rail selectors/state, planned Notes/Alerts controls, raw run error/question/credential/token references, copied shell breakpoint literals, and newly added `window.confirm` calls all have zero production matches.

**Disposable responsive/live gate:** scheduler-disabled sidecar `8421`, Vite `8432`, and headless Chrome CDP `9223` used only `/tmp/arkscope-p2-8-slice-2.db`; no normal desktop process or real profile was touched. Screenshots:

- `/tmp/arkscope-p2-8-shell-1440x900.png`
- `/tmp/arkscope-p2-8-shell-1024x768.png`
- `/tmp/arkscope-p2-8-shell-961x768.png`
- `/tmp/arkscope-p2-8-shell-960x768.png`
- `/tmp/arkscope-p2-8-shell-959x768.png`
- `/tmp/arkscope-p2-8-shell-390x844.png`

DOM and pixel inspection prove 961px = one persistent grouped nav/two columns; 960px and below = one menu trigger/one column/zero reserved rail; every width has no horizontal overflow, clipped top bar, duplicate focusable nav, planned control, diagnostic leak, or blank third column. Both Drawers focus close and restore their trigger. Developer Mode persists through reload and hides again without backend mutation. Repeated exact Data Sources and Research-thread targets apply while subsequent local selection remains possible. A queued fixture appeared on the first shell discovery; after `mark_terminal(..., "succeeded")`, measured DB `completed_at` to `待查看` was **1.283 s**, under one 5-second direct reconcile cycle. Work/session projection contained identity/timestamps only and no fixture prompt, model, token, credential, result, or raw error.

**Process cleanup:** isolated unified sessions `86428` (sidecar; Uvicorn PID `679832`), `9046` (Vite), and `34895` (Chrome PID `682625`) were explicitly stopped; a post-stop process scan found no matching test service. Temporary screenshots remain only long enough for independent review evidence.

**Bounded observation, not fixed here:** real `Research` initialization contains a pre-existing effect-order race where configured-route reset can overwrite the one-provider auto-selection in the same React batch. The new observer integration uses two available providers and an explicit OpenAI choice, matching existing supported UX; this slice does not change provider/model/effort selection behavior. Slice 3 or a dedicated Research behavior correction may own that separately if reproduced in product use.

## Global Constraints

- Canonical authority: `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`. The bounded sequencing authority is `docs/superpowers/specs/2026-07-12-p2-8-settings-stabilization-design.md`.
- Implementation base is `29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb` (`master`, 2026-07-16). Grounded frontend baseline is **46 files / 453 tests**, with typecheck and production build green; the build has only the existing chunk-size warning.
- This is a frontend shell slice. `src/`, `data_sources/`, and backend `tests/` must remain byte-identical to the base. No Python route, DB schema, migration, execution manager, scheduler, provider, agent, tool, prompt, or permission change is allowed.
- Existing Research APIs are sufficient: `GET /research/threads` discovers active runs and `GET /research/runs/{id}` reconciles a run already observed by this desktop session. Add only the missing TypeScript client helper for the latter route.
- The global drawer is a notification surface, not complete Research history. It contains current active runs plus succeeded/failed/interrupted runs actually observed by the current desktop session, including a reload of the same `sessionStorage` session. Research remains the durable result/history authority.
- Research must call the shell observer immediately after run creation, during active-run hydration, and after every replay response. This closes the fast-run race where a run could finish between 5-second shell polls.
- Direct reconciliation polls only already-observed active run IDs every 5 seconds. The heavier `/research/threads` discovery runs on mount, browser focus, and a separate 30-second cadence; do not perform its current per-thread active lookup every 5 seconds.
- A network/poll failure preserves the last truthful work registry. It never converts unavailable data into an empty list and never exposes raw provider errors in normal mode.
- Global work membership is Research-only. Card generation/translation, Portfolio capture, news jobs, schedules, and provider tests do not enter this registry.
- The drawer does not cancel Research. It states that work continues after navigation and navigates to the owning thread; explicit Stop remains owned by the Research surface.
- Final shipped navigation is exact and ordered: `探索` = 工作台/自選股/全部標的/新聞·事件; `研究` = AI 研究; `追蹤` = 持倉; `系統` = System / Health/設定. Notes and Alerts are reserved by the spec but absent from DOM, focus order, and navigation metadata until shipped.
- Group labels are low-emphasis, noninteractive, and non-focusable. No planned item is represented as a disabled control.
- Normal top bar contains ArkScope identity, current page/ticker context, actionable sidecar health, and nonzero background-work/attention count. It must not render `apiBase`, raw tool count, routine polling time, or global fixed-task model diagnostics.
- Developer Mode is a frontend shell-display preference persisted under `arkscope.shell.developerMode.v1`. It is toggled from System / Health and reveals a secondary diagnostic row; it does not alter backend behavior or Settings IA.
- The global placeholder right rail, edge tab, and all width-reservation state are removed. The work list and narrow navigation use transient `Drawer`; closed drawers reserve zero layout width.
- `shellOverlayBreakpointPx = 960` remains the sole shell breakpoint authority. `useShellOverlay()` decides persistent navigation versus overlay navigation; do not add another `@media` shell breakpoint literal.
- `NavigationTarget` implements only destinations with a current actionable owner in this slice: shipped view, ticker, Research thread/run, and enabled Settings section. Card/Evidence/Note/Alert/report variants land with their first actionable consumer instead of creating dead routes.
- Repeated exact-target requests carry a monotonically increasing sequence so an already-mounted Research or Settings surface can consume the same destination again without being permanently pinned there.
- Existing Research conversation/provider/model/effort behavior, thread deletion, transcript authority, and polling semantics remain unchanged. Slice 3 still owns Research history/evidence layout, full progress, rename/archive, typed errors, and replacement of its `window.confirm`.
- Existing Settings content, section ownership, route mutation behavior, and IA remain unchanged. Slice 4 owns grouped IA, search, collapse, and pure file decomposition.
- Use existing `Button`, `IconButton`, `Drawer`, `BoundedProgress`, and status primitives. Use `lucide-react` icons; do not add hand-authored SVG.
- Normal mode never renders raw Research `run.error`. Developer diagnostics remain sanitized and never include tokens, secrets, credential payloads, or raw broker identifiers.
- Static ratchets: no new `window.confirm`, no undefined shared class, no raw-exception interpolation, no disabled planned control, no copied shell breakpoint, no empty rail width, and no new production `Alerts`/`Notes` navigation label.
- Implementation stops at `IMPLEMENTED FOR REVIEW`. Do not merge, mark Slice 2 LIVE, start Slice 3, or update the external Design Kit before independent implementation review and responsive/live gates pass.

## Domain State Mapping

| Research run domain state | Common UI state | Shell behavior |
| --- | --- | --- |
| `queued` | `running` | Active count; `等待執行`; no session bound before `started_at` |
| `running` | `running` | Active count; elapsed time and Research session bound |
| `succeeded` | `ready` | Attention count until opened/dismissed; no answer copied |
| `failed` | `failed` | Attention count until handled; generic next step, no raw error |
| `cancelled` / `interrupted` | `interrupted` | Attention count until handled; exact owning thread remains navigable |
| thread/run poll unavailable | retained prior state | No invented `empty`; global sidecar health owns connectivity |

## File Map

**Create**

- `apps/arkscope-web/src/shell/navigation.ts` and `.test.ts` — shipped IA, target types, validation.
- `apps/arkscope-web/src/shell/ShellNavigation.tsx` and `.test.tsx` — grouped wide/drawer navigation body.
- `apps/arkscope-web/src/shell/shellPreferences.ts` — fail-closed Developer Mode preference.
- `apps/arkscope-web/src/shell/ShellTopBar.tsx` and `.test.tsx` — normal/developer topbar.
- `apps/arkscope-web/src/shell/researchWork.ts` and `.test.tsx` — Research notification registry, polling, observer hook.
- `apps/arkscope-web/src/shell/BackgroundWorkIndicator.tsx` and `.test.tsx` — topbar control and transient work Drawer.
- `apps/arkscope-web/src/shell/shell.css` and `ShellCss.test.ts` — namespaced responsive shell layout.
- `apps/arkscope-web/src/AppShell.test.tsx` — mounted shell integration.
- `apps/arkscope-web/src/ResearchShellNavigation.test.tsx` — real Research target/observer integration.

**Modify**

- `apps/arkscope-web/src/App.tsx` — compose shell modules; remove old nav, diagnostics, and rail.
- `apps/arkscope-web/src/Dashboard.tsx` — System-owned Developer Mode control.
- `apps/arkscope-web/src/Research.tsx` — consume exact thread target and report run observations.
- `apps/arkscope-web/src/Settings.tsx` and `SettingsModelRouting.test.ts` — exact enabled-section requests only.
- `apps/arkscope-web/src/api.ts` — add `getResearchRun(runId)` over the existing route.
- `apps/arkscope-web/src/main.tsx` — import shell CSS.
- `apps/arkscope-web/src/styles.css` — remove superseded shell/topbar/right-rail rules only.
- This plan and `docs/design/PROJECT_PRIORITY_MAP.md` — evidence/status bookkeeping.

---

## Acceptance Trace

| Approved Slice 2 outcome | Owning tasks | Hard proof |
| --- | --- | --- |
| Workflow-grouped shipped navigation | 0, 1 | literal IA order, uniqueness, semantics, mounted rendering |
| No planned disabled controls | 0, 1, 6 | metadata/DOM absence plus source ratchet |
| Normal/Developer top bar | 2, 5 | diagnostic-leak negatives, persisted display-only toggle |
| No placeholder right rail | 5, 6 | mounted absence, CSS selector removal, two-column proof |
| Actionable `NavigationTarget` resolver | 0, 5 | ticker/Research/Settings exact targets and repeat sequencing |
| Research-only global work indicator/Drawer | 3, 4, 5 | bounded identity registry, fast-run observer order, privacy/membership negatives |
| 960px shell behavior and zero closed width | 6, 7 | token-driven DOM/CSS tests plus 961/960/959/mobile screenshots |

---

## Task 0: Lock the Shell IA and Actionable Navigation Targets

**Files:**

- Create: `apps/arkscope-web/src/shell/navigation.ts`
- Create: `apps/arkscope-web/src/shell/navigation.test.ts`

**Contract:** One reviewed metadata source defines shipped navigation and exact target ownership. Reserved future destinations do not enter the TypeScript union until they have an actionable owner.

- [x] **Step 1: Install dependencies only if this worktree does not already have them, then record the frontend baseline**

```bash
test -d apps/arkscope-web/node_modules || npm install --workspace apps/arkscope-web
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected baseline: `46 files / 453 tests` pass; typecheck passes; build passes with only the existing chunk-size warning.

- [x] **Step 2: Write six failing metadata/target tests**

Create `navigation.test.ts` with these exact cases:

1. `publishes the approved four workflow groups in canonical order`
2. `contains every shipped view exactly once`
3. `does not publish Notes or Alerts as planned controls`
4. `resolves a ticker target to ticker detail without inventing a nav item`
5. `resolves Research and Settings targets to their owning shipped views`
6. `increments the request sequence even when the exact target repeats`

The expected metadata is literal and reviewable:

```ts
expect(SHELL_NAV_GROUPS.map((group) => [
  group.label,
  group.items.map((item) => [item.view, item.label]),
])).toEqual([
  ["探索", [["Home", "工作台"], ["Watchlist", "自選股"], ["Universe", "全部標的"], ["News", "新聞·事件"]]],
  ["研究", [["Research", "AI 研究"]]],
  ["追蹤", [["Holdings", "持倉"]]],
  ["系統", [["System", "System / Health"], ["Settings", "設定"]]],
]);
expect(JSON.stringify(SHELL_NAV_GROUPS)).not.toMatch(/Notes|Alerts|研究筆記|告警/);
```

- [x] **Step 3: Run the focused test and prove RED for missing shell authority**

```bash
npm test --workspace apps/arkscope-web -- src/shell/navigation.test.ts
```

Expected: the suite fails because `./navigation` does not exist. A syntax, setup, or unrelated failure does not count as RED.

- [x] **Step 4: Implement the exact target and resolution contracts**

Use this public shape:

```ts
export type ShellView =
  | "Home"
  | "Watchlist"
  | "Universe"
  | "News"
  | "Research"
  | "Holdings"
  | "System"
  | "Settings";

export type EnabledSettingsSection =
  | "models"
  | "investor_profile"
  | "providers"
  | "data_storage"
  | "news_storage"
  | "macro_storage"
  | "data_sources";

export type NavigationTarget =
  | { kind: "view"; view: ShellView }
  | { kind: "ticker"; ticker: string }
  | { kind: "research_thread"; threadId: string; runId?: string }
  | { kind: "settings_section"; section: EnabledSettingsSection };

export interface NavigationRequest<T extends NavigationTarget = NavigationTarget> {
  sequence: number;
  target: T;
}

export interface ResolvedNavigationTarget {
  view?: ShellView;
  ticker?: string;
  research?: NavigationRequest<Extract<NavigationTarget, { kind: "research_thread" }>>;
  settings?: NavigationRequest<Extract<NavigationTarget, { kind: "settings_section" }>>;
}

export function nextNavigationRequest(
  currentSequence: number,
  target: NavigationTarget,
): NavigationRequest {
  return { sequence: currentSequence + 1, target };
}

export function resolveNavigationTarget(request: NavigationRequest): ResolvedNavigationTarget {
  const target = request.target;
  if (target.kind === "view") return { view: target.view };
  if (target.kind === "ticker") {
    const ticker = target.ticker.trim().toUpperCase();
    if (!ticker) throw new Error("ticker navigation target must not be empty");
    return { ticker };
  }
  if (target.kind === "research_thread") {
    return {
      view: "Research",
      research: { sequence: request.sequence, target },
    };
  }
  if (target.kind === "settings_section") {
    return {
      view: "Settings",
      settings: { sequence: request.sequence, target },
    };
  }
  const unreachable: never = target;
  throw new Error(`unsupported navigation target: ${String(unreachable)}`);
}
```

`SHELL_NAV_GROUPS` must include stable `view`, Chinese-primary `label`, and a Lucide icon key. It must not contain `enabled`, `planned`, or placeholder entries. Export `shellViewLabel(view)` by looking up this metadata so App/topbar do not create a second label map.

- [x] **Step 5: Run focused tests and typecheck**

```bash
npm test --workspace apps/arkscope-web -- src/shell/navigation.test.ts
npm run typecheck --workspace apps/arkscope-web
```

Expected: `6 tests` pass and typecheck passes.

- [x] **Step 6: Commit the IA authority**

```bash
git add apps/arkscope-web/src/shell/navigation.ts apps/arkscope-web/src/shell/navigation.test.ts
git commit -m "feat: define shell navigation targets"
```

## Task 1: Render Workflow-Grouped Wide and Overlay Navigation

**Files:**

- Create: `apps/arkscope-web/src/shell/ShellNavigation.tsx`
- Create: `apps/arkscope-web/src/shell/ShellNavigation.test.tsx`
- Modify: `apps/arkscope-web/src/App.tsx`

**Contract:** Wide and narrow shells consume the same grouped navigation body. Group labels are headings, not controls; planned features are absent rather than disabled.

- [x] **Step 1: Write six failing component tests with the house `createRoot` + `act` harness**

1. `renders four noninteractive workflow group labels`
2. `renders eight shipped destinations in canonical order`
3. `marks only the current view with aria-current page`
4. `dispatches an exact view target and closes an overlay copy`
5. `renders one aria-hidden Lucide icon per destination with no literal svg source`
6. `contains no disabled Notes or Alerts controls`

The test must query buttons and `[data-shell-nav-group]`; it must not test implementation-only class names. For the last case, assert both text absence and zero disabled navigation buttons.

- [x] **Step 2: Run the focused suite and prove RED because the component is absent**

```bash
npm test --workspace apps/arkscope-web -- src/shell/ShellNavigation.test.tsx
```

Expected: module resolution fails for `./ShellNavigation`.

- [x] **Step 3: Implement the grouped navigation body**

Use `LayoutDashboard`, `Star`, `ListFilter`, `Newspaper`, `Search`, `BriefcaseBusiness`, `Activity`, and `Settings` from `lucide-react`. The component receives metadata rather than rebuilding it:

```ts
export interface ShellNavigationProps {
  currentView: ShellView;
  onNavigate: (target: NavigationTarget) => void;
  onAfterNavigate?: () => void;
}
```

Each destination is a real `button` with icon, label, and `aria-current={currentView === item.view ? "page" : undefined}`. Each group label is a `<div>` or heading with `data-shell-nav-group`, never a button or link. `onAfterNavigate` is called only after dispatching a shipped destination and lets `App` close the narrow Drawer.

- [x] **Step 4: Replace only the old inline navigation metadata/render loop in `App.tsx`**

Delete `NAV`, `ENABLED`, `LABELS`, and the inline `NAV.map(...)`. Import `ShellView`, `NavigationTarget`, and `ShellNavigation`. At this task boundary, retain the existing wide `<nav>` shell and rendering switch; responsive Drawer composition lands in Task 6.

Do not retain a fallback branch that renders `規劃中`; the `ShellView` union is exhaustive and contains only shipped views.

- [x] **Step 5: Run focused and existing frontend tests**

```bash
npm test --workspace apps/arkscope-web -- src/shell/navigation.test.ts src/shell/ShellNavigation.test.tsx
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
```

Expected: `12 focused tests` pass; the full frontend remains green.

- [x] **Step 6: Commit grouped navigation**

```bash
git add apps/arkscope-web/src/App.tsx apps/arkscope-web/src/shell/ShellNavigation.tsx apps/arkscope-web/src/shell/ShellNavigation.test.tsx
git commit -m "feat: group shipped shell navigation"
```

## Task 2: Separate the Normal Top Bar from Developer Diagnostics

**Files:**

- Create: `apps/arkscope-web/src/shell/shellPreferences.ts`
- Create: `apps/arkscope-web/src/shell/ShellTopBar.tsx`
- Create: `apps/arkscope-web/src/shell/ShellTopBar.test.tsx`
- Modify: `apps/arkscope-web/src/App.tsx`
- Modify: `apps/arkscope-web/src/Dashboard.tsx`

**Contract:** Normal mode communicates identity, current context, actionable health, and nonzero work attention. Raw local endpoint/tool/poll/model diagnostics live in a secondary Developer Mode row controlled from System / Health.

- [x] **Step 1: Write eleven failing tests**

Preference tests:

1. `defaults Developer Mode off when storage is empty or unavailable`
2. `round trips the versioned Developer Mode preference`
3. `treats every value except the literal enabled sentinel as off`

Top-bar tests:

4. `shows ArkScope current context and healthy sidecar copy in normal mode`
5. `makes failed sidecar health an actionable System target`
6. `does not show apiBase tool count poll time or model diagnostics in normal mode`
7. `omits the background-work control when both counts are zero`
8. `shows a single work control when active or attention count is nonzero`
9. `shows the secondary diagnostics row only in Developer Mode`
10. `keeps developer diagnostics sanitized and labelled as diagnostics`
11. `keeps identity and context in stable named slots when status copy changes`

Use fixed-width `data-testid` slots for test 11; assert the semantic slots remain present rather than relying on jsdom pixel layout. In the mounted App test added in Task 5, use a recognizable sidecar exception fixture and prove it is absent from both the normal top bar and normal System view until Developer Mode is enabled.

- [x] **Step 2: Run the focused suite and prove RED on missing modules**

```bash
npm test --workspace apps/arkscope-web -- src/shell/ShellTopBar.test.tsx
```

Expected: module resolution fails for `shellPreferences` or `ShellTopBar`.

- [x] **Step 3: Implement fail-closed shell preferences**

```ts
export const DEVELOPER_MODE_STORAGE_KEY = "arkscope.shell.developerMode.v1";

export function readDeveloperMode(storage: Pick<Storage, "getItem"> = window.localStorage): boolean {
  try { return storage.getItem(DEVELOPER_MODE_STORAGE_KEY) === "enabled"; }
  catch { return false; }
}

export function writeDeveloperMode(
  enabled: boolean,
  storage: Pick<Storage, "setItem"> = window.localStorage,
): void {
  try { storage.setItem(DEVELOPER_MODE_STORAGE_KEY, enabled ? "enabled" : "disabled"); }
  catch { /* display preference remains in React state for this session */ }
}
```

- [x] **Step 4: Implement `ShellTopBar` without embedding work-registry logic**

```ts
export interface ShellDiagnostics {
  apiBase: string;
  toolsRegistered: number | null;
  lastStatusAt: string | null;
  cardModel: string | null;
}

export interface ShellTopBarProps {
  contextLabel: string;
  status: StatusState;
  developerMode: boolean;
  diagnostics: ShellDiagnostics;
  workControl?: ReactNode;
  onNavigate: (target: NavigationTarget) => void;
  menuControl?: ReactNode;
}
```

Normal health labels are `Sidecar 已連線`, `Sidecar 無法連線`, or `正在連線`. The failed state is a button that dispatches `{ kind: "view", view: "System" }`. Render `workControl` only when supplied. Developer diagnostics may display the four typed fields, but no status exception string.

- [x] **Step 5: Move preference ownership into `App` and add the System control**

`App` initializes `developerMode` once from `readDeveloperMode`, passes it to `ShellTopBar`, and passes `developerMode` plus `onDeveloperModeChange` to `DashboardView`. `DashboardView` renders one labelled checkbox/toggle under a `Developer Mode` heading. Changing it updates React state and `localStorage`; it does not fetch or mutate backend configuration. Its normal sidecar failure state shows `無法連線至本機 Sidecar` plus Retry; the existing raw `status.message` is rendered only while Developer Mode is enabled.

Delete `lastOk` display from the normal row. Preserve the timestamp only as `diagnostics.lastStatusAt`. Delete the topbar fixed-task model button; Settings navigation remains available through the canonical nav.

- [x] **Step 6: Run the focused suite, full frontend, and typecheck**

```bash
npm test --workspace apps/arkscope-web -- src/shell/ShellTopBar.test.tsx
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
```

Expected: `11 focused tests` pass; the full frontend remains green.

- [x] **Step 7: Commit the top-bar mode split**

```bash
git add apps/arkscope-web/src/App.tsx apps/arkscope-web/src/Dashboard.tsx apps/arkscope-web/src/shell/shellPreferences.ts apps/arkscope-web/src/shell/ShellTopBar.tsx apps/arkscope-web/src/shell/ShellTopBar.test.tsx
git commit -m "feat: separate shell diagnostics from normal mode"
```

## Task 3: Build the Bounded Research Work Registry

**Files:**

- Create: `apps/arkscope-web/src/shell/researchWork.ts`
- Create: `apps/arkscope-web/src/shell/researchWork.test.tsx`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/Research.tsx`

**Contract:** The shell observes Research runs without becoming a second history store. It persists at most 50 minimal run identities in session storage, discovers server-owned active runs, reconciles only previously observed terminal runs, and preserves prior truth when polling fails.

- [x] **Step 1: Write twelve failing registry tests**

Pure state/projection cases:

1. `maps queued and running runs to active work`
2. `maps succeeded and failed runs to attention work`
3. `maps cancelled and interrupted runs to interrupted attention`
4. `projects no question answer error token usage credential id or raw provider payload`
5. `deduplicates the same run observed by Research and shell polling`
6. `caps persisted identities at the newest 50 records`

Hook/polling cases with injected API and fake timers:

7. `hydrates active runs from thread summaries immediately`
8. `reconciles a session-observed run through getResearchRun after it leaves active summaries`
9. `preserves prior work when either polling leg fails`
10. `polls observed active runs every five seconds discovers threads every thirty seconds without overlap and disposes both timers`
11. `dismisses terminal work without hiding an active run`
12. `does not discover terminal runs that this desktop session never observed`

For case 4, serialize both React state projection and `sessionStorage` and assert absence of the actual fixture values for `question`, `error`, `credential_id`, `token_usage`, and answer text, not merely absence of property names.

- [x] **Step 2: Run the focused suite and prove RED on the missing registry**

```bash
npm test --workspace apps/arkscope-web -- src/shell/researchWork.test.tsx
```

Expected: module resolution fails for `./researchWork`.

- [x] **Step 3: Add the missing frontend helper over the existing route**

```ts
export function getResearchRun(runId: string): Promise<{ run: ResearchRunDTO }> {
  return getJSON<{ run: ResearchRunDTO }>(
    `/research/runs/${encodeURIComponent(runId)}`,
    8_000,
  );
}
```

Do not add a backend route or change the DTO. The existing FastAPI handler at `src/api/routes/research.py` remains byte-identical.
In registry case 8, let the `getRun` leg use this real helper behind `vi.stubGlobal("fetch", ...)` and assert the encoded `/research/runs/{id}` URL; do not let an injected fake make the new client seam untested.

- [x] **Step 4: Implement minimal projection and session identity storage**

Use this public surface:

```ts
export type ShellResearchWorkStatus = ResearchRunDTO["status"];

export interface ResearchWorkItem {
  runId: string;
  threadId: string;
  threadTitle: string;
  status: ShellResearchWorkStatus;
  createdAt: string;
  startedAt: string | null;
  completedAt: string | null;
}

export interface ResearchWorkState {
  items: ResearchWorkItem[];
  activeCount: number;
  attentionCount: number;
  refresh: () => Promise<void>;
  observeRun: (run: ResearchRunDTO, threadTitle?: string) => void;
  dismiss: (runId: string) => void;
}

export interface ResearchWorkApi {
  getThreads: typeof getResearchThreads;
  getRun: typeof getResearchRun;
}

export function useResearchWorkRegistry(options?: {
  api?: ResearchWorkApi;
  storage?: Pick<Storage, "getItem" | "setItem">;
  activePollMs?: number;
  discoveryPollMs?: number;
  now?: () => number;
}): ResearchWorkState;
```

Persist only `{ runId, threadId, observedAt }` under `arkscope.shell.researchWork.v1`. Parsing is fail-closed per record: reject malformed/empty IDs, sort deterministically by `observedAt`, and keep the newest 50. A storage exception leaves in-memory observation working.

The initial/focus/30-second discovery refresh performs these bounded legs:

1. Call `getResearchThreads(50)` and build a title lookup.
2. Project every nonterminal `active_run` and remember its identity.
3. For persisted identities with no in-memory projection (session reload), call `getResearchRun(runId)` once with `Promise.allSettled` and project successful results. Terminal projections are immutable and are not refetched.
4. Merge by `runId`, preferring the newest server DTO; retain the previous item for any failed leg.
5. Never infer `empty` from a failed response and never scan terminal history beyond the 50 observed identities.

The 5-second active reconciliation calls `getResearchRun(runId)` only for currently projected `queued`/`running` items, using `Promise.allSettled`; this is how an observed run becomes terminal between discovery cycles. Guard discovery and active reconciliation with separate in-flight refs so neither cadence overlaps its own prior request. Add a `focus` listener that requests discovery and remove it on unmount.

- [x] **Step 5: Wire immediate observations into all three real Research seams**

Extend the component without making shell context mandatory in isolated tests:

```ts
export interface ResearchViewProps {
  onOpenTicker: (ticker: string) => void;
  navigationRequest?: NavigationRequest<Extract<NavigationTarget, { kind: "research_thread" }>> | null;
  onObserveRun?: (run: ResearchRunDTO, threadTitle?: string) => void;
}
```

Call `onObserveRun`:

- for each `thread.active_run` during `getResearchThreads()` hydration, with that thread title;
- immediately after `createResearchRun(body)` resolves, before `pollRun(run)`;
- after every `getResearchRunEvents()` response, before terminal/nonterminal branching.

These calls are notification only. They must not alter reducer frames, polling cadence, stop behavior, provider/model/effort selection, or persistence.

- [x] **Step 6: Run focused tests and prove the API/backend boundary**

```bash
npm test --workspace apps/arkscope-web -- src/shell/researchWork.test.tsx
npm run typecheck --workspace apps/arkscope-web
git diff --exit-code 29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb -- src data_sources tests
```

Expected: `12 tests` pass, typecheck passes, and the backend boundary diff is empty.

- [x] **Step 7: Commit the registry and observer seam**

```bash
git add apps/arkscope-web/src/api.ts apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/shell/researchWork.ts apps/arkscope-web/src/shell/researchWork.test.tsx
git commit -m "feat: observe server-owned research work"
```

## Task 4: Add the Research-Only Background Work Indicator and Drawer

**Files:**

- Create: `apps/arkscope-web/src/shell/BackgroundWorkIndicator.tsx`
- Create: `apps/arkscope-web/src/shell/BackgroundWorkIndicator.test.tsx`
- Modify: `apps/arkscope-web/src/shell/ShellTopBar.tsx`

**Contract:** A nonzero top-bar notification opens a transient, navigational work drawer. Rows use compact `BoundedProgress`, expose no raw result/error, and never imply that fixed tasks or complete history are tracked.

- [x] **Step 1: Write ten failing component tests**

1. `renders no control and no reserved drawer width for an empty registry`
2. `labels one control with separate active and attention counts`
3. `opens a transient Drawer and returns focus to the trigger on close`
4. `renders queued work without a fabricated stage bound`
5. `renders running work against the configured Research session bound`
6. `renders succeeded failed and interrupted rows with common states`
7. `never renders raw run errors answers credential identifiers or token usage`
8. `navigates to the exact owning Research thread and optional run`
9. `marks terminal attention handled only after navigation or explicit dismissal`
10. `contains no global cancel action and explains that work continues after navigation`

Use fake timers for elapsed-time assertions. The failed fixture must contain a recognizable raw error and the DOM must not contain it.

- [x] **Step 2: Run the focused suite and prove RED on the absent indicator**

```bash
npm test --workspace apps/arkscope-web -- src/shell/BackgroundWorkIndicator.test.tsx
```

Expected: module resolution fails for `./BackgroundWorkIndicator`.

- [x] **Step 3: Implement the top-bar control and transient Drawer**

```ts
export interface BackgroundWorkIndicatorProps {
  work: ResearchWorkState;
  researchSessionBoundMs: number | null;
  onNavigate: (target: NavigationTarget) => void;
}
```

Use a Lucide `Bell` or `Activity` icon inside `IconButton`/`Button`. Keep the trigger ref and pass it as `returnFocusRef` to `Drawer`. The trigger copy must distinguish `執行中 N` from `待查看 N`; when both exist, expose both in the accessible label.

Each row derives:

- `queued`: `status="running"`, stage `等待執行`, `stageBoundMs={null}`;
- `running`: `status="running"`, stage `AI 研究執行中`, bound from `runtime.research_runtime.session_timeout_s * 1000`;
- `succeeded`: `status="succeeded"`, stage `研究完成`;
- `failed`: `status="failed"`, title `研究未完成`, detail `開啟原對話查看可採取的下一步。`;
- `cancelled`/`interrupted`: `status="interrupted"`, stage `研究已中止`.

For every row, `continuesAfterNavigation={true}`, `canCancel={false}`, and `resultLabel="結果留在 AI 研究對話"`. Calculate elapsed time from the typed timestamps and clamp malformed/negative values to zero. No percentage is rendered.

- [x] **Step 4: Implement terminal handling and exact navigation**

Clicking a row dispatches:

```ts
onNavigate({
  kind: "research_thread",
  threadId: item.threadId,
  runId: item.runId,
});
```

Then close the Drawer. For terminal rows, call `work.dismiss(item.runId)` only after dispatch. A separate dismiss icon may remove a terminal row without navigation, but it must have an explicit accessible label. Active rows cannot be dismissed.

- [x] **Step 5: Run focused tests and typecheck**

```bash
npm test --workspace apps/arkscope-web -- src/shell/BackgroundWorkIndicator.test.tsx src/shell/ShellTopBar.test.tsx
npm run typecheck --workspace apps/arkscope-web
```

Expected: `21 focused tests` pass and typecheck passes.

- [x] **Step 6: Commit the notification surface**

```bash
git add apps/arkscope-web/src/shell/BackgroundWorkIndicator.tsx apps/arkscope-web/src/shell/BackgroundWorkIndicator.test.tsx apps/arkscope-web/src/shell/ShellTopBar.tsx
git commit -m "feat: add research work notification drawer"
```

## Task 5: Integrate Exact Targets Across App, Research, and Settings

**Files:**

- Create: `apps/arkscope-web/src/AppShell.test.tsx`
- Create: `apps/arkscope-web/src/ResearchShellNavigation.test.tsx`
- Modify: `apps/arkscope-web/src/App.tsx`
- Modify: `apps/arkscope-web/src/Research.tsx`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/SettingsModelRouting.test.ts`

**Contract:** One App-owned dispatcher resolves every shell target. Research and Settings consume sequenced requests once, so the same target can be requested again while ordinary in-page selection remains locally owned.

- [x] **Step 1: Write eight failing mounted-shell tests**

Use Vitest module fakes for heavy page surfaces while mounting the real `App`, `ShellTopBar`, `ShellNavigation`, target resolver, and work indicator:

1. `renders the grouped shipped shell with no planned controls or right rail`
2. `opens ticker detail from an exact ticker target and returns to the owning view`
3. `opens the exact Research thread from a work row`
4. `opens the exact enabled Settings section from a status target`
5. `increments delivery when the same exact target is requested twice`
6. `routes failed sidecar health to System Health`
7. `keeps raw sidecar errors apiBase tool and polling diagnostics out of normal shell and System view`
8. `limits global background work membership to Research observations`

The component fakes must expose received `navigationRequest` and `onObserveRun` props in the DOM or captured calls. Do not assert only that the broad view changed.

- [x] **Step 2: Write three failing real Research integration tests**

In `ResearchShellNavigation.test.tsx`, reuse the existing `createRoot` + `act`, fetch stub, and API fixture style:

1. `consumes a sequenced thread target after hydration and preserves later local thread selection`
2. `reports each hydrated active run to the shell observer`
3. `reports a created run before replay and reports the terminal replay DTO`

For case 1, dispatch the same target with a larger sequence after local selection and prove it applies again. For case 3, capture call order so `created` observation precedes the first `/events` request.

- [x] **Step 3: Add two failing Settings request tests to the existing mounted suite**

Add:

1. `opens an enabled section from a sequenced shell request`
2. `reapplies the same section only when its request sequence advances`

Use `models` and `providers`. The prop type must not accept disabled `app_records` or `permissions`; add a TypeScript `satisfies EnabledSettingsSection` fixture rather than a runtime dead-route test.

- [x] **Step 4: Run all three suites and prove RED on missing props/dispatcher**

```bash
npm test --workspace apps/arkscope-web -- src/AppShell.test.tsx src/ResearchShellNavigation.test.tsx src/SettingsModelRouting.test.ts
```

Expected: new assertions fail because App does not yet dispatch exact targets and the two surfaces do not consume requests.

- [x] **Step 5: Make `App` the sole navigation dispatcher**

Use a sequence ref so callbacks do not depend on stale state:

```ts
const navigationSequenceRef = useRef(0);
const [researchNavigation, setResearchNavigation] = useState<ResearchNavigationRequest | null>(null);
const [settingsNavigation, setSettingsNavigation] = useState<SettingsNavigationRequest | null>(null);

const navigate = useCallback((target: NavigationTarget) => {
  const request = nextNavigationRequest(navigationSequenceRef.current, target);
  navigationSequenceRef.current = request.sequence;
  const resolved = resolveNavigationTarget(request);
  setDetail(resolved.ticker ? { ticker: resolved.ticker } : null);
  if (resolved.view) setView(resolved.view);
  if (resolved.research) setResearchNavigation(resolved.research);
  if (resolved.settings) setSettingsNavigation(resolved.settings);
}, []);
```

Plain view navigation clears ticker detail. Research/Settings requests remain as last-delivered envelopes; consumers key on `sequence`, not object presence. Derive top-bar context from ticker detail or the canonical navigation label, never a second label map.

Adapt existing child callbacks at the App boundary rather than widening every page in this slice:

```tsx
<HomeView
  status={status}
  onNavigate={(next) => navigate({ kind: "view", view: next })}
  onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })}
  runtime={runtime}
/>
```

Use the same ticker adapter for Watchlist, Universe, News, and Research. Because a ticker target has no resolved `view`, opening detail preserves the current owning view and Back returns there.

Create the registry once at App root and compose:

```tsx
const researchWork = useResearchWorkRegistry();

<ResearchView
  onOpenTicker={(ticker) => navigate({ kind: "ticker", ticker })}
  navigationRequest={researchNavigation}
  onObserveRun={researchWork.observeRun}
/>
```

Pass `runtime?.research_runtime.session_timeout_s * 1000` to `BackgroundWorkIndicator`, with null for missing/non-finite values.

- [x] **Step 6: Consume the Research target after hydration without pinning selection**

In `ResearchView`, track the last consumed navigation sequence in a ref. An effect watches `navigationRequest`, `state.threads`, and `selectThread`:

1. ignore null or already-consumed sequence;
2. wait until the requested thread exists in hydrated `state.threads`;
3. mark the sequence consumed and call the existing `selectThread(threadId)`;
4. do not keep enforcing the target after a user locally selects another thread.

The optional `runId` identifies the notification source but does not add a second run-history view. The owning thread is the current actionable destination; Slice 3 owns richer run/history addressing.

- [x] **Step 7: Consume enabled Settings targets with the same sequence discipline**

Export the existing `SettingsSection` type only as needed internally, but expose this narrower prop:

```ts
export interface SettingsViewProps {
  runtime: RuntimeConfig | null;
  onRuntimeChanged: () => Promise<void>;
  navigationRequest?: NavigationRequest<Extract<NavigationTarget, { kind: "settings_section" }>> | null;
}
```

An effect marks a new sequence consumed and calls the existing `setSection(request.target.section)`. Do not modify `SETTINGS_SECTIONS`, collapse behavior, model-routing state, or any mutation handler.

- [x] **Step 8: Run focused integration, full frontend, and typecheck**

```bash
npm test --workspace apps/arkscope-web -- src/AppShell.test.tsx src/ResearchShellNavigation.test.tsx src/SettingsModelRouting.test.ts
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
```

Expected: `13 new integration tests` pass and the full frontend remains green.

- [x] **Step 9: Commit exact target integration**

```bash
git add apps/arkscope-web/src/App.tsx apps/arkscope-web/src/Research.tsx apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/AppShell.test.tsx apps/arkscope-web/src/ResearchShellNavigation.test.tsx apps/arkscope-web/src/SettingsModelRouting.test.ts
git commit -m "feat: connect exact shell navigation targets"
```

## Task 6: Converge the Two-Column Shell and Remove the Placeholder Rail

**Files:**

- Create: `apps/arkscope-web/src/shell/shell.css`
- Create: `apps/arkscope-web/src/shell/ShellCss.test.ts`
- Modify: `apps/arkscope-web/src/App.tsx`
- Modify: `apps/arkscope-web/src/main.tsx`
- Modify: `apps/arkscope-web/src/styles.css`

**Contract:** At 961px and wider, the shell has navigation plus content. At 960px and narrower, navigation is a transient Drawer. There is never a third placeholder column, edge tab, empty rail reservation, or copied CSS breakpoint.

- [x] **Step 1: Write five failing source/CSS contract tests**

1. `defines a two-column wide shell and no third rail track`
2. `switches overlay layout through data-shell-overlay without an at-media rule`
3. `contains no legacy rightrail rail-tab rail-open or rail-closed selector`
4. `defines every literal app-shell class used by App and shell components`
5. `imports shell css from main and keeps the canonical breakpoint in tokens only`

Read `shell.css`, `styles.css`, `App.tsx`, and shell component sources with `node:fs`, following `ui/classCoverage.test.ts`. The breakpoint test asserts no `@media` and no literal `960`, `959`, or `961` in production `shell.css`; boundary numbers remain in `ui/tokens` and tests.

- [x] **Step 2: Run the CSS suite and prove RED on the absent stylesheet/legacy selectors**

```bash
npm test --workspace apps/arkscope-web -- src/shell/ShellCss.test.ts
```

Expected: `shell.css` is absent and legacy rail selectors still exist.

- [x] **Step 3: Compose the persistent/overlay navigation from the existing breakpoint hook**

At App root:

```tsx
const shellOverlay = useShellOverlay();
const [navigationOpen, setNavigationOpen] = useState(false);

<div className="app-shell" data-shell-overlay={String(shellOverlay)}>
  <ShellTopBar
    contextLabel={detail?.ticker ?? shellViewLabel(view)}
    status={status}
    developerMode={developerMode}
    diagnostics={{
      apiBase,
      toolsRegistered: status.kind === "ready" ? status.status.tools_registered : null,
      lastStatusAt: lastOk,
      cardModel: runtime ? `${runtime.card_synthesis.provider}/${runtime.card_synthesis.model}` : null,
    }}
    workControl={(
      <BackgroundWorkIndicator
        work={researchWork}
        researchSessionBoundMs={researchSessionBoundMs}
        onNavigate={navigate}
      />
    )}
    onNavigate={navigate}
    menuControl={shellOverlay ? <IconButton icon={<Menu />} label="開啟導覽" onClick={() => setNavigationOpen(true)} /> : null}
  />
  <div className="app-shell-layout">
    {!shellOverlay ? (
      <aside className="app-shell-navigation" aria-label="主要導覽">
        <ShellNavigation currentView={view} onNavigate={navigate} />
      </aside>
    ) : null}
    <div className="app-shell-content">{selectedSurface}</div>
  </div>
  <Drawer open={shellOverlay && navigationOpen} title="導覽" onClose={() => setNavigationOpen(false)}>
    <ShellNavigation currentView={view} onNavigate={navigate} onAfterNavigate={() => setNavigationOpen(false)} />
  </Drawer>
</div>
```

Build `selectedSurface` immediately before this return by moving the existing ticker/detail plus exhaustive shipped-view conditional unchanged; do not introduce a dynamic registry or fallback `規劃中` surface.

When `shellOverlay` flips false, close the navigation Drawer in an effect. Do not render two focusable navigation copies at once.

- [x] **Step 4: Implement namespaced shell CSS with stable dimensions**

The minimum contract is:

```css
.app-shell {
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100vh;
}

.app-shell-layout {
  display: grid;
  grid-template-columns: minmax(184px, 216px) minmax(0, 1fr);
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.app-shell[data-shell-overlay="true"] .app-shell-layout {
  grid-template-columns: minmax(0, 1fr);
}

.app-shell-navigation,
.app-shell-content {
  min-width: 0;
  min-height: 0;
}
```

Add namespaced rules for top-bar slots, diagnostic row, grouped nav, work rows, and narrow menu control. Use existing color/radius/spacing variables and wrap long labels. Do not use viewport-scaled font sizes, negative letter spacing, nested cards, gradients, or decorative shapes.

- [x] **Step 5: Remove only superseded legacy shell styles and markup**

Delete from `styles.css` the old `.shell`, `.topbar*`, `.body.rail-*`, `.leftnav`, `.navitem`, `.rightrail*`, `.rail-tab*`, and their shell-specific 760px overrides. Leave unrelated component-local 760/900/1100 responsive debt untouched for its owning slices.

Delete `railOpen`, placeholder copy, rail markup, and edge-tab markup from `App.tsx`. Import `./shell/shell.css` in `main.tsx` after `styles.css` and before/alongside `ui/primitives.css` so shared variables exist and namespaced shell rules are explicit.

- [x] **Step 6: Run CSS contracts, mounted shell tests, full frontend, typecheck, and build**

```bash
npm test --workspace apps/arkscope-web -- src/shell/ShellCss.test.ts src/AppShell.test.tsx src/shell/ShellNavigation.test.tsx src/shell/ShellTopBar.test.tsx
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected: `5 CSS tests` and all focused suites pass; full frontend, typecheck, and build remain green with only the existing chunk warning.

- [x] **Step 7: Commit shell convergence**

```bash
git add apps/arkscope-web/src/App.tsx apps/arkscope-web/src/main.tsx apps/arkscope-web/src/styles.css apps/arkscope-web/src/shell/shell.css apps/arkscope-web/src/shell/ShellCss.test.ts
git commit -m "feat: converge the responsive application shell"
```

## Task 7: Run Ratchets, Responsive Gates, and Stop Review-Ready

**Files:**

- Modify: `docs/superpowers/plans/2026-07-16-p2-8-slice-2-shell-convergence.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Reconcile the exact frontend test ledger**

The reviewed target is:

| Test file | New collected nodes |
| --- | ---: |
| `shell/navigation.test.ts` | 6 |
| `shell/ShellNavigation.test.tsx` | 6 |
| `shell/ShellTopBar.test.tsx` | 11 |
| `shell/researchWork.test.tsx` | 12 |
| `shell/BackgroundWorkIndicator.test.tsx` | 10 |
| `AppShell.test.tsx` | 8 |
| `ResearchShellNavigation.test.tsx` | 3 |
| `shell/ShellCss.test.ts` | 5 |
| additions to `SettingsModelRouting.test.ts` | 2 |
| **Total** | **63** |

Expected final frontend accounting: **54 files / 516 tests**, added/removed collection **+63 / -0** from base **46 / 453**. If implementation review adds a regression test, first record its RED, update every ledger total, and explain the delta; never force counts to match this estimate.

- [x] **Step 2: Run static scope, privacy, and semantic ratchets**

```bash
git diff --exit-code 29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb -- src data_sources tests
git diff --name-only 29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb...HEAD
rg -n --glob '!*.test.*' "rightrail|rail-tab|railOpen|rail-open|rail-closed" apps/arkscope-web/src/App.tsx apps/arkscope-web/src/shell apps/arkscope-web/src/styles.css
rg -n --glob '!*.test.*' "Alerts|Notes|研究筆記|告警|規劃中" apps/arkscope-web/src/App.tsx apps/arkscope-web/src/shell
rg -n --glob '!*.test.*' "run\.(error|question|credential_id|token_usage)|credentialId|tokenUsage" apps/arkscope-web/src/shell
rg -n "@media|960|959|961" apps/arkscope-web/src/shell/shell.css
git diff 29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb...HEAD -- apps/arkscope-web/src | rg "^\+.*window\.confirm"
```

Expected: backend diff is empty; changed names are only the files in this plan; all five `rg` ratchets produce no matches. The DTO projection test remains the stronger proof that prompt/error/token/credential fixture values never enter work state or session storage.

- [x] **Step 3: Run frontend verification from a clean process**

```bash
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
```

Expected: final reconciled file/test ledger passes, typecheck passes, and build passes with only the existing chunk-size warning. No watch process remains.

- [x] **Step 4: Run a disposable responsive/interaction gate**

Start a scheduler-disabled sidecar against `/tmp/arkscope-p2-8-slice-2.db` and Vite on unused 84xx ports. After sidecar startup, seed one disposable Research thread and queued run through `ResearchThreadStore.ensure_thread()` and `ResearchRunStore.create_run()` directly against that temporary DB; do not dispatch a real model call and do not use the real profile DB.

Use separate terminals and record their PIDs:

```bash
ARKSCOPE_API_PORT=8421 ARKSCOPE_API_RELOAD=0 ARKSCOPE_DISABLE_SCHEDULER=1 ARKSCOPE_PROFILE_DB=/tmp/arkscope-p2-8-slice-2.db python -m src.api
```

```bash
VITE_API_BASE=http://127.0.0.1:8421 ARKSCOPE_WEB_DEV_PORT=8432 npm run dev --workspace apps/arkscope-web -- --host 127.0.0.1
```

After `/healthz` responds, seed without invoking the execution manager:

```bash
python -c "from src.research_threads import ResearchThreadStore; from src.research_runs import ResearchRunStore; p='/tmp/arkscope-p2-8-slice-2.db'; ResearchThreadStore(p).ensure_thread(id='shell-fixture-thread', title='Shell fixture research'); ResearchRunStore(p).create_run(id='shell-fixture-run', thread_id='shell-fixture-thread', question='fixture only', ticker=None, provider='openai', model='fixture-model', effort='low', auth_mode='api_key', credential_id=None)"
```

Inspect DOM and capture screenshots under `/tmp` at:

```text
1440x900
1024x768
961x768
960x768
959x768
390x844
```

Prove:

1. 961px has one persistent grouped navigation and two layout columns; 960px and below have one menu trigger, no persistent nav, and zero reserved rail width.
2. Notes/Alerts/planned controls and the placeholder right rail are absent at every width.
3. Normal topbar never shows raw API base, tool count, polling time, or fixed-task model.
4. System / Health toggles Developer Mode; diagnostics appear only in its secondary row and persist across a browser reload.
5. The seeded run appears without waiting for a second shell cycle; opening/closing the Drawer traps/restores focus and states that navigation does not cancel work.
6. Change the disposable run to `succeeded` with `ResearchRunStore.mark_terminal()`. Within one direct 5-second active-run cycle it becomes attention, exposes no prompt/result/error payload, and its row opens the exact Research thread.
7. The same thread and Settings section can be requested twice; each request applies, but local in-page selection remains possible afterward.
8. No page-level horizontal overflow, clipped topbar text, overlapping work rows, blank third column, or duplicate focusable nav exists.

Stop the temporary sidecar/Vite/Chrome processes and remove only `/tmp` fixture data/screenshots after evidence is recorded. Do not restart, stop, or mutate the user's normal desktop app for this gate.

- [x] **Step 5: Verify constructive backend A/B equivalence**

Because this slice modifies no backend byte, the stronger proof is:

```bash
git diff --exit-code 29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb -- src data_sources tests
git diff --name-status 29f37f86993a0f1ce7ad8289f3e51d6fc5620dfb...HEAD -- src data_sources tests
```

Expected: both commands are empty. Record backend collection delta `+0 / -0` and state that canonical backend A/B was intentionally replaced by byte identity; do not spend ten minutes running identical archives or claim an independently executed backend A/B.

- [x] **Step 6: Mark the branch implementation review-ready and stop**

After every gate above passes:

1. Change this plan status to `IMPLEMENTED FOR REVIEW`, preserving all RED/GREEN evidence and actual counts.
2. Add a newest-first priority-map entry with branch/tip, exact test ledger, responsive screenshot paths, and reviewer focus.
3. Keep the canonical spec status `APPROVED`; do not mark Slice 2 LIVE before review and merge.
4. Do not sync the external Design Kit yet. After implementation review, sync only shipped Slice 2 shell/screens and record that separate gate.
5. Do not merge, delete the worktree, start Slice 3, or modify the user's normal desktop process.

Recommended review focus:

1. only one IA/target metadata authority exists;
2. planned items are absent rather than disabled;
3. Developer Mode is display-only and normal mode has no diagnostic leaks;
4. registry persistence contains identities only and poll failures preserve prior truth;
5. fast Research runs cannot escape observation between shell polls;
6. terminal discovery is bounded to current-session observed IDs, not advertised as history;
7. repeated exact targets apply once per sequence without pinning local selection;
8. 961/960 behavior follows the token with no second breakpoint;
9. closed Drawers and removed rail reserve zero width; and
10. no backend, Settings IA, Research execution, or fixed-task behavior changed.

- [x] **Step 7: Commit review-ready evidence**

```bash
git add docs/superpowers/plans/2026-07-16-p2-8-slice-2-shell-convergence.md docs/design/PROJECT_PRIORITY_MAP.md
git commit -m "docs: mark p2.8 slice 2 shell review-ready"
```
