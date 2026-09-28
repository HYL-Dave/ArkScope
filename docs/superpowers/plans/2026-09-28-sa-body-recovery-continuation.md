# SA Body Recovery Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair selected SA article bodies after one start, with durable progress, correct current-membership precedence and no loss of financial first-fill work during upgrade.

**Architecture:** Keep browser navigation in the existing shared acquisition queue. A small native journal in `sa_company_refresh.db` owns body-job intent, targets and outcomes; a shared local membership decision supplies body and discussion eligibility. App Settings owns scope and count limits, while capture, retention and permanent exclusion remain separate decisions.

**Tech Stack:** Python 3.10, SQLite, Pydantic, FastAPI, WebExtension JavaScript, React/TypeScript, pytest, Vitest, Playwright/Selenium browser fixtures.

**Spec:** [Approved design](../specs/2026-09-28-sa-body-recovery-continuation-design.md).

**Status:** Approved September 28; inline implementation in `feat/sa-body-continuation-20260928`, then one independent whole-branch review and complete regression. Formal acquisition remains unchanged until the cutover gates.

**Progress:** Task 1 implemented and focused regression passed (192 tests). Tasks 2-7 and all formal cutover gates remain open. RCL/VISN historical Current rows are stale and their accepted tracking is former-only; they are negative cases, not additional valid mixed-current examples.

## Global Constraints

- `max_articles_per_job=0`, `body_lookback_days=0`, `body_scope=all_retained`, `comment_scope=current` are the defaults.
- Count/day values are strict integers in `[0, 2**53)`; zero disables that selection limit, not shared acquisition controls.
- Current wins over historical Closed within/across cohorts; `portfolio_status='closed'` with `current_tracking=1` is not former-only.
- Closed/Former bodies and existing comments stay retained. Permanent exclusions survive; no content is deleted in this implementation batch.
- No automatic restoration of explicit removals, terminal exclusions or ownership; no ticker-prefix matching or invented article roles/dates.
- Existing pacing, navigation budgets, provider consent, financial target selection and news/Alpha schedule frequency are unchanged.
- Preview, Settings reads and public job status are local-only and do not install stores, navigate, spawn a provider CLI or make paid requests.
- Rate-limit deadlines permit later admission; login/challenge/access pauses require explicit operator handling. Unknown navigation needs existing recovery.
- Firefox temporary-addon reload is a prerequisite after browser restart, not something a native journal can automate.
- SEC/lifecycle removal, LLM classification, destructive content cleanup, evidence removal and local disk cleanup are separate batches.

## Review Focus

1. Same security with old Closed and newer Current, or a partially closed position: comments remain eligible without changing historical links. Task 1 owns the matrix; Task 4 proves every caller uses it.
2. Save succeeds before worker/journal checkpoint, or cancellation races admission: no duplicate repaired-body navigation or resurrected job. Tasks 2 and 3 own crash/race tests.
3. Upgrade/reload silently normalizes financial config or clears pending scopes: exact identity/intent comparisons and an executed continuation must fail the cutover gate. Task 6 owns the negative controls.
4. Huge valid lookbacks, missing dates, multibyte titles and stale pagination: no overflow, invented date, oversized native response or changed target set. Tasks 1 and 2 own these inputs.
5. Scope/ownership/exclusion changes while a job waits, including unreadable profile state: recheck before acquisition and never interpret unavailable authority as an empty exclusion list. Tasks 1, 3 and 4 own the guards.

## File Ownership

| Unit | Files and responsibility |
| --- | --- |
| Settings policy | New `src/sa/article_acquisition_settings.py`; strict profile settings and public validation view. |
| Eligibility | New `src/sa/article_acquisition_scope.py`; read-only coherent membership/identity context and article decisions. Modify `src/sa/article_body_recovery.py` for configured selection. |
| Native job | New `src/sa/article_body_recovery_jobs.py`; owned SQLite journal and bounded results. Modify `src/sa/company_collector.py`, `src/sa_native_host.py`, `src/sa/extension_run_protocol.py` only at body-job/receipt boundaries. |
| Browser worker | New `extensions/sa_alpha_picks/article_body_recovery.js`; durable wake/cancel/reconcile orchestration. Integrate through existing `background.js`, `acquisition_client.js`, Firefox manifest and dependency-graph packaging. |
| Discussion admission | `src/tools/data_access.py`, `src/sa_native_host.py`, `extensions/sa_alpha_picks/background.js`; all comment selectors and traversal guards use the same decision. |
| Operator surfaces | New `apps/arkscope-web/src/settings/SAArticleAcquisitionSection.tsx`; API methods/routes, Settings integration, locale files, popup and both collection guides. |
| Verification | Focused tests below; new browser/cutover harnesses live under `tests/`, never under an evidence directory. |

Do not move unrelated code out of large modules. Extract only the existing body-recovery block into its focused browser module, keeping page capture and tab cleanup in their established owners.

## Execution Prerequisites

- [ ] **After written-plan approval, prepare execution isolation:** use `superpowers:using-git-worktrees`, branch `feat/sa-body-continuation-20260928`, private data/native registrations/browser profiles. Keep the formal master/native host and user-owned untracked files untouched. Before feature edits, reproduce a private baseline and inspect any unrelated worktree changes.
- [ ] **Use the project environment for all commands:** `/home/hyl/.virtualenvs/llm_app/bin/python` is the `python` used below. Run tests only against private fixture stores; installed-browser gates use the offline runner in Task 7.

## Task 1: Scope Settings And Current-First Eligibility

**Files:** Create the settings/scope modules above, `tests/test_sa_article_acquisition_settings.py`, `tests/test_sa_article_acquisition_scope.py`. Modify `src/sa/article_body_recovery.py` and `tests/test_sa_article_body_recovery.py`. Read/reuse `src/data_source_routing.py`, `src/sa_tracking_memberships.py`, `src/active_universe.py`; do not rewrite their historical records.

**Interfaces:**
- `ArticleAcquisitionSettings`: fields/defaults from Global Constraints; `parse_article_settings(raw: str | None) -> ArticleAcquisitionSettings`, `load_article_settings(dal=None) -> ArticleAcquisitionSettings`, `article_settings_view(raw: str | None) -> dict`.
- Setting key: `data_sources.sa_article_acquisition.settings`; reuse `read_setting` rather than a schema-installing store constructor.
- `read_article_scope_context(*, sa_db: str | Path, profile_db: str | Path) -> dict`: `status`, `context_id`, `articles`, `cohorts`, `securities`, `exclusions`; typed unavailable on missing/inconsistent authority. No public response exposes credentials or reservation tokens.
- `decide_article_acquisition(article_id: str, *, operation: Literal['body', 'comments'], settings: ArticleAcquisitionSettings, context: dict) -> dict`: `allowed`, `reason_code`, `effective_membership`, `context_id`.
- Extend `build_recovery_manifest(db_path, *, as_of=None, settings=None, scope_context=None) -> dict`; omitted dependencies resolve through the read-only owners. Tests supply private settings/context explicitly. Include effective policy/context identity in `manifest_id`.

- [ ] **Write failing policy tests** for exact defaults, `True`, fractions, negative/unsafe integers, unknown fields/enums and malformed persisted JSON. Preserve the distinction between missing settings (defaults) and unreadable/invalid settings (blocked).

```python
def test_default_article_settings():
    assert parse_article_settings(None).model_dump() == {
        'max_articles_per_job': 0, 'body_scope': 'all_retained',
        'body_lookback_days': 0, 'comment_scope': 'current',
    }
```

- [ ] **Write failing membership/selection tests.** Private fixtures cover one cohort with Current+Closed, old closed/new current entry dates, `closed/current_tracking=1`, newer current followed by delayed closed, ordinary former-only, same ticker reused by a different issuer, explicit removal, ARCH/LTHM/TA terminal exclusions, accepted aliases, shared articles and unreadable authority. For every current case assert comment eligibility and unchanged old link/entry dates; former-only defaults to comments denied/body allowed. A current security's article is not denied solely because its accepted link references its older closed cohort.
- [ ] **Write age tests** proving old current entries remain selected, older Former bodies become eligible under `all_retained/0`, `current` retains but excludes former-only bodies from repair, and missing dates are allowed only without an age cap unless independently eligible as an entry. A huge valid lookback uses a minimum-date boundary without overflowing `timedelta`. Candidate/date evidence never becomes a confirmed Entry/Exit link.
- [ ] **Run RED:** `python -m pytest -q tests/test_sa_article_acquisition_settings.py tests/test_sa_article_acquisition_scope.py tests/test_sa_article_body_recovery.py`. Confirm failures name the missing contract/new behavior; fix test setup errors before implementation.
- [ ] **Implement the interfaces.** Read existing accepted tracking/current projections, established identity mappings and nonstale SA observations consistently. A valid current identity wins over ordinary former history; explicit removals retain their established restoration rules. Protect source conflicts. An unassigned article can be a body candidate under `all_retained`, not an automatic comment target or deletion candidate. Keep priority 1 for current entries/candidates, then current follow-ups, then other selected retained articles. `max_articles_per_job` limits selection at explicit start, not inventory totals.
- [ ] **Run GREEN and regression:** the RED command plus `tests/test_sa_tracking_memberships.py tests/test_sa_tracking_installation.py tests/test_active_universe.py`. Keep existing age-boundary assertions by passing explicit legacy selection settings where needed; do not delete the tests to change defaults. Commit `feat(sa): centralize article scope and current-first eligibility`.

## Task 2: Native Journal, Pagination And Admission

**Files:** Create `src/sa/article_body_recovery_jobs.py`, `tests/test_sa_body_recovery_jobs.py`. Modify `src/sa/company_collector.py`, `src/sa_native_host.py`, `src/sa/extension_run_protocol.py`, `tests/test_sa_body_recovery_native.py`, `tests/test_sa_acquisition_authority.py`, `tests/test_sa_acquisition_receipts.py`.

**Interfaces:**
- `BodyRecoveryJobs(control_db: str | Path, *, sa_db: str | Path, profile_db: str | Path, clock=time.time)`.
- `handle(message: dict, *, client: dict) -> dict` accepts `start`, `state`, `items`, `next`, `checkpoint`, `cancel`, `resume`. `public_status() -> dict` is a redacted read-only view. Browser mutations require the selected collector identity and generation.
- Native `article_body_recovery_control` carries `protocol_version=2`, `operation`, and operation-specific fields. Existing preview/check/save actions also declare body protocol 2. Advertise support in the local capability reply; do not change unrelated acquisition protocol 2 operations.
- Start fields: `request_id`, `manifest_id`, `expected_generation`. Persist the original manual intent and selected finite manifest before returning `job_id`, `revision`, `state`, `counts` and effective settings. One nonterminal job per selected installation; duplicate matching starts return the same job, conflicting starts fail.
- Job states: `pending`, `running`, `waiting`, `paused`, `cancelling`, `cancelled`, `complete`, `partial`. Item states: `pending`, `running`, `saved`, `skipped`, `failed`; restriction/deadline waits keep their target pending. Counts include selected, saved, skipped, failed and pending.
- Body `begin_task` includes `body_job_id`, `body_job_revision`, `article_id`. Validate/associate these in the collector's existing transaction; store the resulting task identity on the item before navigation. Continuation has `trigger='continuation'`, referencing the persisted manual intent, not a fabricated manual trigger.
- `checkpoint` identifies job/revision/article/task and typed outcome; native verification, retained-body readback and terminal acquisition receipt determine the accepted outcome. Public `items` uses an opaque job/manifest-bound cursor; body-job native replies have a 65,536-byte UTF-8 budget independent of job length. Do not change unrelated financial/news response contracts.

- [ ] **Write failing journal tests** for duplicate requests, conflicting payloads, stale preview, two concurrent starts, wrong owner/generation, cancellation revisions, nonexistent/finalized jobs and crash after snapshot persistence but before response. A job's item IDs remain fixed when captured bodies subsequently disappear from the live preview.
- [ ] **Write failing receipt/paging tests.** Save-before-checkpoint reconciles as saved/already available without new navigation; forged task IDs or a completed unrelated operation cannot authorize a checkpoint. Uncertain reservations block continuation. Unicode/long metadata stays within the byte budget; every selected article appears exactly once across pages, with stale/foreign cursors rejected.

```python
def test_start_retry_does_not_duplicate_job(journal_case):
    first = journal_case.start(request_id='same-start')
    again = journal_case.start(request_id='same-start')
    assert first['job_id'] == again['job_id']
    assert journal_case.job_count() == 1
    assert journal_case.navigation_count() == 0
```

`journal_case` is a private test fixture in `tests/test_sa_body_recovery_jobs.py`; it creates a configured/selected real collector and private capture/profile stores, and exposes the three operations used above. It never opens formal stores.

- [ ] **Run RED:** `python -m pytest -q tests/test_sa_body_recovery_jobs.py tests/test_sa_body_recovery_native.py tests/test_sa_acquisition_authority.py tests/test_sa_acquisition_receipts.py`.
- [ ] **Implement the journal and bridge.** Explicit start installs exact owned `sa_body_recovery_installation`, `sa_body_recovery_jobs`, `sa_body_recovery_items` tables transactionally in an already validated collector database. Use an owned schema version; leave the collector's `PRAGMA user_version=2`, base state shape, ownership and counters unchanged. Reject partial/unknown owned schema. Reads never install tables. Start cancellation and item admission serialize on this database; setting a body-job flag must not bypass normal capacity/restriction/navigation admission.
- [ ] **Preserve save integrity.** Keep exact article URL/identity and expected-digest checks. Before accepting a save/checkpoint recheck exclusions; an in-flight valid save can finish after cancellation but cannot schedule another item. Known terminal item failures continue to other work only after confirmed cleanup. Old five-item state remains history; never convert it automatically into a v2 job. Reject old/new protocol mismatch before body navigation.
- [ ] **Run GREEN:** RED command plus `tests/test_sa_company_collector.py tests/test_sa_acquisition_controls.py tests/test_sa_acquisition_status.py`. Commit `feat(sa): persist bounded-transport body recovery jobs`.

## Task 3: Durable One-Article Browser Continuation

**Files:** Create `extensions/sa_alpha_picks/article_body_recovery.js`. Modify `background.js`, `acquisition_client.js`, `manifest.firefox.json`, `tests/js/run_sa_body_repair_fixture.mjs`, `tests/test_sa_body_repair_extension.py`, `tests/test_sa_body_repair_browser.py`, `tests/test_sa_extension_packaging.py`.

**Interfaces:**
- `SAArticleBodyRecovery.create(deps)` returns async `preview()`, `start(manifestId)`, `status()`, `wake()`, `cancel(jobId)`, `resume(jobId)` and `syncAlarm()`. Inject native messaging, storage, alarms, shared queue, clock and one-page capture function using the existing module style.
- Storage `saArticleBodyRecoveryV2` contains only schema version, job/owner reference, next wake and local cancellation intent. `saArticleBodyRecovery` remains legacy history. Alarm: `saArticleBodyRecoveryContinuation`.
- Popup actions remain preview/start/state/cancel, with new `resume_article_body_recovery`. Their worker results use Task 2's status shape. The collector descriptor forwards job/revision/article to native admission.
- Keep `captureArticleBodyRecovery(target, run, diagnostics)` in `background.js`, adapting `run` to the new worker's cancellation/progress callbacks and using the queue's active acquisition task. The page-capture function must no longer depend on the legacy batch array or persist legacy batch state. Each item record carries the native `task_id`; existing extension job receipts add `body_recovery_job_id` for readback, without duplicating article prose.

- [ ] **Write failing deterministic worker scenarios:** a single start completes eight items; simulated elapsed time exceeds 30 minutes; process restarts between items and after save; duplicate wakeups; cancel during native read/admission/save; native disconnect; delayed checkpoint; owner change; old/corrupt storage. Assert no second navigation for an already repaired article and no resurrection after a persisted cancellation.
- [ ] **Write scheduling/restriction assertions:** at most one admitted article per worker turn, native pacing respected, queued financial and routine jobs progress between body items, cooldown retains its target then resumes after the exact deadline, login/challenge/access never auto-clears, a parse failure yields partial completion and does not erase remaining items. No alarm starts a job without prior manual intent.

```javascript
assert.equal(result.startRequests, 1);
assert.equal(result.uniqueSavedArticles, 8);
assert.equal(result.batchTimeouts, 0);
assert.equal(result.navigationsAfterCancel, 0);
```

Return these counters from named scenarios in the existing JS fixture, derived from actual worker/native calls rather than assigning expected values.

- [ ] **Run RED:** `python -m pytest -q tests/test_sa_body_repair_extension.py tests/test_sa_extension_packaging.py tests/test_sa_acquisition_queue.py`.
- [ ] **Implement the module and wiring.** Remove the five-item/whole-job 30-minute runtime caps, retaining page-operation deadlines. Reconcile pending native work before each wake. Hold the native lifetime port only during one active page, never during cooldown. Queue each item in the existing background lane; persist waits and resume via alarms/startup. If native cancellation cannot be acknowledged, persist local cancel intent first and send it before any future admission. Fail closed when the pending task is unknown.
- [ ] **Wire real packaging and protocol checks.** Load the module before `background.js` in Firefox and before event listeners in Chrome's import graph. Exercise the packaged worker in isolated Firefox and Chromium with popup closed and repeated suspend/reload; no SA network traffic. Unsupported temporary-addon reload/identity loss must show the required recovery action, not claim automatic continuation.
- [ ] **Run GREEN:** RED command plus the browser gate `ARKSCOPE_BROWSER_ACCEPTANCE=1 python -m pytest -q tests/test_sa_body_repair_browser.py tests/test_sa_acquisition_browser.py`, in the private offline runner described below. Commit `feat(sa): resume body recovery one admitted article at a time`.

## Task 4: Apply The Same Scope To All Discussion Paths

**Files:** Modify `src/tools/data_access.py`, `src/sa_native_host.py`, `extensions/sa_alpha_picks/background.js`, `src/sa/extension_run_protocol.py`. Create `tests/test_sa_comment_acquisition_scope.py`; extend `tests/test_sa_comment_refresh_extension.py`, `tests/test_sa_comment_backfill_backend.py` and `tests/test_sa_partial_comments.py` rather than replacing existing comment recovery assertions.

**Interfaces:**
- Native `get_article_acquisition_eligibility` accepts exact article ID and `operation='comments'`, returning Task 1's decision using fresh local context/settings.
- `save_sa_articles_meta` preserves its response fields, but filters `need_comments`, combined `need_content` comment traversal and reconciliation/enrichment work using the same decision. Include typed scope-skip counts, distinct from genuinely pending eligible comments.
- The browser checks eligibility immediately before comment traversal, including first detail capture, enrichment and per-item retries. A valid body can still be stored when comments are out of scope; body acquisition and comments must not be one inseparable permission.

- [ ] **Write failing parameterized tests** for Quick, Full, Deep/backfill, scanned-list count changes, historic pending recovery, TTL refresh, enrichment and first-detail capture. In each, current/re-entered/partial-position cases remain eligible; former-only and permanently excluded discussions are not navigated or retried by default. Old associations and comments remain byte-for-byte unchanged by the decision.
- [ ] **Write race tests** where a current target becomes former before traversal, an old closed target becomes current while waiting, and `comment_scope` narrows. Re-read before traversal; scope skips must not become a failed Alpha run or keep a meaningless pending backlog. A context-read error is deferred/unavailable, not an empty successful queue. Fresh list metadata cannot requeue deliberately purged content.

```python
@pytest.mark.parametrize('mode', ['quick', 'full', 'backfill'])
def test_reentered_target_is_not_removed_by_closed_history(scope_capture, mode):
    reply = scope_capture.select_comments(mode=mode, state='reentered')
    assert scope_capture.current_article_id in reply['eligible_ids']
    assert reply['historical_links_changed'] is False
```

Define `scope_capture` locally using private DAL/store fixtures and actual `save_sa_articles_meta`; `eligible_ids` is the union of returned work groups, not a separate selection implementation.

- [ ] **Run RED:** `python -m pytest -q tests/test_sa_comment_acquisition_scope.py tests/test_sa_body_recovery_native.py tests/test_sa_body_repair_extension.py`.
- [ ] **Implement shared filtering and traversal guards**, using Task 1's decision without a second ticker/closed predicate. Preserve list metadata discovery needed to recognize future re-entry. Do not turn excluded comments into capture failures; do not hide failures on eligible items.
- [ ] **Run GREEN and comment/Alpha regression:** `python -m pytest -q tests/test_sa_comment_acquisition_scope.py tests/test_sa_body_recovery_native.py tests/test_sa_body_repair_extension.py tests/test_sa_comment_refresh_extension.py tests/test_sa_comment_backfill_backend.py tests/test_sa_partial_comments.py tests/test_sa_comment_capture.py tests/test_sa_comment_recency.py tests/test_sa_comment_acceptance.py tests/test_sa_quick_workload.py tests/test_sa_alpha_refresh_receipts.py tests/test_sa_extension_reconciliation_flow.py`. Commit `fix(sa): stop former-only comments without suppressing current re-entry`.

## Task 5: Settings, Progress And Operator Documentation

**Files:** Create `apps/arkscope-web/src/settings/SAArticleAcquisitionSection.tsx`, `apps/arkscope-web/src/settings/SAArticleAcquisitionSection.test.tsx`, `tests/test_sa_article_acquisition_routes.py`, `tests/test_sa_article_settings_browser.py`. Modify `src/api/routes/seeking_alpha.py`, `apps/arkscope-web/src/api.ts`, `apps/arkscope-web/src/settings/DataSourcesSection.tsx`, `apps/arkscope-web/src/settings/settings.css`, `apps/arkscope-web/src/i18n/resources/en/settings.ts`, `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`, `extensions/sa_alpha_picks/popup.html`, `extensions/sa_alpha_picks/popup.js`, `tests/test_sa_body_repair_popup_layout.py`, `SA_COLLECTION_GUIDE.md`, `SA_COLLECTION_GUIDE.zh-Hant.md`, `extensions/sa_alpha_picks/FIREFOX.md`.

**Interfaces:**
- `GET/PUT /sa/article-acquisition-settings`: Task 1's view/model; writes use `require_profile_state_write` and the existing profile settings store. A save does not start collection or alter the financial config.
- `GET /sa/body-recovery-status`: Task 2's public summary, with no store creation, client ID/token disclosure or native-host spawn.
- API methods: `getSAArticleAcquisitionSettings()`, `putSAArticleAcquisitionSettings(values)`, `getSABodyRecoveryStatus()`; share typed response shapes with the component's fixtures.

- [ ] **Write failing route/UI tests** for defaults, zero/unlimited, explicit scopes/age, invalid saved policy, save/readback/undo, save errors, blocked reads and no navigation/provider calls. Assert changing body scope does not delete or mutate Former content; changing it does not reset an active body job's frozen selection.
- [ ] **Write failing popup tests** for complete/partial/waiting/paused/cancelling states, offline cancellation pending, legacy history, incompatible host, explicit resume and current progress. Assert no `Start next up to 5` or whole-job timeout promise remains. A new complete job requires actual terminal outcomes, not merely a successful RPC.
- [ ] **Run RED:** `python -m pytest -q tests/test_sa_article_acquisition_routes.py tests/test_sa_body_repair_popup_layout.py`; `npm run test --workspace apps/arkscope-web -- src/settings/SAArticleAcquisitionSection.test.tsx`.
- [ ] **Implement the surfaces.** Use unframed layout within the existing SA Settings section, numeric inputs and scope menus, existing lucide save/undo controls, localized labels and errors. Show selected/saved/skipped/failed/pending, next eligible time and reason; do not present an unreliable completion estimate. Keep the popup's Preview, one Start, Cancel and conditional Resume commands.
- [ ] **Update guides with actual shipped behavior**, including body versus discussion scope, Current-over-Closed precedence, historical retention, manual cancellation versus temporary pause, default values and temporary Firefox reload. Do not claim original Entry/Exit articles have been identified or permanent-content cleanup has shipped.
- [ ] **Run GREEN**, full frontend tests, build and visible-i18n scan. Add browser layout checks in `tests/test_sa_article_settings_browser.py`, with network-intercepted fixtures, English/Traditional Chinese, widths 1440/940/720/390; inspect screenshots and popup widths 320/390 for text fit and operable controls. Commit `feat(sa): expose recovery scope and durable progress`.

## Task 6: Mandatory Financial Queue Preservation Gate

**Files:** Create `tests/test_sa_midfill_upgrade.py`, `tests/test_sa_midfill_upgrade_browser.py`, `tests/sa_cutover_assertions.py`. Reuse `tests/test_sa_company_refresh.py`, `tests/test_sa_company_refresh_pacing.py`, existing real-browser packaging helpers and the Task 2 journal. Amend production files only to repair failures covered by these tests; no new scheduling policy or general migration framework.

**Interfaces:**
- `assert_financial_checkpoint_preserved(before: dict, after: dict) -> None` in the test helper compares the exact fields below, not aggregate counts. Mismatches raise `AssertionError` naming the changed non-secret field.
- Baseline product reference: `b24a2c1d`; read only the needed extension/native files from Git into private fixtures, not a full multi-GB repository clone. Candidate code is the implementation branch. Exercise old-to-new and new-to-old compatibility at an idle boundary.
- Checkpoint includes `companyFinancialRefresh.config`, ordered `pending_scopes`, `pending_requested_at`, `pending_force`, `intent_revision`, success/retry `records`, pause/cooldown fields, selected collector identity/generation/ledger, native pacing/budgets, and routine schedule values/revisions. Pending acquisition must be absent or proven terminal before the idle checkpoint. Omit volatile scheduling timestamps from equality, but assert recalculated wakeups do not occur before native eligibility.

- [ ] **Write failing upgrade tests.** Start a real old-version manual financial queue with scheduling disabled, complete one of four scopes, leaving three distinct pending IDs and its success receipt. Repeat with scheduling enabled and with a paced/retry-delayed item. Reconstruct the candidate worker over the same private persisted state and database; do not call configure/activation/Cancel to make the test pass.

```python
def test_midfill_upgrade_resumes_remaining_scope_without_restarting(upgrade_case):
    before, after = upgrade_case.upgrade_at_idle()
    assert_financial_checkpoint_preserved(before, after)
    receipt = upgrade_case.run_next_financial_scope()
    assert receipt['scope_id'] == before['pending_scopes'][0]
    assert upgrade_case.pending_ids() == before['pending_scopes'][1:]
    assert upgrade_case.repeat_navigation_for_saved_scopes() == 0
```

`upgrade_case` uses the old/candidate worker modules and actual private native collector, not a stub returning a successful receipt. Derive scope IDs and receipts from the worker calls and stored captures.

- [ ] **Write negative controls** that deliberately drop one pending ID, replace an ID without changing the count, reset an intent revision, alter a success timestamp or change collector generation. Each must fail preservation. Replaying old Cancel/configuration-changing activation must be detected as destructive to intent, not accepted as a pause.
- [ ] **Write installed-browser upgrade gates.** In disposable Firefox/Chromium profiles, exercise disabling the selected extension without uninstalling, replacing/reloading the same-ID package, then enabling it with persisted state. Verify the actual temporary Firefox mechanism is supported and retains state. If that pause/reload method is unavailable or loses state, the gate fails and mid-fill formal cutover is prohibited; do not skip it, edit storage to reconstruct success, or silently substitute a different pause method. Keep all fixture traffic loopback/intercepted.
- [ ] **Run RED:** `python -m pytest -q tests/test_sa_midfill_upgrade.py`. Browser tests run with `ARKSCOPE_BROWSER_ACCEPTANCE=1` through the private offline runner.
- [ ] **Implement only proven compatibility fixes** and the harness. Starting a body job after reload must leave financial intent unchanged; interleave both and verify new body task receipts plus financial progress. On rollback, first stop/cancel the v2 body job at a verified cleanup boundary, preserve saved bodies and journal history, and prove old financial/news workers still read their state. Never restore an old whole-capture DB over newer successful data as a default rollback.
- [ ] **Run GREEN:** all mid-fill tests, both browser variants, `tests/test_sa_company_refresh.py`, `tests/test_sa_company_refresh_pacing.py`, `tests/test_sa_acquisition_receipts.py`. Retain a compact result including baseline/candidate hashes, compared field hashes, remaining IDs/counts and actual receipt IDs. Commit `test(sa): gate mid-fill upgrades on financial queue preservation`.

## Task 7: Freeze, Independent Review And Full Regression

**Files:** No additional product surface. Update this plan's checkboxes and the operator guides as needed. Keep logs/screenshots under ignored `data/verification/sa-body-<candidate-sha>/`; retain one concise receipt, not another committed artifact bundle.

- [ ] **Request independent whole-branch review** after Tasks 1-6, explicitly covering re-entry, per-page native authority, exclusion persistence and mid-fill negative controls. Fix actionable findings with regressions. A reviewer's subset is not the full verification gate.
- [ ] **Freeze a candidate commit** and run the complete backend using the existing offline authority:

```bash
ARKSCOPE_VERIFICATION_WORK="$PWD/data/verification/sa-body-$CANDIDATE_SHA" ARKSCOPE_FORMAL_DATA=/mnt/md0/PycharmProjects/ArkScope/data /home/hyl/.virtualenvs/llm_app/bin/python docs/superpowers/evidence/2026-09-27-provider-state/offline_tests.py -q tests --junitxml="$PWD/data/verification/sa-body-$CANDIDATE_SHA/backend.xml"
```

Set `CANDIDATE_SHA` to the frozen commit and create its private output directory first. This runner enables installed browser gates and rejects formal DB/network/provider CLI access. Keep its dependent evidence helpers until the separate cleanup batch. Report actual totals/skips and exit code; do not copy old totals or disable a failing browser gate.

- [ ] **Run complete frontend/desktop verification**, under the existing offline Node guard where applicable:

```bash
NODE_OPTIONS="--require=$PWD/docs/superpowers/evidence/2026-09-15-runtime-acceptance-cleanup/checks/offline_node.cjs" npm run test --workspace apps/arkscope-web
node --test apps/arkscope-desktop/navigation.test.js apps/arkscope-desktop/sidecarConfig.test.js
npm run build --workspace apps/arkscope-web
npm run check:i18n-literals --workspace apps/arkscope-web
```

- [ ] **Inspect browser evidence** for Task 5 layouts and Task 6 actual installed-addon upgrade/continuation. No blank/error-only screenshots count as acceptance. Repeat the complete affected gates after any product or harness fix; retain the final frozen hash with results.
- [ ] **Produce the merge/cutover receipt** listing exact tests, limitations, rollback procedure and the following gates. Do not merge/update the formal extension merely because offline tests pass.

## Formal Cutover Checklist

These are **required gates**, not optional operator guidance. Do not start the pause until the implementation, review and offline gates are complete. The operator must explicitly approve the short interruption.

| Gate | Evidence required to proceed |
| --- | --- |
| G1: Queue preservation | Task 6 old-to-new/reload/rollback tests and all negative controls pass on the frozen candidate, including installed Firefox. Confirm the exact non-destructive pause method; no generic Cancel or configuration reset. |
| G2: Quiescent backup | Operator pauses the selected extension using that verified method, closes acquisition tabs and App. Read back no unknown/active native task; back up affected DBs/identity marker and selected extension queue/settings state privately. Record exact pending IDs, success records, intent, schedules and collector identity hashes. If quiescence cannot be proved, stop before replacement. |
| G3: Post-upgrade equality | Before resuming, compare against the G2 checkpoint using the same field assertions as G1. Owner, policies, schedules, successes and pending identities must match. Any mismatch blocks restoration/verification until repaired under the stopped boundary. |
| G4: Financial continuation | Immediately request restoration, then observe a new successful financial acquisition receipt for a previously pending scope (or verified reuse followed by the next pending acquisition), its stored observation and corresponding pending removal. Already saved scopes must not be restarted. A green badge or aggregate count alone is insufficient. |
| G5: New body receipt | After operator preview/start, observe a v2 journal job, a new terminal body acquisition receipt and stored body outcome linked by job/article/task IDs. Confirm financial/news progress alongside it. This proves a new workflow ran, not that the entire body backlog has finished. |

If G4/G5 waits on a real login/access/rate-limit restriction, report the actual reason and leave live acceptance open; do not declare complete or bypass the restriction. Failure after restoration uses the rehearsed rollback and immediate state readback, preserving new retained data. Never leave collection silently stopped while waiting for a report or review.

## Plan Self-Review

- [x] Spec coverage: Tasks 1/4 cover configurable scope, Current precedence and retention protection; 2/3 cover persistence, pagination, cancellation, restrictions and compatible admission; 5 covers App/popup/docs; 6/7 and G1-G5 cover mandatory upgrade and live proof. Destructive cleanup remains separate.
- [x] Interfaces: settings and decision shapes are defined once, native/browser share job states and protocol fields, and Settings/public readers reuse the same journal summary.
- [x] Review-focus inputs have named owners and concrete assertions; no new live provider call is part of offline verification.
- [x] Execution method retained: inline implementation followed by independent whole-branch review. All implementation/cutover checkboxes remain open until actually performed.
