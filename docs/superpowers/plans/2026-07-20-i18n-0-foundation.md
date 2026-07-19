# I18N-0 App-Wide Localization Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task by task. Use
> superpowers:using-git-worktrees before Task 0,
> superpowers:test-driven-development for every behavior change,
> superpowers:requesting-code-review before integration, and
> superpowers:verification-before-completion before any passing or complete
> claim. Steps use checkbox syntax for tracking.

> **Status:** CLEARED FOR IMPLEMENTATION — INDEPENDENT PLAN REVIEW GREEN,
> 2026-07-20
>
> The app-wide i18n decision received independent written-review GREEN at
> <code>ad53508</code>. Independent plan review subsequently returned GREEN
> with no must-fix. Product implementation is authorized only from the
> clearance commit created by this status transition and must stop at
> review-ready before merge.

**Goal:** Establish the additive I18N-0 foundation: one profile-backed locale
authority, synchronous cache-first rendering, typed bundled resources, a
StrictMode-safe locale controller, and a TypeScript-aware literal ratchet. Do
not translate an existing product surface and do not expose a language
selector.

**Architecture:** The existing <code>profile_settings</code> table owns one
key-specific <code>ui_locale</code> preference through two narrow profile
routes. A localStorage value is read synchronously before React starts but is
written only after a successful authoritative GET or PUT. A dependency-injected
locale controller serializes visible state, DB reconciliation, cache writes,
document language, optimistic writes, rollback, and stale-response rejection.
Static TypeScript resources initialize one bundled i18next instance without a
detector, loader, Suspense, or dynamic import. A standalone TypeScript-compiler
scanner snapshots existing visible-literal debt, rejects any increase, and
requires zero debt in explicitly migrated scopes.

**Tech Stack:** Python 3/FastAPI/Pydantic, existing SQLite
<code>ProfileStateStore</code>, React 18, TypeScript 5.9 as installed under the
existing 5.x range, i18next 26.3.6, react-i18next 17.0.10, Vitest 4/jsdom,
TypeScript compiler API, Vite/Electron, and canonical virgin-archive A/B
verification.

---

## Implementation Ledger

> Populate only in the isolated implementation worktree. No product behavior is
> merged until independent implementation review and explicit user approval.

| Item | Evidence |
|---|---|
| plan-review clearance commit | <code>2a35f1b08c94970086c51845f9a3b86718f096b2</code> |
| implementation worktree/base | <code>/tmp/arkscope-i18n-0-foundation</code> on <code>codex/i18n-0-foundation</code>, descended from <code>2a35f1b08c94970086c51845f9a3b86718f096b2</code>; product-behavior baseline remains <code>220e163</code> |
| Task 0 baseline | frontend <code>65 files / 636 tests</code>; backend collect <code>4562</code>; focused profile collect <code>47</code>; product diff against <code>220e163</code> empty; worktree clean |
| allowed-file baseline SHA-256 | <code>package.json faf1c3c5</code>; <code>package-lock.json aef24e35</code>; <code>profile.py 70f2a7e3</code>; <code>api.ts 0c6ae26b</code>; <code>main.tsx 96f910e2</code>; <code>index.html 67d560ce</code>; <code>vitest.config.ts be95d358</code> |
| typed-key mode selected | pending Task 2 probe: selector API preferred; standard typed dot-path is the sole pre-approved fallback |
| RED/GREEN commits | pending |
| backend node accounting | reviewed target <code>+7/-0</code>; collect <code>4562 -> 4569</code> |
| frontend node accounting | reviewed target <code>+44/-0</code>; <code>65 files / 636 tests -> 73 files / 680 tests</code> |
| resource ledger | exactly two non-empty keys per locale in I18N-0; no public-selector labels or autonyms |
| literal-ratchet ledger | pending deterministic debt snapshot count, migrated-scope list, exact allowlist count, and second-run equality proof |
| verification | pending focused/full/typecheck/build/A-B/static/runtime evidence |
| deviations | none authorized beyond the selector-typing fallback in Locked Decision 18 |
| independent implementation review | pending |
| merge/user verification | forbidden before independent implementation GREEN and user approval |

---

## Design Authority and Locked Decisions

1. Primary authority is
   <code>docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md</code>,
   status WRITTEN DECISION REVIEW APPROVED at <code>ad53508</code>.
2. <code>docs/design/ARKSCOPE_TERMINOLOGY.md</code> remains the only copy and
   terminology authority. This plan creates no parallel glossary.
3. I18N-0 is foundation only. Existing Shell, Settings, Research, Portfolio,
   News, and other visible copy remains byte-identical. No public language
   selector, disabled placeholder, hidden affordance, fourth Settings tab, or
   Shell control is rendered.
4. The only supported runtime values are <code>zh-Hant</code> and
   <code>en</code>. First-run and fallback locale is <code>zh-Hant</code>. The
   app never inspects browser, OS, Electron, timezone, or geolocation locale.
5. <code>profile_state.db.profile_settings["ui_locale"]</code> is the durable
   authority. Existing schema and generic store methods are reused; no schema
   migration, new table, generic settings API, or status-read mutation is
   allowed.
6. Backend routes are exactly:

   ~~~text
   GET /profile/settings/ui-locale
   PUT /profile/settings/ui-locale  {"locale":"zh-Hant"|"en"}
   ~~~

   GET returns <code>{"locale": value, "source": "default"|"stored"}</code>.
   PUT returns <code>{"locale": value, "source": "stored"}</code>.
7. Missing DB state is a pure-read <code>zh-Hant</code> default. An invalid
   stored value returns HTTP 500 with only stable
   <code>{"code":"invalid_ui_locale"}</code> detail, leaks no corrupt value,
   and does not rewrite the row.
8. PUT uses Pydantic allowlist validation, calls
   <code>require_profile_state_write("set_ui_locale", {"locale": value})</code>
   before writing, and never exposes an arbitrary profile-setting key.
9. <code>localStorage["arkscope.ui.locale.v1"]</code> is a write-through
    first-paint cache, not authority. Missing, malformed, unknown, unavailable,
    or throwing storage reads are ignored. One cache adapter owns a storage
    resolver and catches both property acquisition failures and
    <code>getItem</code>/<code>setItem</code> failures; main never dereferences
    <code>window.localStorage</code> outside that adapter.
10. Cache writes have one production owner: the locale controller. Bootstrap
    only reads. The controller writes cache only after a successful DB GET or
    successful DB PUT. Cache write failure cannot block the app or undo a
    successful authority operation.
11. Before <code>createRoot</code>, bootstrap synchronously chooses the valid
    cache value or <code>zh-Hant</code>, initializes bundled resources, updates
    <code>document.documentElement.lang</code>, and leaves no loading screen or
    empty shell.
12. Startup reconciliation is fail-open. A failed GET preserves the bootstrap
    locale, document language, and cache; it does not display a global failure
    or block normal app loading.
13. One controller instance coalesces coincident/StrictMode startup reads for
    its lifetime. Every authority operation has a monotonic sequence. A GET
    that started before a newer PUT can never alter runtime locale, committed
    state, or cache after that PUT begins, whether the PUT succeeds or fails.
14. A user write is optimistic in runtime/document state only. It blocks a
    second write. Success commits and updates cache. Failure restores the prior
    committed visible locale, keeps cache unchanged, and exposes only the
    stable code <code>write_failed</code>; no raw exception or dynamic
    translation key is put into controller state. A future visible consumer
    maps that code to <code>settings.locale.writeFailed</code> through one
    explicit typed allowlist.
15. Cross-client convergence is startup plus successful local write only.
    I18N-0 adds no polling, SSE, BroadcastChannel, storage-event authority,
    Electron IPC, or live push.
16. i18next and react-i18next resources are static TypeScript imports bundled
    in both locales. Initialization is synchronous. Detector plugins, backend
    loaders, network resource fetches, Suspense, and dynamic imports are
    forbidden.
17. Dependency versions are pinned exactly to i18next 26.3.6 and
    react-i18next 17.0.10. Registry grounding on 2026-07-20 confirmed
    react-i18next 17.0.10 requires i18next at least 26.2, React at least 16.8,
    and TypeScript 5/6/7.
18. Typed selector use with <code>enableSelector: "optimize"</code> is the
    preferred key style. Task 2 must prove it against the pinned declarations.
    If and only if those declarations cannot provide stable project typecheck,
    standard i18next typed dot-path calls such as
    <code>t("locale.writeFailed")</code> are the pre-approved mechanism-internal
    fallback. The implementation must remove selector-only config, use one
    style consistently, and record the failed probe and chosen mode. It does
    not reopen the architecture decision. Custom wrappers, untyped casts,
    relaxed compiler settings, or mixed key styles remain forbidden.
19. I18N-0 resource paths are exactly:

   | Namespace | Semantic key | zh-Hant | en |
   |---|---|---|---|
   | common | <code>i18n.missingTranslation</code> | <code>此文字暫時無法顯示。</code> | <code>This text is temporarily unavailable.</code> |
   | settings | <code>locale.writeFailed</code> | <code>無法儲存介面語言，已還原先前設定。</code> | <code>Could not save the interface language. The previous setting was restored.</code> |
   | shell | no leaves in I18N-0 | empty typed object | empty typed object |

   Resource headers link to the terminology authority. No selector labels or
   autonyms are prebuilt.
20. Recursive key paths must be exactly equal between locales and every leaf
    must be a non-empty string. Unknown keys log in development and return the
    locale-appropriate safe missing-copy string; production never echoes a raw
    key.
21. i18next owns messages only. Existing count, money, signed percentage, P&L,
    date/time, timezone, and market-session formatters remain byte-identical.
22. Translation keys are static semantic keys. Template construction,
    concatenation, backend/user values as keys, source-language sentences as
    keys, and mixed selector/dot-path use are prohibited. Stable identifiers
    remain interpolation values.
23. Existing tests continue to render with explicit <code>zh-Hant</code>
    setup. They continue asserting actual Traditional Chinese output, never
    resource keys. I18N-0 does not duplicate the 636-test suite in English.
24. The TypeScript-aware scanner is a standalone RED-first deliverable, not an
    incidental regex. It uses the installed TypeScript compiler API and has
    fixture-backed tests for JSX text, visible props, ARIA labels,
    placeholders, expression/template copy, normal-mode message sinks, and
    dynamic-key misuse.
25. Scanner candidates are normalized deterministic records with file,
    semantic kind, literal, and occurrence count. They include CJK and
    alphabetic English visible literals. In addition to known visible contexts,
    every CJK-bearing runtime string/template outside an explicitly structural
    AST context is conservatively reported, and return strings from presenter
    functions ending in Label, Description, Message, Reason, Text, or Title are
    reported. They do not use line numbers as identity.
26. The scanner has three distinct reviewed records:
    - a generated legacy-debt snapshot for translatable pre-I18N-0 literals;
    - a migrated-scope manifest whose candidate count must be zero, excluding
      resources and exact allowlisted non-localized content; and
    - an exact allowlist containing file, kind, literal, occurrence count,
      classification, and reason.
27. The only allowlist classifications are <code>stable_identifier</code> and
    <code>user_or_source_content</code>. Developer diagnostics are not a
    visible-copy exemption; they belong outside normal-mode visible sinks.
28. Debt is not an allowlist. Current findings may be a subset of the snapshot,
    but no signature or occurrence count may increase. A migrated scope cannot
    use debt. Allowlist entries must match a current finding exactly; stale,
    broad, duplicate, empty-reason, or translatable-sentence entries fail.
29. I18N-0 starts the migrated scope with <code>src/main.tsx</code> and
    <code>src/i18n/**</code>. Resources, declaration files, tests, and explicit
    test-support files are classified exclusions, not product debt. The exact
    non-localized allowlist starts empty unless implementation discovers a
    real stable identifier in a migrated scope; any addition is a stop and
    review event.
30. After I18N-0, every new visible product message is bilingual in the same
    owning slice. The checked-in debt snapshot and migrated-scope gate enforce
    this without pretending current legacy surfaces are already translated.
31. No implementation step may alter IA, navigation, CSS, responsive
    breakpoints, domain behavior, backend-origin copy policy, formatter output,
    API generic error behavior, or Design Kit artifacts.

---

## Grounded Baseline

- Plan-authoring head: <code>ad53508</code>, with clean product diff against
  <code>220e163</code>.
- Product behavior baseline: <code>220e163</code>. Commits
  <code>eb89bd1</code> and <code>ad53508</code> are documentation-only.
- Fresh frontend run on <code>ad53508</code>:

  ~~~text
  Test Files  65 passed (65)
  Tests       636 passed (636)
  ~~~

- Fresh backend collection on <code>ad53508</code>:

  ~~~text
  4562 tests collected
  ~~~

- Last independently reproduced merged backend family at the same product
  bytes: 29 failed / 4452 passed / 74 skipped / 18 warnings / 7 errors.
  Task 0 re-records the exact environment baseline before implementation;
  canonical acceptance is failure-set equality plus exactly seven added nodes.
- Current frontend source inventory: 76 non-test TypeScript/TSX files and 65
  Vitest files. There is no <code>src/i18n</code> or web scripts directory.
- <code>apps/arkscope-web/index.html</code> currently hardcodes
  <code>lang="en"</code>; <code>main.tsx</code> installs UI tokens and renders
  App directly.
- <code>vitest.config.ts</code> has no setup file. Existing component tests
  mount surfaces directly and rely on current Traditional Chinese literals.
- <code>ProfileStateStore.get_setting</code> and
  <code>ProfileStateStore.set_setting</code> already exist. The profile router
  already has a key-specific default-watchlist precedent and is mounted.
- <code>api.ts</code> already exposes key-specific profile GET/PUT helpers
  beside the default-watchlist functions.
- The repository has no i18next dependency, detector, translation backend,
  locale context, scanner, or locale preference key.
- Node is 22.14.0 and npm is 10.9.2. TypeScript resolves from the workspace as
  5.9.3 under the existing 5.x dependency range.

---

## Exact File Map

**Modify**

- <code>apps/arkscope-web/package.json</code>
- <code>package-lock.json</code>
- <code>src/api/routes/profile.py</code>
- <code>apps/arkscope-web/src/api.ts</code>
- <code>apps/arkscope-web/src/main.tsx</code>
- <code>apps/arkscope-web/index.html</code>
- <code>apps/arkscope-web/vitest.config.ts</code>
- this plan, implementation ledger only after clearance
- <code>docs/design/PROJECT_PRIORITY_MAP.md</code>, status entries only at
  review-ready and merge closeout

**Create: backend test**

- <code>tests/test_ui_locale_routes.py</code>

**Create: runtime**

- <code>apps/arkscope-web/src/i18n/locale.ts</code>
- <code>apps/arkscope-web/src/i18n/resources.ts</code>
- <code>apps/arkscope-web/src/i18n/i18next.d.ts</code>
- <code>apps/arkscope-web/src/i18n/index.ts</code>
- <code>apps/arkscope-web/src/i18n/bootstrap.ts</code>
- <code>apps/arkscope-web/src/i18n/localeController.ts</code>
- <code>apps/arkscope-web/src/i18n/LocaleProvider.tsx</code>
- <code>apps/arkscope-web/src/i18n/resources/zh-Hant/common.ts</code>
- <code>apps/arkscope-web/src/i18n/resources/zh-Hant/shell.ts</code>
- <code>apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts</code>
- <code>apps/arkscope-web/src/i18n/resources/en/common.ts</code>
- <code>apps/arkscope-web/src/i18n/resources/en/shell.ts</code>
- <code>apps/arkscope-web/src/i18n/resources/en/settings.ts</code>
- <code>apps/arkscope-web/src/test/setupI18n.ts</code>

**Create: frontend tests**

- <code>apps/arkscope-web/src/i18n/resources.test.ts</code>
- <code>apps/arkscope-web/src/i18n/locale.test.ts</code>
- <code>apps/arkscope-web/src/i18n/bootstrap.test.ts</code>
- <code>apps/arkscope-web/src/i18n/localeController.test.ts</code>
- <code>apps/arkscope-web/src/i18n/LocaleProvider.test.tsx</code>
- <code>apps/arkscope-web/src/UiLocaleApi.test.ts</code>
- <code>apps/arkscope-web/src/i18n/foundationBoundaries.test.ts</code>
- <code>apps/arkscope-web/src/i18n/visibleLiteralScanner.test.ts</code>

**Create: scanner/tooling**

- <code>apps/arkscope-web/scripts/i18n/visible-literal-scanner.mjs</code>
- <code>apps/arkscope-web/scripts/i18n/visible-literal-debt.json</code>
- <code>apps/arkscope-web/scripts/i18n/visible-literal-allowlist.json</code>
- <code>apps/arkscope-web/scripts/i18n/migrated-scopes.json</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/jsx-text.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/visible-props.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/aria-labels.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/placeholder.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/expression-template.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/message-sinks.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/ignored-contexts.tsx.txt</code>
- <code>apps/arkscope-web/scripts/i18n/fixtures/dynamic-keys.tsx.txt</code>

Anything outside this map is a stop condition except implementation-ledger and
priority-map status-only edits.

---

## Exact Test Ledger

### Backend: exactly +7/-0

File <code>tests/test_ui_locale_routes.py</code>:

1. <code>test_get_ui_locale_defaults_to_zh_hant_without_writing</code>
2. <code>test_get_ui_locale_returns_stored_zh_hant</code>
3. <code>test_get_ui_locale_returns_stored_en</code>
4. <code>test_get_ui_locale_rejects_corrupt_value_without_mutation_or_leak</code>
5. <code>test_put_ui_locale_accepts_both_supported_values</code>
6. <code>test_put_ui_locale_gates_before_writing</code>
7. <code>test_put_ui_locale_rejects_unknown_payload_without_writing</code>

No existing backend node is renamed, removed, or evolved.

### Frontend: exactly +44/-0

File <code>src/i18n/resources.test.ts</code>, +6:

1. <code>keeps locale namespace and recursive key paths identical</code>
2. <code>requires every resource leaf to be a non-empty string</code>
3. <code>initializes bundled zh-Hant resources synchronously</code>
4. <code>switches to bundled English without loading resources</code>
5. <code>returns localized safe copy instead of a raw missing key</code>
6. <code>supports exactly one reviewed typed translation-key style</code>

File <code>src/i18n/locale.test.ts</code>, +5:

1. <code>allowlists exactly zh-Hant and en</code>
2. <code>treats a missing cache entry as absent</code>
3. <code>ignores malformed and unknown cache values</code>
4. <code>ignores storage read exceptions</code>
5. <code>writes only valid locale values and tolerates cache write failure</code>

File <code>src/i18n/bootstrap.test.ts</code>, +3:

1. <code>applies a valid cached locale synchronously before returning</code>
2. <code>defaults synchronously to zh-Hant without a valid cache</code>
3. <code>never writes cache or fetches resources during bootstrap</code>

File <code>src/i18n/localeController.test.ts</code>, +9:

1. <code>authoritative GET corrects runtime document and cache</code>
2. <code>same-locale GET still refreshes the write-through cache once</code>
3. <code>GET failure preserves bootstrap truth and performs no cache write</code>
4. <code>PUT is optimistic but writes cache only after success</code>
5. <code>PUT failure rolls back and exposes only the stable error code</code>
6. <code>prevents overlapping locale writes</code>
7. <code>late startup GET cannot override a newer successful PUT</code>
8. <code>late startup GET cannot override rollback after a newer failed PUT</code>
9. <code>coalesces coincident and StrictMode-style startup reconciliation</code>

File <code>src/i18n/LocaleProvider.test.tsx</code>, +3:

1. <code>subscribes to controller state and reconciles once under StrictMode</code>
2. <code>exposes locale busy and stable error state without raw detail</code>
3. <code>locale changes rerender labels without remounting child state</code>

File <code>src/UiLocaleApi.test.ts</code>, +2:

1. <code>GETs the key-specific ui-locale route</code>
2. <code>PUTs only the validated locale field to the key-specific route</code>

File <code>src/i18n/foundationBoundaries.test.ts</code>, +6:

1. <code>bootstraps locale before createRoot and mounts both providers</code>
2. <code>uses zh-Hant as the static document fallback</code>
3. <code>fixes the Vitest default locale to zh-Hant</code>
4. <code>uses no detector loader Suspense or dynamic resource import</code>
5. <code>renders no language selector autonym or planned locale affordance</code>
6. <code>keeps bootstrap reads separate from authority reconciliation and cache writes</code>

File <code>src/i18n/visibleLiteralScanner.test.ts</code>, +10:

1. <code>detects and normalizes JSX text through the TypeScript AST</code>
2. <code>detects label title description and alt props</code>
3. <code>detects aria-label and ariaLabel props</code>
4. <code>detects placeholder props</code>
5. <code>detects visible expression and template copy</code>
6. <code>detects visible objects message sinks presenter returns and conservative CJK runtime literals</code>
7. <code>ignores comments import paths tests resources and declarations</code>
8. <code>rejects dynamic keys while accepting the one reviewed typed key style</code>
9. <code>requires exact current allowlist entries and rejects stale entries</code>
10. <code>allows legacy debt only to shrink and requires zero in migrated scopes</code>

No existing frontend node is renamed, removed, or evolved. Any raw removal is a
stop condition, even if the net count remains positive.

### Cumulative accounting

| Checkpoint | Frontend files/tests | Backend collect |
|---|---:|---:|
| baseline | 65 / 636 | 4562 |
| Task 1 locale routes | 65 / 636 | 4569 |
| Task 2 typed resources | 66 / 642 | 4569 |
| Task 3 cache/bootstrap | 68 / 650 | 4569 |
| Task 4 API/controller/provider | 71 / 664 | 4569 |
| Task 5 app integration/boundaries | 72 / 670 | 4569 |
| Task 6 scanner | 73 / 680 | 4569 |

The file count counts Vitest files, not production modules or scanner fixtures.

---

## Task 0: Plan Clearance, Worktree, and Re-grounding

**Files:**
- Modify this plan status/ledger only after independent plan GREEN.
- Do not change product files in this task.

- [x] **Step 1: Record plan clearance**

  After independent review GREEN, change status to CLEARED FOR IMPLEMENTATION,
  commit that docs-only change, and record the full commit as
  <code>PLAN_REVIEW_CLEARANCE_COMMIT</code>. The implementation branch must
  descend from that commit. Keep <code>220e163</code> separately as
  <code>PRODUCT_BEHAVIOR_BASE</code>.

- [x] **Step 2: Create an isolated worktree**

  Use the established linked-worktree mechanism and branch name
  <code>codex/i18n-0-foundation</code>. Copy only the existing git-crypt key
  into linked Git metadata if required. Do not copy databases, tokens, browser
  profiles, node_modules, or dirty files.

- [x] **Step 3: Re-run baselines before RED**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run
  pytest --collect-only -q
  pytest --collect-only -q tests/test_profile_state.py
  git diff --exit-code 220e163 -- src data_sources tests apps package.json package-lock.json extensions
  git status --short
  ~~~

  Expected: frontend 65/636, backend collect 4562, focused profile collection
  47, empty product diff, and clean worktree. Record the existing backend
  failure family from the latest canonical merged evidence; do not run the
  full five-minute baseline twice unless the reviewer requests it.

- [x] **Step 4: Protect scope**

  Record SHA-256 for every allowed-to-change existing product file and a
  name-only diff baseline. Any pre-existing user change is a stop condition;
  this plan has no dirty-file accommodation.

---

## Task 1: Add the Key-Specific Locale API

**Files:**
- Create <code>tests/test_ui_locale_routes.py</code>
- Modify <code>src/api/routes/profile.py</code>

- [ ] **Step 1: Write all seven route tests first**

  Use direct handler calls and temporary <code>ProfileStateStore</code>
  instances; do not use TestClient. For the invalid stored-value test, plant a
  value such as <code>fr</code>, assert HTTP 500 detail equals only
  <code>{"code":"invalid_ui_locale"}</code>, and prove the row is unchanged.
  For the gate-order test, use an event-recording fake permission function and
  store so the required order is <code>permission -> set_setting</code>.

- [ ] **Step 2: Run RED**

  ~~~bash
  pytest -q tests/test_ui_locale_routes.py
  ~~~

  Expected: collection/import failure because the body model, constants, and
  handlers do not exist. A failure caused by TestClient startup, real DB access,
  or an unrelated route is invalid RED.

- [ ] **Step 3: Implement the narrow route contract**

  Add one key constant, one two-value allowlist, one Pydantic body model, a pure
  GET handler, and a gated PUT handler beside the default-watchlist precedent.
  Do not modify <code>ProfileStateStore</code>.

  The implementation shape is:

  ~~~python
  UI_LOCALE_KEY = "ui_locale"
  UI_LOCALES = frozenset({"zh-Hant", "en"})

  class UiLocaleBody(BaseModel):
      locale: Literal["zh-Hant", "en"]
  ~~~

  GET must validate stored state at runtime rather than trust historical DB
  contents. PUT validation occurs before the permission gate; the gate occurs
  before the store write.

- [ ] **Step 4: Run GREEN and accounting**

  ~~~bash
  pytest -q tests/test_ui_locale_routes.py
  pytest --collect-only -q tests/test_ui_locale_routes.py
  pytest --collect-only -q
  ~~~

  Expected: 7/7 and backend collect 4569, with no existing node removed.

- [ ] **Step 5: Commit**

  Commit only the route and seven tests with message
  <code>feat: add profile ui locale routes</code>.

---

## Task 2: Pin Dependencies and Build Typed Static Resources

**Files:**
- Modify <code>apps/arkscope-web/package.json</code>
- Modify <code>package-lock.json</code>
- Create resource modules, <code>resources.ts</code>,
  <code>i18next.d.ts</code>, <code>index.ts</code>, and
  <code>resources.test.ts</code>

- [ ] **Step 1: Install exactly the reviewed versions**

  ~~~bash
  npm install --save-exact i18next@26.3.6 react-i18next@17.0.10 --workspace apps/arkscope-web
  npm ls i18next react-i18next
  ~~~

  The web manifest must contain exact versions without caret or tilde. No
  detector, backend, ICU, extraction, or localization package may appear.

- [ ] **Step 2: Write six resource tests**

  Tests must recursively flatten both locale trees, compare namespace and key
  sets, reject empty/whitespace leaves, prove immediate translations in both
  locales, and prove an unknown key never echoes its key.

  The sixth node is also the compile-time type probe. First write it using the
  selector callback style and <code>enableSelector: "optimize"</code>. Do not
  cast the translation function or resource tree.

- [ ] **Step 3: Run RED**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run src/i18n/resources.test.ts
  npm run typecheck --workspace apps/arkscope-web
  ~~~

  Expected: missing resource/runtime modules. Once the modules exist, the type
  probe must independently settle the selector decision.

- [ ] **Step 4: Apply the selector advisory exactly once**

  Preferred GREEN is selector mode. If pinned selector declarations fail a
  minimal known-key compile probe, record the exact compiler diagnostic and
  convert the probe plus runtime calls to standard typed dot paths. Remove
  <code>enableSelector</code> rather than leaving dead config. Do not try a
  third form and do not mix styles.

- [ ] **Step 5: Implement resources and runtime initialization**

  Both locales export the exact two-key ledger above. The Shell namespace is an
  intentionally empty typed object. Build a static resource object and one
  i18next type augmentation. Initialization must set:

  - supported languages to exactly <code>zh-Hant</code> and <code>en</code>;
  - fallback and initial default to <code>zh-Hant</code>;
  - synchronous initialization;
  - React binding without Suspense;
  - safe missing-key output and development logging; and
  - <code>interpolation.escapeValue: false</code>, because React owns output
    escaping and unsafe HTML rendering remains forbidden.

- [ ] **Step 6: Run GREEN and inspect dependency diff**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run src/i18n/resources.test.ts
  npm run typecheck --workspace apps/arkscope-web
  git diff -- apps/arkscope-web/package.json package-lock.json
  ~~~

  Expected: 1 file / 6 tests. Lockfile changes must be limited to the two
  reviewed packages and their actual resolved metadata.

- [ ] **Step 7: Commit**

  Commit dependency and resource foundation together with message
  <code>feat: add typed bundled i18n resources</code>. Record selector or
  dot-path mode in the ledger.

---

## Task 3: Implement Cache and Synchronous Bootstrap

**Files:**
- Create <code>src/i18n/locale.ts</code>
- Create <code>src/i18n/bootstrap.ts</code>
- Create <code>src/i18n/locale.test.ts</code>
- Create <code>src/i18n/bootstrap.test.ts</code>

- [ ] **Step 1: Write eight tests**

  Use an injected storage resolver returning
  <code>Pick&lt;Storage, "getItem"|"setItem"&gt; | null</code>, an injected
  document element, and an isolated i18next instance. Cache values are the raw
  exact locale identifiers, not JSON. Test missing, empty/whitespace, raw
  unknown values, resolver/property acquisition exceptions, method exceptions,
  both valid values, and call ordering.

  The first bootstrap test must assert language, translated known key, and
  <code>lang</code> immediately after the synchronous function returns. Waiting
  a microtask would not prove the first-paint contract.

- [ ] **Step 2: Run RED**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/locale.test.ts \
    src/i18n/bootstrap.test.ts
  ~~~

  Expected: missing cache/bootstrap modules.

- [ ] **Step 3: Implement one locale owner**

  <code>locale.ts</code> owns:

  - <code>UiLocale</code>;
  - <code>SUPPORTED_UI_LOCALES</code>;
  - <code>UI_LOCALE_CACHE_KEY</code>;
  - runtime validation;
  - one cache adapter with exception-safe storage resolution/read; and
  - exception-safe cache write returning success/failure only for diagnostics.

  It must not import React, API functions, or Settings.

- [ ] **Step 4: Implement bootstrap**

  Bootstrap reads cache exactly once, applies valid cache or
  <code>zh-Hant</code> through the initialized i18next instance, updates the
  root <code>lang</code>, and returns the chosen locale. It must not write
  storage, call fetch, create a controller, or read DB authority.

- [ ] **Step 5: Run GREEN and commit**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/locale.test.ts \
    src/i18n/bootstrap.test.ts
  npm run typecheck --workspace apps/arkscope-web
  ~~~

  Expected: 2 files / 8 tests. Commit as
  <code>feat: add synchronous locale bootstrap</code>.

---

## Task 4: Add API Client, Monotonic Controller, and React Provider

**Files:**
- Modify <code>apps/arkscope-web/src/api.ts</code>
- Create <code>src/i18n/localeController.ts</code>
- Create <code>src/i18n/LocaleProvider.tsx</code>
- Create <code>src/UiLocaleApi.test.ts</code>
- Create <code>src/i18n/localeController.test.ts</code>
- Create <code>src/i18n/LocaleProvider.test.tsx</code>

- [ ] **Step 1: Write two API tests**

  Stub fetch and prove the exact GET path, PUT method, JSON content type, and
  body containing only <code>locale</code>. No generic setting key may enter the
  frontend function signature.

- [ ] **Step 2: Write nine controller tests with deferred promises**

  Construct a fake adapter with:

  ~~~ts
  type UiLocaleAuthority = {
    get(): Promise<UiLocaleResponse>;
    put(locale: UiLocale): Promise<UiLocaleResponse>;
  };
  ~~~

  Inject runtime apply, cache write, and authority functions. Use deferred GET
  and PUT promises to prove both stale-response cases, not fake resolved
  ordering.

- [ ] **Step 3: Write three provider tests**

  Mount a probe under StrictMode. The state-preservation node keeps a child
  counter/input value across a locale update and proves the child was not
  remounted. The provider exposes state and command through context only; it
  renders no control or status copy.

- [ ] **Step 4: Run RED**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/UiLocaleApi.test.ts \
    src/i18n/localeController.test.ts \
    src/i18n/LocaleProvider.test.tsx
  ~~~

  Expected: missing client functions, controller, and provider.

- [ ] **Step 5: Implement API functions**

  Add type-only <code>UiLocale</code> import to <code>api.ts</code> and runtime
  response validation in the controller boundary. A malformed success payload
  is treated as a failed authority read/write; it never becomes a locale.

- [ ] **Step 6: Implement the controller state machine**

  State is limited to:

  ~~~ts
  type UiLocaleState = {
    locale: UiLocale;
    busy: boolean;
    errorCode: "write_failed" | null;
  };
  ~~~

  Keep committed visible locale and operation sequence private. Startup
  reconciliation is single-flight and one-shot per controller lifetime.
  Cache-write exceptions are swallowed after authority success. Raw caught
  objects never enter state, events, logs intended for normal UI, or context.

- [ ] **Step 7: Implement provider**

  Use <code>useSyncExternalStore</code> or an equivalent subscription that is
  safe under concurrent React. The effect calls one-shot reconciliation.
  Context exposes current state and <code>setLocale</code> for later slices,
  but no production consumer is added in I18N-0. It does not call
  <code>t(state.errorCode)</code>; the dynamic-key prohibition remains
  absolute.

- [ ] **Step 8: Run GREEN and commit**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/UiLocaleApi.test.ts \
    src/i18n/localeController.test.ts \
    src/i18n/LocaleProvider.test.tsx
  npm run typecheck --workspace apps/arkscope-web
  ~~~

  Expected: 3 files / 14 tests. Commit as
  <code>feat: add monotonic locale controller</code>.

---

## Task 5: Integrate Before First Paint and Fix Test Locale

**Files:**
- Modify <code>apps/arkscope-web/src/main.tsx</code>
- Modify <code>apps/arkscope-web/index.html</code>
- Modify <code>apps/arkscope-web/vitest.config.ts</code>
- Create <code>apps/arkscope-web/src/test/setupI18n.ts</code>
- Create <code>apps/arkscope-web/src/i18n/foundationBoundaries.test.ts</code>

- [ ] **Step 1: Write all six boundary tests**

  Static tests may read source, but must assert semantic order rather than
  whitespace. The selector-absence node scans production App, Shell, Settings,
  and i18n provider code while excluding resources/tests. It proves there is no
  label, autonym pair, locale select, disabled placeholder, or fourth workflow
  tab.

- [ ] **Step 2: Run RED**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/foundationBoundaries.test.ts
  ~~~

  Expected failures include wrong static <code>lang</code>, no bootstrap before
  <code>createRoot</code>, no providers, and no test setup.

- [ ] **Step 3: Integrate in strict order**

  Main performs:

  1. UI token installation;
  2. synchronous locale bootstrap;
  3. root lookup;
  4. one controller construction;
  5. React root creation; and
  6. StrictMode render with I18nextProvider and LocaleProvider around App.

  Set static HTML fallback to <code>zh-Hant</code>. Do not make
  <code>main.tsx</code> async and do not wait for DB before render.

- [ ] **Step 4: Establish deterministic test locale**

  Add one Vitest setup file that initializes/reset the singleton to
  <code>zh-Hant</code> before each test without clearing product state or
  changing timezone. Existing tests must require no source edits.

- [ ] **Step 5: Run focused then full GREEN**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/resources.test.ts \
    src/i18n/locale.test.ts \
    src/i18n/bootstrap.test.ts \
    src/i18n/localeController.test.ts \
    src/i18n/LocaleProvider.test.tsx \
    src/UiLocaleApi.test.ts \
    src/i18n/foundationBoundaries.test.ts
  npm test --workspace apps/arkscope-web -- --run
  npm run typecheck --workspace apps/arkscope-web
  ~~~

  Expected checkpoint: 72 files / 670 tests. All pre-existing 65/636 nodes
  remain.

- [ ] **Step 6: Commit**

  Commit as <code>feat: bootstrap locale before React render</code>.

---

## Task 6: Build the TypeScript-Aware Visible-Literal Ratchet

**Files:**
- Modify <code>apps/arkscope-web/package.json</code> to add
  <code>check:i18n-literals</code>
- Create scanner, manifests, fixtures, debt snapshot, and
  <code>visibleLiteralScanner.test.ts</code>

- [ ] **Step 1: Write eight fixture files before scanner code**

  Fixtures are source text with a non-compiled suffix. Each positive fixture
  contains one narrowly named category plus near-miss code. The ignored fixture
  contains comments, import paths, test/resource/declaration paths, stable
  non-visible constants, and punctuation-only JSX.

- [ ] **Step 2: Write all ten scanner tests**

  Invoke the real Node CLI with <code>process.execPath</code>; do not reimplement
  scanner logic in tests. Parse its JSON output and compare deterministic
  records. The final two nodes use temporary manifests to prove stale
  allowlists fail, legacy counts can only decrease, a new literal/count fails,
  and migrated scopes reject even snapshotted debt.

- [ ] **Step 3: Run RED**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/visibleLiteralScanner.test.ts
  ~~~

  Expected: all nodes fail because the CLI is absent. A regex-only partial
  script is not accepted as intermediate GREEN.

- [ ] **Step 4: Implement AST candidate extraction**

  Use <code>typescript.createSourceFile</code> with TSX parsing. Detect:

  - normalized non-empty JSX text;
  - string/template content in JSX expression children;
  - string/template content in visible JSX attributes;
  - object properties named label, title, description, alt, placeholder,
    aria-label/ariaLabel, caption, helperText, emptyMessage, errorMessage,
    statusText, or tooltip;
  - string/template arguments to normal-mode message setters such as
    setErr/setError/setNotice/setWarning/setMessage/setBlockedReason; and
  - every CJK-bearing runtime literal/template outside imports, property keys,
    type-only declarations, tests, resources, and other explicitly structural
    contexts, plus return strings from presenter functions whose names end in
    Label/Description/Message/Reason/Text/Title; and
  - non-static translation-key construction at reviewed translation call
    sites.

  Report CJK or alphabetic English candidates; ignore whitespace and
  punctuation-only content. Ignore comments/import specifiers by AST context,
  not by deleting source text. Resolve translation calls from i18next instance
  imports and <code>useTranslation</code> destructuring; do not classify every
  unrelated function named <code>t</code> as a translation function.

- [ ] **Step 5: Implement deterministic policy checking**

  CLI modes are:

  ~~~text
  scan <path...>          emit sorted JSON candidates
  snapshot                emit/write the legacy debt inventory
  check                   apply exclusions, exact allowlist, debt ceiling,
                          migrated-scope zero rule, and dynamic-key rule
  ~~~

  The package script runs <code>check</code> from the web workspace root.
  Validation fails on malformed manifests, duplicate signatures, stale
  allowlist entries, classifications other than
  <code>stable_identifier</code>/<code>user_or_source_content</code>, empty
  reasons, debt increases, candidate debt in migrated scopes, dynamic keys, or
  nondeterministic output.

- [ ] **Step 6: Generate and review the one-time debt snapshot**

  Run snapshot against all production
  <code>src/**/*.{ts,tsx}</code>, excluding only:

  - test files;
  - <code>src/i18n/resources/**</code>;
  - <code>*.d.ts</code>;
  - <code>src/test/**</code>; and
  - generated/type-only files proven to have no runtime UI.

  Write sorted signatures/counts to
  <code>visible-literal-debt.json</code>. Initialize exact allowlist entries to
  an empty array. Initialize migrated scopes to <code>src/main.tsx</code> and
  <code>src/i18n/**</code>. Record candidate/signature totals in the ledger.

  Review the diff for accidental tests, resources, import paths, comments,
  secrets, or machine-specific paths. Those are scanner defects, not allowlist
  candidates. Source/user-content-shaped literals already present in product
  code remain debt until their owning surface explicitly classifies them; do
  not silently promote them into the foundation allowlist.

  Also compare the scanner's CJK-bearing file set with a broad
  <code>rg -l</code> inventory. Every production file present only in the broad
  inventory must be explained by comments, imports, type-only declarations, or
  another exact structural exclusion. An unexplained file is a scanner defect
  and stop condition, not acceptable baseline debt.

- [ ] **Step 7: Prove deterministic equality and GREEN**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/visibleLiteralScanner.test.ts
  sha256sum apps/arkscope-web/scripts/i18n/visible-literal-debt.json
  npm run check:i18n-literals --workspace apps/arkscope-web
  npm run check:i18n-literals --workspace apps/arkscope-web
  sha256sum apps/arkscope-web/scripts/i18n/visible-literal-debt.json
  ~~~

  The two hashes must be identical: check mode cannot rewrite or reorder the
  snapshot. Expected focused result: 1 file / 10 tests.

- [ ] **Step 8: Commit**

  Commit scanner, fixtures, manifests, snapshot, test, and package script as
  <code>test: enforce visible localization debt</code>.

---

## Task 7: Canonical Verification and Runtime Smoke

**Files:**
- Modify no product file unless a reviewed test exposes a defect.
- Update implementation ledger with commands and exact outputs.

- [ ] **Step 1: Run exact focused gates**

  ~~~bash
  pytest -q tests/test_ui_locale_routes.py
  npm test --workspace apps/arkscope-web -- --run \
    src/i18n/resources.test.ts \
    src/i18n/locale.test.ts \
    src/i18n/bootstrap.test.ts \
    src/i18n/localeController.test.ts \
    src/i18n/LocaleProvider.test.tsx \
    src/UiLocaleApi.test.ts \
    src/i18n/foundationBoundaries.test.ts \
    src/i18n/visibleLiteralScanner.test.ts
  ~~~

  Expected: backend 7, frontend 8 files / 44 tests.

- [ ] **Step 2: Run full frontend gates**

  ~~~bash
  npm test --workspace apps/arkscope-web -- --run
  npm run typecheck --workspace apps/arkscope-web
  npm run build --workspace apps/arkscope-web
  npm run check:i18n-literals --workspace apps/arkscope-web
  ~~~

  Expected: 73 files / 680 tests; clean typecheck; successful build with only
  the pre-existing chunk-size warning.

- [ ] **Step 3: Prove exact node accounting**

  Compare sorted <code>vitest list</code> output from virgin archives of
  <code>220e163</code> and product tip using the same node_modules. Required
  comm result is exactly +44/-0 with the distribution in this plan. Compare
  backend node IDs similarly; required result is +7/-0.

- [ ] **Step 4: Run canonical backend A/B**

  Run sequential full pytest from virgin archives of <code>220e163</code> and
  product tip in the same environment. Require:

  - existing node failure-set bidirectional diff empty;
  - existing failed/skipped/warning/error families equal;
  - collect exactly 4562 -> 4569;
  - added nodes exactly the seven reviewed route nodes; and
  - no removed/renamed backend node.

  Do not substitute a dirty-worktree run. If the environment has a known hang,
  preserve both sides symmetrically and hand canonical completion to the
  independent reviewer rather than claiming PASS.

- [ ] **Step 5: Run immutable/static ratchets**

  Prove:

  - changed files exactly match the file map;
  - <code>src/profile_state.py</code>, schemas, dependencies, schedulers,
    domain stores, formatters, CSS, all current surface components, desktop,
    and extensions are byte-identical to <code>220e163</code>;
  - no navigator/OS locale detection;
  - no detector/backend-loader/Suspense/dynamic resource import;
  - no public selector labels/autonym pair in reachable production UI;
  - no dynamic translation key;
  - cache write helper has one production importer, the controller;
  - locale API exposes no generic settings key;
  - scanner debt does not increase and migrated scopes are zero; and
  - no raw exception is stored in locale context.

- [ ] **Step 6: Run isolated browser/desktop smoke**

  Use a temporary profile DB and isolated ports. Never mutate the production
  profile or browser storage.

  Verify:

  1. no DB value plus empty cache paints with <code>lang=zh-Hant</code>;
  2. cached <code>en</code> is applied before React and later corrected to
     default <code>zh-Hant</code> by GET, with cache corrected only afterward;
  3. stored <code>en</code> plus empty cache starts at static
     <code>zh-Hant</code>, corrects once to <code>en</code>, and writes cache;
  4. a failed locale GET leaves the shell usable in bootstrap locale;
  5. no locale selector/autonyms/planned control appears;
  6. existing Settings navigation and drafts remain operational;
  7. no blank first paint, console exception, horizontal overflow, or layout
     shift attributable to an added control at 1440x900 and 390x844; and
  8. isolated services, DBs, browser profiles, and ports are cleaned.

  Instrument document-lang changes before navigation; a screenshot taken after
  settlement cannot prove first-paint ordering.

- [ ] **Step 7: Run no-PG and final worktree gates**

  Run the established no-PG smoke, then:

  ~~~bash
  git diff --check
  git status --short
  git log --oneline --decorate -12
  ~~~

  No DB, token, screenshot, browser profile, generated build output, or
  node_modules path may be staged.

---

## Task 8: Review-Ready Documentation and Stop

**Files:**
- Modify this plan implementation ledger
- Modify <code>docs/design/PROJECT_PRIORITY_MAP.md</code> status only

- [ ] **Step 1: Reconcile the ledger**

  Record clearance/base hashes, typed-key mode, each RED/GREEN commit, exact
  +7/-0 and +44/-0 proof, resource key paths, debt/allowlist/scope totals,
  focused/full/A-B/static/runtime results, process cleanup, and every reviewed
  deviation.

- [ ] **Step 2: Mark implementation review-ready, not LIVE**

  Priority map entry must say I18N-0 implementation is complete for independent
  review; I18N-1 remains queued and is not opened.

- [ ] **Step 3: Commit evidence**

  Commit only plan/map evidence with message
  <code>docs: record i18n foundation verification</code>.

- [ ] **Step 4: Stop**

  Request independent implementation review. Do not merge, expose a selector,
  begin Shell translation, update Design Kit, alter production DB preference,
  or delete the worktree.

---

## Independent Reviewer Focus

The reviewer should independently verify:

1. exact +7/-0 backend and +44/-0 frontend node ledgers;
2. invalid stored locale is typed, non-mutating, and does not leak its value;
3. permission gate occurs before locale write;
4. bootstrap locale and document language are synchronous before createRoot;
5. DB read failure is fail-open and no cache write occurs;
6. cache writes exist only after successful GET/PUT;
7. late GET cannot win after either successful or failed newer PUT;
8. StrictMode/coincident startup reads issue one authority GET;
9. optimistic failure restores prior runtime/document state and exposes no raw
   exception;
10. selector versus dot-path mode is one typed style with no casts or mixed use;
11. resources are bundled, exact-key-equal, non-empty, and safe on missing key;
12. default test locale preserves all 636 existing assertions unchanged;
13. scanner uses TypeScript AST and every requested fixture category is a true
    RED-to-GREEN contract;
14. debt can only shrink, migrated scopes are zero, and allowlist entries are
    exact/current/reviewed rather than a hiding place for translation debt;
15. no selector, visible copy migration, formatter drift, IA/CSS change,
    detector, loader, Suspense, or dynamic import;
16. canonical backend A/B failure-set equality and exact node addition; and
17. isolated runtime proof captures pre-React document-lang transitions rather
    than inferring them from the settled page.

---

## Stop Conditions

Stop and return for design/review if:

1. locale persistence requires a schema/table change or generic settings API;
2. a valid stored <code>en</code> is normalized back to zh-Hant;
3. first paint requires async main, Suspense, resource fetch, or a loading UI;
4. DB failure blocks normal app render;
5. cache must be written before DB success;
6. a stale startup GET can alter state after a newer PUT starts;
7. overlapping locale writes cannot be prevented without adding a public UI;
8. pinned selector typing fails and standard typed dot-path also fails;
9. typing requires casts, compiler relaxation, custom wrappers, or mixed modes;
10. i18next changes existing formatter behavior;
11. any existing Traditional Chinese test assertion must be rewritten to a key;
12. any visible surface, CSS, IA, breakpoint, domain DTO, generic API error
    behavior, desktop code, or extension changes;
13. scanner uses regex instead of AST for the reviewed categories;
14. scanner misses any required fixture, scans comments/import paths, or needs
    a broad directory/literal bypass;
15. legacy debt can grow, migrated scope can consume debt, or stale allowlist
    entries pass;
16. exact allowlist needs a translatable sentence or source/user secret;
17. generated debt inventory contains tests, resources, machine paths, secrets,
    or nondeterministic order;
18. any unreviewed test node disappears or raw accounting differs;
19. backend A/B existing failure set changes; or
20. runtime verification would require production DB or browser-profile
    mutation.

---

## Post-Review Merge Closeout (Not Part of Implementation Clearance)

Only after independent implementation GREEN and explicit user merge approval:

1. restore the main checkout to clean tracked state;
2. fast-forward merge the reviewed branch;
3. rerun backend 7, frontend 8/44, full 73/680, typecheck, build, scanner,
   no-PG smoke, and merged-tree startup smoke;
4. verify production profile DB remains byte-identical unless the user later
   explicitly uses the locale API; I18N-0 itself performs only a pure GET;
5. mark I18N-0 LIVE in plan/decision/map and promote I18N-1 Shell + common UI as
   the single NEXT unit;
6. do not sync Design Kit because I18N-0 adds no visible control or translated
   surface;
7. update memory/decision log; and
8. remove the worktree/branch only after all closeout evidence is retained.
