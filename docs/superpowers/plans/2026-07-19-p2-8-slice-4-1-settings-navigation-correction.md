# P2.8 Slice 4.1 Settings Navigation Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task by task. Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** FAST-FORWARD MERGED — DESKTOP USER CHECK PENDING
>
> Independent plan review returned GREEN on 2026-07-20 with no must-fix.
> Independent implementation review returned GREEN on product tip `4931050`.
> `master` fast-forwarded through evidence tip `bfdc32c`; merged-tree gates are
> green, but LIVE status still requires the normal desktop user check.

**Goal:** Correct the rejected Slice 4 Settings composition by replacing the
all-groups long page with three accessible workflow tabs and one mounted group,
while preserving exact navigation anchors, protecting dirty/in-flight work,
and making `總經資料` the sole detailed FRED snapshot owner.

**Architecture:** `SettingsView` remains the controller for active workflow,
exact navigation intent, model-route state, and group-change guards. A new
shared `ui/Tabs` primitive owns tab semantics and mounts only its selected
panel. Section owners report only `{ dirty, busy, reason }` booleans/copy to a
small navigation-guard seam; they never expose draft values. Dirty transitions
require an explicit `ConfirmDialog`, while busy transitions are vetoed with a
visible `InlineAlert`. Investor Profile remains byte-identical: its existing
`aria-busy` is the hard-block signal and a Settings-owned capture boundary
conservatively records user edits until the user explicitly discards them or
the panel remounts. `DataSourcesSection` drops `/macro/snapshot`; the expanded
`MacroStorageSection` independently loads `/macro/status` and
`/macro/snapshot` and preserves either successful leg.

**Tech Stack:** React 18, TypeScript, Vitest/jsdom, existing ArkScope UI
primitives and `lucide-react`, Vite/Electron, CSS driven by
`useShellOverlay()`, and Git worktree/byte-identity gates. Backend Python, API
DTOs/runtime client code, databases, schedulers, Holdings, Investor Profile,
Dashboard/System, and browser extensions are immutable in this slice.

---

## Implementation Ledger

> Populated from the isolated implementation worktree. Product behavior remains
> unmerged until independent implementation review and explicit user approval.

| Item | Evidence |
|---|---|
| plan-review clearance commit | `1a68c3a51590701eceaea2b86c9b370073671c82` |
| implementation worktree/base | `codex/p2-8-slice-4-1-settings` at `/tmp/arkscope-p2-8-slice-4-1`, opened from clearance `1a68c3a`; product-behavior baseline `f797673`; linked-worktree checkout used the established `--no-checkout` flow and copied only the existing git-crypt key into linked Git metadata |
| RED/GREEN commits | Task 1 `f45dddc` (missing shared Tabs -> six primitive contracts); Task 2 `0e8bbb1` (collapse metadata -> active-group contracts); Task 3 `b5328d7` (value-free dirty/busy owner reports); Task 4 `51c6067` (guarded one-panel workflow tabs, commit-keyed focus, lifecycle preservation); Task 5 `1bc388f` (independent FRED status/snapshot legs and single detailed owner); visual review hardening `4931050` (RED CSS contract, then no-wrap narrow-screen actions) |
| raw node accounting | sorted focused-node comm from virgin `f797673` archive to product head: exactly `+42/-12`; all 12 removals match the reviewed list and no other node disappeared; net `+30`, `134 -> 164` |
| focused/full frontend gates | final fresh run: focused `18 files / 164 tests` and full `65 files / 636 tests`, all passing; `npm run typecheck` clean; production build succeeds with only the pre-existing chunk-size warning |
| immutable/static gates | all six `git diff --exit-code f797673` gates are empty (`src data_sources tests`, `api.ts`, `Holdings.tsx`, `InvestorProfilePanel.tsx`, `Dashboard.tsx`, `extensions`); retired collapse key appears only as cleanup constant and is never read; active-group key has one owner; Macro snapshot has one production consumer; old Calendar labels, detailed Data Sources snapshot owner, Settings `window.confirm`, `aria-live`, local media queries, and 959/960/961 literals are absent; class coverage passes |
| six-viewport interaction gate | PASS at `1440x900`, `1024x768`, `961x768`, `960x768`, `959x768`, and `390x844`; screenshots retained under `/tmp/arkscope-p2-8-s4-1-visual/shots/`; verified one mounted panel, rail/overlay exclusivity, tabs keyboard/focus, exact navigation precedence, stale-focus clearing, dirty confirm/busy veto, preserved parent state, Data Sources effect cleanup, five Macro truth states, no overlap or page overflow, and no browser exceptions; polling evidence `2 -> 2` while unmounted and `2 -> 4` after remount |
| process cleanup | profile and Macro backup SHA-256 values were byte-identical before/after the browser gate; isolated sidecar/Vite/Chrome stopped and ports `8426/8436/9226` refuse connections; temporary SQLite copies and Chrome profile deleted; only screenshots retained |
| independent implementation review | GREEN on product tip `4931050`: reviewer independently reproduced `65/636`, exact `+42/-12`, all static and six immutable byte gates, code-level guard/Tabs/FRED contracts, and a separate 41-check responsive interaction matrix |
| merge and merged-tree verification | `master` fast-forwarded `1a68c3a -> bfdc32c`; focused `18/164`, full `65/636`, typecheck, and build pass on the merged tree; only the existing chunk-size warning remains; desktop user check and LIVE closeout pending |

---

## Design Authority and Locked Decisions

1. The primary authority is
   `docs/superpowers/specs/2026-07-19-p2-8-slice-4-1-settings-navigation-correction-design.md`,
   status `WRITTEN SPEC REVIEW APPROVED` at `726744b`.
2. The canonical parent remains
   `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`.
   The addendum supersedes only the rejected Slice 4 Settings IA.
3. `docs/design/ARKSCOPE_TERMINOLOGY.md` is the only terminology authority.
   This plan does not create a second glossary or runtime locale layer.
4. Settings has exactly three workflow groups in this order:

   | Group ID | Label | Anchors, in order |
   |---|---|---|
   | `ai_models` | `AI 與模型` | `providers`, `models`, `fixed_task_runtime`, `research_runtime` |
   | `personalization` | `個人化` | `investor_profile` |
   | `data_sync` | `資料與同步` | `data_sources`, `data_storage`, `news_storage`, `macro_storage` |

5. Exactly one group panel is mounted. CSS hiding, `display:none`, and an
   always-mounted keep-alive substitute are forbidden.
6. The shared `Tabs` primitive matches shipped Holdings behavior: horizontal
   automatic activation, ArrowLeft/ArrowRight wrap, Home/End, roving
   `tabIndex`, linked tab/panel IDs, and one mounted panel. V1 has no activation
   mode prop. A tab item may expose its button ref so an owning overlay can
   restore focus without a DOM query. Holdings remains byte-identical and
   migrates in its next owning slice.
7. Settings requires one narrow generic extension to the controlled Tabs
   callback: `onValueChange` may return `false` to veto a requested selection.
   On veto, the primitive keeps the current tab selected and restores focus to
   it. This is not a manual-activation mode; it exists only so a consumer can
   honor a reviewed dirty/busy guard without violating automatic activation.
8. Empty directory search lists the active group's anchors. Non-empty
   `搜尋所有設定` searches all registry groups. `searchSettings("")` itself keeps
   returning all anchors in registry order.
9. Search and `NavigationTarget` switch group first and focus the exact anchor
   after React has committed that panel. Manual tab selection clears pending
   exact focus and targets the new group's first anchor.
10. `arkscope.settings.activeGroup.v1` is the sole active-group preference.
    Missing/malformed/unknown/unavailable storage fails closed to `ai_models`.
    Production never reads or interprets
    `arkscope.settings.collapsedGroups.v1`; a successful new-key write may
    attempt best-effort removal only.
11. A group-change request is one typed intent:

    ```ts
    type SettingsNavigationIntent = {
      group: SettingsGroupId;
      anchor: SettingsAnchorId;
      kind: "manual_group" | "exact_anchor";
    };
    ```

    `manual_group` clears pending focus. `exact_anchor` records pending focus.
    Preference persistence happens only after the intent is accepted.
12. Dirty work is not silently discarded. A cross-group request opens one
    `ConfirmDialog`; cancel keeps the active group, confirm explicitly discards
    local drafts and applies the original typed intent. The dialog and any
    visible reason must not include credential, token, profile, or draft values.
13. Busy authorization/mutations are not discarded and are not confirmable.
    The selection is vetoed, the selected tab keeps focus, and a stable
    `InlineAlert state="blocked"` explains what must finish or be cancelled.
14. Model route drafts, discovery, and task-test results already live in
    `SettingsView`; they survive group unmount and require no discard warning.
    The shared `saving` mutation is busy and blocks leaving `ai_models`.
15. Provider local drafts are confirmable dirty state. ChatGPT OAuth (including
    its manual phase), credential mutation, and credential probe are busy hard
    blocks. Provider discovery remains parent-owned and survives unmount.
16. Fixed-task and Research runtime drafts are confirmable dirty state. Their
    saves/resets use parent-owned `saving`, which is a busy hard block.
17. Data Sources interval/config drafts and pending guarded edits are
    confirmable dirty state. Its mutations are busy hard blocks. Passive
    schedule polling and read refreshes are safe to unmount and must stop.
18. Investor Profile remains byte-identical. `SettingsView` observes the
    existing `.investor-profile-panel[aria-busy="true"]` only when a group
    change is requested. User input/change events inside its anchor set a
    conservative potential-dirty flag. Because Slice 5 owns a precise form
    controller, 4.1 intentionally permits a false-positive discard prompt
    after an already-saved edit; it permits no false-negative silent discard.
    Confirmed leave clears the flag; remount starts clean from server truth.
19. `DataSourcesSection` retains compact FRED config/health only from its
    existing provider-config and provider-health payloads. It makes no
    `/macro/status` or `/macro/snapshot` request.
20. `MacroStorageSection` is the only Settings consumer of
    `getMacroSnapshot()`. It loads status and snapshot as independent legs,
    never clears successful truth because the other leg failed, never emits raw
    exceptions, and does not claim a Calendar product or a never-run state.
21. No implementation step may alter backend/API/DTO behavior, provider/model
    eligibility, timeout ranges, schedule cadence, Investor Profile semantics,
    the shell breakpoint, or extension code.

---

## Grounded Baseline and Owner Inventory

- Plan authoring base: `726744b` (`docs: clear Settings correction spec review`).
- Product behavior base: merged Slice 4 at `f797673`. The commits between
  `f797673` and `726744b` are documentation-only.
- Freshly reproduced frontend baseline on `726744b`:

  ```text
  Test Files  63 passed (63)
  Tests       606 passed (606)
  ```

- Current production sizes:
  - `Settings.tsx`: 696 lines;
  - `DataSourcesSection.tsx`: 946 lines;
  - `MacroStorageSection.tsx`: 85 lines;
  - `ProviderSection.tsx`: 1,013 lines;
  - `InvestorProfilePanel.tsx`: 486 lines and immutable.
- Current `SettingsView` still owns `collapsedGroups`, renders all expanded
  groups, and uses a one-frame reveal tied to collapse state.
- `DataSourcesSection.load()` currently has four legs and is the only current
  Settings call site for `getMacroSnapshot()`; it also renders the detailed
  `FRED 資料快照` table.
- `MacroStorageSection` currently calls only `getMacroStatus()` and visibly
  promises `Macro / Calendar`.
- `ConfirmDialog` delegates to `useOverlayFocus`, whose current entry captures
  `returnFocusRef.current` only when the overlay opens. A dirty switch has two
  legitimate close targets (cancel -> current tab, confirm -> destination tab),
  so Task 4 must retain the explicit ref object and resolve its latest connected
  target at removal rather than query the DOM or race focus with a timeout.
- The current relevant focused baseline is exactly `16 files / 134 tests`:

  ```bash
  npx vitest list \
    src/SettingsCss.test.ts \
    src/ui/classCoverage.test.ts \
    src/settings/settingsRegistry.test.ts \
    src/SettingsStabilizationCss.test.ts \
    src/SettingsWorkspace.test.tsx \
    src/SettingsPostPgExitStorage.test.ts \
    src/SettingsNewsStorage.test.ts \
    src/SettingsModelRouting.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/FixedTaskRuntimeSection.test.tsx \
    src/ProviderSection.test.ts \
    src/CredentialList.test.ts \
    src/ResearchRuntimeSection.test.ts \
    src/ui/primitives.test.tsx \
    src/ui/overlays.test.tsx \
    src/InvestorProfilePanel.test.tsx
  ```

### Owner-by-owner lifecycle decision

| Surface state | Current owner | 4.1 decision | Switch policy |
|---|---|---|---|
| model route drafts | `SettingsView` | preserve in parent | switch allowed |
| discovery/task-test state | `SettingsView` | preserve in parent | switch allowed |
| model/runtime save/reset | `SettingsView.saving` | unchanged | busy block |
| Provider setup/API-key/OAuth metadata drafts | `ProviderSection` | report boolean dirty state | confirm discard |
| ChatGPT OAuth/manual completion | `ProviderSection` | report existing OAuth/busy lifecycle | hard block until complete/cancel |
| credential mutation/probe | `ProviderSection` / `CredentialList` | add narrow busy report | hard block |
| fixed-task runtime draft | `FixedTaskRuntimeSection` | report comparison to props | confirm discard |
| Research runtime draft | `ResearchRuntimeSection` | report comparison to props | confirm discard |
| Investor Profile form/calibration text | immutable `InvestorProfilePanel` | Settings capture boundary | confirm discard |
| Investor Profile mutation | existing `aria-busy` | Settings reads semantic DOM signal at request time | hard block |
| Data Sources interval/config drafts | `DataSourcesSection` | report boolean dirty state | confirm discard |
| Data Sources mutations | `DataSourcesSection.busy` | report boolean busy state | hard block |
| Data Sources polling/read refresh | `DataSourcesSection` effects | no preservation | unmount and stop safely |
| storage/news/macro read state | each read-only section | no preservation | unmount and reload |

The guard payload is deliberately value-free:

```ts
export interface SettingsNavigationGuardState {
  dirty: boolean;
  busy: boolean;
  dirtyReason: string | null;
  busyReason: string | null;
}

export type SettingsNavigationGuardChange = (
  state: SettingsNavigationGuardState,
) => void;
```

No callback receives a secret, profile value, route body, provider error, or
raw exception.

---

## Exact Test Accounting

Raw node accounting is locked at `+42/-12`, net `+30`:

| Test owner | Added | Removed | Net |
|---|---:|---:|---:|
| `ui/Tabs.test.tsx` (new) | 6 | 0 | +6 |
| `settings/settingsRegistry.test.ts` | 5 | 3 | +2 |
| `SettingsWorkspace.test.tsx` | 12 | 6 | +6 |
| `ProviderSection.test.ts` | 2 | 0 | +2 |
| `CredentialList.test.ts` | 1 | 0 | +1 |
| `FixedTaskRuntimeSection.test.tsx` | 1 | 0 | +1 |
| `ResearchRuntimeSection.test.ts` | 1 | 0 | +1 |
| `SettingsProviderConfig.test.ts` | 3 | 1 | +2 |
| `SettingsPostPgExitStorage.test.ts` | 2 | 2 | 0 |
| `SettingsModelRouting.test.ts` | 2 | 0 | +2 |
| `settings/MacroStorageSection.test.tsx` (new) | 7 | 0 | +7 |
| `ui/overlays.test.tsx` (strengthened in place) | 0 | 0 | 0 |
| **Total** | **42** | **12** | **+30** |

Targets:

- focused: `16 files / 134 tests -> 18 files / 164 tests`;
- full frontend: `63 files / 606 tests -> 65 files / 636 tests`;
- no removed node outside the 12 explicitly listed below;
- no backend collection change.

### Explicit removed/renamed nodes

`settings/settingsRegistry.test.ts` removes these three collapse contracts:

1. `defaults_every_group_expanded_when_storage_is_absent`
2. `round_trips_only_known_collapsed_group_ids`
3. `fails_closed_to_expanded_for_malformed_or_unknown_storage`

`SettingsWorkspace.test.tsx` replaces these six superseded IA nodes:

1. `renders_generic_page_header_and_all_shipped_groups_and_anchors`
2. `collapses_persists_and_unmounts_a_group_body`
3. `restores_remembered_collapse_while_first_use_stays_expanded`
4. `searches_chinese_and_english_aliases_without_filtering_page_content`
5. `selecting_a_result_expands_scrolls_and_focuses_the_exact_anchor`
6. `exposes_compact_accessible_group_toggles_with_aria_expanded`

`SettingsProviderConfig.test.ts` replaces:

1. `renders the FRED local snapshot panel`

`SettingsPostPgExitStorage.test.ts` replaces:

1. `shows Macro / Calendar as normal macro and calendar status`
2. `renders_market_empty_and_macro_failed_states_as_user_outcomes`

No other test ID may disappear or change name without stopping to reconcile
this ledger before implementation continues.

---

## Task 0: Establish the Reviewed Worktree and RED Ledger

**Files:**
- Create only the isolated worktree; no product edits.
- Record evidence in this plan's implementation ledger section after review
  clearance.

- [x] **Step 1: Record the plan-review clearance base**

  After independent review, flip the status to `CLEARED FOR IMPLEMENTATION`,
  commit that docs-only change, and record its hash:

  ```bash
  git rev-parse HEAD
  git diff --exit-code 726744b -- src data_sources tests apps/arkscope-web/src
  ```

  The first hash is `PLAN_REVIEW_CLEARANCE_COMMIT`. The second command must be
  empty because plan review is docs-only.

- [x] **Step 2: Create the isolated worktree from clearance**

  ```bash
  git worktree add ../ArkScope-p2-8-slice-4-1 -b codex/p2-8-slice-4-1-settings PLAN_REVIEW_CLEARANCE_COMMIT
  git status --short --branch
  ```

  Stop if the worktree is not clean. Do not use the main checkout for
  implementation.

- [x] **Step 3: Reproduce all baselines before RED**

  From `apps/arkscope-web`:

  ```bash
  npm test -- --run
  npx vitest list \
    src/SettingsCss.test.ts \
    src/ui/classCoverage.test.ts \
    src/settings/settingsRegistry.test.ts \
    src/SettingsStabilizationCss.test.ts \
    src/SettingsWorkspace.test.tsx \
    src/SettingsPostPgExitStorage.test.ts \
    src/SettingsNewsStorage.test.ts \
    src/SettingsModelRouting.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/FixedTaskRuntimeSection.test.tsx \
    src/ProviderSection.test.ts \
    src/CredentialList.test.ts \
    src/ResearchRuntimeSection.test.ts \
    src/ui/primitives.test.tsx \
    src/ui/overlays.test.tsx \
    src/InvestorProfilePanel.test.tsx
  ```

  Require `63/606` and focused `134`. Record the exact node list as the raw
  accounting base.

- [x] **Step 4: Capture immutable-path digests**

  Record `git hash-object` for:

  ```text
  apps/arkscope-web/src/api.ts
  apps/arkscope-web/src/Holdings.tsx
  apps/arkscope-web/src/InvestorProfilePanel.tsx
  apps/arkscope-web/src/Dashboard.tsx
  ```

  Also record name-only trees for `src/`, `data_sources/`, `tests/`, and
  `extensions/`. These become final byte gates.

- [x] **Step 5: Commit no code in Task 0**

  The first product commit belongs to Task 1 after its RED tests fail for the
  intended missing primitive.

---

## Task 1: Add the Shared Automatic-Activation Tabs Primitive

**Files:**
- Create: `apps/arkscope-web/src/ui/Tabs.tsx`
- Create: `apps/arkscope-web/src/ui/Tabs.test.tsx`
- Modify: `apps/arkscope-web/src/ui/index.ts`
- Modify: `apps/arkscope-web/src/ui/primitives.css`

- [x] **Step 1: Write six RED tests**

  Add exactly these nodes:

  1. `renders_accessible_linkage_and_only_the_selected_panel`
  2. `click_activates_and_roves_tabindex`
  3. `arrow_right_activates_next_and_wraps`
  4. `arrow_left_activates_previous_and_wraps`
  5. `home_and_end_activate_boundaries`
  6. `vetoed_change_preserves_selected_tab_and_focus`

  Test a controlled harness. Assert one `tablist`, three `tab`s, one
  `tabpanel`, reciprocal `aria-controls`/`aria-labelledby`, one
  `aria-selected=true`, one `tabIndex=0`, and no inactive panel DOM. The veto
  case must pass external `tabRef`s, prove each always-mounted tab button is
  available to the owner, return `false` from the callback, and prove selection
  and focus stay on the current tab.

- [x] **Step 2: Run RED**

  ```bash
  npm test -- --run src/ui/Tabs.test.tsx
  ```

  Expected failure: `./Tabs` does not exist. Any unrelated failure is a stop.

- [x] **Step 3: Implement the narrow V1 interface**

  Use this reviewed shape (names may differ only mechanically):

  ```ts
  export interface TabItem<Value extends string> {
    value: Value;
    label: ReactNode;
    panel: ReactNode;
    tabRef?: Ref<HTMLButtonElement>;
  }

  export interface TabsProps<Value extends string> {
    ariaLabel: string;
    value: Value;
    items: readonly TabItem<Value>[];
    onValueChange: (value: Value) => boolean | void;
    className?: string;
  }
  ```

  Use `useId()` for the ID namespace and a ref map for focus. Merge each optional
  external `tabRef` with the internal ref; do not replace the internal keyboard
  owner or make the caller query the DOM. Keyboard handling must call the same
  request function as click handling. A return value of `false` means veto;
  refocus the currently selected tab and do not mount a new panel. Any other
  return value accepts the request and focuses the activated tab. Do not add a
  mode prop, disabled-item model, URL routing, or persistence.

- [x] **Step 4: Add primitive CSS**

  Add `.ui-tabs`, `.ui-tab-list`, `.ui-tab`, and `.ui-tab-panel` rules in
  `primitives.css`. Use existing tokens, radius cap, no negative letter spacing,
  no viewport-scaled font, and stable minimum heights. The tab row may wrap only
  when needed; it must not create page-level horizontal overflow.

- [x] **Step 5: Export and run GREEN**

  ```bash
  npm test -- --run src/ui/Tabs.test.tsx src/ui/primitives.test.tsx src/ui/classCoverage.test.ts
  npm run typecheck
  ```

  Expected checkpoint: new Tabs `6/6`, existing primitive/class nodes unchanged.

- [x] **Step 6: Commit**

  ```bash
  git add apps/arkscope-web/src/ui/Tabs.tsx apps/arkscope-web/src/ui/Tabs.test.tsx apps/arkscope-web/src/ui/index.ts apps/arkscope-web/src/ui/primitives.css
  git commit -m "feat: add accessible tabs primitive"
  ```

---

## Task 2: Replace Collapse Metadata with Active-Group Navigation Metadata

**Files:**
- Modify: `apps/arkscope-web/src/settings/settingsRegistry.ts`
- Modify: `apps/arkscope-web/src/settings/settingsPreferences.ts`
- Modify: `apps/arkscope-web/src/settings/settingsRegistry.test.ts`

- [x] **Step 1: Replace three collapse nodes with five active-group nodes**

  Remove the three IDs listed in the accounting section and add exactly:

  1. `defaults_active_group_to_ai_models_without_storage`
  2. `round_trips_only_known_active_group_ids`
  3. `fails_closed_to_ai_models_for_malformed_unknown_or_unavailable_storage`
  4. `never_reads_or_interprets_the_retired_collapse_key`
  5. `best_effort_cleanup_failure_never_blocks_active_group_write`

  The old-key test must use a spy storage object that fails if
  `readActiveSettingsGroup()` calls
  `getItem("arkscope.settings.collapsedGroups.v1")`. It tests the new API, not
  the temporary pre-Task-4 compatibility export. The cleanup test
  must let `setItem` succeed, make `removeItem` throw, and prove the new value
  remains accepted.

- [x] **Step 2: Run RED**

  ```bash
  npm test -- --run src/settings/settingsRegistry.test.ts
  ```

  Expected failures: active-group preference and group lookup APIs do not
  exist. Keep visible registry metadata and the current directory API unchanged
  in this task so the pre-tabs consumer remains green between commits.

- [x] **Step 3: Add preference and registry helpers without breaking the current consumer**

  Add:

  ```ts
  export const SETTINGS_ACTIVE_GROUP_STORAGE_KEY = "arkscope.settings.activeGroup.v1";
  export const RETIRED_SETTINGS_COLLAPSE_STORAGE_KEY = "arkscope.settings.collapsedGroups.v1";
  export function readActiveSettingsGroup(...): SettingsGroupId;
  export function writeActiveSettingsGroup(...): void;
  ```

  The retired constant is write-cleanup metadata only. Production may pass it
  to `removeItem` after a successful new-key write; it may never pass it to
  `getItem` or parse its value through the new API. Keep the current
  `readCollapsedSettingsGroups` / `writeCollapsedSettingsGroups` exports
  mechanically unchanged only until Task 4, because the pre-tabs
  `SettingsView` still imports them and every intermediate commit must compile.
  Do not add a new caller or behavior to those compatibility exports; Task 4
  removes both exports and their imports in the same commit. Add `settingsGroup(id)` and
  `firstSettingsAnchor(id)` pure helpers so `SettingsView` and the directory do
  not duplicate searches through `SETTINGS_GROUPS`. Active-group validation
  must derive from `SETTINGS_GROUPS`; do not retain or introduce a second
  hand-written group-ID set in `settingsPreferences.ts`.

- [x] **Step 4: Run GREEN**

  ```bash
  npm test -- --run src/settings/settingsRegistry.test.ts
  npm test -- --run
  npm run typecheck
  ```

  Expected checkpoint: `12 registry tests` (`+5/-3`) and the full package is
  `64 files / 614 tests` at this cumulative point (Task 1 added one file/six
  nodes; Task 2 is net +2).

- [x] **Step 5: Commit**

  ```bash
  git add apps/arkscope-web/src/settings/settingsRegistry.ts apps/arkscope-web/src/settings/settingsPreferences.ts apps/arkscope-web/src/settings/settingsRegistry.test.ts
  git commit -m "refactor: define active Settings workflow state"
  ```

---

## Task 3: Add Value-Free Navigation Guard Reports at the Local Owners

**Files:**
- Create: `apps/arkscope-web/src/settings/settingsNavigationGuard.ts`
- Modify: `apps/arkscope-web/src/settings/ProviderSection.tsx`
- Modify: `apps/arkscope-web/src/settings/RuntimeLimitSections.tsx`
- Modify: `apps/arkscope-web/src/settings/DataSourcesSection.tsx`
- Modify: `apps/arkscope-web/src/ProviderSection.test.ts`
- Modify: `apps/arkscope-web/src/CredentialList.test.ts`
- Modify: `apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx`
- Modify: `apps/arkscope-web/src/ResearchRuntimeSection.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`

- [x] **Step 1: Write seven RED owner tests**

  Add exactly:

  `ProviderSection.test.ts`

  1. `reports_credential_and_oauth_form_drafts_without_exposing_secret_values`
  2. `reports_oauth_and_credential_mutations_as_navigation_blocking_until_settled`

  `CredentialList.test.ts`

  3. `reports_probe_as_navigation_blocking_until_settled`

  `FixedTaskRuntimeSection.test.tsx`

  4. `reports_runtime_draft_dirty_and_clears_when_settings_catch_up`

  `ResearchRuntimeSection.test.ts`

  5. `reports_runtime_draft_dirty_and_clears_when_settings_catch_up`

  `SettingsProviderConfig.test.ts`

  6. `reports_unsaved_provider_and_schedule_drafts_to_navigation_owner`
  7. `reports_mutations_as_navigation_blocking_and_clears_after_completion`

  Use deferred Promises for mutation/probe/OAuth paths. Assert that reports
  contain only booleans and fixed reason copy; planted token/API-key/draft
  strings must never appear in callback arguments.

- [x] **Step 2: Run RED**

  ```bash
  npm test -- --run src/ProviderSection.test.ts src/CredentialList.test.ts src/FixedTaskRuntimeSection.test.tsx src/ResearchRuntimeSection.test.ts src/SettingsProviderConfig.test.ts
  ```

  Expected failures: navigation guard props/types do not exist.

- [x] **Step 3: Add the shared type, not a second state store**

  `settingsNavigationGuard.ts` contains only the interface, callback type, and
  an immutable clear constant. It must not import API types or persist data.

- [x] **Step 4: Report Provider state**

  Add optional `onNavigationGuardChange` to `ProviderSection`. Dirty is true
  when any user-entered setup/API-key/OAuth/manual/rename/metadata draft exists.
  Do not count provider selection, disclosure open state, messages, or search
  query as dirty.

  Add one local credential-mutation busy owner around `addKey`,
  `importClaudeToken`, `setActive`, `saveCredentialDetails`, and `removeKey`.
  Existing `pollBusy`, `manualBusy`, and non-null `oauth` make OAuth busy.
  `CredentialList` reports probe busy upward. Do not duplicate parent-owned
  discovery state in this report.

  An effect reports derived booleans and stable copy; cleanup reports clear.
  Never put draft values in the report or a DOM data attribute.

- [x] **Step 5: Report runtime state**

  Each runtime section compares its controlled draft strings against current
  settings props and reports dirty. `saving` remains parent-owned and is not
  duplicated as child busy. Existing settings-prop effects must still reset the
  draft after successful refresh.

- [x] **Step 6: Report Data Sources state and remove its detailed snapshot owner**

  Report dirty when any interval draft or provider-field draft is non-empty, or
  `pendingGuardedEdit` is non-null. Report busy when the existing `busy` string
  is non-empty. Passive polling, full read refresh, and server-owned schedule
  runs are not busy navigation blockers.

  In the same owner edit, remove `getMacroSnapshot`, `MacroSnapshot`, and
  `MacroSnapshotItem` imports/state; remove `formatMacroValue`; reduce `load()`
  to schedule/health/config legs; remove the detailed FRED panel. Keep
  `fredProviderDetail()` using only `signals.local_snapshot` and
  `auto_refresh_enabled`. If the auto-refresh signal is absent, render an
  unknown neutral phrase instead of claiming it is off.

- [x] **Step 7: Replace the one superseded Data Sources node**

  Rename `renders the FRED local snapshot panel` to
  `does_not_request_or_render_the_detailed_fred_snapshot`. Remove the snapshot
  fixture/import from this file. Assert:

  - compact FRED health remains;
  - `FRED 資料快照`, `Fed Funds`, and `fred-snapshot-scroll` are absent;
  - no snapshot request exists to count;
  - lifecycle full refresh still calls only schedule/health/config; and
  - the explicit scroll-owner list no longer includes `fred-snapshot-scroll`.

  Update existing polling assertions in place; do not rename them.

- [x] **Step 8: Run GREEN**

  ```bash
  npm test -- --run src/ProviderSection.test.ts src/CredentialList.test.ts src/FixedTaskRuntimeSection.test.tsx src/ResearchRuntimeSection.test.ts src/SettingsProviderConfig.test.ts
  npm run typecheck
  ```

  Expected raw checkpoint: `+8/-1`, with every pre-existing non-snapshot node
  retained. Cumulative full-package target: `64 files / 621 tests`.

- [x] **Step 9: Commit**

  ```bash
  git add apps/arkscope-web/src/settings/settingsNavigationGuard.ts apps/arkscope-web/src/settings/ProviderSection.tsx apps/arkscope-web/src/settings/RuntimeLimitSections.tsx apps/arkscope-web/src/settings/DataSourcesSection.tsx apps/arkscope-web/src/ProviderSection.test.ts apps/arkscope-web/src/CredentialList.test.ts apps/arkscope-web/src/FixedTaskRuntimeSection.test.tsx apps/arkscope-web/src/ResearchRuntimeSection.test.ts apps/arkscope-web/src/SettingsProviderConfig.test.ts
  git commit -m "fix: protect Settings section lifecycle state"
  ```

---

## Task 4: Replace the Long Page with Guarded Workflow Tabs

**Files:**
- Modify: `apps/arkscope-web/src/Settings.tsx`
- Modify: `apps/arkscope-web/src/settings/SettingsDirectory.tsx`
- Modify: `apps/arkscope-web/src/settings/settingsRegistry.ts`
- Modify: `apps/arkscope-web/src/settings/settingsPreferences.ts`
- Modify: `apps/arkscope-web/src/settings/settings.css`
- Modify: `apps/arkscope-web/src/settings/settingsRegistry.test.ts`
- Modify: `apps/arkscope-web/src/ui/useOverlayFocus.ts`
- Modify: `apps/arkscope-web/src/ui/overlays.test.tsx`
- Modify: `apps/arkscope-web/src/SettingsWorkspace.test.tsx`
- Modify: `apps/arkscope-web/src/SettingsModelRouting.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`
- Modify: `apps/arkscope-web/src/SettingsNewsStorage.test.ts`
- Modify: `apps/arkscope-web/src/SettingsCss.test.ts`

- [x] **Step 1: Replace six superseded workspace nodes**

  Add these six replacement IDs (each is one raw add paired to one explicit
  removal):

  1. `renders_page_header_tabs_and_only_default_group_anchors`
  2. `manual_tab_switch_unmounts_prior_group_and_targets_first_anchor`
  3. `restores_valid_active_group_and_ignores_retired_collapse_key`
  4. `searches_all_groups_while_empty_directory_stays_in_active_group`
  5. `selecting_cross_group_result_mounts_group_then_focuses_exact_anchor`
  6. `renders_three_workflow_tabs_with_one_selected_panel`

  Preserve and evolve the other seven existing workspace IDs in place.

- [x] **Step 2: Add six new workspace guard/navigation nodes**

  Add exactly:

  1. `manual_tab_change_clears_stale_pending_anchor`
  2. `navigation_target_overrides_persisted_active_group`
  3. `unmounts_data_sources_polling_when_leaving_data_sync`
  4. `dirty_section_requires_explicit_discard_before_group_change`
  5. `busy_section_blocks_group_change_with_visible_reason`
  6. `investor_profile_guard_blocks_busy_and_confirms_potential_draft_without_modifying_panel`

  Instrument section mocks with mount/unmount counters and guard callback
  buttons. The Investor Profile mock must expose the same root
  `aria-busy` shape and editable input as the immutable real component; do not
  change `InvestorProfilePanel.tsx`.

- [x] **Step 3: Add two parent-preservation nodes**

  In `SettingsModelRouting.test.ts`, add exactly:

  1. `preserves_model_route_drafts_across_workflow_tab_unmounts`
  2. `preserves_discovery_state_across_workflow_tab_unmounts`

  These prove the already-parent-owned states survive an AI -> data -> AI round
  trip without a discard dialog. Existing exact-target tests must migrate from
  the collapse key to the active-group key without renaming.

- [x] **Step 4: Strengthen registry and static RED expectations**

  In the existing registry terminology/search nodes, require:

  - `macro_storage.title === "總經資料"`;
  - FRED/snapshot/series/observation aliases route to `macro_storage`;
  - schedule/health/credential/SA extension/IBKR client ID remain under
    `data_sources`;
  - `data_sources` does not match a FRED snapshot-only query; and
  - no visible registry title contains `Calendar`, `行事曆`, or the rejected
    translated-original duplication.

  Strengthen the existing `SettingsCss.test.ts` nodes in place to require no
  production collapse-key read/collapse UI class, exactly one active-group key
  owner, shared Tabs classes, and complete literal Settings class coverage.
  The collapse assertions must fail against the long-page implementation.

  Strengthen the existing overlay return-focus node in place: while a
  `ConfirmDialog` is open, change the element held by its explicit
  `returnFocusRef`, close it, and require focus on the latest connected target.
  This must fail because the current overlay stack snapshots the element only
  when the dialog opens. Do not add or rename an overlay node.

- [x] **Step 5: Run RED**

  ```bash
  npm test -- --run src/SettingsWorkspace.test.tsx src/SettingsModelRouting.test.ts src/SettingsCss.test.ts src/settings/settingsRegistry.test.ts src/ui/overlays.test.tsx
  ```

  Expected failures: no tabs, all groups still mount, old preference is read,
  guards are not integrated, old Macro navigation metadata remains, and the
  old one-frame reveal remains.

- [x] **Step 6: Move data-panel harnesses onto the explicit active group**

  Before changing production composition, update the shared render helpers in
  `SettingsProviderConfig.test.ts`, `SettingsPostPgExitStorage.test.ts`, and
  `SettingsNewsStorage.test.ts` to seed
  `arkscope.settings.activeGroup.v1 = "data_sync"` (or activate that tab through
  the public UI when the test specifically covers tab behavior). Do not rename
  any News node or any Provider Config node beyond the separately accounted
  FRED snapshot replacement. This keeps each intermediate commit's full suite
  green under one-mounted-group semantics. Update only the existing directory
  assertion in `SettingsPostPgExitStorage.test.ts` to expect `總經資料`; retain
  its historical Macro-content node IDs until their explicit Task 5
  replacements.

- [x] **Step 7: Finalize directory filtering and navigation metadata**

  Add `activeGroup: SettingsGroupId` to `SettingsDirectory`. For a normalized
  empty query, use only `settingsGroup(activeGroup).sections`; for a non-empty
  query, use `searchSettings(query)`. Change the visible/accessible label and
  placeholder to `搜尋所有設定`. Keep deterministic Enter selection and neutral
  no-match text. Do not change `searchSettings("")`.

  Update the registry to satisfy the prewritten RED expectations:

  - `macro_storage.title === "總經資料"`;
  - FRED/snapshot/series/observation aliases route to `macro_storage`;
  - schedule/health/credential/SA extension/IBKR client ID remain under
    `data_sources`;
  - `data_sources` does not match a FRED snapshot-only query; and
  - no visible registry title contains `Calendar`, `行事曆`, or the rejected
    translated-original duplication.

  This is deliberately in the same commit as the tab consumer and updated
  data-panel harnesses. Do not expose the final directory prop or final visible
  metadata in Task 2 while the long-page consumer still owns the old API.

- [x] **Step 8: Implement one guarded intent reducer in `SettingsView`**

  Replace `collapsedGroups`/`toggleGroup` with `activeGroup` initialized from
  `readActiveSettingsGroup()`. Derive the initial current anchor with
  `firstSettingsAnchor(activeGroup)`.

  Once `SettingsView` no longer imports the collapse helpers, delete
  `readCollapsedSettingsGroups` and `writeCollapsedSettingsGroups` from
  `settingsPreferences.ts` in this same commit. Keep only the retired key
  constant needed for best-effort cleanup; final production must have no old-key
  read path.

  Keep one `PendingSettingsIntent` for dirty confirmation and one
  value-free blocked notice. Every manual tab, directory, Enter, search, and
  `NavigationTarget` path must use the same `requestSettingsNavigation(intent)`
  function.

  Decision order for a cross-group intent:

  1. derive current busy/dirty state;
  2. if busy, veto and show stable blocked copy;
  3. else if dirty, veto and open `ConfirmDialog` with the typed intent;
  4. else apply immediately.

  Same-group exact-anchor navigation never unmounts and does not invoke a
  discard prompt.

  On confirm, point `returnFocusRef` to the destination tab before closing so
  focus lands on the selected destination, clear the Investor potential-dirty
  flag when applicable, then apply the original intent. On cancel, keep the old
  selection and return focus to its selected tab.

  Keep refs for all three always-mounted tab buttons through `TabItem.tabRef`.
  Use one mutable dialog return ref: initialize it to the current tab when the
  dialog opens, set it to the current tab immediately before cancel, and set it
  to the destination tab immediately before confirm. Never locate a tab by
  label or CSS query.

- [x] **Step 9: Integrate local guard reports**

  Store only the latest guard per local owner. Combine:

  - Provider + fixed runtime + Research runtime + parent `saving` for
    `ai_models`;
  - Investor capture flag plus an on-request query of existing `aria-busy` for
    `personalization`;
  - Data Sources for `data_sync`.

  Discovery and route drafts are explicitly excluded because their state is
  preserved in `SettingsView`. Report cleanup on section unmount must not make
  an already-approved intent race or reopen the dialog.

- [x] **Step 10: Render `Tabs` with only the selected panel**

  Remove `ChevronDown`, `ChevronRight`, group headers, collapse buttons, and
  all-groups mapping. Build three `TabItem<SettingsGroupId>` values from the
  registry. Each panel contains only the active group's anchor bands and the
  responsive current-group directory layout.

  Keep the workflow tabs above the rail/content layout. Do not put tab panels,
  groups, or the directory in decorative cards.

- [x] **Step 11: Replace reveal timing with a commit-keyed effect**

  The exact-focus effect depends on `[activeGroup, pendingReveal]`, verifies the
  pending anchor belongs to the mounted group, queries the now-committed anchor,
  calls `scrollIntoView({ block: "start" })`, focuses with
  `{ preventScroll: true }`, and then clears that exact pending value. Do not use
  a fixed timeout or a one-shot rAF as the mount guarantee.

  Manual group changes set the first anchor but clear `pendingReveal`; focus
  remains on the activated tab. Search/NavigationTarget set pending exact focus.

- [x] **Step 12: Preserve responsive directory exclusivity**

  Pass `activeGroup` to both directory render forms. Keep the persistent rail
  only when `shellOverlay` is false and the Drawer only when true/open. Search
  result selection from the Drawer closes it before exact focus. Escape without
  selection still returns focus to the directory trigger.

- [x] **Step 13: Update CSS and satisfy static contracts**

  Remove obsolete `.settings-workspace-group > header` and collapse-specific
  rules. Add only Settings-local layout classes around the shared Tabs output.
  Keep `data-settings-overlay` as the only responsive switch; add no `@media`
  and no 959/960/961 literal.

  Satisfy the prewritten `SettingsCss.test.ts` assertions without adding a new
  static-test node.

  The final no-Calendar production-copy ratchet belongs to Task 5, where the
  old Macro body is actually replaced. Task 4 may temporarily retain that body
  behind the newly named registry anchor; it must not claim the content rewrite
  is already complete.

  Update `useOverlayFocus` so an explicit `returnFocusRef` remains an overlay
  entry reference and its latest connected `.current` is preferred at removal;
  otherwise preserve the captured previous-element and fallback ordering.
  This is the narrow mechanism needed for cancel-to-current versus
  confirm-to-destination focus. Existing Drawer and nested-overlay behavior
  must remain unchanged.

- [x] **Step 14: Run GREEN**

  ```bash
  npm test -- --run src/SettingsWorkspace.test.tsx src/SettingsModelRouting.test.ts src/SettingsProviderConfig.test.ts src/SettingsPostPgExitStorage.test.ts src/SettingsNewsStorage.test.ts src/SettingsCss.test.ts src/settings/settingsRegistry.test.ts src/ui/Tabs.test.tsx src/ui/overlays.test.tsx
  npm run typecheck
  ```

  Expected raw Task 4 delta: workspace `+12/-6`, model routing `+2/-0`, no
  `SettingsCss` or overlay node change. Cumulative full-package target:
  `64 files / 629 tests`.

- [x] **Step 15: Commit**

  ```bash
  git add apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/settings/SettingsDirectory.tsx apps/arkscope-web/src/settings/settingsRegistry.ts apps/arkscope-web/src/settings/settingsPreferences.ts apps/arkscope-web/src/settings/settings.css apps/arkscope-web/src/settings/settingsRegistry.test.ts apps/arkscope-web/src/ui/useOverlayFocus.ts apps/arkscope-web/src/ui/overlays.test.tsx apps/arkscope-web/src/SettingsWorkspace.test.tsx apps/arkscope-web/src/SettingsModelRouting.test.ts apps/arkscope-web/src/SettingsProviderConfig.test.ts apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts apps/arkscope-web/src/SettingsNewsStorage.test.ts apps/arkscope-web/src/SettingsCss.test.ts
  git commit -m "fix: organize Settings by workflow tabs"
  ```

---

## Task 5: Make `總經資料` the Sole Detailed FRED Owner

**Files:**
- Modify: `apps/arkscope-web/src/settings/MacroStorageSection.tsx`
- Create: `apps/arkscope-web/src/settings/MacroStorageSection.test.tsx`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`
- Verify: `apps/arkscope-web/src/settings/DataSourcesSection.tsx`

- [x] **Step 1: Write seven isolated Macro RED tests**

  Add exactly:

  1. `loads_status_and_snapshot_independently_and_renders_both_truths`
  2. `preserves_snapshot_details_when_status_leg_fails`
  3. `preserves_status_coverage_when_snapshot_leg_fails`
  4. `renders_missing_database_and_table_as_unavailable_not_empty_success`
  5. `renders_zero_rows_as_zero_stored_without_claiming_never_run`
  6. `keeps_stored_data_neutral_when_auto_refresh_is_off`
  7. `refresh_reloads_each_leg_once_without_raw_exception_copy`

  Use real DTO-shaped fixtures. Plant unique raw exception strings and assert
  they never enter normal DOM. The partial tests must preserve the successful
  leg, not merely show an alert. The refresh node must select the accessible
  `重新整理` command rather than a glyph or CSS selector.

- [x] **Step 2: Replace two storage integration node IDs**

  Replace the two IDs listed in accounting with:

  1. `shows_total_macro_data_without_claiming_calendar_product`
  2. `renders_market_empty_and_macro_partial_failures_as_user_outcomes`

  The directory expectation already changed to `總經資料` in Task 4. Because
  only one group mounts, the helper must continue selecting `資料與同步` before
  asserting storage anchors. Extend this integration file's hoisted API state
  with a real `MacroSnapshot` fixture plus an independently throwable snapshot
  leg; reset both Macro legs after each test. Do not let the newly added
  `getMacroSnapshot()` call fall through to real `fetch`. Keep the other three
  node IDs unchanged.

- [x] **Step 3: Run RED**

  ```bash
  npm test -- --run src/settings/MacroStorageSection.test.tsx src/SettingsPostPgExitStorage.test.ts
  ```

  Expected failures: Macro owns no snapshot leg, raw errors render, and old
  Calendar copy remains.

- [x] **Step 4: Implement independent read legs**

  `MacroStorageSection` owns separate `status`, `snapshot`, `statusUnavailable`,
  and `snapshotUnavailable` state. `load()` uses one `Promise.allSettled` over
  `getMacroStatus()` and `getMacroSnapshot()`:

  - fulfilled leg replaces that leg's truth and clears its stable unavailable
    flag;
  - rejected leg retains any prior successful truth and sets only stable copy;
  - one failed leg renders `InlineAlert state="partial"`;
  - both failed before any truth render a stable failed/unavailable state;
  - no raw exception detail is shown in normal mode.

  Add an unmount/sequence guard so a late older refresh cannot replace a newer
  accepted leg. Do not add a third request, cache, schema, or DTO.

- [x] **Step 5: Render honest detailed truth**

  Use visible title `總經資料`. Render:

  - snapshot series/value/observation/fetched-at details from the existing DTO;
  - stored coverage/timestamps from status;
  - `0 筆已儲存` for an observed zero count;
  - unavailable/unknown for absent DB/table;
  - neutral `自動刷新關閉` while retaining stored data and fetched-at; and
  - event-table counts, if returned, as compact stored coverage only, not a
    Calendar feature promise.

  Do not hard-code 11 series. Keep existing table scroll ownership and wrapping
  classes, now under Macro. Use the existing `Button` and `InlineAlert`
  primitives plus lucide `RefreshCw` for the refresh command and state copy;
  do not retain the raw `↻` glyph button, invent a chip, or add a local alert
  style.

- [x] **Step 6: Prove ownership mechanically**

  ```bash
  rg -n "getMacroSnapshot" apps/arkscope-web/src/Settings.tsx apps/arkscope-web/src/settings
  rg -n "FRED 資料快照|fred-snapshot-scroll|settings-fred-table" apps/arkscope-web/src/settings/DataSourcesSection.tsx
  ```

  The first command must show one production consumer in
  `MacroStorageSection.tsx`; type/test references are outside this scoped
  command. The second command must return no matches.

- [x] **Step 7: Run GREEN**

  ```bash
  npm test -- --run src/settings/MacroStorageSection.test.tsx src/SettingsPostPgExitStorage.test.ts src/SettingsProviderConfig.test.ts src/SettingsStabilizationCss.test.ts
  npm run typecheck
  ```

  Expected raw Task 5 delta: Macro `+7`, storage integration `+2/-2`; Data
  Sources retains its Task 3 `+3/-1` accounting. Cumulative full-package
  target: `65 files / 636 tests`.

- [x] **Step 8: Commit**

  ```bash
  git add apps/arkscope-web/src/settings/MacroStorageSection.tsx apps/arkscope-web/src/settings/MacroStorageSection.test.tsx apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts apps/arkscope-web/src/settings/DataSourcesSection.tsx apps/arkscope-web/src/SettingsProviderConfig.test.ts
  git commit -m "fix: give FRED details one Settings owner"
  ```

---

## Task 6: Reconcile the Exact Ledger and Mechanical Ratchets

**Files:**
- Modify only tests already named if a reviewed assertion needs mechanical
  adjustment.
- Do not add behavior or broaden scope.

- [x] **Step 1: List and diff test nodes**

  Generate baseline and head node lists from the exact focused command. Use
  sorted `comm` output to verify raw `+42/-12`. The 12 removed IDs must be the
  exact reviewed set; every other removal is a stop condition.

- [x] **Step 2: Run the focused 18-file gate**

  ```bash
  npm test -- --run \
    src/SettingsCss.test.ts \
    src/ui/classCoverage.test.ts \
    src/settings/settingsRegistry.test.ts \
    src/SettingsStabilizationCss.test.ts \
    src/SettingsWorkspace.test.tsx \
    src/SettingsPostPgExitStorage.test.ts \
    src/SettingsNewsStorage.test.ts \
    src/SettingsModelRouting.test.ts \
    src/SettingsProviderConfig.test.ts \
    src/FixedTaskRuntimeSection.test.tsx \
    src/ProviderSection.test.ts \
    src/CredentialList.test.ts \
    src/ResearchRuntimeSection.test.ts \
    src/ui/primitives.test.tsx \
    src/ui/overlays.test.tsx \
    src/InvestorProfilePanel.test.tsx \
    src/ui/Tabs.test.tsx \
    src/settings/MacroStorageSection.test.tsx
  ```

  Require `18 files / 164 tests`.

- [x] **Step 3: Run static ratchets**

  Require all of the following:

  - production `arkscope.settings.collapsedGroups.v1` appears only as a cleanup
    constant and never in a `getItem` call;
  - `arkscope.settings.activeGroup.v1` has exactly one production owner;
  - `getMacroSnapshot` has exactly one Settings production consumer;
  - `DataSourcesSection` contains no detailed snapshot table owner;
  - Settings production contains no `Macro / Calendar`,
    `總體經濟與行事曆`, or `總經與行事曆` label;
  - no `window.confirm` in Settings production;
  - no `@media` or 959/960/961 literal in Settings/Tabs source or CSS;
  - no new `aria-live` in Settings; and
  - class coverage remains empty.

- [x] **Step 4: Prove immutable paths**

  ```bash
  git diff --exit-code f797673 -- src data_sources tests
  git diff --exit-code f797673 -- apps/arkscope-web/src/api.ts
  git diff --exit-code f797673 -- apps/arkscope-web/src/Holdings.tsx
  git diff --exit-code f797673 -- apps/arkscope-web/src/InvestorProfilePanel.tsx
  git diff --exit-code f797673 -- apps/arkscope-web/src/Dashboard.tsx
  git diff --exit-code f797673 -- extensions
  ```

  No exception is allowed, including backend test fixtures.

- [x] **Step 5: Run the full frontend gate**

  ```bash
  npm test -- --run
  npm run typecheck
  npm run build
  ```

  Require `65 files / 636 tests`, clean typecheck, and build success. The
  already-known chunk-size warning is acceptable; any new warning is not.

- [x] **Step 6: Commit only ledger/test hardening if needed**

  If no changes were needed, do not create an empty commit. Any accounting
  deviation requires explicit plan amendment and review before continuing.

---

## Task 7: Responsive, Keyboard, Focus, and Lifecycle Browser Gate

**Files:**
- No product edits unless a failing reviewed contract first gets a RED test.
- Store screenshots/evidence outside tracked product paths.

- [x] **Step 1: Start an isolated no-scheduler sidecar and Vite server**

  Use temporary profile/data paths and unused ports. Never point a test server
  at production writable DBs. Record PIDs, roots, ports, and cleanup commands.

- [x] **Step 2: Verify all six exact viewports**

  Capture and inspect:

  ```text
  1440x900
  1024x768
  961x768
  960x768
  959x768
  390x844
  ```

  At each size require no horizontal page overflow, readable labels, visible
  focus rings, no content overlap, and no clipped tabs. At 961px require one
  persistent rail and no trigger/Drawer. At 960px, 959px, and 390px require one
  trigger, no persistent rail, and one transient Drawer only when open.

- [x] **Step 3: Verify Tabs keyboard contract**

  Starting on `AI 與模型`, use ArrowRight twice, ArrowLeft with wrap, Home, and
  End. Selection, focus, mounted panel, current-group directory, and stored
  group must move together. Mouse activation must match keyboard behavior.

- [x] **Step 4: Verify search and exact-target timing**

  - Empty query lists only current-group anchors.
  - `FRED` finds `總經資料`, switches to `資料與同步`, then focuses
    `macro_storage` after mount.
  - `OAuth` finds Provider.
  - Enter selects the deterministic first result.
  - Manual switch after an exact request does not later resurrect stale focus.
  - A seeded persisted `data_sync` group is overridden by a fresh Provider
    `NavigationTarget`.

- [x] **Step 5: Verify dirty/busy lifecycle behavior without real credentials**

  Use safe non-secret drafts and mocked/isolated delayed responses:

  - Provider draft -> switch request -> ConfirmDialog; cancel preserves draft;
    confirm switches and remount later starts clean.
  - Runtime draft follows the same rule.
  - Data Sources draft follows the same rule.
  - Pending Provider/Data Source mutation vetoes selection and shows a stable
    blocked alert.
  - Investor form edit prompts before leave; an `aria-busy=true` mutation vetoes
    leave. Do not issue a real provider login or write production profile data.
  - Model route draft and discovery result survive AI -> data -> AI without a
    discard dialog.

- [x] **Step 6: Verify polling lifecycle**

  With `資料與同步` selected, observe Data Sources schedule polling listener/timer
  existence. Switch away and prove listener/timer cleanup and no later state
  write. Switch back and prove one fresh lifecycle, not accumulated duplicate
  polling.

- [x] **Step 7: Verify FRED ownership and honest states**

  Using fixture-backed API responses, inspect both-success, each one-leg
  failure, missing DB/table, zero rows, and refresh-off/stored-data states.
  Data Sources must retain only compact health; `總經資料` must hold the one
  detailed table. No raw planted exception or top-level Calendar feature
  promise may appear; factual stored event-table labels remain allowed.

- [x] **Step 8: Stop every process**

  Confirm the chosen sidecar/Vite/browser ports refuse connections and record
  cleanup. Do not end the task with a live verification session.

---

## Task 8: Review-Ready Closeout

**Files:**
- Modify: this plan (implementation ledger only)
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md` only after implementation review
  status changes
- Do not mark the product LIVE before merge and user verification.

- [x] **Step 1: Fill the implementation ledger**

  Record:

  - implementation base and product base;
  - each product/test commit;
  - RED reason and GREEN command per task;
  - raw node `+42/-12` proof;
  - focused `18/164` and full `65/636` results;
  - immutable-path and static ratchet outputs;
  - six-viewport screenshots and interaction results;
  - process cleanup; and
  - every reviewed deviation, if any.

- [x] **Step 2: Run final worktree checks**

  ```bash
  git status --short
  git diff --check
  git log --oneline --decorate -12
  ```

  The worktree may contain only intentional tracked plan-ledger changes before
  the final docs commit. No generated screenshots, DBs, tokens, or browser
  profiles may be staged.

- [x] **Step 3: Commit review evidence**

  ```bash
  git add docs/superpowers/plans/2026-07-19-p2-8-slice-4-1-settings-navigation-correction.md
  git commit -m "docs: record Settings correction verification"
  ```

- [x] **Step 4: Stop review-ready**

  Request independent implementation review. Do not merge, sync Design Kit,
  mark LIVE, open i18n implementation, or delete the worktree yet.

---

## Independent Reviewer Focus

The reviewer should independently verify, not trust the ledger, especially:

1. raw node `+42/-12` and the exact 12 removals;
2. Tabs automatic activation, wrap, Home/End, one mounted panel, and veto focus;
3. no CSS-hidden inactive group;
4. exact-focus effect runs only after the owning group commits;
5. manual tab selection clears stale pending anchors;
6. active preference fail-closed behavior and old-key never-read proof;
7. owner inventory: parent-preserved route/discovery versus locally guarded
   Provider/runtime/Data Sources/Investor states;
8. no value leakage through guard callbacks or visible reasons;
9. OAuth and real mutations are hard blocks, not confirmable discard;
10. Investor Profile is byte-identical and its conservative guard has no
    false-negative path;
11. Data Sources has no snapshot request/table and its polling unmounts;
12. Macro's two legs preserve independent truth and never show raw errors;
13. no Calendar product promise or invented never-ran semantics;
14. exact 961/960/959 breakpoint behavior; and
15. absolute backend/API/Holdings/Investor/Dashboard/extensions byte identity.

---

## Stop Conditions

Stop and return for design/review if any of these occurs:

1. preserving a required workflow seems to require keeping inactive groups
   mounted;
2. Investor Profile must be edited to satisfy the guard;
3. OAuth cannot be safely hard-blocked with existing section ownership;
4. a guard needs to expose draft/token/profile values;
5. Tabs needs a manual-activation mode or per-surface keyboard fork;
6. exact focus requires a fixed delay rather than commit-keyed mounting;
7. a new Settings route, anchor, preference key, backend endpoint, DTO, or API
   call is required;
8. Data Sources needs `/macro/status` or `/macro/snapshot` for compact truth;
9. Macro needs schema/run telemetry to distinguish never-ran from zero rows;
10. any immutable path changes;
11. any test node outside the reviewed 12 disappears or raw accounting differs;
12. a new raw exception, `window.confirm`, `aria-live`, undefined class, or
    shell breakpoint owner appears;
13. a visual viewport clips tabs, overlaps content, or mounts both directory
    forms; or
14. live verification would require production credential/DB mutation.

---

## Post-Review Merge Closeout (Not Part of Implementation Clearance)

Only after independent implementation GREEN and explicit user merge approval:

1. restore the main checkout to clean tracked state;
2. fast-forward merge the reviewed branch;
3. rerun focused `18/164`, full `65/636`, typecheck, build, static ratchets, and
   merged-tree desktop smoke;
4. restart the desktop app and obtain the user's Settings verification;
5. mark Slice 4.1 and corrected Slice 4 Settings LIVE in spec/plan/map;
6. perform Design Kit sync #5 for shared Tabs, three-tab Settings IA, and
   `總經資料` states only;
7. open the app-wide i18n decision document (Shell + Settings first), while
   keeping Slice 5 queued per the priority map;
8. update memory/decision log; and
9. remove the worktree/branch only after all closeout evidence is retained.
