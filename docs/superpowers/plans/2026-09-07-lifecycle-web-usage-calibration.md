# Lifecycle Web Usage Calibration

**September 7 live update:** The earlier eight-SDK/eight-HTTP campaign remains
sealed in `../evidence/2026-09-07-lifecycle-web-usage-canary/RESULTS.md`. The user
renewed source authority and allowed larger bounds. The newer instrument-scoping
campaign uses four SDK submissions / nine of twenty-four HTTP attempts; it has
one complete fresh live protocol but no action-ready model finding. Public
originals resolve source coverage; output/grounding and bounded-follow-up work
remain. Current backend is 6,931 passed / 12 skipped, focus 2,266, integration
3,085 and 25 named reverse mutants. Other auth budgets remain unchanged, and no
other channel ran live. No production installation/action/restart/merge/push.
See `../evidence/2026-09-07-lifecycle-web-instrument-scoping/RESULTS.md` for the
distinct allowance, failed diagnostics and pending schema decision.

## Authority And Scope

Continue offline implementation after the attended-write concurrency seal
`1c4564f7d59261deb2fdb710fa421e90e5541be1b55df482774bbec1cc26e0e4`.
The user's offer of advance authorization is not unlimited dispatch permission.
The separately proposed live envelope below requires confirmation before use.
No production data/credential read, provider dispatch, installation, App restart,
commit, merge or push belongs to the offline amendment.

## Observed Problem

The unchanged September 7 Sonnet canary records a completed search with SDK
top-level input/output of 4 / 1,036 and per-model input/output of 29,706 / 3,228,
plus 3,976 cache-created input, 3,354 cache-read input and two Web searches.
The existing adapter consumes only top-level `usage`. Source failure then loses
the accepted phase's counters from the durable product result.

Installed Claude Agent SDK 0.2.151 exposes `model_usage` entries with camelCase
keys, passed through from the CLI. [Official cost tracking documentation](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
distinguishes main-loop counters from `model_usage`, which includes nested work.
It also calls monetary figures local estimates, not billing authority. This
amendment reports observed counters, not subscription charging, account quota,
USD cost or context capacity. The previous seal and live receipts are immutable.

## Bounded Correction

1. Claude Web results use the selected-model-validated `model_usage` map for
   input/output and separately retain reported cache/search counters. Missing
   fields or an absent/empty aggregate remain unknown; never substitute smaller
   top-level counters or choose the maximum of incompatible scopes. Present
   malformed counters remain typed errors. The known top-level counters survive
   in closed internal diagnostics, not as an alternative total.
2. Keep the shared `ModelReply` input/output contract and add optional,
   purpose-specific counter provenance. Other transports retain their current
   counter semantics; do not rewrite Research or Content Translation. Reports
   from accepted phases are captured by the existing `on_reply` hook and bound
   to their exact journal call/remote terminal. The hook does not dispatch.
3. Persist the bounded report in existing final result JSON, on both success and
   ordinary failure. No new DDL or mutable result table. Recheck call bindings
   on write and read. Missing legacy reports are unknown, not fabricated
   zero-call receipts; malformed present reports do not become absent reports.
   A process crash or failed journal write can still lose in-memory counters:
   recovery must then show unknown. This is not crash-durable per-token logging.
4. Aggregate only accepted, identified phase reports. Expose the known subtotal
   separately from totals covering every submitted phase. Missing/unfinished or
   rejected replies do not become zero consumption. A single completed search
   followed by source failure can have fully reported submitted work without
   being a successful investigation. No accounting field authorizes adoption.
5. A closed optional DTO reaches both UI and Research. Show it in a collapsed
   execution-usage section: provenance, reported/missing coverage, input/output
   and separately reported cache counts. Do not project remote IDs, tokens, raw
   SDK objects or native cost estimates. Legacy records explicitly lack counter
   scope. Numeric limits are JSON-safe integer representation, not model limits.

## RED And Positive Controls

- Reproduce the sealed Sonnet counters through the real SDK wire parser, not a
  made-up result shape. Test zero, absent aggregate, absent fields, malformed
  bool/string/negative/unsafe integer, and wrong-model controls.
- A real temporary controller/pipeline with search success and source failure
  must retain the search count and actual source attempts. A second submitted
  phase with no accepted reply stays partial; no submitted phase is counted
  twice. Test four auth channels without live calls.
- Test exact call/session/terminal binding, rejected duplicate reports,
  mutable/tampered JSON, legacy missing fields, zero versus unknown and no
  model/credential/remote ID leak in UI/Research. A usage-only failed result is
  never a finding and survives population accounting.
- Both locales must distinguish full reported coverage from a partial subtotal
  and unreported counters. Parser and real-component/browser owners cover
  malformed present versus absent legacy data, zero counts and small screens.
- Mutations must fail named owners across the whole affected focus/full UI;
  preserve raw RED, repaired results, source hashes and unique node changes.
  Full backend, frontend, typecheck/build/i18n and the evidence seal precede live
  dispatch. This amendment does not reopen the confirmed write-concurrency fix.

## Separate Research Follow-Up

`claude_code_sdk_driver._aggregate_model_usage` still reads snake_case keys from
the camelCase per-model map, and `_result_token_usage` prefers a nonzero
top-level value. This is the same diagnostic family on another execution path.
Record and reproduce it separately; do not silently broaden this lifecycle
change to Research billing/provenance behavior or use its helper as correct
normalization merely because it already exists.

## Proposed Conditional Live Envelope

After offline admission and explicit confirmation: one public TA investigation
in a newly created temporary journal, Sonnet 5 with medium effort on the unique
selected Claude Code OAuth credential. Both helper overrides select Sonnet 5.
At most two SDK submissions, search then analysis; search has six CLI turns
and four admitted WebSearch uses, analysis two turns. Four public sources,
eight source HTTP attempts including redirects, at most two redirects per page;
32 MiB encoded and 128 MiB decoded per source, 180 seconds shared source reading
and 180 seconds per model phase. These are enforceable local/CLI bounds, not
native hidden provider HTTP counts or a monetary/subscription-quota guarantee.

Read only the selected OAuth credential/token and exact SEC contact field needed
for public retrieval. No `.env`, alternative key/account, production snapshot,
profile/market/SA write, human adoption, migration, App restart, merge or push.
Model/protocol/safety failure stops dispatch without retry or fallback. A failed
supplementary source is recorded and does not prevent reading the remaining
already-authorized candidates. Bind final source/runner/runtime hashes before
dispatch; capture actual counters, source attempts, auth/model/session witnesses
and cleanup, without private identifiers in published evidence.
The prepared runner uses a 660-second local completion deadline to include
validation/cleanup after the source and two model phase deadlines; it grants no
additional model submission. Its checkpoint hash must be supplied explicitly.

Protocol success requires owned search and analysis terminals, validated exact
citations, durable readback, literal subscription auth and the selected model.
Quality is independent: bind TravelCenters common stock, not senior notes or a
generic TA abbreviation; acquisition alone is not delisting and BP is not a
same-security successor. Read gaps stay disclosed; essential uncertainty or
contradictory active/OTC evidence still blocks action. No finding is applied by
this canary, even if action-ready.

## Offline Completion

- [x] Usage scope, call-bound durable final reports and closed shared projection.
- [x] Real SDK wire and four-channel synthetic success/failure/readback controls.
- [x] Whole-focus baseline/restoration: 2,195; integration: 3,014. Sixteen
  backend mutations fail named owners on that entire focus.
- [x] Complete backend: 6,860 passed / 12 skipped / three existing edgartools
  warnings. Complete frontend: 1,604 passed with eight owned mutations.
- [x] Browser: 54 cases / 108 screenshots, two locales and 1440/390/320 widths.
- [x] Disk-backed maximum-source concurrency: both removal and rename finish
  two jobs with four 128 MiB sources per job. Human confirmation takes
  22.534 / 21.033 seconds; each write transaction stays below 0.525 seconds;
  peak child RSS stays below 1.8 GiB. Not a whole-App memory guarantee.
- [x] Current-source canary harness: nine offline cases and three owned
  mutations. Its `on_reply` observer preserves the controller callback.
- [x] Record the separate Research counter defect without changing that path.
- [x] Explicit confirmation and bounded live attempts, recorded in the linked
  September 7 results. Only the authorized selected credential metadata/token
  and exact SEC contact field were read. Historical pre-authorization evidence
  remains unchanged.
- [ ] Citation/date/source quality follow-up and a new complete live gate after
  separately renewing the exhausted public-source HTTP budget.
- [ ] Remaining live-channel gates and separately authorized production
  installation/population cutover, merge, restart and user hand testing.

Final source, measurement, node-ledger and historical-failure sealing is
recorded by the create-only `2026-09-07-lifecycle-web-usage/files.sha256.json`
artifact and its verification, not inferred from the checkboxes in this plan.

Historical results are not quietly replaced: the first backend campaign was
interrupted after the first full frontend run exposed the expected +21 i18n
leaf-count update; both complete final campaigns were rerun. The canary's first
nine-case green run had an empty HTTP-observation list. A populated-list owner
exposed `request_number` versus `request_index`; corrected final rehearsal and
the reverse mutation now cover it. Earlier sealed live packets remain unchanged.
