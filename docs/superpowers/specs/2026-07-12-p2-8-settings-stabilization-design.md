# P2.8 Settings Stabilization Design

> **Status: LIVE / MERGED — fast-forwarded through `ca3db2f`, 2026-07-13.**
> This is a bounded insertion after P2.8 Slice 1. It does not replace the
> canonical shell authority or pre-implement the later Settings and Investor
> Profile slices.

## 1. Decision

The user selected a mixed sequence:

1. repay the immediately visible UI debt described here;
2. keep the measured startup regression as a deferred observation;
3. design Portfolio 1.1 for account value, cash, realized profit/loss, and
   transaction effects;
4. return to P2.8 Slice 2, Slice 3, Slice 4, and Slice 5.

This stabilization is deliberately smaller than P2.8 Slice 4. It fixes
overlap, stale migration language, and one incorrect user-facing term without
changing Settings information architecture.

Authority remains
`docs/superpowers/specs/2026-07-12-p2-8-canonical-shell-interaction-design.md`.

## 2. Verified Current State

### 2.1 Delivered versus pending P2.8 work

Slice 1 delivered the token and primitive foundation plus the first Holdings
and Investor Profile presentation repairs. It did not add portfolio financial
data and did not redesign all Settings content.

- Slice 2 owns shell navigation, top bar, placeholder-rail removal, and the
  Research-only background-work indicator.
- Slice 3 owns the AI Research workspace.
- Slice 4 owns Settings extraction and full information architecture.
- Slice 5 owns the summary-first Investor Profile and qualitative/scenario
  calibration experience.

Waiting for Slice 2 alone would therefore not fix the issues in this design.

### 2.2 Data Sources overlap

Three concrete layout failures share two causes:

- a running schedule renders `done / total`, current ticker, and percentage
  inside one `ds-chip`, whose CSS is `white-space: nowrap`;
- the SA extension and FRED snapshot tables use fixed table layout plus the
  global no-wrap table rule without an owning horizontal-scroll region.

The existing Data Sources fixture uses `progress: null` only. It does not
exercise long current tickers, long SA details, long macro titles, or narrow
content widths.

### 2.3 Stale normal-mode copy

Enabled Settings directory descriptions and the Market Data, News Ingestion,
Macro / Calendar, and Data Sources panels still explain PostgreSQL exit,
SQLite authority, local/legacy projections, mirrors, and migration-era route
states. Those facts no longer help a normal user decide what to do.

`App Records` is excluded: it is `enabled: false`, normal navigation filters
disabled entries, and its absence is test-pinned. Its historical description
and component remain untouched.

### 2.4 Investor Profile terminology

The persisted field remains `risk_appetite`, but the current Chinese UI says
`風險胃納`. The user ruled that all normal UI occurrences become
`風險意願`. `風險承受能力` remains unchanged.

### 2.5 Startup observation, deferred

Three fresh scheduler-disabled probes compared the 2026-07-08 pre-Holdings
plan tip `91ca631` with current `master`:

| Measurement | 91ca631 median | current median |
| --- | ---: | ---: |
| FastAPI ready-total | about 2.24 s | about 3.11 s |
| process wall time | about 3.13 s | about 4.40 s |
| route count | 145 | 158 |

Vite itself was ready in about 0.2 seconds. Import profiling attributes most
of the current cost to eager route imports that pull card synthesis, Research,
OpenAI/Anthropic SDKs, model canary, and related agent modules before the
desktop shell loads its URL.

The regression is real but acceptable. This design records it only. It does
not add lazy imports, startup profiling, a splash screen, resource controls, or
performance gates. A future loading screen is an option only if startup delay
becomes materially disruptive.

## 3. Scope

### 3.1 Included

- enabled directory descriptions for Data Storage, News Ingestion, and
  Macro / Calendar;
- the normal-mode Market Data panel;
- News Ingestion, renamed and reduced to a news-data status surface;
- the normal-mode Macro / Calendar panel;
- Data Sources header, provider/SA/FRED tables, credential table, scheduler
  table, and running-progress presentation;
- all user-facing `風險胃納` strings in Investor Profile presentation,
  mismatch labels, and their tests.

### 3.2 Excluded

- Settings extraction, grouping, anchors, search, or navigation changes;
- merging News, Macro, Data Sources, or other sections;
- App Records and Permissions;
- backend DTO, route, storage, scheduler, provider, or mutation changes;
- portfolio cash, account net liquidation, realized profit/loss, execution
  history, or trade classification;
- qualitative risk tiers, scenario questions, or calibration-flow redesign;
- Developer Mode implementation;
- startup performance implementation;
- P2.8 Slice 2, Slice 3, Slice 4, or Slice 5 behavior.

## 4. Normal-Mode Copy Rule

Every touched sentence follows one rule:

> Preserve source and path facts that change what the user can do. Remove
> storage-backend and migration-history narration.

Normal mode may show:

- provider/source name;
- configured, available, stale, blocked, running, partial, or failed state;
- data count, coverage, latest observation, last attempt, and last success;
- required action and actionable limitation;
- credential ownership such as App, environment variable, or
  `config/.env`, because that tells the user where a setting must be changed.

Normal mode does not narrate:

- PostgreSQL/PG exit or fallback history;
- SQLite/local authority;
- mirror/projection/dual-write history;
- `legacy`, `direct-local`, `normalized write`, internal database names,
  rollout flags, or migration phase names.

Technical history may later live in Developer Mode. This slice does not build
that destination.

## 5. Surface Design

### 5.1 Market Data

The panel becomes a concise market-data status:

- prices, news, IV, fundamentals, and financial-data counts;
- latest observation/fetch timestamps;
- recent incremental update;
- trading-day coverage.

`本地市場資料庫`, `本地路由`, `local authority`, PG retirement copy, and
database implementation names disappear from the normal surface. Existing
read-only status and coverage behavior remains unchanged.

### 5.2 News Data Status

`News Ingestion` becomes `新聞資料狀態`. It retains:

- article count, source count, and latest article;
- last successful collection and last attempt;
- current collection state;
- most recent provider/general error.

It stops rendering write-route, PostgreSQL, local/legacy projection, rollout
and pre-exit language.

Two mutation controls require an explicit disposition:

- the direct-news routing checkbox calls `PUT /news/settings` and persists
  `use_local_news`;
- the normalized-writes checkbox calls
  `PUT /news/settings/normalized-writes` and persists
  `use_normalized_news_writes`.

The normal UI stops rendering both checkbox branches. This is an intentional
removal of migration-era user controls, not a copy-only edit. The underlying
profile settings, environment overrides, compatibility mutation routes, status
DTO fields, and route-resolution code remain unchanged. Programmatic callers
can still reach the guarded routes; in the completed post-exit state those
routes already reject selecting the retired OFF path, and the current UI
already hides the checkboxes when `news_hard_local=true`.

Whether this surface later merges into Data Sources remains a Slice 4 decision.

### 5.3 Macro / Calendar

The panel retains:

- FRED series and observation counts;
- release/economic/earnings/IPO calendar counts;
- latest fetch times;
- actionable provider limitations, such as a required paid entitlement.

It removes local-only, SQLite, database filename, PG-mirror, ingestion-pipeline,
and rollout explanations. The FRED snapshot table inside Data Sources follows
the responsive table contract in Section 7.

### 5.4 Data Sources

The header explains only that each provider can be configured, checked,
scheduled, and run independently.

Raw `source_badges` are no longer rendered because the current field mixes
useful provider identity with storage-route implementation terms. Existing DTO
content remains untouched.

Credential source labels remain because they determine where the user can
change a value. Runtime-policy narration such as DB-first or legacy fallback is
not shown in normal mode.

### 5.5 Investor Profile

The exact normal-mode replacements are:

- `風險胃納 (1-10)` -> `風險意願 (1-10)`;
- `風險胃納 vs 承受能力` -> `風險意願與風險承受能力`;
- `風險胃納高於承受能力` -> `風險意願高於承受能力`;
- `承受能力高於風險胃納` -> `承受能力高於風險意願`.

The schema, payload, derivation, prompt wording, numeric scale, and risk
capacity term do not change. Slice 5 later adds qualitative labels and scenario
anchors. Implementation closeout also updates the project terminology
reference so user-facing Chinese maps `risk appetite` to `風險意願`.

## 6. Source Run Progress

`SourceRunProgress` is a Data Sources domain component, not a new generic
progress engine.

### 6.1 Known progress

When `running=true`, `progress != null`, and `total > 0`, the selected
user-approved layout is:

1. current item on its own wrapping line;
2. a visual progress track on its own line;
3. `done / total` and a rounded percentage below it.

Percentage derives only from the real DTO and is clamped to 0-100 for display.
The track exposes `role="progressbar"`, `aria-valuemin`,
`aria-valuemax`, and `aria-valuenow`.

### 6.2 Indeterminate progress

When progress is absent or its total is not positive, the component shows only
the running state. It does not invent a percentage or animate a fake linear
completion estimate.

### 6.3 Polling and ownership

The existing 5-second poll remains unchanged. Poll updates do not use
`aria-live` and therefore do not announce every tick. The existing
`StatusBadge` owns the running appearance; `SourceRunProgress` owns current
item, track, and counts only.

## 7. Responsive Table Contract

SA extension health, FRED snapshot, provider health, provider credentials, and
schedule tables each receive an explicit horizontal-scroll owner and a reviewed
minimum table width.

- The viewport/content region never becomes wider because of a table.
- Font size is not reduced to force content to fit.
- SA detail, macro title, and latest-run detail columns may wrap.
- dates, state badges, numeric values, and command controls remain compact and
  non-overlapping;
- the schedule progress cell owns its internal width and cannot cover the
  latest-run cell.

This is a stabilization of existing tables. It does not migrate them to the
Slice 1 `DataTable` component or redesign row actions.

## 8. Domain-State Mapping

The Data Sources surface maps existing domain terms to the canonical common
states:

| Domain condition | Common state |
| --- | --- |
| requests pending | `loading` |
| no snapshot/data or never run | `empty` |
| connected, available, last run succeeded | `ready` |
| source `running=true` | `running` |
| provider stale or durable run partial | `partial/stale` |
| missing required configuration/key or a duplicate trigger blocked by an existing run | `blocked` |
| request, provider segment, or durable run failed | `failed` |
| no current domain signal | `interrupted` is not synthesized |

A user-disabled schedule is a stable neutral state, not a failure. It receives
no state badge and is shown as muted plain text (`排程關閉`) beside the existing
control. This is an explicit presentation exception rather than a fabricated
`ready` state. Existing domain labels remain authoritative; shared primitives
standardize presentation.

## 9. Error and Accessibility Boundaries

- Existing API and mutation behavior stays unchanged.
- Already-loaded content remains visible when refresh fails.
- Error/detail text wraps and cannot enlarge the page.
- No new raw-exception interpolation is introduced.
- The progress bar has an accessible name including the source label.
- Color is never the only state signal.
- Polling does not create repetitive live-region announcements.
- Command focus and keyboard behavior remain unchanged.

Typed error redesign for all legacy Settings paths remains owned by Slice 4.

## 10. Verification Contract

The implementation plan must begin RED-first and include:

1. known progress with a long current ticker/item;
2. indeterminate running state;
3. zero/non-positive totals without division or fake percentage;
4. progressbar ARIA values and no polling live region;
5. long SA detail, long FRED title, long latest-run error, and credential
   content inside explicit scroll owners;
6. enabled directory and panel text free of storage/migration narration while
   actionable credential-source labels remain;
7. both News mutation checkboxes absent from the rendered normal UI, zero
   `setUseLocalNews` / `setNormalizedNewsWrites` calls during render, and
   unchanged effective fields from the status response; backend byte identity
   keeps the status endpoint and compatibility mutation routes unchanged;
8. a disabled schedule rendered as muted `排程關閉` text without a status badge;
9. the four Investor Profile/mismatch wording replacements and all affected
   existing assertions;
10. Market, News, Macro, and Data Sources loading/empty/ready/running/failed
   states where applicable, plus partial/stale and blocked states on Data
   Sources;
11. full frontend Vitest, TypeScript, and production build;
12. browser checks at 1440x900, 1024x768, 961x768, 959x768, and 390x844 with
    long-content fixtures and a non-null running progress fixture;
13. no overlap, clipping, page-level horizontal overflow, font shrinking, or
    inaccessible progress state;
14. backend and backend-test byte identity for this frontend-only slice.

Static gates are scoped to enabled normal Settings surfaces. They must not
rewrite unreachable App Records history, comments, backend compatibility
fields, or archival documents merely to make a repository-wide word search
empty.

## 11. Lineage and Sequence

This work repays display debt left by the historical PG-exit transition. The
Priority Map already marks PG-EXIT closed; this design does not reopen it.

After this stabilization is reviewed, implemented, verified, and merged, the
next promoted product design is Portfolio 1.1. P2.8 then resumes with Slice 2
unless the Priority Map records a newer explicit ruling.
