# I18N-1 Shell + Common UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Use
> superpowers:using-git-worktrees before Task 0,
> superpowers:test-driven-development for every behavior change,
> superpowers:requesting-code-review before integration, and
> superpowers:verification-before-completion before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status:** CLEARED FOR IMPLEMENTATION — INDEPENDENT PLAN REVIEW GREEN,
> 2026-07-20
>
> I18N-0 is LIVE COMPLETE through merge-closeout commit `ac57858`. This plan is
> the single NEXT unit named by the approved app-wide i18n decision. It does not
> authorize product implementation until independent plan review returns GREEN
> and a clearance commit is recorded.

**Goal:** Localize the shipped application Shell and the generic Drawer and
BoundedProgress copy it consumes into complete `zh-Hant` and English resources,
while preserving navigation, work ownership, formatter output, component
state, responsive layout, and the selector-last release contract.

**Architecture:** Extend the existing bundled `common` and `shell` namespaces,
then consume them through typed selector calls only. Navigation keeps semantic
group/view identifiers in `navigation.ts`; one new `shellLabels.ts` seam maps
those closed unions to static typed selectors. Source-owned values remain data:
ticker symbols, thread titles, run IDs, model names, API endpoints, counts, and
elapsed-time formatter output are interpolated or passed through rather than
made translation keys. The visible-literal ratchet promotes `App.tsx`, all of
`shell/**`, `Drawer.tsx`, and `BoundedProgress.tsx` to zero-debt migrated scope;
the product name `ArkScope` is the sole exact stable-identifier allowlist entry.

**Tech Stack:** React 18, TypeScript 5.9, i18next 26.3.6 selector API,
react-i18next 17.0.10, Vitest 4/jsdom, the existing TypeScript-AST literal
scanner, Vite/Electron, and Playwright/CDP browser verification against isolated
temporary profile databases.

---

## Design Authority

1. Primary product authority:
   `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md`.
2. Terminology authority:
   `docs/design/ARKSCOPE_TERMINOLOGY.md`.
3. Shell behavior/IA authority:
   `docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`.
4. Foundation mechanism and gate evidence:
   `docs/superpowers/plans/2026-07-20-i18n-0-foundation.md`.
5. Product-behavior baseline is merged `master` at `ac57858`. The later
   plan-review clearance commit travels with the implementation branch but does
   not replace this A/B behavior anchor.

If this plan conflicts with any authority above, stop and amend the authority
before changing product code.

---

## Locked Decisions

1. I18N-1 is frontend-only. No backend route, DTO, schema, store, scheduler,
   extension, desktop-main, or API client behavior changes.
2. The public locale selector remains absent. Runtime `en` is exercised only by
   test/dev setup and isolated seeded profiles.
3. There is no IA, navigation-order, visual-style, breakpoint, polling,
   persistence, or work-membership redesign.
4. `SHELL_NAV_GROUPS` remains the structural authority for exactly four groups
   and eight shipped destinations, but stores only stable semantic IDs, views,
   and icons. It stores no source-language labels.
5. One explicit allowlist maps every `ShellNavGroupId` and `ShellView` to a
   typed static selector. Dynamic translation-key construction remains banned.
6. `shellViewLabel()` takes the active Shell translator. Ticker detail context
   remains the normalized ticker value and is never localized.
7. `ArkScope` is a stable product identifier. It remains a literal and becomes
   the sole reviewed `stable_identifier` allowlist entry; it is not duplicated
   into locale resources.
8. Traditional Chinese visible copy remains byte-for-byte equivalent unless
   this plan explicitly records one correction. The sole correction is the
   BackgroundWork result destination: the owner passes `AI 研究對話`, so generic
   progress renders the natural `結果：AI 研究對話` instead of the duplicated
   `結果：結果留在 AI 研究對話`.
9. English navigation labels are: `Explore`, `Research`, `Monitor`, `System`;
   `Home`, `Watchlist`, `Universe`, `News`, `AI Research`, `Holdings`,
   `System / Health`, and `Settings`.
10. `Home`, `News`, `AI Research`, `Explore`, `Research`, `Monitor`, and
    `System / Health` are added to the terminology authority in the same commit
    as their resources. Existing `Watchlist`, `Universe`, `Holdings`, and
    `Settings` terms are reused, not redefined.
11. `Drawer` owns only `Close`, `Pin`, and `Unpin`. Its title, body, footer, and
    child controls remain owner-provided React content.
12. `BoundedProgress` owns generic elapsed/bound/navigation/cancellation/result
    copy and default failure copy. `stageLabel`, `resultLabel`, `errorTitle`,
    and `errorDetail` remain owner inputs.
13. `formatElapsed()` remains byte-identical and locale-neutral (`15m 30s`).
    This slice does not move duration, number, date, timezone, P&L, or financial
    formatting into i18next.
14. Background-work domain mapping remains:
    - `queued` and `running` -> common `running` presentation;
    - `succeeded` -> common `ready` presentation;
    - `failed` -> common `failed` presentation; and
    - `cancelled`/`interrupted` -> common `interrupted` presentation.
15. Thread titles received from Research are user/source content and remain
    unchanged. Missing titles are represented as `null` in the registry and
    translated at render time as the active-locale AI Research label.
16. The registry must never capture a translated fallback string. This is what
    makes an already-open Background Work Drawer switch locale without stale
    copy or registry mutation.
17. Run IDs, counts, durations, API base, tool count, status timestamp, model
    name, and source thread title are interpolation/source values. None becomes
    a resource key.
18. Developer Mode values remain sanitized and technical; only their labels are
    localized. Raw `StatusState.error.message`, Research error/question/answer,
    credential ID, token usage, and provider payload remain unrendered.
19. Resource additions are exactly `common +17` and `shell +37` non-empty leaf
    keys in each locale. Locale key paths remain recursively identical.
20. Tests continue to assert Traditional Chinese rendered copy under the fixed
    default test locale. English coverage is additive and focused; existing
    behavior tests are not converted to key assertions.
21. Locale changes rerender labels without remounting the selected Shell view,
    closing an open navigation/background Drawer, clearing work state, or
    changing focus ownership.
22. CSS remains byte-identical except for the reviewed one-line
    `flex-wrap: wrap` addition to `.shell-topbar-primary` in `shell.css`.
    English must fit the nav/topbar/Drawer layout at the canonical six
    viewports. Font size, labels, and minimum control widths are never reduced
    to make copy fit. Any CSS beyond that exact declaration is a new stop and
    review condition.
23. Scanner ownership after this slice is exactly:
    `src/App.tsx`, `src/shell/**`, `src/ui/Drawer.tsx`, and
    `src/ui/BoundedProgress.tsx`, in addition to I18N-0 scopes.
24. All 59 legacy debt signatures (61 occurrences) owned by those paths retire.
    `ArkScope` remains one current candidate under the exact allowlist. Expected
    scanner totals are candidates `1649`, current signatures `1563`, debt
    signatures `1562`, allowlist entries `1`.
25. Design Kit does not synchronize partial localization. I18N-6 owns the
    public selector and bilingual Design Kit release state.

---

## Grounded Baseline

Reproduced on clean merged `master` at `ac57858` on 2026-07-20:

- frontend full suite: `73 files / 680 tests`, all passing;
- backend collection: `4569` tests;
- focused owned baseline: `10 files / 87 tests` across App Shell, Shell,
  Drawer, BoundedProgress, resources, and foundation boundaries;
- scanner: `1709` candidates, `1621` current/debt signatures, `0` allowlist;
- migrated scopes: `src/i18n/**`, `src/main.tsx`;
- `src/i18n/resources/*/shell.ts` is empty;
- `src/App.tsx` owns three navigation literals and two primary-navigation
  accessible-name occurrences;
- `src/shell/**` owns 37 visible-debt signatures including navigation,
  topbar, Background Work, and the captured `AI 研究` fallback;
- `Drawer.tsx` owns three control labels;
- `BoundedProgress.tsx` owns 15 signatures / 16 occurrences;
- the selected backend fields are already safely projected: normal Shell sees
  status kind only; Developer Mode sees sanitized diagnostic values; Research
  work excludes raw question/error/answer/credential/token/provider payload;
- no product file currently imports a translation hook for Shell/common UI;
  and
- the normal desktop may remain running during implementation because every
  browser/runtime gate uses isolated ports, profile DBs, and browser storage.

The exact focused baseline command is:

```bash
cd apps/arkscope-web
npx vitest list \
  src/AppShell.test.tsx \
  src/shell/navigation.test.ts \
  src/shell/ShellNavigation.test.tsx \
  src/shell/ShellTopBar.test.tsx \
  src/shell/BackgroundWorkIndicator.test.tsx \
  src/shell/researchWork.test.tsx \
  src/ui/BoundedProgress.test.tsx \
  src/ui/overlays.test.tsx \
  src/i18n/resources.test.ts \
  src/i18n/foundationBoundaries.test.ts
```

These ten existing files collect exactly 87 nodes. The reviewed runtime
deviation also brings the existing `src/shell/ShellCss.test.ts` into the
focused set; it contributes six baseline nodes. The final 12-file command in
Task 7 contains those 11 existing files plus the new
`src/shell/shellLabels.test.ts`: `11 files / 93 tests -> 12 files / 108 tests`.

---

## Reviewed Runtime Deviation: Localized Topbar Wrapping

The first English `390x844` browser run found a real horizontal overflow:
`.shell-topbar-primary` needed approximately `420px` while the viewport was
`390px`. The complete English `To review 1` label extended beyond the content
edge; truncating that label, shrinking font size, or reducing reviewed control
minimums would hide meaning to preserve a single-line layout.

Temporary CDP diagnosis proved that adding exactly `flex-wrap: wrap` to
`.shell-topbar-primary` removes the overflow while retaining every label and
existing minimum width. The same stylesheet already uses wrapping for
`.shell-topbar-diagnostics`, so this is an existing Shell layout pattern rather
than a new breakpoint or responsive mode. The diagnostic box-height delta is
not an acceptance constant; the real implementation must record leaf-control
row positions and actual topbar heights in both locales.

This scope amendment adds one named RED-first node to the existing
`ShellCss.test.ts`: `keeps the topbar primary row wrap-safe for long localized
labels`. The product delta is exactly one declaration. Runtime acceptance is:

- `zh-Hant` at `390px` remains one primary-control row;
- `en` at `390px` wraps the health/work controls onto a second row without
  clipping or horizontal overflow;
- both locales remain one row at every canonical viewport at least `768px`
  wide; and
- any different row distribution or additional CSS is a stop condition.

---

## Exact Resource Inventory

### `common` namespace: exactly +17 leaves per locale

| Key | `zh-Hant` | `en` |
| --- | --- | --- |
| `actions.close` | `關閉` | `Close` |
| `actions.pin` | `釘選` | `Pin` |
| `actions.unpin` | `取消釘選` | `Unpin` |
| `actions.stop` | `停止` | `Stop` |
| `boundedProgress.failureTitle` | `工作失敗` | `Work failed` |
| `boundedProgress.failureDetail` | `工作未完成，請依錯誤指示處理。` | `The work did not complete. Follow the error guidance to continue.` |
| `boundedProgress.awaitingConfirmation` | `已達上界，等待伺服器確認` | `Bound reached; waiting for server confirmation` |
| `boundedProgress.completedAnnouncement` | `工作完成` | `Work completed` |
| `boundedProgress.interruptedAnnouncement` | `工作已中止` | `Work interrupted` |
| `boundedProgress.overallElapsed` | `總耗時 {{duration}}` | `Overall elapsed {{duration}}` |
| `boundedProgress.stageElapsed` | `階段耗時 {{duration}}` | `Stage elapsed {{duration}}` |
| `boundedProgress.stageBound` | `本階段上界 {{duration}}` | `Stage bound {{duration}}` |
| `boundedProgress.continuesAfterNavigation` | `離開頁面後繼續` | `Continues after leaving this page` |
| `boundedProgress.trackingNotGuaranteed` | `離開頁面後不保證追蹤` | `Tracking is not guaranteed after leaving this page` |
| `boundedProgress.cancellationAvailable` | `可從此處取消` | `Can be cancelled here` |
| `boundedProgress.cancellationUnavailable` | `無法從此處取消` | `Cannot be cancelled here` |
| `boundedProgress.result` | `結果：{{destination}}` | `Result: {{destination}}` |

### `shell` namespace: exactly +37 leaves per locale

| Key | `zh-Hant` | `en` |
| --- | --- | --- |
| `navigation.primaryLabel` | `主要導覽` | `Primary navigation` |
| `navigation.drawerTitle` | `導覽` | `Navigation` |
| `navigation.openDrawer` | `開啟導覽` | `Open navigation` |
| `navigation.groups.explore` | `探索` | `Explore` |
| `navigation.groups.research` | `研究` | `Research` |
| `navigation.groups.monitor` | `追蹤` | `Monitor` |
| `navigation.groups.system` | `系統` | `System` |
| `navigation.views.home` | `工作台` | `Home` |
| `navigation.views.watchlist` | `自選股` | `Watchlist` |
| `navigation.views.universe` | `全部標的` | `Universe` |
| `navigation.views.news` | `新聞·事件` | `News` |
| `navigation.views.research` | `AI 研究` | `AI Research` |
| `navigation.views.holdings` | `持倉` | `Holdings` |
| `navigation.views.system` | `System / Health` | `System / Health` |
| `navigation.views.settings` | `設定` | `Settings` |
| `topbar.sidecar.ready` | `Sidecar 已連線` | `Sidecar connected` |
| `topbar.sidecar.error` | `Sidecar 無法連線` | `Sidecar unavailable` |
| `topbar.sidecar.loading` | `正在連線` | `Connecting` |
| `topbar.developerDiagnostics` | `Developer diagnostics` | `Developer diagnostics` |
| `topbar.diagnostics.apiValue` | `API {{value}}` | `API {{value}}` |
| `topbar.diagnostics.toolsValue` | `Tools {{value}}` | `Tools {{value}}` |
| `topbar.diagnostics.lastStatusValue` | `Last status {{value}}` | `Last status {{value}}` |
| `topbar.diagnostics.cardModelValue` | `Card model {{value}}` | `Card model {{value}}` |
| `backgroundWork.triggerAria` | `AI 研究背景工作：{{summary}}` | `AI Research background work: {{summary}}` |
| `backgroundWork.activeCount` | `執行中 {{count}}` | `Running {{count}}` |
| `backgroundWork.attentionCount` | `待查看 {{count}}` | `To review {{count}}` |
| `backgroundWork.drawerTitle` | `背景工作` | `Background work` |
| `backgroundWork.sessionScope` | `僅顯示此桌面工作階段觀察到的 AI 研究。` | `Only AI Research observed in this desktop session is shown.` |
| `backgroundWork.openConversation` | `開啟對話` | `Open conversation` |
| `backgroundWork.dismissAria` | `忽略 {{runId}}` | `Dismiss {{runId}}` |
| `backgroundWork.stages.queued` | `等待執行` | `Waiting to run` |
| `backgroundWork.stages.running` | `AI 研究執行中` | `AI Research running` |
| `backgroundWork.stages.succeeded` | `研究完成` | `Research complete` |
| `backgroundWork.stages.failed` | `研究未完成` | `Research incomplete` |
| `backgroundWork.stages.interrupted` | `研究已中止` | `Research interrupted` |
| `backgroundWork.resultDestination` | `AI 研究對話` | `AI Research conversation` |
| `backgroundWork.failureNextStep` | `開啟原對話查看可採取的下一步。` | `Open the original conversation to see the available next step.` |

No alternative wording is selected during implementation. A requested copy
change is a plan-review amendment so tests/resources do not drift independently.

---

## Exact File Map

### Create

- `apps/arkscope-web/src/shell/shellLabels.ts`
- `apps/arkscope-web/src/shell/shellLabels.test.ts`

### Modify: product/runtime

- `apps/arkscope-web/src/App.tsx`
- `apps/arkscope-web/src/shell/navigation.ts`
- `apps/arkscope-web/src/shell/ShellNavigation.tsx`
- `apps/arkscope-web/src/shell/ShellTopBar.tsx`
- `apps/arkscope-web/src/shell/BackgroundWorkIndicator.tsx`
- `apps/arkscope-web/src/shell/researchWork.ts`
- `apps/arkscope-web/src/ui/Drawer.tsx`
- `apps/arkscope-web/src/ui/BoundedProgress.tsx`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/common.ts`
- `apps/arkscope-web/src/i18n/resources/en/common.ts`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/shell.ts`
- `apps/arkscope-web/src/i18n/resources/en/shell.ts`

### Modify: tests and ratchet data

- `apps/arkscope-web/src/i18n/resources.test.ts`
- `apps/arkscope-web/src/i18n/foundationBoundaries.test.ts`
- `apps/arkscope-web/src/AppShell.test.tsx`
- `apps/arkscope-web/src/shell/navigation.test.ts`
- `apps/arkscope-web/src/shell/ShellNavigation.test.tsx`
- `apps/arkscope-web/src/shell/ShellTopBar.test.tsx`
- `apps/arkscope-web/src/shell/BackgroundWorkIndicator.test.tsx`
- `apps/arkscope-web/src/shell/researchWork.test.tsx`
- `apps/arkscope-web/src/shell/ShellCss.test.ts`
- `apps/arkscope-web/src/ui/BoundedProgress.test.tsx`
- `apps/arkscope-web/src/ui/overlays.test.tsx`
- `apps/arkscope-web/scripts/i18n/visible-literal-debt.json`
- `apps/arkscope-web/scripts/i18n/visible-literal-allowlist.json`
- `apps/arkscope-web/scripts/i18n/migrated-scopes.json`

### Modify: reviewed documentation/ledger

- `docs/design/ARKSCOPE_TERMINOLOGY.md`
- `docs/design/PROJECT_PRIORITY_MAP.md`
- `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md`
- `docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md`

### Modify: reviewed runtime layout exception

- `apps/arkscope-web/src/shell/shell.css` -- add only `flex-wrap: wrap` to
  `.shell-topbar-primary`

### Must remain byte-identical to `ac57858`

- all backend `src/**`, `data_sources/**`, and `tests/**`;
- `apps/arkscope-web/src/api.ts`;
- every current product surface except `App.tsx`;
- `Settings.tsx`, `settings/**`, `Research.tsx`, Research workspace/history/
  evidence components, Holdings/Portfolio, News, Watchlist, Universe, Home,
  Ticker Detail, Dashboard/System, and AICard;
- `ui/Status.tsx`, `ui/Button.tsx`, `ui/ConfirmDialog.tsx`, `ui/DataTable.tsx`,
  `ui/Tabs.tsx`, tokens, and focus/breakpoint hooks;
- all CSS except the exact reviewed one-line `shell.css` declaration;
- desktop and extension trees; and
- package manifests and lockfile.

---

## Exact Test Ledger

No existing test node is removed or renamed. Existing assertions evolve only
in three reviewed places: the explicit result-destination copy correction;
Task 3's navigation authority shape from labels to IDs/views; and Task 5's
missing-thread-title expectation from captured `AI 研究` to semantic `null`.

| File | Added nodes | Exact new node names |
| --- | ---: | --- |
| `src/i18n/resources.test.ts` | 1 | `resolves the reviewed common and shell copy in both locales` |
| `src/shell/shellLabels.test.ts` | 2 | `maps every shell workflow group in both locales`; `maps every shipped shell view in both locales` |
| `src/shell/ShellNavigation.test.tsx` | 1 | `renders the reviewed English navigation without changing structure` |
| `src/AppShell.test.tsx` | 3 | `renders English overlay navigation names from the shell namespace`; `switches locale without losing the selected shell view`; `switches locale without closing the background-work drawer` |
| `src/shell/ShellTopBar.test.tsx` | 1 | `renders English health and developer diagnostic labels without exposing raw errors` |
| `src/shell/BackgroundWorkIndicator.test.tsx` | 2 | `renders English background-work chrome while preserving source titles`; `updates only fallback copy when locale changes with the drawer open` |
| `src/shell/researchWork.test.tsx` | 1 | `keeps a missing thread title semantic instead of capturing localized fallback copy` |
| `src/shell/ShellCss.test.ts` | 1 | `keeps the topbar primary row wrap-safe for long localized labels` |
| `src/ui/BoundedProgress.test.tsx` | 1 | `renders English generic progress copy while preserving owner-provided values` |
| `src/ui/overlays.test.tsx` | 1 | `localizes Drawer controls without remounting the open panel` |
| `src/i18n/foundationBoundaries.test.ts` | 1 | `records the exact I18N-1 migrated scopes and sole ArkScope allowlist` |

Accounting:

- frontend: `73 files / 680 tests -> 74 files / 695 tests`, exactly `+15/-0`;
- focused owned set: original `10 files / 87 tests`, augmented reviewed
  baseline `11 files / 93 tests`, final `12 files / 108 tests`;
- backend: `4569 -> 4569`, exact `+0/-0` by byte identity;
- resources: `common +17`, `shell +37` per locale, exact key parity;
- scanner debt: `1621 -> 1562`, exactly `-59` signatures;
- allowlist: `0 -> 1`, exact `ArkScope` stable identifier; and
- migrated scopes: `2 -> 6`, exact four additions.

Parameterized loops stay inside the named nodes and do not create hidden test
IDs. If collection differs, stop and reconcile this ledger before continuing.

---

## Backend-Origin and Source-Content Boundary

| Value | Classification | I18N-1 behavior |
| --- | --- | --- |
| `StatusState.kind` | stable frontend enum | explicit localized health copy |
| `StatusState.error.message` | raw/generic error | never rendered |
| thread title | user/source content | pass through unchanged; nullable fallback translated at render |
| Research status | stable DTO enum | explicit allowlist to localized stage labels |
| Research question/error/answer/credential/token/provider payload | private/raw data | omitted by existing projection and tests |
| run ID | stable identifier | interpolation only in exact dismissal accessible name |
| API base/model name/status timestamp/tool count | Developer diagnostic value | pass through sanitized value; localize surrounding label |
| ticker context | stable identifier | pass through normalized ticker |
| elapsed duration | existing formatter result | pass through `formatElapsed()` unchanged |

There is no new backend-copy mapping and no generic API `Error.message` may
enter a translated resource or visible normal-mode sink.

---

## Implementation Ledger

This table is the single in-plan owner for implementation evidence. Populate
it incrementally after independent plan review clears Task 0; do not replace
exact commands, hashes, node IDs, or artifacts with prose summaries.

| Evidence | Required record | Current state |
| --- | --- | --- |
| Plan review | findings, resolution commit, clearance commit | GREEN; assertion-ledger advisory resolved; clearance `857677871faf9777a4a2e294a6b0db3209c1a784` |
| Branch ancestry | product A/B base, clearance base, worktree path, branch | Product base `ac57858`; `codex/i18n-1-shell-common-ui` at `/tmp/arkscope-i18n-1-shell`, opened from clearance `85767787` |
| TDD commits | RED command/output and GREEN commit for Tasks 1-6 | Not started; product implementation unauthorized |
| Resource accounting | exact Common/Shell paths and per-locale leaf counts | Planned `common +17`, `shell +37`; not implemented |
| Test accounting | baseline/head lists, comm output, per-file additions/removals | Baseline backend `4569`, frontend `73/680`, original focused `10/87`; reviewed focused baseline `11/93`; planned frontend `+15/-0`, backend `+0/-0` |
| Runtime CSS deviation | RED/GREEN node, exact one-line hunk, both-locale row geometry | Reviewed after English `390px` overflow; implementation not started |
| Literal ratchet | before/after totals, manifest hashes, exact allowlist/scopes | Baseline confirmed `1709/1621/1621/0`; migration not applied |
| Immutable gates | backend/API/CSS/desktop/extensions/non-owner diffs | Not run against an implementation tip |
| Runtime gate | locale/viewport matrix, focus/state/privacy assertions, process cleanup | Not run |
| Independent review | reviewer commands, findings, reviewed product/docs tips | Not requested |
| Merge closeout | merge hash, merged-tree reruns, desktop check, next unit | Not authorized |

---

## Task 0: Review Clearance, Worktree, and Re-grounding

**Files:**
- Modify: `docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [x] **Step 1: Apply independent plan-review findings**

  Resolve every must-fix in this document. Recompute exact test/resource/
  scanner accounting for any approved change. Do not hide review additions in
  a net total.

- [x] **Step 2: Mark the plan cleared and commit docs only**

  Change status to `CLEARED FOR IMPLEMENTATION`, synchronize the map, and
  commit:

  ```bash
  git add docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: clear i18n shell implementation plan"
  ```

  Record that commit as `PLAN_REVIEW_CLEARANCE_COMMIT` in the ledger.

- [x] **Step 3: Create an isolated implementation worktree**

  From the clearance commit:

  ```bash
  git worktree add /tmp/arkscope-i18n-1-shell -b codex/i18n-1-shell-common-ui PLAN_REVIEW_CLEARANCE_COMMIT
  ```

  Never implement in the user's normal checkout.

  The initial direct checkout stopped at the known linked-worktree git-crypt
  boundary before materialization. The clean retry used `--no-checkout`, copied
  only `.git/git-crypt/keys/default` into linked Git metadata, then populated
  `HEAD` with `git read-tree -mu HEAD`. No DB, token, browser profile, dirty
  main-checkout file, or user data was copied.

- [x] **Step 4: Re-run and record exact baselines**

  Run:

  ```bash
  pytest --collect-only -q
  npm test --workspace apps/arkscope-web -- --run
  npm run check:i18n-literals --workspace apps/arkscope-web
  ```

  Require backend `4569`, frontend `73/680`, and scanner
  `1709/1621/1621/0`. Run the focused list command from Grounded Baseline and
  require the ten existing files to total 87 while the new file is absent.

- [x] **Step 5: Prove the behavior baseline and dirty-tree boundary**

  Record `ac57858` as product baseline. Require a clean implementation worktree
  and a main checkout whose only allowed unrelated change remains user-owned;
  any overlap with this file map is a stop condition.

---

## Task 1: Add Reviewed Common and Shell Resources

**Files:**
- Modify: `docs/design/ARKSCOPE_TERMINOLOGY.md`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/common.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/common.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/shell.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/shell.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

- [ ] **Step 1: Write the failing exact-resource test**

  Add the named test to `resources.test.ts`. It creates a fresh instance per
  locale, obtains fixed `common` and `shell` translators, and proves both
  interpolation and representative terminology:

  ```ts
  it("resolves the reviewed common and shell copy in both locales", () => {
    const cases = [
      {
        locale: "zh-Hant" as const,
        close: "關閉",
        result: "結果：AI 研究對話",
        universe: "全部標的",
        running: "執行中 2",
      },
      {
        locale: "en" as const,
        close: "Close",
        result: "Result: AI Research conversation",
        universe: "Universe",
        running: "Running 2",
      },
    ];

    for (const expected of cases) {
      const instance = createInstance();
      initializeI18n(instance, expected.locale);
      const commonT = instance.getFixedT(expected.locale, "common");
      const shellT = instance.getFixedT(expected.locale, "shell");
      expect(commonT(($) => $.actions.close)).toBe(expected.close);
      expect(commonT(($) => $.boundedProgress.result, {
        destination: expected.locale === "en"
          ? "AI Research conversation"
          : "AI 研究對話",
      })).toBe(expected.result);
      expect(shellT(($) => $.navigation.views.universe)).toBe(expected.universe);
      expect(shellT(($) => $.backgroundWork.activeCount, { count: 2 }))
        .toBe(expected.running);
    }
  });
  ```

- [ ] **Step 2: Run RED**

  ```bash
  npm test --workspace apps/arkscope-web -- --run src/i18n/resources.test.ts
  ```

  Expected: the new assertions fail because the reviewed keys/values do not
  exist. A separate typecheck in Step 5 proves the selectors statically.

- [ ] **Step 3: Extend the terminology authority**

  Add exact canonical rows:

  | Concept | English | Traditional Chinese |
  | --- | --- | --- |
  | Primary work surface | Home | 工作台 |
  | Event/news surface | News | 新聞·事件 |
  | AI research surface | AI Research | AI 研究 |
  | Shell workflow group | Explore | 探索 |
  | Research workflow group | Research | 研究 |
  | Monitoring workflow group | Monitor | 追蹤 |
  | System diagnostics surface | System / Health | System / Health |

  Do not copy the full resource inventory into the terminology document.

- [ ] **Step 4: Add the exact resource trees**

  Preserve the existing `i18n.missingTranslation` leaf, then add the exact
  Common inventory. The Traditional Chinese shape is:

  ```ts
  const common = {
    i18n: { missingTranslation: "此文字暫時無法顯示。" },
    actions: {
      close: "關閉",
      pin: "釘選",
      unpin: "取消釘選",
      stop: "停止",
    },
    boundedProgress: {
      failureTitle: "工作失敗",
      failureDetail: "工作未完成，請依錯誤指示處理。",
      awaitingConfirmation: "已達上界，等待伺服器確認",
      completedAnnouncement: "工作完成",
      interruptedAnnouncement: "工作已中止",
      overallElapsed: "總耗時 {{duration}}",
      stageElapsed: "階段耗時 {{duration}}",
      stageBound: "本階段上界 {{duration}}",
      continuesAfterNavigation: "離開頁面後繼續",
      trackingNotGuaranteed: "離開頁面後不保證追蹤",
      cancellationAvailable: "可從此處取消",
      cancellationUnavailable: "無法從此處取消",
      result: "結果：{{destination}}",
    },
  } as const;
  ```

  Add the exact English values from the inventory with the same shape. Replace
  each empty Shell resource with the exact `navigation`, `topbar`, and
  `backgroundWork` trees and all 37 leaves from the inventory. Retain the
  terminology-authority header in all four files.

- [ ] **Step 5: Run GREEN and the generic resource gates**

  ```bash
  npm test --workspace apps/arkscope-web -- --run src/i18n/resources.test.ts
  npm run typecheck --workspace apps/arkscope-web
  ```

  Expected: `1 file / 7 tests`; exact key parity/non-empty tests remain green.

- [ ] **Step 6: Commit**

  ```bash
  git add docs/design/ARKSCOPE_TERMINOLOGY.md \
    apps/arkscope-web/src/i18n/resources \
    apps/arkscope-web/src/i18n/resources.test.ts
  git commit -m "feat: add shell localization resources"
  ```

---

## Task 2: Localize Drawer and BoundedProgress Generic Copy

**Files:**
- Modify: `apps/arkscope-web/src/ui/Drawer.tsx`
- Modify: `apps/arkscope-web/src/ui/BoundedProgress.tsx`
- Modify: `apps/arkscope-web/src/ui/overlays.test.tsx`
- Modify: `apps/arkscope-web/src/ui/BoundedProgress.test.tsx`

- [ ] **Step 1: Write the failing English BoundedProgress test**

  Import the global i18next instance and add:

  ```tsx
  it("renders English generic progress copy while preserving owner-provided values", async () => {
    await act(async () => { await i18n.changeLanguage("en"); });
    await mount(
      <BoundedProgress
        {...baseProps}
        status="running"
        stageLabel="Provider-owned stage"
        resultLabel="Owner destination"
        canCancel
        onCancel={vi.fn()}
      />,
    );

    expect(host!.textContent).toContain("Provider-owned stage");
    expect(host!.textContent).toContain("Overall elapsed 15m 30s");
    expect(host!.textContent).toContain("Stage elapsed 2m 00s");
    expect(host!.textContent).toContain("Stage bound 15m 00s");
    expect(host!.textContent).toContain("Continues after leaving this page");
    expect(host!.textContent).toContain("Can be cancelled here");
    expect(host!.textContent).toContain("Result: Owner destination");
    expect(host!.querySelector("button")?.textContent).toContain("Stop");
  });
  ```

- [ ] **Step 2: Write the failing Drawer locale/remount test**

  Import i18next and add:

  ```tsx
  it("localizes Drawer controls without remounting the open panel", async () => {
    stubMatchMedia(false);
    await render(
      <Drawer open pinnable pinned={false} title="Source title"
        onClose={vi.fn()} onPinnedChange={vi.fn()}>
        <button>Source child</button>
      </Drawer>,
    );
    const panel = document.querySelector('[role="dialog"]');
    expect(document.querySelector('[aria-label="釘選"]')).not.toBeNull();
    expect(document.querySelector('[aria-label="關閉"]')).not.toBeNull();

    await act(async () => { await i18n.changeLanguage("en"); });
    expect(document.querySelector('[role="dialog"]')).toBe(panel);
    expect(document.querySelector('[aria-label="Pin"]')).not.toBeNull();
    expect(document.querySelector('[aria-label="Close"]')).not.toBeNull();
    expect(panel?.textContent).toContain("Source title");
    expect(panel?.textContent).toContain("Source child");
  });
  ```

- [ ] **Step 3: Run RED**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/ui/BoundedProgress.test.tsx src/ui/overlays.test.tsx
  ```

  Expected: both English assertions fail while all existing focus/state tests
  remain green.

- [ ] **Step 4: Translate Drawer-owned controls**

  In `Drawer`, call `useTranslation("common")` and replace only the three
  labels:

  ```tsx
  const { t } = useTranslation("common");
  const pinLabel = pinned
    ? t(($) => $.actions.unpin)
    : t(($) => $.actions.pin);
  // ...
  <IconButton label={pinLabel} /* existing props unchanged */ />
  <IconButton label={t(($) => $.actions.close)} /* existing props unchanged */ />
  ```

  Do not translate `title`, `children`, or `footer` inside Drawer.

- [ ] **Step 5: Translate BoundedProgress-owned messages**

  Keep `formatElapsed`, status mapping, and props unchanged. Use one Common
  translator and explicit static selectors:

  ```tsx
  const { t } = useTranslation("common");
  const announcement = awaitingConfirmation
    ? t(($) => $.boundedProgress.awaitingConfirmation)
    : status === "succeeded"
      ? t(($) => $.boundedProgress.completedAnnouncement)
      : status === "interrupted"
        ? t(($) => $.boundedProgress.interruptedAnnouncement)
        : null;
  ```

  Render all values through exact selectors:

  ```tsx
  {errorTitle ?? t(($) => $.boundedProgress.failureTitle)}
  {errorDetail ?? t(($) => $.boundedProgress.failureDetail)}
  {t(($) => $.boundedProgress.overallElapsed, { duration: formatElapsed(overallElapsedMs) })}
  {t(($) => $.boundedProgress.stageElapsed, { duration: formatElapsed(stageElapsedMs) })}
  {t(($) => $.boundedProgress.stageBound, { duration: formatElapsed(stageBoundMs) })}
  {t(($) => $.boundedProgress.result, { destination: resultLabel })}
  ```

  Select navigation/cancellation copy with explicit conditionals. Use
  `t(($) => $.actions.stop)` for the button. Do not build a selector from a
  status string.

- [ ] **Step 6: Run GREEN, focus, and type gates**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/ui/BoundedProgress.test.tsx src/ui/overlays.test.tsx
  npm run typecheck --workspace apps/arkscope-web
  ```

  Expected: existing `22` nodes plus exactly `2` additions, all green.

- [ ] **Step 7: Commit**

  ```bash
  git add apps/arkscope-web/src/ui/Drawer.tsx \
    apps/arkscope-web/src/ui/BoundedProgress.tsx \
    apps/arkscope-web/src/ui/overlays.test.tsx \
    apps/arkscope-web/src/ui/BoundedProgress.test.tsx
  git commit -m "feat: localize shared shell primitives"
  ```

---

## Task 3: Localize Navigation and App Shell Chrome

**Files:**
- Create: `apps/arkscope-web/src/shell/shellLabels.ts`
- Create: `apps/arkscope-web/src/shell/shellLabels.test.ts`
- Modify: `apps/arkscope-web/src/shell/navigation.ts`
- Modify: `apps/arkscope-web/src/shell/navigation.test.ts`
- Modify: `apps/arkscope-web/src/shell/ShellNavigation.tsx`
- Modify: `apps/arkscope-web/src/shell/ShellNavigation.test.tsx`
- Modify: `apps/arkscope-web/src/App.tsx`
- Modify: `apps/arkscope-web/src/AppShell.test.tsx`

- [ ] **Step 1: Write RED tests for semantic navigation authority**

  Evolve the existing `publishes the approved four workflow groups in
  canonical order` node so it expects IDs and views, not labels:

  ```ts
  expect(SHELL_NAV_GROUPS.map((group) => [
    group.id,
    group.items.map((item) => item.view),
  ])).toEqual([
    ["explore", ["Home", "Watchlist", "Universe", "News"]],
    ["research", ["Research"]],
    ["monitor", ["Holdings"]],
    ["system", ["System", "Settings"]],
  ]);
  ```

  Create `shellLabels.test.ts` with fresh fixed translators and the two named
  nodes. Assert the complete group and view arrays in both locales, exactly as
  listed in the resource inventory.

- [ ] **Step 2: Write RED component/integration tests**

  Add the English ShellNavigation node:

  ```tsx
  await act(async () => { await i18n.changeLanguage("en"); });
  const { host } = await renderNavigation();
  expect(Array.from(host.querySelectorAll("[data-shell-nav-group]"), (node) => node.textContent))
    .toEqual(["Explore", "Research", "Monitor", "System"]);
  expect(Array.from(host.querySelectorAll("button"), (node) => node.textContent?.trim()))
    .toEqual(["Home", "Watchlist", "Universe", "News", "AI Research", "Holdings", "System / Health", "Settings"]);
  ```

  Add two App nodes before implementation:

  1. stub overlay `matchMedia`, switch to English before render, assert menu
     `Open navigation`, Drawer title `Navigation`, and both nav accessible names
     `Primary navigation`;
  2. navigate to `AI 研究`, switch locale to English, and prove the same Research
     surface node remains mounted while current nav/context become
     `AI Research`.

- [ ] **Step 3: Run RED**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/shell/navigation.test.ts \
    src/shell/shellLabels.test.ts \
    src/shell/ShellNavigation.test.tsx \
    src/AppShell.test.tsx
  ```

  Expected: missing semantic IDs/helper plus untranslated English UI fail.

- [ ] **Step 4: Remove source-language labels from navigation data**

  Define:

  ```ts
  export type ShellNavGroupId = "explore" | "research" | "monitor" | "system";

  export interface ShellNavItem {
    view: ShellView;
    icon: ShellNavIcon;
  }

  export interface ShellNavGroup {
    id: ShellNavGroupId;
    items: readonly ShellNavItem[];
  }
  ```

  Rebuild `SHELL_NAV_GROUPS` with the exact IDs/views/icons and no `label`
  property. Remove the old `shellViewLabel()` from this file.

- [ ] **Step 5: Add the single typed label seam**

  `shellLabels.ts` contains exhaustive switches and no dynamic key:

  ```ts
  import type { TFunction } from "i18next";
  import type { ShellNavGroupId, ShellView } from "./navigation";

  type ShellT = TFunction<"shell">;

  export function shellNavGroupLabel(id: ShellNavGroupId, t: ShellT): string {
    switch (id) {
      case "explore": return t(($) => $.navigation.groups.explore);
      case "research": return t(($) => $.navigation.groups.research);
      case "monitor": return t(($) => $.navigation.groups.monitor);
      case "system": return t(($) => $.navigation.groups.system);
    }
  }

  export function shellViewLabel(view: ShellView, t: ShellT): string {
    switch (view) {
      case "Home": return t(($) => $.navigation.views.home);
      case "Watchlist": return t(($) => $.navigation.views.watchlist);
      case "Universe": return t(($) => $.navigation.views.universe);
      case "News": return t(($) => $.navigation.views.news);
      case "Research": return t(($) => $.navigation.views.research);
      case "Holdings": return t(($) => $.navigation.views.holdings);
      case "System": return t(($) => $.navigation.views.system);
      case "Settings": return t(($) => $.navigation.views.settings);
    }
  }
  ```

  TypeScript's closed unions provide exhaustiveness; do not add a string-key
  fallback.

- [ ] **Step 6: Wire ShellNavigation**

  Use `useTranslation("shell")`, `group.id` as key, and the two label helpers.
  Preserve button structure, order, icons, `aria-current`, and callbacks.

- [ ] **Step 7: Wire App-owned labels and context**

  Use one Shell translator in `App`:

  ```tsx
  const { t } = useTranslation("shell");
  // ...
  contextLabel={detail?.ticker ?? shellViewLabel(view, t)}
  // ...
  label={t(($) => $.navigation.openDrawer)}
  // ...
  aria-label={t(($) => $.navigation.primaryLabel)}
  // ...
  title={t(($) => $.navigation.drawerTitle)}
  ```

  Both persistent and Drawer nav accessible names use the same static selector.
  Do not move selected view/detail/navigation state.

- [ ] **Step 8: Run GREEN and exact structure tests**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/shell/navigation.test.ts \
    src/shell/shellLabels.test.ts \
    src/shell/ShellNavigation.test.tsx \
    src/AppShell.test.tsx
  npm run typecheck --workspace apps/arkscope-web
  ```

  Expected additions: shell labels `2`, ShellNavigation `1`, AppShell `2`.

- [ ] **Step 9: Commit**

  ```bash
  git add apps/arkscope-web/src/App.tsx \
    apps/arkscope-web/src/AppShell.test.tsx \
    apps/arkscope-web/src/shell/navigation.ts \
    apps/arkscope-web/src/shell/navigation.test.ts \
    apps/arkscope-web/src/shell/shellLabels.ts \
    apps/arkscope-web/src/shell/shellLabels.test.ts \
    apps/arkscope-web/src/shell/ShellNavigation.tsx \
    apps/arkscope-web/src/shell/ShellNavigation.test.tsx
  git commit -m "feat: localize shell navigation"
  ```

---

## Task 4: Localize Topbar Health and Developer Diagnostics

**Files:**
- Modify: `apps/arkscope-web/src/shell/ShellTopBar.tsx`
- Modify: `apps/arkscope-web/src/shell/ShellTopBar.test.tsx`

- [ ] **Step 1: Write the failing English/sanitization test**

  Add the named node. Switch to English, render error status with Developer Mode,
  and assert:

  ```ts
  expect(host.querySelector("[data-testid='shell-health']")?.textContent)
    .toContain("Sidecar unavailable");
  expect(diagnostics?.getAttribute("aria-label")).toBe("Developer diagnostics");
  expect(diagnostics?.textContent).toContain(`API ${DIAGNOSTICS.apiBase}`);
  expect(diagnostics?.textContent).toContain("Tools 19");
  expect(diagnostics?.textContent).toContain(`Last status ${DIAGNOSTICS.lastStatusAt}`);
  expect(diagnostics?.textContent).toContain(`Card model ${DIAGNOSTICS.cardModel}`);
  expect(host.textContent).not.toContain("recognizable private sidecar exception");
  ```

- [ ] **Step 2: Run RED**

  ```bash
  npm test --workspace apps/arkscope-web -- --run src/shell/ShellTopBar.test.tsx
  ```

  Expected: English health copy fails.

- [ ] **Step 3: Replace topbar literals with static selectors**

  Call `useTranslation("shell")`. Map the three status kinds explicitly and
  render full diagnostic messages rather than assembling translated fragments:

  ```tsx
  t(($) => $.topbar.diagnostics.apiValue, {
    value: diagnosticValue(diagnostics.apiBase),
  })
  ```

  Repeat for tools/status/model. Keep the literal product identifier
  `<span>ArkScope</span>` for the reviewed allowlist. Never interpolate
  `status.message`.

- [ ] **Step 4: Run GREEN and existing node-stability tests**

  ```bash
  npm test --workspace apps/arkscope-web -- --run src/shell/ShellTopBar.test.tsx
  npm run typecheck --workspace apps/arkscope-web
  ```

  Expected: existing 11 nodes plus exactly 1 addition.

- [ ] **Step 5: Commit**

  ```bash
  git add apps/arkscope-web/src/shell/ShellTopBar.tsx \
    apps/arkscope-web/src/shell/ShellTopBar.test.tsx
  git commit -m "feat: localize shell top bar"
  ```

---

## Task 5: Localize Background Work Without Capturing Locale

**Files:**
- Modify: `apps/arkscope-web/src/shell/researchWork.ts`
- Modify: `apps/arkscope-web/src/shell/researchWork.test.tsx`
- Modify: `apps/arkscope-web/src/shell/BackgroundWorkIndicator.tsx`
- Modify: `apps/arkscope-web/src/shell/BackgroundWorkIndicator.test.tsx`
- Modify: `apps/arkscope-web/src/AppShell.test.tsx`

- [ ] **Step 1: Write RED registry semantics**

  Evolve the existing reconciliation node to expect `threadTitle: null` for a
  missing title. Add the named node proving an empty/whitespace title remains
  null, a later source title replaces it, and neither `AI 研究` nor
  `AI Research` appears in serialized registry/session storage.

- [ ] **Step 2: Write RED BackgroundWork English and live-fallback tests**

  Add the two named nodes:

  1. English with source title `MU source title`: assert `Running 1`,
     `Background work`, `AI Research running`, `AI Research conversation`,
     `Open conversation`, English dismissal accessible name, and unchanged
     source title.
  2. Missing title: open the Drawer in Chinese, capture the same row and dialog
     elements, switch to English, assert `AI 研究 -> AI Research`, generic copy
     changes, and both element identities plus work counts remain unchanged.

- [ ] **Step 3: Write RED App integration for an open work Drawer**

  Seed one running work item, open Background Work in Chinese, switch i18next to
  English, and assert the same dialog remains open with English title/trigger
  while the current Home surface remains mounted.

- [ ] **Step 4: Run RED**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/shell/researchWork.test.tsx \
    src/shell/BackgroundWorkIndicator.test.tsx \
    src/AppShell.test.tsx
  ```

  Expected: captured fallback and untranslated Background Work fail.

- [ ] **Step 5: Make missing title semantic in the registry**

  Change only the internal projection type/seam:

  ```ts
  export interface ResearchWorkItem {
    // existing fields
    threadTitle: string | null;
  }

  function normalizedTitle(
    value: string | null | undefined,
    previous?: string | null,
  ): string | null {
    const title = value?.trim();
    return title || previous || null;
  }
  ```

  Let `observeRun` accept `threadTitle?: string | null`. Remove
  `FALLBACK_THREAD_TITLE`. Do not change persisted identity shape or polling.

- [ ] **Step 6: Localize the Background Work presenter**

  Use `useTranslation("shell")` in the indicator and progress row. Keep explicit
  status mapping:

  ```ts
  function stageLabel(item: ResearchWorkItem, t: TFunction<"shell">): string {
    if (item.status === "queued") return t(($) => $.backgroundWork.stages.queued);
    if (item.status === "running") return t(($) => $.backgroundWork.stages.running);
    if (item.status === "succeeded") return t(($) => $.backgroundWork.stages.succeeded);
    if (item.status === "failed") return t(($) => $.backgroundWork.stages.failed);
    return t(($) => $.backgroundWork.stages.interrupted);
  }
  ```

  Use static selectors for counts, trigger aria-label, Drawer title/footer,
  dismissal label, open action, failure title/detail, and result destination.
  Render title as:

  ```tsx
  <strong>{item.threadTitle ?? shellViewLabel("Research", t)}</strong>
  ```

  Pass `t(($) => $.backgroundWork.resultDestination)` as the destination only;
  generic BoundedProgress adds `Result:`/`結果：`.

- [ ] **Step 7: Run GREEN and privacy tests**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/shell/researchWork.test.tsx \
    src/shell/BackgroundWorkIndicator.test.tsx \
    src/AppShell.test.tsx
  npm run typecheck --workspace apps/arkscope-web
  ```

  Expected additions: research registry `1`, BackgroundWork `2`, AppShell `1`.
  Existing planted private values remain absent.

- [ ] **Step 8: Commit**

  ```bash
  git add apps/arkscope-web/src/AppShell.test.tsx \
    apps/arkscope-web/src/shell/researchWork.ts \
    apps/arkscope-web/src/shell/researchWork.test.tsx \
    apps/arkscope-web/src/shell/BackgroundWorkIndicator.tsx \
    apps/arkscope-web/src/shell/BackgroundWorkIndicator.test.tsx
  git commit -m "feat: localize background research work"
  ```

---

## Task 6: Retire Shell Literal Debt and Lock Migrated Scope

**Files:**
- Modify: `apps/arkscope-web/scripts/i18n/visible-literal-debt.json`
- Modify: `apps/arkscope-web/scripts/i18n/visible-literal-allowlist.json`
- Modify: `apps/arkscope-web/scripts/i18n/migrated-scopes.json`
- Modify: `apps/arkscope-web/src/i18n/foundationBoundaries.test.ts`

- [ ] **Step 1: Write the failing manifest contract test**

  Add the named node. Parse all three manifests and assert exact scopes and the
  sole allowlist entry:

  ```ts
  expect(migrated.scopes).toEqual([
    "src/i18n/**",
    "src/main.tsx",
    "src/App.tsx",
    "src/shell/**",
    "src/ui/BoundedProgress.tsx",
    "src/ui/Drawer.tsx",
  ]);
  expect(allowlist.entries).toEqual([{
    file: "src/shell/ShellTopBar.tsx",
    kind: "jsx_text",
    literal: "ArkScope",
    count: 1,
    classification: "stable_identifier",
    reason: "ArkScope is the product name and is identical in every locale.",
  }]);
  ```

  Also parse each debt signature and assert none belongs to App, `shell/**`,
  Drawer, or BoundedProgress.

- [ ] **Step 2: Run RED**

  ```bash
  npm test --workspace apps/arkscope-web -- --run src/i18n/foundationBoundaries.test.ts
  ```

  Expected: scopes/allowlist still show I18N-0 state.

- [ ] **Step 3: Mechanically remove exactly 59 owned debt signatures**

  Use a one-off Node transform that parses each signature's first tuple value,
  filters the four exact ownership scopes, sorts no data, asserts removal count
  `59`, and rewrites with two-space indentation plus final newline. Do not run a
  repo-wide replacement or regenerate unrelated debt.

  The owned predicate is exactly:

  ```js
  const owned = (file) =>
    file === "src/App.tsx"
    || file.startsWith("src/shell/")
    || file === "src/ui/Drawer.tsx"
    || file === "src/ui/BoundedProgress.tsx";
  ```

- [ ] **Step 4: Add exact scope and allowlist manifests**

  Apply the arrays shown in Step 1 verbatim. No second identifier and no
  translatable sentence enters the allowlist.

- [ ] **Step 5: Run GREEN and scanner twice**

  ```bash
  npm test --workspace apps/arkscope-web -- --run src/i18n/foundationBoundaries.test.ts
  npm run check:i18n-literals --workspace apps/arkscope-web
  npm run check:i18n-literals --workspace apps/arkscope-web
  ```

  Expected scanner JSON both times:

  ```json
  {
    "candidateCount": 1649,
    "signatureCount": 1563,
    "debtSignatureCount": 1562,
    "allowlistCount": 1,
    "migratedScopes": [
      "src/App.tsx",
      "src/i18n/**",
      "src/main.tsx",
      "src/shell/**",
      "src/ui/BoundedProgress.tsx",
      "src/ui/Drawer.tsx"
    ]
  }
  ```

  Hash all three manifests before/after the second check; checks must be
  read-only.

- [ ] **Step 6: Run the exact focused ledger**

  Run the 12-file list and test set. Require `12 files / 108 tests`, exact
  `+15/-0`, and the distribution in this plan.

- [ ] **Step 7: Commit**

  ```bash
  git add apps/arkscope-web/scripts/i18n/visible-literal-debt.json \
    apps/arkscope-web/scripts/i18n/visible-literal-allowlist.json \
    apps/arkscope-web/scripts/i18n/migrated-scopes.json \
    apps/arkscope-web/src/i18n/foundationBoundaries.test.ts
  git commit -m "test: ratchet localized shell coverage"
  ```

---

## Task 7: Canonical Verification and Both-Locale Runtime Gate

**Files:**
- Modify: `apps/arkscope-web/src/shell/shell.css`
- Modify: `apps/arkscope-web/src/shell/ShellCss.test.ts`
- Update the implementation ledger in this plan.

- [ ] **Step 0: Implement the reviewed topbar exception RED-first**

  Add the named `ShellCss.test.ts` node and require it to fail because
  `.shell-topbar-primary` lacks `flex-wrap: wrap`. Then add exactly that one
  declaration to `shell.css` and require the focused CSS file to pass all seven
  nodes. Do not change another selector, declaration, label, minimum width,
  breakpoint, token, or font size.

- [ ] **Step 1: Run exact focused tests**

  ```bash
  npm test --workspace apps/arkscope-web -- --run \
    src/AppShell.test.tsx \
    src/shell/navigation.test.ts \
    src/shell/shellLabels.test.ts \
    src/shell/ShellNavigation.test.tsx \
    src/shell/ShellTopBar.test.tsx \
    src/shell/BackgroundWorkIndicator.test.tsx \
    src/shell/researchWork.test.tsx \
    src/shell/ShellCss.test.ts \
    src/ui/BoundedProgress.test.tsx \
    src/ui/overlays.test.tsx \
    src/i18n/resources.test.ts \
    src/i18n/foundationBoundaries.test.ts
  ```

  Expected: `12 files / 108 tests`.

- [ ] **Step 2: Run full frontend gates**

  ```bash
  npm test --workspace apps/arkscope-web -- --run
  npm run typecheck --workspace apps/arkscope-web
  npm run build --workspace apps/arkscope-web
  npm run check:i18n-literals --workspace apps/arkscope-web
  ```

  Expected: `74 files / 695 tests`; clean typecheck; successful build with only
  the existing chunk-size warning; exact scanner totals from Task 6.

- [ ] **Step 3: Prove exact node accounting**

  Compare sorted `vitest list` output from virgin archives of `ac57858` and
  product tip, using the same root `node_modules`. Require exact `+15/-0`, no
  rename, and the per-file distribution in the ledger.

- [ ] **Step 4: Prove constructive backend/API/CSS A/B**

  Run byte-identity gates against `ac57858`:

  ```bash
  git diff --exit-code ac57858 -- src data_sources tests
  git diff --exit-code ac57858 -- apps/arkscope-web/src/api.ts
  git diff --exit-code ac57858 -- apps/arkscope-web/src/styles.css \
    apps/arkscope-web/src/ui/primitives.css \
    apps/arkscope-web/src/settings/settings.css
  git diff ac57858 -- apps/arkscope-web/src/shell/shell.css
  git diff --exit-code ac57858 -- apps/arkscope-desktop extensions
  ```

  The `shell.css` diff must contain exactly the reviewed one-line
  `flex-wrap: wrap` declaration inside `.shell-topbar-primary`; every other CSS
  byte remains identical.

  Because both backend archives are byte-identical, full pytest A/B is
  constructively equal and must not spend ten minutes proving identical trees.
  Backend collect remains `4569`; no backend test is added or removed.

- [ ] **Step 5: Run static/privacy/scope ratchets**

  Prove:

  - changed product files exactly match the reviewed file map;
  - no `t()` call uses a string/template/dynamic variable key;
  - no locale selector/autonym/planned locale control renders;
  - no source-language labels remain in migrated scopes except exact ArkScope;
  - `formatElapsed()` diff is empty;
  - `StatusState.error.message`, Research question/error/answer, credential ID,
    and token usage do not appear in Shell DOM;
  - no new `window.confirm`, breakpoint literal, `@media`, raw exception, or
    undefined shared class;
  - no resource contains a ticker, model, API base, run ID, or planted private
    fixture value; and
  - all non-owned surfaces and common primitives are byte-identical.

- [ ] **Step 6: Run isolated both-locale browser gate**

  Use a temporary profile DB and isolated ports (recommended
  API `8424`, Vite `8434`, CDP `9226`). Do not use the production profile,
  browser storage, or normal desktop process.

  Seed each locale through the reviewed locale PUT against its temporary
  sidecar, then use a fresh browser context. For the matching first-paint cache,
  write the versioned cache only after that temporary PUT succeeds; do not
  insert profile rows directly or seed cache without authority. Seed one
  terminal Research run and a matching session-scoped observed identity so
  Background Work is deterministic. Run separate `zh-Hant` and `en` profiles.
  At each locale verify all six canonical viewports:

  - `1440x900`, `1024x768`, `961x768`, `960x768`, `959x768`, `390x844`;
  - four group labels and eight destination labels are exact;
  - topbar identity/context/health are coherent;
  - Developer Mode diagnostic labels translate while values remain exact;
  - at `961` the persistent navigation is unique; at `960` and below only the
    menu/Drawer copy exists, with localized accessible names and focus return;
  - Background Work trigger/Drawer/stage/result/dismiss/open labels are exact;
  - source thread title, run ID, ticker, model, and diagnostic values remain
    unchanged;
  - no raw key, mixed-locale generic chrome, selector, overlap, clipping,
    horizontal overflow, blank panel, or console exception;
  - page/component font sizes match the baseline; and
  - screenshots and DOM assertions identify locale and viewport.

  Also record leaf-control row positions and actual primary/topbar heights.
  At `390px`, Traditional Chinese must remain one row and English must place
  health/work controls on a second row. At all canonical widths `>=768px`, both
  locales must remain one row. Do not turn any measured height delta into a
  magic acceptance constant.

  Do not manufacture production data. Remove isolated DBs/profiles/screenshots
  only after evidence is summarized in the ledger.

- [ ] **Step 7: Run no-PG and final worktree checks**

  ```bash
  python -m src.smoke.pg_unreachable_e2e
  git diff --check
  git status --short
  git log --oneline --decorate -12
  ```

  Require `ok:true`, `pg_attempts:[]`, no staged build/browser/DB artifacts,
  and no untracked secret-bearing evidence.

---

## Task 8: Record Review-Ready Evidence and Stop

**Files:**
- Modify: `docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md`
- Modify: `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`

- [ ] **Step 1: Fill the implementation ledger**

  Record clearance/base/product hashes, every RED/GREEN commit, exact resource
  paths/counts, test comm output, scanner totals/hashes, immutable gates,
  no-PG result, browser matrix, process cleanup, and any reviewed deviation.

- [ ] **Step 2: Mark implementation review-ready, not LIVE**

  Decision/map must say I18N-1 implementation is complete for independent
  review. I18N-2 remains queued and is not opened. The public selector remains
  absent.

- [ ] **Step 3: Commit evidence docs**

  ```bash
  git add docs/superpowers/plans/2026-07-20-i18n-1-shell-common-ui.md \
    docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md \
    docs/design/PROJECT_PRIORITY_MAP.md
  git commit -m "docs: record i18n shell verification"
  ```

- [ ] **Step 4: Stop for independent implementation review**

  Do not merge, expose the selector, open I18N-2, or sync Design Kit before
  independent review GREEN and explicit user merge approval.

---

## Independent Reviewer Focus

1. exact `common +17` / `shell +37` key parity and non-empty values;
2. no source-language label remains in navigation structure;
3. static selector allowlists are exhaustive and no dynamic key exists;
4. current view/ticker/work/open-Drawer state survives locale rerender;
5. registry stores `null`, not localized fallback copy;
6. source thread title and stable identifiers remain unchanged;
7. Traditional Chinese parity plus the one explicit result-copy correction;
8. topbar raw error/privacy boundary and Developer diagnostic interpolation;
9. Drawer focus/inline/overlay semantics remain unchanged;
10. BoundedProgress semantics, formatter output, and domain mapping remain
    unchanged;
11. exact `+15/-0`, `74/695`, and `12/108` ledgers, including the named
    `ShellCss.test.ts` node;
12. scanner exact `1649/1563/1562/1`, with only ArkScope allowlisted;
13. backend/API/non-owned-surface byte identity plus the exact one-line
    `.shell-topbar-primary` CSS exception;
14. no selector/autonym/planned locale affordance;
15. both-locale six-viewport layout/focus/accessible-name evidence; and
16. no production DB/browser/process mutation.

---

## Stop Conditions

Stop and return to review if:

1. any CSS beyond the reviewed `.shell-topbar-primary { flex-wrap: wrap; }`
   declaration, or any breakpoint, token, IA, or font-size change appears
   necessary;
2. a backend/API/DTO/schema/store change appears necessary;
3. a non-owned surface or primitive must change;
4. a public locale selector/autonym becomes reachable;
5. a dynamic key, alternate translation style, detector, loader, Suspense, or
   formatter migration appears;
6. resource inventory differs from exact `+17/+37`;
7. any value is empty or locale key sets differ;
8. a source/user value is copied into resources;
9. `ArkScope` cannot remain the sole allowlist entry;
10. migrated scope contains any non-allowlisted scanner candidate;
11. scanner totals differ without an explained scanner defect or reviewed
    resource/scope change;
12. a locale change remounts a selected surface, closes a Drawer, loses work,
    or changes source content;
13. English overflows/clips at any canonical viewport;
14. raw error/private Research fields enter the Shell;
15. test collection differs from exact `+15/-0` or any node is renamed/removed;
16. backend/API/protected-tree byte identity fails, or the Shell CSS diff is
    anything other than the reviewed one-line declaration;
17. no-PG smoke records an attempt; or
18. verification would require production DB or browser-profile mutation.

---

## Post-Review Merge Closeout (Not Part of Implementation Clearance)

Only after independent implementation GREEN and explicit user merge approval:

1. restore the main checkout to clean tracked state;
2. fast-forward merge the reviewed branch;
3. rerun focused `12/108`, full `74/695`, typecheck, build, scanner, no-PG,
   immutable gates, and merged-tree both-locale startup smoke;
4. restart the normal desktop once and verify the default `zh-Hant` Shell is
   behaviorally unchanged; no production locale write is required;
5. mark I18N-1 LIVE in plan/decision/map and promote I18N-2 Settings as the
   single NEXT unit;
6. keep the public selector absent;
7. do not sync Design Kit because this remains partial localization;
8. update memory/decision log; and
9. remove the worktree/branch only after closeout evidence is retained.
