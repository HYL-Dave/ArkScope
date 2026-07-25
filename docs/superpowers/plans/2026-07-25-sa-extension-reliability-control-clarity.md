# SA Extension Reliability and Control-Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: INDEPENDENT IMPLEMENTATION REVIEW GREEN - MERGE APPROVED**
>
> The design passed independent review and its required disclosure amendment
> plus all three advisories are incorporated through `9da1a9c9`. A later
> grounding pass found and closed the routine-capture/telemetry ordering
> ambiguity in `c49a2417`. Independent full-plan review returned GREEN. Its
> one required baseline correction and two grounding advisories are resolved
> below with no product or test-accounting change. The docs-only commit that
> contains this resolution is resolved with `git rev-parse HEAD` as
> `PLAN_REVIEW_CLEARANCE_COMMIT=7d4f11164861aa0a50cc7771fef7388577f4da0b`.
> The isolated implementation worktree records that authority below. Merge,
> extension installation, and production repair remain separately
> unauthorized.

**Goal:** Make the Seeking Alpha browser extension impossible to package with
missing runtime dependencies, make partial capture failures durably visible,
provide bounded and audited Market News recovery without F12, and replace the
popup's ambiguous controls with five honest, accessible actions.

**Architecture:** Assemble Firefox from a computed dependency graph before
any destructive replacement. A pure versioned run protocol has equivalent JS
and Python implementations driven by one synthetic fixture corpus. The
extension derives capture truth locally, writes a bounded telemetry record to
`chrome.storage.local`, and sends it through the native host to a sidecar
endpoint that derives the only permitted database status and records each
client event once. Repair is a separate sidecar-owned `job_runs` lifecycle:
the sidecar freezes a canonical manifest, the extension uses its authenticated
browser session to execute targets, and the sidecar atomically checkpoints and
finalizes results after capture readback. The popup owns immediate English
control copy; the web app owns durable localized health from stable codes and
counts.

**Tech stack:** Firefox/Chrome MV3 classic JavaScript, Python 3 standard
library packaging, FastAPI/Pydantic, SQLite `BEGIN IMMEDIATE`, native
messaging, pytest, Node/jsdom, React 18, TypeScript 5.9, i18next, and Vitest.
No new runtime, test, npm, or Python dependency is authorized.

---

## Design Authority

1. Product authority:
   `docs/superpowers/specs/2026-07-25-sa-extension-reliability-control-clarity-design.md`.
2. Sequence authority: `docs/design/PROJECT_PRIORITY_MAP.md`.
3. Broader extension roadmap: `docs/design/SA_EXTENSION_ROADMAP.md`.
4. Browser/native-host setup boundary:
   `docs/design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md`.
5. Alpha Picks comment continuity remains owned by the reviewed reconciliation
   design and implementation plan; this unit may consume but not change its
   state transitions or terminal authority.
6. Localized-surface boundary:
   `docs/superpowers/specs/2026-07-20-app-wide-i18n-decision.md`.
7. Behavioral base: clean `master` at `c49a2417`. All commits after
   `38178f65` are docs-only, so product bytes at the plan base equal the
   independently reviewed pre-spec product.

If implementation needs to contradict any authority above, stop and amend the
authority before changing product code.

## Independent Design-Review Resolution

The independent review was GREEN with one required docs amendment and three
advisories. All are binding here:

1. The third Alpha action is `Deep Repair Scan`, not `Repair Comment Gaps`.
   The popup must disclose 200 article-list load rounds, no separate global
   Alpha detail-fetch cap, 20 reconciliation-enrichment items, 140 comment
   scrolls/120 seconds/five stable-bottom rounds per selected article, and the
   configured additional recovery batch (default 50). It must say this is the
   deepest and potentially longest Alpha action.
2. `18/30/80` are Market News detail budgets, not Alpha Picks limits. Any test,
   copy, or implementation that assigns them to Alpha is wrong and must stop.
3. The 450 historical failure records all contain only
   `detail_not_saved`. That legacy prose may identify targets but may not seed
   a modern item state or reason code. Fresh execution must classify each ID.
4. The separately approved historical manifest is recorded-ID repair and has
   no age cutoff. The 168-hour cap applies only to interval rediscovery.
5. Every consumer of extension `failed` rows must be audited. `/jobs/status`
   and `/jobs/history` intentionally become honest about degraded extension
   runs; extension rows must not enter scheduler retry/backoff control.

Grounding also resolved one ordering issue after review: capture outcome is
derived before telemetry can be posted, so routine telemetry persistence is a
separate axis. A locally complete capture with audit pending remains usable
but cannot become a durable healthy anchor until replay succeeds. Repair is
stricter: a durable running audit row is a start precondition and durable
finalization is required to complete the repair lifecycle.

## Independent Plan-Review Resolution

Independent full-plan review returned GREEN with one required docs fix and
two advisories. All three were independently checked before clearance:

1. The frontend full node-list hash was misrecorded. Re-running the same
   relative-path normalization that reproduces the focused hash gives
   `5f9a1624b31a47dc9b786f57fa5de77eca86dde269c68ada3787d7210b05fd13`
   for all `1056` nodes. The incorrect `f6351647...` value is retired.
2. Backend and frontend node-list recipes are now stated separately. Pytest
   hashes its emitted `file::node` IDs as-is; Vitest normalizes absolute file
   paths to web-app-relative paths before pairing them with node names.
3. The review correctly found that the `10/50` recovery defaults lacked a
   grounded pointer in this plan, but its suggestion that the defaults might
   not exist is not adopted. `AgentConfig` owns both defaults and profile
   overrides; `DataAccessLayer` consumes them and implements the parked-row
   distinction. The exact symbols and locations are recorded below.

## Post-Merge Contrast-Repair Clearance

After the reviewed implementation merged, user inspection exposed a popup
contrast regression that the original browser gate did not measure. The
design authority now contains the approved computed-style evidence and exact
repair boundary. This is a post-merge reviewed deviation, not a reopening of
capture behavior.

Grounded baseline at `4bf7a503` is:

- `tests/test_sa_extension_popup.py` has `12` nodes;
- `tests/test_sa_extension_packaging.py` has `10` nodes;
- the focused pair is `22 passed`;
- backend collection remains `4710` and frontend remains `95 files / 1063`;
- the worktree is clean and both `master` and
  `codex/sa-extension-reliability` point at `4bf7a503` before the deviation.

The deviation adds exactly one popup contrast node and removes none. Expected
accounting is backend `+1/-0` to `4711`; the focused pair becomes `23`, while
frontend node accounting remains unchanged. The product file set is limited
to `popup.html` and `popup_action_catalog.js`; the fixture runner and popup
pytest owner may change only to implement the generic computed-style gate.
All scraper, protocol, native-host, backend, web-app, package, and database
owners remain byte-identical.

## Grounded Baseline

The following values were reproduced on clean `c49a2417` on 2026-07-25.

| Gate | Baseline |
| --- | ---: |
| Backend full collection | `4621` nodes |
| Backend focused extension/health collection | `9 files / 238` nodes |
| Backend focused run | `238 passed` |
| Backend full sorted node-list SHA-256 | `488eeaab65ffad32bd098dbc4b1df0eb3ed3b62feabfe3a62b1a76324d960a17` |
| Backend focused sorted node-list SHA-256 | `ca36c2cc8616982fa8dd2c2f386743751691de6bd4f9bf52134229d830740de8` |
| Frontend full collection | `95 files / 1056` nodes |
| Frontend focused health collection/run | `4 files / 62` nodes, green |
| Frontend full sorted relative node-list SHA-256 | `5f9a1624b31a47dc9b786f57fa5de77eca86dde269c68ada3787d7210b05fd13` |
| Frontend focused sorted relative node-list SHA-256 | `025e871755c356f0be89089e92d0241d06b335af52ae8a2ca0f66e06b187f643` |
| i18n resource leaves per locale | Settings `681`; total `1781` |
| i18n scanner | `36/20/0/20`, scope `src/**` |
| Production incident observation | `25` runs / `450` records / `118` IDs / `30` currently body-missing |

Alpha comment-recovery configuration is grounded as follows:

| Contract | Canonical owner / consumer |
| --- | --- |
| Full additional recovery default `10` | `AgentConfig.sa_comments_backfill_per_full_scan` in `src/agents/config.py:136`; optional profile key `seeking_alpha.comments_backfill_per_full_scan` is applied at `src/agents/config.py:363-364`; `src/tools/data_access.py:1180-1184` consumes it with the same fallback. |
| Backfill additional recovery default `50` | `AgentConfig.sa_comments_backfill_per_backfill_scan` in `src/agents/config.py:137`; optional profile key `seeking_alpha.comments_backfill_per_backfill_scan` is applied at `src/agents/config.py:365-366`; `src/tools/data_access.py:1175-1179` consumes it with the same fallback. |
| Parked-row distinction | `src/tools/data_access.py:1208-1212` includes every pending row for `backfill` and excludes rows with `comment_recovery_parked_at` for `full`. |

Backend focused distribution:

```text
tests/test_extension_install_paths.py             4
tests/test_job_runs.py                           54
tests/test_provider_health.py                    18
tests/test_sa_extension_alpha_picks.py            5
tests/test_sa_extension_health.py                 7
tests/test_sa_extension_reconciliation_ui.py      9
tests/test_sa_market_news_health.py               34
tests/test_sa_native_host_telemetry.py            10
tests/test_sa_tools.py                            97
                                                   --
                                                  238
```

Frontend focused distribution:

```text
src/SettingsProviderConfig.test.ts                33
src/i18n/resources.test.ts                        14
src/saExtensionHealthDisplay.test.ts               3
src/settings/settingsBackendCopy.test.ts          12
                                                   --
                                                   62
```

Baseline commands:

```bash
pytest --collect-only -q > /tmp/arkscope-sa-ext-full-collect.txt
pytest --collect-only -q \
  tests/test_extension_install_paths.py \
  tests/test_sa_extension_alpha_picks.py \
  tests/test_sa_extension_reconciliation_ui.py \
  tests/test_sa_native_host_telemetry.py \
  tests/test_job_runs.py \
  tests/test_sa_extension_health.py \
  tests/test_sa_market_news_health.py \
  tests/test_provider_health.py \
  tests/test_sa_tools.py \
  > /tmp/arkscope-sa-ext-focused-collect.txt

pytest -q \
  tests/test_extension_install_paths.py \
  tests/test_sa_extension_alpha_picks.py \
  tests/test_sa_extension_reconciliation_ui.py \
  tests/test_sa_native_host_telemetry.py \
  tests/test_job_runs.py \
  tests/test_sa_extension_health.py \
  tests/test_sa_market_news_health.py \
  tests/test_provider_health.py \
  tests/test_sa_tools.py

cd apps/arkscope-web
npx vitest list --json=/tmp/arkscope-sa-ext-fe-full.json
npx vitest list --json=/tmp/arkscope-sa-ext-fe-focused.json \
  src/saExtensionHealthDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/i18n/resources.test.ts
npx vitest run \
  src/saExtensionHealthDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/i18n/resources.test.ts
```

Backend node-list hashes take every pytest collection line containing `::`
as its emitted `file::node` ID, sort with `LC_ALL=C`, include one final
newline, and run `sha256sum`. Frontend hashes pair the web-app-relative `.file`
with `.name` as `relative-file<TAB>node-name`, apply the same sort/newline/hash
steps, and never hash checkout-specific absolute paths. A count or hash drift
before product edits is a stop condition.

## Consumer and Ownership Audit

### Existing failed-row consumers

The implementation must preserve this explicit audit:

| Consumer | Current behavior | Required behavior |
| --- | --- | --- |
| `GET /jobs/status` via `list_jobs_status()` | latest DB row becomes `last_status` | Latest degraded extension row is honestly `failed`; structured result remains available. No retry is started here. |
| `GET /jobs/history` | returns stored rows | Shows derived DB status and structured result without raw exception prose. |
| `src/service/jobs.py::run_job` | creates backend-owned rows | Unchanged. It never consumes extension rows to schedule retries. |
| scheduler state/backoff | separate scheduler-owned state | Byte-identical. Extension `job_runs` rows never enter scheduler retry/backoff. |
| `sa_market_news_health` | latest generic succeeded timestamp | Latest structured derived-complete, non-skipped sync only; latest attempt/outcome reported separately. |
| `provider_health` | latest succeeded Market News row may advance SA success | Same derived-complete rule; degraded updates attempt/warning, not success. |
| `sa_extension_health` | outer status plus raw backend prose | Stable code/count/run metadata; no raw telemetry prose. |
| web Settings health | labels chain; ignores table detail but forwards all details to Developer diagnostics | New telemetry/repair rows use localized code/count presentation; arbitrary telemetry detail never enters DOM. Existing older diagnostics remain the separate sanitizer backlog. |

No other `job_runs.status` consumer or failure counter may be discovered during
implementation. A new consumer is a stop-and-amend event.

### Storage ownership

- `profile_state.db.job_runs` owns extension telemetry and repair audit.
- `sa_capture.db` owns captured Market News metadata and bodies.
- For the new telemetry and repair controls, the native host owns neither
  database and only proxies fixed sidecar routes. Its existing capture DAL
  handlers remain behaviorally unchanged.
- `chrome.storage.local` is a bounded delivery outbox/cache, never durable
  audit authority.
- Popup prose is English and ephemeral. Web health prose is localized and
  durable. Stable codes and counts are the only cross-surface contract.
- Generic `/jobs/status` and `/jobs/history` projections must reduce repair
  manifests/progress to kind, counts, stable state, run ID, and bounded hash
  prefix. Exact target IDs/pathnames remain available only to the fixed repair
  execution endpoints and never enter generic history, health, or logs.

## Locked Implementation Decisions

### Runtime dependency graph

1. Add `extensions/sa_alpha_picks/build_firefox.py`, using only the Python
   standard library.
2. It parses manifest asset fields, local HTML dependencies, literal
   `importScripts(...)`, and literal
   `chrome.scripting.executeScript({files:[...]})` arrays.
3. A nonliteral `importScripts` or `files` expression is a build error, not a
   warning or fallback.
4. Build into a sibling temporary directory, validate exact closure, then
   replace `build/firefox` atomically. Restore the previous directory if final
   replacement fails.
5. `install_firefox.sh` invokes the builder before native-host registration
   writes. It no longer has runtime-file `cp` lines or `scrape*.js` globs.
6. `PACKAGING_GATE_TIP` is recorded immediately after Task 1. Every later
   extension file must build through that checkpoint contract.

### Protocol modules

1. Add pure classic-script global
   `extensions/sa_alpha_picks/extension_run_protocol.js` and Python twin
   `src/sa/extension_run_protocol.py`.
2. Chrome `background.js` conditionally loads the JS module with a literal
   `importScripts()` call. Firefox uses the exact order
   `compat_firefox.js`, protocol, telemetry (after Task 3), then
   `background.js`. The modules are never dynamically constructed.
3. One synthetic fixture corpus at
   `tests/fixtures/sa_extension/run_outcomes.json` drives both
   implementations. It contains opaque fake IDs only.
4. Closed operations are exactly:
   `alpha_picks_sync`, `alpha_picks_manual_fetch`, `market_news_sync`,
   `market_news_retry_recorded`, and `market_news_incident_recovery`.
5. Closed item states are exactly `repaired`, `already_present`,
   `unavailable_at_source`, and `failed_retryable`.
6. The complete reason enum is owned once in each language and parity-tested:

```text
body_saved
body_present_at_freeze
body_present_during_run
source_http_404
source_http_410
source_removed_marker
access_restricted
login_required
modal_blocked
navigation_timeout
detail_timeout
dom_not_ready
parser_empty
native_host_unavailable
detail_save_failed
extension_dependency_missing
interrupted
unknown_failure
not_due
already_pending
operator_cancelled
protocol_invalid
manifest_invalid
telemetry_unavailable
current_scope_failed
closed_scope_failed
article_metadata_failed
article_detail_failed
comment_scan_failed
reconciliation_failed
list_navigation_failed
list_scrape_failed
metadata_save_failed
detail_queue_failed
capture_readback_failed
```

7. A complete phase has no failure reason. Failed/skipped phases must carry a
   permitted reason. Counts are recomputed from phases/items and a mismatch is
   invalid.
8. `telemetry_unavailable` belongs only to the separate audit-delivery or
   repair-lifecycle projection. A capture phase named for telemetry, or a
   capture outcome changed by telemetry delivery, is invalid.
9. `unavailable_at_source` accepts only `source_http_404`,
   `source_http_410`, or `source_removed_marker`. Current browser navigation
   does not expose HTTP response status, so 404/410 remain protocol-valid but
   are emitted only if a reviewed transport later supplies them. The shipped
   browser path may emit `source_removed_marker` only from an exact tested SA
   marker. It never guesses from an empty page.
10. The extension includes `derived_outcome`; the sidecar independently derives
   it and rejects disagreement. Database status is not accepted from the
   extension.

### Routine telemetry outbox

1. Add `extensions/sa_alpha_picks/extension_telemetry.js` as a pure injectable
   outbox controller used by `background.js`.
2. Storage key is versioned: `arkscope.sa.telemetryOutbox.v1`.
3. Each record has a UUID client event ID, canonical structured result,
   timestamps, attempt count, and stable delivery code. No raw exception text
   is persisted in the record.
4. The record is committed to `chrome.storage.local` before native messaging.
5. Exact bounds use UTF-8 canonical JSON bytes: at most `100` records, at most
   `7 * 24` hours old, at most `131072` bytes per record, and at most
   `4194304` total outbox bytes. Oldest-first eviction is recorded in
   `arkscope.sa.telemetryOutboxState.v1` with cumulative count, timestamp, and
   stable reason. An individually oversized record is rejected as visibly
   unavailable; it is never silently truncated into false protocol truth.
6. Startup, popup open, and the next extension job call one serialized flush.
7. A record is removed only after `{persisted:true, run_id:<int>}`.
8. Outbox storage failure yields `unavailable`; sidecar failure with a stored
   record yields `pending`. Neither changes capture `derived_outcome`.
9. Add `JobRunsLocalStore.record_extension_event_once()`. It uses one
   `BEGIN IMMEDIATE` transaction, scans canonical extension payload event IDs,
   returns the existing ID for an identical event, and rejects reuse with a
   different event hash. No schema/index is added.

### Repair service and execution bounds

1. Add `src/sa/market_news_recovery.py` as the domain owner. Routes remain in
   `src/api/routes/seeking_alpha.py`; native actions map to fixed paths and
   cannot supply an arbitrary URL.
2. Repair job name is exactly `sa_market_news_repair`.
3. `JobRunsLocalStore` gains atomic methods for start-or-return-running,
   running progress merge, terminal finalize, and structured extension
   summaries. Every write uses `BEGIN IMMEDIATE`; no read-then-write race is
   accepted.
4. Canonical manifest JSON uses sorted keys and compact separators. Hash is
   SHA-256 of immutable algorithm/version, kind, interval, sorted target
   descriptors, source run IDs, and bounds. Run ID, wall-clock creation
   timestamp, progress, and outcomes are excluded.
5. Pathnames must be canonical `https://seekingalpha.com` paths with no query,
   fragment, credentials, alternate host, or traversal. UI/logs expose count
   and hash prefix, not licensed titles or URLs.
6. Exact incident constants:

```text
MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS = 168
MARKET_NEWS_INCIDENT_MAX_LIST_SCROLL_ROUNDS = 60
MARKET_NEWS_INCIDENT_MAX_LIST_ELAPSED_MS = 600000
MARKET_NEWS_INCIDENT_STABLE_ROUNDS = 5
MARKET_NEWS_REPAIR_DETAIL_ATTEMPTS_PER_PASS = 80
```

   These are attempted-work bounds, not completeness claims. More than 80
   frozen IDs resume under the same run ID/hash in another pass.
7. Recorded-ID repair ignores age. Incident known-ID selection uses the actual
   preview interval. Metadata discovery is a separate leg and may run with
   zero known IDs.
8. Each item checkpoint is idempotent by `(run_id, news_id, attempt_id)`.
   Repeating an identical checkpoint is a no-op; conflicting reuse fails.
9. Terminal finalization re-reads body presence. Baseline-present becomes
   `already_present`; baseline-absent now present becomes `repaired`; explicit
   removed evidence may remain `unavailable_at_source`; everything else is
   `failed_retryable`.
10. Closing the popup does not cancel. Cancel is explicit. A stale running row
    remains resumable and marks unresolved progress `interrupted`; it is never
    auto-promoted to success.
11. Normal Market News sync and repair share the existing extension-side
    mutex. They cannot interleave tab navigation.

### Popup presentation

1. Add `extensions/sa_alpha_picks/popup_action_catalog.js` as the only owner of
   five labels, descriptions, disclosure prose, and non-guarantees.
2. Fixed limits come from `background.js` structured fields; Full/Deep
   additional recovery batches come from a native structured numeric response.
   Unavailable native values render `configured limit unavailable`.
3. The five normal actions are grouped 3+2 and named exactly:
   `Quick Update`, `Full Article Scan`, `Deep Repair Scan`,
   `Sync Latest News`, `Catch Up News (24h)`.
4. `Retry Recorded Failures` is contextual, not a sixth permanent control.
5. `Advanced recovery tools` is collapsed by default and promoted/focused from
   a real gap. It has no arbitrary date controls.
6. Existing Alpha Picks article-link review and `Advanced: specify article
   URLs` remain in their reconciliation owner. They are not merged into,
   relabeled as, or removed by Market News recovery.
7. Each normal button points to one description element with
   `aria-describedby`. Pointer hover and keyboard focus reveal that same node.
   No duplicate `title` prose exists.
8. `What these actions do` is inline; no `help.html` is added.
9. Popup remains English and must contain no CJK product copy.

### Durable health presentation

1. Health segments evolve additively to optional `code`, numeric `counts`,
   `run_id`, bounded `manifest_hash_prefix`, and `occurred_at`. Existing setup
   segments may retain their old detail for the separately queued sanitizer
   work; new telemetry/repair segments do not carry arbitrary detail.
2. Add `market_news_repair` after `telemetry_last` in the fixed display order.
3. Unknown codes render one generic localized warning. Normal mode never
   renders the code. Developer Mode may render only
   `^[a-z][a-z0-9_]{0,63}$`; no raw detail, path, traceback, SQL, or URL is
   admitted.
4. Add exactly 13 leaves under `settings.dataSources.extension.status`:
   `captureComplete`, `captureSkipped`, `detailFailuresRecorded_one`,
   `detailFailuresRecorded_other`, `captureFailed`, `telemetryNotRecorded`,
   `repairActive`, `repairComplete`, `repairRetryable_one`,
   `repairRetryable_other`, `unknownWarning`, `developerCode`, and
   `manifestPrefix`.
5. Settings leaves become `694`; total leaves become `1794` in each locale.

## File Map

### New product files

- `extensions/sa_alpha_picks/build_firefox.py`
- `extensions/sa_alpha_picks/extension_run_protocol.js`
- `extensions/sa_alpha_picks/extension_telemetry.js`
- `extensions/sa_alpha_picks/popup_action_catalog.js`
- `src/sa/extension_run_protocol.py`
- `src/sa/market_news_recovery.py`

### Modified extension files

- `extensions/sa_alpha_picks/install_firefox.sh`
- `extensions/sa_alpha_picks/manifest.firefox.json`
- `extensions/sa_alpha_picks/background.js`
- `extensions/sa_alpha_picks/popup.html`
- `extensions/sa_alpha_picks/popup.js`
- `extensions/sa_alpha_picks/scrape_detail.js` only if the exact reviewed
  removed-source marker needs a structured return; otherwise byte-identical

### Modified backend files

- `src/service/job_runs_store.py`
- `src/api/routes/jobs.py`
- `src/api/routes/seeking_alpha.py`
- `src/sa_native_host.py`
- `src/tools/data_access.py`
- `src/tools/backends/sa_capture_backend.py`
- `src/service/sa_extension_health.py`
- `src/service/sa_market_news_health.py`
- `src/service/provider_health.py`

### Modified web files

- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/saExtensionHealthDisplay.ts`
- `apps/arkscope-web/src/settings/settingsBackendCopy.ts`
- `apps/arkscope-web/src/settings/DataSourcesSection.tsx`
- `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- `apps/arkscope-web/src/i18n/resources/en/settings.ts`

### New test/fixture files

- `tests/test_sa_extension_packaging.py`
- `tests/test_sa_extension_run_protocol.py`
- `tests/test_sa_extension_telemetry_outbox.py`
- `tests/test_sa_market_news_recovery.py`
- `tests/test_sa_extension_popup.py`
- `tests/js/run_sa_extension_protocol_fixture.mjs`
- `tests/js/run_sa_extension_telemetry_fixture.mjs`
- `tests/js/run_sa_extension_popup_fixture.mjs`
- `tests/fixtures/sa_extension/run_outcomes.json`
- synthetic popup/packaging fixtures under `tests/fixtures/sa_extension/`

### Modified test files

- `tests/test_extension_install_paths.py`
- `tests/test_sa_extension_alpha_picks.py`
- `tests/test_sa_extension_reconciliation_ui.py` (English/file-set coverage
  only; no node-accounting change)
- `tests/test_sa_native_host_telemetry.py`
- `tests/test_job_runs.py`
- `tests/test_sa_extension_health.py`
- `tests/test_sa_market_news_health.py`
- `tests/test_provider_health.py`
- `tests/test_sa_tools.py`
- `apps/arkscope-web/src/saExtensionHealthDisplay.test.ts`
- `apps/arkscope-web/src/settings/settingsBackendCopy.test.ts`
- `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- `apps/arkscope-web/src/i18n/resources.test.ts`

### Evidence/status files

- this plan
- the design authority status header at plan clearance; its review-resolution
  body only if implementation discovers a reviewed deviation
- `docs/design/PROJECT_PRIORITY_MAP.md`
- `docs/design/SA_EXTENSION_ROADMAP.md`
- one committed redacted evidence ledger under `docs/superpowers/evidence/`
  created during implementation

### Absolute byte-identical boundaries

Unless the plan is amended and independently re-reviewed:

- all database schema/migration files;
- Alpha Picks comment-continuity transition owners in
  `src/tools/backends/sa_capture_backend.py` outside new Market News query
  helpers;
- `extensions/sa_alpha_picks/article_identity.js` and article/comment/list
  scrapers except the explicitly conditional `scrape_detail.js` marker seam;
- `extensions/sa_alpha_picks/manifest.json` (the Chrome service worker loads
  the new classic-script modules through literal `importScripts()` calls);
- Market News auto-sync schedule windows and existing routine detail budgets;
- all agent prompts, tools, research, portfolio, market-data, and formatter
  owners;
- all web CSS;
- Electron/desktop code;
- package manifests and lockfiles; and
- all app i18n namespaces except the 13 Settings health leaves above.

## Exact Test Accounting

### Backend/raw ledger

| File | Add | Remove | Final delta |
| --- | ---: | ---: | ---: |
| `tests/test_extension_install_paths.py` | 1 | 1 | 0 |
| `tests/test_sa_extension_packaging.py` | 10 | 0 | +10 |
| `tests/test_sa_extension_run_protocol.py` | 12 | 0 | +12 |
| `tests/test_sa_extension_telemetry_outbox.py` | 8 | 0 | +8 |
| `tests/test_sa_market_news_recovery.py` | 16 | 0 | +16 |
| `tests/test_sa_extension_popup.py` | 12 | 0 | +12 |
| `tests/test_sa_extension_alpha_picks.py` | 3 | 0 | +3 |
| `tests/test_sa_native_host_telemetry.py` | 4 | 0 | +4 |
| `tests/test_job_runs.py` | 10 | 1 | +9 |
| `tests/test_sa_extension_health.py` | 4 | 0 | +4 |
| `tests/test_sa_market_news_health.py` | 4 | 0 | +4 |
| `tests/test_provider_health.py` | 2 | 0 | +2 |
| `tests/test_sa_tools.py` | 5 | 0 | +5 |
| **Total** | **91** | **2** | **+89** |

Expected backend final collection: `4621 + 91 - 2 = 4710`.

Expected focused collection: `9 existing + 5 new = 14 files`,
`238 + 91 - 2 = 327` nodes.

The only removed backend IDs are:

1. `test_firefox_installer_copies_every_popup_script_dependency`
2. `test_record_extension_job_rejects_invalid_status`

Their explicit successors are:

1. `test_firefox_installer_delegates_to_atomic_dependency_closure_builder_before_registration`
2. `test_record_extension_job_rejects_caller_supplied_status`

No other existing node may disappear or be renamed.

### Frontend/raw ledger

| File | Add | Remove | Final delta |
| --- | ---: | ---: | ---: |
| `src/saExtensionHealthDisplay.test.ts` | 5 | 1 | +4 |
| `src/SettingsProviderConfig.test.ts` | 3 | 0 | +3 |
| existing resource/backend-copy nodes | 0 | 0 | 0 |
| **Total** | **8** | **1** | **+7** |

Expected frontend final collection: `95 files / 1063 nodes`.
Expected focused collection: `4 files / 69 nodes`.

The only removed frontend ID is:

```text
displaySAExtensionSegments > maps every known extension segment in both locales and preserves unknown ids
```

Its successor is:

```text
displaySAExtensionSegments > maps every known segment and fails unknown health prose closed in both locales
```

Existing resource-count and SA segment-key nodes evolve in place. They do not
change node ID and do not count as remove/add.

### Task checkpoints

| Checkpoint | Backend full | Backend focused | Frontend full | Frontend focused |
| --- | ---: | ---: | ---: | ---: |
| Base | 4621 | 238 | 1056 | 62 |
| Task 1 packaging (`+11/-1`) | 4631 | 248 | unchanged | unchanged |
| Task 2 protocol (`+15/-0`) | 4646 | 263 | unchanged | unchanged |
| Task 3 telemetry (`+22/-1`) | 4667 | 284 | unchanged | unchanged |
| Task 4 health (`BE +10`; `FE +8/-1`) | 4677 | 294 | 1063 | 69 |
| Task 5 recovery backend (`+21/-0`) | 4698 | 315 | 1063 | 69 |
| Task 6 popup/runtime (`+12/-0`) | 4710 | 327 | 1063 | 69 |

Any count drift stops implementation until this plan and the exact node list
are reconciled in a reviewed docs commit. Net totals may not hide removals.

---

## Task 0: Plan Clearance, Isolation, and Baseline Evidence

**Files:**
- Modify this plan status only after independent GREEN
- Modify the design authority status to record plan-review GREEN
- Modify `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify `docs/design/SA_EXTENSION_ROADMAP.md`

- [x] **Step 1: Receive independent full-plan review**

Do not begin product work on a conditional or partial review. Incorporate
required findings in docs, rerun grounding affected by them, and obtain final
GREEN.

- [x] **Step 2: Record clearance**

Set this plan to `CLEARED FOR IMPLEMENTATION - REVIEW-READY HANDOFF REQUIRED`,
set the design authority to `PLAN REVIEW GREEN - IMPLEMENTATION CLEARED`,
commit docs only, and record the 40-character hash as
`PLAN_REVIEW_CLEARANCE_COMMIT`.

- [x] **Step 3: Create an isolated worktree**

```bash
git status --short
git worktree add ../ArkScope-sa-extension-reliability \
  -b codex/sa-extension-reliability master
cd ../ArkScope-sa-extension-reliability
git rev-parse HEAD
```

Expected: clean worktree at the clearance commit. Mount the same existing root
`node_modules` into any virgin A/B archive used later; do not run an unreviewed
dependency update.

Resolved implementation authority:

- `PLAN_REVIEW_CLEARANCE_COMMIT`:
  `7d4f11164861aa0a50cc7771fef7388577f4da0b`;
- branch/worktree: `codex/sa-extension-reliability` at
  `/mnt/md0/PycharmProjects/ArkScope-sa-extension-reliability`;
- the initial direct checkout stopped at the known linked-worktree
  `git-crypt` smudge boundary. The clean retry used `--no-checkout`, copied
  only `.git/git-crypt/keys/default` with mode `0600`, then populated `HEAD`
  with `git read-tree -mu HEAD`. The protected evaluation document reads
  `47,608` bytes. No database, browser profile, token, or user-owned file was
  copied;
- the existing root `node_modules` is linked into the worktree; no dependency
  installation or lockfile change occurred.

- [x] **Step 4: Reproduce baseline counts and hashes**

Run the commands under Grounded Baseline. Preserve normalized node lists under
`/tmp`; do not commit them. Expected counts/hashes must match exactly.

Reproduced in the isolated worktree: backend `4621` with
`488eeaab65ffad32bd098dbc4b1df0eb3ed3b62feabfe3a62b1a76324d960a17`,
backend focused `238` with
`ca36c2cc8616982fa8dd2c2f386743751691de6bd4f9bf52134229d830740de8`
and `238 passed`; frontend `95/1056` with
`5f9a1624b31a47dc9b786f57fa5de77eca86dde269c68ada3787d7210b05fd13`,
frontend focused `4/62` with
`025e871755c356f0be89089e92d0241d06b335af52ae8a2ca0f66e06b187f643`
and `62 passed`.

- [x] **Step 5: Capture protected-boundary hashes**

Record SHA-256 or `git diff --exit-code` anchors for schema files, protected
scrapers, continuity owners, CSS, desktop, package manifests/lockfiles, agent
and research owners. This is evidence, not a permission to modify them.

All fixed-base `git diff --exit-code c49a2417` gates in Task 8 Step 5 pass at
baseline. The explicit audit set (`scrape_detail.js`, the Market News helper
owners, and `DataSourcesSection.tsx`) is also empty before product edits.

- [x] **Step 6: Commit status only**

```bash
git add docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md \
  docs/superpowers/specs/2026-07-25-sa-extension-reliability-control-clarity-design.md \
  docs/design/PROJECT_PRIORITY_MAP.md docs/design/SA_EXTENSION_ROADMAP.md
git commit -m "docs: clear SA extension reliability implementation plan"
```

---

## Task 1: RED-First Atomic Firefox Dependency Closure

**Files:**
- Create `extensions/sa_alpha_picks/build_firefox.py`
- Modify `extensions/sa_alpha_picks/install_firefox.sh`
- Modify `tests/test_extension_install_paths.py`
- Create `tests/test_sa_extension_packaging.py`
- Create packaging fixtures under `tests/fixtures/sa_extension/packaging/`

- [x] **Step 1: Replace the old popup-only node with its named successor**

The successor must assert that the installer invokes the build helper before
launcher/config/native-manifest writes and contains no runtime asset `cp` list
or `scrape*.js` glob.

- [x] **Step 2: Add ten RED packaging nodes**

Use exactly these IDs:

```text
test_dependency_graph_closes_manifest_html_imports_and_injected_scripts
test_dependency_graph_includes_article_identity_for_both_injection_sites
test_new_literal_runtime_dependency_is_included_without_builder_edits
test_missing_runtime_dependency_fails_before_output_replacement
test_dynamic_execute_script_or_import_scripts_dependency_is_rejected
test_unsafe_remote_or_traversing_asset_reference_is_rejected
test_build_output_is_exact_and_drops_stale_files
test_generated_popup_loads_firefox_compat_exactly_once_before_popup
test_failed_build_preserves_the_previous_known_good_output
test_chrome_source_dependency_graph_is_complete
```

Run:

```bash
pytest -q tests/test_extension_install_paths.py tests/test_sa_extension_packaging.py
```

Expected RED: `11` new/successor nodes fail for missing builder/delegation;
the three installer-host path parameter cases remain green.

Observed: exactly `11 failed / 3 passed` before product implementation.

- [x] **Step 3: Implement the strict graph parser**

Use `json`, `html.parser`, `pathlib`, `tempfile`, and a narrow balanced-token
scanner for JavaScript calls. Do not use a permissive regex that can skip a
dynamic expression. Every error names the source file and rejected reference.

- [x] **Step 4: Implement exact temporary build and atomic replacement**

Expose a side-effect-free graph command plus a build command. Tests must use a
temporary output. Never point a test at the loaded `build/firefox` directory.

- [x] **Step 5: Route the installer through the builder**

Build first. Only after success write launcher/config/native registration.
Keep host ID and addon ID unchanged.

- [x] **Step 6: Verify GREEN and a real fresh artifact**

```bash
pytest -q tests/test_extension_install_paths.py tests/test_sa_extension_packaging.py
tmp="$(mktemp -d)"
python3 extensions/sa_alpha_picks/build_firefox.py \
  --source extensions/sa_alpha_picks \
  --output "$tmp/firefox"
test -f "$tmp/firefox/article_identity.js"
find "$tmp/firefox" -maxdepth 1 -type f -printf '%f\n' | LC_ALL=C sort
rm -rf "$tmp"
```

Expected: `14` focused nodes green (three parametrized host cases plus the
eleven ledger nodes); exact generated closure; no npm invocation.

Observed: `14 passed`; a fresh real build contains exactly `12` files,
including `article_identity.js`. Two independent output directories had the
same file list and per-file hashes. The normalized artifact hash-list SHA-256
is `089a379302cdd6cd7ada109675caae295b38450d88720d7010bab797cd5c8866`.

- [x] **Step 7: Commit and record packaging checkpoint**

```bash
git add extensions/sa_alpha_picks/build_firefox.py \
  extensions/sa_alpha_picks/install_firefox.sh \
  tests/test_extension_install_paths.py tests/test_sa_extension_packaging.py \
  tests/fixtures/sa_extension/packaging
git commit -m "fix: make SA Firefox packaging dependency-complete"
git rev-parse HEAD
```

Record this 40-character hash as `PACKAGING_GATE_TIP` in the evidence ledger.
Every later task must rebuild successfully at each commit.

Resolved `PACKAGING_GATE_TIP`:
`a2869f2ce7a2c2e603657593ef9534a438cd02a6`. Backend checkpoint collection is
`4631`, focused collection is `248`, and their sorted node-list SHA-256 values
are `6a005572814a1c539e96b521b0a9cdb2984d47e8ec625f0dc6a696d6da3a635b`
and `46fcc1766e2e8301e75b7ce5cdb7089d5d98e81955a916f1f84c0e9c72f2a300`.

---

## Task 2: RED-First Structured Run Protocol and JS/Python Parity

**Files:**
- Create `extensions/sa_alpha_picks/extension_run_protocol.js`
- Modify `extensions/sa_alpha_picks/manifest.firefox.json`
- Modify `extensions/sa_alpha_picks/background.js`
- Create `src/sa/extension_run_protocol.py`
- Create `tests/fixtures/sa_extension/run_outcomes.json`
- Create `tests/js/run_sa_extension_protocol_fixture.mjs`
- Create `tests/test_sa_extension_run_protocol.py`
- Modify `tests/test_sa_extension_alpha_picks.py`

- [x] **Step 1: Add twelve RED protocol nodes**

```text
test_js_and_python_protocol_results_match_the_shared_fixture_corpus
test_complete_market_sync_maps_to_succeeded_and_is_healthy_eligible
test_top_level_ok_with_retryable_details_derives_degraded_and_failed_db_status
test_fatal_list_or_save_phase_derives_failed
test_alpha_detail_or_reconciliation_failure_cannot_derive_complete
test_skipped_not_due_maps_to_typed_succeeded_but_is_not_healthy_eligible
test_item_state_reason_matrix_rejects_incompatible_pairs
test_only_explicit_404_410_or_removed_marker_is_source_unavailable
test_unknown_operation_schema_phase_item_or_reason_fails_closed
test_declared_counts_must_equal_derived_phase_and_item_counts
test_operation_mode_and_job_name_contracts_are_closed
test_legacy_unstructured_success_and_raw_prose_are_not_protocol_truth
```

The fixture must include every adversarial case from design Section 11.2.
Expected RED: missing modules and parity runner.

Observed: the combined protocol/background run was exactly `15 failed / 5
passed`; every new node failed because the protocol modules or real adapters
were absent, while all five existing Alpha Picks nodes remained green. The
top-level `ok` incident fixture contains exactly `18` opaque retryable item
outcomes.

- [x] **Step 2: Add three RED background integration nodes**

```text
test_background_loads_required_runtime_dependencies_before_registering_jobs
test_alpha_adapter_carries_nested_detail_and_reconciliation_failures_into_phases
test_market_adapter_preserves_exact_failed_ids_and_stable_reason_codes
```

These may use a narrow Node VM with mocked `chrome`, but must execute real
product adapter functions rather than search for words only.

- [x] **Step 3: Implement pure derivation and validation in both languages**

Do not parse English error strings in Python. Browser catch sites map known
conditions to stable codes. Unknown exceptions become `unknown_failure` and
raw text stays out of the canonical result/outbox.

- [x] **Step 4: Adapt existing Alpha and Market results**

Keep legacy capture fields needed by current popup/storage only as temporary
source input. The new structured result is the telemetry and health contract.
`detail_failed > 0`, `details.failed > 0`, failed current/closed scope, or
failed reconciliation must not be complete.

- [x] **Step 5: Wire scripts through both manifests and rebuild**

Chrome uses a literal guarded `importScripts`; Firefox lists protocol before
`background.js`. The Task 1 builder must include every new file without edits.

- [x] **Step 6: Verify GREEN**

```bash
pytest -q tests/test_sa_extension_run_protocol.py \
  tests/test_sa_extension_alpha_picks.py \
  tests/test_sa_extension_packaging.py
```

Expected: protocol `12/12`, Alpha `8/8`, packaging `10/10`.

Observed: protocol `12/12`, Alpha `8/8`, and packaging `10/10` pass. One
in-place adapter hardening then proved that an unknown legacy Market status
was incorrectly complete (`1 failed`); the explicit fail-closed branch made
the same node green without changing the ledger. Backend collection is
`4646` with sorted node-list SHA-256
`8d0a838196e2cd5552844963ce270985bcb169c3ad096df375d48ead7a78c8f1`;
focused collection/run is `263/263` with SHA-256
`00b1d9ed399b898f1821dac7f1039cc6b41359ae578864acb94bbb726f651366`.
Two independent real Firefox builds were byte-identical, each with exactly
`13` files; normalized artifact hash-list SHA-256 is
`f34e12aa153b054735ca133fcb918d682e4d52b9cd6a5481d39aecd5cd719522`.

- [x] **Step 7: Commit**

```bash
git add extensions/sa_alpha_picks/extension_run_protocol.js \
  extensions/sa_alpha_picks/manifest.firefox.json \
  extensions/sa_alpha_picks/background.js \
  src/sa/extension_run_protocol.py \
  tests/fixtures/sa_extension/run_outcomes.json \
  tests/js/run_sa_extension_protocol_fixture.mjs \
  tests/test_sa_extension_run_protocol.py \
  tests/test_sa_extension_alpha_picks.py
git commit -m "feat: derive SA extension outcomes from structured truth"
```

Resolved Task 2 product tip:
`46bce5886b7d466bcc0d0cd3f21d522a4ca41619`.

---

## Task 3: RED-First Bounded Telemetry Outbox and Atomic Recording

**Files:**
- Create `extensions/sa_alpha_picks/extension_telemetry.js`
- Modify `extensions/sa_alpha_picks/background.js`
- Modify `extensions/sa_alpha_picks/manifest.firefox.json`; keep the Chrome
  manifest byte-identical
- Modify `src/sa_native_host.py`
- Modify `src/api/routes/jobs.py`
- Modify `src/service/job_runs_store.py`
- Create `tests/js/run_sa_extension_telemetry_fixture.mjs`
- Create `tests/test_sa_extension_telemetry_outbox.py`
- Modify `tests/test_sa_native_host_telemetry.py`
- Modify `tests/test_job_runs.py`

- [x] **Step 1: Add eight RED outbox nodes**

```text
test_outbox_commits_record_before_native_delivery
test_persisted_delivery_removes_only_the_matching_event
test_sidecar_unavailable_keeps_a_pending_record
test_duplicate_flush_reuses_the_same_client_event_id
test_startup_popup_open_and_next_job_share_one_serialized_flush
test_outbox_count_and_total_byte_bounds_evict_oldest_and_surface_loss
test_outbox_age_bound_evicts_expired_and_surfaces_the_loss
test_oversize_storage_failure_or_event_conflict_is_visible_and_never_persisted
```

Observed: exact `8 failed`; every node failed because
`extension_telemetry.js` did not exist. The shared protocol fixture loaded
before that missing-file boundary.

- [x] **Step 2: Replace one job endpoint node and add nine more**

Remove `test_record_extension_job_rejects_invalid_status`; add its named
successor plus:

```text
test_record_extension_job_rejects_caller_supplied_status
test_local_store_records_client_event_once_inside_immediate_transaction
test_local_store_duplicate_event_returns_existing_run_id
test_local_store_rejects_event_id_reuse_with_different_hash
test_local_store_rolls_back_invalid_event_without_partial_row
test_extension_record_endpoint_derives_complete_status
test_extension_record_endpoint_maps_degraded_to_failed
test_extension_record_endpoint_maps_skipped_to_typed_succeeded
test_extension_record_endpoint_rejects_invalid_protocol_or_reason
test_structured_extension_summary_separates_latest_attempt_from_latest_complete
```

The final summary node must insert an older complete event after a newer
degraded event and prove capture timestamps, not insertion order, own latest
attempt and latest healthy selection.

- [x] **Step 3: Add four native-host RED nodes**

```text
test_native_host_rejects_extension_record_with_caller_status
test_native_host_projects_numeric_action_limits_without_faking_defaults
test_native_host_routes_recovery_actions_only_to_fixed_sidecar_paths
test_native_host_returns_typed_sidecar_rejection_without_raw_detail
```

Existing native post/degrade/no-profile-writer nodes evolve in place.

Observed across job-runs plus native telemetry: exact `18 failed / 59
passed`. Failures were the absent atomic-store/summary methods, old
caller-owned request model, old native payload, and absent limits/fixed-route
interfaces. Existing unrelated nodes stayed green.

- [x] **Step 4: Implement outbox controller and job wrapper integration**

Inject storage/native/clock/UUID dependencies for tests. Persist a structured
last-run summary separately from legacy raw refresh snapshots so popup status
can display capture outcome and audit persistence without mutating capture
truth. Strengthen the existing
`test_background_loads_required_runtime_dependencies_before_registering_jobs`
node in place to require telemetry after protocol and before job registration;
do not rename or recount it.

- [x] **Step 5: Remove caller DB status from native/API contracts**

Use Pydantic `extra="forbid"`. Native host validates required identity and
timestamps, forwards the structured result to the fixed endpoint, and returns
only stable persistence fields. The sidecar derives status and event hash.

- [x] **Step 6: Implement atomic local-store dedupe**

Do not call `list_runs()` then insert. Open one connection, `BEGIN IMMEDIATE`,
parse existing extension payload event identities, compare canonical event
hash, then insert or return existing. Commit exactly once.

- [x] **Step 7: Prove no scheduler/backoff coupling**

Strengthen existing `/jobs/status`/history tests and add a source census in
the evidence ledger. The scheduler modules and scheduler-state store must have
zero product diff.

Observed: Chrome manifest plus scheduler/data-scheduler owners are
byte-identical. The old direct `recordExtensionJobAsync`, caller-status
classifier, and slug-derived job writer have zero residual hits.

- [x] **Step 8: Verify GREEN and rebuild**

```bash
pytest -q tests/test_sa_extension_telemetry_outbox.py \
  tests/test_sa_native_host_telemetry.py tests/test_job_runs.py \
  tests/test_sa_extension_run_protocol.py
tmp="$(mktemp -d)"
python3 extensions/sa_alpha_picks/build_firefox.py \
  --source extensions/sa_alpha_picks --output "$tmp/firefox"
rm -rf "$tmp"
```

Expected: outbox `8/8`; native `14/14`; job runs `63/63`; protocol `12/12`.

Observed: those four suites are exactly `8/8`, `14/14`, `63/63`, and
`12/12`; with Alpha adapter coverage the Task 3 core is `105/105`. The
canonical 12-file focused set is `284/284`. Full collection is `4667` and
focused collection is `284`; sorted node-list SHA-256 values are
`51548195153e1f9e12a24fa5475d9de33b4afba9e813ae3a5ce5abd1a66ef085`
and `2c3b4e302fff4c190ebbc3bb5a05db2b4ece2186a5c2d0430b41bab25217a717`.
Two independent Firefox builds are byte-identical and contain exactly `14`
files; normalized artifact hash-list SHA-256 is
`951dc32c892a1d35f64fcb0b0d49eb31752536420f913aa8522a4850444dc7b5`.

- [x] **Step 9: Commit**

```bash
git add extensions/sa_alpha_picks/extension_telemetry.js \
  extensions/sa_alpha_picks/background.js \
  extensions/sa_alpha_picks/manifest.firefox.json \
  src/sa_native_host.py src/api/routes/jobs.py src/service/job_runs_store.py \
  tests/js/run_sa_extension_telemetry_fixture.mjs \
  tests/test_sa_extension_telemetry_outbox.py \
  tests/test_sa_native_host_telemetry.py tests/test_job_runs.py
git commit -m "feat: persist SA extension telemetry idempotently"
```

Resolved Task 3 product tip:
`df49d5b5369193c4bd94ef660cd90df0892d956e`.

---

## Task 4: RED-First Healthy Anchors and Localized Durable Health

**Files:**
- Modify `src/service/sa_extension_health.py`
- Modify `src/service/sa_market_news_health.py`
- Modify `src/service/provider_health.py`
- Modify `tests/test_sa_extension_health.py`
- Modify `tests/test_sa_market_news_health.py`
- Modify `tests/test_provider_health.py`
- Modify the six web files and four web tests listed in File Map

- [x] **Step 1: Add ten backend RED nodes**

`tests/test_sa_extension_health.py`:

```text
test_latest_structured_degraded_run_reports_stable_code_and_counts
test_legacy_succeeded_run_is_unverified_not_healthy
test_repair_segment_reports_active_and_terminal_structured_state
test_new_telemetry_segments_never_expose_raw_backend_detail
```

`tests/test_sa_market_news_health.py`:

```text
test_latest_derived_complete_sync_is_the_only_extension_success_anchor
test_later_degraded_run_updates_attempt_without_advancing_success
test_skipped_and_legacy_succeeded_rows_do_not_advance_success
test_structured_summary_outage_degrades_without_hiding_capture_stats
```

`tests/test_provider_health.py`:

```text
test_sa_provider_uses_derived_complete_success_and_latest_attempt_separately
test_sa_provider_ignores_legacy_and_skipped_success_rows
```

Observed: the three backend owner suites were exactly `11 failed / 58 passed`
before product edits. The ten new nodes plus the evolved structured-summary
owner failed on generic-success/raw-detail behavior; unrelated nodes remained
green.

- [x] **Step 2: Add frontend RED accounting**

Rename the one obsolete raw-detail-preservation node to its named successor.
Add four further `saExtensionHealthDisplay` nodes covering localized counts,
unknown-code fail-closed behavior, bounded Developer code, and repair state.
Add three `SettingsProviderConfig` mounted nodes covering normal-mode zero raw
detail, Developer stable-code-only output, and a localized degraded row.

Observed: the presenter plus mounted Settings suites were exactly
`9 failed / 34 passed` before frontend product edits. The named successor and
seven new nodes failed for the absent structured presentation contract.

- [x] **Step 3: Implement structured summaries and health projections**

One store summary returns latest attempt plus latest structured
derived-complete timestamp. `sa_market_news_health` and `provider_health` use
that same result. Do not duplicate row interpretation.

- [x] **Step 4: Implement the additive API/presenter contract**

Existing setup segments remain compatible. Telemetry and repair segments omit
raw `detail`. Unknown segment keys remain visible as stable identifiers, but
unknown condition copy is generic and localized.

- [x] **Step 5: Add exactly 13 resource leaves and evolve counts**

Both locale key sets must remain equal/nonempty. Settings becomes `694`, total
`1794`. No popup English is added to app resources.

- [x] **Step 6: Verify focused backend/frontend and i18n gates**

```bash
pytest -q tests/test_sa_extension_health.py \
  tests/test_sa_market_news_health.py tests/test_provider_health.py \
  tests/test_job_runs.py

cd apps/arkscope-web
npx vitest run \
  src/saExtensionHealthDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/i18n/resources.test.ts
npm run typecheck
npm run check:i18n-literals
```

Expected: frontend `4 files / 69` nodes; resources `694/1794`; scanner remains
`36/20/0/20` because all copy lives in resources.

Observed: canonical backend collection is `4677`, the 12-file focused set is
`294/294`, and sorted node-list SHA-256 values are
`ec699e992433f5c2cabe612e5f609fad1ca64ae88915034bb8e56aa2bfcd7de9`
and `d35c5155ed480f3495567ce172bc00b391b6e69d4768526d288d2b738a679a47`.
Frontend is exactly `95 files / 1063 passed`; the four-file focused set is
`69/69`, with sorted relative node-list SHA-256 values
`a93c02bc28d1924f23f7895338d723e968dcb389a494ff0e0f993e4c092019d4`
and `5c3859c3c7db7fe90c13f3c46d49610eae64986ef0b89e558246ee0cf13c6cdf`.
TypeScript, resource parity/nonempty (`694/1794`), and scanner
`36/20/0/20` all pass. The full-suite diagnostic-sink ratchet caught a
presenter output initially named `detail`; renaming that reviewed output to
`copy` removed the ambiguous raw-detail sink without changing node accounting.

- [x] **Step 7: Commit**

```bash
git add src/service/sa_extension_health.py \
  src/service/sa_market_news_health.py src/service/provider_health.py \
  tests/test_sa_extension_health.py tests/test_sa_market_news_health.py \
  tests/test_provider_health.py \
  apps/arkscope-web/src/api.ts \
  apps/arkscope-web/src/saExtensionHealthDisplay.ts \
  apps/arkscope-web/src/settings/settingsBackendCopy.ts \
  apps/arkscope-web/src/settings/DataSourcesSection.tsx \
  apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts \
  apps/arkscope-web/src/i18n/resources/en/settings.ts \
  apps/arkscope-web/src/saExtensionHealthDisplay.test.ts \
  apps/arkscope-web/src/settings/settingsBackendCopy.test.ts \
  apps/arkscope-web/src/SettingsProviderConfig.test.ts \
  apps/arkscope-web/src/i18n/resources.test.ts
git commit -m "feat: surface structured SA extension degradation"
```

Check staged paths before committing. Do not stage unrelated generated or
user files.

Resolved Task 4 product tip:
`1e52ed4e391d42ff9421b42308ba14a6fad15ed6`. The post-commit Firefox
dependency-closure build succeeds and contains exactly the same 14 reviewed
runtime files.

---

## Task 5: RED-First Durable Market News Repair Domain

**Files:**
- Create `src/sa/market_news_recovery.py`
- Modify `src/service/job_runs_store.py`
- Modify `src/api/routes/seeking_alpha.py`
- Modify `src/api/routes/jobs.py`
- Modify `src/sa_native_host.py`
- Modify `src/tools/data_access.py`
- Modify `src/tools/backends/sa_capture_backend.py`
- Create `tests/test_sa_market_news_recovery.py`
- Modify `tests/test_sa_tools.py`

- [x] **Step 1: Add sixteen RED domain nodes**

```text
test_manifest_json_and_hash_are_canonical_and_order_independent
test_manifest_accepts_only_canonical_sa_pathnames_without_query_or_fragment
test_recorded_failure_preview_has_no_age_cutoff_and_does_not_classify_legacy_prose
test_latest_structured_retryable_ids_can_be_previewed_contextually
test_incident_preview_uses_latest_derived_complete_anchor
test_incident_preview_caps_at_168_hours_or_marks_missing_anchor_unverified
test_preview_separates_known_detail_targets_from_unknown_metadata_gap
test_zero_target_rules_distinguish_no_work_from_real_discovery_scope
test_atomic_start_returns_one_running_run_and_manifest_under_concurrency
test_resume_preserves_run_id_manifest_hash_and_baseline
test_progress_checkpoint_is_idempotent_by_news_id_and_attempt_id
test_conflicting_or_incompatible_progress_is_rejected_without_write
test_finalize_reconciles_already_present_repaired_and_source_unavailable
test_finalize_marks_missing_or_omitted_targets_failed_retryable
test_cancel_and_stale_interruption_preserve_resumable_manifest_truth
test_terminal_status_counts_and_result_hash_are_derived_and_idempotent
```

The atomic-start node must race both identical and different requested
manifests. There is still only one running row; a competing request receives
the already-running run ID and its actual immutable manifest, never a response
that relabels it as the newly requested scope.

- [x] **Step 2: Add five RED DAL/backend nodes**

```text
test_market_news_rows_by_exact_ids_ignore_age_and_return_only_manifest_fields
test_market_news_body_presence_readback_is_exact_for_frozen_ids
test_market_news_missing_detail_interval_uses_inclusive_canonical_bounds
test_recovery_queries_and_job_history_never_expose_titles_bodies_full_urls_or_target_paths
test_market_news_recovery_queries_fail_closed_when_local_db_is_unavailable
```

- [x] **Step 3: Implement read-only preview queries**

Use bound SQL parameters and SQLite read-only connections. Return only opaque
ID, canonical pathname, published timestamp, and body-presence bit. Existing
routine candidate query and 24-hour predicate remain unchanged.

- [x] **Step 4: Implement manifest service**

Recorded failure target extraction may read legacy `detail_failures[].news_id`
only as target evidence. It may not use legacy `error` to assign state/reason.
Incident preview reads the structured complete anchor and returns actual
interval plus separate discovery descriptor.

- [x] **Step 5: Implement atomic repair store operations**

The running result may hold checkpoint progress. Immutable manifest remains in
payload. Verify payload hash before every progress/final call. Never overwrite
or re-freeze baseline fields.

- [x] **Step 6: Add fixed sidecar routes and native actions**

Use explicit request models for preview, start, state, checkpoint, finalize,
and cancel. The native host maps action names to these exact routes; extension
input cannot supply a sidecar path. Generic `/jobs/status` and `/jobs/history`
must project repair rows to count/state/run/hash-prefix metadata and omit exact
target descriptors; fixed repair state/execution routes retain the full
machine contract.

- [x] **Step 7: Verify GREEN on synthetic DBs**

```bash
pytest -q tests/test_sa_market_news_recovery.py tests/test_sa_tools.py \
  tests/test_job_runs.py tests/test_sa_native_host_telemetry.py
```

Expected new recovery `16/16`; `test_sa_tools.py` `102/102`.

Observed: recovery is `16/16`; `test_sa_tools.py` is `102/102`; the four-file
Task 5 execution set is `195/195`. Backend collection is exactly `4698`, and
the 13-file checkpoint collection is exactly `315`. Their sorted node-list
SHA-256 values are
`d7c35ad0fae96f6f0e4fd0211fdc9a1bdd8e51eeb63d616587f435dabff2f284`
and
`3f1b0a608ab2037c403e57eddb53c31dca47e10ef47977d2c10b6e1594375b48`.
The full-suite diagnostic run retained the existing bare-data failure family
and identified twelve earlier Task 3/4 harness/legacy-anchor assertions for
in-place evolution before final canonical A/B; no Task 5 node failed.

- [x] **Step 8: Commit**

```bash
git add src/sa/market_news_recovery.py src/service/job_runs_store.py \
  src/api/routes/seeking_alpha.py src/api/routes/jobs.py src/sa_native_host.py \
  src/tools/data_access.py src/tools/backends/sa_capture_backend.py \
  tests/test_sa_market_news_recovery.py tests/test_sa_tools.py \
  tests/test_job_runs.py tests/test_sa_native_host_telemetry.py
git commit -m "feat: add audited resumable Market News repair"
```

Resolved Task 5 product tip:
`8b20e608765d2ef134a6249a2ebf0bccd400361f`.

---

## Task 6: RED-First Extension Recovery Runtime and Honest Popup

**Files:**
- Create `extensions/sa_alpha_picks/popup_action_catalog.js`
- Modify `extensions/sa_alpha_picks/background.js`
- Modify `extensions/sa_alpha_picks/popup.html`
- Modify `extensions/sa_alpha_picks/popup.js`
- Modify `tests/test_sa_extension_reconciliation_ui.py` without node-count
  change
- Create `tests/js/run_sa_extension_popup_fixture.mjs`
- Create `tests/test_sa_extension_popup.py`

- [x] **Step 1: Add twelve RED mounted/runtime nodes**

```text
test_popup_groups_exactly_five_normal_actions_as_three_plus_two
test_each_normal_action_has_one_hover_focus_and_aria_description_owner
test_action_disclosure_has_scope_when_to_use_and_non_guarantee_for_every_action
test_alpha_rows_show_exact_deep_bounds_and_never_use_market_18_30_80_limits
test_configured_comment_limits_render_or_report_configured_limit_unavailable
test_retry_recorded_failures_exists_only_for_real_retryable_ids
test_advanced_recovery_is_collapsed_normally_and_promoted_by_a_real_gap
test_recovery_confirmation_repeats_actual_interval_known_ids_and_discovery_scope
test_zero_executable_scope_starts_no_job_but_zero_known_ids_can_start_discovery
test_active_repair_resumes_the_same_run_id_and_manifest_hash_after_popup_reopen
test_recorded_and_incident_runtime_use_exact_ids_bounds_mutex_and_reach_evidence
test_popup_stays_english_keyboard_coherent_and_free_of_true_text_clipping
```

Observed: exactly `12 failed`; every node reached the mounted fixture and
failed on the absent catalog, grouped controls, recovery runtime, or bounded
disclosure rather than on harness setup.

- [x] **Step 2: Build one structured action-limit response**

Fixed values are read from live background constants. Native Full/Deep batch
limits are numeric or unavailable. Test all five rows against source constants
and reject a shape that labels Market `18/30/80` as Alpha detail bounds.

- [x] **Step 3: Implement structured last-run status and descriptions**

Use DOM construction/textContent. Do not use `innerHTML` for dynamic values.
Only stable reason labels from the catalog/protocol render. Reopening the popup
loads last structured state and triggers outbox flush without replaying stale
alerts.

- [x] **Step 4: Implement recovery messages under the shared mutex**

Recorded repair traverses the frozen target list with no age filter. Incident
scan tracks rounds, elapsed time, growth, oldest observed timestamp, stable
rounds, reached-start evidence, and unresolved interval. At most 80 detail
attempts occur per pass; Resume continues the same manifest.

- [x] **Step 5: Implement contextual and Advanced controls**

No F12 path is required. A diagnostic wrapper, if retained, must call the
same public runtime action and return run ID/hash. Preserve the existing Alpha
article-link review and manual URL disclosure under their reconciliation
contract; the new Market News Advanced disclosure is a separate owner.

- [x] **Step 6: Evolve the existing English boundary node**

Add `popup_action_catalog.js`, protocol, and telemetry product copy to the
existing CJK census without renaming the node.

- [x] **Step 7: Verify mounted behavior and packaging**

```bash
pytest -q tests/test_sa_extension_popup.py \
  tests/test_sa_extension_reconciliation_ui.py \
  tests/test_sa_extension_alpha_picks.py \
  tests/test_sa_extension_packaging.py
tmp="$(mktemp -d)"
python3 extensions/sa_alpha_picks/build_firefox.py \
  --source extensions/sa_alpha_picks --output "$tmp/firefox"
diff -u <(find "$tmp/firefox" -maxdepth 1 -type f -printf '%f\n' | sort) \
  <(python3 extensions/sa_alpha_picks/build_firefox.py \
       --source extensions/sa_alpha_picks --list \
       | sed 's/^manifest\.firefox\.json$/manifest.json/' | sort)
rm -rf "$tmp"
```

Task 6 execution correction: the independently reviewed command named a
nonexistent `--print-expected-files` option. The side-effect-free graph CLI
shipped by Task 1 is `--list`; the `sed` projection reflects the builder's
intentional source `manifest.firefox.json` to artifact `manifest.json`
rename. This docs-only correction changes no product or node accounting.

Expected: popup `12/12`; reconciliation `9/9`; Alpha `8/8`; packaging
`10/10`.

Observed: the canonical Task 6 set is exactly `39/39`; all four JavaScript
syntax checks pass. A fresh Firefox build contains exactly `15` files, and its
sorted file list equals the side-effect-free dependency-graph projection.

Four bounded, zero-node-count execution evolutions are explicit:

1. `tests/test_sa_extension_reconciliation_flow.py` now loads the real
   protocol/telemetry dependency graph through `importScripts`; the same 11
   existing node IDs no longer rely on an incomplete VM.
2. `tests/test_sa_local_readers.py` seeds the existing health node with a
   structured derived-complete event rather than a legacy unverified success
   row. Its node ID is unchanged.
3. `install_firefox.sh` and `FIREFOX.md` now name the shipped `Quick Update`
   control instead of the retired `Quick Refresh` label.
4. The reviewed packaging command typo is corrected above from the nonexistent
   option to the shipped `--list` projection. This is docs-only.

- [x] **Step 8: Commit**

```bash
git add extensions/sa_alpha_picks/background.js \
  extensions/sa_alpha_picks/popup.html extensions/sa_alpha_picks/popup.js \
  extensions/sa_alpha_picks/popup_action_catalog.js \
  tests/js/run_sa_extension_popup_fixture.mjs \
  tests/test_sa_extension_popup.py \
  tests/test_sa_extension_reconciliation_ui.py
git commit -m "feat: make SA extension controls bounded and auditable"
```

Resolved Task 6 product tip:
`679b7a65a97fc48f8b8d1f9551ad95c597b424db`.

---

## Task 7: Canonical Static, Accounting, and Copied-DB Gates

**Files:**
- Create/update the redacted evidence ledger
- No product changes unless a failed gate triggers reviewed deviation

- [x] **Step 1: Prove exact node accounting**

Collect base and tip in clean virgin archives with the same Python/Node
dependencies. Normalize and `comm` the lists.

Required:

```text
backend: +91/-2, final 4710
backend focused: 14 files / 327
frontend: +8/-1, final 95 files / 1063
frontend focused: 4 files / 69
```

Every removed ID must be one of the three named removals in Exact Test
Accounting.

- [x] **Step 2: Run canonical focused suites**

```bash
pytest -q \
  tests/test_extension_install_paths.py \
  tests/test_sa_extension_packaging.py \
  tests/test_sa_extension_run_protocol.py \
  tests/test_sa_extension_telemetry_outbox.py \
  tests/test_sa_market_news_recovery.py \
  tests/test_sa_extension_popup.py \
  tests/test_sa_extension_alpha_picks.py \
  tests/test_sa_extension_reconciliation_ui.py \
  tests/test_sa_native_host_telemetry.py \
  tests/test_job_runs.py \
  tests/test_sa_extension_health.py \
  tests/test_sa_market_news_health.py \
  tests/test_provider_health.py \
  tests/test_sa_tools.py

cd apps/arkscope-web
npx vitest run \
  src/saExtensionHealthDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/i18n/resources.test.ts
```

Expected: backend `327/327`; frontend `69/69`.

- [x] **Step 3: Run full suites and build gates**

```bash
cd /mnt/md0/PycharmProjects/ArkScope-sa-extension-reliability
pytest -q
cd apps/arkscope-web
npm test
npm run typecheck
npm run build
npm run check:i18n-literals
```

Expected collections `4710` and `95/1063`; scanner `36/20/0/20` and
unchanged manifest hashes. Record any pre-existing environment failures by
canonical A/B failure-set equivalence; do not relabel them passing.

- [x] **Step 4: Prove packaging closure after all extension edits**

Rebuild twice into empty temporary directories. Exact file lists and file
hashes must match. Delete one copied source dependency in a disposable tree
and prove build failure leaves an existing output byte-identical.

- [x] **Step 5: Prove byte-identical boundaries**

Run the fixed-base gates below:

```bash
git diff --exit-code c49a2417 -- \
  sql data_sources resources/skills \
  src/agents src/analysis src/auth_drivers src/collectors \
  src/fundamentals src/macro_calendar src/monitor src/news_normalized \
  src/options_math src/signals \
  src/research_runtime_config.py src/research_threads.py \
  src/research_errors.py src/research_run_manager.py \
  src/research_history.py src/research_runs.py \
  src/portfolio_observations.py src/portfolio_state.py \
  src/portfolio_activity.py src/portfolio_capture.py \
  src/portfolio_capture_ibkr.py src/portfolio_capture_scheduler.py \
  src/portfolio_capture_types.py src/portfolio_ibkr.py \
  src/portfolio_overview.py src/market_data_admin.py \
  src/market_data_direct.py src/tools/portfolio_holdings_tools.py \
  src/tools/portfolio_tools.py \
  apps/arkscope-desktop \
  apps/arkscope-web/src/styles.css \
  apps/arkscope-web/src/shell/shell.css \
  apps/arkscope-web/src/ui/primitives.css \
  apps/arkscope-web/src/settings/settings.css \
  apps/arkscope-web/package.json apps/arkscope-desktop/package.json \
  package.json package-lock.json requirements.txt

git diff --exit-code c49a2417 -- \
  extensions/sa_alpha_picks/manifest.json \
  extensions/sa_alpha_picks/article_identity.js \
  extensions/sa_alpha_picks/scrape.js \
  extensions/sa_alpha_picks/scrape_articles_list.js \
  extensions/sa_alpha_picks/scrape_comments.js \
  extensions/sa_alpha_picks/scrape_market_news.js

git diff --unified=0 c49a2417 -- \
  extensions/sa_alpha_picks/scrape_detail.js \
  src/tools/backends/sa_capture_backend.py \
  src/tools/data_access.py \
  apps/arkscope-web/src/settings/DataSourcesSection.tsx
```

The final command is an explicit hunk audit: only the conditional removed
marker, reviewed Market News read helpers, and non-formatter health rendering
may differ. Compare every formatter implementation and behavior-test path
named in `docs/design/I18N_FORMATTER_INVENTORY.md` against `c49a2417`; record
the exact resolved path list and hashes in evidence. No other scraper,
continuity transition, routine-cadence/budget, or formatter hunk is allowed.

- [x] **Step 6: Create two isolated 0600 backup pairs**

Use `sqlite3.Connection.backup()` to create pair A and pair B, each containing
one production-snapshot `profile_state.db` and one production-snapshot
`sa_capture.db` (four `/tmp` database files total). Immediately `chmod 0600`.
Do not stop or write production for this probe. Record pre-probe production
size/mtime/integrity and verify them unchanged afterward.

- [x] **Step 7: Run copied-DB preview and state-machine proof**

On snapshot pair A, run read-only recorded-failure and incident previews twice.
Require the same hash/counts and no pair-A DB changes. On snapshot pair B, use
synthetic fake IDs only to prove:

1. atomic start;
2. duplicate start returns same run;
3. progress idempotence;
4. interruption/resume;
5. body readback reclassification;
6. failed retryable prevents complete;
7. terminal result hash;
8. second finalize is idempotent;
9. integrity check `ok`; and
10. FK violations `0`.

Do not execute browser repair against production IDs during this task.

- [x] **Step 8: Record the fresh historical preview privately**

Evidence may state run count, unique ID count, current body-present/missing
counts, interval, and manifest hash. Ordinary committed evidence must replace
exact IDs with stable salted hashes and must not contain title/body/full URL.
Any unexplained drift is a stop condition.

---

## Task 8: Isolated Chrome/Firefox Runtime and Accessibility Gate

**Files:**
- Evidence ledger only unless a reviewed deviation is required

- [x] **Step 1: Start an isolated sidecar**

Use copied DBs, `ARKSCOPE_PROFILE_DB`, `ARKSCOPE_SA_DB`, scheduler disabled,
and unused ports. Point a temporary native-host config at that sidecar. Never
overwrite the user's production native config; restore/remove the temporary
path after the gate.

- [x] **Step 2: Load fresh artifacts**

Load Chrome from the source graph and Firefox from a newly generated artifact.
Do not reuse the manually repaired old Firefox build. Verify every expected
runtime file is present before loading.

- [x] **Step 3: Run outcome/telemetry lifecycle**

Prove:

1. healthy quick sync -> capture complete + persisted + DB succeeded;
2. injected one-detail failure -> capture degraded + DB failed;
3. healthy anchor does not advance;
4. sidecar down -> capture usable + audit pending;
5. popup reopen shows pending and flushes once;
6. sidecar restored -> same event persists once and anchor updates only if the
   captured run itself was complete; and
7. outbox count/age eviction is visible in a synthetic fixture, not production.

- [x] **Step 4: Run popup interaction matrix**

In both browsers, verify five controls, 3+2 grouping, hover/focus descriptions,
inline table, contextual Retry, Advanced disclosure, confirmation, resume,
tab order, and no DevTools requirement. Use element-level clipping census at
the shipped popup width; exclude visually hidden nodes and intentional masked
values only.

- [x] **Step 5: Run bounded recovery probes on synthetic targets**

Use fake fixture-backed pages or a bounded test responder, never licensed
committed content. Prove exact-ID no-age retry, 30-hour actual interval, >168h
cap, separate metadata discovery, zero-known-ID discovery, reached-start and
unresolved interval evidence, close/reopen resume, and shared mutex.

- [x] **Step 6: Run localized web health matrix**

At `390`, `760`, `960`, and `1440` in `zh-Hant` and `en`, render complete,
degraded, unknown-code, active-repair, retryable-repair, and telemetry-unseen
states. Require zero raw planted detail in normal mode, only a validated stable
code in Developer Mode, and no document or element-level text clipping.

- [x] **Step 7: Clean the isolated environment**

Stop sidecar/browser test profiles, remove temporary native config and DB
copies containing licensed data, and verify all test ports refuse connections.
Do not remove retained production backups created later during approved repair.

---

## Task 9: Review-Ready Evidence and Handoff

**Files:**
- Create `docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md`
- Modify this plan status
- Modify priority map/roadmap status to review-ready, not LIVE

- [x] **Step 1: Write the evidence ledger**

Include:

- base, `PACKAGING_GATE_TIP`, and final 40-character hashes;
- exact `+91/-2` and `+8/-1` node diffs;
- final normalized node-list hashes;
- protocol fixture and packaging artifact hashes;
- outbox count/age/record-byte/total-byte bounds and idempotence proof;
- failed-row consumer audit;
- copied-DB preview counts/hash with redacted IDs;
- synthetic repair state-machine result;
- Chrome/Firefox popup/accessibility evidence;
- localized web health evidence;
- protected-boundary diffs; and
- commands, exit codes, and honest environmental limitations.

- [x] **Step 2: Run final cleanliness checks**

```bash
git diff --check
git status --short
rg -n "detail_failed.*succeeded|status: outcome.status|status=request.status" \
  extensions/sa_alpha_picks src tests
rg -n "scrape\\*\\.js|rm -rf \"\\$BUILD_DIR\"" \
  extensions/sa_alpha_picks/install_firefox.sh
rg -n "title=|window\.confirm|help\.html" \
  extensions/sa_alpha_picks/popup.html extensions/sa_alpha_picks/popup.js \
  extensions/sa_alpha_picks/popup_action_catalog.js
```

Expected: no legacy contradictory status path, no glob/destructive installer
assembly, and no duplicate help/confirmation mechanisms. Review every hit;
comments/fixtures are not silently ignored.

- [x] **Step 3: Commit evidence/status**

```bash
git add docs/superpowers/evidence/2026-07-25-sa-extension-reliability-control-clarity.md \
  docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md \
  docs/design/PROJECT_PRIORITY_MAP.md docs/design/SA_EXTENSION_ROADMAP.md
git commit -m "docs: record SA extension reliability evidence"
```

- [x] **Step 4: Stop at independent implementation review**

Do not merge, install into production browsers, write production telemetry,
or execute historical repair. Report the review-ready tip and exact commands.

---

## Task 10: Post-Merge Popup Contrast Repair

**Files:**
- Modify `tests/js/run_sa_extension_popup_fixture.mjs`
- Modify `tests/test_sa_extension_popup.py`
- Modify `extensions/sa_alpha_picks/popup.html`
- Modify `extensions/sa_alpha_picks/popup_action_catalog.js`
- Modify this plan and the design/evidence/priority/roadmap closeout records

- [ ] **Step 1: RED - expose browser-computed contrast evidence**

Add one `contrast_audit` fixture scenario. It must open every `<details>`,
remove `hidden` only inside the disposable fixture DOM, provide text for the
resolved auto-sync hint, render the recovery confirmation and reconciliation
buttons, and return computed foreground/background/border/font properties for
every text-bearing button plus every non-empty visible text node. Transparent
backgrounds resolve through ancestors to the body background.

The Python node computes WCAG relative luminance from those returned RGB
values. It requires ordinary text `>=4.5`, large text `>=3.0`, and any button
whose fill does not distinguish it from its surrounding surface to have a
boundary `>=3.0`. Disabled buttons are reported separately and must retain a
readable label even though WCAG exempts inactive controls.

- [ ] **Step 2: Verify RED for the grounded failures**

Run:

```bash
pytest -q tests/test_sa_extension_popup.py::test_popup_all_states_use_contrast_safe_text_and_control_boundaries
```

Expected: FAIL listing the five normal actions, two auto-sync helper lines,
resolved-window hint, partial status, `reviewRecoveryScopeBtn`, `manualBtn`,
and the normal action boundary. The three recovery descendants and Retry must
not appear in the failure list.

- [ ] **Step 3: GREEN - repair the single CSS owner**

In `popup.html`:

- delete the five ID-specific normal-action background/hover rules;
- use `#174b72` on `#fff` with `#7b93ab` border for `.action-button` and the
  outline review control;
- use `#666` for helper copy;
- use `#b45309` for partial status on `#fff3e0`;
- use `#315f7d` with white text for the manual action and existing filled
  recovery actions;
- set disabled text to a dark foreground on `#bdbdbd`; and
- keep every filled reconciliation variant's white foreground explicit.

In `popup_action_catalog.js`/`popup.html`, add exactly one shared disclosure
note stating that scans may activate and scroll Seeking Alpha tabs and that
switching tabs in the same browser during a run is unsupported.

- [ ] **Step 4: Verify GREEN and mutation sensitivity**

Run the new node and the focused pair. In disposable copies, independently
restore one legacy ID background, remove the review-control variant, restore
the orange manual background, and restore each low-contrast helper/partial
value. Every mutation must make the contrast node RED for the expected owner.

Expected focused result: `23 passed` (`+1/-0`).

- [ ] **Step 5: Run Chrome and Firefox visual gates**

Load Chrome from source and Firefox from a fresh deterministic artifact. Open
all disclosures and drive conditional controls visible. Verify computed
contrast, keyboard focus, descriptions, no clipping, five normal actions, and
the new shared tab-activation warning. Confirm both browsers render the
outline boundary and all filled actions clearly.

- [ ] **Step 6: Close out only after installed-browser proof**

Record the contrast gate gap, historical repair result, Firefox-only
auto-sync operating choice, and P2.6 Part 2 boundary. The operating choice is
not a browser capability claim: Firefox is the single auto-sync owner because
scrolling captures activate a working tab, isolating automation from daily
Chrome use and avoiding duplicate schedules. Chrome remains a manual fallback.
An app-owned collector remains unadopted and requires its own decision/spec.
Only then mark design, plan, evidence, roadmap, and priority map LIVE COMPLETE.

---

## Independent Reviewer Focus

1. Reproduce base -> `PACKAGING_GATE_TIP` -> final rather than only base ->
   final. Later runtime work must not mask packaging regressions.
2. Recompute `+91/-2` backend and `+8/-1` frontend by node ID.
3. Verify the two backend and one frontend removals are exactly the named
   semantic successors.
4. Delete/rename `article_identity.js` in a disposable tree and verify atomic
   builder failure preserves prior output.
5. Add a dynamic injection expression and verify hard failure.
6. Run the JS/Python fixture corpus independently and inspect incompatible
   state/reason cases.
7. Confirm no request model or native message accepts independent DB status.
8. Race duplicate telemetry and repair starts; require one row/run.
9. Verify degraded maps to DB failed but never scheduler backoff.
10. Verify last healthy ignores degraded, skipped, and legacy unstructured
    succeeded rows.
11. Confirm outbox record precedes native send and eviction is visible.
12. Confirm historical generic prose supplies target identity only.
13. Confirm recorded-ID repair has no age predicate and incident discovery has
    a 168-hour cap.
14. Confirm zero-known-ID incident discovery remains executable and honest.
15. Confirm terminal item states derive from capture readback and explicit
    source evidence only.
16. Confirm Alpha disclosures use 5/200 rounds, no global detail cap,
    4/12/20 enrichment, 12/80/140 comment scrolls, and native 10/50 defaults;
    reject any Alpha `18/30/80` copy.
17. Confirm exactly five permanent controls and one description owner per
    control.
18. Confirm web health has localized code/count copy and zero arbitrary detail.
19. Re-run copied-DB manifest/hash/idempotence proof without production writes.
20. Verify protected schema, continuity, scraper, CSS, desktop, package, prompt,
    and unrelated i18n boundaries.

## Post-Review Merge and Production Repair Procedure

This section executes only after independent implementation GREEN and explicit
user approval. Merge approval and historical-repair approval are separate.

### Merge and deployment

1. Stop extension auto-sync and close ArkScope, Chrome, Firefox, sidecar, native
   hosts, and schedulers that can write the affected stores.
2. Create retained timestamped 0600 SQLite online backups of production
   `profile_state.db` and `sa_capture.db`; run integrity and FK checks.
3. Restore any test-only config and require clean worktrees.
4. `git merge --ff-only codex/sa-extension-reliability`.
5. Rerun merged focused `327`, frontend `69`, full collections/runs, typecheck,
   build, scanner, package closure, no-PG smoke, and byte gates.
6. Build Firefox only with merged code. Reload Chrome source and Firefox fresh
   artifact through normal browser UI. The user may perform the browser click;
   no F12 command is part of deployment.
7. Restart ArkScope/sidecar and run one bounded normal sync. Verify structured
   telemetry and localized health before considering repair.

### Fresh historical preview and approval

1. Keep auto-sync off.
2. Generate the fresh `recorded_failures` preview through the shipped popup/API
   path.
3. Compare run count, unique IDs, current body presence, interval, and manifest
   hash with review evidence. Do not require `27` or `30`; explain drift.
4. Present exact target count and manifest hash to the user. Stop for explicit
   approval of that exact manifest.

### Repair and closeout

1. Start the approved manifest. More than 80 targets resume under the same
   run/hash; they are never truncated into a false complete run.
2. Monitor per-item checkpoints and telemetry. Browser closure leaves a
   resumable row.
3. Finalize only after capture readback. Report all four states/reasons.
4. Require profile/SA integrity, FK zero, pre/post body-presence counts, result
   hash, idempotent replay, and no duplicate job rows.
5. Unresolved retryable IDs remain explicit; they are not relabeled success.
6. Re-enable auto-sync only after normal quick sync is derived-complete and
   durably persisted.
7. Flip design/plan/evidence/priority/roadmap status to LIVE only after a final
   independent ground-truth check.
8. Remove the worktree and branch only after merge ancestry and clean status
   are proven. Do not push unless the user separately requests it.

## Stop Conditions

Stop and amend/re-review if any of the following occurs:

1. Product/test counts differ from the locked ledger.
2. Packaging needs a hand-maintained fallback or npm dependency.
3. A runtime dependency cannot be statically closed.
4. Build failure can damage the previous known-good artifact.
5. Caller-supplied DB status survives anywhere.
6. JS/Python protocol results differ for any fixture.
7. Paywall/login/modal/empty DOM/soft-404 becomes source-unavailable.
8. Event dedupe or repair start is read-then-write rather than one immediate
   transaction.
9. A schema migration/index is needed.
10. Native host opens profile DB.
11. Routine capture is blocked only because telemetry is down.
12. Repair starts without a durable running row.
13. Extension failed rows enter scheduler backoff/retry.
14. Legacy succeeded rows advance healthy anchors.
15. Recorded-ID retry gains an age predicate.
16. Incident discovery exceeds 168 hours or accepts arbitrary dates.
17. Zero known IDs incorrectly suppress a real discovery interval.
18. Metadata rediscovery is labeled complete history.
19. Popup grows a sixth permanent recovery action, duplicate help prose, or
    CJK copy.
20. Existing Alpha article-link review or manual URL recovery is removed,
    absorbed into Market News recovery, or behaviorally changed.
21. UI presents Market `18/30/80` as Alpha limits.
22. Licensed content enters fixtures, committed evidence, logs, or web copy.
23. Alpha comment continuity semantics, Market routine cadence, `/sa/feed`,
    extension locale authority, Settings sanitizer, calibration refusal,
    Coverage v2, CSS, formatter, agent prompt, or unrelated UI enters scope.
24. Any unexpected product owner must change.
25. Production preview drift cannot be explained before user approval.

## Plan Self-Review Checklist

- [x] Design review amendment and all advisories are reflected.
- [x] Market `18/30/80` is not assigned to Alpha.
- [x] Routine capture and telemetry persistence are separate axes.
- [x] Repair audit creation/finalization is strict and non-circular.
- [x] Packaging lands and is checkpointed before later extension edits.
- [x] Protocol enums, validation, and parity fixtures are closed.
- [x] Outbox count/age/byte policy is explicit and loss is visible.
- [x] Atomic store operations require `BEGIN IMMEDIATE` and no schema.
- [x] Consumer audit names `/jobs/status`, history, health, and scheduler.
- [x] Recovery bounds and no-age historical route are explicit.
- [x] Metadata gap remains unknown before discovery.
- [x] Popup copy has one owner and five normal controls.
- [x] Health localization has exact resource accounting.
- [x] Backend `+91/-2` and frontend `+8/-1` arithmetic closes.
- [x] Every removed test ID and successor is named.
- [x] Copied-DB and production gates keep licensed content out of git.
- [x] Product implementation stops at independent review.
- [x] Historical repair requires a second exact-manifest user approval.
