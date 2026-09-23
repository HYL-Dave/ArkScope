# SA Automation Coordination And Controls

Status: written design for review, not implemented behavior. On September 23
the operator approved extending the explicitly selected collector to all SA
automation, initially Firefox, while developing Chrome and Firefox together.
They also require a simpler whole-watchlist workflow and configurable pacing,
including 15 seconds. Existing production collectors/settings are unchanged.
Accepting this direction does not authorize production activation or migration.

## Outcome And Scope

Keep routine news, Alpha Picks and comment acquisition useful while company
financial backfill uses otherwise available capacity. Selection, execution,
progress and pauses must be understandable without following a test runbook.
Keep research access local-first and source-labeled; no paid fallback, new
provider, account rotation, challenge bypass or new headless collector.

This is an extension/native-host coordination change, not the persistent-service
or external-MCP workstream. Those remain required and independently deliverable.
Use the existing queue, capture handlers, native authority and telemetry owners;
do not introduce a second scheduler service or rewrite working extractors.

## Verified Starting Point

- `background.js` serializes jobs within one extension installation through
  `saSyncJobChain`. News and Alpha Picks automatic triggers coalesce while
  pending. A news job includes its detail loop and occupies the queue until it
  finishes; this is serialization, not priority scheduling or cross-browser
  exclusion. Financial watchlist work currently submits one scope at a time.
- `src/sa/company_collector.py` owns financial-only selection, reservations,
  cooldown and a fixed 60-second admission gap. Other SA flows do not inherit
  that cross-installation authority. The financial scheduler separately enforces
  a one-minute alarm floor and capture cleanup includes another ten-second wait.
  Adding a numeric popup field alone would not implement 15-second pacing.
- Annual captures can include TTM or Last Report columns. The isolated AAPL
  and AMD annual observations both contain TTM. Annual-page selection therefore
  does not mean all of its content changes only once a year.
- Native telemetry and the API's strict request schema omit collector identity.
  A client event UUID is not a browser/installation identity or admission proof.
- The [read-only seven-day audit](../evidence/2026-09-23-sa-automation-baseline.json)
  covers September 16 12:23:59 UTC through September 23 12:23:59 UTC, by
  `started_at`: news has 814 receipts, **190 complete and 624 skipped**; Alpha
  Picks has 38, **36 complete and two degraded**. None contains browser identity.
  No credentials, article bodies or raw research payloads were exported.

These are job outcomes, not page counts or HTTP request counts. One job may
navigate many pages, and one page may issue many requests. The theoretical
86,400 / gap calculation ignores loading, parsing, saving, other jobs and sleep.
Neither a 10-50x traffic estimate nor a safe quota follows from these receipts.

Owners: [queue and handlers](../../../extensions/sa_alpha_picks/background.js),
[financial scheduler](../../../extensions/sa_alpha_picks/company_refresh.js),
[collector](../../../src/sa/company_collector.py),
[outbox](../../../extensions/sa_alpha_picks/extension_telemetry.js),
[native forwarding](../../../src/sa_native_host.py),
[telemetry endpoint](../../../src/api/routes/jobs.py).

## Scheduling Choice

Use **routine-first priority**, not strict round-robin and not separate concurrent
workers. Round-robin would grant financial backfill equal turns even when
routine work is waiting; parallel workers would weaken tab/admission control.

- The priority queue contains due news, Alpha Picks and comment/reconciliation
  acquisition. Preserve existing extraction/cleaning and configured eligibility
  intervals. Existing small internal page delays remain source-specific.
- The background queue contains company financial work, including operator-
  requested bulk updates. One financial scope runs only when no eligible
  priority job is ready. Do not enqueue the entire financial universe ahead of
  subsequent routine triggers in the existing FIFO promise chain.
- Recheck priority at every financial task boundary and after its pacing wait.
  A newly arrived priority task does not abort a page already being acquired;
  finish/save/clean up that bounded task before yielding. Existing readiness and
  execution timeouts remain, so a hung capture cannot monopolize the runner.
- Do not split existing news/Alpha Picks extraction loops merely to interleave
  financial work. Admission, metering and receipt wrappers do change: preserving
  product behavior is not a claim that their code remains byte-identical.
- Coalesce repeated triggers by operation/scope. A waiting periodic job is
  rechecked for eligibility before navigation. Missed intervals do not create a
  catch-up burst. Local reads, previews and skipped jobs do not spend capacity.
- Persist financial intent, cursor/completion state and earliest eligibility.
  Cancellation invalidates queued intent and stale asynchronous continuations.
  An uncertain active reservation still needs explicit recovery after stopping
  the previous collector; no automatic lease takeover.
- Strict priority can delay financial completion indefinitely. Show
  `waiting_for_priority_work` with the oldest pending age, not a fictitious
  completion guarantee. Report prolonged delay; do not silently boost financial
  priority or bypass a budget. Routine priority is not a real-time SLA.

## One Acquisition Owner

Extend the selected browser-installation identity and generation to all managed
SA acquisition through one local authority beside the selected SA store. Each
admitted action must belong to that generation. A browser family name is not
enough: two Chrome profiles or two registered extensions are separate clients.

An explicit activation selects Firefox initially. The other installations can
read local data/status but cannot start managed SA acquisition. Selection is
not inferred from opening a popup, saving configuration or seeing a heartbeat.
No automatic browser failover. A switch requires the old owner to be idle or
explicitly stopped/recovered, and must disclose the destination's schedule
configuration; do not silently copy or enable another installation's schedules.

When Firefox is closed, scheduled SA acquisition waits. The UI must say that the
collector is unavailable, rather than displaying an apparently healthy schedule.
This does not require Firefox to be the user's default browsing application.
It does not make a temporary add-on survive restart or let a closed browser run.

Old extensions can navigate before asking the native host to save. Rejecting an
old save protocol therefore cannot prevent their traffic. Production activation
must inventory/update the registered installations and stop their old automatic
jobs first. Registration does not prove a browser was previously running. Keep
activation separate from code installation; do not claim control over manual
website browsing, other machines or unrelated clients.

## Pacing And Capacity

### Configurable Financial Gap

Expose financial-task pacing in advanced settings, with its effective value
visible in the main summary. Retain 60 seconds for existing configurations until
explicitly changed; offer 15/30/60-second choices and valid custom positive
seconds. Validate numeric/time bounds on both sides, with no silent clamping.
The gap is from completed financial task cleanup to the next financial task's
start, not an HTTP request rate. Routine jobs may use that waiting time, subject
to their own pacing and the shared admission policy.

Use one authoritative deadline; remove redundant fixed financial sleeps rather
than adding a configurable wait to the old ten/sixty-second delays. During active
execution a short timer can request the next admitted task. Persist deadlines
and use alarms/startup to recover after suspension. Timers are an optimization,
not durable state. Do not keep one multi-hour message handler alive or add dummy
traffic solely to keep a worker awake. Clock regression cannot bypass a deadline.

Chrome's installed-extension alarms have a 30-second minimum wake interval and
may run late; unloaded event pages also lose ordinary timers. Consequently a
15-second setting is a **minimum wait**, not a guaranteed launch every 15 seconds.
Verify active continuation and suspended/restarted recovery separately in both
browsers, including a packaged Chrome build; unpacked behavior is insufficient.
References: [Chrome alarms](https://developer.chrome.com/docs/extensions/reference/api/alarms#method-create),
[worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle),
[Firefox event pages](https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Background_scripts#change_timers_into_alarms).

### Shared Navigation Budgets

Introduce operator-defined rolling one-hour and 24-hour budgets across managed
SA **top-level page-navigation attempts**, plus reserved capacity for routine
work. Include list/detail navigation, reloads and navigation retries from all
managed acquisition flows. Reserve/debit atomically before navigation; an
uncertain started attempt is not refunded. Idempotent admission prevents a
retried control message from being counted twice. Store counters durably under
the same local authority; browser switching/restart must not reset them.

For each window, routine work may use remaining total capacity. Financial work
must leave the still-unused routine reservation available. Validate that the
reservation does not exceed the total. Exhaustion defers work until eligibility
returns; priority cannot override the total ceiling. Lack of background capacity
does not hold a busy lock or block eligible routine work.

These are local safety budgets, not SA entitlements or measured HTTP quotas.
View changes, scrolling and page subrequests can generate additional traffic;
retain their existing bounds and expose observable action counts separately.
Do not label navigation counts as complete request accounting. No interception
of credentials or wholesale network logging is needed for this design.

Do not invent numerical hourly/daily limits from 814 job receipts. Budget values
are explicit operator inputs at attended activation, validated in both native
and UI paths. New coordinated background acquisition remains disabled without
an accepted policy. Tests use explicit synthetic limits. Existing production
automation is not altered while this design/implementation is being prepared.
First activation records `managed_since` and prior-traffic coverage as unknown;
later missing/corrupt counters fail closed instead of creating a fresh allowance.

### Shared Restrictions

A recognized rate-limit or human-verification signal pauses further managed SA
acquisition across both priorities before tab cleanup. Preserve saved progress;
no switching browser, manual Update now or shorter gap bypasses the restriction.
Retain the existing local rate-limit backoff initially; respect a reliably
observed longer provider deadline. Human verification requires operator action,
not a timer or automatic repeated challenge attempts. Resume does not issue a
catch-up burst.

Parser/layout or one-page data gaps remain scope-specific unless evidence shows
a site-wide restriction. Do not suspend news merely because a financial row is
unsupported. The initial detector is bounded visible-page evidence, not a claim
of complete HTTP 429/Retry-After monitoring. Test these distinctions explicitly.

## Operator Workflow And Estimates

- Clearly show test versus production context and the selected installation.
  Default new target selection to the App's complete watchlist, with actual
  membership count, unsupported symbols and selectable statement/view scope.
- One explicit primary action configures and enables updates in this browser.
  It summarizes any owner change and refuses active/conflicting acquisition.
  Preserve settings without starting work as a secondary action. Do not silently
  enable production while upgrading the extension.
- Ordinary immediate update fills missing/due observations. Explicit force
  refresh is an advanced command with its scope/cost preview; it remains subject
  to priority, budget, pacing and restrictions.
- Allow independent annual and quarterly repeat-check intervals. Preserve the
  old interval for both on upgrade; do not silently replace it with 30/7 days.
  Explain the current TTM/latest-report column scope and show its actual capture
  time. No claim that historical facts expire or annual pages update only yearly.
- Recompute the preview as selections change: companies, total scopes, missing,
  due, reusable and blocked scopes. Preview is read-only; revalidate on execution.
  Distinguish first fill from routine maintenance and remaining from total work.
- Separate minimum pacing time from observed load/parse/save time, priority
  interference and budget-window delay. Use observed timing ranges where there
  is coverage; otherwise say timing is unknown. Avoid double-counting delays
  already included in measured durations. At 1,080 scopes, 15 seconds alone is
  roughly 4.5 hours of inter-task waits, not a 4.5-hour completion forecast.
- Make paused, waiting, running, complete and failed states visible, including
  current task, pending count and next eligibility. Support multi-day progress
  without requiring the popup to remain open. An unexpectedly interrupted active
  page still has explicit recovery; ordinary queued work resumes from its state.

## Identity And Receipts

Extend producer, outbox, native forwarding, strict API schema, canonical event
hash and persisted projection together. Record browser family, installation ID,
extension build/protocol, collector generation, batch/task/admission identifiers,
priority, trigger, attempt outcomes and observed navigation counts. Keep queue
wait, actual acquisition duration, deferred/skipped outcome and telemetry
delivery failure distinct. Do not include credentials, cookies or full page text.

Browser labels/UUIDs supplied by a caller are not authorization. The native
authority must validate the active owner/generation and bind admission receipts
to that state before acquisition; telemetry references that admission evidence.
Reject mismatches instead of trusting a browser string. Where transport identity
is unavailable, disclose that limit rather than call a self-report authenticated.
External tools gain no acquisition permission from this change.

Allow delayed legacy outbox records to retain their old hash/projection and an
explicit absent identity, without granting legacy acquisition admission or
rewriting history. Verify replay/idempotency and identity tampering together.

## Acceptance And Rollout

1. Offline mixed-workload tests: repeated due triggers, priority arrival during
   financial pacing/capture, long existing batches, cancellation, starvation
   status, closed collector and no silent browser takeover.
2. Shared-authority tests: concurrent installations, atomic capacity reservation,
   window boundaries, restart/clock regression, uncertain navigation, corrupt
   counters, old protocol and source-specific versus site-wide failures.
3. Schema/outbox round trips: full identity survives forwarding and retries;
   conflicting identity/hash is refused; old rows remain unknown, not inferred.
4. Installed Firefox and Chrome: actual 15-second active continuation, worker
   suspension and alarm recovery, completed scopes not repeated, no overlap or
   phantom success. No claim that timers run while browser/device is asleep.
5. UI tests: live read-only estimates, test/production identity, all-watchlist
   counts, separate check intervals, one-action activation and responsive layout.
6. Bounded signed-in acceptance: mix the existing two-company test list with
   explicitly enabled routine work in isolation. Observe identity, navigation
   counts, actual timing and restrictions before any production bulk rollout.

Freeze the integration candidate for full regressions. Deployment then checks
all installed clients, asks for explicit budget/owner/schedule acceptance and
uses an attended bounded production trial. No activation is implied by a green
fixture test or acceptance of this written design. Ordinary manual website use
remains outside the managed navigation budget.

## Remaining Independent Work

This does not complete persistent-service lifetime/failure delivery, external
read/analysis MCP, other audited research-tool gaps, production comment backlog,
replacement-dependent SEC retirement, news search/retention, runtime migration,
cross-platform validation or Python sandbox work. The root
[Data Acquisition And Updates](../../../DATA_ACQUISITION_AND_UPDATES.md)
continues to describe current behavior separately from this proposal.
