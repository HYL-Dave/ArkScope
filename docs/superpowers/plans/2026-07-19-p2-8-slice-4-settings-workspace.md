# P2.8 Slice 4 Settings Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task by task. Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** IMPLEMENTATION IN PROGRESS — TASK 3 COMPLETE

> **Independent plan review (2026-07-19):** GREEN with no must-fix. Exact
> accounting is locked at frontend `+34/-0`; implementation must stop
> review-ready for an independent code review before merge.

**Goal:** Replace the category-switched 3,742-line Settings surface with one
compact, searchable, workflow-grouped workspace while preserving every shipped
setting authority and mutation contract.

**Architecture:** First extract the existing sections without changing their
rendering, tests, API calls, or CSS. Then introduce one static Settings registry
for group/anchor/search metadata, one fail-closed collapse preference, and one
responsive directory that is persistent above the canonical shell breakpoint
and a transient Drawer at or below it. `SettingsView` remains the controller for
the shared model catalog and route mutations; extracted section modules continue
to own their existing independent reads and writes. The final page always renders
its three shipped workflow groups, while model-catalog loading/failure is confined
to the AI group instead of hiding unrelated settings.

**Tech Stack:** React 18, TypeScript, Vitest/jsdom, existing ArkScope UI
primitives and `lucide-react`, Vite/Electron, CSS driven by the reviewed
`shellOverlayBreakpointPx = 960` token, and Git worktree/byte-identity gates.
The Python backend, API DTOs, databases, schedulers, provider calls, and browser
extension are out of scope.

---

## Design Authority and Locked Decisions

1. The design authority is
   `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`,
   especially Sections 5, 9, 12.3, 12.4, 13 Slice 4, 14, and 15. This plan may
   make implementation details concrete but may not weaken the grouped
   single-page, search, remembered-collapse, exact-anchor, responsive, or
   pure-move contracts.
2. Slice 2's later reviewed decision is also authoritative: Developer Mode is
   owned by System / Health and does not alter Settings IA. Slice 4 must not
   duplicate or move that control.
3. The final normal Settings page has exactly three non-empty groups, in this
   order:

   | Group | Visible sections, in order |
   |---|---|
   | `ai_models` — `AI 與模型` | `providers`, `models`, `fixed_task_runtime`, `research_runtime` |
   | `personalization` — `個人化` | `investor_profile` |
   | `data_sync` — `資料與同步` | `data_sources`, `data_storage`, `news_storage`, `macro_storage` |

   Provider login/credential discovery remains separate from model routing.
   Providers appears first because it supplies the executable credential context;
   model routing, fixed-task limits, and Research limits stay adjacent.
4. `app_records` and `permissions` remain absent from normal rendering, search,
   focus order, anchor metadata, and `NavigationTarget`. Do not render an empty
   `App and Advanced` group. The disabled historical App Records implementation
   may be mechanically extracted for compatibility, but this slice neither
   revives it nor changes its backend routes.
5. Investor Profile moves into the `個人化` group without changing its form,
   calibration, proposal, prompt-injection, risk-mismatch, or save semantics.
   Summary-first/profile-scenario redesign remains Slice 5.
6. Existing model/provider/data-source behavior is preserved. This slice does
   not change credential precedence, discovery, route eligibility, task tests,
   runtime timeout ranges, schedule cadence, polling, provider configuration,
   health interpretation, data queries, or mutation bodies.
7. The generic page heading is `設定`. Model-only copy, route actions, and the
   four-cell runtime summary no longer occupy the global header. Save stays
   visible in `模型與任務路由`; import/export moves into a closed advanced
   disclosure in that same section. The redundant global runtime band is removed:
   route cards and Provider credential context remain the owned facts.
8. The visible section titles use current user vocabulary:

   | Anchor | Primary visible title |
   |---|---|
   | `providers` | `Provider 登入與憑證` |
   | `models` | `模型與任務路由` |
   | `fixed_task_runtime` | `固定 AI 任務執行限制` |
   | `research_runtime` | `AI 研究執行限制` |
   | `investor_profile` | `投資人設定` |
   | `data_sources` | `資料來源與排程` |
   | `data_storage` | `市場資料` |
   | `news_storage` | `新聞資料` |
   | `macro_storage` | `總體經濟與行事曆` |

   English/provider terms remain static search aliases where useful; they do
   not force mixed-language headings everywhere.
9. Search is over reviewed static metadata only: section title, concise
   description, and allowlisted EN/zh keywords. It never indexes DOM text,
   credential aliases, account labels, model discovery results, provider errors,
   paths, tokens, or any other dynamic value. The default directory remains
   compact and renders section titles only; descriptions are search metadata,
   not always-visible rail prose.
10. Typing filters the directory results but never removes or reorders page
    content. Selecting a result, clicking an anchor, pressing Enter on a non-empty
    result set, or consuming a shell target expands the owning group, closes the
    narrow Drawer, scrolls the exact section into view, and focuses its
    `tabIndex=-1` anchor. A no-result query shows neutral text, not a disabled
    control.
11. Collapse preference is stored under
    `arkscope.settings.collapsedGroups.v1`. First use, unavailable storage,
    malformed JSON, wrong shape, and unknown-only values all fail closed to every
    shipped group expanded. Only known group IDs are persisted.
12. A collapsed group unmounts its body. This stops hidden Data Sources polling
    and avoids retaining invisible controls. Selecting an exact target expands
    and persists that group before focus. Search itself does not rewrite collapse
    state until the user selects a result.
13. The compact directory is persistent only when `useShellOverlay()` is false.
    At 960px and below, exactly one `設定目錄` button opens the existing transient
    `Drawer`; no duplicate focusable directory remains in the DOM. Closed Drawer
    width is zero and focus returns to its trigger.
14. The Settings implementation does not contain a numeric 959/960/961 shell
    breakpoint or a new `matchMedia` owner. CSS keys responsive layout from a
    component `data-settings-overlay` value supplied by `useShellOverlay()`.
15. Group and section wrappers are unframed full-width bands. Do not put a group
    card around existing task/provider/tool cards. The persistent directory is
    likewise an unframed rail, not a card nested beside cards.
16. New page/directory/collapse/search/confirmation controls use existing
    `PageHeader`, `Button`, `IconButton`, `Drawer`, and `ConfirmDialog` plus
    `lucide-react` icons. Existing specialized controls remain behaviorally
    unchanged unless this plan explicitly names them.
17. The two remaining Settings `window.confirm` owners are repaid here:
    guarded provider-config edits and credential deletion use `ConfirmDialog`.
    Confirm/cancel/focus semantics are tested; mutation functions and payloads
    remain unchanged.
18. Model catalog loading or failure may not hide Investor Profile or any data
    group. Dependent AI content presents a bounded local state; unrelated section
    components remain mounted and independently usable.
19. Normal-mode raw-error cleanup beyond code newly introduced by this slice is
    not expanded into a provider/API error-redesign project. No new raw exception
    interpolation may be added, and the new catalog-level state uses stable user
    copy rather than the thrown message.
20. Every test node addition/removal/rename is accounted below. Any unreviewed
    collection drift, backend/API/DTO change, duplicated model authority, new
    setting, new persistence key, new provider call, or Investor Profile semantic
    change is a stop-and-review condition.

---

## Grounded Baseline and Exact Accounting

- Plan authoring base: `72fc39f` (`docs: record post-restart universe
  verification`). The worktree is clean; `master` is ahead of `origin/master`
  by 22 commits, and pushing remains user-owned.
- Current production shape, rechecked on this base:
  - `apps/arkscope-web/src/Settings.tsx`: exactly 3,742 lines;
  - current Settings renders one of seven enabled technical categories at a
    time behind `catalog && ...`;
  - the global title remains `模型與任務路由` even for non-model categories;
  - the global runtime band and route actions are model-specific;
  - two production `window.confirm` calls remain, at guarded provider config
    and credential deletion;
  - the directory still uses `.settings-nav-card` and
    `.settings-section-button`;
  - only `models`, `providers`, `investor_profile`, `data_storage`,
    `news_storage`, `macro_storage`, and `data_sources` are actionable shell
    Settings targets.
- Current full frontend baseline, freshly reproduced:

  ```text
  Test Files  60 passed (60)
  Tests       572 passed (572)
  ```

- Current focused baseline is exactly `15 files / 101 tests`:

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/CredentialList.test.ts \
    src/DiscoveryResultView.test.ts \
    src/FixedTaskRuntimeSection.test.tsx \
    src/ModelRoutingSection.test.ts \
    src/ProviderSection.test.ts \
    src/ResearchRuntimeSection.test.ts \
    src/SettingsDisclosure.test.ts \
    src/SettingsModelRouting.test.ts \
    src/SettingsNewsStorage.test.ts \
    src/SettingsPostPgExitStorage.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/SettingsStabilizationCss.test.ts \
    src/InvestorProfilePanel.test.tsx \
    src/shell/navigation.test.ts \
    src/ui/classCoverage.test.ts
  ```

- Reviewed raw frontend accounting target is exactly `+34/-0`:

  | Test owner | Added | Removed | Net |
  |---|---:|---:|---:|
  | `settings/settingsRegistry.test.ts` | 10 | 0 | +10 |
  | `SettingsWorkspace.test.tsx` | 13 | 0 | +13 |
  | `SettingsModelRouting.test.ts` | 5 | 0 | +5 |
  | `CredentialList.test.ts` | 2 | 0 | +2 |
  | `SettingsProviderConfig.test.ts` | 1 | 0 | +1 |
  | `SettingsCss.test.ts` | 3 | 0 | +3 |
  | **Total** | **34** | **0** | **+34** |

- Existing tests may be strengthened or updated in place for the grouped DOM,
  exact anchors, and ConfirmDialog, but no existing node ID is removed or
  renamed. Parameterized additions require counting collected node IDs, not
  source functions.
- Reviewed targets are focused `101 -> 135`, full frontend
  `60 files / 572 tests -> 63 files / 606 tests`, clean typecheck, and clean
  production build except the existing chunk-size warning.
- This is frontend-only. Canonical backend equivalence is constructive:
  `git diff --exit-code IMPLEMENTATION_BASE -- src data_sources tests` must be
  empty. Do not spend a full backend A/B run to compare byte-identical trees.

---

## Execution Ledger

```text
PLAN_REVIEW_CLEARANCE_COMMIT: 7e56bce508e0ec74e9d74a61e0250f2dc200bb2f
IMPLEMENTATION_BASE: 7e56bce508e0ec74e9d74a61e0250f2dc200bb2f
IMPLEMENTATION_BRANCH: codex/p2-8-slice-4-settings
IMPLEMENTATION_WORKTREE: /tmp/arkscope-p2-8-slice-4
WORKTREE_MATERIALIZATION: initial checkout stopped at the known linked-worktree git-crypt smudge boundary; retry used --no-checkout, copied only .git/git-crypt/keys/default into linked Git metadata, then git read-tree -mu HEAD; final status clean
FOCUSED_BASELINE: 15 files / 101 tests passed
FRONTEND_BASELINE: 60 files / 572 tests passed
TYPECHECK_BASELINE: clean
BUILD_BASELINE: clean except the reviewed chunk-size warning (595.06 kB main bundle)
STRUCTURAL_BASELINE: Settings.tsx 3742 lines; two window.confirm owners; settings-band/settings-nav-card/settings-section-button present
TASK_1_TEST_GUARD: recursive source coverage first exposed nine pre-existing undefined Settings classes; Task 1 pins that exact unordered debt set so pure-move cannot add drift, and Task 6 owns reducing it to zero
TASK_1_EXTRACTION: Settings.tsx 3742 -> 671 lines; seven section modules plus one legacy module; source-level base comparison PASS for controller and every moved JSX/function block
TASK_1_VERIFICATION: focused 15 files / 101 tests; full frontend 60 files / 572 tests; typecheck/build clean except reviewed chunk warning
TASK_1_PRODUCT_COMMIT: 6195026 (pure extraction); ledger commit 8489ae4
TASK_2_RED: settingsRegistry.test.ts failed because settingsRegistry/settingsPreferences did not exist
TASK_2_GREEN: registry/preferences 10 nodes added; navigation node strengthened in place; SettingsSection type-only union widened to close the nine-anchor compiler contract before Task 3 rendering; full frontend 61 files / 582 tests; typecheck clean
TASK_2_PRODUCT_COMMIT: 9c38c4e; ledger commit 3b209b0
TASK_3_RED: 13 workspace nodes collected; 12 failed for the reviewed old shell shape and the existing App Records exclusion node remained green
TASK_3_INTEGRATION: one-page mounting required zero-node helper evolution in SettingsNewsStorage/SettingsProviderConfig and focus-based evolution of the two existing model navigation nodes; class coverage began reading settings.css; the existing save-route contract required moving its button into the models anchor before the Task 4 import/export and catalog-isolation work
TASK_3_GREEN: 13/13 new workspace nodes; full frontend 62 files / 595 tests; typecheck/build clean except the reviewed chunk warning (594.11 kB main bundle)
TASK_3_PRODUCT_COMMIT: ef30ef8
```

Product RED/GREEN commits, exact collection reconciliation, static gates, and
browser evidence are appended here as they exist. Do not pre-fill passing
claims.

---

## File Map

### Create

- `apps/arkscope-web/src/settings/settingsRegistry.ts` — single group/anchor,
  title, description, keyword, DOM-ID, owner-group, and deterministic search
  authority.
- `apps/arkscope-web/src/settings/settingsRegistry.test.ts` — ten pure registry,
  search, and collapse-storage contracts.
- `apps/arkscope-web/src/settings/settingsPreferences.ts` — versioned,
  fail-closed recognized-group collapse persistence.
- `apps/arkscope-web/src/settings/SettingsDirectory.tsx` — shared wide/Drawer
  directory body, static search, group/result controls, and no product data.
- `apps/arkscope-web/src/settings/SettingsSectionAnchor.tsx` — stable focusable
  section wrapper and full-width group wrapper.
- `apps/arkscope-web/src/settings/ModelRoutingSection.tsx` — pure-moved model
  cards, task-test presentation, and model notes.
- `apps/arkscope-web/src/settings/RuntimeLimitSections.tsx` — pure-moved fixed
  task and Research runtime limit panels.
- `apps/arkscope-web/src/settings/ProviderSection.tsx` — pure-moved Provider,
  credential, setup, probe, discovery, and login UI.
- `apps/arkscope-web/src/settings/DataStorageSection.tsx` — pure-moved market
  storage and trading-day coverage UI.
- `apps/arkscope-web/src/settings/NewsStorageSection.tsx` — pure-moved news
  storage UI.
- `apps/arkscope-web/src/settings/MacroStorageSection.tsx` — pure-moved macro
  storage UI.
- `apps/arkscope-web/src/settings/DataSourcesSection.tsx` — pure-moved provider
  health/config/schedule UI and its existing dual-cadence polling.
- `apps/arkscope-web/src/settings/legacy/AppRecordsSection.tsx` — mechanically
  preserved disabled compatibility surface; never registered or rendered.
- `apps/arkscope-web/src/settings/settings.css` — namespaced page/group/directory
  layout driven by `data-settings-overlay`, with no numeric shell breakpoint.
- `apps/arkscope-web/src/SettingsWorkspace.test.tsx` — thirteen mounted
  single-page, directory, search, collapse, responsive, and accessibility nodes.
- `apps/arkscope-web/src/SettingsCss.test.ts` — three CSS/source ratchet nodes.

### Modify

- `apps/arkscope-web/src/Settings.tsx` — thin Settings controller/composition,
  grouped page, shared catalog/route state, exact-target reveal, and compatibility
  re-exports for existing tests/importers.
- `apps/arkscope-web/src/main.tsx` — preserve the existing `styles.css` ->
  `shell.css` -> `primitives.css` order, then import `settings/settings.css` as
  the final Settings-owned cascade layer.
- `apps/arkscope-web/src/styles.css` — remove superseded legacy Settings page
  directory/runtime-band layout only; retain specialized model/provider/data
  component rules until their own owners change.
- `apps/arkscope-web/src/shell/navigation.ts` — derive the actionable Settings
  target union from the registry, adding fixed-task and Research-runtime anchors
  without changing the target kind or dispatcher.
- `apps/arkscope-web/src/shell/navigation.test.ts` — strengthen the existing
  Settings-target node in place for every reviewed anchor; zero new node.
- `apps/arkscope-web/src/SettingsStabilizationCss.test.ts` — recursively read
  extracted Settings sources while retaining its two existing node IDs.
- `apps/arkscope-web/src/ui/classCoverage.test.ts` — strengthen one existing
  node to cover every extracted Settings TSX file; zero new node.
- `apps/arkscope-web/src/SettingsModelRouting.test.ts` — evolve four existing
  nodes and add exactly five catalog/action/exact-target contracts.
- `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts` — evolve the existing
  five directory/category assertions to grouped single-page semantics; no node
  change.
- `apps/arkscope-web/src/SettingsProviderConfig.test.ts` — evolve the guarded
  confirm node and add one cancel/focus node.
- `apps/arkscope-web/src/CredentialList.test.ts` — add two credential-delete
  dialog/focus nodes.
- Remaining existing Settings tests — import through `./Settings` compatibility
  re-exports and remain node/behavior equivalent unless explicitly named.
- This plan and `docs/design/PROJECT_PRIORITY_MAP.md` — status, exact ledger,
  independent review, and closeout evidence only.

### Must Not Modify

- `src/**`, `data_sources/**`, and `tests/**`
- `apps/arkscope-web/src/api.ts` and all API request/DTO shapes
- `apps/arkscope-web/src/InvestorProfilePanel.tsx` and its domain helpers
- `apps/arkscope-web/src/Dashboard.tsx` and Developer Mode ownership
- `apps/arkscope-web/src/shell/ShellNavigation.tsx`, top bar, and background work
- `extensions/**`
- production SQLite files, profile settings, credentials, schedules, model
  routes, and `data/backups/**`
- external Design Kit files until implementation review is GREEN

---

## Acceptance Trace

| Approved outcome | Owning tasks | Hard proof |
|---|---|---|
| Pure module extraction before IA edits | 0, 1 | exact 83 Settings tests and 572 full tests unchanged in extraction commit |
| Three workflow groups, all expanded first-use | 2, 3 | registry order/uniqueness plus mounted DOM |
| One scannable page, not nested routes | 3 | all nine anchors present together with fresh preferences; content remains during search |
| Search crosses collapsed groups | 2, 3 | static index; result selection expands, scrolls, focuses |
| Remembered collapse | 2, 3 | versioned fail-closed storage + remount test |
| Exact Settings anchors | 2, 4 | registry-derived target union; sequence and focus tests |
| Wide rail / narrow Drawer | 3, 6, 7 | `useShellOverlay`, focus restore, six viewport gate |
| Generic page hierarchy and local model actions | 4 | PageHeader, no global runtime band, closed import/export disclosure |
| Catalog failure isolation | 4 | deferred/rejected catalog mounted tests |
| No disabled/historical placeholders | 2, 3, 6 | registry/DOM/source absence |
| Provider/Models ownership stays distinct | 2, 4 | registry order plus unchanged leaf suites |
| Investor semantics unchanged | 1, 3, 7 | unchanged 9-node Investor suite and byte diff |
| Settings confirms use shared primitive | 5 | confirm/cancel/mutation/focus tests and zero `window.confirm` ratchet |
| Compact unified layout | 3, 6, 7 | shared primitives, unframed bands, class coverage, visual gate |

---

## Task 0: Review Clearance, Worktree, and Baseline

**Files:**
- Modify later: this plan's execution ledger only

- [x] **Step 1: Record independent plan-review clearance**

  Do not implement from this draft commit. After independent review returns
  GREEN, update the status to `CLEARED FOR IMPLEMENTATION`, commit that docs-only
  change, and record its full hash as `PLAN_REVIEW_CLEARANCE_COMMIT`.

- [x] **Step 2: Create an isolated worktree from the clearance commit**

  ```bash
  git worktree add /tmp/arkscope-p2-8-slice-4 -b codex/p2-8-slice-4-settings PLAN_REVIEW_CLEARANCE_COMMIT
  ```

  Record `IMPLEMENTATION_BASE=$(git rev-parse HEAD)` and prove the worktree is
  clean. Do not reuse the running master checkout or disturb the user's desktop.

- [x] **Step 3: Reproduce the exact baseline**

  Run the 15-file focused command above and the complete frontend suite.
  Expected: `101` focused and `60/572` full. Then run:

  ```bash
  npm run typecheck --workspace apps/arkscope-web
  npm run build --workspace apps/arkscope-web
  ```

  Record the existing build warning separately; any test drift is a stop.

- [x] **Step 4: Record the structural inventory**

  Confirm before RED:

  ```bash
  wc -l apps/arkscope-web/src/Settings.tsx
  rg -n "window\.confirm|settings-nav-card|settings-section-button|settings-band" \
    apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/styles.css
  ```

  Expected: 3,742 lines, two `window.confirm` owners, and all three superseded
  layout families present.

- [x] **Step 5: Commit no product changes in Task 0**

  Add the baseline evidence to this plan ledger only after it exists. Task 1 is
  the first code task.

---

## Task 1: Pure-Move Settings Section Extraction

**Files:**
- Create: the seven section modules and one legacy module listed in File Map
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/SettingsStabilizationCss.test.ts`
- Modify: `apps/arkscope-web/src/ui/classCoverage.test.ts`
- Test: all existing Settings/Investor tests; no new test node

**Contract:** Move code before changing IA. The extraction commit preserves the
current category-switched DOM, catalog gate, labels, API calls, state ownership,
CSS classes, exports, and all 572 frontend nodes.

- [x] **Step 1: Make source-based tests extraction-safe without changing nodes**

  Evolve `SettingsStabilizationCss.test.ts` so its two existing tests concatenate
  `Settings.tsx` plus every `.tsx` below `src/settings/`, discovered recursively
  and sorted. On the pre-extraction tree this remains equivalent; after files
  move, the same test source requires no further edit.

  Strengthen the existing class-coverage node in the same way: literal classes
  from every extracted Settings TSX file must resolve in `styles.css` or
  `ui/primitives.css`. Keep the existing node ID.

- [x] **Step 2: Run the unchanged GREEN baseline**

  Run the 15-file command. Expected: exactly `101 passed`; collection must not
  change.

- [x] **Step 3: Move leaf components by responsibility**

  Move functions and their private helpers without rewriting them:

  - model cards/test presentation -> `ModelRoutingSection.tsx`;
  - fixed/Research limits -> `RuntimeLimitSections.tsx`;
  - Provider/credential/setup/probe/discovery -> `ProviderSection.tsx`;
  - market/trading coverage -> `DataStorageSection.tsx`;
  - news -> `NewsStorageSection.tsx`;
  - macro -> `MacroStorageSection.tsx`;
  - provider health/config/schedule/polling -> `DataSourcesSection.tsx`;
  - disabled App Records -> `settings/legacy/AppRecordsSection.tsx`.

  Keep `SettingsView`, route draft/controller helpers, and current section switch
  in `Settings.tsx` for this commit.

- [x] **Step 4: Preserve compatibility imports and exports**

  `Settings.tsx` must import the moved bindings it still renders locally and
  re-export the names existing tests and consumers import. A forwarding export
  alone does not create a local binding:

  ```ts
  import {
    ModelRoutingSection,
  } from "./settings/ModelRoutingSection";
  import {
    FixedTaskRuntimeSection,
    ResearchRuntimeSection,
  } from "./settings/RuntimeLimitSections";
  import {
    CredentialList,
    DiscoveryResultView,
    ProviderSection,
    SetupDisclosure,
  } from "./settings/ProviderSection";

  export { ModelRoutingSection } from "./settings/ModelRoutingSection";
  export { FixedTaskRuntimeSection, ResearchRuntimeSection } from "./settings/RuntimeLimitSections";
  export {
    CredentialList,
    DiscoveryResultView,
    ProviderSection,
    SetupDisclosure,
  } from "./settings/ProviderSection";
  ```

  Do not update existing importers merely to make the move visible.

- [x] **Step 5: Prove pure-move equivalence**

  Run all 12 current Settings-focused files: exactly `83 passed`. Run the full
  frontend: exactly `60 files / 572 tests`. Typecheck and build must pass.

  Also inspect the extraction commit with:

  ```bash
  git diff --color-moved=dimmed-zebra IMPLEMENTATION_BASE -- \
    apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/settings
  ```

  No label, branch, request, mutation, class, or JSX structure change is allowed.

- [x] **Step 6: Commit the pure move**

  ```bash
  git add apps/arkscope-web/src/Settings.tsx \
    apps/arkscope-web/src/settings \
    apps/arkscope-web/src/SettingsStabilizationCss.test.ts \
    apps/arkscope-web/src/ui/classCoverage.test.ts
  git commit -m "refactor: extract settings sections"
  ```

---

## Task 2: Registry, Search Authority, and Collapse Preference

**Files:**
- Create: `apps/arkscope-web/src/settings/settingsRegistry.ts`
- Create: `apps/arkscope-web/src/settings/settingsPreferences.ts`
- Create: `apps/arkscope-web/src/settings/settingsRegistry.test.ts`
- Modify: `apps/arkscope-web/src/shell/navigation.ts`
- Modify: `apps/arkscope-web/src/shell/navigation.test.ts`

**Contract:** One non-React registry owns every visible group/anchor and every
search alias. Shell target typing consumes that authority instead of maintaining
a second seven-value list.

- [x] **Step 1: Add exactly ten RED registry/preference nodes**

  Add these non-parameterized tests:

  1. `declares_three_nonempty_groups_in_workflow_order`
  2. `assigns_every_shipped_anchor_exactly_once`
  3. `keeps_provider_login_separate_and_before_model_routing`
  4. `keeps_fixed_and_research_limits_adjacent_to_model_routing`
  5. `excludes_app_records_permissions_and_empty_advanced_groups`
  6. `indexes_reviewed_chinese_english_and_provider_terms`
  7. `returns_deterministic_static_matches_without_dynamic_values`
  8. `defaults_every_group_expanded_when_storage_is_absent`
  9. `round_trips_only_known_collapsed_group_ids`
  10. `fails_closed_to_expanded_for_malformed_or_unknown_storage`

  RED must be missing modules/exports, not a fixture typo.

- [x] **Step 2: Implement the exact registry shape**

  Use literal readonly data with this public shape:

  ```ts
  export type SettingsGroupId = "ai_models" | "personalization" | "data_sync";

  export type SettingsAnchorId =
    | "providers"
    | "models"
    | "fixed_task_runtime"
    | "research_runtime"
    | "investor_profile"
    | "data_sources"
    | "data_storage"
    | "news_storage"
    | "macro_storage";

  export interface SettingsSectionDefinition {
    id: SettingsAnchorId;
    group: SettingsGroupId;
    title: string;
    description: string;
    keywords: readonly string[];
  }

  export interface SettingsGroupDefinition {
    id: SettingsGroupId;
    title: string;
    sections: readonly SettingsSectionDefinition[];
  }

  export const SETTINGS_GROUPS: readonly SettingsGroupDefinition[] = /* exact table above */;
  export const SETTINGS_ANCHOR_IDS: readonly SettingsAnchorId[] = /* flattened, unique */;
  export function settingsSection(id: SettingsAnchorId): SettingsSectionDefinition;
  export function settingsGroupFor(id: SettingsAnchorId): SettingsGroupDefinition;
  export function settingsAnchorDomId(id: SettingsAnchorId): string;
  export function searchSettings(query: string): readonly SettingsSectionDefinition[];
  ```

  `searchSettings` applies `normalize("NFKC")`, trim, and lower-case to static
  fields only. Blank query returns all sections in registry order. Matching does
  not inspect the DOM or runtime objects.

- [x] **Step 3: Implement fail-closed preferences**

  ```ts
  export const SETTINGS_COLLAPSE_STORAGE_KEY = "arkscope.settings.collapsedGroups.v1";

  export function readCollapsedSettingsGroups(
    storage?: Pick<Storage, "getItem">,
  ): ReadonlySet<SettingsGroupId>;

  export function writeCollapsedSettingsGroups(
    collapsed: ReadonlySet<SettingsGroupId>,
    storage?: Pick<Storage, "setItem">,
  ): void;
  ```

  Resolve `window.localStorage` inside each function's `try` block only when an
  explicit storage is absent; an unavailable `window`, a throwing storage
  getter, and throwing `getItem`/`setItem` all fail closed. Store a sorted JSON
  array. Reads retain recognized IDs and drop unknown IDs;
  malformed/non-array/unknown-only input yields an empty set, meaning all groups
  expanded.

- [x] **Step 4: Make shell target typing consume the registry**

  In `shell/navigation.ts`:

  ```ts
  import type { SettingsAnchorId } from "../settings/settingsRegistry";
  export type EnabledSettingsSection = SettingsAnchorId;
  ```

  Keep `{ kind: "settings_section"; section: ... }`, resolver behavior, and
  sequence envelopes unchanged. Strengthen the existing navigation test node to
  loop over all nine IDs without adding collection.

- [x] **Step 5: Run GREEN and commit**

  Expected new collection: `+10`, full frontend `582`. Then:

  ```bash
  git add apps/arkscope-web/src/settings/settingsRegistry.ts \
    apps/arkscope-web/src/settings/settingsPreferences.ts \
    apps/arkscope-web/src/settings/settingsRegistry.test.ts \
    apps/arkscope-web/src/shell/navigation.ts \
    apps/arkscope-web/src/shell/navigation.test.ts
  git commit -m "feat: define settings workspace registry"
  ```

---

## Task 3: Grouped Workspace, Searchable Directory, and Responsive Drawer

**Files:**
- Create: `apps/arkscope-web/src/settings/SettingsDirectory.tsx`
- Create: `apps/arkscope-web/src/settings/SettingsSectionAnchor.tsx`
- Create: `apps/arkscope-web/src/SettingsWorkspace.test.tsx`
- Create: `apps/arkscope-web/src/settings/settings.css`
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/main.tsx`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`

**Contract:** Replace category switching with one page containing all nine
shipped anchors. The directory is navigation within the page, not another route
layer. Collapse unmounts group bodies; exact selection restores them first.

- [x] **Step 1: Add exactly thirteen RED workspace nodes**

  Add these tests with real registry/preferences and leaf components mocked only
  at their public section boundaries:

  1. `renders_generic_page_header_and_all_shipped_groups_and_anchors`
  2. `omits_legacy_model_header_runtime_band_and_global_route_actions`
  3. `renders_one_persistent_searchable_directory_on_wide_screens`
  4. `renders_one_directory_trigger_and_transient_drawer_on_narrow_screens`
  5. `collapses_persists_and_unmounts_a_group_body`
  6. `restores_remembered_collapse_while_first_use_stays_expanded`
  7. `searches_chinese_and_english_aliases_without_filtering_page_content`
  8. `selecting_a_result_expands_scrolls_and_focuses_the_exact_anchor`
  9. `enter_selects_the_first_deterministic_search_result`
  10. `shows_neutral_no_match_copy_without_a_disabled_control`
  11. `directory_selection_closes_the_narrow_drawer_and_restores_one_focus_path`
  12. `renders_no_empty_advanced_group_or_historical_disabled_section`
  13. `exposes_compact_accessible_group_toggles_with_aria_expanded`

  For scroll assertions, stub `HTMLElement.prototype.scrollIntoView` before the
  action. For focus, assert `document.activeElement` is the exact anchor. For
  responsive behavior, stub `matchMedia` before mount; do not mock
  `useShellOverlay` itself. In node 11, selection ends on the target anchor after
  Drawer cleanup; plain Escape is the path that returns focus to the trigger.

- [x] **Step 2: Add section and group wrappers**

  `SettingsSectionAnchor` renders the stable DOM ID, `tabIndex={-1}`, and a
  `data-settings-anchor` marker. It does not add a visible card or duplicate the
  leaf component heading.

  The group wrapper renders one compact heading and an `IconButton` using
  `ChevronDown`/`ChevronRight`; `aria-expanded` reflects the body. The body is
  absent, not merely hidden, when collapsed.

- [x] **Step 3: Build one reusable directory body**

  `SettingsDirectory` receives registry data, query, current target, and
  callbacks. Use a labelled search input with the `Search` icon. Render group
  labels as low-emphasis non-focusable text and section results as ordinary
  title-only navigation buttons; do not repeat technical descriptions down the
  default rail. Search may use hidden registry descriptions/aliases but still
  renders only the matched title and owning group. Do not render duplicate
  wide/narrow directories in one DOM.

- [x] **Step 4: Compose the generic page shell**

  `SettingsView` renders the narrow `設定目錄` command with a `Menu` icon and
  otherwise follows this shape:

  ```tsx
  <main className="main settings-workspace" data-settings-overlay={String(shellOverlay)}>
    <PageHeader title="設定" />
    {/* wide aside OR narrow Button + Drawer */}
    <div className="settings-workspace-layout">
      {/* directory */}
      <div className="settings-workspace-groups">{/* three groups */}</div>
    </div>
  </main>
  ```

  Keep the existing controller state/functions for now. Render every group in
  registry order. Place each existing leaf component under its corresponding
  anchor. Group collapse uses `readCollapsedSettingsGroups` at initialization
  and writes only on an explicit toggle or exact-target expansion.

- [x] **Step 5: Implement exact local reveal behavior**

  One `revealSection(id)` function must:

  1. expand and persist the owner group;
  2. close the narrow Drawer;
  3. wait one animation frame for the body to mount;
  4. `scrollIntoView({ block: "start" })` on the stable anchor;
  5. `focus({ preventScroll: true })` on that same anchor.

  Cancel/ignore a scheduled reveal after unmount. Reuse this function for
  directory clicks, search result selection, Enter, provider-to-model links,
  and shell requests.

- [x] **Step 6: Add namespaced responsive CSS**

  Import `settings/settings.css` after `ui/primitives.css` in `main.tsx`, without
  reordering the existing three shared stylesheets. Wide layout is a stable
  `minmax(190px, 230px) minmax(0, 1fr)` grid with a sticky unframed directory.
  `[data-settings-overlay="true"]` switches to one column and hides the
  persistent directory in favor of the Drawer trigger. Section/group bands use
  border separators and shared spacing tokens. Long labels wrap; anchor focus is
  visible; `scroll-margin-top` accounts for the shell top bar. Add no numeric
  media query.

- [x] **Step 7: Evolve existing directory tests in place**

  Keep all five `SettingsPostPgExitStorage.test.ts` node IDs. Replace assertions
  about active category buttons with assertions that all enabled sections are
  present together, retired App Records is absent, and user-facing titles no
  longer narrate migration history.

- [x] **Step 8: Run GREEN and commit**

  Expected cumulative collection: `+23` and full frontend `595`.

  ```bash
  git add apps/arkscope-web/src/Settings.tsx \
    apps/arkscope-web/src/SettingsWorkspace.test.tsx \
    apps/arkscope-web/src/settings/SettingsDirectory.tsx \
    apps/arkscope-web/src/settings/SettingsSectionAnchor.tsx \
    apps/arkscope-web/src/settings/settings.css \
    apps/arkscope-web/src/main.tsx \
    apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
  git commit -m "feat: group settings into one workspace"
  ```

---

## Task 4: Model Action Ownership, Catalog Isolation, and Exact Anchors

**Files:**
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/settings/ModelRoutingSection.tsx`
- Modify: `apps/arkscope-web/src/settings/ProviderSection.tsx`
- Modify: `apps/arkscope-web/src/SettingsModelRouting.test.ts`

**Contract:** The generic page no longer behaves like a Models page. Model
catalog state and actions stay inside AI-owned anchors, while unrelated groups
remain available. Existing target IDs still work and the two new runtime anchors
become exact actionable destinations.

- [ ] **Step 1: Add exactly five RED nodes**

  Add:

  1. `catalog_loading_does_not_hide_personalization_or_data_groups`
  2. `catalog_failure_stays_inside_ai_group_and_preserves_other_sections`
  3. `owns_save_in_models_and_import_export_in_a_closed_advanced_disclosure`
  4. `opens_fixed_task_runtime_from_a_sequenced_exact_target`
  5. `opens_research_runtime_only_when_the_request_sequence_advances`

  Evolve the existing Models/Providers sequence nodes in place to assert focused
  anchors rather than an `.active` category button. Do not rename them.

- [ ] **Step 2: Remove the whole-page catalog gate**

  Rename the controller's loading/error state to catalog-specific state. The
  page, groups, directory, Investor Profile, and data sections render before the
  catalog resolves and after it rejects. The AI group keeps all four stable
  anchors; dependent model/provider content shows one stable local loading or
  failure presentation. Runtime-limit anchors continue to render whenever their
  existing `runtime` fields are available.

  New catalog failure copy is stable and does not interpolate the thrown value:
  `無法載入 AI 模型設定。請重新整理，或到 System / Health 檢查連線。`

- [ ] **Step 3: Relocate route actions**

  Delete the global `.page-head-actions` and `.settings-band` rendering. In the
  `models` anchor:

  - render visible `Button` with `Save` icon for `儲存路由`;
  - render `匯入與匯出` as a closed `<details>` advanced disclosure;
  - inside it, render `Upload`/`Download` Buttons for the same existing handlers;
  - keep blocked-save explanation adjacent to the save action;
  - preserve exact disabled conditions and request functions.

  Do not add autosave or change import/export destinations.

- [ ] **Step 4: Route in-page cross-links through the exact reveal function**

  `ModelRoutingSection.onOpenProviders` reveals `providers`; Provider
  `onUseModel` updates the same draft and then reveals `models`. No category state
  remains. Shell requests reuse the same sequence discipline and exact reveal
  path.

- [ ] **Step 5: Run GREEN and commit**

  Expected cumulative collection: `+28`; full frontend `600`.

  ```bash
  git add apps/arkscope-web/src/Settings.tsx \
    apps/arkscope-web/src/settings/ModelRoutingSection.tsx \
    apps/arkscope-web/src/settings/ProviderSection.tsx \
    apps/arkscope-web/src/SettingsModelRouting.test.ts
  git commit -m "feat: localize settings model actions"
  ```

---

## Task 5: Replace Settings Confirmations

**Files:**
- Modify: `apps/arkscope-web/src/settings/DataSourcesSection.tsx`
- Modify: `apps/arkscope-web/src/settings/ProviderSection.tsx`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/CredentialList.test.ts`

**Contract:** Replace both `window.confirm` calls with typed shared dialogs while
preserving mutation payloads and preventing cancel/Escape from mutating.

- [ ] **Step 1: Add/strengthen the provider-config dialog contracts**

  Strengthen the existing
  `confirms guarded IBKR client id edits` node so Save first opens a dialog and
  makes no request; confirming sends the existing payload exactly once. Add one
  new node:

  `cancels_a_guarded_provider_edit_without_mutation_and_restores_focus`

  Its cancel and Escape paths leave the draft intact, make zero PUT calls, close
  the dialog, and return focus to the Save trigger.

- [ ] **Step 2: Implement pending guarded edit state**

  Store `{provider, field, value, fieldMeta}` only after the user clicks Save and
  assign that button to a `useRef<HTMLElement | null>` return-focus owner. Pass
  the ref through `ConfirmDialog.returnFocusRef`. Render the dialog with the
  backend-provided `guard_reason` as the consequence and `套用變更` as the
  confirmation label. Only the dialog confirm calls the existing
  `putProviderConfig` path with `{[field]: true}`. Busy state disables both
  actions through the existing dialog contract.

- [ ] **Step 3: Add exactly two credential-delete nodes**

  Add:

  1. `opens_credential_delete_confirmation_and_cancel_restores_trigger_focus`
  2. `confirms_only_the_selected_credential_delete`

  Use two credential rows in the second test to prove exact identity. Before
  confirmation, `onDelete` has zero calls.

- [ ] **Step 4: Implement one credential delete dialog owner**

  `CredentialList` stores the selected editable credential and assigns the
  clicked button to one `useRef<HTMLElement | null>` passed as
  `ConfirmDialog.returnFocusRef`. Render one dialog outside the row loop. The
  title is `刪除 Credential？`; consequence names the display label and states
  that the saved login entry is removed. Confirmation calls the unchanged
  `onDelete(id)` once and closes. Do not show credential IDs or token details.

- [ ] **Step 5: Run GREEN and commit**

  Expected cumulative collection: `+31`; full frontend `603`.

  ```bash
  git add apps/arkscope-web/src/settings/DataSourcesSection.tsx \
    apps/arkscope-web/src/settings/ProviderSection.tsx \
    apps/arkscope-web/src/SettingsProviderConfig.test.ts \
    apps/arkscope-web/src/CredentialList.test.ts
  git commit -m "refactor: use settings confirmation dialogs"
  ```

---

## Task 6: CSS, Class Coverage, and Static Ratchets

**Files:**
- Create: `apps/arkscope-web/src/SettingsCss.test.ts`
- Modify: `apps/arkscope-web/src/settings/settings.css`
- Modify: `apps/arkscope-web/src/styles.css`
- Modify: `apps/arkscope-web/src/ui/classCoverage.test.ts`

**Contract:** Finish the visual ownership transition without rewriting
specialized panels. The Settings shell is compact, unframed, token-driven, and
free of stale category/card selectors.

- [ ] **Step 1: Add exactly three RED static/CSS nodes**

  Add:

  1. `uses_data_driven_shell_overlay_without_numeric_breakpoint_literals`
  2. `defines_every_literal_class_in_extracted_settings_modules`
  3. `removes_legacy_directory_runtime_band_and_confirm_owners`

  The third node scans production Settings sources and relevant CSS for:
  `.settings-nav-card`, `.settings-section-button`, `.settings-band`, and
  `window.confirm`. It also asserts `app_records` and `permissions` are absent
  from the registry.

- [ ] **Step 2: Remove only superseded page-shell CSS**

  Delete the old directory card/button/layout/runtime-band rules and their 760px
  directory overrides. Keep `.settings-grid`, `.settings-panel`,
  `.settings-section-head`, model/provider/data table classes, and component-local
  wrapping rules unless the new namespaced shell replaces them explicitly.

- [ ] **Step 3: Complete class and layout coverage**

  The strengthened class-coverage test must recursively inspect every
  production TSX under `src/settings/` plus `Settings.tsx`, and must resolve
  classes against `styles.css`, `ui/primitives.css`, and
  `settings/settings.css`. Ensure every new literal class is defined, long
  directory labels use normal wrapping, group bands do not have panel
  backgrounds/radii, and the content track has `min-width: 0`.

- [ ] **Step 4: Run GREEN and commit**

  Expected final collection: focused `135`, full frontend
  `63 files / 606 tests`.

  ```bash
  git add apps/arkscope-web/src/SettingsCss.test.ts \
    apps/arkscope-web/src/settings/settings.css \
    apps/arkscope-web/src/styles.css \
    apps/arkscope-web/src/ui/classCoverage.test.ts
  git commit -m "style: unify settings workspace layout"
  ```

---

## Task 7: Full Verification, Responsive Gate, and Review-Ready Stop

**Files:**
- Modify: this plan ledger
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Must not modify: product code unless a new RED reproduces a discovered defect

- [ ] **Step 1: Run exact focused and full frontend gates**

  Run the updated focused command including the three new test files. Expected:
  `18 files / 135 tests`. Then run:

  ```bash
  npm test --workspace apps/arkscope-web -- --run
  npm run typecheck --workspace apps/arkscope-web
  npm run build --workspace apps/arkscope-web
  ```

  Expected: `63 files / 606 tests`; only the existing chunk warning is allowed.

- [ ] **Step 2: Run constructive backend and scope gates**

  ```bash
  git diff --exit-code IMPLEMENTATION_BASE -- src data_sources tests
  git diff --exit-code IMPLEMENTATION_BASE -- apps/arkscope-web/src/api.ts
  git diff --exit-code IMPLEMENTATION_BASE -- apps/arkscope-web/src/InvestorProfilePanel.tsx apps/arkscope-web/src/Dashboard.tsx
  git diff --exit-code IMPLEMENTATION_BASE -- extensions
  ```

  Any output is a stop condition.

- [ ] **Step 3: Run mechanical ratchets**

  Prove:

  - zero `window.confirm` in `Settings.tsx` and `src/settings/**`;
  - zero legacy `.settings-nav-card`, `.settings-section-button`, and
    `.settings-band` selectors/usages;
  - zero 959/960/961 literals in production Settings TS/TSX/CSS;
  - zero `app_records`/`permissions` in the runtime registry;
  - exactly one collapse storage key owner;
  - exactly one static Settings registry owner;
  - no `aria-live` added to polling Settings content;
  - no new public-route raw exception or API/backend file;
  - no nested group-card selector/background;
  - all literal classes resolve.

- [ ] **Step 4: Run a disposable real-browser visual/interaction gate**

  Start an isolated Vite instance against one isolated sidecar/profile copy;
  never reuse or mutate the user's running desktop profile. Check:

  - `1440x900`, `1024x768`, `961x768`, `960x768`, `959x768`, and `390x844`;
  - first visit shows three expanded groups and all nine anchors;
  - 961px has one persistent directory; 960/959/390 have one trigger and one
    transient Drawer, with no duplicate focusable directory;
  - search `IBKR client id`, `OpenAI`, `風險意願`, and `FRED` reaches the reviewed
    sections; no credential/model/error dynamic value enters results;
  - collapsed state survives reload; selecting a result or System's existing
    `資料來源設定` target expands/focuses the exact anchor;
  - Escape/cancel restores focus for directory and both confirmation dialogs;
  - Data Sources long tables retain one horizontal scroll owner and do not
    overlap text/progress/status cells;
  - no group/card nesting, horizontal page overflow, clipped text, blank rail,
    disabled historical item, model-only page title, or global runtime band;
  - Settings page scroll remains functional at every viewport, explicitly
    guarding the Slice 2 scroll regression.

  Store screenshots only under `/tmp`, record paths/dimensions, and stop all
  disposable processes. Do not save Settings mutations during this gate.

- [ ] **Step 5: Self-review exact accounting and diff**

  Use Vitest's collected node list to prove raw `+34/-0`; reconcile any drift
  before review. Inspect every changed file for secret/dynamic-search leakage,
  duplicated authorities, stale imports, and unrelated formatting churn.

- [ ] **Step 6: Update docs and stop review-ready**

  Record commit hashes, RED/GREEN evidence, exact counts, static gates, browser
  evidence, and process cleanup in this plan. Update the priority map to
  `IMPLEMENTED FOR REVIEW`, commit docs, and stop. Do not merge, mark Slice 4
  LIVE, begin Slice 5, or sync the external Design Kit before independent
  implementation review returns GREEN.

---

## Independent Reviewer Focus

1. Pure-move commit contains no behavior/CSS/test collection drift.
2. Registry is the only group/anchor/search authority; shell target type derives
   from it rather than copying the union.
3. Provider login/discovery and model routing remain distinct authorities and
   visible sections.
4. All nine shipped sections coexist in one page; search never hides page
   content or indexes runtime values.
5. Collapse is fail-closed, remembered, and unmounts hidden polling content.
6. Exact target/search/directory paths expand before scroll/focus and repeated
   request sequences work without pinning local selection.
7. Wide and narrow directory variants are mutually exclusive and use the one
   shell breakpoint authority.
8. Catalog failure cannot erase Investor Profile or data settings.
9. Route actions moved locally without payload/disable/authority changes; the
   redundant global summary is gone.
10. Both prior Settings `window.confirm` paths use `ConfirmDialog`, with exact
    mutation identity and cancel/focus behavior.
11. Investor Profile, API, backend, scheduler, provider, extension, Developer
    Mode, and System behavior are byte-identical.
12. Visual gate proves compact hierarchy, no nested cards, no overlap/overflow,
    and working page scroll at all six widths.

---

## Stop Conditions

Stop and return to design/review if implementation requires any of the following:

1. changing an API/DTO/backend/database/provider/scheduler contract;
2. changing Investor Profile semantics or starting Slice 5 work;
3. duplicating or moving Developer Mode out of System / Health;
4. adding a fourth empty group, disabled historical item, nested settings route,
   or planned placeholder;
5. indexing DOM/runtime/credential/model/error values for search;
6. adding autosave, lazy hidden fallback behavior, or a second model catalog;
7. keeping hidden Data Sources polling alive after its group is collapsed;
8. adding a numeric Settings shell breakpoint or a second matchMedia owner;
9. making a group/card wrapper that nests existing cards inside another card;
10. deleting App Records backend compatibility or changing an unrelated legacy
    surface as part of visual cleanup;
11. removing/renaming an existing test node or changing the reviewed `+34/-0`
    ledger without explicit re-review;
12. touching production profile/credential/schedule/model-route state during
    offline or visual verification.

---

## Post-Review Merge Closeout

Only after independent implementation GREEN and explicit user approval:

1. stop disposable services and prove their ports/PIDs are gone;
2. fast-forward merge the reviewed branch into `master`;
3. rerun focused `135`, full `63/606`, typecheck, build, static ratchets, and
   backend byte-identity from the merged tree;
4. restart the normal desktop app from merged `master`;
5. user-check Settings at normal desktop width: directory, search, collapse,
   Models save placement, Providers, Investor Profile, and Data Sources table;
6. mark this plan `MERGED / LIVE`, update P2.8 Slice 4 and decision log, and
   record any external Design Kit sync separately;
7. remove the implementation worktree/branch only after merged verification;
8. next sequencing returns to the priority map. Slice 5 Investor Profile UX and
   the already-designed Alpha Picks/universe follow-ups remain independent work
   units; do not begin either implicitly.
