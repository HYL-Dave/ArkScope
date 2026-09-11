# Integration Review: R2 And Bounded Usage Supplement

## Findings

**PROVISIONAL / REVISE: two concrete P2 blockers remain in frozen R2. Parent is correcting the shared terminal boundary; R3 review is pending. No additional blocker was found in the other reviewed cross-task interfaces or the bounded usage-helper cleanup.**

### P2: Final Statistics Read Failure Re-Enters Model Dispatch

The newly fallible count read at [agent.py:204](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:204) runs during `result("succeeded")` inside the recoverable action block. Its `ValueError("investigation_recording_unavailable")` is caught as model feedback at [agent.py:432](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:432), allowing another model call instead of terminating conservatively. The now-available Task 1 R2 review and corrected diagnostic demonstrate three completed calls where one is expected. Pending-call and normal-read controls pass.

Existing `task1-r2-final-focused-01.xml` records **2 failed / 19 passed**, with the stats-read retry and completion-acknowledgement cases below as its only failures. Diagnostic/XML hashes match the Task 1 R2 report. This reviewer independently traced the new count read through the inner exception handler; no diagnostic was rerun. Storage/finalization failures must bypass model-correctable feedback without a zero-count fallback.

### P2: Committed Completion Observation Can Disagree With Saved Usage

At [agent.py:289](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:289), `on_step("model_result", ...)` precedes `replies.append(reply)`. If the observation commits but the callback raises before returning, the controller persists the failure result with one durable call and unknown aggregate token totals. The journal nevertheless contains that completed call's known usage. The unchanged [store validator:94](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/store.py:94) expects the recorded totals and rejects the terminal read with `investigation_integrity`.

This is distinct from the now-corrected pre-dispatch reservation mismatch. Existing `task1_r2_boundary_diagnostics.py::test_completed_observation_ack_failure_remains_readable[after_commit]` demonstrates the completion boundary: one dispatch, one completed call, one committed observation with usage 10/20, saved totals None/None, then a failing controller read. Its normal and before-commit controls pass. `task1-r2-boundary-01.xml` contains **1 failed / 2 passed**, no errors/skips. This reviewer inspected the diagnostic and XML and independently traced the frozen source; the diagnostic was not rerun or authored here.

Required correction: reconcile interrupted-completion aggregates with durable observations before publishing the terminal result. Preserve the strict reader, stop-before-further-dispatch behavior, and honest unknown totals when no completed observation was committed. The existing before-commit and after-commit controls must both remain readable. No historical-data migration or speculative compatibility work is requested.

## Exact Identity

- Base/observed HEAD: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
- Subject: `integrationr2-review-package.md`, superseding the original 49-path integration package.
- Package SHA-256: `e5d5c39bd1e093a2c7e123516b4dd43b61e236915ac115df99a629150a62a3ac`.
- Exact embedded diff: **430438 bytes**, SHA-256 `a056cfa2e5fb936ffc024a25c5dd83eb3488e4dab651bdb329468ca7d7265f91`.
- All **50** declared paths initially matched current bytes/absence: 39 present files and 11 deleted entries. The exact path-scoped Git diff matched and `git diff --check` was clean. All five retired module files were separately confirmed absent.
- R2 changes only three earlier entries (`agent.py`, `store.py`, ownership tests) and adds `security_lifecycle_web_contract.py` to scope. Task 1 R2's 34 entries, Task 2 R1's 12 entries and Task 3's five entries matched their respective packages. Other integration-boundary source is unchanged.
- Subsequent parent edits to the ownership tests became visible after the R2 freeze verification. This assessment remains bound to the immutable package, not later edits. The earlier `tested-source-hashes-r1.json` and interrupted full run do not certify R2.

## Integration Checks

| Boundary | Verified Source And Existing Controls |
| --- | --- |
| Deleted owners | AST import check across 680 `src`/`tests` Python files found no imports to the five deleted modules. Production text search also found no retired module names, `web_runs`, `web_review_id` or `web_journal_inventory`. Absence-test strings are not runtime dependencies. |
| Direct confirmation | [Route import:18](/tmp/arkscope-listing-sec-macro-convergence/src/api/routes/lifecycle_investigation.py:18) reaches the new review owner. [Review:157](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/review.py:157) preloads validated material, rechecks its binding in the write transaction, and retains attended consent, idempotency and rollback. Shared review and transition guards import the new owner directly; there is no old-store dispatcher. |
| Packet/history contract | Assessment-ID generation (`sla_web_`), current packet construction including `web` keys, confirmation validation, preview digest function and executable journal schema are AST-identical to base. [Adoption:23](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/adoption.py:23) binds step/call/source material; [history:135](/tmp/arkscope-listing-sec-macro-convergence/src/ticker_identity_history.py:135) reads current journal rows, validates captured execution/passages and never substitutes today's model registry. Invalid provenance becomes unavailable. |
| R2 reservation accounting | [RunControl:190](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_web_contract.py:190) adds only a default recorded-count property. [Current override:331](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/store.py:331) reads the persisted call count; [agent stats:203](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/agent.py:203) samples it once for submissions and token completeness. Local request budgeting remains unchanged. Zero durable calls yields zero tokens; a committed unacknowledged reservation remains one call with unknown outcome/tokens. All four reservation owners pass. |
| Completion versus stop | Completed observations are recorded before reply aggregation and the subsequent stop/deadline check; no new action is dispatched by recording them. The observation validator is AST-identical to R1. Ordinary completion, cancellation, deadline and pre-commit recording-failure owners pass; the post-commit acknowledgement case is the finding above. |
| Actual backup primitive | [Migration:67](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/migration.py:67) and [disposal:240](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:240) import/call [sqlite_backup.py:9](/tmp/arkscope-listing-sec-macro-convergence/src/sqlite_backup.py:9): exclusive destination creation, real `Connection.backup`, explicit destination closure. Approval checks, backup-before-mutation and locked revalidation remain. No obsolete schema facade or trigger disabling is restored. |
| FK identity and current retention | [foreign_keys:65](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:65) resolves declared parents through parameterized catalog lookup with SQLite `NOCASE`, preserving distinct Unicode identifiers and missing-target fallback. Closure, market retention and delete ordering share it; pre-backup and locked checks both consume it. Existing cased-CASCADE/race controls and distinct-Unicode mutations prove the intended semantics. [Current preservation owner:120](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:120) confirms a real investigation, disposes unrelated fixture rows, then verifies identical journal read and `already_applied`. |
| Population and live tool | [Population:467](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_population.py:467) retains assessment/evidence/fact/translation/transition closure and rejects unexpected sealed material. [Current detail:320](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_current.py:320) returns `version/as_of/item`. The service, Research wrapper and [registry:722](/tmp/arkscope-listing-sec-macro-convergence/src/tools/registry.py:722) remain connected. Existing real service/tool equality and dangling-dependency owners pass. |
| SEC foundation only | Configuration uses existing profile snapshot/single-setting APIs; paths use existing market-path authority without creating capture data. Only SEC tests import the new package. No new runtime/tool/schedule registration exists, intentionally. This is not a user-ready SEC workflow. |

## Existing Proof Verified

Counts below were parsed from actual JUnit testcase records, not rerun or summed into a combined-suite result.

| Artifact | Observed Result |
| --- | --- |
| `parent-reservation-red.xml` | 2 failed / 2 passed; cancel-before-reservation and reservation-failure arms fail, normal and committed-reservation acknowledgement-loss controls pass. |
| `parent-reservation-green.xml` | 155 passed, no failures/errors/skips: ownership 16, agent 18, controller 25, usage 10, store 31, shared contract 55. |
| `task1-r2-boundary-01.xml` | 1 failed / 2 passed; completion observation committed before callback failure is the remaining blocker. |
| `task2-r1-final.xml` | 164 passed, including the current-adoption/disposal and registered-tool equality controls inspected above. Task 2 R1 review agrees; its evidence hashes match. |
| `task2-r1-mutation-declared.xml`, `task2-r1-mutation-casefold.xml` | 12 and 2 expected failures respectively. Earlier backup-overwrite and current-detail inverse proofs were also inspected. |
| `task3-green-frozen-12.xml` | 128 passed, no failures/errors/skips; foundation evidence only. |
| `backend-full-before-reservation-fix.xml` | 5299 passed / 12 skipped records; parent explicitly interrupted this R1 run. Not a complete suite and not R2 validation. |

Key evidence SHA-256:
- R2 155-pass XML: `a474bff429f3f7fed1a093eee25f883a8b2f76c89dda726f5c917bedd412512e`.
- Completion-boundary XML: `30ecc5326d89fb8f5de909c77cda1257859b933fc610292280c93a797ac8cd4c`.
- Completion-boundary diagnostic: `f214a761c692d5187a039e10eff63b1c9df99ba863b8dcf9741daa8ec83b550f`.

## Census And Remaining Work

The supplied `census-final-account.json` and compressed census agree on **4309 candidates / 3352 uncertainties**. Both new candidates are the intended SEC foundation modules classified `test_only`, with no entrypoint. All **32** new uncertainty IDs are accounted for as `unchanged_source_relocated`; their mapped source lines were independently compared with the named base locations. `review_required: true` remains truthful.

That census's source manifest is **pre-R2**: its agent, store, shared contract and ownership-test hashes differ from the frozen R2 identities. The supplied counts are verified historical evidence, not a newly generated R2 census. Final source/census reconciliation and exact test-node accounting remain parent-owned; no speculative new counts are asserted.

After both concrete terminal-boundary corrections, final acceptance still needs the corrected frozen identity, affected focused proof, a fresh complete backend run and exact node accounting. Parent reports R3 will follow; this provisional report does not assess that correction. No complete R2 run was available at review time. Prior green scopes do not erase the red boundary proof.

## Bounded Usage Supplement

The user subsequently authorized removal of `phase_usage`, `validate_usage_report`, `project_usage_report` and `USAGE_COVERAGE` from `src/auth_drivers/lifecycle_web_usage.py`, plus four absence cases in the existing ownership-test file. This adds one source path beyond the R2 package, not a new runtime capability.

- `rg` across all source/tests finds these names only in the new absence owner, not in any source consumer. All six retained function source segments (`_counter`, `_counters`, `_sum`, `token_totals`, `claude_usage_observation`, `validate_usage_observation`) are byte-identical to base. Removing the four named definitions leaves all other executable AST unchanged.
- The ownership supplement adds one parameterized function and changes no frozen R2 test function, verified by AST comparison with the packaged test source.
- Existing `parent-obsolete-usage-red.xml`: 4 expected failures. `parent-obsolete-usage-green.xml`: 73 passes, zero failures/errors/skips, including all four absence cases. Neither was rerun here.
- Observed usage file SHA-256: `50d159c4fcab0a4e42eda6a3a884677af16a8d472a25667ab1a3f9db992233ae`; ownership file SHA-256: `eb2e4d29630d4d6f066a857161ea516e4272503f99fb0d45aeacbaf50a2608f8`.
- Exact `git diff --no-ext-diff -U20 <base> -- src/auth_drivers/lifecycle_web_usage.py` SHA-256: `ddf4a64a3ec909c086dd5723d8de97872d410336d7b610868cec595f3df21406`. The supplement is separately identified; it is not misrepresented as part of the unchanged R2 patch hash.
- Nonblocking hygiene: the supplemental `git diff --check` reports a new blank line at EOF in the usage file. No source edit was made by this reviewer. The R2-only whitespace check remains clean.

## Review Limits

This was a bounded independent integration review, not a whole-repository re-audit. Only static source/interface checks, read-only Git/hash checks, structured census inspection and existing XML inspection were performed. The reviewed offline runner was read but not executed. No database was opened, including fixture databases; no source/test/configuration/token file was changed; no provider/network, installation, restart, commit, subagent or test execution was performed. Only this scratch report was written.

## Structured Assessment

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-listing-sec-macro-convergence",
    "sourceType": "patch_file",
    "base": "2842c497dabfdb0b13c315e22b206128eba9f57d",
    "head": "Frozen integrationr2-review-package.md, package SHA-256 e5d5c39bd1e093a2c7e123516b4dd43b61e236915ac115df99a629150a62a3ac; subsequent edits excluded",
    "changedFiles": [
      "src/api/routes/lifecycle_investigation.py",
      "src/lifecycle_investigation/adoption.py",
      "src/lifecycle_investigation/agent.py",
      "src/lifecycle_investigation/disposal.py",
      "src/lifecycle_investigation/migration.py",
      "src/lifecycle_investigation/review.py",
      "src/lifecycle_investigation/schema.py",
      "src/lifecycle_investigation/store.py",
      "src/lifecycle_web_migration.py",
      "src/lifecycle_web_projection.py",
      "src/lifecycle_web_schema.py",
      "src/lifecycle_web_store.py",
      "src/sec_research/__init__.py",
      "src/sec_research/config.py",
      "src/sec_research/paths.py",
      "src/security_lifecycle_current.py",
      "src/security_lifecycle_population.py",
      "src/security_lifecycle_review.py",
      "src/security_lifecycle_web_contract.py",
      "src/sqlite_backup.py",
      "src/ticker_identity_history.py",
      "src/ticker_identity_transition.py",
      "tests/test_current_investigation_ownership.py",
      "tests/test_lifecycle_investigation_adoption_safety.py",
      "tests/test_lifecycle_investigation_attended_concurrency.py",
      "tests/test_lifecycle_investigation_gaps.py",
      "tests/test_lifecycle_investigation_retirement.py",
      "tests/test_lifecycle_investigation_review.py",
      "tests/test_lifecycle_investigation_routes.py",
      "tests/test_lifecycle_investigation_source_journal.py",
      "tests/test_lifecycle_investigation_store.py",
      "tests/test_lifecycle_investigation_usage_journal.py",
      "tests/test_lifecycle_journal_codec.py",
      "tests/test_lifecycle_source_capacity.py",
      "tests/test_lifecycle_source_context.py",
      "tests/test_lifecycle_source_progress.py",
      "tests/test_lifecycle_source_read_report.py",
      "tests/test_lifecycle_web_attended_concurrency.py",
      "tests/test_lifecycle_web_gaps.py",
      "tests/test_lifecycle_web_migration.py",
      "tests/test_lifecycle_web_read.py",
      "tests/test_lifecycle_web_review.py",
      "tests/test_lifecycle_web_store.py",
      "tests/test_lifecycle_web_usage_journal.py",
      "tests/test_sec_research_config.py",
      "tests/test_sec_research_paths.py",
      "tests/test_security_lifecycle_current.py",
      "tests/test_security_lifecycle_population.py",
      "tests/test_sqlite_backup.py",
      "tests/test_ticker_identity_history.py"
    ],
    "sha256": "a056cfa2e5fb936ffc024a25c5dd83eb3488e4dab651bdb329468ca7d7265f91"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {
    "rating": "high",
    "rationale": "The combined patch touches persistent confirmation/history contracts and explicit database disposal; the identified P2 affects terminal-job readability, not unauthorized adoption or demonstrated data deletion."
  },
  "regressionLikelihood": {
    "rating": "high",
    "rationale": "Two demonstrated terminal-boundary defects remain in frozen R2: final statistics failure can dispatch more model work, and post-commit completion acknowledgement can make saved usage inconsistent. R3 correction is pending."
  },
  "regressionProtection": {
    "rating": "partial",
    "rationale": "Supplied R2 155-pass proof covers reservation interruptions and shared controls but not post-commit completion acknowledgement; that separate diagnostic fails. No complete R2 backend result exists.",
    "exactHeadChecksPassed": false
  },
  "recoverability": {
    "rating": "managed",
    "rationale": "Producer correction requires a new frozen snapshot and rerun of affected owners; source rollback alone does not establish recovery for any already persisted mismatched result. No actual-store recovery is assessed or authorized."
  },
  "confidence": {
    "rating": "moderate",
    "rationale": "Exact frozen diff and source hashes were verified and the failure was traced independently. Runtime evidence is existing XML, not a new execution by this reviewer; subsequent source/test edits are excluded."
  },
  "applicability": {
    "status": "confirmed",
    "rationale": "The current controller, store, review routes, transition writer, history projection and registered current-review tool directly consume the changed interfaces."
  },
  "statusQuoRisk": {
    "rating": "unknown",
    "rationale": "This bounded integration review does not assess production state or a complete not-merging scenario."
  },
  "autoMergeExclusions": [
    "migration",
    "persistent_state",
    "public_contract",
    "other"
  ],
  "affectedRuntimeRoots": [
    "src/api/routes/lifecycle_investigation.py",
    "src/lifecycle_investigation/controller.py",
    "src/lifecycle_investigation/migration.py",
    "src/lifecycle_investigation/disposal.py",
    "src/security_lifecycle_review.py",
    "src/ticker_identity_transition.py",
    "src/ticker_identity_history.py",
    "src/tools/security_lifecycle_tools.py:get_security_lifecycle_review"
  ],
  "materialBoundaries": [
    {
      "id": "finalization-no-dispatch",
      "invariant": "Host final-statistics read failures terminate without further model work.",
      "runtimeRoot": "agent.result -> agent.stats -> recoverable action handler",
      "counterexample": "Corrected task1-r2-final-focused-01.xml completed/stats-unavailable case performs three completed calls instead of one because the read ValueError becomes model feedback.",
      "legitimateControl": "Normal read and pending-call read-failure controls preserve one call; no zero-count fallback is required.",
      "result": "contradicted"
    },
    {
      "id": "completion-observation",
      "invariant": "A failed terminal job remains readable when a completed observation was committed before acknowledgement failed.",
      "runtimeRoot": "InvestigationController._execute/read -> agent.stats -> InvestigationStore.decode_capture",
      "counterexample": "task1-r2-boundary-01.xml after_commit: one completed call and a committed model_result with usage 10/20, but saved totals None/None; read raises investigation_integrity.",
      "legitimateControl": "The same diagnostic's normal and before_commit arms pass; reader validation must remain strict.",
      "result": "contradicted"
    },
    {
      "id": "reservation-count",
      "invariant": "Saved submissions and token completeness use durable calls without relaxing the local dispatch budget.",
      "runtimeRoot": "RunControl / InvestigationControl -> agent.stats",
      "counterexample": "Cancellation or reservation failure before INSERT leaves a local reservation but zero durable calls; a lost acknowledgement after INSERT leaves one durable unresolved call.",
      "legitimateControl": "All four frozen reservation owners pass: zero durable work has zero totals, committed unresolved work remains unknown, and ordinary completed work retains known usage.",
      "result": "supported"
    },
    {
      "id": "current-approval-history",
      "invariant": "Current direct owners retain bound human approval and captured history without obsolete journal dispatch.",
      "runtimeRoot": "lifecycle_investigation.review -> security_lifecycle_review / ticker_identity_transition / ticker_identity_history",
      "counterexample": "Changed request/call/source binding or missing packet-bound provenance must not become approval or a fabricated explanation.",
      "legitimateControl": "Direct imports and transactional binding remain; assessment ID and packet construction, confirmation validation and journal schema match base AST. History uses captured execution and fails unavailable for invalid binding.",
      "result": "supported"
    },
    {
      "id": "backup-retention",
      "invariant": "Shared backup remains exclusive and current/unknown references survive unrelated approved disposal.",
      "runtimeRoot": "migration.apply_installation / disposal.apply_disposal_stage",
      "counterexample": "Existing destination or upper/mixed-case external CASCADE target, including a dependency arriving after preview or backup.",
      "legitimateControl": "Both consumers call actual SQLite backup; all FK consumers resolve catalog identity with NOCASE. Supplied 164-pass scope includes cross-task current confirmation preservation, race controls and distinct Unicode targets.",
      "result": "supported"
    },
    {
      "id": "current-tool",
      "invariant": "Removing obsolete population projection does not remove the registered current-review read.",
      "runtimeRoot": "registry -> get_security_lifecycle_review -> SecurityLifecycleReadService.get_current_review",
      "counterexample": "Reintroducing web_runs or accepting unexpected sealed manifest material violates the current result/material shape.",
      "legitimateControl": "Live registry function reaches version/as_of/item; strict material equality and current reference closure remain, with supplied service/tool and malformed-material controls.",
      "result": "supported"
    },
    {
      "id": "sec-foundation",
      "invariant": "SEC config/path foundation does not activate an incomplete workflow.",
      "runtimeRoot": "src/sec_research/config.py and paths.py",
      "counterexample": "Treating NULL as absent, changing path authority, or adding runtime registration would exceed the foundation contract.",
      "legitimateControl": "Existing profile snapshot/set_setting and market resolver APIs are used; only the two SEC test modules import the package. Supplied foundation evidence records 128 passes.",
      "result": "supported"
    }
  ],
  "validation": [
    {
      "name": "Frozen R2 identity and import/interface checks",
      "status": "passed",
      "protects": "50 hashes/absences initially matched; exact 430438-byte diff matched; five retired modules absent; no retired imports in 680 parsed source/test files. Unchanged task scopes matched their own packages."
    },
    {
      "name": "parent-reservation-green.xml",
      "status": "passed",
      "protects": "Existing evidence parsed: 155 passes, including all four reservation owners and shared RunControl tests. Not rerun."
    },
    {
      "name": "task1-r2-boundary-01.xml",
      "status": "failed",
      "protects": "Existing evidence parsed: after_commit fails with investigation_integrity; normal and before_commit pass. Source flow independently traced."
    },
    {
      "name": "Task 2 R1 and Task 3 existing proof",
      "status": "passed",
      "protects": "164 and 128 passing records; actual cross-interface assertions inspected. Not claimed as full combined R2 execution."
    },
    {
      "name": "Complete R2 backend and exact node account",
      "status": "unavailable",
      "protects": "Parent-owned work pending. Interrupted prior run has 5299 passes and 12 skips, not a complete R2 result."
    },
    {
      "name": "Supplied pre-R2 census account",
      "status": "passed",
      "protects": "4309 candidates, 3352 uncertainties, two foundation/test-only additions and 32 unchanged-source relocation mappings verified; this is not a fresh R2 census."
    },
    {
      "name": "task1-r2-final-focused-01.xml",
      "status": "failed",
      "protects": "Existing corrected proof: 19 passes and two failures, stats-read extra dispatch and post-commit completion acknowledgement. Diagnostic/XML hashes match the Task 1 R2 report."
    },
    {
      "name": "Bounded usage-helper supplement",
      "status": "passed",
      "protects": "Four unused symbols removed, no remaining source consumers, six surviving helpers byte-identical, unchanged prior test functions; existing RED 4 failures and GREEN 73 passes. Not part of the frozen R2 patch identity."
    }
  ],
  "unknowns": [
    {
      "summary": "Parent is correcting both terminal-boundary failures; R3 frozen identity, focused proof, complete backend result and exact node accounting remain pending.",
      "decisionCritical": true
    },
    {
      "summary": "The supplied census source manifest predates four R2 file identities and needs final-source reconciliation, without inventing new counts.",
      "decisionCritical": true
    },
    {
      "summary": "Existing JUnit was inspected rather than independently rerun; actual databases and production recovery were intentionally not inspected.",
      "decisionCritical": false
    }
  ],
  "evidencePlan": []
}
```
