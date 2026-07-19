# P2.8 Canonical Shell and Interaction Design

> **Status: ADOPTED DESIGN; WRITTEN SPEC REVIEW APPROVED, 2026-07-12.**
> This document is the implementation authority for ArkScope shell structure,
> interaction primitives, cross-surface navigation, and the bounded UI repair
> sequence. The Claude Design companion was synchronized after approval; each
> implementation slice still requires its own separately reviewed plan.
> **Settings IA amendment, 2026-07-19:** Slice 4.1 replaces the rejected
> all-groups single-page composition. Its written review is approved at
> `2026-07-19-p2-8-slice-4-1-settings-navigation-correction-design.md`.

## 1. Purpose and Authority

ArkScope has working product surfaces, but they have grown through independent
slices. The result is functional fragmentation rather than one coherent
workbench: some pages use mature compact components, some use browser-default
controls, some reserve space for empty panels, and some expose development
diagnostics as permanent product chrome.

P2.8 establishes one canonical shell and interaction contract before Notes,
Alerts, and Track B add more surfaces.

Authority order for this domain:

1. This spec owns shell information architecture, shared interaction semantics,
   responsive behavior, and UI state presentation.
2. Domain specs continue to own domain data and behavior. For example,
   `ARKSCOPE_WORKBENCH_PRODUCT_SPEC.md` owns the EvidencePacket boundary,
   Models-UX owns model eligibility semantics, and the Investment Skills/Profile
   design owns approved-profile prompt behavior.
3. `DESKTOP_APP_VISION_DRAFT.md` remains an intent source, not an implementation
   authority.
4. The external Claude Design project is a synchronized visual implementation
   companion. After this spec is approved, its tokens, components, voice, and
   screen kit must be updated to conform. If it conflicts with this spec, this
   spec wins.

## 2. Grounded Current State

The audit used the merged desktop/web app with real local data at 1440x900 and
code reads from the same revision.

### 2.1 Shell

- `apps/arkscope-web/src/App.tsx` renders planned Alerts and Notes as disabled
  navigation buttons. Their disabled appearance is indistinguishable in kind
  from controls that are temporarily unavailable.
- The top bar permanently displays `sidecar ok`, registered tool count, raw
  `apiBase`, and last refresh time.
- The global right rail is a placeholder for future assistant/summary content;
  opening it reserves width without delivering an active workflow.
- System and Settings repeat portions of model, credential, and health status.

### 2.2 Surface fragmentation

Current file sizes are evidence of concentrated ownership, not a reason for a
blind rewrite:

| File | Lines |
| --- | ---: |
| `Settings.tsx` | 3,839 |
| `styles.css` | 2,549 |
| `api.ts` | 2,163 |
| `Research.tsx` | 873 |
| `Watchlist.tsx` | 672 |
| `TickerDetail.tsx` | 625 |
| `Holdings.tsx` | 584 |

`Holdings.tsx` consumes `section-band`, `section-head`, `btn-primary`,
`btn-secondary`, `table-wrap`, `inline-form`, `status-grid`, and `metric`, but
none of those selectors exists in `styles.css`. `InvestorProfilePanel.tsx` has
the same defect for `investor-profile-panel`, `ip-grid`, `ip-chip`,
`ip-calibration`, `ip-actions`, and `ip-guardrail`. Both surfaces therefore
fall back toward browser-default controls and spacing.

### 2.3 Research

- `Research.tsx` and `styles.css` implement a fixed
  `220px / flexible / 320px` three-column grid.
- The Evidence/tool trace column consumes width even when empty.
- Thread history has delete but no rename/archive UI, even though the thread
  table already stores title, created/updated timestamps, and `archived_at`.
- Research execution is already server-owned: switching threads or leaving the
  surface detaches polling without cancellation; explicit Stop cancels.
- The pending bubble says only thinking/generating. It does not show stage time,
  configured upper bound, or the over-bound confirmation window.

### 2.4 Settings and Investor Profile

- Settings has seven enabled technical categories plus disabled historical
  categories. The top-level title remains model-oriented when another category
  is selected.
- Providers and Models already have a correct ownership split: Providers owns
  login/credential discovery; Models owns task routing after availability is
  known. P2.8 must preserve that distinction.
- Investor Profile currently presents abstract fields and bare 1-10 values
  before explaining how ArkScope understands the user.
- Track A/A.5 already supplies the correct data boundary: append-only calibration
  messages, inert proposals, explicit approve/reject, and approved-profile-only
  prompt injection.

### 2.5 Other audit findings

- Watchlist renders the complete sorted row set and currently has no pagination
  or virtualization. A live profile produced 148 rows with dense per-row actions.
- Ticker Detail still has a chart placeholder. Its Notes tab is a small
  per-ticker add/delete seed, not Notes V1.
- Saved reports have a local store, read API, and `saved_report_id` linkage from
  cards, but no global GUI list/detail entry. They are an invisible durable
  entity.
- Production frontend code has five `window.confirm` ownership areas:
  Watchlist, Universe, Holdings, Research, and Settings.
- Generic route errors still expose strings derived directly from exceptions,
  including non-typed card synthesis/translation failures.
- Responsive behavior currently uses independent 760px, 900px, and 1100px
  media-query decisions rather than one shell breakpoint authority.

## 3. Goals

1. Make ArkScope feel like one compact professional workbench without turning
   it into a decorative redesign.
2. Give future Notes, Alerts, and Track B surfaces stable primitives and
   navigation rules.
3. Make long-running AI work truthful about ownership, elapsed time, bounds,
   cancellation, and result location.
4. Preserve domain semantics already made honest by Models-UX, provider health,
   market coverage, and the EvidencePacket contract.
5. Decompose implementation into reviewable workflow slices with explicit
   migration and verification gates.

## 4. Non-Goals

- No one-branch visual rewrite or whole-app component conversion.
- No light-theme implementation. The current dark theme remains authoritative.
- No Notes, Alerts, recurring research, Research collections, or Track B
  implementation in this design slice.
- No automatic LLM classification of research history.
- No Reference store implementation before Notes V1 owns its exact schema and
  deletion policy.
- No server-owned fixed-task conversion inside the shell slice.
- No implementation of the Intraday Behavior Layer in P2.8.
- No wholesale `api.ts` or `styles.css` refactor unrelated to the first consumer
  of a primitive.

## 5. Product and Visual Principles

### 5.1 Compact progressive disclosure

ArkScope uses compact density everywhere. Operational surfaces such as
Holdings, Watchlist, Research, and News prioritize scanning, comparison, and
repeated action. Understanding surfaces such as Settings and calibration add
summaries, rationale, scenario anchors, and disclosure, but do not use oversized
cards or large decorative whitespace.

Consistency comes from shared typography, controls, spacing, state semantics,
and interaction contracts. It does not require every surface to present the
same amount of information.

### 5.2 Framing

- Page sections are full-width bands or unframed layouts with separators.
- Cards are reserved for repeated entities, modals, and genuinely framed tools.
- Cards are not nested inside cards.
- Display-scale headings are not used inside compact panels.
- Controls keep stable dimensions across loading, error, hover, and dynamic
  label states.
- General framed-component radius uses a reviewed token scale capped at 8px.
  Circular indicators and semantic pills are explicit exceptions.

### 5.3 Terminology

Visible names use user tasks and outcomes, not internal module names. Existing
canonical EN/zh terms and mixed-language policy live in the single authority
[`ARKSCOPE_TERMINOLOGY.md`](../../design/ARKSCOPE_TERMINOLOGY.md). Navigation
groups, Settings groups, and other high-frequency labels require a terminology
pass before their implementation plan is approved. Domain specs link to that
authority rather than copying shared terminology tables.

## 6. App Shell and Navigation

### 6.1 Top bar

The normal top bar contains:

- ArkScope identity;
- current page/context;
- actionable health state;
- active background-work count when nonzero;
- only the contextual task/model information needed by the current workflow.

Normal mode does not show ports, `apiBase`, raw tool count, or routine polling
timestamps. System/Settings may enable Developer Mode. Developer Mode can then
expose those diagnostics in a secondary top-bar row or diagnostic disclosure.

### 6.2 Main navigation

Final order is reserved by this spec; unfinished items are not rendered.

| Group | Items |
| --- | --- |
| Explore / 探索 | Home / 工作台; Watchlist / 自選股; Universe / 全部標的; News / 新聞·事件 |
| Research / 研究 | AI Research / AI 研究; Notes / 研究筆記 |
| Monitor / 追蹤 | Holdings / 持倉; Alerts / 告警 |
| System / 系統 | System / Health; Settings / 設定 |

Group labels are low-emphasis, noninteractive, and non-focusable. `disabled`
means the current state prevents an otherwise implemented action. It never
means “planned.” If a roadmap surface is later desired, it must be a separate
governed, noninteractive primitive whose membership is limited to adopted specs
in the operating queue.

### 6.3 Main content and contextual panels

Every surface uses one `PageHeader` contract: title, compact status/context,
primary command, and optional secondary commands. The title must describe the
visible content.

The global placeholder right rail is removed. Contextual detail uses Drawer.
Empty panels never reserve main-content width.

## 7. Shared Interaction Primitives

### 7.1 Core set

The shared set includes:

- `PageHeader`, compact toolbar, search, filter, and segmented control;
- text input, textarea, select, checkbox/toggle, numeric input, and slider where
  numeric position is meaningful;
- command button, icon button, menu, and disclosure;
- automatic-activation `Tabs` where a small stable set switches peer views;
- `StatusBadge`, inline alert, empty state, loading state, and typed error state;
- `DataTable`, row-action menu, inline editor, archived/closed filter;
- `ConfirmDialog`;
- `Drawer`;
- `BoundedProgress`;
- `BackgroundWorkIndicator` and `BackgroundWorkRow`;
- `NavigationTarget` resolution;
- persistent `Reference` contract.

An implementation rule applies to every slice: a primitive must land no later
than its first consumer. A primitive slice implements only the depth required by
the current consumer; unused variants are not built preemptively.

### 7.2 Drawer

Drawer has two modes:

- `transient`: temporary detail, diagnostics, or task list;
- `pinnable`: contextual information that users compare with the main content.

The first shell consumer needs only transient Drawer. Research later adds the
pinnable extension for Evidence. Opening manages focus; closing returns focus to
the trigger. Below the shell breakpoint, all drawers are overlays.

### 7.3 BoundedProgress

`BoundedProgress` represents real long-running work without inventing a linear
percentage.

It displays:

- current stage;
- overall elapsed time;
- stage elapsed time and that stage’s configured bound, when known;
- whether the work continues after navigation;
- whether explicit cancellation is supported;
- the durable result destination.

Bounds belong to stages. For example, `model_timeout_s` bounds model execution,
not local evidence gathering or final persistence. Overall elapsed time must not
be compared directly with a model-stage bound.

When stage elapsed reaches the configured bound while the client is in its
server-confirmation grace window, the component enters an explicit state:

> 已達上界，等待伺服器確認 / Bound reached; waiting for server confirmation.

It does not show an unexplained `930s / 900s` progress value. A terminal timeout
uses a typed error state.

Long-running ArkScope work has a target ownership rule: leaving a page, closing
a drawer, or detaching a client does not cancel work. Explicit Stop or an
unrecoverable process/external failure ends it. Current fixed card tasks do not
yet meet the durable tracking half of this contract; Section 12 records the
phased membership.

### 7.4 Global work indicator

`BackgroundWorkRow` is defined here as a compact `BoundedProgress` summary plus
one exact `NavigationTarget`. The top bar shows only running/attention counts.
Its transient Drawer shows active, failed, interrupted, and newly completed
work.

The authoritative result remains in its owning surface. The global row never
copies answer/card/report content. A completion can be opened now or later.
Viewed/dismissed successful rows may fade out; failed/interrupted rows remain
until handled.

### 7.5 DataTable and confirmation

DataTable standardizes the behavioral contract already proven in Holdings:

- compact scan rows;
- row-action menu;
- inline editing where appropriate;
- soft close/archive;
- optional closed/archived view;
- stable user-owned fields across synchronized refreshes.

The present Holdings implementation is not the authority: browser-default
styles and `window.confirm` are repair targets. `ConfirmDialog` owns destructive
and high-impact confirmation, including consequence text and inbound-reference
warnings when applicable.

### 7.6 Status semantics

The common product-state set is:

`loading`, `empty`, `ready`, `running`, `partial/stale`, `blocked`, `failed`, and
`interrupted`.

Domain labels remain precise. Each consuming slice must publish a mapping from
its domain vocabulary to these states. Existing domain maps such as
`MODEL_UX_LABELS`, provider health labels, coverage labels, and scheduler labels
remain the semantic source; the primitive standardizes presentation rather than
re-translating their meaning.

## 8. AI Research Workspace

### 8.1 Layout

- The conversation is the only permanent primary region.
- The composer remains fixed at the bottom of that region.
- “New research” is a PageHeader/toolbar command and does not depend on opening
  history.
- History is a transient on-demand Drawer.
- Evidence is an on-demand Drawer that can be pinned on wide screens.

On narrow screens, history and Evidence are mutually overlaying drawers. An
empty Evidence state never reserves width.

### 8.2 History

Each thread row displays title, ticker/topic metadata when present, created
date, last-updated date, and execution state.

V1 automatic organization is deterministic only:

- ticker;
- date;
- run state;
- search/filter over stored metadata.

LLM topic grouping is not part of V1. User collections and manual
reclassification are a separate data-model slice. High-frequency recurring
questions become saved research templates/scheduled work later; they are not a
classification feature.

Initial title generation may continue to truncate the first question, but the
surface must add rename. Archive hides the thread from the normal list while
preserving content and references. Permanent deletion uses ConfirmDialog.

### 8.3 Per-run model selection

Research may change provider/model between turns because the backend replays
thread messages rather than maintaining a provider-bound response-id chain.
History is intent context; time-sensitive facts are re-fetched through tools.

Every run selects the complete `(provider, model, effort)` tuple. The selector
uses the same effective picker authority as Models-UX: capability, active
credential entitlement, and auth/task executability. It displays auth/billing
context, including whether the run consumes subscription quota or API-key usage.
There is no second model catalog and no silent provider/model/effort fallback.

Default precedence is intentionally asymmetric:

1. An existing thread uses its last successful tuple for continuity.
2. A new thread uses the user’s most recent explicit selection.
3. With no prior selection, use the Settings route.
4. If a saved choice is no longer executable, require a new choice.

`research_runs` already persists the tuple. Implementation needs a query for the
latest successful tuple, not a new storage field.

### 8.4 Run interaction

While a run is active, the composer remains editable as a local draft. Send is
disabled; V1 does not silently queue a second request. Explicit Stop remains
available and maps to `interrupted/cancelled` domain semantics.

The Evidence Drawer has two user-facing sections:

- Evidence: claims, sources, citations, and evidence records;
- Run details: tools, elapsed time, token totals, applied stance/skills, and
  other user-relevant trace.

Raw replay events, internal IDs, and low-level diagnostics are Developer Mode
content.

### 8.5 Background membership

The global work Drawer V1 includes server-owned Research runs only. Fixed card
generation/translation shows page-local BoundedProgress while the page is
attached; leaving currently loses tracking even if the server later writes the
result to the card list. Those tasks join the global work Drawer only after the
separate server-owned fixed-task run slice lands.

## 9. Settings Information Architecture

### 9.1 Workflow tabs with a scoped directory

Settings remains one application view and does not create a nested route for
every category. Its content is composed as three workflow tabs: AI and Models,
Personalization, and Data and Sync.

- Only the active workflow group is mounted.
- A compact left rail lists anchors for the active group; at and below the
  shell breakpoint the same directory is a transient Drawer.
- The search control is explicitly global. Empty search lists the active group;
  a non-empty search crosses all groups and groups its results by workflow.
- Selecting a cross-group result switches the workflow, waits for mount, then
  scrolls/focuses the exact stable anchor.
- `NavigationTarget` has precedence over the remembered group and follows the
  same mount-before-focus contract.
- Manual tab selection clears any pending search/navigation anchor.
- The last active group is remembered fail-closed. The retired collapse-state
  preference is never read or migrated.

Code ownership remains separate from visual routing. Settings stays decomposed
into section modules. The exact preference, focus, FRED/Macro ownership, and
verification contracts are owned by the Slice 4.1 addendum
`2026-07-19-p2-8-slice-4-1-settings-navigation-correction-design.md`.

### 9.2 Grouping and migration map

Group names follow the canonical terminology authority; their ownership is
locked.

| Current owner/surface | Target group | Target subsection/ruling |
| --- | --- | --- |
| `ModelRoutingSection` | AI and Models | Task routing; keep Models-UX semantics |
| `FixedTaskRuntimeSection` | AI and Models | Fixed card/translation limits, adjacent to those routes |
| `ResearchRuntimeSection` | AI and Models | AI Research execution limits |
| `ProviderSection` | AI and Models | Login, active credentials, discovery, and tests; remains distinct from routing |
| Model route import/export | AI and Models | Advanced disclosure, not global page commands |
| `InvestorProfilePanel` | Personalization | Profile summary, calibration, approved settings |
| `DataStorageSection` | Data and Sync | Local market storage/read authority |
| `NewsStorageSection` | Data and Sync | News ingestion/write route |
| `MacroStorageSection` | Data and Sync | Detailed FRED/Macro snapshot and stored coverage; no Calendar feature claim |
| `DataSourcesSection` | Data and Sync | Provider health, schedules, SA telemetry/setup |
| `AppRecordsSection` (disabled) | App and Advanced | Historical migration disclosure only; not normal navigation |
| Permissions (disabled) | App and Advanced | Render only when an implemented permission surface exists |
| Developer Mode | App and Advanced | Shell diagnostics toggle |
| System / Health | Separate System surface | Live diagnostics; do not duplicate normal Settings controls |

Provider login/discovery and model task routing may share the same semantic
group, but they remain separate subsections and authorities.

### 9.3 Mechanical decomposition

Several large Settings sections already have component boundaries and focused
tests. File extraction is a pure-move stage before behavioral IA changes. It
uses strict A/B accounting: failure sets and passed counts remain equal, with no
test additions/removals inside the move commit.

## 10. Investor Profile and Calibration

### 10.1 Independent facts and display priority

The underlying facts are independent:

- an approved profile may or may not exist;
- a draft proposal may or may not be pending.

Display priority is deterministic:

1. A pending proposal always renders the proposal-review state, whether or not
   an approved profile exists.
2. Without a pending proposal, an approved profile renders the summary state.
3. Without either, render first-time calibration/onboarding.

An unapproved proposal never enters Research or card prompts. During proposal
review, the currently approved profile remains active. Rejecting a proposal
discards that proposal but retains the append-only calibration journal and
allows another calibration session.

### 10.2 First-time calibration

First-time calibration uses a hybrid guided dialogue:

- a small deterministic set of practical scenarios;
- optional free-form description and real past observations;
- agent follow-up on ambiguity, contradictions, and missing capacity facts;
- a structured proposal with per-field rationale;
- explicit user edit/approve/reject.

The calibration agent asks and organizes. It does not give stock picks or
investment advice. Users who already understand their profile may skip directly
to detailed editing.

### 10.3 Summary and editing

The default profile surface answers:

- How does ArkScope currently understand me?
- What evidence/approved answers produced that understanding?
- What remains uncertain?
- Is stated risk appetite materially different from stated capacity?

The summary displays plain-language style/horizon, understanding confidence,
rationale, and mismatch warnings before raw values. All editing entries,
including direct edit, use qualitative labels and scenario anchors first; 1-10
values are secondary structured representations.

Current `risk_mismatch` continues to compare approved `risk_appetite` and
`risk_capacity` only. Profile-versus-holdings exposure is a future cross-domain
warning with a different name and contract.

### 10.4 Prompt boundary

Raw calibration text never enters Research/card prompts. Only an enabled,
approved structured profile may affect synthesis/chat context. Disabling
personalization preserves saved values but forces effective stance off and must
retain Track A’s byte-identical-off behavior.

## 11. Cross-Surface Navigation and Persistent References

### 11.1 NavigationTarget

`NavigationTarget` is a transient resolution contract: where a click goes now.
It supports at least:

- ticker;
- AI card;
- Research thread and run;
- Evidence;
- Note;
- Alert;
- report;
- exact Settings section/anchor.

Global work rows, status warnings, citations, and reference controls use the
same resolver rather than each surface inventing navigation state.

### 11.2 Reference

`Reference` is a persistent relationship with stable source and target IDs,
inbound lookup, and tombstone behavior. It is separate from NavigationTarget.

Notes V1 may reference Research, Evidence, cards, and reports. Reference display
uses a live join for current title/status so rename does not stale the note. A
stored label snapshot is fallback metadata only when the target is deleted or
unreadable.

Evidence IDs are packet-local (`E1`, `E2`, ...). Stable Evidence references use
a compound identity such as `(owner_type, owner_id, evidence_id)`, where owner
is the card/run/packet authority.

Archive preserves references. Permanent delete must not silently break them.
Tombstone behavior is the minimum. Notes V1 owns the choice between blocking
deletion and allowing an explicit confirmed delete with a tombstone.

### 11.3 Saved reports IA finding

Reports remain a named P2.8 finding. This spec does not add another navigation
item. Notes V1 must choose between:

- retaining per-card/per-ticker access; or
- exposing reports in a Research library while keeping report and note entities
  distinct.

## 12. Async Work, Errors, Time, and Responsive Behavior

### 12.1 Error presentation

Normal mode shows a typed reason and an actionable next step. It does not render
raw exception text as the primary message. Developer Mode may expand sanitized
raw details. Secrets and tokens remain redacted in both modes.

Existing generic exception-to-HTTP/UI paths are repair debt, not grandfathered
behavior. They are assigned to the implementation slice that owns the affected
surface. A static ratchet prevents new generic 5xx exception interpolation.

Retry, refresh, and cancel preserve already-loaded content unless a domain
contract explicitly requires clearing it.

### 12.2 Time zones

Storage remains UTC. Generic user activity displays in the desktop/browser IANA
timezone. Market-session concepts are domain exceptions: they anchor to the
exchange timezone and label it explicitly (for US equities, ET). A secondary
local timestamp may be shown where useful.

Recent relative times must expose the exact timestamp. Research history shows
both created and last-updated semantics rather than one ambiguous date.

### 12.3 Accessibility

- Every control is keyboard reachable.
- Drawers trap/manage focus and restore it to their trigger.
- Color is never the only state signal.
- Icon buttons have accessible names and tooltips.
- Disabled controls explain the current-state reason when that reason is not
  already visible.
- Dynamic announcements for completed/failed work use appropriate live-region
  behavior without repeatedly announcing polling updates.

### 12.4 Responsive contract

`shellOverlayBreakpoint = 960px` is the sole authority for changing persistent
shell rails/drawers into overlays. Implementations must expose equivalent CSS
and TypeScript values from one reviewed token source; components do not invent
their own shell breakpoints.

Component-local wrapping may use separately named tokens, but cannot redefine
shell panel behavior.

Operational tables prioritize columns and allow horizontal scrolling. They do
not shrink text until it overlaps or becomes unreadable. Font size does not
scale with viewport width.

Required viewport checks include 1440x900, 1024x768, both sides of the shell
breakpoint (961x768 and 959x768), the breakpoint itself (960x768, on the overlay
side), and 390x844.

## 13. Implementation Sequence

P2.8 is a multi-slice line. Each slice gets its own reviewed implementation
plan. A primitive lands in or before the first slice that consumes it.

The numbering below records dependency order inside P2.8, not authority for the
whole line to preempt Notes/Alerts until every repair ships. The priority map
promotes one workflow slice at a time. After the minimum primitive foundation,
Notes V1 may become the next promoted consumer; it must consume these contracts
rather than inventing parallel primitives.

### Slice 1: Primitive foundation plus first repairs

Implement only the variants needed by current consumers:

- token source, including radius scale and 960px shell breakpoint;
- PageHeader and compact controls;
- StatusBadge/alerts/state presentation;
- transient Drawer;
- compact BoundedProgress;
- DataTable row-action contract;
- ConfirmDialog;
- class-coverage test for migrated components;
- Holdings and Investor Profile missing-style repairs as first consumers.

Pinnable Drawer is not built until Research consumes it.

### Slice 2: Shell convergence

- workflow-grouped navigation;
- removal of planned disabled controls;
- normal/Developer top bar;
- removal of placeholder right rail;
- NavigationTarget resolver;
- BackgroundWorkIndicator/Drawer with Research-only membership.

### Slice 3: Research workspace

- on-demand history and Evidence drawers;
- pinnable Evidence extension;
- full BoundedProgress stage presentation;
- deterministic history search/filter/date display;
- current-thread and global selection precedence;
- input-draft/Stop behavior;
- typed Research errors.

Rename/archive may be a small follow-up within this line. Collections/manual
classification require a separately reviewed data-model slice.

### Slice 4: Settings

1. Pure-move extraction with strict A/B equivalence.
2. Initial grouped single-page IA, anchors, search, and remembered collapse.
3. Terminology review and exact NavigationTarget anchors.

The initial IA was merged and independently verified, but the desktop user
check rejected its all-groups long-page composition. It is historical delivery,
not the final LIVE contract.

### Slice 4.1: Settings navigation correction

1. Shared automatic-activation `Tabs`, first consumed by Settings.
2. Three workflow tabs with one mounted group and current-group directory.
3. Global search and NavigationTarget mount-before-focus behavior.
4. Versioned active-group preference; retired collapse state is never read.
5. Detailed FRED snapshot ownership under `總經資料`, with only compact
   operational FRED state retained in Data Sources.
6. Single terminology authority and exact six-viewport verification.

### Slice 5: Investor Profile UX

- summary-first information hierarchy;
- proposal comparison and rationale;
- qualitative risk labels and scenario anchors;
- hybrid first-time scenario/dialogue calibration.

### Slice 6: Notes V1 prerequisite decisions

Notes V1 owns the Reference store schema, Reports IA decision, and exact delete
policy. P2.8 does not prebuild a generic data layer with no consumer.

## 14. Verification Contract

Every frontend slice runs:

- focused tests;
- the complete Vitest suite;
- TypeScript check;
- production build;
- desktop/browser smoke against real route mounting;
- visual checks at every viewport in Section 12.4;
- keyboard/focus and accessible-name checks;
- overlap, clipping, and empty-panel width checks.

State testing covers loading, empty, ready, running, and failed for every
applicable component. A surface with partial/stale, blocked, or interrupted
semantics must test those states explicitly. Each slice documents its domain
term-to-common-state map.

Mechanical gates are required in slice plans:

- no new production `window.confirm` call;
- no new undefined shared class in migrated components;
- no new public-route raw-exception interpolation for generic server errors;
- no planned item represented as a disabled control;
- no per-component shell breakpoint literal;
- no empty closed Drawer reserving content width.

These are ratchets. Existing occurrences are removed with their owning surface;
they do not block unrelated first slices unless touched.

Settings extraction uses the pure-move ideal: unchanged tests, unchanged failure
set, unchanged passed count, no behavioral edits in the move commit.

## 15. Repair and IA Inventory

| Finding | Owner |
| --- | --- |
| Undefined Holdings shared classes | Slice 1 |
| Undefined Investor Profile `ip-*` classes | Slice 1 |
| Drifted radius and shell breakpoint literals | Slice 1 token foundation, then per-surface migration |
| `window.confirm` in Watchlist, Universe, Holdings, Research, Settings | ConfirmDialog foundation in Slice 1; repay with each owning surface |
| Permanent top-bar diagnostics | Slice 2 |
| Disabled planned Notes/Alerts controls | Slice 2 |
| Global placeholder right rail | Slice 2 |
| Fixed Research three-column layout | Slice 3 |
| Research pending state without elapsed/bound semantics | Slice 3 |
| Research title/archive/search gaps | Slice 3 and bounded follow-ups |
| Generic Research errors | Slice 3 |
| 3,839-line Settings ownership | Slice 4 pure move before IA changes |
| Settings title/content mismatch and technical names | Slice 4, corrected and completed by Slice 4.1 |
| Rejected all-groups Settings long page | Slice 4.1 workflow tabs and one mounted group |
| Split detailed FRED ownership and false Calendar promise | Slice 4.1 `總經資料` ownership correction |
| Holdings local tablist duplicates shared `Tabs` semantics | Next Holdings-owning slice; Slice 4.1 keeps Holdings byte-identical |
| Abstract Investor Profile form hierarchy | Slice 5 |
| Generic card synthesis/translation exception strings | Owning card surface/runtime follow-up; typed timeout remains the precedent |
| Watchlist 148-row live profile and dense cryptic actions | Separate operational-list follow-up after primitives exist |
| Ticker chart placeholder | Separate product feature, not P2.8 shell work |
| Saved reports with no GUI home | Notes V1 IA decision |
| System/Settings duplicated summaries | Resolve during Slices 2 and 4; System keeps diagnostics, Settings keeps controls |

## 16. Related Deferred Research Capability

`2026-06-25-intraday-behavior-layer-design.md` already defines the user’s future
short-horizon research feature: deterministic metrics over minute-scale bars for
trend/chop/whipsaw/quiet/volatile-breakout behavior. P2.8 does not choose 1, 5,
or 15 minute intervals. The feature’s own implementation review will choose
intervals based on signal purpose, data quality, and provider budget.

That feature is a future consumer of:

- ticker-panel layout;
- BoundedProgress and background work;
- StatusBadge/data-quality semantics;
- NavigationTarget into ticker details;
- future read-only agent tools.

It is unrelated to Investor Profile preference calibration.

## 17. Locked Decisions and Remaining Ownership

This spec has no implementation-blocking design question.

Locked here:

- compact progressive disclosure;
- normal/Developer shell modes;
- workflow-grouped final navigation with no planned disabled controls;
- transient and pinnable Drawer modes;
- stage-aware BoundedProgress and global-work notification semantics;
- adaptive Research workspace and model-selection precedence;
- workflow-tab Settings IA with one mounted group and global exact-anchor search;
- summary-first Investor Profile with guided scenario calibration;
- separate NavigationTarget and Reference contracts;
- 960px shell breakpoint;
- phased implementation and mechanical verification ratchets.

Owned by later specs:

- Research collections/manual classification schema;
- server-owned fixed-task runs;
- Notes Reference-store schema and Reports IA;
- Alerts product behavior;
- Watchlist scaling strategy;
- Intraday Behavior implementation interval policy;
- light theme.
