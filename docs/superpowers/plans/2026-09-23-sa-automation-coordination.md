# SA Automation Coordination Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run existing SA acquisition through one explicitly selected Chrome or Firefox installation, protecting routine work while making whole-watchlist financial updates configurable and understandable.

**Architecture:** Extend the existing local collector authority and database, not a second service. A shared browser queue chooses due routine work before one financial scope; every managed page navigation needs durable native admission. Existing extractors, saved observations and source routing stay authoritative.

**Tech Stack:** Python 3.10+, SQLite transactions, existing Native Messaging host, shared JavaScript, Chrome MV3 and Firefox MV3, pytest/Node VM fixtures and installed-browser tests.

**Spec:** [SA Automation Coordination And Controls](../specs/2026-09-23-sa-automation-coordination-design.md).

Status: Tasks 1-7 implementation and isolated browser/native verification are
complete on the feature branch. Signed-in coordination/Chrome native acceptance
remains open. Task 8 freezes documentation and source, obtains a fresh review,
then runs the complete final regression before any merge. See the
[evidence](../evidence/2026-09-23-sa-automation-coordination/README.md).
Firefox remains the initial preference, not a fixed dependency. No production
schedule, quota, registration or database has been changed.

## Global Constraints

- No automatic browser failover.
- No production schedule is enabled by a code upgrade.
- Retain 60 seconds for existing configurations until explicitly changed; offer 15/30/60-second choices and valid custom positive seconds.
- Do not invent numerical hourly/daily limits from 814 job receipts.
- Priority cannot override the total ceiling.
- Timers are an optimization, not durable state.
- No paid fallback, new provider, account rotation, challenge bypass or new headless collector.
- Keep Chrome and Firefox on the same source modules and popup; retain Firefox manifest minimum `121.0`.
- Production activation is a separate attended operation after all old automated installations are stopped/updated.
- Use isolated databases, fake clocks and fake provider/browser I/O for development. Never initialize a store merely to inspect it.
- Preserve existing source settings, configured routine intervals and extractor behavior. Fix admission/stop defects without silently changing cadence.
- Keep current observation identifiers, retained articles/comments, citations and user watchlist intact. No data purge, automatic fallback, merge or push in implementation tasks.

## Review Focus

| Condition a user can encounter | Expected behavior | Owning tests |
|---|---|---|
| Disable and re-enable a schedule while its old callback is queued | Old intent cannot acquire; a new due request must be admitted | Task 1: queued disable/re-enable |
| Native reply lost after a navigation debit | No duplicate debit or replayed navigation; uncertain work remains recoverable | Tasks 2/3: replay and lost reply |
| News arrives during the financial gap, or routine work consumes the budget | News runs first; financial work waits without monopolizing a reservation | Tasks 4/5: priority during wait, capacity release |
| Owner switches while an old outbox event is undelivered | Historical identity remains valid evidence; old owner cannot acquire again | Tasks 2/3: generation fencing and delayed event |
| First quick scan expands to full, browser sleeps, or watchlist changes | Capacity still bounds acquisition; saved work survives; removed targets do not run | Tasks 4/5/7: expansion, suspension and membership |

## Files And Delivery Boundaries

| Owner | Responsibility |
|---|---|
| `src/sa/company_collector.py` | Extend the existing `CompanyCollector` authority in place to all managed SA operations; its historical class/file name does not create a second authority. Preserve the existing database path and financial readback guards. |
| New `src/sa/acquisition_policy.py` | Pure policy validation and rolling-window admission calculation; no connections or I/O. |
| `src/sa_native_host.py` | New shared control action, native admission validation, existing financial source-policy checks and telemetry forwarding. |
| New `extensions/sa_alpha_picks/acquisition_queue.js` | Routine/background ordering and in-installation coalescing; no SQLite/network authority. |
| New `extensions/sa_alpha_picks/acquisition_client.js` | Task lifecycle, navigation admission and visible restriction reporting around existing browser handlers. |
| `extensions/sa_alpha_picks/background.js` | Wire every existing trigger and navigation through those owners; retain extractor loops. |
| `extensions/sa_alpha_picks/company_refresh.js` | Durable financial intent, eligibility, per-view intervals, pacing deadlines and read-only preview. |
| `extensions/sa_alpha_picks/popup_company_refresh.js`, `popup.html`, `popup.js` | One explicit activation flow, scope/cost preview, shared collector status and advanced controls. |
| Existing JS/Python run protocol, outbox, jobs route/store | Preserve complete/partial/paused evidence and acquisition identity end to end. |
| Existing manifests, Firefox builder, packaging tests | Same runtime dependency closure in both browsers. |

Tasks 1-6 are one integration delivery. Commits remain independently reviewable;
do not deploy intermediate authority/protocol changes to the user's browsers.
Service lifetime, external MCP, retention and other research repairs remain
separate lanes, not prerequisites or secretly included scope.

## Task 1: Honor Routine Schedule Intent At Execution

**Files:**
- Modify: `extensions/sa_alpha_picks/background.js` (alarm callbacks, `enqueueAutoSaSyncJob`, both setters).
- Test: new `tests/test_sa_auto_sync_admission.py` using `tests/test_sa_extension_popup.py::_run_background_probe`.

**Interfaces:** Preserve `enqueueAutoSaSyncJob(jobKey, jobOpts, jobFn) -> Promise`.
Read enabled state and an intent revision at trigger time, recheck both inside
the queued callback. Increment the corresponding revision on an explicit
enable/disable/configuration change. News additionally retains
`shouldRunMarketNewsAutoSync() -> Promise<boolean>`. Do not apply automatic
eligibility checks to explicit manual refresh commands.

- [x] **Write the queued-disable RED test.** Start with the following complete
  behavioral case; repeat for both job keys and for disable-then-reenable.

```python
from tests.test_sa_extension_popup import _run_background_probe

def test_disabling_queued_alpha_picks_prevents_acquisition():
    result = _run_background_probe(r"""
      await companyCollectorIdentity;
      extensionTelemetryController.flush=async()=>({});
      extensionTelemetryController.submit=async()=>({});
      chrome.alarms.clear=async()=>true;
      chrome.alarms.create=async()=>{};
      await chrome.storage.local.set({alphaPicksAutoSyncEnabled:true});
      let release, start;
      const ready=new Promise(resolve=>{start=resolve;});
      enqueueSaSyncJob({},async()=>{
        start(); await new Promise(resolve=>{release=resolve;}); return {};
      });
      await ready;
      let calls=0;
      const pending=enqueueAutoSaSyncJob('alphaPicks',{},async()=>{calls++;return {};});
      await setAlphaPicksAutoSyncEnabled(false,30);
      release();
      await pending;
      return {calls};
    """)
    assert result["calls"] == 0
```

- [x] **Run RED:** `/home/hyl/.virtualenvs/llm_app/bin/python -m pytest tests/test_sa_auto_sync_admission.py -q`. The existing implementation must fail with one call, not with a broken fixture.
- [x] **Implement the guard inside the coalesced callback.** The essential
  condition is executable only when both observations agree:

```javascript
if (!current.enabled || current.revision !== submitted.revision) {
  return {status: "skipped", reason: "operator_cancelled"};
}
```

  Store each snapshot as `{enabled, revision}` from its own existing setting
  keys plus a new integer revision key. Missing revision normalizes to zero;
  a state read failure refuses acquisition. Capture intent before queuing and
  make rapid concurrent triggers coalesce during that read too.
- [x] **Add late-alarm and rapid-toggle tests.** After disable, direct alarm
  delivery must not acquire. Disable/re-enable must invalidate the old callback.
  A manual command remains available; repeated due triggers still coalesce.
- [x] **Run GREEN and commit:** focused admission, popup, company refresh and
  run-protocol tests. Commit `fix(sa): recheck queued automatic acquisition intent`.

## Task 2: One Durable Authority And Navigation Allowance

**Files:**
- Create: `src/sa/acquisition_policy.py`.
- Modify: `src/sa/company_collector.py`, `src/sa_native_host.py`.
- Test: `tests/test_sa_company_collector.py`, new `tests/test_sa_acquisition_policy.py`.

**Interfaces:** Pure `navigation_eligibility(attempts, policy, priority, now) ->
dict`, where attempts are `(timestamp_seconds, "routine"|"background")` pairs,
policy has `hour_limit`, `day_limit`, `hour_reserve`, `day_reserve`, and output is
`{allowed: bool, retry_at: float|None}`. Reject booleans/non-integer counts,
non-finite clocks and reserves outside `[0, limit]`.

`CompanyCollector.handle(message)` remains the transaction facade. The new
native action is `sa_acquisition_control`; supported operations:

| Operation | Required inputs beyond `client` | Result |
|---|---|---|
| `status` | Optional expected ledger identity | Read-only owner/generation, restrictions, capacity and pending status; no reservation secret |
| `configure` | Validated policy, financial gap, `confirm_activation`, expected owner generation | Accepted policy and `ledger_id`; no acquisition |
| `select` | Expected generation, destination schedule summary acknowledgement | Idle-only selection, monotonically incremented generation |
| `begin_task` | Generation, request ID, operation/mode, trigger, intent revision; financial scope/force/check interval when applicable | `task_id`, private token and generation, or typed reused/deferred/denied result |
| `admit_navigation` | Task token, generation, unique navigation ID, action kind, destination class | One-use attempt receipt or typed deferral |
| `observe_restriction` | Task token, recognized reason, optional reliable later retry deadline | Persisted site pause/cooldown before cleanup |
| `finish_task` | Token, result projection, confirmed cleanup | Durable terminal task receipt; existing financial saved-observation verification retained |
| `recover` / `resume` | Explicit stopped/handled confirmation, expected generation | Recovery/resume without quota reset or cooldown bypass |

Operation/mode maps, not caller-supplied priority, select the lane. News,
Alpha Picks, manual article/reconciliation and news-repair operations are routine;
company financial acquisition is background. Financial route selection remains
checked in the native host before `begin_task`. External model tools gain no new
acquisition authority.
Replace the financial-only `company_refresh_control` dispatch and callers in
this integration; old acquisition control is refused, not kept as a bypass.
Retain `get_company_watchlist` as a read-only action. Adapt existing collector
test helpers to the new messages while keeping their assertions about saved
observations, source routing, clock rollback and explicit stopped recovery.

- [x] **Write RED for reserved capacity and exact window boundaries.**

```python
from src.sa.acquisition_policy import navigation_eligibility

def test_financial_work_leaves_unused_routine_reserve():
    policy = dict(hour_limit=4, day_limit=8, hour_reserve=2, day_reserve=2)
    attempts = [(100.0, "background"), (101.0, "background")]
    assert navigation_eligibility(attempts, policy, "background", 102)["allowed"] is False
    assert navigation_eligibility(attempts, policy, "routine", 102)["allowed"] is True
    assert navigation_eligibility(attempts, policy, "background", 3701)["allowed"] is True
```

- [x] **Run RED:** `python -m pytest tests/test_sa_acquisition_policy.py -q` with the project interpreter.
- [x] **Implement one pure window calculation and use it inside `BEGIN IMMEDIATE`.**

```python
used = len(window_attempts)
routine_used = sum(priority == "routine" for _, priority in window_attempts)
unused_reserve = max(0, reserve - routine_used)
ceiling = limit if requested_priority == "routine" else limit - unused_reserve
allowed = used < ceiling
```

  Windows are `(now-window_seconds, now]`. Admission must pass both windows.
  Compute next eligibility by evaluating the sorted expiration instants from
  both windows, not by assuming one oldest row always frees usable capacity.
  No guessed default limits. Store task/attempt rows in the existing authority
  database with unique request/navigation IDs, owner generation and policy
  revision. Switches retain the entire ledger. Never refund an uncertain debit.
- [x] **Extend explicit initialization, not read paths.** Store `managed_since`,
  ledger UUID and `prior_traffic_coverage="unknown"`. Use an adjacent creation
  marker containing the ledger UUID to distinguish a never-initialized database
  from a lost one. Create the marker exclusively before first initialization;
  interrupted initialization or mismatching/missing state fails closed. An
  existing financial-only database requires an explicit idle/stopped upgrade
  with a local backup, preserving pauses, successful scopes and ownership.
  Unknown schema is refused, not rebuilt. No automatic production migration.
- [x] **Add authority tests:** eight independent connections race for one
  reservation; two Chrome installations differ; stale generation fails after
  an explicit Firefox/Chrome switch; 15-second setting cannot bypass cooldown;
  clock regression refuses admission. Duplicate navigation ID returns the same
  debit with `replayed=true`, never a fresh executable permit. Policy changes
  cannot erase attempts; a lowered limit defers existing work. Missing/corrupt
  marker/database/rows after activation must refuse new acquisition.
- [x] **Run GREEN and commit:** policy, collector, native-host routing tests.
  Commit `feat(sa): share acquisition ownership and navigation capacity`.

## Task 3: Honest Deferred Results And Identity-Bound Receipts

**Files:**
- Modify: `extensions/sa_alpha_picks/extension_run_protocol.js`, `extension_telemetry.js`, `background.js`.
- Modify: `src/sa/extension_run_protocol.py`, `src/sa_native_host.py`, `src/api/routes/jobs.py`, `src/service/job_runs_store.py`.
- Modify: `src/service/sa_extension_health.py`, `extensions/sa_alpha_picks/popup_action_catalog.js`, `extensions/sa_alpha_picks/popup.js`, `apps/arkscope-web/src/saExtensionHealthDisplay.ts`, `apps/arkscope-web/src/saExtensionHealthDisplay.test.ts`, `apps/arkscope-web/src/i18n/resources/en/settings.ts`, `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`.
- Test: `tests/test_sa_extension_run_protocol.py`, `tests/test_sa_extension_telemetry_outbox.py`, `tests/test_sa_native_host_telemetry.py`, `tests/test_job_runs.py`.

**Interfaces:** New result schema version 2 retains version-1 validation and
canonicalization unchanged for delayed evidence only. Add phase state `deferred`
and its count; closed reasons: `capacity_exhausted`, `waiting_for_priority_work`,
`collector_unavailable`, `collector_other_installation`, `site_paused`.
Fatal failures retain precedence; otherwise any deferred phase yields
`derived_outcome="deferred"`, `db_status="succeeded"`,
`healthy_anchor_eligible=false`. This uses the existing terminal DB enum without
calling a deferral a healthy acquisition. A failure remains failed/degraded,
not a deferral. Typed whole-run skip remains distinct.

The `acquisition` envelope on new telemetry contains `schema_version=1`,
`ledger_id`, `browser`, `client_id`, `build`, `protocol_version`, `generation`,
`task_id`, `batch_id`, `priority`, `trigger`, navigation-attempt count,
queue-wait/acquisition-duration milliseconds, and `identity_basis`.
Native authority validates immutable finished-task evidence before forwarding;
API/store projection and event hash include the validated envelope. Browser
label/UUID remain self-reported attributes, not authenticated human identity.
The ledger binds authorization/generation, not the truth of the user-agent string.
It is required for version-2 events that acquired data. Legacy v1 events and
pre-admission skips may omit it; neither may claim admitted identity or completed
acquisition through that exception. A coalesced/not-due callback does not invent
a task or consume navigation capacity merely to send telemetry.

- [x] **Write a shared JS/Python protocol fixture for mid-batch deferral.**

```json
{
  "schema_version": 2,
  "operation": "market_news_sync",
  "mode": "quick",
  "phases": {
    "list_navigation": {"state": "complete", "reason_code": null},
    "list_scrape": {"state": "complete", "reason_code": null},
    "metadata_save": {"state": "complete", "reason_code": null},
    "detail_fetch": {"state": "deferred", "reason_code": "capacity_exhausted"},
    "capture_readback": {"state": "complete", "reason_code": null}
  },
  "item_outcomes": []
}
```

  Both derivations must return deferred/not-healthy, not complete/protocol-invalid.
- [x] **Run RED:** protocol and native/API roundtrip tests reject the unsupported
  version/envelope on the old implementation.
- [x] **Implement version-specific canonicalization and projection.**

```python
event_document = {"client_event_id": client_event_id,
                  "started_at": event_started, "finished_at": event_finished,
                  "result": result}
if acquisition_present:
    event_document["acquisition"] = validated_acquisition
```

  `acquisition_present` means the request actually included it, not a default
  `None`. Keep the existing diagnostics conditional too. Freeze the full new
  envelope before outbox persistence. The strict native/API allowlists and
  `record_extension_event_once` all change in the same commit. Public history
  includes only this bounded projection, never task secrets or URLs.
- [x] **Test delayed delivery and tampering.** Complete a task, switch owner,
  replay its old outbox event: one durable row with its old identity. Replay the
  same event ID with a different client/generation: reject. Missing terminal
  task evidence: refuse new identity claims, keep outbox delivery failure
  visible. Legacy v1 event hash stays byte-identical and records identity as
  absent. Legacy telemetry does not permit legacy acquisition.
- [x] **Test actual health consumers.** `src/service/sa_extension_health.py`
  must not promote a deferred event into the healthy anchor; UI/history must
  show waiting rather than a green successful capture. Retain completed data
  despite telemetry delivery errors. Keep task evidence at least through the
  seven-day outbox horizon and never discard active/undelivered evidence merely
  because the rolling traffic window ended.
- [x] **Run GREEN and commit:** outbox, protocol, native, job store, health and
  related frontend history tests. Commit `feat(sa): persist acquisition identity and deferred outcomes`.

## Task 4: Priority Queue And Guarded Existing Navigation

**Files:**
- Create: `extensions/sa_alpha_picks/acquisition_queue.js`, `acquisition_client.js`.
- Modify: `background.js`, `manifest.firefox.json` in that directory.
- Test: new `tests/test_sa_acquisition_queue.py`, `tests/test_sa_extension_reconciliation_flow.py`, `tests/test_sa_extension_diagnostics_flow.py`, `tests/test_sa_extension_packaging.py`.

**Interfaces:**

```javascript
// SAQueue.create({now}) returns these functions:
enqueue({key, priority, eligible, run}); // Promise<result>, coalesces by key
status(); // active key, pending lane counts, oldest wait and blocked reason

// SAAcquisition.create({control, storage, now}) returns:
runTask(descriptor, handler); // handler receives the task context below
// context.navigate({id, kind, destinationClass}, perform) -> Promise<browser result>
// context.observeRestriction(reason, retryAt) -> Promise<receipt>
// context.finish(result, cleanupConfirmed) -> Promise<receipt>
```

Use globals in the existing module style, Chrome `importScripts`, and Firefox
manifest dependency ordering. The task context consumes Task 2's control
messages. It persists task/navigation intent before native I/O; it never treats
an absent/ambiguous native response as admission.
Use Task 3's deferred-result protocol from the first guarded handler; do not
temporarily route a partial batch through the old complete/failed-only shape.

- [x] **Write the priority RED fixture in the existing Node VM harness.**

```javascript
const queue = SAQueue.create({now: () => 1000});
const order = [];
let release, entered;
const started = new Promise(resolve => { entered = resolve; });
const active = queue.enqueue({key:'active', priority:'background', eligible:async()=>true,
  run:async()=>{entered(); await new Promise(resolve=>{release=resolve;}); order.push('active');}});
await started;
const finance = queue.enqueue({key:'finance',priority:'background',eligible:async()=>true,
  run:async()=>{order.push('finance');}});
const news = queue.enqueue({key:'news',priority:'routine',eligible:async()=>true,
  run:async()=>{order.push('news');}});
release();
await Promise.all([active,finance,news]);
return order; // Python assertion: ['active', 'news', 'finance']
```

- [x] **Run RED:** `python -m pytest tests/test_sa_acquisition_queue.py -q`.
- [x] **Implement FIFO within each lane and routine-first selection at every
  task boundary.** Select with `routine.shift() || background.shift()`, then
  await and recheck `eligible()` before `run()`. Do not acquire a native active
  reservation while waiting for pacing/capacity. Persist financial waiting
  deadlines rather than sleeping inside the queue; expose starvation honestly.
  Route the old `enqueueSaSyncJob`, `enqueueAutoSaSyncJob` and
  `enqueueMarketNewsRecovery` paths through this one queue. Preserve Task 1's
  revision fences and existing automatic coalescing.
- [x] **Wrap every managed top-level navigation before calling the browser.**

```javascript
await task.navigate({id: navigationId, kind: "detail", destinationClass: "sa_article"},
  () => chrome.tabs.update(tabId, {url: item.url, active: false}));
```

  The client calls `admit_navigation` first and requires a fresh one-use permit.
  On replayed/unknown receipt it stops for recovery; it must not call `perform`
  again. Cover create/update/reload/retry and current, removed, articles, news,
  financial and recovery pages. Focus-only changes are not navigation debits;
  view clicks/scrolls keep existing bounds and separate observed action counts.
  Current-tab capture still needs task ownership before script injection.
- [x] **Fix the known login continuation and share restriction detection.**
  Move the existing bounded visible login/challenge/rate-limit detection into
  the acquisition client/readiness path for all flows, without network logging.
  On recognized site restriction, await native persistence, save completed
  progress and stop before the next page. Subscription-specific paywalls and
  layout/row gaps remain scope-specific; do not turn them into site-wide bans.
  If native restriction persistence fails, stop locally and leave the active
  reservation uncertain. Cleanup cannot authorize another page.
- [x] **Add tests:** the review's login replay now opens only current picks;
  rate/challenge affects both lanes; a financial layout failure still permits
  news; budget exhausted halfway through a news batch retains completed bodies
  and pending IDs without claiming complete; quick-to-full auto-upgrade also
  passes every navigation through the budget; old owner/current-tab commands
  cannot bypass admission. Verify no raw navigation call site is unaccounted for.
- [x] **Run GREEN and commit:** queue, reconciliation, diagnostics, protocol and
  packaging tests. Commit `feat(sa): prioritize routine work and guard page acquisition`.

## Task 5: Durable Financial Pacing, Scope Preview And Progress

**Files:**
- Modify: `extensions/sa_alpha_picks/company_refresh.js`, `background.js`, `src/sa/company_collector.py`.
- Test: `tests/test_sa_company_refresh.py`, `tests/test_sa_company_collector.py`.

**Interfaces:** Configuration adds `interval_days_by_view={annual, quarterly}`
and `financial_gap_seconds`; existing `interval_days` initializes both views
once without changing their values. New configurations keep both at 7 days and
gap at 60 seconds. `preview(config) -> Promise<projection>` is read-only and
returns actual target/scopes, missing/due/reusable/blocked counts, first-fill
flag, pacing lower bound and independently labeled observed-duration coverage.
`run({force:false})` fills missing/due work; advanced `force:true` is explicit.
Task 2's `next_financial_at` is the only pacing authority.

- [x] **Write RED for independent intervals, reads and pacing.** In the existing
  injected-clock fixture, annual and quarterly both succeed at time T. Set
  annual=30 and quarterly=7, advance to T+8 days; preview must report one due
  quarterly scope and one reusable annual scope, with no acquisition calls.
  Reading again at T+9 must not shift either success time or due deadline.

```javascript
await api.configure({...config, interval_days_by_view:{annual:30,quarterly:7},
  financial_gap_seconds:15});
const before = calls.length;
const first = await api.preview({...config, interval_days_by_view:{annual:30,quarterly:7}});
const second = await api.preview({...config, interval_days_by_view:{annual:30,quarterly:7}});
return {before, after:calls.length, first, second};
// Assert calls unchanged; identical clock gives identical deadlines and counts.
```

- [x] **Run RED:** `python -m pytest tests/test_sa_company_refresh.py -q`.
- [x] **Implement authoritative deadline continuation.** Remove financial
  cleanup's fixed ten-second sleep and stop using the one-minute alarm floor as
  an active-task gap. After cleanup, native authority sets
  `next_financial_at=finished_at+financial_gap_seconds`. Persist intent and this
  deadline before scheduling any timer. An active timer asks the priority queue
  again; alarms/startup recover the same state. Never hold the queue or native
  active token for the gap. Browser sleep makes execution later, never earlier.
  Use bounded timers with alarm fallback for long durations; reject numeric
  values whose millisecond/deadline conversion is not safely representable.
- [x] **Implement non-mutating preview and due-only ordinary update.**

```javascript
const remainingGaps = Math.max(0, pendingScopes - 1);
const pacingFloorSeconds = remainingGaps * config.financial_gap_seconds;
```

  Add any already-active authoritative delay separately. Do not present this
  lower bound as completion time. Keep observed capture time, routine waiting
  and capacity waiting separate; unknown sample coverage stays unknown. Resolve
  the complete App watchlist on preview and recheck before each scope. Local
  preview never claims ownership, spends capacity, or advances check time.
- [x] **Add tests for 15/30/60 seconds, active timer lost/recreated, stale timer
  after cancellation, watchlist removal, retry backoff, unchanged content reuse
  and failure preserving old data.** With news arriving at gap second 10, news
  runs before the next financial scope. Setting annual=30 is only a test input;
  do not silently adopt it as the production default because annual pages have
  TTM. Zero/missing/invalid settings must not create an infinite retry loop.
- [x] **Run GREEN and commit:** refresh/collector/queue/packaging tests.
  Commit `feat(sa): add resumable configurable financial refresh pacing`.

## Task 6: One Explicit Activation And A Useful Scope Preview

**Files:**
- Modify: `extensions/sa_alpha_picks/popup.html`, `popup_company_refresh.js`, `popup.js`, `background.js`.
- Test: `tests/test_sa_extension_popup.py`, `tests/js/run_sa_extension_popup_fixture.mjs`.

**Interfaces:** Popup message `preview_company_refresh` calls Task 5's read-only
preview; `enable_sa_updates_here` validates/saves selected configuration, obtains
explicit owner-change acknowledgement and accepted capacity policy, then enables
the selected schedule last. `save_company_refresh` saves without owner selection
or acquisition. Ordinary `run_company_refresh` uses `force:false`; an explicitly
confirmed advanced command uses `force:true`. Read existing controls through the
shared status projection; no independent browser-local notion of active owner.

- [x] **Write mounted RED scenarios.** Reuse `_run` and extend the runner with
  `preview_company_scope`, `enable_sa_updates_here`, and failure responses:

```python
def test_scope_preview_does_not_select_or_start_collector():
    result = _run("preview_company_scope")
    actions = [message["action"] for message in result["sent"]]
    assert "preview_company_refresh" in actions
    assert "enable_sa_updates_here" not in actions
    assert "run_company_refresh" not in actions

def test_failed_activation_keeps_schedule_disabled():
    result = _run("enable_sa_updates_here", activationError="collector_busy")
    assert result["companyRefreshEnabled"] is False
    assert "collector_busy" in result["companyRefreshStatus"]
```

- [x] **Run RED:** popup tests before changing controls.
- [x] **Implement a compact shared popup flow.** Main area: explicit test vs
  production, collector/browser/installation, actual complete watchlist count,
  statements/views, per-view repeat checks, first-fill/maintenance preview,
  pending/current/next eligibility and effective financial gap. Primary action:
  enable chosen updates here; secondary: save only or update missing/due now.
  Advanced: 15/30/60/custom gap, total/reserved capacity, force refresh and
  explicit stopped/recovery. Do not move existing news/AP actions into a second
  browser-specific UI. Use established controls; no nested decorative cards.
- [x] **Implement activation as fail-closed steps.** Save intent disabled, verify
  expected owner generation/policy acknowledgement, select/configure only while
  idle, persist confirmed state, then set enabled and install alarms. Any failure
  leaves acquisition off and reports exactly which step failed. Idempotent
  repeated activation cannot steal a newly selected owner. Do not auto-copy the
  previous browser's schedules or infer selection from opening this popup.
- [x] **Test every preview checkbox and dirty-state refresh.** A 180-company
  synthetic universe yields 540 scopes for three annual statements and 1,080
  after quarterly is checked. Pacing wait at 15 seconds is `(1080-1)*15`, not an
  exact ETA. Unsupported symbols, unavailable watchlist, other owner, capacity
  exhaustion and stale heartbeat must all remain visible. Missing heartbeat is
  unavailable/unknown, not proof that a browser is closed. Previews arriving out
  of order cannot overwrite the latest unsaved selection.
- [x] **Run GREEN and screenshot real popup layouts in both browser engines.**
  Check narrow popup and standalone heights, wrapping, scroll reachability and
  no clipped buttons. Commit `feat(sa): simplify shared collector and watchlist controls`.

## Task 7: Installed Package Parity And Mixed-Workload Acceptance

**Files:**
- Modify: `extensions/sa_alpha_picks/build_firefox.py` only if dependency closure needs it; manifests and `tests/test_sa_extension_packaging.py`.
- Create: `tests/js/run_sa_acquisition_browser_fixture.mjs`, `tests/test_sa_acquisition_browser.py`.
- Update controlled test artifacts: `/home/hyl/ArkScope-Company-Test/native_host.py`, `check_ready.py`, and test extension build only after verifying their current contents.
- Evidence: `docs/superpowers/evidence/2026-09-23-sa-automation-coordination/`.

**Interfaces:** Node fixture returns JSON with `browser`, ordered admissions,
navigation attempts, owner generation, stored scopes, deferred outcomes and
remaining reservations. It runs against isolated fake pages/native I/O only.
The installed private native wrapper must exercise the real framed protocol;
API mocks alone cannot establish host readiness.

- [x] **Write RED package-closure and host-action checks.** Both builds must load
  queue/client before background registration. The private wrapper must accept
  the exact new action used by the extension, refuse unapproved source actions,
  and preserve test database isolation. Do not fix the previous six-action
  whitelist problem by allowing every native action.

```python
def test_both_builds_include_shared_acquisition_modules():
    graph = _load_builder().discover_dependency_graph(EXT_DIR)
    assert {"acquisition_queue.js", "acquisition_client.js"} <= set(graph.files)
```

- [x] **Run RED then implement/rebuild the private artifacts atomically.** Keep
  test addon/host IDs and AAPL/AMD private watchlist separate from production.
  Verify the actual framed native request succeeds before asking the user to
  click anything. Preparing Chrome requires a separate test registration, not
  assuming the Firefox host registration covers Chrome.
- [x] **Run installed offline cases on Firefox and Chromium.** Use real alarms
  and worker restart plus fake providers: active 15-second continuation, news
  arriving during gap, cancellation, simultaneous browsers, budget exhaustion,
  retained partial data, lost native acknowledgement and sleeping worker restart.
  Assert zero overlapping acquisitions and no repeated saved scopes. Unpacked
  Chromium alarm behavior is not sufficient production Chrome acceptance.
- [ ] **Request bounded signed-in acceptance only after preflight.** Firefox
  first, two companies plus explicitly enabled bounded routine work, synthetic
  operator-accepted low capacity for the trial. Stop at a challenge/restriction,
  inspect saved rows and receipts. Separately test signed-in Chrome under an
  explicit idle owner switch. Do not start the 180-plus production universe.
- [x] **Record evidence and commit:** distinguish installed offline, real SA,
  user-confirmed and unverified cases. Commit `test(sa): verify coordinated browser acquisition end to end`.

## Task 8: Freeze, Review And Controlled Rollout Handoff

**Files:**
- Update: `DATA_ACQUISITION_AND_UPDATES.md`, `docs/design/PROJECT_PRIORITY_MAP.md`, `docs/superpowers/plans/2026-09-21-company-research-workflow.md`, this plan.
- Update: coordination evidence directory from Task 7.

**Interfaces:** One frozen source revision for the full regression and external
review. Operator-facing status separates implemented, offline verified,
signed-in verified and not activated. Root acquisition document remains the
durable policy linked from README, not an evidence file alone.

- [ ] **Freeze and run focused regressions serially.** Include the current SA
  suites, active-universe membership, job history/health, action source-policy
  enforcement and current local-read no-side-effect tests. No provider calls or
  parallel full backend runs against shared state.
- [ ] **Run the complete candidate verification once:**

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -m pytest tests -q
npm test --workspace apps/arkscope-web
npm run typecheck --workspace apps/arkscope-web
npm run build --workspace apps/arkscope-web
npm run check:i18n-literals --workspace apps/arkscope-web
node --test apps/arkscope-desktop/*.test.js
git diff --check
```

  Use the established isolated regression environment; the commands are separate
  executions, not concurrent. Record exact revision, counts, skips, exits and
  evidence paths. Compare to the prior frozen `e91075cc` acceptance, but do not
  assert the old totals as the expected new totals.
- [ ] **Review current versus planned policy and rollout inventory.** Before
  actual activation, inventory registered production extensions, verify their
  code revisions and explicitly stop/update all legacy automated instances.
  Select one installation and its schedules, gap and hourly/daily totals/reserves
  with the operator. Clearly disclose unmeasured prior/manual website traffic.
  Retain old data, stopped old profiles and a backed-up authority state; rollback
  stops acquisition rather than running old clients against a new ledger.
- [ ] **Report the integrated result without merging/pushing automatically.**
  User approval to develop is not activation. Follow branch completion review
  only after accepted tests. User pushes manually. Mark any missing signed-in
  Chrome or production trial as open, not waived by fixture tests.

## Coverage And Handoff

| Spec requirement | Task |
|---|---|
| Browser-neutral single selected installation, no takeover | 2, 4, 6, 7 |
| Routine priority, no preemption, coalescing and starvation status | 1, 4, 5 |
| 15-second configurable financial gap and suspension-safe progress | 2, 5, 7 |
| Rolling budgets, reserved routine capacity, corruption/replay guards | 2, 3, 4 |
| Site restriction versus scope failure; stop before next page | 3, 4 |
| Dynamic whole-watchlist preview, per-view checks, one-action setup | 5, 6 |
| End-to-end identity, old outbox replay, honest deferred result | 3 |
| Test-host readiness, Chrome/Firefox parity, explicit activation | 7, 8 |

Cadence is intentionally not increased in this delivery. The review found that
quick comment acquisition is change-driven, not seven-day scheduled recovery.
After the new attempt/yield and coverage receipts exist, evaluate a separately
bounded comment-maintenance schedule and explicit news-window presets; never
silently enable unrestricted Full/Deep scans as a workaround.

The initial implementations and the older two-company Firefox financial acceptance
already exist. This delivery implements coordination and both scheduling repairs;
installed offline results do not replace new signed-in coordination acceptance.
Persistent service/failure delivery and external read/analysis MCP
remain required independent work; recent-news retention is lower priority by
the operator's latest decision. Other research-tool gaps retain their existing
owners. None is declared complete by this handoff.
