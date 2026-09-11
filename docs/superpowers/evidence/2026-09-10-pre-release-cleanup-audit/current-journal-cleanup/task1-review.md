# Task 1 Independent Spec And Quality Review

## Findings

### P2: Valid interrupted jobs become unreadable after a completed reply

**Location:** [src/lifecycle_investigation/store.py:94](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/store.py:94), specifically the aggregate comparison at lines 94-98.

The new validator assumes every reply counted in saved token totals already has a durable `model_result` step. The real agent does not make those operations atomic: [agent.py:287](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:287) appends the reply first, then `record()` checks cancellation/deadline before writing the step. A normal interruption at this boundary saves an `AgentFailure.result` or incomplete result through [controller.py:175](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/controller.py:175).

**Reproduction:** the scratch diagnostic runs the real current agent, controller, journal and local-news fixture with a synthetic model transport. Immediately after the model's completed terminal is durable, either call the real `service.cancel(control.run_id)` or advance the injected monotonic clock beyond the run deadline, then return the completed reply. No row damage, trigger bypass or source monkeypatch is involved.

Both jobs finish and retain:
- One durable call: `("step-1", "completed")`.
- Zero `model_result` steps.
- Saved stats: `model_submissions=1, input_tokens=10, output_tokens=20`.
- Job status `cancelled` or `incomplete`, respectively.

The validator calculates expected totals as `None` and raises `ValueError("investigation_integrity")` instead of returning that truthful terminal state. The diagnostic fails at the actual controller read. Reopened store reads and the latest-job route share the same failing path ([controller.py:104](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/controller.py:104), [routes:208](/tmp/arkscope-listing-sec-macro-convergence/src/api/routes/lifecycle_investigation.py:208)). This affects real current interrupted work, not deprecated compatibility. The base current reader decoded these records without this new rejection.

**Proof:** [task1_review_diagnostics.py:16](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_review_diagnostics.py:16), nodes `test_completed_reply_interruption_remains_readable[cancel]` and `[deadline]`. [task1-review-interruption-01.xml](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-review-interruption-01.xml): **2 failed, 1 passed, 1.49s**. The otherwise identical uninterrupted conclusion passes.

**Required correction:** make durable observation accounting and interrupted readback agree. Preserve visibility of the terminal job, treating unbound usage as unavailable where necessary; retain the completed-call, uniqueness, shape and fully recorded aggregate integrity checks. Add these interruption-boundary owners. Simply disabling observation validation would discard useful transferred protection.

## Verdict

**Revise.** One P2 blocker to Task1 sign-off. No additional blocker was established in the bounded review of the extracted current review/history/capture paths. The observed impact is loss of interrupted-run readback, not an approval bypass or destruction of the stored job.

## Scope And Identity

- Repository: `/tmp/arkscope-listing-sec-macro-convergence`.
- Base: `2842c497dabfdb0b13c315e22b206128eba9f57d`; head is the frozen uncommitted Task1 package.
- Package: `task1-review-package.md`, SHA-256 `afc891beca211511c8141c7a08dfb39fab82b1e5e00083284a8005201994a50a`.
- Exact fenced diff bytes: 302783 bytes; SHA-256 `6b3b7ee9a00bfee029d59c587433ee68689e882d827355acc3a9908a0dc33ca3`.
- All 32 initial path hashes/absences matched at entry. All 11 source path hashes/absences still match at closeout.
- The only later mismatch is the user-announced addition to `tests/test_current_investigation_ownership.py`. Its added block at lines 21-46 was read. Current SHA-256: `c1c01709bef13098318da9904a0877bf93fe207e2dfddf6a7ecde8793d568628`. It is supplemental evidence, not silently attributed to the original package hash.
- Task2 schema/backup/disposal/population/FK work was excluded. No deprecated journal, migration or compatibility behavior is requested.

## Concrete Checks

| Boundary | Checked behavior |
| --- | --- |
| Physical ownership | Old store/review/projection paths are absent; no active source imports of them remain. API, generic review and transition writer import the current review owner directly. |
| Approval and reversal | Current `sla_web_` assessment IDs, packet `web` keys and consumed error contracts remain. Provider veto/freshness/adoption-value/ID helpers match base AST evidence. Confirmation still rechecks permissions, current identity/provider/evidence/profile state, literal gap acknowledgement and the central attended-only writer. Existing current safety owners cover atomic rollback, idempotency, scheduled recheck and reversal with retained provenance. |
| Ephemeral binding | `adoption.py:23` includes ordered source hashes, ordered step identity/kind/hashes, calls with remote/terminal state, job status and schema generation. `on_connection` checks exact type, database path, run and active transaction. Added-step/call/source counterexamples are represented in the inspected integration XML. |
| Owned capture | `validated_read` and `InvestigationStore.read` close owned connections before source JSON decode/finding validation. Caller-owned reads do not close the caller's transaction. The 20 DELETE/WAL prepare/confirm/execute/generic-command test arms assert an actual unrelated writer commit during expensive work. |
| Current model context | `as_adoption` requires `supplied_passages` to be a list of strings before set conversion, matches the last request/output/completed call, revalidates citations and compares the validated result. Empty/wrong/malformed context is not accepted as proof. |
| Historical provenance | `ticker_identity_history.py:126` uses captured provider/auth/model text without current registry admission. Header, result and approved passage digests remain checked. Missing/null `web`, wrong lane or unbound result goes to `record_invalid`, not a manual explanation; re-signed passage URL/time/text owners exercise this. Provider history still resolves captured evidence, not the latest provider lookup. |
| Observation contracts | Gaps use strict shape, safe reason codes, current corpus choices and canonical URLs. Usage checks bind each unique result to a completed call and remote ID, validate counters/observations and compare totals. Source reports use the existing structured validator. The new four-case reopened-source owner now tests legitimate reports versus boolean counts, extraneous headers and credential URLs at the store read boundary. The interruption finding above is the missing legitimate control. |

## Verification Evidence

Existing results were inspected as evidence, not rerun or treated as independent proof of correctness:
- `parent-integration-focused.xml`: 684 tests, zero failures/errors/skips, 98.454s. Confirmed named current approval, reversal, source, usage, binding and historical-passage owners are present.
- `task1-tests-final-verification.xml`: 428 tests, zero failures/errors/skips, 83.155s. Parsed the XML directly even though the transfer narrative was still being finalized.
- The four-case late ownership addition and its inverse plugin were source-reviewed only / not executed by this reviewer. The earlier source-report helper tests alone did not own the new store branch.
- Scoped `git diff --check 2842c497 -- <Task1 source paths>` exited 0.

Independent targeted command, run once from the worktree:
```bash
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-review-interruption-01 /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/offline_pytest.py -q .superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1_review_diagnostics.py --junitxml=.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task1-review-interruption-01.xml
```

Diagnostic SHA-256: `4b104027da65480bb0b08024962c1948150c49ef928b837834007c2a82df27cc`.
Diagnostic XML SHA-256: `b5d0cccdf63ab380b50851657ae3093bd1b32fa4c9f24eb78cf1dd5c8fdea097`.

## Limitations And Risk

Source remained read-only. Writes were confined to this scratch review, the scratch diagnostic and its clean runner output/root. No full-suite rerun, production/config/token access, provider call, dependency install, restart, commit or subagent was performed. Test fixtures used only synthetic credentials and temporary databases through the existing offline runner.

The broad extraction's impact-if-wrong is high because it touches governed persistent receipts and public read contracts; protection is partial despite useful existing integration coverage. The concrete regression is reproducible, with high confidence. Recovery is managed: rows remain intact and Task1 changes no schema, but reverting the entire extraction would require coordination with Task2's removed imports. The final removed-node census was not certified here, and no post-fix/r1 source is covered.

## Structured Assessment

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-listing-sec-macro-convergence",
    "sourceType": "patch_file",
    "base": "2842c497dabfdb0b13c315e22b206128eba9f57d",
    "head": "Frozen Task1 snapshot in task1-review-package.md; later ownership-test-only addition reviewed separately",
    "changedFiles": [
      "src/api/routes/lifecycle_investigation.py",
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
    "sha256": "6b3b7ee9a00bfee029d59c587433ee68689e882d827355acc3a9908a0dc33ca3"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {
    "rating": "high",
    "rationale": "The extraction reaches governed tracking writes, persisted attended receipts, historical explanations and current run readback. The demonstrated defect is bounded to interrupted-run visibility, not an approval bypass."
  },
  "regressionLikelihood": {
    "rating": "high",
    "rationale": "Two deterministic real-agent/controller tests reproduce unreadable current jobs after ordinary cancellation or deadline expiry."
  },
  "regressionProtection": {
    "rating": "partial",
    "rationale": "Existing XML and assertion inspection cover adoption, reversals, binding, writer availability and malformed observations, but miss completion-before-result-step interruption. The independent three-case proof has two failures.",
    "exactHeadChecksPassed": false
  },
  "recoverability": {
    "rating": "managed",
    "rationale": "No Task1 schema migration or data deletion is introduced. A coordinated runtime correction can restore reads of retained rows; full extraction rollback is coupled to Task2 import removal."
  },
  "confidence": {
    "rating": "high",
    "rationale": "All 11 scoped source/absence hashes match the immutable package. The only later mismatch is the explicitly supplied ownership-test addition. Failure is reproduced with stock agent/store/controller and synthetic transport, not damaged rows."
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
    "Aggregate checks assume in-memory reply accounting and durable model_result append are atomic.",
    "Current persisted IDs and packet keys also identify privileged attended decisions."
  ],
  "protectiveFactors": [
    "Exact file hash binding and physically removed legacy executable modules.",
    "Real current workflow, concurrency and history assertion coverage.",
    "No source changes or production access during this review."
  ],
  "materialBoundaries": [
    {
      "id": "interrupted_readback",
      "invariant": "Ordinary interrupted current jobs remain readable without inventing successful work.",
      "runtimeRoot": "InvestigationController.read/latest",
      "counterexample": "Agent appends a completed reply to replies, then cancellation/deadline prevents record(model_result). Saved totals are 10/20 with one completed call and zero model_result steps. store.py:94-98 rejects the stock result.",
      "legitimateControl": "The same one-call conclusion without interruption saves its model_result and reads successfully.",
      "result": "contradicted"
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
      "legitimateControl": "Canonical URLs, token_totals, validate_usage_observation and validate_source_read_report validate the read path. The late four-case ownership addition explicitly exercises the source_read branch; its execution was not rerun by this reviewer.",
      "result": "supported"
    }
  ],
  "validation": [
    {
      "name": "task1-review-interruption-01.xml: cancel and deadline",
      "status": "failed",
      "protects": "Readable current terminal jobs at the remote-completion/local-step persistence boundary; two reproducible failures."
    },
    {
      "name": "task1-review-interruption-01.xml: none",
      "status": "passed",
      "protects": "Uninterrupted real current conclusion and reopened readback; one positive control."
    },
    {
      "name": "parent-integration-focused.xml",
      "status": "passed",
      "protects": "Supplied XML inspected, not rerun: 684 tests, zero failures/errors/skips, including named current source/adoption/history guards."
    },
    {
      "name": "task1-tests-final-verification.xml",
      "status": "passed",
      "protects": "Supplied XML inspected, not rerun: 428 tests, zero failures/errors/skips. Does not include the new review diagnostics."
    },
    {
      "name": "Task1 source hashes and scoped git diff --check",
      "status": "passed",
      "protects": "All scoped source contents/absences still match the package; no scoped whitespace errors."
    },
    {
      "name": "Late four-case reopened source-report ownership addition",
      "status": "skipped",
      "protects": "Source reviewed at c1c01709bef13098318da9904a0877bf93fe207e2dfddf6a7ecde8793d568628; this reviewer did not run it or its inverse plugin."
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

