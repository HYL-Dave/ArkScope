# SA Health Truth and Typed Diagnostics Implementation Plan

> **Status:** PLAN GREEN; TASKS 0-3 COMPLETE; TASKS 4-6 BATCH EXECUTION ACTIVE;
> TASK 7, MERGE, PUSH, AND LIVE TRAFFIC NOT AUTHORIZED
>
> **Date:** 2026-08-14
>
> **Design authority:**
> `docs/superpowers/specs/2026-08-13-sa-health-schedule-layout-design.md`.
> The user approved the base design and the later diagnostic/hash-migration
> rulings. Macro scheduler/layout closed at `9c9021af`; this plan is the
> required post-Macro re-grounding.
>
> **Product grounding base:** `9c9021afe6e9fe4d27a971f0841d38d213354a94`
> (docs-only closeout over reviewed Macro cutover `da7efd9a`).
>
> **Roles:** Codex authors and implements RED-first after independent plan
> review. Fable independently reconstructs identities, reviews evidence and
> product diffs, and returns the implementation/merge rulings. The user owns
> product, live-provider, and destructive-data decisions.

**Goal:** separate SA browser/native-host chain truth from the latest capture
outcome, preserve bounded typed failure evidence without raw logs, and make the
Settings panel show an exact cause when one is known without guessing network,
provider-page, browser, or database provenance.

**Architecture:** the API owns diagnostic validation and immutable-event
hashing; `job_runs.payload` stores only admitted diagnostics or a fixed
rejection/absence marker; active native save handlers return one closed local
persistence error envelope; one extension collector records a typed entry
before every failed detail count; the health service owns chain-state and a
bounded 20-run recurrence projection; the frontend renders only admitted DTO
fields. Macro's schedule table and CSS remain inherited, byte-protected
baseline.

**Stack:** Python 3.10, FastAPI, Pydantic, SQLite, Chrome/Firefox extension
JavaScript, React 18, TypeScript, Vitest 4.1.8, Vite 5.4.21, Playwright 1.58.0,
Chrome 150.0.7871.128.

---

## 0. Authority, boundaries, and grounding

### 0.1 Binding decisions

This plan implements design LD 1 through LD 9. The following are locked:

1. `chain_state` replaces top-level `ok`; no parallel compatibility boolean
   remains.
2. Only `config`, `manifests`, `launcher`, `host_ping`,
   `telemetry_binding`, and `capture_readback` determine chain state.
3. `telemetry_last` and `market_news_repair` are operation history and never
   make the chain interrupted.
4. A degraded run is `warn/capture_degraded`; retryable item counts remain
   visible but do not become chain failure.
5. `detail_failures_recorded` retires atomically from producer, frontend
   switch, translations, fixtures, and tests.
6. The API/backend, not the extension, owns canonical event hashing.
7. A request with no diagnostics preserves the exact legacy hash document.
   A present valid envelope hashes admitted diagnostics; an invalid envelope
   hashes only a fixed rejection marker. Raw rejected bytes never persist.
8. `event_conflict` terminally drains the extension outbox item as
   unavailable; it never retries forever or claims persistence.
9. Local save failures expose stable typed classification, not raw exception,
   path, SQL, provider text, or stack trace.
10. Health reads at most the latest 20 completed allowlisted SA extension
    rows. Recurrence is operational history, never repair linkage.
11. `重新檢查` remains a GET-only local read. No polling, provider retry, or
    capture action is added.
12. Traditional Chinese uses `擷取`; this line introduces no `攝入`.
13. Macro owns schedule controls, source IDs, cadence, table wrapping, column
    widths, and CSS. This line does not edit those files.

No live SA/provider request, extension installation, production DB mutation,
schedule change, repair, push, or destructive operation is authorized by this
plan.

### 0.2 Post-Macro baseline

The planning worktree is a no-op-git-crypt linked worktree at exact master
`9c9021af`. The main tree and planning tree were clean before grounding.

| Identity | Count | SHA-256 | Runtime witness |
|---|---:|---|---|
| Backend full | 4,359 | `c100ee5de4ad42c490e6048e4b7cf22540e417f579987c676796663608d17afd` | collect-only, zero test bodies |
| Backend SA focused, 11 files | 275 | `e6ae1a5a38629f558beff0586a98b5e0ea4f28c6a3a516c1302119b874ce3336` | `275 passed` |
| Frontend full | 1,172 / 101 files | `d40a30d5e50690f79b644e0b25122da02441eb0cf54ab02793d02269419e23cb` | inherited Macro closeout |
| Frontend SA owner, 4 files | 74 | `7ec82dccd499299ec0a1ebd796740bea7186a804920b89deb9ad898a968bbd01` | `74 passed` |
| Settings regression, 15 files | 246 | `c1be07c3d9c7335c4d4172af59cae1234c45c5f6429032f33bbff120280070aa` | `246 passed` |
| Native canonical | 4,359 seen | reporter `7bf1eca4...` | `4,347 passed / 12 skipped / 0 failed` |

Backend focused files are:

```text
tests/test_sa_extension_health.py                         11
tests/test_job_runs.py                                    68
tests/test_sa_native_host_telemetry.py                    14
tests/test_sa_extension_telemetry_outbox.py                8
tests/test_sa_extension_alpha_picks.py                     8
tests/test_sa_extension_run_protocol.py                   12
tests/test_sa_extension_packaging.py                      10
tests/test_sa_extension_reconciliation_flow.py            11
tests/test_sa_reconciliation_native_host.py               10
tests/test_sa_local_readers.py                            21
tests/test_sa_tools.py                                   102
```

Frontend SA owner files are:

```text
src/SettingsProviderConfig.test.ts                        41
src/saExtensionHealthDisplay.test.ts                       7
src/settings/settingsBackendCopy.test.ts                  12
src/i18n/resources.test.ts                                14
```

The Settings regression projection is exactly:

```text
src/AppShell.test.tsx                                     22
src/ProviderSection.test.ts                               26
src/SettingsCss.test.ts                                   10
src/SettingsInvestorProfileIntegration.test.tsx            3
src/SettingsModelRouting.test.ts                          17
src/SettingsNewsStorage.test.ts                            7
src/SettingsPostPgExitStorage.test.ts                     14
src/SettingsProviderConfig.test.ts                        41
src/SettingsStabilizationCss.test.ts                       2
src/SettingsWorkspace.test.tsx                            33
src/settings/MacroStorageSection.test.tsx                 14
src/settings/settingsBackendCopy.test.ts                  12
src/settings/settingsCopy.test.ts                         10
src/settings/settingsReadCache.test.ts                    19
src/settings/settingsRegistry.test.ts                     16
```

These 15 per-file counts sum to 246. Task 5 changes this projection only
through the four Provider additions and one Provider removal listed in
Section 2.4, yielding the pinned final 249-node stream.

### 0.3 Dated normal-state visual witness

The user supplied a healthy comparison state after Macro closeout:

| Screenshot | Size | SHA-256 | Observed truth |
|---|---:|---|---|
| `Screenshot from 2026-08-14 13-48-20.png` | 927 x 417 | `3e698db56ffe4765c2859e8429b6833deff504a7a08a321f0be51113abb232b7` | chain available at 13:47 Asia/Taipei; all six structural rows healthy; latest capture complete; historical `market_news_repair` complete at manifest `e93207f17091`; readback healthy |

This is a normal-state regression witness, not evidence that failure
observability is complete. Final browser admission must preserve its green
chain semantics while separately proving degraded/interrupted states with
fixture data.

### 0.4 Owned paths

Product owners:

```text
new src/sa/extension_diagnostics.py
src/api/routes/jobs.py
src/service/job_runs_store.py
src/sa_native_host.py
src/service/sa_extension_health.py
new extensions/sa_alpha_picks/extension_diagnostics.js
extensions/sa_alpha_picks/extension_telemetry.js
extensions/sa_alpha_picks/background.js
extensions/sa_alpha_picks/manifest.firefox.json
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/saExtensionHealthDisplay.ts
apps/arkscope-web/src/settings/DataSourcesSection.tsx
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
```

Test owners:

```text
new tests/test_sa_extension_diagnostics.py
new tests/test_sa_native_host_diagnostics.py
new tests/test_sa_extension_diagnostics_flow.py
new tests/js/run_sa_extension_diagnostics_fixture.mjs
tests/test_sa_extension_health.py
tests/test_sa_extension_telemetry_outbox.py
tests/test_sa_extension_alpha_picks.py
tests/js/run_sa_extension_telemetry_fixture.mjs
tests/js/run_sa_extension_protocol_fixture.mjs
apps/arkscope-web/src/saExtensionHealthDisplay.test.ts
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/i18n/resources.test.ts
```

Task evidence may evolve this plan, the design status/re-grounding section,
`docs/design/PROJECT_PRIORITY_MAP.md`, and one new evidence file. Any other
product/test path is a stop-and-amend event.

### 0.5 Existing owner identity table

| Path | Lines | SHA-256 at `9c9021af` |
|---|---:|---|
| `src/api/routes/jobs.py` | 335 | `457ea7f453a0b5b547644d310bfd62cc74d432856f55c34a45048873a3c7ad29` |
| `src/service/job_runs_store.py` | 1,212 | `7975c34587b590d1dcb59f1bd18dc5094dbeb3e5a948e60e2993315825758d2f` |
| `src/sa_native_host.py` | 1,209 | `711788e0520e6d69c3f535cb76c65332b5409b30ce48289b140698aa90eae777` |
| `src/service/sa_extension_health.py` | 406 | `196a71f9d0393a6303e9f0f4670b5b291ee60f74992078cb288e9f509f21e71e` |
| `extensions/sa_alpha_picks/extension_telemetry.js` | 413 | `62645345250fb0640fce6f8c12cfb5712ea99ab1924188832d48890b15514158` |
| `extensions/sa_alpha_picks/background.js` | 3,127 | `053d1eea77997bbb9705a45f2af1a329f6a9be92023ed4768ecd39f67090e383` |
| `extensions/sa_alpha_picks/manifest.firefox.json` | 35 | `97a89078ce740e3f5198f1296c05e7ba303265403ee8712dfc352383ea123645` |
| `tests/test_sa_extension_health.py` | 485 | `78deff5dd0f40d4acd8c48429763457e361c2f2e4ee342411e9ee0ae7fb0c5f1` |
| `tests/test_sa_extension_telemetry_outbox.py` | 99 | `829af738a9b83ba2fe190feb75e8489052834debc86ea96c62cb7bd08c9e0467` |
| `tests/test_sa_extension_alpha_picks.py` | 239 | `b6f3dd846c44bfd5077818082a1a6c924f6afa5820da5fa01881cf03534d0844` |
| `tests/js/run_sa_extension_telemetry_fixture.mjs` | 237 | `66e29a472b34f78b718ebf9fb46d4cf859fadbca357ca2b3f35285eaf2a62b84` |
| `tests/js/run_sa_extension_protocol_fixture.mjs` | 79 | `8c016fe4d38d99c924dd44358d0a3259abffd6ba010b539b2fca2e7e04e46854` |
| `apps/arkscope-web/src/api.ts` | 3,010 | `62ea6c1ec6a23014c8785db012710b2924daa67a6860a7b3a8ca51f5cc70e0fb` |
| `apps/arkscope-web/src/saExtensionHealthDisplay.ts` | 135 | `c5e256799ad647f4d380d3d19511d92ea4fab913159859ba5bdbb8cd8390ff0b` |
| `apps/arkscope-web/src/settings/DataSourcesSection.tsx` | 896 | `695a7876e5123e0f5e0dcd8c2074bf9d822d59a1bd6aad1d8dda36683689fbd8` |
| `apps/arkscope-web/src/i18n/resources/en/settings.ts` | 1,093 | `8d21837ae234b03e1ee7c7779fb7a33ec149bdde858e73e1fd13567a24b4038e` |
| `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts` | 1,092 | `a459555b7e66090eae25bf0bb7d91b248d999ef867f9933bfa62b75b3bb8dd50` |
| `apps/arkscope-web/src/saExtensionHealthDisplay.test.ts` | 192 | `6a3dbaf665287cc0dbe9d8da16631e3b8f7ccde08e0f6544f148222edb7e6542` |
| `apps/arkscope-web/src/SettingsProviderConfig.test.ts` | 1,717 | `c9265cc9ec73db465b697305e86d82ad798ae69f27b534f84ad57a4184a7529e` |
| `apps/arkscope-web/src/i18n/resources.test.ts` | 1,262 | `8efeb4a357d2272ec0a044b62ed74979caed7166161a838a9297a559173a0376` |

### 0.6 Byte-protected product boundary

The following 17 paths remain byte-identical. The aggregate recipe is exact:
take these literal paths, UTF-8 byte-sort the path lines, pass them in that
order to GNU `sha256sum` (standard `<digest><two spaces><path>\n` output), then
SHA-256 that complete 17-row byte stream including its one final newline.
Equivalently, from the plan worktree at this document version:

```bash
awk '
  /^### 0[.]6 / { in_section = 1 }
  in_section && /^```text$/ { capture = 1; next }
  capture && /^```$/ { exit }
  capture { print }
' docs/superpowers/plans/2026-08-14-sa-health-diagnostics.md \
  | LC_ALL=C sort \
  | xargs sha256sum \
  | sha256sum
```

The resulting aggregate is
`1c5b539a05e51eef3f52e0cad9efa02063db077cfb7e190f20ccdc8b0580e0ae`:

```text
src/sa/extension_run_protocol.py
src/sa_capture_store.py
src/tools/data_access.py
extensions/sa_alpha_picks/extension_run_protocol.js
extensions/sa_alpha_picks/scrape.js
extensions/sa_alpha_picks/scrape_detail.js
extensions/sa_alpha_picks/scrape_articles_list.js
extensions/sa_alpha_picks/scrape_comments.js
extensions/sa_alpha_picks/scrape_market_news.js
extensions/sa_alpha_picks/article_identity.js
extensions/sa_alpha_picks/manifest.json
tests/fixtures/sa_extension/run_outcomes.json
apps/arkscope-web/src/settings/dataScheduleControls.tsx
apps/arkscope-web/src/settings/MacroStorageSection.tsx
apps/arkscope-web/src/Settings.tsx
apps/arkscope-web/src/styles.css
apps/arkscope-web/src/settings/settingsReadCache.ts
```

This protects capture algorithms, retry/cadence, canonical run protocol,
Macro schedule/layout ownership, Settings cache/navigation, and the Chrome
manifest. Firefox gains only the new literal diagnostics dependency; Chrome
loads it through the existing literal `importScripts` dependency closure.

---

## 1. Implementation contract

### 1.1 API validation and canonical event identity

Create `src/sa/extension_diagnostics.py` as the single Python authority for:

- closed stages, target kinds, existing admitted reason codes, and the seven
  diagnostics-only reason codes;
- aware-UTC timestamp parsing/canonicalization;
- `target_ref`, `attempt_count`, entry-count, omitted-count, message, and
  32-KiB canonical JSON bounds;
- recursive secret/prohibited-content rejection; and
- accepted, rejected, and absent durable projections.

`ExtensionJobRecordRequest.extension_diagnostics` is intentionally typed as a
raw optional value at the Pydantic boundary. Strict nested Pydantic rejection
would return 422 before the valid terminal result can be persisted, violating
LD 5. The handler distinguishes omission through `model_fields_set`; explicit
`null`, malformed objects, unknown fields, bad entries, secrets, or overflow
all become the fixed rejected projection.

Canonical documents are exact:

```text
legacy omission:
  {client_event_id, started_at, finished_at, result}

valid present envelope:
  {client_event_id, started_at, finished_at, result,
   extension_diagnostics: {status: recorded, schema_version: 1,
                           entries: [...], omitted_count}}

invalid present envelope:
  {client_event_id, started_at, finished_at, result,
   extension_diagnostics: {status: rejected,
                           error_code: invalid_extension_diagnostics}}
```

The store receives only the admitted projection. New legacy-shaped rows store
`{status: "absent"}` in payload, but that marker is not added to legacy hash
identity. A duplicate of an old stored event therefore resolves to the old row.

`JobRunsLocalStore.completed_extension_runs_by_name()` uses a bounded SQL
query over exact allowlisted names, `trigger_source='extension'`, terminal
rows only, newest first, hard maximum 20. It is read-only and creates no
schema/file.

### 1.2 Native-host persistence classification

Active SA save handlers share one closed helper:

```text
status: "error"
error_code: "database_busy" |
            "database_integrity_failed" |
            "database_write_failed"
retryable: boolean
message: optional fixed sanitized sentence
```

The active set is exactly:

```text
save_market_news
save_market_news_detail
save_articles_meta
save_article_content
save_comments_only
```

SQLite busy/locked maps to `database_busy`; integrity/constraint/corruption
families map to `database_integrity_failed`; false returns and all other local
save exceptions map to `database_write_failed`. Logs may retain local operator
detail under the existing logger policy, but the response never interpolates
`str(exception)`. Success responses contain no failure envelope.

The native telemetry bridge allows exactly the sibling
`extension_diagnostics` field and forwards no caller status/hash. A sidecar
response continues to be reduced to `{status, persisted, run_id, error_code}`.

### 1.3 Extension collector and outbox

Create `extension_diagnostics.js` before `background.js`. It owns a per-job
collector with:

- exact closed stage/reason/target vocabularies;
- at most 32 frozen entries and `omitted_count <= 10000`;
- fixed safe messages only, never raw `Error.message`, URL, title, body,
  comments, HTML, cookie, token, email, filesystem path, SQL, or stack;
- one timestamp read when an entry is accepted; and
- an explicit empty recorded envelope for a successful run.

`enqueueSaSyncJob()` creates one collector after `started_at`, passes it to the
job function, and submits its frozen envelope before `finished_at` leaves the
run. All Alpha Picks, manual-fetch, and Market News failure paths append one
entry at the owning layer before increasing failed counts or producing the
terminal protocol result.

The implementation removes raw `failed++`/`failed += 1` sites from those
flows in favor of one helper that records the typed entry and returns the
single increment. A static/runtime fixture proves there is no count-only
failure branch. Top-level failures that do not increment a detail count also
append one phase diagnostic.

Native response mapping is source-preserving:

- missing/unreachable host -> `native_transport/native_host_unavailable`;
- malformed host reply -> `native_transport/native_response_invalid`;
- admitted database code -> `local_persistence/<same code>`;
- browser navigation/readiness/injection/parser branches keep their browser
  stage and reviewed existing reason; and
- unknown extension exceptions -> `extension_runtime/unknown_failure`.

`extension_telemetry.js` freezes diagnostics into the immutable outbox record.
Legacy queued records without the field remain deliverable. `event_conflict`
removes the matching item and records bounded unavailable delivery; only
transient sidecar failure remains pending.

### 1.4 Health projection

`collect_sa_extension_health()` returns:

```text
chain_state: "available" | "degraded" | "interrupted"
generated_at: aware UTC ISO string
segments: [...]
```

`ok` is removed. The latest capture segment adds only allowlisted fields:

```text
job_name: "sa_alpha_picks_refresh" | "sa_market_news_refresh"
diagnostics_status: "recorded" | "rejected" | "absent"
diagnostics_error_code: "invalid_extension_diagnostics" | null
diagnostics: admitted entries only
diagnostic_recurrence:
  [{job_name, stage, reason_code, affected_run_count, latest_occurred_at}]
```

The latest run uses exact `derived_outcome`; `degraded` never depends on the
presence of a positive count. Diagnostics are sorted by `occurred_at` with
input order as the tie-breaker. Recurrence scans exactly the bounded read from
Section 1.1, groups by `(job_name, stage, reason_code)`, counts affected runs
not entries, and sorts newest occurrence then closed tuple. Rejected and absent
rows do not invent a cause.

The current screenshot's complete run must stay `chain_state=available`. A
degraded capture with six healthy structural rows is also chain available and
shows a warning capture row. Historical repair remains a separate timestamped
row.

### 1.5 Frontend DTO and presentation

`api.ts` uses closed DTOs for chain state, diagnostic status, stages, target
kinds, reason codes, entries, and recurrence. It removes `ok`; `unknown` values
cannot be widened to free strings at the presentation boundary.

`displaySAExtensionSegments()` owns pure display projection:

- workload and occurrence time are always attached to a completed capture;
- complete/skipped/degraded/failed use distinct copy and tone;
- normal mode shows the latest admitted typed cause and safe counts;
- navigation/load timeout explicitly says stored evidence cannot distinguish
  network, provider-page, and browser causes;
- rejected diagnostics say the capture result was retained but its diagnostic
  payload was invalid;
- absent diagnostics on degraded/failed legacy rows say
  `原因未記錄（舊版資料）`;
- repair copy says `最近一次歷史修復`, never current recovery; and
- developer mode exposes only admitted job/stage/reason/target/time/retry/
  attempt/omitted/recurrence fields.

`DataSourcesSection` renders `chain_state` directly. Its existing cache and
manual recheck wiring remain unchanged: initial visible GET plus explicit
recheck GET, no POST and no automatic retry/poll.

### 1.6 Exact i18n ledger

Retire exactly two paths:

```text
dataSources.extension.status.detailFailuresRecorded_one
dataSources.extension.status.detailFailuresRecorded_other
```

Add exactly 44 paths in both locales:

```text
dataSources.extension.degraded
dataSources.extension.workloads.alphaPicks
dataSources.extension.workloads.marketNews
dataSources.extension.status.captureDegraded
dataSources.extension.status.legacyCauseAbsent
dataSources.extension.status.diagnosticsRejected
dataSources.extension.status.additionalDiagnostics
dataSources.extension.status.captureCounts
dataSources.extension.stages.tabNavigation
dataSources.extension.stages.pageReadiness
dataSources.extension.stages.scriptInjection
dataSources.extension.stages.contentParse
dataSources.extension.stages.nativeTransport
dataSources.extension.stages.localPersistence
dataSources.extension.stages.reconciliation
dataSources.extension.stages.extensionRuntime
dataSources.extension.reasons.accessRestricted
dataSources.extension.reasons.loginRequired
dataSources.extension.reasons.modalBlocked
dataSources.extension.reasons.navigationTimeout
dataSources.extension.reasons.detailTimeout
dataSources.extension.reasons.domNotReady
dataSources.extension.reasons.parserEmpty
dataSources.extension.reasons.nativeHostUnavailable
dataSources.extension.reasons.extensionDependencyMissing
dataSources.extension.reasons.reconciliationFailed
dataSources.extension.reasons.commentScanFailed
dataSources.extension.reasons.unknownFailure
dataSources.extension.reasons.tabClosed
dataSources.extension.reasons.browserApiFailed
dataSources.extension.reasons.scriptInjectionFailed
dataSources.extension.reasons.nativeResponseInvalid
dataSources.extension.reasons.databaseBusy
dataSources.extension.reasons.databaseIntegrityFailed
dataSources.extension.reasons.databaseWriteFailed
dataSources.extension.developer.jobName
dataSources.extension.developer.stage
dataSources.extension.developer.reason
dataSources.extension.developer.target
dataSources.extension.developer.occurredAt
dataSources.extension.developer.retryable
dataSources.extension.developer.attemptCount
dataSources.extension.developer.recurrence
dataSources.extension.developer.omittedCount
```

The Settings namespace changes `785 -> 827`; locale total changes
`1869 -> 1911`. Both removed paths join `retiredSettingsPaths`; all 44 additions
join `postSliceSettingsPaths`. Frozen inventory constants
`641 / 23 / 664 / 95 / 3` and adjusted subtree counts remain unchanged.

Copy constraints:

- zh-Hant uses natural `擷取`, `頁面尚未就緒`, `本機資料庫忙碌`, and
  `最近一次歷史修復`; no `攝入`;
- the navigation-timeout sentence preserves uncertainty rather than naming a
  network cause; and
- English/zh-Hant key paths remain exactly parallel.

---

## 2. Exact node accounting

### 2.1 Derivation rule

Every stream is UTF-8 byte-sorted with one trailing newline:

```text
target = sort(unique(base - exact_removed_ids + exact_added_ids))
```

Backend additions use the full pytest node ID
`path/to/test.py::test_name`. In the frontend listings below, `<TAB>` denotes
one literal U+0009 tab between the source path and Vitest full test name; the
hashed stream contains the tab byte, not the five display characters.

Task 0 must prove every addition is absent, every removal exists once, streams
are unique/disjoint, and each staged hash is reconstructed from the collected
base rather than trusted from prose.

### 2.2 Backend additions

Task 1 adds 11 nodes in `tests/test_sa_extension_diagnostics.py`:

```text
test_valid_diagnostics_round_trip_into_payload_and_extended_hash
test_valid_empty_diagnostics_records_explicit_recorded_status
test_invalid_diagnostics_persist_terminal_result_with_fixed_rejection_marker
test_rejected_diagnostics_retry_deduplicates_without_raw_bytes
test_changed_admitted_diagnostics_for_same_event_conflicts
test_legacy_request_preserves_pre_diagnostics_hash_and_deduplicates
test_diagnostic_validator_rejects_unknown_fields_enums_and_time_bounds
test_diagnostic_validator_rejects_identifiers_sizes_and_secret_sentinels_atomically
test_completed_extension_reader_returns_latest_twenty_allowlisted_rows
test_completed_extension_reader_excludes_running_repair_and_unknown_jobs
test_extension_record_route_passes_only_admitted_or_marker_projection_to_store
```

Addition stream SHA-256:
`e257bc36995ed72bfbce39c0886238c04f0de106ea0bd7664f02c45e3b8c99b5`.

Task 2 adds 8 nodes in `tests/test_sa_native_host_diagnostics.py`:

```text
test_sqlite_busy_maps_to_database_busy_without_raw_exception
test_sqlite_integrity_maps_to_database_integrity_failed_without_raw_exception
test_unknown_save_exception_maps_to_database_write_failed_without_raw_exception
test_false_save_result_maps_to_database_write_failed
test_active_save_handlers_share_the_closed_failure_envelope
test_successful_save_response_has_no_failure_diagnostic
test_extension_record_native_bridge_forwards_closed_diagnostics_without_extra_fields
test_native_response_projection_never_contains_path_sql_stack_or_secret_sentinels
```

Addition stream SHA-256:
`a9df387a09c5e60808d854755fc57473e3e751944bc1e7c3263bb1ceafc820ca`.

Task 3 adds 8 nodes in `tests/test_sa_extension_diagnostics_flow.py`:

```text
test_diagnostic_collector_accepts_closed_entries_and_caps_at_thirty_two
test_diagnostic_collector_rejects_secret_or_unbounded_fields_before_transport
test_alpha_detail_failure_branches_record_exactly_one_diagnostic_before_increment
test_market_news_failures_preserve_target_and_stable_reason_without_url_or_body
test_comment_scan_and_unknown_exception_reuse_existing_reason_codes
test_native_failure_envelope_keeps_transport_and_local_persistence_distinct
test_successful_saves_submit_an_explicit_empty_diagnostics_envelope
test_telemetry_outbox_freezes_diagnostics_into_the_immutable_record
```

Addition stream SHA-256:
`50da1c4b1e9f6be9602f7e77436674eb9cd7d911e6a8068a5862e54f843c8a08`.

Task 4 adds 8 nodes in `tests/test_sa_extension_health.py`:

```text
test_each_structural_failure_independently_interrupts_chain
test_structural_warning_degrades_chain_without_interrupting_it
test_capture_and_repair_failures_never_change_chain_state
test_latest_capture_projects_allowlisted_workload_and_diagnostics
test_legacy_failed_capture_reports_cause_absent_without_inference
test_diagnostic_recurrence_is_bounded_to_latest_twenty_allowlisted_completed_runs
test_diagnostic_recurrence_groups_by_job_stage_and_reason_deterministically
test_detail_failures_recorded_has_no_health_producer
```

Addition stream SHA-256:
`e2b18edce3e0808eaec1a81eef10f94343e21766615a9f0085405f4e01dbeb51`.

The complete 35-node backend addition stream SHA-256 is
`7da0e54b8985ebe58873a3b51d98f9515ef8b25329dc356a026799d2bcd8075e`.
There are no backend removals or renames.

### 2.3 Backend staged identities

| Stage | Delta | Full collection | Focused collection |
|---|---:|---|---|
| Base | - | `4359 / c100ee5de4ad42c490e6048e4b7cf22540e417f579987c676796663608d17afd` | `275 / e6ae1a5a38629f558beff0586a98b5e0ea4f28c6a3a516c1302119b874ce3336` |
| Task 1 API/store | `+11` | `4370 / 554dc03c78ff70f362fd24df4a4f562510b47597916d42c56251dcb869b85b83` | `286 / 9c68d4a2fa4cce3c37b1cfa5365a92dd4de2caf835eb74d9e03b3a9413d70a7c` |
| Task 2 native host | `+8` | `4378 / 03bceb26c4691823d21d903fb4fb064df4734d69b2c7c8e6ce0ff55509265b18` | `294 / 4826f566d053acab428e9574ddc64c72acbb57e9a12858cdddffb9a67b27e793` |
| Task 3 extension | `+8` | `4386 / c3969f490e2adc485668916784ce0f48d9d974bf11f312b1c635b1ea110b0fc6` | `302 / 73b47eef08012db1fcef649cc0c8cdaf989f2cd6bdb13d999b70c504e2986269` |
| Task 4 health | `+8` | `4394 / b0285ee3a3d124c4bbe380ad0dea022ef09fa46b52b6a14a0375c5f2459a62fb` | `310 / f9e7c89c0a6bf082e5dc2e29dfe13aef275fe517c8c0622118e58658fef2049e` |

Existing backend node IDs stay fixed. Body evolution is authorized only in:

```text
tests/test_sa_extension_health.py::test_config_failure_does_not_hide_other_segments
tests/test_sa_extension_health.py::test_fresh_install_has_warn_for_missing_history_not_fail
tests/test_sa_extension_health.py::test_health_reports_all_segments_and_latest_extension_slug_row
tests/test_sa_extension_health.py::test_latest_structured_degraded_run_reports_stable_code_and_counts
tests/test_sa_extension_health.py::test_legacy_succeeded_run_is_unverified_not_healthy
tests/test_sa_extension_health.py::test_new_telemetry_segments_never_expose_raw_backend_detail
tests/test_sa_extension_health.py::test_repair_segment_reports_active_and_terminal_structured_state
tests/test_sa_extension_telemetry_outbox.py::test_oversize_storage_failure_or_event_conflict_is_visible_and_never_persisted
tests/test_sa_extension_alpha_picks.py::test_background_loads_required_runtime_dependencies_before_registering_jobs
```

A tenth existing backend node body edit is a stop-and-amend event.

### 2.4 Frontend add/remove ledger

Remove exactly three IDs:

```text
src/saExtensionHealthDisplay.test.ts<TAB>displaySAExtensionSegments > localizes structured detail failure counts in both locales
src/saExtensionHealthDisplay.test.ts<TAB>displaySAExtensionSegments > exposes only bounded stable codes as Developer diagnostics
src/SettingsProviderConfig.test.ts<TAB>Settings provider config authority > shows only the stable SA health code in Developer Mode
```

Removal stream SHA-256:
`f10630ba3d7b0f796fb821310b789c99f5645a62670fd8406acaa2ddaa40fb80`.

Add exactly eight IDs:

```text
src/saExtensionHealthDisplay.test.ts<TAB>displaySAExtensionSegments > localizes degraded capture counts and typed diagnostic causes in both locales
src/saExtensionHealthDisplay.test.ts<TAB>displaySAExtensionSegments > exposes only admitted diagnostic fields and bounded recurrence in Developer Mode
src/saExtensionHealthDisplay.test.ts<TAB>displaySAExtensionSegments > distinguishes browser readiness native transport and local persistence without raw detail
src/saExtensionHealthDisplay.test.ts<TAB>displaySAExtensionSegments > renders legacy diagnostic absence without inventing a cause
src/SettingsProviderConfig.test.ts<TAB>Settings provider config authority > renders only admitted SA diagnostic fields in Developer Mode
src/SettingsProviderConfig.test.ts<TAB>Settings provider config authority > renders all three SA chain states with distinct copy and tone
src/SettingsProviderConfig.test.ts<TAB>Settings provider config authority > renders degraded Alpha Picks history without interrupting a healthy chain
src/SettingsProviderConfig.test.ts<TAB>Settings provider config authority > labels repair as historical and never as current recovery
```

Addition stream SHA-256:
`418a58b6e4f14a2e7c14124c34d0ecdb15b9ca423ee13337f65ec697173a1e38`.

The three renames are semantic: retaining their old names after the producer
and Developer contract changes would create false-test-name debt.

### 2.5 Frontend identities

| Projection | Base | Final after Task 5 |
|---|---|---|
| Full | `101 files / 1172 / d40a30d5e50690f79b644e0b25122da02441eb0cf54ab02793d02269419e23cb` | `101 files / 1177 / 9530dcd91d8a7d684faa5e56f2986fbaeaa22e1d89f67818a12ed5d8ca77d1b1` |
| SA owner, 4 files | `74 / 7ec82dccd499299ec0a1ebd796740bea7186a804920b89deb9ad898a968bbd01` | `79 / 0d6568f19a5d572688bbbb303f32c7cff5f86b19ce51bcc5b730b86beb91753d` |
| Settings regression, 15 files | `246 / c1be07c3d9c7335c4d4172af59cae1234c45c5f6429032f33bbff120280070aa` | `249 / a3a5e481cace86991db6d8ec5da56c2d973d224e1cb1de57f631c210a646a16e` |

The Settings projection contains only the four Provider additions and its one
Provider rename. `saExtensionHealthDisplay.test.ts` and
`i18n/resources.test.ts` are outside that 15-file projection; the 4-file SA
owner projection is the authority for the complete `+8/-3` change.

Existing frontend node body evolution is authorized only for:

```text
SettingsProviderConfig: caches_extension_health_only_after_visible_mount_and_manual_recheck
SettingsProviderConfig: keeps structured SA telemetry raw detail out of normal mode
SettingsProviderConfig: renders a localized degraded SA health row in English
saExtensionHealthDisplay: maps every known segment and fails unknown health prose closed in both locales
saExtensionHealthDisplay: localizes active and retryable repair state with a bounded manifest prefix
settingsBackendCopy: maps every SA Extension segment key
i18n resources: contains the reviewed remaining-surface namespace inventory in both locales
i18n resources: preserves the reviewed pre-Slice-5 Settings-origin inventory across the Common move
```

The three removed IDs are not counted as body edits. A ninth retained frontend
node body edit or a fourth removal is a stop-and-amend event.

### 2.6 Native target

All 35 backend additions are hermetic and unskipped. Final native target is:

```text
4,394 collected = 4,382 passed + 12 skipped + 0 failed
```

Frontend final target is `1,177 passed / 0 failed`. Any different count,
skip split, or stream is a stop event.

---

## 3. RED and mutation discipline

### 3.1 RED admission

- New Python modules may fail by `ModuleNotFoundError` inside the new test
  body; collection itself must still equal the staged identity.
- New JS diagnostics nodes may fail because the new runtime module/file is
  absent or the old output lacks diagnostics.
- Existing-file import/collection errors, syntax failures, changed test IDs,
  or unrelated failures are rejected RED.
- RED and GREEN use the same sorted collection stream for that stage.
- RED tests are not committed separately; product and tests land atomically
  after admitted RED evidence.

### 3.2 Required mutations

Each mutation starts from a clean final product tip, changes one live semantic,
must make its named owner RED, then restores the entire owner file to its exact
pre-mutation SHA. A mutation whose owner stays GREEN is rejected evidence.

| ID | Mutation | Required RED owner |
|---|---|---|
| M1 | Include `telemetry_last` in chain-state reduction | `test_capture_and_repair_failures_never_change_chain_state` |
| M2 | Add an `absent` marker to the legacy hash document | `test_legacy_request_preserves_pre_diagnostics_hash_and_deduplicates` |
| M3 | Reject the whole run when diagnostics are malformed | `test_invalid_diagnostics_persist_terminal_result_with_fixed_rejection_marker` |
| M4 | Return raw `str(exception)` from an active native save | `test_native_response_projection_never_contains_path_sql_stack_or_secret_sentinels` |
| M5 | Restore one count-only `failed++` branch | `test_alpha_detail_failure_branches_record_exactly_one_diagnostic_before_increment` |
| M6 | Keep `event_conflict` pending in the outbox | existing outbox conflict owner |
| M7 | Render a raw diagnostic message in normal mode | `distinguishes browser readiness native transport and local persistence without raw detail` |
| M8 | Describe an old repair as recovery of the latest run | `labels repair as historical and never as current recovery` |
| M9 | Make recheck issue a POST/provider action | existing manual-recheck owner plus browser ledger |

---

## 4. Task sequence

### Task 0 - Re-ground and create evidence

1. Verify exact master, design/plan/map blobs, clean main/planning worktrees,
   and product ancestry from `da7efd9a` through docs-only `9c9021af`.
2. Recollect all baseline streams in Section 0.2 and reconstruct every staged
   identity in Section 2 from the plan's literal rows.
3. Run backend focused `275/275`, frontend owner `74/74`, and Settings
   regression `246/246` once; record exact commands/transcripts.
4. Record the dated normal screenshot metadata and SHA without copying the
   image or any home-directory path into a runtime artifact.
5. Build existing-owner and protected manifests from exact Git blobs.
6. Create
   `docs/superpowers/evidence/2026-08-14-sa-health-diagnostics.md`, update
   statuses/map, commit docs only, and stop for Task 0 review unless the user
   later grants a bounded batch ruling.

### Task 1 - API validation, hash migration, and durable projection

1. Add the 11 tests from Section 2.2 and collect exact Task 1 identity.
2. Record admitted RED for absent validator/query behavior.
3. Implement `src/sa/extension_diagnostics.py`.
4. Add raw optional request field plus omission detection and three canonical
   hash paths to `jobs.py`.
5. Extend `record_extension_event_once()` to store only accepted/rejected/
   absent projection, preserving default compatibility for existing callers.
6. Add the bounded allowlisted completed-run reader.
7. Run new 11, existing `test_job_runs.py`, focused `286`, and full
   collect-only `4370`; verify protected bytes.
8. Commit product/tests, then evidence/docs; stop for review.

### Task 2 - Native-host stable failure envelope

1. Add the 8 native tests and capture exact Task 2 RED.
2. Implement one private classifier/response helper and apply it to exactly
   the five active save handlers.
3. Allow the diagnostics sibling through `_handle_record_extension_job`
   without allowing status/hash/extra fields.
4. Prove success envelopes unchanged where callers consume them and all
   failure responses omit raw sentinels.
5. Run new 8, native-host/reconciliation/tool owners, focused `294`, and full
   collect-only `4378`; verify protected bytes.
6. Commit product/tests, then evidence/docs; stop for review.

### Task 3 - Extension collection and terminal outbox conflict

1. Add the 8 flow nodes and evolve only the two existing IDs authorized in
   Section 2.3. Record exact Task 3 RED.
2. Add `extension_diagnostics.js` and the literal Firefox/Chrome loading path.
3. Thread one collector through `enqueueSaSyncJob`, Alpha Picks, manual fetch,
   and Market News; replace all count-only failure sites.
4. Freeze the sibling envelope into telemetry records and terminally drain
   `event_conflict`.
5. Run JS fixture owners, protocol/packaging/reconciliation regressions,
   focused `302`, and full collect-only `4386`; prove zero URL/body/token
   sentinels in request artifacts.
6. Commit product/tests, then evidence/docs; stop for review.

### Task 4 - Chain state and bounded recurrence

1. Add the 8 health nodes and capture behavior-level RED at exact Task 4
   identity.
2. Replace `ok` with structural-only `chain_state`.
3. Project exact outcome, workload, admitted diagnostic status/entries, and
   bounded recurrence. Retire `detail_failures_recorded` producer.
4. Run health owners, all backend focused `310`, full collect-only `4394`, and
   protected/census gates.
5. Commit product/tests, then evidence/docs; stop for review.

### Task 5 - Closed frontend DTO, truthful copy, and local-only recheck

1. Apply exact `+8/-3` test-ID ledger and capture frontend RED at
   `1177/9530dcd9...` collection.
2. Replace `ok` DTO/rendering with closed chain state and diagnostic DTOs.
3. Implement pure normal/developer projections and historical repair copy.
4. Apply the exact 44-add/2-retire i18n ledger and the two authorized resource
   inventory node changes.
5. Prove manual recheck remains one local health GET and zero POST/provider
   calls; preserve retained cache truth on read failure.
6. Run frontend owner `79/79`, Settings `249/249`, full `1177/1177`,
   typecheck, build, and i18n scanner.
7. Run the early browser matrix in Section 5. Any overlap, raw detail, wrong
   chain tone, or non-GET traffic is a stop.
8. Commit product/tests, then evidence/docs; stop for review.

### Task 6 - Mutations and final admission

1. Execute M1-M9 independently with RED transcript, exact diff, pre/post owner
   SHA, and byte-exact restoration.
2. Recollect all final streams; run backend focused `310`, frontend owner `79`,
   Settings `249`, and complete native/full targets.
3. Run typecheck/build/scanner, extension dependency closure, secret census,
   protected aggregate, no-unowned-path, and production-asset equality gates.
4. Replay the browser matrix with final bytes and inspect both screenshots at
   original resolution.
5. Manifest every generated file/process/profile/port and remove only exact
   new artifacts.
6. Complete the review packet and stop for full independent implementation
   review. Merge, push, extension installation, and live provider work remain
   unauthorized.

### Task 7 - Fast-forward merge and closeout

Only after Task 6 independent GREEN:

1. prove base-to-tip linear ancestry and clean main/implementation trees;
2. fast-forward merge only; do not push;
3. create a fresh exact-master worktree and rerun final collections, focused
   suites, native/full, static gates, protected bytes, and browser matrix with
   new artifact names;
4. write a docs-only closeout and stop for focused closeout review; and
5. remove the implementation worktree/merged branch only after that review.

---

## 5. Browser contract

Use a hermetic fixture server and Chrome at `1322 x 777` and `390 x 844`.
Unknown requests fail the harness. Record method/path/status only; no live
sidecar, extension, SA page, or provider is contacted.

Required scenarios:

1. healthy chain + complete capture reproduces the 2026-08-14 green semantics;
2. healthy chain + degraded Alpha Picks shows available header, warning row,
   workload, timestamp, counts, and typed cause;
3. structural warning shows degraded header; structural failure shows
   interrupted header;
4. old repair is visibly historical and cannot read as current recovery;
5. normal mode distinguishes browser readiness, native transport, and local
   persistence without raw code/message;
6. developer mode shows only admitted bounded fields and recurrence;
7. legacy absence and rejected diagnostics have distinct honest copy;
8. initial mount and recheck are GET-only; the click adds exactly one health
   GET, with zero POST on mount/focus/visibility/idle/click;
9. no clipping, overlap, horizontal page overflow, or schedule-table
   regression occurs; and
10. no `攝入`, raw sentinel, URL, email, token, path, SQL, or stack text appears
    in DOM, console, network ledger, or screenshot.

---

## 6. Evidence and commit discipline

Each Task 1-5 produces two commits:

```text
<product and tests>
docs: record SA diagnostics task N evidence
```

Do not squash. RED is retained as artifact, not a standalone commit. Every
packet contains:

- exact base/tip/owner/protected hashes;
- raw collected-node streams and runtime reporter JSON/transcripts;
- RED and GREEN transcripts;
- diff and changed-path inventory;
- sentinel/network/process/production-boundary receipts applicable to the
  task; and
- `SHA256SUMS` covering every payload plus its own separately reported hash.

Rejected operator runs remain labelled rejected and cannot satisfy a later
gate. An environment flake requires first-transcript retention, isolated owner
control, and a clean complete rerun or an explicitly reviewed partition; it
never licenses assertion weakening.

---

## 7. Stop conditions

Stop and write a bounded amendment if any condition occurs:

1. master/base/owner blob or any staged collection identity differs;
2. a planned addition already exists, a removal is absent, or node streams are
   non-unique;
3. an unowned product/test path changes;
4. any protected path or aggregate changes;
5. top-level `ok` survives in SA health DTO or consumer;
6. `detail_failures_recorded` survives outside dated docs/evidence;
7. diagnostics alter terminal outcome, counts, retry policy, or provider work;
8. malformed diagnostics prevent a valid terminal result from persisting;
9. a legacy omission changes the pre-amendment hash identity;
10. rejected raw diagnostics, URL/body/comment/title/token/email/path/SQL/stack
    text reach durable state, API DTO, browser ledger, or DOM;
11. a native save returns raw exception text or an unreviewed error code;
12. any failed detail count lacks exactly one preceding typed diagnostic;
13. `event_conflict` remains queued/retried or is described as persisted;
14. health reads more than 20 completed allowlisted rows or creates/mutates a
    database during read;
15. telemetry or repair state changes chain state;
16. UI guesses a network/provider/browser root cause not present in admitted
    evidence;
17. recheck, mount, focus, visibility, or idle sends a POST/provider request;
18. schedule components, cadence, source IDs, Macro CSS/layout, capture
    algorithms, retry windows, or canonical run protocol change;
19. i18n differs from exact 44-add/2-retire ledger, frozen inventory constants
    move, locales diverge, or `攝入` is introduced;
20. backend adds/removes other than `+35/-0` or frontend other than `+8/-3`;
21. more existing node bodies evolve than the exact Section 2 lists;
22. native target differs from `4382P/12S/0F` or frontend from `1177/1177`;
23. any live SA/provider request, extension install/reload, production write,
    schedule/repair action, push, or destructive operation occurs; or
24. generated artifacts/processes/profiles/ports cannot be exactly accounted
    for and cleaned.

---

## 8. Handoff

The next permitted action is independent plan review. After GREEN, Task 0 may
begin. No product/test edit is authorized before that ruling.

After this line closes, the approved sequence remains: PG consumer inventory,
PG no-tail retirement, then runtime-owner/CSS-boundary work including EIR-001.
This plan neither reopens Macro nor absorbs PG cleanup.
