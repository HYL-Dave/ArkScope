# Task 1 R3 Independent Review

## Finding

### P2: Web-source cleanup masks a terminal journal failure as cancellation

**Location:** [src/lifecycle_investigation/agent.py:199](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:199), interacting with [read_url cleanup at line 335](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:335).

The new `journal_call` correctly stops control and raises `AgentFailure("investigation_recording_unavailable", None)` when a host callback fails. But a web-source `on_source` or `source_captured` failure exits through `read_url.finally`. After stopping the reader and joining its pool, that block calls `record("source_read", ...)`. Its [line 204 check](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:204) sees the stopped control and raises `WebModelError("stop_requested")`, replacing the original failure.

The new outer `except AgentFailure` cannot preserve an exception already replaced by cleanup. The [generic handler at line 454](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:454) constructs a non-null failed result; [controller.py:175](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/controller.py:175) then stores `cancelled` with `failure_code="stop_requested"`. This loses the host recording error and violates the intended no-result persistence-failure boundary.

**Reproduction:** run the real agent/controller/store with no initial local news, a synthetic completed search returning one public URL, then `read_url`. Fail either `store.source` or the `source_captured` step callback before its actual write or immediately after the real write commits. All four combinations produce:

- Expected: `("failed", "investigation_recording_unavailable", None)`.
- Actual: `("cancelled", "stop_requested", <non-null result>)`.
- `cancel_requested_at is None`; three durable model calls are completed, no extra call is dispatched, the reader is stopped, and source rows reflect the real before/after-commit boundary.

**Proof:** [task1_r3_cleanup_diagnostics.py:18](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r3_cleanup_diagnostics.py:18), `test_web_source_cleanup_preserves_journal_failure`, failing arms `[before_commit-source]`, `[before_commit-source_captured]`, `[after_commit-source]`, `[after_commit-source_captured]`. Both `[none-*]` controls pass, including successful search/read/conclude and cleanup.

**Required correction:** retain resource cleanup while preserving terminal host failures and their no-result boundary. Completed source bookkeeping must not replace the original failure with a dispatch stop check. This does not require weakening stored observation validation or restoring deprecated behavior.

## Verdict

**Revise. One P2 blocker remains.** The direct R2 defects are corrected, but R3 does not yet propagate the same host-failure contract through web-source cleanup. The parent acknowledged this finding and proposed a subsequent correction; that correction is outside this frozen assessment. Further source-dependent probes were paused as requested.

## R3 Controls And Whole-Task1 Scope

- All nine direct callback controls pass: local source, `model_result` and `agent_action`, each with normal acknowledgement and before/after-commit failure. Failures retain readable committed observations, produce no final result and do not redispatch. The local-source owner fails before initial dispatch and does not enter `read_url.finally`.
- All four final-statistics controls pass: completed/pending calls with available/unavailable durable-count reads. There is one read and one model entry; failure leaves a readable no-result terminal. Local budget, stop, selection and terminal polling adds no database reads.
- All four reservation controls pass. Pre-reservation cancellation/failure has zero durable calls and zero tokens; commit/ack loss has one pending call, unknown tokens and `remote_outcome_unknown`. Local budget enforcement and request IDs remain local; no counter rollback or zero-on-read-error fallback.
- Completed model observations still record before reply aggregation and cancellation/deadline checks. Completed cancellation/deadline controls and all ten current known/unknown/lost usage owners pass. Strict reader checks are unchanged.
- Nested search/action `ValueError` handlers do not directly recover `AgentFailure` as model feedback. The concrete failure is the exception replacement in web-source cleanup described above.
- The bounded usage cleanup removes only `phase_usage`, `validate_usage_report`, `project_usage_report` and `USAGE_COVERAGE`. The removed old store was their actual consumer; current source has no remaining live calls. All six retained helper ASTs match base, including `claude_usage_observation`, `token_totals` and `validate_usage_observation`; four absence owners pass.
- Whole-Task1 review carries forward for unchanged paths: physical removal of old store/review/projection, direct current imports, retained `sla_web_` IDs and `web` packet keys, attended approvals/reversals, provider/identity/evidence/freshness checks, atomic writes and idempotency, ephemeral binding including steps/calls, owned capture closing before decode, checked supplied-passage shape, captured historical execution/passages and strict gap/usage/source contracts. No additional blocker was established there. Task2/schema/backup/SEC-foundation work is excluded.

## Exact Evidence

[task1-r3-review-focused-01.xml](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r3-review-focused-01.xml): **45 passed, 4 failed, 15.320s**, zero errors/skips. Passes are 33 parent current ownership cases, ten current usage cases and two scratch normal web controls. The four failures share the single finding above.

```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r3-review-focused-01 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_r3_cleanup_diagnostics.py tests/test_current_investigation_ownership.py tests/test_lifecycle_investigation_usage_journal.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-r3-review-focused-01.xml
```

Evidence SHA-256:
- Six-arm diagnostic: `e3e96c8a9cd0464dc1932fa721c7e2bd5b6c05202c96427cc56072146dcf9d80`.
- Independent XML: `28a82737494b7c92031e2a6d0d6902eacfd6bc9063da71fd981bca99df57119e`.

Supplied XML inspected, not rerun: `parent-finalization-green.xml` has 192 passes, zero failures/errors/skips, 22.067s; `parent-finalization-red.xml` has eight expected failures and 25 passes; `parent-obsolete-usage-red.xml` has four expected absence failures. The independently rerun 33 owners all pass. Scoped `git diff --check` exited 0.

The parent's 51-file complete backend run was reported running, with a stop/refreeze planned after this finding. No completed full-suite result is claimed, and no full suite was run here. Refreshed census accounting is parent-supplied; this review does not re-certify its totals or replace its retained `review_required` classifications.

## Snapshot And Limits

- Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
- Package: `task1r3-review-package.md`; SHA-256 `f49f04ce3d619919b5d162abde820667ac58495b1af5ad9410165f75ce6c7c47`.
- Exact fenced diff: 337161 bytes; SHA-256 `4a9ab77cd266b6e975447b2a202936c38b9fab0c11d24cf37de515fe4c095cc6`.
- All 35 scoped path hashes/absences matched before and after the focused run, before the proposed later correction. R2-to-R3 changes are limited to agent finalization, parent ownership tests and the bounded usage-helper removal.
- Original review remains `f309dac5ee402ae77858f7f45cbbd9bde78b6081dc3e0414f8d28e6897f990af`; R1 remains `f2d919afaf573295d0e45804f4b69374487ee2dfd617968ca1ccd1c5fa8918c1`; R2 remains `6c635a726fa33d05bca65a4e0965c0f997afadb511b12c07ad71a581d88cd6b9`.

Source and product tests stayed read-only. Only scratch diagnostics, their clean offline runner root/XML and this report were written. No production/config/token access, real provider call, install, restart, commit or subagent. No post-R3 fix sign-off is implied.

## Structured Assessment

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-listing-sec-macro-convergence",
    "sourceType": "patch_file",
    "base": "2842c497dabfdb0b13c315e22b206128eba9f57d",
    "head": "Frozen Task1 R3 snapshot in task1r3-review-package.md; proposed later cleanup correction excluded",
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
      "tests/test_ticker_identity_history.py",
      "src/auth_drivers/lifecycle_web_usage.py"
    ],
    "sha256": "4a9ab77cd266b6e975447b2a202936c38b9fab0c11d24cf37de515fe4c095cc6"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {
    "rating": "high",
    "rationale": "The whole extraction reaches governed tracking writes, persistent receipts, historical explanations and current run readback. The remaining demonstrated defect mislabels a host persistence failure as cancellation and saves a synthesized result; no approval bypass is established."
  },
  "regressionLikelihood": {
    "rating": "high",
    "rationale": "Four deterministic before/after-commit web-source failures demonstrate that read_url finally replaces the new no-result AgentFailure with stop_requested."
  },
  "regressionProtection": {
    "rating": "partial",
    "rationale": "All 33 promoted current ownership cases and ten usage cases pass independently. Existing source-callback owners capture local news, so they miss the web reader finally path; four scratch regressions fail while two normal web controls pass.",
    "exactHeadChecksPassed": false
  },
  "recoverability": {
    "rating": "managed",
    "rationale": "Task1 introduces no schema migration. A bounded runtime correction can preserve future terminal truth, but already misclassified runs lack a reliable persisted original error and may require operational review. Full extraction rollback remains coupled to separate Task2 work."
  },
  "confidence": {
    "rating": "high",
    "rationale": "All 35 frozen path hashes/absences match before and after the focused run. The failure is reproduced through the real agent/controller/store with synthetic model and source I/O, and traced through cleanup to the persisted terminal row."
  },
  "applicability": {
    "status": "confirmed",
    "rationale": "The current investigation API starts InvestigationController._execute, which invokes run_agent with store callbacks. Public web-source reads enter the affected read_url finally path; the controller persists its replacement failure."
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
    "journal_call requests stop on a host persistence failure, but read_url finally then calls record, whose check raises stop_requested and masks the intended AgentFailure with result=None.",
    "The outer generic handler synthesizes a result for the replacement error, and the controller persists cancelled despite cancel_requested_at being null."
  ],
  "protectiveFactors": [
    "Exact frozen-path identity, physical removal of legacy executable modules and direct current review imports.",
    "Prior whole-Task1 authority, concurrency, capture and historical-material review remains applicable to unchanged paths.",
    "R3 preserves direct host-callback failures and unavailable statistics as no-result terminal failures, with no redispatch.",
    "Completed observations are durably recorded before aggregation and stop/deadline checks; local budget and durable reservation counters remain separate.",
    "The four orphan two-phase usage members are removed while all six retained helper ASTs remain identical to base.",
    "No runtime/test edits or production/provider access during this independent review."
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
      "legitimateControl": "Reader validation remains unchanged. All four reopened source-report owners and all ten current usage owners pass independently on frozen R3, including malformed aggregates and unknown/lost outcomes.",
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
      "runtimeRoot": "run_agent.stats -> journal_call -> outer AgentFailure handler -> controller",
      "counterexample": "Make the single final durable-count read unavailable after either a completed conclusion or pending reservation.",
      "legitimateControl": "All four promoted completed/pending and available/unavailable cases pass independently: one database read, one model entry, no fabricated result on read failure, readable failed or remote_outcome_unknown terminal. Local polling adds no reads.",
      "result": "supported"
    },
    {
      "id": "completed_observation_ack",
      "invariant": "A committed completed usage observation cannot become an unreadable failed job when acknowledgement is lost.",
      "runtimeRoot": "run_agent.submit -> journal_call -> controller -> InvestigationStore.read",
      "counterexample": "A local source, model_result or agent_action callback raises before its write or after the real write commits.",
      "legitimateControl": "All nine direct callback controls pass independently. Failure produces no final result, preserves committed records, stops additional dispatch, and remains readable. This support does not extend through web read_url cleanup.",
      "result": "supported"
    },
    {
      "id": "web_source_cleanup",
      "invariant": "Host persistence failures stay terminal with their original safe code and no final result while reader resources are closed.",
      "runtimeRoot": "run_agent.read_url finally at agent.py:331 -> record/check -> generic outer handler -> InvestigationController._execute",
      "counterexample": "Fail on_source or source_captured before or after the actual store commit during a searched web-source read. journal_call stops control and raises AgentFailure(code,None); finally record(source_read) raises stop_requested instead. All four arms persist cancelled with a synthesized non-null result, although no cancellation was requested.",
      "legitimateControl": "Both normal web-source controls succeed after four model calls. Failure arms stop after three completed calls, close the reader and preserve the expected committed source rows, isolating terminal exception propagation as the defect.",
      "result": "contradicted"
    },
    {
      "id": "usage_orphan_removal",
      "invariant": "Remove obsolete two-phase report ownership without changing current usage observation or token contracts.",
      "runtimeRoot": "src/auth_drivers/lifecycle_web_usage.py and current agent/store/adapter consumers",
      "counterexample": "A remaining current consumer depends on a removed report helper, or retained observation/token logic changes with the deletion.",
      "legitimateControl": "The removed store was the actual report consumer; scoped source/test references contain no remaining live call. All six retained helper ASTs are identical to base, four absence owners pass and ten current usage-journal owners pass.",
      "result": "supported"
    }
  ],
  "validation": [
    {
      "name": "task1-r3-review-focused-01.xml",
      "status": "failed",
      "protects": "Independent exact-R3 offline run: 49 tests, 45 passed, four failed, zero errors/skips, 15.320s. All four web-source before/after-commit failures lose the original no-result failure in cleanup."
    },
    {
      "name": "All 33 current investigation ownership cases",
      "status": "passed",
      "protects": "Independent R3 run covers physical ownership, four obsolete-helper absences, source-read shapes, completed interruption, direct callback acknowledgement boundaries, one-read statistics failure and durable reservation counts."
    },
    {
      "name": "Ten current usage-journal cases",
      "status": "passed",
      "protects": "Independent R3 run preserves known/unknown/lost usage and rejection of malformed, duplicate, unbound or inconsistent stored observations."
    },
    {
      "name": "Two normal searched web-source controls",
      "status": "passed",
      "protects": "The same synthetic search/read/conclude workflow succeeds, with correct reader closure and source persistence, when callbacks acknowledge normally."
    },
    {
      "name": "parent-finalization-green.xml",
      "status": "passed",
      "protects": "Supplied exact-package evidence inspected, not rerun: 192 passed, zero failures/errors/skips, 22.067s; current owners, agent/controller/store/usage, execution cleanup and 55 shared-control cases."
    },
    {
      "name": "parent-finalization-red.xml and parent-obsolete-usage-red.xml",
      "status": "passed",
      "protects": "Supplied pre-fix sensitivity evidence inspected: eight expected finalization failures with 25 controls passed, and four expected obsolete-helper absence failures."
    },
    {
      "name": "Retained usage helper AST comparison",
      "status": "passed",
      "protects": "All six retained function ASTs match base. Only phase_usage, validate_usage_report, project_usage_report and USAGE_COVERAGE are removed."
    },
    {
      "name": "Whole-Task1 carry-forward and nested-handler trace",
      "status": "passed",
      "protects": "Prior unchanged review/history/capture/authority boundaries remain applicable. Nested recoverable ValueError handlers do not catch AgentFailure directly; the contradicted path is exception replacement by web-source finally."
    },
    {
      "name": "Frozen snapshot, immutable prior reports and scoped diff check",
      "status": "passed",
      "protects": "All 35 path hashes/absences matched before and after the focused run. Original, R1 and R2 reports retain their recorded hashes. Scoped git diff --check exited zero."
    }
  ],
  "unknowns": [
    {
      "summary": "The parent reported a running complete backend suite on 51 frozen files, then planned to stop it for correction. No completion result is claimed. Refreshed census figures are parent-supplied accounting, not independently recomputed in this bounded review.",
      "decisionCritical": false
    },
    {
      "summary": "No production/provider/platform rollout verification was authorized. The proposed post-R3 cleanup fix and six promoted owners have not been reviewed or tested here.",
      "decisionCritical": false
    }
  ],
  "evidencePlan": []
}
```

