# Task 1 R1 Independent Review

## Findings

### P2: Pre-dispatch reservation interruption still makes terminal jobs unreadable

**Location:** [src/lifecycle_investigation/store.py:91](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/store.py:91), the new `stats["model_submissions"] != len(calls)` read guard.

The original completed-observation defect is corrected in r1, but the submission-count invariant has a separate producer mismatch. [InvestigationControl.reserve_model_request:337](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/store.py:337) calls the inherited in-memory reservation before `store.reserve_call`. The inherited method inserts into `_calls` ([contract:212](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_web_contract.py:212)). If durable reservation sees a cancellation or fails, the in-memory request remains counted. `agent.stats()` saves that count, and the real controller successfully persists the failed/cancelled result with zero durable calls.

**Deterministic reproduction:** in the existing real-controller fixture, wrap `store.reserve_call` to call the real `store.cancel(identity)` immediately before invoking the original reservation. This models another connection cancelling between local and durable reservation; it does not damage rows or bypass triggers. The original reservation raises `stop_requested`. A second arm raises a reservation recording error before any call row is inserted, matching the existing store-level recording-failure contract.

Both arms finish before any synthetic remote dispatch and preserve:
- Zero durable call rows and zero returned model replies.
- A saved result with `model_submissions=1` and token totals `(None, None)`.
- A durable job status of `cancelled` or `failed`.

The controller's subsequent read raises `ValueError("investigation_integrity")` at the new read guard. The latest-job and reopened-store paths share this guard. This is ordinary current interrupted work, not an old-feature compatibility request. The existing recording-failure test in `test_lifecycle_investigation_store.py` only checks a still-running job with no result; r1's new recording-failure owner fails the later `model_result` append after a durable completed call, so neither covers this earlier boundary.

**Proof:** [task1_r1_review_diagnostics.py:24](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r1_review_diagnostics.py:24), nodes `test_pre_dispatch_reservation_interruption_remains_readable[cancel_before_reservation]` and `[reservation_failure]`. [task1-r1-review-focused-01.xml](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r1-review-focused-01.xml): **2 failed, 27 passed, 8.996s**. The same workflow without reservation interruption passes.

**Required correction:** make submission accounting distinguish a failed local reservation from durable submitted work, including the associated known/unknown totals. Preserve stop-before-dispatch and strict reader integrity. Add terminal controller/reopen owners for this boundary, not only control-object assertions.

## Original Finding Resolution

The original report remains byte-for-byte unchanged: SHA-256 `f309dac5ee402ae77858f7f45cbbd9bde78b6081dc3e0414f8d28e6897f990af`.

R1's correction at [agent.py:288](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:288) is precise:
1. Completed terminal/remote binding and optional usage-observation validation still precede persistence.
2. `on_step("model_result", ...)` persists already completed work without the dispatch-time stop/deadline check; the controller callback still enforces its permission check and the store still enforces ownership.
3. Only a successful callback appends the reply to aggregated usage. An append failure therefore retains unknown totals for the durable call.
4. `check()` runs before returning the reply for further action processing. No new model or source work is authorized by recording the observation.

All four promoted completed-reply owners pass independently, including recording failure. Four additional scratch controls cover known and unknown tokens under both cancellation and deadline expiry using a returned `search_web` action: each retains one completed observation, dispatches exactly once, records no `agent_action` or `web_search`, and offers no adoption. The original completion-before-step scenario is resolved for newly produced r1 results; the remaining finding is the earlier reservation boundary.

## Whole-Task1 Verdict

**Revise: one remaining P2 blocker.** This is a whole-Task1 review carried forward from the original assessment, plus the exact r1 delta, not a review of only the new function.

All 11 original source/absence hashes match the first reviewed package. Accordingly, the original concrete checks still apply to physical removal of old store/review/projection, direct current imports, retained `sla_web_` IDs and `web` receipt keys, provider/identity/freshness/evidence guards, atomic attended approval/idempotency/reversal, ordered step/call ephemeral binding, owned capture closing before decode, strict supplied-passage shape and captured history provenance. The store's observation validator is unchanged, not weakened to make the correction pass.

The new source-read owner is now included in the frozen package. All four arms pass in the independent r1 run. Supplied inverse XML also shows the intended three malformed-record failures when that branch is skipped, followed by eight restored passes. No additional blocker was established in the unchanged extraction/history paths. Task2 FK/schema/backup/disposal/population work remains excluded.

## Frozen Identity

- Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
- Package: `task1r1-review-package.md`; SHA-256 `8cb7219b120ead250fc1b1a6d2cff71e47b0a7777ae44b2165011f48cba3a0ff`.
- Exact fenced diff: 310628 bytes; SHA-256 `acf0fa97fc7c1eedca73d2058548ec0324fd213ff176447089492303a5478e53`.
- All 33 current path hashes/absences matched before and after the focused run.
- Only `src/lifecycle_investigation/agent.py` and `tests/test_current_investigation_ownership.py` differ from the initial declared scope; agent is the one added source path.
- Agent SHA-256: `34232b6237705b5b71488de90bb899244e9bfd12adc2d5bc9f90b5913c16b379`.
- Parent ownership-test SHA-256: `3976d916a53cb4aaee4dafe658a604b2119ecac43078fbc84c26a0b1fb6f1f7a`.

## Verification

Independent existing-runner invocation from the worktree:
```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r1-review-focused-01 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r1_review_diagnostics.py tests/test_current_investigation_ownership.py tests/test_lifecycle_investigation_usage_journal.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r1-review-focused-01.xml
```

Results: 12 parent ownership nodes passed; all 10 current usage nodes passed; five new scratch controls passed; two new reservation-boundary proofs failed. Known totals, partial/unknown usage, lost remote outcomes, unbound/duplicate usage and malformed aggregate refusals all retain their current owners.

Supplied XML inspected separately:
- `parent-completed-interruption-green.xml`: 65 passed, zero failures/errors/skips, 11.812s.
- `parent-report-mutation.xml`: three intended malformed-source diagnostic failures and five positive passes.
- `parent-report-restored.xml`: eight passed.
- The earlier 684-pass integration and 428-pass transfer runs remain evidence for the unchanged scope, not claimed as full-suite r1 verification.

Scoped `git diff --check` exited 0. Diagnostic SHA-256: `81528a1cd12de52963f7dd422f3a8c09eba0652c034ebbf3a9c23adcca8e69c1`. XML SHA-256: `3e34ffb7e4968d53ab7643797da6ec8806c10e19d3e3e264b3381099ea43b36b`.

## Limits

Only scratch diagnostics, this report and clean temporary runner output were written. No production/config/token access, provider calls, dependency installation, restart, commit, subagent or full-suite rerun. No post-r1 changes are covered. The original report and diagnostic/XML are preserved unchanged. Correcting only a future producer does not certify historical damaged or mismatched rows; no migration or disposal is requested by this review.

## Structured Assessment

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-listing-sec-macro-convergence",
    "sourceType": "patch_file",
    "base": "2842c497dabfdb0b13c315e22b206128eba9f57d",
    "head": "Frozen Task1 r1 snapshot in task1r1-review-package.md",
    "changedFiles": [
      "src/api/routes/lifecycle_investigation.py",
      "src/lifecycle_investigation/agent.py",
      "src/lifecycle_investigation/adoption.py",
      "src/lifecycle_investigation/store.py",
      "src/lifecycle_investigation/schema.py",
      "src/lifecycle_investigation/review.py",
      "src/lifecycle_web_store.py",
      "src/lifecycle_web_review.py",
      "src/lifecycle_web_projection.py",
      "src/security_lifecycle_review.py",
      "src/ticker_identity_transition.py",
      "src/ticker_identity_history.py",
      "tests/test_current_investigation_ownership.py",
      "tests/test_lifecycle_investigation_adoption_safety.py",
      "tests/test_lifecycle_investigation_attended_concurrency.py",
      "tests/test_lifecycle_investigation_gaps.py",
      "tests/test_lifecycle_investigation_source_journal.py",
      "tests/test_lifecycle_investigation_usage_journal.py",
      "tests/test_lifecycle_investigation_store.py",
      "tests/test_lifecycle_investigation_review.py",
      "tests/test_lifecycle_investigation_routes.py",
      "tests/test_lifecycle_journal_codec.py",
      "tests/test_lifecycle_source_capacity.py",
      "tests/test_lifecycle_source_context.py",
      "tests/test_lifecycle_source_progress.py",
      "tests/test_lifecycle_source_read_report.py",
      "tests/test_lifecycle_web_attended_concurrency.py",
      "tests/test_lifecycle_web_gaps.py",
      "tests/test_lifecycle_web_read.py",
      "tests/test_lifecycle_web_review.py",
      "tests/test_lifecycle_web_store.py",
      "tests/test_lifecycle_web_usage_journal.py",
      "tests/test_ticker_identity_history.py"
    ],
    "sha256": "acf0fa97fc7c1eedca73d2058548ec0324fd213ff176447089492303a5478e53"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {
    "rating": "high",
    "rationale": "The extraction reaches governed tracking writes, persisted attended receipts, historical explanations and current run readback. The demonstrated defect is bounded to interrupted-run visibility, not an approval bypass."
  },
  "regressionLikelihood": {
    "rating": "high",
    "rationale": "The completed-reply defect is corrected, but two deterministic real-controller proofs still produce unreadable cancelled/failed jobs when reservation fails before a durable call exists."
  },
  "regressionProtection": {
    "rating": "partial",
    "rationale": "The independent r1 run passed all 12 parent ownership nodes, all 10 usage nodes and five new controls, but failed two pre-dispatch reservation readback cases. Earlier integration evidence covers unchanged Task1 paths.",
    "exactHeadChecksPassed": false
  },
  "recoverability": {
    "rating": "managed",
    "rationale": "No Task1 schema migration or data deletion is introduced. A coordinated runtime correction can restore reads of retained rows; full extraction rollback is coupled to Task2 import removal."
  },
  "confidence": {
    "rating": "high",
    "rationale": "All 33 r1 path hashes/absences matched before and after focused execution. The exact completed-observation correction and adjacent reservation mismatch were traced through real agent/controller/store paths."
  },
  "applicability": {
    "status": "confirmed",
    "rationale": "InvestigationController.read/latest call InvestigationStore.read, which now always invokes the changed validator; the current HTTP routes expose these paths."
  },
  "statusQuoRisk": {
    "rating": "moderate",
    "rationale": "The base retains abandoned executable owners and lacks the new step/call binding and diagnostic shape protections. The finding calls for correction, not wholesale removal of these controls."
  },
  "autoMergeExclusions": [
    "privileged_boundary",
    "persistent_state",
    "public_contract",
    "other"
  ],
  "affectedRuntimeRoots": [
    "src/api/routes/lifecycle_investigation.py:208",
    "src/lifecycle_investigation/controller.py:104",
    "src/security_lifecycle_review.py:241",
    "src/ticker_identity_transition.py:885",
    "src/ticker_identity_history.py:175"
  ],
  "importantCallers": [
    "InvestigationController._execute",
    "InvestigationStore.decode_capture",
    "adoption.validated_read",
    "review.confirm",
    "review.investigation_transition_guard",
    "security_lifecycle_review.execute",
    "ticker_identity_history.project_decision"
  ],
  "riskDrivers": [
    "In-memory call reservation increments model_submissions before the durable reservation can fail or observe cancellation.",
    "The new read guard equates in-memory request counts with persisted calls even on failed/cancelled outcomes."
  ],
  "protectiveFactors": [
    "Exact file hash binding and physically removed legacy executable modules.",
    "Real current workflow, concurrency and history assertion coverage.",
    "No source changes or production access during this review.",
    "R1 journals completed bound observations before aggregating replies and checking stop/deadline, without dispatching further work."
  ],
  "materialBoundaries": [
    {
      "id": "completed_observation",
      "invariant": "Completed replies remain durably bound and readable after stop/deadline, with unknown usage preserved and no subsequent work.",
      "runtimeRoot": "run_agent.submit -> InvestigationController.read/latest",
      "counterexample": "Stop/deadline arrives after remote completion; model_result persistence may also fail.",
      "legitimateControl": "agent.py:288-293 calls on_step before replies.append, then check(). Four promoted owners pass, including recording failure; four independent known/unknown stop controls prove no agent_action, web_search or second dispatch.",
      "result": "supported"
    },
    {
      "id": "attended_authority",
      "invariant": "Only the same digest-bound human approval may alter tracking, and reversals retain provenance.",
      "runtimeRoot": "review.confirm and TickerIdentityTransitionStore",
      "counterexample": "Stripped confirmation, changed assessment, changed provider/evidence/profile state, or automation reaches the central writer.",
      "legitimateControl": "Current confirmation, idempotent replay and reversal use retained sla_web_ IDs/web packet keys; current safety owners in the supplied integration XML exercise both directions.",
      "result": "supported"
    },
    {
      "id": "snapshot_binding",
      "invariant": "Owned source decode releases its transaction, and cached material is rechecked inside the caller transaction.",
      "runtimeRoot": "adoption.validated_read/read_on_connection",
      "counterexample": "Source, request-step or call added after validation; wrong database/run or no active transaction.",
      "legitimateControl": "Ordered source/step/call binding plus schema generation rejects changes; DELETE and WAL tests exercise real unrelated writer commits during decoding and finding validation.",
      "result": "supported"
    },
    {
      "id": "historical_material",
      "invariant": "History uses captured execution and approved passages, not today's model registry or fabricated fallback.",
      "runtimeRoot": "ticker_identity_history.project_decision",
      "counterexample": "Missing web binding, wrong lane, changed result digest or re-signed passage URL/time/text.",
      "legitimateControl": "_model validates captured provider/auth and model text without current admission. Approved result/passages digests remain mandatory and missing provenance becomes record_invalid.",
      "result": "supported"
    },
    {
      "id": "observation_shapes",
      "invariant": "Stored gap, usage and source-report observations retain their current contracts.",
      "runtimeRoot": "InvestigationStore.decode_capture",
      "counterexample": "Malformed gaps, duplicate/unbound/noncompleted usage, bool counters, extraneous headers or credential-bearing source URL.",
      "legitimateControl": "The reader is byte-identical to the first frozen package. All four reopened source-report owners and all ten usage owners pass independently at r1, including malformed aggregates and unknown/lost outcomes.",
      "result": "supported"
    },
    {
      "id": "reservation_readback",
      "invariant": "A local reservation that never becomes durable cannot poison terminal job readback or be represented as a remote submission.",
      "runtimeRoot": "InvestigationControl.reserve_model_request -> run_agent.stats -> InvestigationStore.decode_capture",
      "counterexample": "store.py:338 changes the inherited in-memory control first; cancellation at reserve_call or a reservation recording error leaves zero durable calls but saved stats.model_submissions=1. store.py:91 rejects the real saved cancelled/failed result.",
      "legitimateControl": "The identical one-call workflow with successful reservation remains readable. Existing store-level recording-failure owner only observes a still-running job with result=None, so it does not exercise this terminal aggregate.",
      "result": "contradicted"
    }
  ],
  "validation": [
    {
      "name": "task1-r1-review-focused-01.xml: reservation boundary",
      "status": "failed",
      "protects": "Two failures: cancellation after in-memory reservation but before durable reservation, and reservation recording failure; both save terminal jobs that cannot be read."
    },
    {
      "name": "task1-r1-review-focused-01.xml: completed stop controls",
      "status": "passed",
      "protects": "Four independent cancellation/deadline x known/unknown usage controls; one completed model_result, no agent_action/web_search, no second dispatch and no adoption."
    },
    {
      "name": "task1-r1-review-focused-01.xml: parent ownership and usage controls",
      "status": "passed",
      "protects": "12 parent ownership nodes plus 10 current usage nodes, including completed-observation recording failure and malformed/known/unknown/lost usage; one additional normal-reservation control also passes."
    },
    {
      "name": "parent-completed-interruption-green.xml",
      "status": "passed",
      "protects": "Supplied r1 XML inspected, not rerun as a whole: 65 passed, zero failures/errors/skips; includes agent/controller/usage coverage."
    },
    {
      "name": "parent-report-mutation.xml and parent-report-restored.xml",
      "status": "passed",
      "protects": "Supplied source-read inverse evidence inspected: intended three mutated failures/five positive passes, then eight restored passes. The inverse failures are sensitivity evidence, not failures of frozen source."
    },
    {
      "name": "Initial whole-Task1 source review and parent-integration-focused.xml",
      "status": "passed",
      "protects": "All original 11 source/absence hashes are unchanged. Reuses the documented initial source review and inspected 684-pass integration evidence for current imports, approval/reversal, captures, bindings and history; not represented as an r1 full-suite rerun."
    },
    {
      "name": "All 33 r1 path hashes and scoped git diff --check",
      "status": "passed",
      "protects": "Snapshot identity verified before and after execution; original review SHA-256 unchanged; no scoped whitespace errors."
    }
  ],
  "unknowns": [
    {
      "summary": "The transfer specialist was still finalizing removed-node accounting. This review does not certify a completed census or full-suite result.",
      "decisionCritical": false
    },
    {
      "summary": "No production, provider, platform rollout or live-store verification was authorized or performed.",
      "decisionCritical": false
    }
  ],
  "evidencePlan": []
}
```

