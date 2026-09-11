# Task 1 R2 Independent Review

## Findings

### P2: Final statistics read failure re-enters model dispatch

**Location:** [src/lifecycle_investigation/agent.py:204](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:204), the newly fallible `recorded_model_requests` read.

For a valid conclusion, `result("succeeded")` is evaluated inside the recoverable action block at [agent.py:386](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:386). A count-read failure raises `ValueError("investigation_recording_unavailable")`; the inner handler at [agent.py:432](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:432) converts it to feedback and continues the model loop. The controller does not receive an immediate conservative no-result failure.

**Reproduction:** use the real agent/controller/store and a synthetic model returning a valid, completed conclusion. After completion, reject only read connections used for final statistics; writes, local budget/stop polling and the initial capture remain available. The unchanged loop performs **three completed model calls instead of one**, stopping only when repeated-output handling and another failed stats construction finally escape. If the model changes its output, the exact retry count need not be three; the demonstrated three-call case is sufficient.

**Proof:** [task1_r2_stats_diagnostics.py:18](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r2_stats_diagnostics.py:18), node `test_stats_read_failure_preserves_readable_terminal_without_result[True-completed]`. In the corrected run, `len(row["calls"])` is 3, expected 1. A pending-call stats failure does preserve readable `remote_outcome_unknown` with no result; it passes because that failure occurs outside the recoverable action handler.

**Required correction:** finalization/storage-read failures must escape recoverable model-action feedback and reach the existing conservative controller failure path without another dispatch. No zero-count fallback or compatibility mechanism is needed.

### P2: Completed observation commit followed by acknowledgement failure remains unreadable

**Location:** [src/lifecycle_investigation/agent.py:289](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:289), `on_step("model_result", ...)` before `replies.append`.

The durable-count change resolves reservation uncertainty but does not reconcile completed-observation uncertainty. If the step commits and its callback then raises, the saved step contains usage `10/20`, while the reply is absent from the in-memory aggregate. The failed result therefore saves one submission with token totals `None/None`. The unchanged reader derives known totals from the durable step and rejects the job as `investigation_integrity`.

**Reproduction:** wrap `store.step`, invoke the real original step for `model_result`, then raise `investigation_recording_unavailable`. This is the same commit/acknowledgement uncertainty accepted for reservation, applied to the completed observation. No rows or triggers are corrupted, and no extra synthetic remote call is made.

**Proof:** [task1_r2_boundary_diagnostics.py:17](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r2_boundary_diagnostics.py:17), node `test_completed_observation_ack_failure_remains_readable[after_commit]`. Normal completion and failure before the step commits both remain readable and pass.

**Required correction:** reconcile the durably committed usage after uncertain acknowledgement, or avoid manufacturing an inconsistent final result when acknowledgement cannot be established. Preserve strict reader validation and do not append a reply unconditionally after a failed write.

## Verdict

**Revise. Two P2 blockers remain.** The reservation-counter fix itself passes its meaningful controls, including commit-then-ack-loss. Neither remaining finding asks for speculative compatibility or optional feature expansion.

## Counter And Failure Controls

- `RunControl.recorded_model_requests` defaults to the existing local count for non-journal users. Its local budget counter, request IDs, stop state, terminal tracking and enforcement are unchanged.
- `InvestigationControl.recorded_model_requests` opens a verified read connection, verifies the run row and counts only that run's durable calls. A missing run/read failure cannot silently become zero.
- `stats()` reads this property once and uses the same value for submissions and both token completeness checks.
- Before-reservation cancellation/error: zero durable calls, zero submissions, zero tokens, no dispatch. Both promoted owners pass.
- Reservation commit with acknowledgement loss: one pending durable call, unknown tokens, `remote_outcome_unknown`, no dispatch. The promoted positive owner passes; local `_calls` is not rolled back.
- Normal completion and existing partial/unknown/lost usage owners pass. The reader's binding/shape/aggregate checks were not loosened.
- The scratch stats owner polls local budget, stop, selection and terminal properties 32 times with read counting enabled. Those polls perform no database reads. Normal result construction uses one stats read.
- A pending-call stats-read failure leaves a readable terminal job with `result=None`, one durable call and unknown tokens. The completed-conclusion variant fails the no-extra-work condition described above.

## Whole-Task1 Scope

This assessment carries forward the original whole-Task1 review and r1 correction review, then traces the r2 delta through the real agent/controller/store and shared control. It does not treat a passing counter unit test as whole-task sign-off.

The extracted review/history paths retain their earlier checked behavior: old store/review/projection are physically absent; current API/generic review/transition imports are direct; stored `sla_web_` IDs, `web` packet keys and consumed error codes remain contracts; attended approval, provider/identity/freshness/evidence checks, atomic rollback, idempotency and reversal remain guarded; ephemeral material includes steps/calls and is rebound in the writer transaction; owned source capture closes before decode; supplied passages have a checked list-of-strings shape; history uses captured execution and approved passage digests without current model admission or fabricated missing-provenance fallback.

R2 changes only agent statistics, the current durable-count property, the shared default property and parent ownership tests relative to r1. No additional blocker was established in the unchanged review/history/capture boundaries. Task2 work is excluded. The subsequently announced orphan two-phase usage-helper removal and its four absence cases are outside this frozen r2 package and require the next package's review.

## Snapshot Identity

- Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
- Package: `task1r2-review-package.md`; SHA-256 `90c1661a27994f4e5788d59ff032d2d1569c9582df423652b049adbd75d1b41e`.
- Exact fenced diff: 319114 bytes; SHA-256 `b83fad127a729009513cce9e0d7fa1d0a4729b5374e94c2e856c7aa75b7714d1`.
- All 34 scoped path hashes/absences matched at entry. All scoped source hashes still matched after the independent run.
- The later `test_obsolete_two_phase_usage_report_is_absent` addition changes only the parent test file relative to this package. AST comparison found **zero changed frozen test functions**. The new absence owner was not selected for the r2 run. Current parent test hash at that check: `eb2e4d29630d4d6f066a857161ea516e4272503f99fb0d45aeacbaf50a2608f8`.
- Original review unchanged: `f309dac5ee402ae77858f7f45cbbd9bde78b6081dc3e0414f8d28e6897f990af`.
- R1 review unchanged: `f2d919afaf573295d0e45804f4b69374487ee2dfd617968ca1ccd1c5fa8918c1`.

## Exact Evidence

[task1-r2-final-focused-01.xml](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r2-final-focused-01.xml): **19 passed, 2 failed, 7.308s**, zero errors/skips. Passes comprise four promoted reservation controls, ten current usage controls, and five scratch positive controls.

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r2-final-focused-01 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r2_stats_diagnostics.py .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r2_boundary_diagnostics.py tests/test_current_investigation_ownership.py::test_pre_dispatch_reservation_uses_durable_count_and_preserves_unknown_outcome tests/test_lifecycle_investigation_usage_journal.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r2-final-focused-01.xml
```

Evidence hashes:
- Corrected stats diagnostic: `25a212249f8c6000df57a7233cdcafe4693ca04fe3dac9c06d5eb8d1c538feb4`.
- Observation acknowledgement diagnostic: `f214a761c692d5187a039e10eff63b1c9df99ba863b8dcf9741daa8ec83b550f`.
- Final XML: `6f694fb4cec432998e49ef8629108fc24363153ad9f534134b7222827f78401e`.

The first stats attempt, `task1-r2-stats-01.xml` (11 passed, 1 failed), detected a second model call, but a diagnostic assertion inside that call prematurely terminated the retry loop. It is not final failure-path evidence. The corrected owner compares polling read counts locally per invocation and lets the real repeated-action handler run; the final XML above supersedes it.

Supplied evidence inspected, not rerun:
- `parent-reservation-green.xml`: 155 passed, zero failures/errors/skips, 15.010s.
- `parent-reservation-red.xml`: two expected pre-fix failures and two controls passed, 1.741s.
- Earlier 684-pass/428-pass evidence remains limited to its prior frozen runtime, not represented as a complete r2 run.
- The parent's stopped full run at 5299 passes/12 skips is partial and is not completion evidence.

Scoped `git diff --check` exited 0. No full suite was run by this reviewer.

## Limits

Source stayed read-only. Only scratch diagnostics, their clean temporary runner stores/XML and this review were written. No production/config/token access, provider call, dependency install, restart, commit, subagent or source fix. No post-r2 runtime or later helper-removal sign-off is implied.

## Structured Assessment

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-listing-sec-macro-convergence",
    "sourceType": "patch_file",
    "base": "2842c497dabfdb0b13c315e22b206128eba9f57d",
    "head": "Frozen Task1 r2 snapshot in task1r2-review-package.md; later orphan-helper absence owner excluded",
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
      "src/security_lifecycle_web_contract.py",
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
    "sha256": "b83fad127a729009513cce9e0d7fa1d0a4729b5374e94c2e856c7aa75b7714d1"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {
    "rating": "high",
    "rationale": "The extraction reaches governed tracking writes, persisted attended receipts, historical explanations and current run readback. The demonstrated defect is bounded to interrupted-run visibility, not an approval bypass."
  },
  "regressionLikelihood": {
    "rating": "high",
    "rationale": "Two concrete failures remain: final stats-read unavailability causes extra model calls, and committed model_result acknowledgement loss creates unreadable aggregate stats."
  },
  "regressionProtection": {
    "rating": "partial",
    "rationale": "The independent corrected frozen-runtime run has 19 passes and two failures. Reservation/known/unknown controls pass, but successful-finalization stats read failure and completed-observation commit-then-error are not protected by the supplied 155-pass run.",
    "exactHeadChecksPassed": false
  },
  "recoverability": {
    "rating": "managed",
    "rationale": "No Task1 schema migration or data deletion is introduced. A coordinated runtime correction can restore reads of retained rows; full extraction rollback is coupled to Task2 import removal."
  },
  "confidence": {
    "rating": "high",
    "rationale": "All 34 r2 path hashes matched before focused execution; runtime hashes still match afterward. The later test-only orphan absence addition leaves all frozen owner ASTs unchanged. Both failures are deterministic through real current controller/agent/store paths."
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
    "A newly fallible final stats read raises ValueError inside the recoverable action-error handler and re-enters model dispatch.",
    "Durable completed usage may exist even when on_step raises before replies.append; count readback alone cannot reconcile usage."
  ],
  "protectiveFactors": [
    "Exact file hash binding and physically removed legacy executable modules.",
    "Real current workflow, concurrency and history assertion coverage.",
    "No source changes or production access during this review.",
    "R1 journals completed bound observations before aggregating replies and checking stop/deadline, without dispatching further work."
  ],
  "materialBoundaries": [
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
      "invariant": "Local budget reservation and durable submission count are distinct; uncertain committed reservations remain pending/unknown.",
      "runtimeRoot": "InvestigationControl.recorded_model_requests and run_agent.stats",
      "counterexample": "Cancellation or error before durable reservation; commit followed by lost acknowledgement.",
      "legitimateControl": "Four promoted owners pass: zero durable calls yield zero submissions and tokens; committed pending call yields one submission, unknown tokens and remote_outcome_unknown. No local _calls rollback or reader relaxation.",
      "result": "supported"
    },
    {
      "id": "stats_read_failure",
      "invariant": "Unavailable final statistics terminate conservatively without sending more model work.",
      "runtimeRoot": "run_agent.stats -> conclude result construction -> inner ValueError handler",
      "counterexample": "Deny read connections only after a completed valid conclusion. The new count getter raises ValueError, agent.py:432 consumes it as feedback, and the real loop completes three model calls rather than one.",
      "legitimateControl": "Normal final count read succeeds once. Pending-call stats failure escapes to a readable remote_outcome_unknown job with no result. In-memory budget/stop polling performs no reads.",
      "result": "contradicted"
    },
    {
      "id": "completed_observation_ack",
      "invariant": "A committed completed usage observation cannot become an unreadable failed job when acknowledgement is lost.",
      "runtimeRoot": "run_agent.submit -> result stats -> InvestigationStore.decode_capture",
      "counterexample": "Call original store.step for model_result, then raise investigation_recording_unavailable. The durable step has 10/20 tokens but replies remains empty; saved totals are None and the reader rejects them.",
      "legitimateControl": "Ordinary acknowledgement yields known totals; failure before the step commits yields unknown totals and remains readable. Both controls pass.",
      "result": "contradicted"
    }
  ],
  "validation": [
    {
      "name": "task1-r2-final-focused-01.xml",
      "status": "failed",
      "protects": "Corrected exact-runtime diagnostic run: 19 passed, two failed. Failures are three completed model calls on unavailable final stats read and unreadable completed-observation commit-then-error."
    },
    {
      "name": "Four promoted reservation controls",
      "status": "passed",
      "protects": "Normal, cancellation before reservation, reservation failure and reservation commit/ack loss all pass in the independent final run."
    },
    {
      "name": "Ten existing current usage controls",
      "status": "passed",
      "protects": "Independent final run retains known, partial/unknown, lost/failed outcomes and rejection of unbound, duplicate, malformed or wrong aggregate usage."
    },
    {
      "name": "Stats read and acknowledgement positive controls",
      "status": "passed",
      "protects": "Five independent passes: completed/pending normal stats, pending unavailable stats with no result, normal completed observation and pre-commit observation failure."
    },
    {
      "name": "parent-reservation-green.xml",
      "status": "passed",
      "protects": "Supplied XML inspected: 155 passed, zero failures/errors/skips, 15.010s; shared RunControl and current agent/controller/store/usage coverage."
    },
    {
      "name": "parent-reservation-red.xml",
      "status": "passed",
      "protects": "Expected pre-fix sensitivity evidence: two reservation mismatch failures and two controls passed."
    },
    {
      "name": "Original whole-Task1 review, r1 review and unchanged-path evidence",
      "status": "passed",
      "protects": "Physical removal, direct review imports, persisted receipt contracts, attended approval/reversal, captures, step/call binding and captured history reviewed previously and carried forward after identifying the bounded r2 delta."
    },
    {
      "name": "Frozen package and test-owner checks",
      "status": "passed",
      "protects": "All 34 paths matched at entry; source hashes unchanged at exit. Only the user-announced later test-only orphan absence addition differs; frozen owner ASTs are identical. Original reports remain immutable."
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

