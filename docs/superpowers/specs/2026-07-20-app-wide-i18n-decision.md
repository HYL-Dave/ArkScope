# ArkScope App-Wide i18n Decision

> **Status: WRITTEN DECISION APPROVED; I18N-0 FOUNDATION LIVE; I18N-1
> IMPLEMENTATION REVIEW-READY, 2026-07-20.**
> This document chooses the app-wide locale authority, runtime localization
> mechanism, migration sequence, public-switch gate, and verification contract.
> Independent written review returned GREEN. I18N-0 subsequently passed its
> separately reviewed implementation, canonical A/B, and merged-tree closeout.
> I18N-1 Shell + common UI is implemented at frozen product tip `5a76528d`;
> independent implementation review is the single next gate. I18N-2 and the
> public selector remain unopened.

## 1. Purpose and Authority

ArkScope targets two interfaces:

- Traditional Chinese with natural Chinese grammar and retained professional
  English where translation loses precision; and
- English.

The current product is predominantly Traditional Chinese source text without a
runtime locale layer. That state creates three separate problems:

1. visible copy, search metadata, and tests are coupled to source-language
   literals;
2. the browser and Electron surfaces have no shared locale authority; and
3. backend-owned labels, reasons, and raw details can bypass any future
   frontend translation layer.

This decision owns:

- supported locale identifiers and defaults;
- preference storage, bootstrap cache, failure behavior, and convergence;
- the frontend i18n library and resource/key architecture;
- the boundary between localized product copy and untranslated source data;
- migration batches and the public language-selector gate;
- backend-origin visible-copy treatment; and
- test, static-analysis, responsive, and accounting requirements.

Authority order:

1. [`ARKSCOPE_TERMINOLOGY.md`](../../design/ARKSCOPE_TERMINOLOGY.md) owns
   canonical terms and mixed-language copy policy.
2. This decision owns runtime locale mechanics and migration sequencing.
3. The P2.8 canonical shell and Slice 4.1 Settings designs continue to own
   layout, navigation, focus, workflow tabs, and Settings section ownership.
4. Domain specs continue to own financial, research, provider, data, and
   portfolio semantics. Localization must not change those semantics.

### 1.1 Grounded baseline

The written-decision baseline is merged `master` at `220e163`:

- frontend: `65 files / 636 tests` at the last merged Slice 4.1 verification;
- React `18.3.1`, TypeScript `5.5.4`, and Vite `5.4`;
- no runtime i18n dependency;
- `53` production `.ts`/`.tsx` files and `50` frontend test files currently
  contain CJK text;
- `index.html` says `lang="en"` even though the visible application is mostly
  Traditional Chinese;
- `profile_state.db` already contains the generic `profile_settings` key/value
  store and `ProfileStateStore.get_setting` / `set_setting` methods;
- Electron and browser local storage are separate origins and therefore cannot
  serve as a shared preference authority;
- Shell navigation and Settings registry labels are literal source strings;
  and
- generic frontend API failures currently append FastAPI `detail` text to an
  `Error.message`, while several DTOs also carry backend labels, reasons,
  warnings, and raw diagnostics.

These counts are grounding snapshots, not implementation acceptance constants.
Every implementation plan re-runs its own baseline and exact node ledger.

## 2. Goals and Non-Goals

### 2.1 Goals

The i18n line must:

1. establish one profile-level locale authority shared by Electron and browser;
2. render the cached locale synchronously on first paint without a language
   flash;
3. externalize product-owned user-visible messages into typed static resources;
4. preserve natural Traditional Chinese and professional English according to
   the terminology authority;
5. provide a complete English interface before exposing an English selector;
6. keep user/source content and stable identifiers intact rather than
   translating or re-keying them;
7. prevent backend raw text from bypassing localized normal-mode copy;
8. preserve current drafts, navigation, polling, focus, formatter semantics,
   and domain behavior while labels change; and
9. make coverage and completion mechanically verifiable rather than a visual
   impression.

### 2.2 Non-goals

This line does not:

- translate research answers, user prompts or notes, news/article content,
  provider content, model output, or imported documents;
- localize ticker symbols, model names, Provider names, series IDs, error
  codes, API field names, or other stable identifiers;
- introduce automatic OS/browser language detection;
- add live locale synchronization, polling, SSE, or cross-window messaging;
- replace existing financial, number, date, timezone, or market-session
  formatter ownership with i18next formatting;
- add a theme/density/interface Settings group in anticipation of future work;
- expose a disabled, partial, or planned language selector;
- redesign surfaces while translating them, except for narrowly reviewed
  copy-layout fixes required by the second locale; or
- promise that Developer Mode raw diagnostics are translated.

## 3. Locale and Copy Contract

### 3.1 Supported locales

The only V1 locale identifiers are:

```ts
type UiLocale = "zh-Hant" | "en";
```

`zh-Hant` is the first-run and fallback locale. `en` is accepted by the API and
runtime from the foundation slice onward even while the public selector is
absent. No read path silently normalizes a valid stored `en` value back to
`zh-Hant`.

The application does not inspect `navigator.language`, the OS locale, Electron
locale, timezone, or geolocation to choose a UI locale. Explicit profile state
wins over inference.

The root document language follows the active locale:

- `zh-Hant` -> `<html lang="zh-Hant">`;
- `en` -> `<html lang="en">`.

Both interfaces remain left-to-right.

### 3.2 Traditional Chinese is deliberately mixed professional language

Traditional Chinese resources use natural Traditional Chinese grammar. They do
not force translations of professional AI/finance terminology. `Provider`,
`OAuth`, `Agent`, `NAV`, `P&L`, `EBITDA`, `ETF`, `FRED`, model names, tickers,
and series IDs remain English where the terminology authority requires it.

Resources own complete messages rather than translated fragments. English
plural/grammar choices and Traditional Chinese counters belong to their locale
messages; components must not assemble a sentence by concatenating translated
words in a fixed source-language order.

This is not a bilingual-display mode. One label must not repeat the same concept
as `譯文 · Original`. English aliases belong in search metadata unless a
specific visible exception is documented.

### 3.3 Selector autonyms are one recorded exception

The future locale selector displays `繁體中文` and `English` as autonyms,
independent of the current locale. A user who selected the wrong language must
still recognize the return path. This is a documented exception under
`ARKSCOPE_TERMINOLOGY.md` §5, not general permission for parallel bilingual
labels.

## 4. Locale Authority and Convergence

### 4.1 One authority and one bootstrap cache

| Layer | Role | May decide the durable locale? |
| --- | --- | --- |
| `profile_state.db.profile_settings` | profile-level authority | yes |
| `localStorage["arkscope.ui.locale.v1"]` | per-origin first-paint cache | no |
| i18next runtime state | current render state | no |

The profile setting key is `ui_locale`. It uses the existing table and requires
no schema migration.

The localStorage value is allowlisted to `zh-Hant | en`. Missing, malformed,
unknown, unavailable, or exception-throwing storage is ignored. The cache is
write-through only:

- a successful authoritative DB read may update it;
- a successful DB write may update it; and
- no speculative, failed, or cache-only path may update it.

The cache is an exported bootstrap fact, not a second authority.

### 4.2 Profile API

The foundation slice adds key-specific profile routes rather than exposing the
generic settings bag:

```text
GET /profile/settings/ui-locale
PUT /profile/settings/ui-locale  { "locale": "zh-Hant" | "en" }
```

GET is a pure read. Missing preference returns `zh-Hant` with a stable
`source: "default"`; a valid stored preference returns `source: "stored"`.
PUT validates the allowlist, passes through `profile_state_write` under a named
`set_ui_locale` operation, writes `ui_locale`, and returns the stored value.

An invalid value already present in the DB is data corruption, not a third
locale. GET returns an HTTP 500 structured `invalid_ui_locale` error and does
not rewrite the row. The UI remains usable through §4.3 fallback, does not
overwrite its cache from that failed read, and a later valid PUT repairs the
preference.

Neither endpoint exposes arbitrary profile-setting keys.

### 4.3 First paint and authoritative correction

Before `createRoot`:

1. synchronously read the allowlisted cache;
2. fall back to `zh-Hant` when no valid cache is available;
3. synchronously initialize i18next with bundled resources;
4. set `document.documentElement.lang`; and
5. render once in that bootstrap locale.

After mount, the app reads the DB authority once:

- success with the same locale refreshes the write-through cache;
- success with a different locale changes runtime language, updates
  `<html lang>`, rerenders, and then updates the cache;
- failure keeps the bootstrap locale and does not block the app; and
- no loading screen or empty shell is introduced for locale retrieval.

The one rerender caused by authoritative correction is expected and is not
classified as a first-paint language flash.

The locale controller is StrictMode-safe and coalesces the startup read. All
read/write results carry a monotonic local request sequence. Once a newer user
write starts, an older startup GET result cannot change runtime language or
cache state. A slow stale response is ignored rather than treated as a new
authority observation.

### 4.4 User-initiated writes

Language selection is optimistic at the render-state level but not at the
cache-authority level:

1. retain the previous committed visible locale;
2. update i18next and `<html lang>` immediately;
3. send the validated PUT and prevent overlapping locale writes;
4. on success, keep the new locale and update the local cache;
5. on failure, restore the previous locale, leave the cache unchanged, and show
   a localized, honest error.

Changing locale does not navigate, invoke the Settings group guard, remount the
application, clear controlled values, or discard drafts. Product state remains
the same; only labels rerender.

Already captured transient copy such as a `dirtyReason` or blocked notice may
remain in the prior language until the next interaction. V1 accepts this
bounded case rather than turning product state into translatable message keys
mid-operation.

### 4.5 Cross-client convergence

V1 convergence occurs only:

- at application startup; and
- when that client successfully changes the locale in Settings.

Two simultaneously open clients do not poll each other or receive a push. A
client that did not make the change converges on its next start. This is an
explicit single-user tradeoff.

## 5. Runtime Mechanism

### 5.1 Selected stack

ArkScope uses:

- `i18next` for the resource runtime; and
- `react-i18next` for React bindings.

Both locale resources are static TypeScript modules bundled into the app.
There is no detector, backend loader, dynamic import, Suspense boundary, or
translation loading state. Initialization is synchronous (`initImmediate:
false` or an equivalent verified configuration).

The rejected alternatives are:

- FormatJS/React Intl: its descriptor/extraction and ICU-centered workflow add
  migration churn without replacing ArkScope's domain formatter contracts; and
- a custom dictionary/context runtime: it would make ArkScope own fallback,
  interpolation, pluralization, rich-text, and integration behavior already
  provided by a maintained library.

### 5.2 Resource layout and namespaces

The foundation begins with:

```text
src/i18n/
  index.ts
  locale.ts
  resources/
    zh-Hant/
      common.ts
      shell.ts
      settings.ts
    en/
      common.ts
      shell.ts
      settings.ts
```

Later surface slices add one bounded namespace each or extend an explicitly
owned existing namespace. Resource files include a header linking to
`ARKSCOPE_TERMINOLOGY.md` as translation authority.

Keys are semantic and stable, for example:

```text
shell.navigation.groups.explore
settings.groups.aiModels.title
settings.locale.writeFailed
common.states.partial
```

Source-language sentences are not keys.

### 5.3 Type and key discipline

The default resource type augments i18next so selectors are checked against the
canonical resource shape. V1 uses the typed selector API with
`enableSelector: "optimize"`; the implementation plan pins compatible package
versions rather than reopening this mechanism choice.

Dynamic translation-key construction is prohibited:

```ts
// prohibited
t(`states.${status}`)

// required
const STATE_KEYS = {
  partial: ($: TranslationSelector) => $.common.states.partial,
  failed: ($: TranslationSelector) => $.common.states.failed,
} as const;
```

An enum/domain mapping uses an explicit typed allowlist. No template string,
concatenation, backend string, or user value becomes a translation key.

For every namespace:

- `zh-Hant` and `en` have exactly equal recursive key paths;
- every leaf is a non-empty string;
- tests fail on a missing key;
- development logs a missing key; and
- production falls back to `zh-Hant` and must never render a raw key. The
  implementation plan must configure a safe missing-key result in addition to
  the build/test gates rather than relying on i18next's default key echo.

### 5.4 Interpolation and source values

Ticker symbols, model/Provider names, series IDs, error codes, counts, dates,
and user/source content enter localized sentences as interpolation values.
They never appear as dynamically generated resource keys and are not copied
into resources merely because an example contains them.

React remains responsible for escaping interpolated text. Rich messages must
use reviewed component interpolation; they must not add unsafe HTML rendering.

### 5.5 Search registries

Settings registry `title` and `description` become translation keys. Search
keywords remain explicit bilingual aliases and are searched independently of
the active locale. Changing to English must not make `總經` unsearchable;
changing to Traditional Chinese must not make `IBKR client id` unsearchable.

Visible search results use the active-locale title and description. Alias
keywords remain invisible unless the owning design explicitly presents them.

### 5.6 Formatter boundary

i18next owns messages, not financial or temporal semantics. Existing owner
functions continue to own:

- count and monetary formatting;
- signed percentages and P&L display;
- exchange/local timezone labels;
- market-session time anchoring; and
- domain-specific compact date/time strings.

String-externalization slices must not replace these with i18next formatting or
silently change precision, separators, sign rules, timezone, or day boundary.
Where a formatter legitimately needs locale awareness, its owning migration
slice adds an explicit `UiLocale` input and tests both locales. Hard-coded
formatter locales are inventoried before the public switch; changing them is a
formatter contract change, not incidental copy cleanup.

## 6. Backend-Origin Visible Copy

### 6.1 Classification

Every backend-origin string rendered in a reachable surface belongs to exactly
one class:

| Class | Examples | V1 treatment |
| --- | --- | --- |
| Stable identifier | ticker, model, Provider, series ID, error code | pass through unchanged |
| User/source content | notes, prompts, research answers, article title/body, provider quotation | pass through unchanged |
| Product-owned label | task/source/field label or description | frontend key selected by stable ID |
| Product-owned state/reason | blocked reason, setup state, schedule outcome, typed error | frontend key selected by stable code |
| Raw diagnostic | exception, `last_error`, provider response detail, internal path | Developer Mode only |
| Unknown product failure | unrecognized code or untyped transport failure | localized generic copy plus stable code; raw detail only in Developer Mode |

Frontend code must not infer a code by substring-matching an English backend
sentence. If a product-owned state lacks a stable ID/code, the owning slice adds
one while retaining any legacy text field only for compatibility/diagnostics.

### 6.2 Minimum existing inventory

The first implementation plans must account for at least these current paths:

| Surface/DTO family | Current backend text | Required landing |
| --- | --- | --- |
| Provider config | field `label`, `guard_reason`, setup `reason` | map `(provider, field)` and guard/setup code to frontend keys |
| Provider tests/health | `detail`, health `label`, `last_error` | localized state/action; raw detail only Developer Mode |
| Data Sources schedule | source `label`/`description`, `retired_reason`, run `reason`, `last_error`, `running_stale_reason` | source ID and reason-code maps; diagnostics separated |
| Model/task catalog | task/effort labels/descriptions, eligibility/discovery `warning` | stable task/model/reason IDs; source diagnostics separated |
| OAuth/credential flows | result `detail` and setup messages | stable result code with localized normal copy |
| Research | typed research error code plus sanitized message | retain typed frontend mapping; raw detail remains Developer Mode |
| News/content states | `empty_reason`, availability/recovery states | stable code mapping; article content remains source text |
| Portfolio/capture | run/issue code and message | stable code mapping; broker identifiers and values pass through |
| Generic API client | FastAPI `detail` appended to `Error.message` | typed `ApiError` envelope; no normal-mode direct raw-detail render |

The grounded normal-mode direct-error owners also include `App`, `Home`,
`Watchlist`, `Universe`, `News`, `TickerDetail`, `AICard`, `Holdings`,
`InvestorProfilePanel`, Research/history mutations, Portfolio activity/capture,
`Settings`, and its Data Sources/Data Storage/News Storage/Provider subsections.
Data Sources, Data Storage, News Storage, Runtime Limits, Model Routing, and
Provider login additionally render DTO `detail`, `warning`, `last_error`, or
`reason` fields directly today. `Dashboard` already limits the status message
to Developer Mode, and the typed Research error presenter is the preferred
positive pattern.

This is the baseline inventory, not permission to ignore other fields. Every
surface plan re-runs a DTO-to-render audit and adds newly found fields before
claiming coverage. The final release ledger lists every baseline owner above as
mapped, source-content-classified, Developer-Mode-gated, or removed.

### 6.3 Typed API error boundary

The current `responseErrorMessage()` behavior is transitional. The target API
client error carries structured fields such as status, code, path, and a
developer diagnostic separately. Normal-mode components choose localized copy
from stable code/status and must not render `e.message` when it contains raw
backend detail.

During migration, each surface converts its consumers under an exact test
ledger. The public selector gate remains closed until every reachable consumer
either:

- uses a stable frontend mapping;
- is explicitly classified as source/user content; or
- is gated to Developer Mode with localized normal-mode reason/action copy.

Planting a secret-like or source-language diagnostic in test fixtures and
proving it does not appear in normal mode is a required recurring boundary
test.

## 7. Migration Sequence

The migration is readers-first and selector-last. Both resources exist from
the foundation slice, but no incomplete public affordance is rendered.

### 7.1 Fixed sequence

| Unit | Scope | Status | Public selector |
| --- | --- | --- | --- |
| I18N-0 Foundation | dependencies, typed static resources, locale API, synchronous bootstrap/cache, `<html lang>`, test/static tooling | LIVE | absent |
| I18N-1 Shell + common UI | navigation, topbar, Drawer labels, background-work chrome, shared states/primitives used by Shell | NEXT | absent |
| I18N-2 Settings | PageHeader, workflow tabs, directory/registry, all reachable Settings sections, Settings backend-copy mappings | queued | absent |
| P2.8 Slice 5 | Investor Profile UX, implemented bilingual from birth against the new Settings/runtime contract | queued | absent |
| I18N-3 Explore | Home, Watchlist, Universe, News, Ticker Detail, AI card, related shared display helpers | queued | absent |
| I18N-4 Research | workspace, history, evidence, progress/errors, model-selection copy not already owned by Settings | queued | absent |
| I18N-5 Portfolio + System + residual | Holdings/overview/activity/capture, Dashboard/System, Markdown chrome, remaining reachable shared copy and formatter audit | queued | absent |
| I18N-6 Release | full coverage/audit, both-locale visual matrix, selector in Settings PageHeader, docs/Design Kit release sync | queued | visible |

I18N-0 through I18N-2 are the first migration tranche and remain separately
reviewed units; they are not one high-churn branch. Slice 5 follows that tranche
so its redesigned content does not create new monolingual debt. The priority
map names only the next unit at each closeout; this table does not authorize
parallel branches or dual `NEXT` entries.

The currently reachable Investor Profile panel is localized in I18N-2; it is
not left as a monolingual hole merely because Slice 5 will later improve it.
Slice 5 reuses, evolves, and explicitly retires those semantic keys under its
own exact ledger while adding all new copy in both locales.

### 7.2 New work during the migration window

After I18N-0, every new reachable surface or newly added product message ships
with `zh-Hant` and `en` keys in the same owning slice, even if that surface lies
outside the directory currently under migration. Existing debt is retired by
the units above; new debt is prohibited immediately.

### 7.3 Per-unit scope discipline

Each migration unit:

- externalizes only its owned surface plus shared keys it actually consumes;
- preserves domain behavior and data contracts except explicitly reviewed
  stable-code additions;
- does not perform unrelated IA or visual redesign;
- records exact resource-key and test-node changes;
- adds one English render smoke for every migrated surface family; and
- leaves no partially migrated public selector.

Unreachable historical components, archived fixtures, and tests are not made
reachable to satisfy localization. They are either removed by their owner or
listed in the exact non-product allowlist with evidence that normal navigation
cannot render them.

## 8. Public Selector Contract

### 8.1 Gate before affordance

Before I18N-6 passes, the language selector does not render. It is not disabled,
hidden behind a tooltip, or labeled planned. Runtime/API support for `en` is a
development and test capability until full coverage is proven.

### 8.2 Final owner and placement

The final selector is one compact labeled `<select>` in the Settings
`PageHeader` action slot, above the three workflow tabs.

- Traditional Chinese label: `介面語言`.
- English label: `Interface language`.
- Options always display the autonyms `繁體中文` and `English`.
- Settings PageHeader may contain app-level identity controls only and has
  exactly one in V1: interface language.

Language is not a workflow group and does not receive a fourth Settings tab.
It is also a low-frequency profile preference and does not occupy permanent
Shell topbar space.

The control is not a Settings registry entry. Registry entries require a real
section anchor; the PageHeader is always visible in Settings, so search for
`語言` need not fabricate an anchor or result.

### 8.3 Interaction

The selector follows §4.4 optimistic/revert behavior. While its write is in
flight it prevents a second selection. A failure restores the prior option and
shows localized error copy without exposing a raw exception.

It does not invoke Settings dirty/busy navigation guards because it does not
change workflow groups. Controlled field values, active tab, search query,
Drawer state, and drafts survive the locale rerender.

## 9. Mechanical Coverage Gates

### 9.1 Resource integrity

Every unit runs a recursive resource audit that proves:

- exact `zh-Hant == en` key-path equality;
- all leaves are non-empty strings;
- no duplicate semantic key has competing owners;
- no dynamic `t()` key construction exists; and
- no raw key is rendered in either locale smoke.

### 9.2 User-visible literal ratchet

Coverage is defined by tooling, not by screenshots alone. A TypeScript-aware
scanner inspects production `apps/arkscope-web/src/**/*.{ts,tsx}` and reports
locale-dependent user-visible literals, including JSX text and known visible
props such as `label`, `title`, `aria-label`, `placeholder`, `description`, and
normal-mode error/status copy.

The scanner excludes only:

- `*.test.*`;
- `src/i18n/resources/**`;
- generated/type-only files with no runtime UI; and
- exact entries in a reviewed non-localized allowlist for stable identifiers or
  documented source content.

It ignores comments and import paths. The allowlist records file, literal,
classification, and reason. It may shrink; adding an entry requires explicit
review and cannot be used for a translatable sentence.

Each completed unit adds its owned paths to a zero-new-literal ratchet. The
I18N-6 release evidence must show:

1. zero unclassified CJK literals outside resources;
2. zero unclassified locale-dependent English UI literals outside resources;
3. zero dynamic translation keys; and
4. no reachable monolingual namespace.

### 9.3 Backend-copy gate

Static source scanning cannot prove runtime DTO safety. Each unit therefore
also inventories the backend fields its surface renders and tests the §6
classification. Final release requires no reachable normal-mode path that
directly renders raw `detail`, `warning`, `last_error`, exception text, or an
assembled generic API `Error.message` without a reviewed source-content or
Developer Mode classification.

### 9.4 Selector absence/presence

- I18N-0 through I18N-5: a static and render test proves the selector is absent.
- I18N-6: the same contract flips to exactly one selector in the Settings
  PageHeader and nowhere else.

## 10. Verification and Accounting

### 10.1 Test strategy

Existing behavioral tests continue to assert rendered Traditional Chinese
copy with the test locale explicitly fixed to `zh-Hant`. They do not switch to
asserting resource keys.

English coverage is intentionally narrower but mandatory:

- exact resource key parity and non-empty values;
- at least one `en` render smoke per migrated surface family;
- no raw key in rendered English output;
- locale-change tests for state preservation and `<html lang>`; and
- final end-to-end coverage of all reachable views in both locales.

The full 636-test suite is not duplicated in English. Domain behavior remains
covered once; locale wiring and layout are covered at the translation boundary.

### 10.2 Foundation tests

I18N-0 must cover:

1. missing DB value -> `zh-Hant` default;
2. valid stored `zh-Hant` and `en`;
3. invalid stored value -> typed error without mutation;
4. PUT allowlist and `profile_state_write` gate;
5. cache missing/malformed/unknown/storage-throws paths;
6. cache first paint before React render;
7. DB correction updating runtime, document language, and cache;
8. DB read failure preserving cache/default without blocking;
9. optimistic PUT success and failure rollback;
10. a late startup GET not overriding a newer user PUT;
11. StrictMode/coincident startup reads being coalesced without cache drift;
12. no cache write before successful DB authority; and
13. no locale detector, resource fetch, Suspense, or dynamic import.

Backend work in I18N-0 requires canonical A/B accounting with exact added
nodes. Frontend-only units keep backend trees byte-identical unless their
reviewed plan explicitly adds a stable DTO code; such additions receive their
own backend ledger and A/B proof.

### 10.3 Per-unit ledger

Every implementation plan records:

- baseline frontend file/test counts at its true branch point;
- every added, removed, renamed, and evolved test node;
- resource keys added per namespace and locale;
- files entering the literal ratchet and any exact allowlist delta;
- backend endpoint/DTO changes, or byte-identity proof when none;
- formatter changes, or byte-identity proof when none; and
- visible-copy removals that cannot be hidden behind a net-positive test count.

### 10.4 Responsive and interaction gates

Every migrated surface is checked in both locales at minimum at:

- `1440x900`;
- `960x768`; and
- `390x844`.

Shell, Settings, and final release use the canonical six widths:

- `1440x900`;
- `1024x768`;
- `961x768`;
- `960x768`;
- `959x768`; and
- `390x844`.

Checks cover clipping, overlap, horizontal overflow, focus names, tab/Drawer
keyboard behavior, stable control dimensions, draft preservation, and exact
navigation. Font size is not reduced to make English fit.

Test behavior must not depend on the machine's browser, OS, or timezone locale.

## 11. Release, Rollback, and Compatibility

The foundation is additive:

- the DB uses an existing table;
- old application versions ignore `ui_locale`;
- both resources are bundled and require no network;
- a DB outage keeps the UI usable; and
- the selector remains absent until completion.

If a pre-selector unit must be reverted, no user-facing control has promised
English coverage. If I18N-6 must be rolled back, the stored locale remains valid
profile data; a prior bilingual build can read it, while a pre-i18n build simply
ignores it.

No migration deletes source/user content or rewrites historical records.

## 12. Documentation, Design Kit, and Priority Map

At decision adoption:

1. `ARKSCOPE_TERMINOLOGY.md` records the selector-autonym exception and remains
   the sole terminology table.
2. The canonical Product Spec links here for runtime locale mechanics rather
   than duplicating them.
3. Design Kit sync #5 remains the completed Slice 4.1/Tabs synchronization; it
   does not pre-render partial i18n screens.
4. I18N-6 owns a later Design Kit locale-control and bilingual-state sync after
   the product gate passes.
5. I18N-0 is LIVE; the priority map names I18N-1 Shell + common UI as the one
   next unit.
6. Slice 5 remains queued behind the Shell + Settings first tranche and then
   ships bilingual from birth.

Each implementation unit receives a separately reviewed plan. This decision
does not authorize combining all migrations into one branch.

## 13. Locked Decisions

No product-choice question remains before implementation planning.

Locked decisions are:

- locales `zh-Hant` and `en`, default/fallback `zh-Hant`;
- no OS/browser locale detection;
- profile DB authority under `ui_locale`;
- versioned localStorage first-paint cache, write-through only;
- fail-open read behavior and honest write rollback;
- startup and local-write convergence only;
- `i18next + react-i18next` with synchronous bundled TypeScript resources;
- no dynamic resource loading, Suspense, or dynamic translation keys;
- semantic typed keys with exact two-locale parity and non-empty values;
- existing tests remain Traditional-Chinese behavioral tests, with bounded
  English render smokes;
- i18next owns messages, not domain formatter semantics;
- stable identifiers and user/source content are not translated;
- backend product copy maps from stable IDs/codes, with raw diagnostics limited
  to Developer Mode;
- no public selector before mechanically complete app coverage;
- new work during migration is bilingual from birth;
- one compact autonym selector in the Settings PageHeader after release gate;
- no registry entry, fake anchor, fourth Settings tab, or topbar language
  control;
- fixed migration sequence with Shell + Settings first and Slice 5 immediately
  after that tranche; and
- exact resource, literal, DTO, test-ledger, and responsive gates before LIVE.
