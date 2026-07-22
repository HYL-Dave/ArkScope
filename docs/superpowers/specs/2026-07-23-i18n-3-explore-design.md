# ArkScope I18N-3 Explore Design

> **Status: DESIGN REVIEW GREEN — IMPLEMENTATION PLAN WRITTEN,
> INDEPENDENT PLAN REVIEW NEXT**
>
> Written against merged `master` at `c0448213` on 2026-07-23. This document
> is the bounded product, localization, error-presentation, and verification
> authority for I18N-3 Explore. Independent full-document review returned
> GREEN with the required zh-Hant copy-preservation rule incorporated below.
> It does not authorize product implementation, backend changes, the public
> locale selector, or any deferred SA extension repair. The separately written
> RED-first implementation plan remains blocked on independent review GREEN.

## 1. Purpose and Authority

I18N-0 established a profile-DB locale authority, synchronous cache-assisted
bootstrap, typed static resources, and the literal scanner. I18N-1 migrated
Shell and common UI. I18N-2 migrated Settings. P2.8 Slice 5 then shipped the
new Investor Profile workspace bilingual from birth.

I18N-3 migrates the user-facing Explore workflow:

- Home / 工作台;
- Watchlist / 自選股;
- Universe / 全部標的;
- News / 新聞·事件;
- Ticker Detail; and
- AI Card surfaces reached from Home or Ticker Detail.

The unit also migrates the shared tag and personalization display helpers
actually consumed by those surfaces. The goal is not a visual or domain
redesign. It is a complete, reactive, and auditable translation of
application-owned chrome while preserving source content, generated content,
workflow state, API behavior, and explicit user-triggered card translation.

Authority order:

1. [`ARKSCOPE_TERMINOLOGY.md`](../../design/ARKSCOPE_TERMINOLOGY.md) owns
   canonical English and Traditional Chinese terminology.
2. [`2026-07-20-app-wide-i18n-decision.md`](2026-07-20-app-wide-i18n-decision.md)
   owns locale storage, bootstrap, runtime mechanics, release sequencing, and
   the selector-last gate.
3. The canonical P2.8 shell design owns Shell navigation, viewport
   breakpoints, overlay behavior, and `NavigationTarget`.
4. Existing News content-availability, DB-universe, AI Card, and tag data
   contracts continue to own domain behavior.
5. This document owns I18N-3 language boundaries, Explore display ownership,
   safe error presentation, locale-switch behavior, file boundaries, and
   verification.

### 1.1 Grounded baseline

At `c0448213`:

- the frontend baseline is `83 files / 863 tests`;
- the backend collection baseline is `4621`;
- the literal policy reports exactly `1033` candidates, `973` current
  signatures, `954` debt signatures, `20` allowlist entries, and `30`
  migrated scopes;
- the six primary Explore files plus `tags.tsx` and
  `personalizationDisplay.ts` contain exactly `317` debt signatures across
  `330` occurrences;
- `personalizationDisplay.ts` alone owns exactly 14 zh-Hant debt signatures:
  seven Assistant Stance labels, four risk-mismatch labels, and three trace
  summary templates;
- `personalizationDisplay.ts` is consumed by `AICard.tsx`, `Research.tsx`, and
  `ResearchEvidenceDrawer.tsx`, while Settings separately owns a second
  stance/mismatch mapping and a test that asserts zh-Hant byte equality;
- `tags.tsx` stores five system-owned facet labels in English but combines
  them with source/user-owned tag values and source IDs;
- Home, Watchlist, Universe, News, Ticker Detail, and AI Card paths store or
  render raw `Error.message` values in normal UI;
- Universe stores localized success and failure sentences directly in state;
- `ApiError` already exposes structured `path`, `status`, `code`, and
  `diagnostic` fields, but its `message` is a legacy display string and mutation
  messages may append backend detail;
- `settingsBackendCopy.diagnosticValue()` is only a Developer Mode visibility
  gate. It does not redact or sanitize;
- the Research sanitizer redacts several credential/token shapes but remains a
  denylist and does not establish a generic safe boundary for paths,
  tracebacks, SQL, IP addresses, or arbitrary exception text;
- Explore surfaces do not currently receive `developerMode` or the generic
  `NavigationTarget` dispatcher consistently; and
- the public locale selector remains absent, as required before I18N-6.

These observations are implementation grounding, not permission to broaden
the unit.

## 2. Goals and Non-Goals

### 2.1 Goals

I18N-3 must:

1. migrate every application-owned visible string in the eight fully owned
   files to static typed `zh-Hant` and `en` resources;
2. preserve source, user, provider, and generated content byte-for-byte;
3. replace raw exception rendering with operation-specific localized copy;
4. provide safe, bounded Developer Mode diagnostics without presenting raw
   exception text;
5. converge stance, mismatch, and trace labels to one shared resource and
   presenter owner;
6. preserve every active Explore workflow state during an in-place locale
   switch;
7. preserve all current loading, empty, degraded, partial, and mutation
   trigger semantics;
8. keep all six Explore surfaces usable in both locales at desktop, shell
   breakpoint, and mobile viewports; and
9. leave an exact resource, scanner, test-node, and file-scope ledger for
   independent review.

### 2.2 Non-goals

I18N-3 does not:

- expose, enable, disable, or placeholder-render the locale selector;
- pass `ui_locale` into an AI prompt;
- automatically translate News, notes, tags, list names, card prose,
  rationale, evidence, or other source/generated content;
- remove or change the defaults of the existing user-triggered AI Card
  translation feature;
- redesign Explore IA, tables, filters, pagination, tabs, cards, or modals;
- change News content-availability derivation or recovery policy;
- repair `/sa/feed` missing-DB empty/bad semantics;
- implement the SA extension packaging, Backfill, or degraded-observability
  backlog;
- change API response DTOs or backend routes without a reviewed spec
  amendment;
- change date, time, number, percentage, or currency formatter ownership;
- migrate all Research chrome before I18N-4;
- clean the Settings diagnostic path as an unreviewed side effect; or
- clean Shell/System residual error presentation before I18N-5.

## 3. Locked Decision 1: Translate Chrome, Preserve Content

### 3.1 Application chrome localizes

Application-owned chrome includes:

- page, section, tab, table-column, disclosure, and form labels;
- button, menu, placeholder, tooltip, title, and accessible names;
- loading, empty, degraded, partial, success, and error explanations;
- system-owned closed-enum display labels;
- count and status sentences whose interpolation values are safe structural
  values; and
- AI Card section headings and traceability chrome.

Both locale values are static TS resources. Keys are semantic and statically
selected. Dynamic translation-key construction remains forbidden.

Existing rendered zh-Hant chrome moves into resources byte-for-byte by
default. Every zh-Hant wording change, including terminology alignment and
removal of a translated-plus-English duplicate, must be individually named in
the implementation plan's copy ledger. When preserving a legacy literal would
conflict with the terminology authority, the terminology authority wins and
the reviewed ledger records the exact before/after pair.

### 3.2 Source and generated content remains original

The following values never pass through `t()` and are never rewritten merely
because `ui_locale` changes:

- ticker symbols, Provider/model names, series IDs, evidence IDs, API/error
  codes, and other stable identifiers;
- user-created Watchlist names, notes, tag values, and search input;
- provider/source names and source taxonomy values where they are legitimate
  data rather than chrome;
- News titles, descriptions, snippets, article types supplied as source data,
  comments, and URLs;
- AI Card question, conclusion, reasons, risks, assumptions, narrative,
  divergence, evidence notes/data, claims, and rationale; and
- already generated or explicitly translated Card content.

Application chrome around those values localizes. For example, a localized
sentence may interpolate a ticker or count, but the ticker itself remains
unchanged.

### 3.3 Explicit AI Card translation survives

The existing Card control that explicitly requests a zh-Hant translation is a
separate user action. I18N-3 must not:

- trigger it from `ui_locale`;
- change its initial Card-language selection;
- discard its result when application locale changes;
- alter its Provider/model/runtime request; or
- remove its current cached server-side behavior.

Changing application locale translates only the control chrome. The selected
original or translated Card body remains selected and byte-identical.

## 4. Locked Decision 2: Structured Explore Errors

### 4.1 Operation-specific normal copy

Normal Mode never renders `Error.message`, `ApiError.message`, backend detail,
tracebacks, SQL, file paths, or arbitrary exception text. It renders localized
copy selected by a closed `ExploreOperation` semantic ID.

The operation inventory must distinguish at least:

| Surface | Read operations | Mutation operations |
| --- | --- | --- |
| Home | load workspace, load/open Card | save Card |
| Watchlist | load lists, load Universe, symbol search, load consensus | create/rename/default list, add/remove member, archive/unarchive, set priority |
| Universe | load Universe and list metadata | import reviewed annotations, hide/restore ticker |
| News | load Market News, load Seeking Alpha feed, load more | none |
| Ticker Detail | load ticker state, price overview, IV, IV history, fundamentals, status, coverage, notes, tag catalog | add/delete note, add/remove tag |
| AI Card | load recent/open Card, load Investor Profile | generate, save, explicitly translate |

The implementation plan may split an operation further, but may not merge
distinct reads and mutations into a generic `request_failed` owner. Partial
multi-leg reads preserve successful legs and identify failed legs with
localized leg labels.

### 4.2 Capture structured facts, never parse display text

Catch paths normalize errors into a locale-independent structure. The
normalizer may read `ApiError.status`, `ApiError.path`, `ApiError.code`, and
`ApiError.diagnostic` directly. It must never regex, split, or infer semantics
from `.message`.

State stores:

- the operation ID;
- a bounded typed error category;
- validated structural metadata; and
- an optional already-sanitized Developer detail.

It does not store localized error sentences. Render time passes this state and
the namespace-typed `explore` translator to one pure presenter.

### 4.3 Safe Developer Mode diagnostics

Developer Mode remains useful on Explore, but its contract is stricter than
the existing Settings diagnostic path.

Safe structural fields are:

- HTTP status only when it is an integer from 100 through 599;
- error code only when it matches a bounded stable-identifier grammar; and
- API pathname only after query and fragment removal, validation as a relative
  API pathname, and truncation to at most 160 characters.

Search text, ticker input, user content, query parameters, filesystem paths,
hosts, IP addresses, and URLs never appear in the displayed path field.

Free-text detail is untrusted. A new pure sanitizer must be fail-closed and
bounded. It must reject rather than partially clean any value containing or
resembling:

- credential/token/authorization material;
- traceback or stack content;
- SQL/database exception text;
- filesystem paths, URLs, hosts, or IP addresses;
- HTML or control characters; or
- over-limit input.

If safety cannot be proved, the presenter omits the detail and may show a
localized `detail omitted` diagnostic state. An implementation that cannot
establish a safe free-text class may return `null` for all arbitrary detail;
code/status/path still provide useful operator diagnostics. Raw text is never
the fallback.

The sanitizer receives an independent RED-first test file with adversarial
fixtures covering secrets, sqlite/traceback text, `/home/...` paths, IPs,
HTML/control characters, and long input.

### 4.4 Recovery routes use the existing dispatcher

Known structured failures may expose an actionable recovery route:

- `active_universe_unavailable` may navigate to `data_sources`;
- an explicit Seeking Alpha degraded/setup state may navigate to
  `data_sources`;
- an explicit News-storage state may navigate to `news_storage`; and
- a future typed Provider-configuration error may navigate to `providers`.

Routes use the existing `NavigationTarget` dispatcher and Settings exact-anchor
mechanism, including current dirty/busy guards and focus behavior. Explore does
not create a second navigation path.

Unknown status, plain text, or an HTTP status alone must not invent a recovery
destination. If an operation needs a semantic backend code that does not
exist, implementation stops for a reviewed DTO amendment; it does not infer a
code from English backend text.

### 4.5 Settings cleanup remains deferred

`settingsBackendCopy.diagnosticValue()` remains the reviewed I18N-2 behavior in
this unit even though it is less strict. Aligning Settings with the new
fail-closed sanitizer is an explicit follow-up, not silent I18N-3 expansion.

## 5. Locked Decision 3: Semantic IDs at Read Time

### 5.1 Translate closed system semantics

Known application-owned enums render through exhaustive typed presenters.
Examples include:

- tag facet labels;
- priority states;
- loading/degraded/content-availability states;
- Card confidence and status chrome;
- Assistant Stance and risk mismatch; and
- boolean traceability labels.

Storage, API requests, filtering, sorting, and comparisons continue to use the
stable IDs. Localized labels are display-only and are never parsed back into
domain state.

### 5.2 Preserve values and identifiers

Tag values, Watchlist names, source IDs, Provider/model names, tickers, evidence
IDs, and unknown stable IDs remain original. A known facet may display a
localized label while its value and source remain unchanged.

Unknown IDs follow the interaction contract of the owning surface:

- interactive/filterable IDs remain visible as their stable raw ID so two
  unknown values do not collapse into one indistinguishable option; and
- aggregation-only compatibility states may use an existing localized
  placeholder with raw ID restricted to Developer Mode.

These are complementary rules, not conflicting fallbacks.

### 5.3 One personalization owner

`personalizationDisplay.ts` remains the stable shared presenter path but loses
all embedded zh-Hant copy. It becomes locale-aware through a namespace-typed
`common` translator supplied by a reactive consumer.

The single owner covers:

- all seven Assistant Stance labels;
- all four risk-mismatch labels; and
- the complete trace summary, including stance, applied skills, and suggested
  skills chrome.

The corresponding leaves move byte-for-byte from `settings` into
`common.personalization`. Existing zh-Hant and English terminology is not
rewritten. Settings-specific stance effect explanations remain in `settings`.

Settings consumers, AICard, Research, and ResearchEvidenceDrawer all switch to
the shared owner in this unit. `Research.tsx` and
`ResearchEvidenceDrawer.tsx` are explicitly limited to the reactive
personalization-presenter connection; their remaining chrome stays owned by
I18N-4. English Research may therefore show the correct localized stance/trace
inside otherwise unmigrated chrome temporarily. That bounded mixed state is
known and accepted.

No presenter reads the i18next singleton internally. Each consumer subscribes
reactively with a hook and passes the correctly typed translator. Supplying an
`explore` translator to a `common` presenter, or the reverse, must fail
TypeScript compilation.

### 5.4 Shared tag display

`tags.tsx` similarly accepts a typed `explore` translator for known facet and
read-only chrome. It keeps:

- tag values;
- source identifiers;
- keys and editability logic; and
- filter values and CSS classes

unchanged. Locale switching changes labels/titles only and cannot change tag
filter results or removal authority.

## 6. Locked Decision 4: Locale Is a Pure Display Change

### 6.1 State that must survive

An in-place locale change preserves component identity and all current state,
including:

- the current Shell view, detail ticker, and Ticker Detail tab;
- Watchlist selection, archived toggle, sort, rename/create/add-member drafts,
  search results, and optimistic priority state;
- Universe query, list filter, tag filters, import result, and busy ticker;
- News mode, query input/applied query, ticker input/applied ticker, source,
  content filter, SA type, day window, loaded items, and pagination offset;
- Notes and tag drafts;
- AICard question, advanced controls, current Card, evidence, selected Card
  language, explicit translation result, save state, and modal state;
- in-flight requests and their request-generation guards;
- disclosure/open states; and
- keyboard focus and the current reading context.

No subtree may use `key={locale}` or another locale-derived remount mechanism.

### 6.2 Request boundary

The locale controller's own `PUT /profile/settings/ui-locale` is the only
request caused by changing locale. Explore data requests must not refire.
Changing locale must not:

- fetch Explore data;
- mutate lists, tags, notes, Universe, or Cards;
- generate or translate a Card;
- clear or restart in-flight work; or
- reset pagination, filters, drafts, or modal state.

A response that completes after the switch stores semantic data and renders
with the current locale. It must not preserve the locale that was active when
the request began.

### 6.3 Derived copy remains reactive

Any memoized value that contains localized copy includes the translator or
locale in its dependencies. At least one representative memoized display path
must be tested across an in-place switch.

Tests prove identity preservation with a marker on an existing node or input,
not merely equal text after a remount. Focus stays on the same control where
the control remains mounted.

Text reflow makes exact `scrollTop` equality inappropriate. The contract is
that code does not reset scroll: a seeded anchor remains in the reading
context and a nonzero scroll position does not jump to zero.

### 6.4 Structured outcomes, not translated state

Success and warning state stores semantic outcomes such as:

```text
{ kind: "universe_import_succeeded", importedCounts, groupsAvailable }
```

It does not store a sentence such as `匯入完成...`. Error state follows Section
4. A locale switch re-renders both success and failure messages immediately.

### 6.5 Formatter work is deferred

Existing date, timestamp, number, percentage, currency, and compact-count
formatters remain their current owners and inputs. I18N-3 does not replace them
with i18next formatting or add machine-locale dependence. A later I18N-6 or
separately reviewed formatter unit may decide whether any formatter should
become explicitly locale-aware.

## 7. Locked Decision 5: Per-Surface Hooks, Pure Presenters

### 7.1 Selected architecture

Each primary surface subscribes directly to the `explore` namespace with
`useTranslation`. Shared semantic presenters are pure functions that receive a
namespace-typed translator from the reactive caller.

This avoids both rejected alternatives:

- one giant Explore copy facade that couples unrelated surfaces; and
- App-level construction/prop-drilling of translated strings, which risks
  stale memoized props and makes locale reactivity indirect.

### 7.2 Resource ownership

- `explore` owns Home, Watchlist, Universe, News, Ticker Detail, AI Card, tag,
  and Explore error/outcome chrome.
- `common.personalization` owns stance, mismatch, and trace summary labels.
- `settings` keeps Settings-only explanations and controls.
- `research` keeps Slice 5's current/per-run personalization disclosure and
  later I18N-4 Research chrome.

Resources remain statically bundled, selector-typed, key-set equal, and
nonempty in both locales. Dynamic keys and source values in resource files are
forbidden.

### 7.3 App wiring

`App.tsx` remains the owner of `developerMode` and the generic navigation
dispatcher. It passes only those capabilities to Explore surfaces that need
them. It does not own Explore text.

The selected surfaces use existing navigation and focus behavior. No new
router, Settings anchor, event bus, or global error store is created.

### 7.4 Backend and API boundary

Backend `src/`, `data_sources/`, and backend `tests/` remain byte-identical.
Frontend API request/response behavior also remains unchanged unless
implementation discovers that a required semantic state lacks a stable code.

In that case work stops for a reviewed amendment. Frontend inference from
English backend text is never an acceptable substitute.

## 8. Locked Decision 6: Preserve Behavior, Repair Only Proven Layout Issues

### 8.1 Trigger semantics are frozen

Existing conditions that produce loading, empty, degraded, partial, success,
and error states remain bit-for-bit equivalent. Their application-owned copy
does migrate. "Behavior frozen" must never be used as a reason to leave a
single-language status string.

The following behavior remains unchanged:

- Home aggregate loading and Card opening;
- Watchlist landing-list selection, optimistic priority, archive, membership,
  and sort behavior;
- Universe source union, hidden veto, filters, import, and restore behavior;
- Market/Seeking Alpha News mode switching, search, day/source/content filters,
  append pagination, and degraded/empty distinction;
- Ticker Detail's four tabs and independent market-data legs;
- note and tag mutation rules;
- AI Card generation, persistence, traceability, and explicit translation;
  and
- all existing request-generation/stale-response guards.

### 8.2 No translation-by-truncation

English copy must remain semantically complete. The implementation may not
solve overflow by:

- reducing font size;
- clipping or ellipsizing required labels;
- replacing precise copy with unexplained abbreviations;
- shrinking touch targets; or
- hiding controls or state.

CSS remains unchanged unless a real measured overflow, overlap, or unstable
control dimension requires correction. Any such correction is a reviewed plan
deviation with RED-first coverage, an exact CSS hunk ledger, and a repeated
responsive matrix. It must use existing responsive/token patterns rather than
new magic breakpoint values.

### 8.3 Responsive matrix

Every migrated primary surface is exercised in both locales at:

- `1440x900`;
- `960x768`; and
- `390x844`.

Representative Explore workflows also run at:

- `1024x768`;
- `961x768`; and
- `959x768`.

Each surface's three required widths include its worst credible composition:

- long English chrome;
- full tag/facet chips where applicable;
- an error or degraded banner in the same viewport; and
- realistic long source content that remains unmodified.

If a particular surface overflows at `960px`, that surface must rerun a
`959/960/961` three-width matrix after repair.

No page-level horizontal overflow, clipped controls, incoherent overlap, or
broken focus name is allowed. Existing intentionally scrollable data regions
may remain scoped scroll containers; the document itself must not overflow.

## 9. Surface Contracts

### 9.1 Home

Home must cover loading, error, and empty states in both locales. Its workspace
load error becomes operation-specific chrome rather than interpolated raw
detail. Aggregate labels, table headings, Card actions, and modal chrome
localize. Tickers, list names, Card metadata, and Card content remain original.

Opening and closing a Card modal preserves focus behavior. Locale switching
while the modal is open does not reload the Card or close the modal.

### 9.2 Watchlist

Watchlist localizes list controls, empty states, table headings, priority
labels, action tooltips, archive/membership explanations, and outcome/error
chrome. It does not translate custom list names, symbol-search results, ticker
symbols, tag values, Provider consensus payloads, or stored notes.

The legacy priority action title is one reviewed copy correction:
`設定優先級` becomes `設定優先順序`, consistent with the terminology authority.
All other current zh-Hant Watchlist chrome follows the byte-preserving default
unless the implementation plan names another exact correction.

Changing locale preserves selection, sorting, all drafts, search results,
optimistic state, and current focus. It does not replay any mutation or reload
Universe/list data.

### 9.3 Universe

Universe displays one locale label, never the former translated-plus-English
duplicate pattern. Filters localize known facet/list chrome while preserving
filter values. Import and hide/restore outcomes are structured state and
re-render in the active locale.

The import outcome preserves all existing counts and the `groups_ok` warning
semantics. It does not put source tag names into resource strings. The
`active_universe_unavailable` code may offer the existing Settings exact-anchor
recovery route.

### 9.4 News

News localizes mode controls, filters, counts, loading/empty/degraded/error
states, content-availability chips, item-type labels, pagination controls, and
accessible names. It preserves:

- News titles, descriptions, snippets, tickers, source names, URLs, and
  publication timestamps;
- current Market versus Seeking Alpha query behavior;
- SQL-side content filtering and facet counts;
- `unknown` as distinct from `headline_only`; and
- terminal versus recoverable content wording.

An unavailable Seeking Alpha feed may offer a Data Sources recovery action.
The known missing-DB `available:true` empty/bad ambiguity remains deferred and
is not silently reclassified here.

### 9.5 Ticker Detail

Ticker Detail localizes its four tab names, table/section labels, loading and
partial-leg states, note/tag controls, and mutation outcomes. The ticker,
company/source data, financial values, statement row names supplied by the
backend, notes, and tag values remain original.

Independent market-data legs remain independent: one failure does not blank
successful IV, history, fundamentals, status, or coverage legs. The state
stores failed leg IDs and structured errors, not a preformatted joined string.

Locale switching preserves the active tab, day window, loaded legs, note/tag
drafts, and focus without data reload.

### 9.6 AI Card

AI Card localizes controls, headings, confidence/status labels, traceability
chrome, completeness labels, modal chrome, and operation-specific errors. It
does not translate Card prose, evidence, claims, notes, source types/IDs, or
other generated/source content through application i18n.

The explicit Card translation path is tested, not assumed. A fake-backed
responder or a bounded live call with typed fallback must exercise the flow;
the gate may not silently skip it. After a translation result exists, changing
application locale preserves the translated Card object, selected Card
language, and node identity without a second translation request.

## 10. File and Scope Boundaries

### 10.1 Fully migrated production files

The following eight existing files become literal-clean migrated scopes:

- `src/Home.tsx`;
- `src/Watchlist.tsx`;
- `src/Universe.tsx`;
- `src/News.tsx`;
- `src/TickerDetail.tsx`;
- `src/AICard.tsx`;
- `src/tags.tsx`; and
- `src/personalizationDisplay.ts`.

New pure Explore presenters live under `src/explore/**`, which also becomes one
migrated scope. Together with the current 30 entries, the reviewed architecture
therefore targets exactly 39 migrated-scope entries. If implementation needs a
different path shape, the plan must reconcile the count before code work.

### 10.2 Explicit bounded cross-surface adaptations

The file map may additionally modify:

- `src/App.tsx` for `developerMode` and existing navigation capability wiring;
- `src/Research.tsx` and `src/ResearchEvidenceDrawer.tsx` only for reactive
  shared-personalization presenter use;
- Settings copy/personalization consumers only to remove the duplicate
  stance/mismatch owner;
- `common`, `settings`, and new `explore` resource files and resource registry;
- focused tests;
- literal scanner manifests; and
- this authority, terminology, and priority-map documentation.

Research files are not added as fully migrated scopes in I18N-3. Their
remaining literals stay in the I18N-4 debt ceiling.

### 10.3 Protected boundaries

Absent a reviewed stop-and-amend event, implementation must prove byte
identity for:

- backend `src/`, `data_sources/`, and backend `tests/`;
- Portfolio/Holdings production surfaces;
- System/Dashboard production surfaces except unchanged App capability wiring;
- Settings CSS and unrelated Settings sections;
- desktop code;
- extensions; and
- package manifests and lockfiles.

No dependency is required.

CSS is protected by default. A measured and reviewed Decision 6 deviation may
open only the exact owning stylesheet and hunk.

## 11. Resource and Scanner Contract

### 11.1 Resource accounting

The implementation plan must record, per locale and subtree:

- all `explore` leaves added;
- all `common.personalization` leaves added;
- all duplicate Settings stance/mismatch leaves removed;
- any shared action leaf intentionally reused; and
- strict key-set equality and nonempty-string proof.

The current `713`-leaf Settings expectation must evolve by the exact removed
leaf count. Settings-only stance effects remain and are not swept into common.
The seven stance and four mismatch English values move byte-for-byte from their
current reviewed resource values. The terminology authority remains the copy
source.

### 11.2 Scanner accounting

The implementation plan starts from:

- candidates `1033`;
- signatures `973`;
- debt signatures `954`;
- allowlist `20`; and
- migrated scopes `30`.

All current debt entries belonging to the eight fully migrated files are
removed from the debt manifest rather than retained as stale ceiling entries.
This includes the 14 `personalizationDisplay.ts` signatures. The allowlist must
remain unchanged unless a separately justified stable-identifier entry is
reviewed; source/user content should normally stay as runtime values rather
than new code literals.

Task 0 of the implementation plan must run the scanner over the true branch
point and lock exact final candidate/signature/debt/allowlist counts. Local
arithmetic for one helper is not a substitute for the full scan.

## 12. Verification Contract

### 12.1 Pure presenter tests

Focused tests must cover:

1. every closed label in both locales;
2. unknown interactive IDs preserving distinct stable values;
3. tag values/source IDs remaining byte-identical;
4. complete stance/mismatch/trace mapping through the common owner;
5. exact existing zh-Hant and English stance/mismatch values;
6. operation-specific error copy for every operation family;
7. read versus mutation error distinction;
8. structured `ApiError` fields used without reading `.message`;
9. query/fragment removal and bounds on displayed API pathname;
10. invalid status/code/path omission;
11. adversarial free-text diagnostic rejection;
12. known recovery targets and unknown-code no-route behavior; and
13. structured success outcomes rendering in both locales.

### 12.2 Mounted surface tests

Because most primary Explore files currently lack direct mounted suites, the
plan must add or evolve focused tests that cover each surface family rather
than relying on App mocks.

Mounted tests include:

- one zh-Hant baseline-render contract per surface;
- one English render smoke per surface;
- no raw key exposure;
- planted source/user/generated strings preserved exactly;
- normal mode containing no planted traceback, sqlite, path, query, token, or
  backend diagnostic;
- Developer Mode showing the diagnostic owner and only safe metadata;
- exact Settings recovery navigation through the shared dispatcher;
- locale-switch node identity, focus, draft, filters, loaded data, and request
  count preservation;
- an in-flight response completing after locale switch in the new locale;
- a representative memoized label changing locale;
- nonzero reading position not reset;
- Home loading/error/empty;
- News Market/SA and content-availability states;
- Ticker independent-leg partial behavior; and
- AI Card explicit translation retained across locale switch.

### 12.3 Static gates

The plan includes mechanical gates for:

- no visible literal in all 39 migrated scopes;
- no dynamic translation key;
- no direct Explore rendering or interpolation of `.message` or raw
  `ApiError.diagnostic`;
- no parser of backend English text;
- no locale-keyed remount;
- no `ui_locale` in Card generation/translation payload or prompt code;
- no automatic translation call tied to locale;
- no source value in resource files;
- no new Settings/Research duplicate stance mapping;
- no new navigation path around `NavigationTarget`;
- no unreviewed CSS change; and
- all protected byte-identity boundaries.

### 12.4 Canonical commands and browser gates

The reviewed plan must run:

- exact focused frontend suites;
- full frontend tests;
- typecheck;
- production build;
- literal-policy check twice with identical output;
- backend byte-identity proof or, after a reviewed amendment, canonical A/B
  with an exact backend node ledger;
- no-PG smoke; and
- the Decision 6 responsive/interaction matrix in an isolated profile with
  scheduler disabled.

Any AI Card generation/translation smoke uses fake-backed deterministic data
unless a bounded live call is explicitly approved and recorded. No paid call
is required merely to prove localization wiring.

## 13. Implementation Sequence and Stop Conditions

### 13.1 Required implementation sequence

The later RED-first implementation plan should sequence work as follows:

1. ground exact baseline/resource/scanner/test ledgers;
2. add `explore` resources and typed test helpers;
3. build and test the pure error/outcome boundary;
4. converge common personalization and shared tag presenters;
5. migrate Home and its Card-modal seam;
6. migrate Watchlist and Universe;
7. migrate News;
8. migrate Ticker Detail and AI Card;
9. add App Developer/navigation wiring and bounded Research/Settings consumer
   adaptations at the owning task boundaries;
10. update scanner manifests atomically after owned files are clean;
11. run exact static/unit/full gates; and
12. run the bilingual responsive and state-preservation matrix.

Every intermediate product commit must keep the relevant focused suites,
typecheck, and resource parity green. The plan may choose a different commit
grouping only if it preserves those dependency boundaries and exact ledgers.

### 13.2 Stop conditions

Implementation stops for review if:

1. a required normal-mode classification needs parsing English backend text;
2. a missing stable code appears to require backend/DTO changes;
3. a source/generated value must enter resources to make the UI work;
4. locale switching requires data refetch, remount, or prompt changes;
5. a shared personalization owner cannot replace the Settings duplicate;
6. Research changes extend beyond the explicitly bounded presenter wiring;
7. a formatter must change;
8. a new dependency or runtime-loaded resource appears necessary;
9. an IA, route, filter, pagination, mutation, or domain-data change appears;
10. a CSS correction needs a new breakpoint or more than a narrow owning hunk;
11. the scanner cannot reach the reviewed exact counts with 39 scopes;
12. the public selector would need to render; or
13. any SA extension/backfill repair becomes entangled with News localization.

## 14. Deferred Work and Acceptance

### 14.1 Explicit deferred items

The following remain visible backlog items:

- align Settings diagnostics with the new fail-closed sanitizer;
- clean `App.tsx` sidecar-status raw `e.message` in I18N-5;
- decide locale-aware formatter behavior in I18N-6 or a later formatter unit;
- resolve `/sa/feed` missing-DB empty versus unavailable semantics;
- deliver the formal SA extension repair batch: packaging completeness gate,
  News Backfill control, degraded observability, and the outstanding
  27-article recovery ruling;
- normalize calibration Anthropic `stop_reason: "refusal"` into the typed
  refusal family; and
- revisit the calibration hard-coded model fallback when that path gains a
  registry.

None of these items blocks I18N-3, and none may be silently absorbed by it.

### 14.2 Acceptance checklist

I18N-3 is complete only when:

1. all eight owned files and `src/explore/**` are literal-clean migrated
   scopes;
2. all application chrome in the six surfaces renders correctly in both
   locales;
3. source/user/generated content remains byte-identical;
4. explicit Card translation remains user-triggered and survives locale
   switching;
5. no Explore normal path renders raw exception or backend detail;
6. Developer diagnostics expose only reviewed safe structural data and
   sanitized optional detail;
7. recovery actions use exact existing Settings anchors;
8. stance/mismatch/trace copy has one common owner and no Settings duplicate;
9. locale switching preserves identity, state, focus, in-flight work, and data
   request counts;
10. behavior triggers and data contracts are unchanged;
11. resource and scanner ledgers match the reviewed plan exactly;
12. the responsive matrix is green without truncating English;
13. backend, extensions, desktop, packages, and protected surfaces pass their
   byte gates; and
14. independent implementation review returns GREEN before merge.

The public locale selector remains absent after I18N-3. I18N-4 Research is the
next migration unit only after merged-tree closeout updates the priority map.
