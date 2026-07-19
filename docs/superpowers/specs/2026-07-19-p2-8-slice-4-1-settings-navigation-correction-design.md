# P2.8 Slice 4.1 Settings Navigation Correction Design

> **Status: LIVE COMPLETE, 2026-07-20; reviewed product tip `4931050`, merged
> evidence tip `bfdc32c`, merged-master user verification GREEN.**
> This is a bounded corrective addendum to the P2.8 canonical shell and
> interaction design. It supersedes only the Settings information-architecture
> decisions delivered by Slice 4. All other P2.8 contracts remain in force.

## 1. Purpose and Authority

P2.8 Slice 4 completed the mechanical Settings extraction and shipped a static
registry, stable anchors, cross-section search, a responsive directory, and
replacement of the remaining Settings `window.confirm` calls. Independent
review and automated browser verification passed. The desktop user check then
found that the resulting information architecture was not acceptable:

- all nine sections form one long vertical document;
- the three workflow groups are simultaneously mounted unless manually
  collapsed;
- the directory helps jumping but does not make the current task boundary
  clear;
- `總體經濟與行事曆 · Macro / Calendar` promises calendar content that the
  product does not currently expose; and
- detailed FRED snapshot content lives under Data Sources while the
  `macro_storage` anchor owns the FRED search target.

At design adoption, Slice 4 was merged but not LIVE. Slice 4.1 became the
owning correction for the rejected IA. It preserves Slice 4's useful
infrastructure and changes only navigation composition, FRED/Macro
presentation ownership, and the terminology authority needed to describe
those changes consistently. The correction is now merged, independently
verified, and accepted on the normal desktop; the corrected Settings surface
is LIVE through Slice 4.1.

Authority order for this work:

1. The P2.8 canonical shell spec remains authoritative except where this
   addendum explicitly replaces its Settings IA wording.
2. This addendum owns the Slice 4.1 Settings workflow tabs, current-group
   directory behavior, FRED/Macro ownership, preference migration, and
   acceptance contract.
3. [`ARKSCOPE_TERMINOLOGY.md`](../../design/ARKSCOPE_TERMINOLOGY.md) is the
   single cross-surface terminology authority.
4. Existing domain specs continue to own provider behavior, model routing,
   Investor Profile semantics, storage, schedules, and data ingestion.

The grounded implementation baseline is merged `master` at `f797673`:

- frontend: `63 files / 606 tests`;
- three registry groups and nine stable Settings anchors;
- persisted collapse key `arkscope.settings.collapsedGroups.v1`;
- all three groups mounted when expanded;
- no shared `Tabs` primitive; and
- full FRED snapshot rendering owned by `DataSourcesSection`, while
  `MacroStorageSection` owns only `/macro/status` table counts.

## 2. Goals and Non-Goals

### 2.1 Goals

Slice 4.1 must:

1. replace the long all-groups Settings document with three workflow tabs;
2. mount only the active workflow group;
3. preserve exact anchors and cross-group search/navigation;
4. introduce one shared accessible `Tabs` primitive with Settings as its first
   consumer;
5. move detailed FRED snapshot presentation to the `macro_storage` owner;
6. stop promising calendar functionality that is not present;
7. keep operational FRED health visible in Data Sources without a second
   snapshot request;
8. establish one terminology authority for current and future localized copy;
9. preserve all existing Settings mutations, provider/model ownership, API
   contracts, and responsive shell behavior; and
10. leave an auditable test ledger for intentionally retired Slice 4 behavior.

### 2.2 Non-goals

Slice 4.1 does not:

- implement runtime locale switching or externalize application strings;
- perform an app-wide wording pass;
- change model eligibility, routing, credential, or provider semantics;
- change Investor Profile behavior or calibration flow;
- add calendar ingestion, calendar routes, collector telemetry, or backfill;
- change FRED schedules, storage schema, or snapshot DTOs;
- redesign Data Sources tables or migrate them to a new data-grid primitive;
- change the shell breakpoint or global navigation;
- migrate Holdings to the new `Tabs` primitive in this branch; or
- synchronize the external Design Kit before implementation is accepted.

## 3. Workflow Navigation

### 3.1 Three workflow tabs

Settings has exactly three top-level workflow tabs in this order:

| Stable group ID | Visible label | Sections, in order |
| --- | --- | --- |
| `ai_models` | `AI 與模型` | `providers`, `models`, `fixed_task_runtime`, `research_runtime` |
| `personalization` | `個人化` | `investor_profile` |
| `data_sync` | `資料與同步` | `data_sources`, `data_storage`, `news_storage`, `macro_storage` |

The selected tab defines the only mounted Settings group. Switching tabs
unmounts the prior group's sections and mounts the selected group. This is a
structural lifecycle guarantee, not CSS hiding. It prevents hidden polling and
removes the rejected all-groups vertical document.

The tabs do not create nested routes. Settings remains one application view and
all existing `SettingsAnchorId` values remain stable.

A manual tab selection makes that group's first section the current directory
anchor and places the newly mounted group at its top. The persisted preference
stores only the group, not a scroll position or anchor. Search and
`NavigationTarget` remain the only paths that activate a non-first anchor while
changing groups.

### 3.2 Current-group directory

On persistent-rail viewports, the left directory shows only sections in the
active group when the search query is empty. On overlay viewports, the same
directory is rendered in the canonical transient `Drawer`; the persistent rail
and Drawer are mutually exclusive.

The directory is an in-group navigation aid, not a second workflow selector.
The workflow tabs remain visible above the content so the active scope is
always explicit.

### 3.3 Cross-group search

The search control is labeled `搜尋所有設定` and appears at the top of the
directory. Its wording must communicate that search crosses all three workflow
groups even though the empty directory lists only the current group.

- Empty query: show current-group sections only.
- Non-empty query: search every registry section and group matches by workflow.
- Selecting a result in another group first activates that group, then waits
  for its content to mount, then scrolls/focuses the exact anchor.
- Enter selects the first deterministic result under the same rule.
- No-match state is plain status text, not a disabled control.

The pure registry helper `searchSettings("")` continues to return all sections
in registry order. Empty-query current-group filtering belongs to the directory
component, so the registry search contract does not silently change.

English aliases may remain searchable through registry keywords without being
duplicated in visible labels.

### 3.4 NavigationTarget and preference precedence

Precedence is explicit:

1. a new `NavigationTarget` for a Settings anchor;
2. a search-result selection;
3. the last valid persisted active group; and
4. default group `ai_models`.

`NavigationTarget` and search create a pending anchor. The reveal effect is
keyed by the active group and pending anchor; it waits until the target group is
mounted before scrolling and focusing. A fixed-delay or one-shot `requestAnimationFrame`
that can run before mount is not sufficient.

Any manual tab change clears the pending anchor. This prevents an old search or
navigation request from unexpectedly focusing content when the user later
returns to that group.

### 3.5 Active-group preference

The only new Settings navigation preference is:

```text
arkscope.settings.activeGroup.v1
```

The stored value is one `SettingsGroupId`, not a serialized UI tree. Missing
storage, unavailable `window`, read/write exceptions, malformed values, and
unknown group IDs fail closed to `ai_models` and never block rendering.

The retired key `arkscope.settings.collapsedGroups.v1` is never read,
interpreted, or migrated. A successful write of the new preference may make a
best-effort attempt to remove the old key; cleanup failure has no effect on the
visible UI or new preference.

## 4. Shared Tabs Primitive

Slice 4.1 introduces `ui/Tabs` before Settings consumes it. V1 deliberately
matches the already-shipped Holdings tab behavior:

- horizontal `tablist`;
- linked `tab` and `tabpanel` IDs;
- one `aria-selected="true"` tab;
- roving `tabIndex`;
- automatic activation: focus movement also selects the tab;
- `ArrowLeft` and `ArrowRight` move with wraparound;
- `Home` and `End` select the first and last tabs;
- mouse/pointer activation remains supported; and
- the selected panel is the only mounted panel.

V1 has no manual/automatic activation option. A future consumer may justify an
additional mode in its own owning slice; Settings does not prebuild it.

Holdings remains byte-identical in Slice 4.1. Its local tab implementation is a
named repair item and migrates to `ui/Tabs` only in the next Holdings-owning
slice. This temporary duplication is tracked rather than hidden inside this
bounded correction.

## 5. Section Ownership

### 5.1 Existing boundaries remain

Workflow grouping is presentation, not code ownership. In particular:

- `ProviderSection` owns provider login, credentials, subscription state,
  credential-scoped discovery, and provider tests.
- `ModelRoutingSection` owns per-task provider/model/effort routing only after
  availability is known.
- Fixed-task and Research runtime limits remain separate subsections adjacent
  to their routes.
- Investor Profile remains the sole Personalization section until Slice 5.
- Developer Mode remains owned by System / Health and does not move into
  Settings.
- disabled historical `app_records` and unimplemented permissions remain
  absent from normal navigation.

Changing tabs must not silently discard a dirty user-entered draft or orphan an
in-flight authorization/mutation workflow. The implementation plan must
inventory the local draft and busy/session owners in Provider, Data Sources,
Investor Profile, and runtime controls. It must state how each affected owner
either preserves session state outside the unmounted presentation or prevents
the switch with an honest visible reason. If that cannot be done within the
reviewed boundary, implementation stops for review. Keeping all groups mounted
through CSS hiding is not an allowed workaround.

### 5.2 Stable anchors and revised visible metadata

All nine anchor IDs remain unchanged. The `macro_storage` registry entry is
revised to:

- title: `總經資料`;
- description: describe stored FRED data and coverage, without promising
  calendar content;
- keywords: own `FRED`, snapshot, series, observations, and relevant macro
  aliases.

`data_sources` retains operational keywords such as provider, health,
credential, schedule, SA extension, and IBKR client ID. It must not retain FRED
snapshot keywords that would route the user to the compact operational row
instead of the detailed data owner.

## 6. FRED and Macro Ownership Correction

### 6.1 Grounded defect

The merged Slice 4 code has two competing FRED presentations:

- `DataSourcesSection` calls `/macro/snapshot` and renders the complete snapshot
  table under `FRED 資料快照`.
- `MacroStorageSection` calls `/macro/status` and renders table row counts under
  `總經與行事曆 · Macro / Calendar`.

The registry sends `FRED` search to `macro_storage`, so the exact target does not
own the detailed snapshot. The visible title also promises economic/earnings
calendar functionality that is explicitly outside the current product surface.
The domain authority
[`MACRO_FRED_PRODUCT_SEMANTICS.md`](../../design/MACRO_FRED_PRODUCT_SEMANTICS.md)
keeps the local FRED snapshot readable with refresh off while leaving Finnhub
economic/earnings calendar backfill outside the shipped surface.

### 6.2 Final ownership

| Concern | Owner after Slice 4.1 | Data source |
| --- | --- | --- |
| FRED credential/configuration | Data Sources | existing provider config payload |
| FRED health and auto-refresh state | Data Sources | existing provider-health `signals` |
| Compact snapshot availability/count summary | Data Sources | existing `signals.local_snapshot`; no snapshot request |
| FRED series values and observation dates | `總經資料` | `/macro/snapshot` |
| Stored table coverage and latest stored timestamps | `總經資料` | `/macro/status` |
| Economic/earnings/IPO calendar product UI | none in Slice 4.1 | deferred |

`DataSourcesSection` stops calling `getMacroSnapshot()` and removes the full
snapshot table. Its FRED provider row may display only facts already present in
provider config/health:

- configured or missing credential;
- local snapshot available/unavailable and its existing counts; and
- auto refresh on/off.

It must not create a second `/macro/status` or `/macro/snapshot` request to make
the compact row richer.

`MacroStorageSection` becomes the only frontend consumer of
`getMacroSnapshot()`. It owns the detailed returned series list, observation
dates, fetched-at values, auto-refresh context, and compact stored-table
coverage. It does not hard-code the current production count of 11 series as a
schema invariant; it renders the existing DTO truth.

### 6.3 Independent request legs

`總經資料` loads `/macro/status` and `/macro/snapshot` as independent legs with
`Promise.allSettled` or an equivalent bounded mechanism. Failure of one leg
does not clear or hide successful truth from the other. A partial
`InlineAlert` explains which portion is unavailable without interpolating a raw
exception in normal mode.

This is one visible owner with two read models, not duplicate ownership.

### 6.4 Honest states

The UI must distinguish only facts the current APIs can establish:

| Observed fact | Required presentation |
| --- | --- |
| Both request legs succeed with rows | detailed series plus coverage and timestamps |
| Snapshot succeeds, status fails | preserve detailed series; partial coverage alert |
| Status succeeds, snapshot fails | preserve stored counts/timestamps; partial detail alert |
| DB or required table is absent | honest unavailable/unknown state for that leg |
| A table reports `row_count = 0` | `0 筆已儲存`; do not claim the collector never ran |
| Auto refresh is off but stored data exists | show stored fetched-at and refresh-off state; do not label provider failure |

`/macro/status` derives `last_fetched_at` from stored rows. There is no collector
run-telemetry table, so a zero-row table cannot distinguish “never executed”
from “executed successfully with zero results.” Slice 4.1 must not invent that
distinction. Adding collector run telemetry is a separate design.

Calendar row counts may remain in compact storage coverage if returned by the
existing status DTO, but they are not promoted as a Calendar feature and do
not restore the old title.

## 7. Terminology and Language Boundary

[`ARKSCOPE_TERMINOLOGY.md`](../../design/ARKSCOPE_TERMINOLOGY.md) owns canonical
EN/Traditional-Chinese pairs and mixed-language rules. Other product documents
link to it instead of copying terminology tables.

The rules relevant to this slice are:

1. locale determines grammar; Traditional Chinese uses natural Traditional
   Chinese sentence structure;
2. proper names, protocols, AI/finance abbreviations, and terms whose
   translation loses normal professional meaning remain English;
3. mature, non-lossy Traditional Chinese terms are used when available;
4. the default is mixed professional language, not literal all-Chinese copy;
5. one label does not repeat the same concept as `譯文 · Original`; and
6. parallel bilingual display requires a documented case-specific reason and
   is not a general mode.

Therefore this slice uses `總經資料`, while `FRED`, `Provider`, `OAuth`, `NAV`,
`P&L`, `EBITDA`, and `ETF` remain English where they occur. English aliases can
support search without appearing beside every visible label.

Slice 4.1 changes only new navigation labels, the `總經資料` ownership copy,
and state copy required by this design. It does not conduct a broad Settings or
application wording pass.

## 8. Responsive and Accessibility Contract

The canonical shell breakpoint remains `960px`, inclusive on the overlay side:

- `961px` and above: persistent current-group directory rail;
- `960px` and below: directory trigger plus transient Drawer;
- the two directory forms are never mounted simultaneously.

Tabs retain stable dimensions and may wrap only if required to avoid clipping;
they do not reduce font size with viewport width. Labels, focus rings, and
selected state must remain visible without horizontal page overflow.

Selecting a directory result in the Drawer closes the Drawer, returns the
application to the selected Settings content, and focuses the exact anchor.
Closing by Escape without a selection returns focus to the directory trigger.

No polling update gains an `aria-live` region. Tabs, search results, partial
alerts, and exact-anchor focus follow the existing P2.8 accessibility rules.

Required visual checks are exactly:

- `1440x900`;
- `1024x768`;
- `961x768`;
- `960x768`;
- `959x768`; and
- `390x844`.

The `960x768` check is mandatory because the breakpoint itself belongs to the
overlay side and is the direct off-by-one boundary.

## 9. Verification Contract

The Slice 4.1 implementation plan starts from `63 files / 606 tests`. It must
name every added, evolved, renamed, and removed test node. Retired collapse
tests and Data Sources snapshot tests cannot be hidden behind a net-positive
test delta.

### 9.1 Required behavior coverage

The plan must cover:

1. `Tabs` ARIA roles/linkage, automatic activation, roving focus, wraparound,
   and Home/End behavior;
2. active-group preference read/write, malformed/unknown values, unavailable
   storage, and old-key-never-read behavior;
3. only the active group being mounted, including unmount of Data Sources
   polling when leaving `data_sync`;
4. empty-query current-group directory versus non-empty cross-group search;
5. manual tab selection choosing the new group's first anchor;
6. search and `NavigationTarget` switching group before exact focus;
7. manual tab changes clearing stale pending anchors;
8. dirty drafts and in-flight authorization/mutations not being silently lost
   across a requested group change;
9. `NavigationTarget` overriding the persisted group;
10. Data Sources making no snapshot request and deriving its FRED row only from
   existing provider/config payloads;
11. `總經資料` as the single detailed snapshot owner;
12. both FRED legs succeeding, each one-leg partial case, missing DB/table,
    zero rows, and refresh-off stored-data behavior; and
13. registry keyword ownership routing FRED/snapshot terms to
    `macro_storage` and operational terms to `data_sources`.

### 9.2 Mechanical boundaries

The implementation must prove byte identity for:

- backend `src/`, `data_sources/`, and all backend tests, without exception;
- frontend API DTO/runtime client code;
- Holdings, including its local tabs;
- Investor Profile;
- Dashboard/System; and
- browser extensions.

Static ratchets must establish:

- production code never reads `arkscope.settings.collapsedGroups.v1`;
- the active-group key has one owner;
- `getMacroSnapshot` has exactly one Settings consumer,
  `MacroStorageSection`;
- Data Sources does not render the detailed FRED snapshot table;
- no new shell breakpoint literal, `window.confirm`, raw-exception display, or
  undefined shared class is introduced; and
- no Calendar label promises an unimplemented surface.

### 9.3 Standard and visual gates

The canonical P2.8 §14 gate remains fully applicable: focused and complete
frontend tests, typecheck, production build, desktop/browser smoke, keyboard
and focus checks, and state/overlap/clipping checks.

The six viewports in §8 additionally verify:

- no horizontal page overflow;
- all three tabs fit and remain operable;
- exactly one directory path is mounted;
- exact-anchor navigation lands under the correct group; and
- Data Sources versus `總經資料` ownership is understandable without duplicate
  detailed content.

## 10. Documentation and Sequencing

This design and its approval update the P2.8 canonical spec in the same docs
line:

- §7.1 gains `Tabs`;
- §9.1 replaces the single-page/collapse contract;
- §9.2 corrects `MacroStorageSection` ownership;
- §12.4 names the exact breakpoint viewport;
- §13 records Slice 4.1 as the corrective Settings slice;
- §15 records the rejected long-page IA and Holdings local-tabs debt; and
- §17 replaces the locked single-page Settings decision.

The original Slice 4 plan remains historical evidence of a reviewed and merged
implementation, but its IA is superseded. The corrected Settings contract is
marked LIVE only through this Slice 4.1 addendum.

Closeout status after implementation and user verification:

1. Slice 4.1 and the corrected Settings surface are LIVE;
2. Design Kit sync #5 for the Tabs primitive, three-tab Settings IA, and
   `總經資料` states is handed to Fable and remains separately pending;
3. the app-wide i18n decision document is next; and
4. Slice 5 Investor Profile UX stays queued until that sequencing decision is
   recorded.

The i18n decision document owns runtime locale mechanism, locale authority,
fallback/detection, string externalization, and the Shell + Settings first
migration. Slice 4.1 does not create a partial locale layer or pre-render future
localized screens in the Design Kit.

## 11. Locked Decisions

No implementation-blocking product question remains in this design.

Locked decisions are:

- three workflow tabs, one mounted group;
- current-group directory with explicitly global search;
- manual tab selection targets the new group's first anchor;
- exact search/NavigationTarget focus after mount;
- manual tab changes clear pending anchors;
- dirty drafts and active authorization/mutations are never silently discarded;
- versioned active-group preference and no collapse-state migration;
- shared automatic-activation `Tabs`, Settings first, Holdings deferred;
- stable nine-anchor model and existing provider/model ownership;
- detailed FRED snapshot owned only by `總經資料`;
- compact Data Sources FRED status from existing payloads only;
- no Calendar feature claim;
- honest zero-row/partial/refresh-off semantics;
- one terminology authority and mixed professional Traditional Chinese;
- no runtime i18n in 4.1; and
- exact six-viewport validation including `960x768`.
