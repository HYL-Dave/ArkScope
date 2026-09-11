# Task 2 Independent Spec And Quality Review

## Finding

**[P1 / High] Differently cased FK targets bypass the required external-reference retention guard.**

Locations: [disposal.py:96](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:96), [disposal.py:148](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:148).

`foreign_keys()` preserves the declared target spelling from `PRAGMA foreign_key_list`. `closure()` compares that spelling to the visited table with case-sensitive Python equality; `market_dependency()` similarly uses case-sensitive set membership. An unrelated child declared with `REFERENCES SECURITY_LIFECYCLE_CASES(case_id) ON DELETE CASCADE` is consequently missed, although SQLite resolves it to the actual lowercase parent. The same problem affects `SECURITY_LIFECYCLE_OBSERVATIONS(id)` on the market side.

The profile path is `preview_disposal -> closure -> profile_scope`, followed by the same ineffective revalidation in `apply_disposal_stage` and the parent DELETE at [disposal.py:247](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:247). On the market path, both preview and `market_scope` miss the dependency before the DELETE at [disposal.py:252](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:252). A cascade can delete the unrelated retained child, leaving `PRAGMA foreign_key_check` clean. Approval digests and repeated checks do not repair an incomplete dependency selection.

**Attribution:** reproduced against both exact base `2842c497` and the frozen Task 2 source. This is a pre-existing named cross-call risk, not a regression introduced by Task 2. It is reported because generic external-FK blocking is an explicit review requirement and Task 2 acceptance invariant. No other Task 2-introduced defect was identified.

Resolve FK target names to canonical SQLite table identities before equality/ownership checks. Add upper/mixed-case external-reference controls, including `ON DELETE CASCADE`, for both profile and market paths. Keep this within the generic guard; do not restore old-web ownership or writer/schema fixtures. No fix was applied during review.

## Verdicts

- **Spec Compliance: NOT FULLY COMPLIANT.** The explicitly required generic external-FK retention guarantee has the confirmed exception above. The other scoped Task 2 requirements are satisfied by the inspected source and evidence.
- **Task Quality: CHANGES REQUESTED for the named retention boundary.** This is not a finding that the Task 2 diff introduced the defect, nor a whole-branch verdict. The recorded green suite covers the lowercase control but does not establish the generic guarantee.

## Exact Review Identity

- Repository: `/tmp/arkscope-listing-sec-macro-convergence`.
- Base and observed HEAD: `2842c497dabfdb0b13c315e22b206128eba9f57d`.
- Subject: frozen uncommitted Task 2 snapshot, bound by `task2-review-package.md`, not a new commit. Neighboring task changes were not treated as Task 2 changes.
- Package SHA-256: `6d9dc5f89c13a6a3419732165f33d324517b3a34592d9a177944526cfe424e17`.
- Exact embedded diff payload SHA-256: `e8a4c3621713330ca0e0b54be17c59d9adbbee5d6af950b86b25f21ed4c071a9`.
- All 12 manifest entries matched: nine present-file hashes and three required absences. The scoped `git diff --no-ext-diff --unified=20 2842c497` matched the packaged diff. Scope: 279 insertions, 390 deletions.

## Spec And Boundary Checks

Read the plan's Global Constraints and Task 2, spec sections 4/9/11, and the recorded schema-ownership checkpoint. The checkpoint's seven absent old-web tables are the supplied retention boundary, not a new production observation. No hypothetical old-web data migration is required here.

| Requirement | Result and inspected owner |
| --- | --- |
| Remove old schema, installer and writers | PASS within this task boundary. The old schema/installer and exclusive migration test file are physically absent. Exact obsolete-owner/SQL scans of `src` and `tests` found only the two negative-test declarations, no remaining runtime references. Task 1's store/review/projection deletions are neighboring work, not independently certified here. |
| Shared create-exclusive, WAL-safe backup with explicit close | PASS. [sqlite_backup.py:9](/tmp/arkscope-listing-sec-macro-convergence/src/sqlite_backup.py:9) uses `O_CREAT | O_EXCL`, mode 0600, SQLite connection backup, and `closing()` for the destination. Both current consumers call it directly. The source connection is not closed. |
| Preserve installation approval, backup and rollback | PASS. [migration.py:52](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/migration.py:52) retains stopped-App and same-path rejection, approval matching, backup readback, locked revalidation, existing-data snapshots, rollback and idempotency. |
| Exact disposal ownership and current retention | PASS for the ownership change; generic blocker exception is the finding. [disposal.py:21](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/disposal.py:21) removes old-web ownership while excluding provider checks and migration receipts. No old trigger disabling remains. Human assessments and current acceptance/transition references remain protected on correctly resolved edges; current acceptance FK is at [schema.py:35](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/schema.py:35). No shared table schema is dropped. |
| Closed population material | PASS. [security_lifecycle_population.py:527](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_population.py:527) requires exactly five material keys and rejects even a resealed obsolete inventory field. Old inventory capture and retention projection are removed. |
| Preserve current reference/digest closure | PASS for this diff. [security_lifecycle_population.py:467](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_population.py:467) retains assessment/evidence/fact/translation checks; [security_lifecycle_population.py:383](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_population.py:383) retains transition/proposal/receipt validation. The manifest remains non-authorizing with no deletion candidates. |
| Keep live model-tool detail/list | PASS. [security_lifecycle_current.py:320](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_current.py:320) still returns `version/as_of/item`; only `web_runs` and its obsolete error/import path disappear. Service at [security_lifecycle_tools.py:1038](/tmp/arkscope-listing-sec-macro-convergence/src/tools/security_lifecycle_tools.py:1038), Research wrapper at [security_lifecycle_tools.py:1338](/tmp/arkscope-listing-sec-macro-convergence/src/tools/security_lifecycle_tools.py:1338), and registry at [registry.py:722](/tmp/arkscope-listing-sec-macro-convergence/src/tools/registry.py:722) remain wired. Listing/history/source checks are unchanged by this diff. |
| Preserve current persisted keys and evidence owners | Task 2 does not rewrite `sla_web_` identities, current packet `web` fields, source captures, confirmation/reversal data, or their retained error contracts. End-to-end extraction ownership remains Task 1's review. |

The backup counterexamples are an existing destination, dangling symlink, committed WAL-only row, and backup failure. The inspected tests observe those properties directly, including that a main-file-only read misses the WAL row while the SQLite backup contains it. Installation/disposal controls also observe unrelated populated data, post-preview changes, receipt failure rollback and retry. These are behavioral owners, not merely absence tests.

## Actual Checks And Evidence

This review did **not** rerun pytest or the suite. Implementer prose was not accepted as proof: existing XML was parsed with `xml.etree.ElementTree`, actual testcase outcomes/node sets were counted, and all eight XML SHA-256 values matched the report.

| Artifact | Actual testcase records |
| --- | --- |
| `task2-baseline.xml` | 138 passed |
| `task2-red.xml` | 10 failed, 11 passed; assertion-based failures, no collection/import errors |
| `task2-green.xml` | 149 passed |
| `task2-final.xml` | 149 passed; same node set as GREEN |
| `task2-mutation-overwrite.xml` | 1 failed: expected `FileExistsError` not raised |
| `task2-mutation-external-fk.xml` | 2 failed: external child admitted into disposable roots; changed-preview path reached FK `IntegrityError` rather than preflight rejection |
| `task2-mutation-closure.xml` | 2 failed: destination remained queryable on both success/failure paths |
| `task2-mutation-detail.xml` | 2 failed: unexpected `web_runs` in service and actual Research-tool results |

All artifacts have zero skips, zero error records and no duplicate node IDs. Baseline-to-final accounting is seven removed, eighteen added, net +11. The exact removed/added sets agree with `task2-report.md`. Final per-file counts are backup 12, population 70, current 44, policy rollover 9, retirement 11, current migration 3.

Inspected owner transfers: six obsolete migration nodes transfer still-current backup/installation guarantees to `test_sqlite_backup.py`, with before-backup approval rejection retained in unchanged `test_lifecycle_investigation_migration.py:21`; the old-web atomic-deletion node becomes shared evidence/fact rollback at [test_lifecycle_investigation_retirement.py:181](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:181). Existing population translation, dangling-evidence and corrupt-receipt assertions remain. The new external-child test at [test_lifecycle_investigation_retirement.py:51](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:51) uses lowercase FK targets only.

Additional fresh checks:

- Read-only Git identity, scoped diff/package comparison, and `git diff --check`: successful; no whitespace errors.
- AST parsing of all nine present Task 2 Python files: successful, without importing product modules.
- AST comparison against the base: current schema `installed`, `verify_journal`, `install_journal`, `_install_on_connection`, transition `profile_snapshot_sha256`, and review `confirmation_for` are unchanged. This checks the named callees, not all neighboring task behavior.
- Static Research call-path inspection included registry registration, both API wrappers and both OAuth allowlists; no provider calls or adapter execution occurred.
- Read the supplied offline runner, but did not execute it or read its fixture databases.

### Fresh Memory-Only FK Probe

Ran with `env -i`, `/usr/bin/python3 -I -B`, `PYTHONDONTWRITEBYTECODE=1`, and unique workspace identity `.superpowers/sdd/2026-09-11-current-journal-and-sec-foundation/task2-review-fk-identities-7c2a28b9`. No directory or database file was created. An audit hook rejected every database open except `:memory:` and denied socket/subprocess activity during subject evaluation.

Extracted the actual `foreign_keys`, `closure`, `market_dependency`, and quoting function via AST, without module imports. Used minimal in-memory owned parents and one `independent_receipt` external child; the profile ownership set contained only the selected owned root. Compared both base and frozen source. Lowercase versus uppercase parent spelling was the only varying fixture input, with FK enforcement ON and `ON DELETE CASCADE` in both cases.

| Root / declared FK target | Base and snapshot blocker | Child rows after conditional parent DELETE | FK errors |
| --- | --- | ---: | ---: |
| Profile / `security_lifecycle_cases` | Blocks | 1 | 0 |
| Profile / `SECURITY_LIFECYCLE_CASES` | Misses | 0 | 0 |
| Market / `security_lifecycle_observations` | Blocks | 1 | 0 |
| Market / `SECURITY_LIFECYCLE_OBSERVATIONS` | Misses | 0 | 0 |

The probe exited 0 after asserting these reproduced observations. It establishes the guard counterexample and SQLite cascade consequence, not a full `apply_disposal_stage` integration run. Full-stage reachability was traced in source. Initial local audit setup rejected the system Python's bytes-form `b':memory:'` event before opening a database; the final hook accepts only the string/bytes spellings of that same memory sentinel. An initial XML-parser attempt also hit an unavailable `hashlib.file_digest` API; the successful audit used portable byte hashing. Neither setup issue was a product-test failure.

## Limits And Cross-Task Status

- No real database, `config/.env`, credentials, production inventory, provider/network, installation, App/server start, disposal operation, Git index or HEAD mutation was performed. The only written artifact is this review, via `apply_patch`; probes created no files.
- JUnit proves the contents of the supplied records, not independently authenticated execution provenance or the complete neighboring worktree at the time of those runs. This review freshly verified current Task 2 hashes and source, not a fresh 149-test run.
- Cannot certify Task 1's complete confirmation/reversal/history extraction, captured-source binding and transaction timing, cancellation, or all transferred tests from this package. Named imported interfaces and obsolete import removal were checked; full Task 1 quality review remains separate.
- Task 3 SEC foundation and Task 4 whole-branch integration, census, full-suite acceptance and rollout are outside this review. No SEC workflow readiness or production disposition approval is implied. The pre-existing FK finding should be resolved before certifying the requested generic guard or authorizing any real disposal.

## Advisory Patch Risk

Task-scoped recommendation: **revise**; workflow label: **revise**. Impact if the disposal guard is wrong is high because retained external data can be deleted. Regression likelihood is moderate: this patch does not introduce the confirmed failure, but retains it in a required path. Protection is partial, recovery requires the operator's backup and coordinated restoration, and confidence is moderate overall. Migration, persistent state and public result shape exclude automatic merge. This is not the separate whole-branch review.

```json
{
  "schemaVersion": 1,
  "patch": {
    "repository": "/tmp/arkscope-listing-sec-macro-convergence",
    "sourceType": "patch_file",
    "base": "2842c497dabfdb0b13c315e22b206128eba9f57d",
    "head": "frozen Task 2 snapshot; package sha256 6d9dc5f89c13a6a3419732165f33d324517b3a34592d9a177944526cfe424e17",
    "changedFiles": ["src/sqlite_backup.py", "src/lifecycle_investigation/migration.py", "src/lifecycle_investigation/disposal.py", "src/security_lifecycle_population.py", "src/security_lifecycle_current.py", "src/lifecycle_web_schema.py", "src/lifecycle_web_migration.py", "tests/test_sqlite_backup.py", "tests/test_lifecycle_investigation_retirement.py", "tests/test_security_lifecycle_population.py", "tests/test_security_lifecycle_current.py", "tests/test_lifecycle_web_migration.py"],
    "sha256": "e8a4c3621713330ca0e0b54be17c59d9adbbee5d6af950b86b25f21ed4c071a9"
  },
  "recommendation": "revise",
  "workflowLabel": "revise",
  "impact": {"rating": "high", "rationale": "The named disposal guard can miss a retained external FK and cascade-delete unrelated data; current model-tool result shape is also affected."},
  "regressionLikelihood": {"rating": "moderate", "rationale": "The confirmed FK defect is also present at the exact base, not introduced by Task 2. The remaining task changes are narrow and supported by inspected controls."},
  "regressionProtection": {"rating": "partial", "rationale": "Inspected XML records contain 149 passing final nodes and four mutation kills, but only lowercase external-FK controls. No fresh suite execution or authenticated exact-execution snapshot was available.", "exactHeadChecksPassed": false},
  "recoverability": {"rating": "managed", "rationale": "Source-only cleanup is reversible; after an explicitly approved disposal, recovering cascaded retained rows requires validated backup restoration and coordination."},
  "confidence": {"rating": "moderate", "rationale": "Exact Task 2 identity and the FK counterexample are verified; source-extracted memory probes are not a full-stage or cross-task integration run."},
  "applicability": {"status": "confirmed", "rationale": "Current installation/disposal and registered Research review consumers use the changed owners. Review includes the explicitly named generic FK contract."},
  "statusQuoRisk": {"rating": "high", "rationale": "The same disposal retention gap was reproduced against 2842c497. Not merging does not remove that risk."},
  "autoMergeExclusions": ["migration", "persistent_state", "public_contract"],
  "affectedRuntimeRoots": ["src/lifecycle_investigation/migration.py:apply_installation", "src/lifecycle_investigation/disposal.py:preview_disposal/apply_disposal_stage", "src/security_lifecycle_population.py:read_population_manifest", "src/tools/security_lifecycle_tools.py:get_security_lifecycle_review"],
  "importantCallers": ["SecurityLifecycleReadService.get_current_review", "Research registry and API wrappers", "current migration/disposal direct backup imports"],
  "riskDrivers": ["Inherited case-sensitive FK target matching", "Digest revalidation repeats the same incomplete selection", "CASCADE leaves no FK violation for postflight detection"],
  "protectiveFactors": ["Exclusive WAL-aware backup with explicit close", "Stopped-App and digest guards", "Transactional receipt/rollback controls", "Closed population and current detail shapes", "Human assessments and correctly resolved external references retained"],
  "materialBoundaries": [
    {"id": "backup", "invariant": "Never replace an existing backup; preserve committed WAL rows and close destination.", "runtimeRoot": "migration.apply_installation and disposal.apply_disposal_stage", "counterexample": "Existing/dangling destination, WAL-only commit, or backup failure.", "legitimateControl": "sqlite_backup.py:9-14 and test_sqlite_backup.py behavioral owners; source and XML reviewed.", "result": "supported"},
    {"id": "external-fk-retention", "invariant": "Unknown external references block disposal regardless of valid SQLite target-name casing.", "runtimeRoot": "disposal.preview_disposal/apply_disposal_stage", "counterexample": "Uppercase parent target with ON DELETE CASCADE is missed on both profile and market paths in base and snapshot.", "legitimateControl": "Identical lowercase FK fixtures block and retain the child. Existing tests exercise this control only.", "result": "contradicted"},
    {"id": "population", "invariant": "Reject extra manifest material while preserving current evidence/translation/transition references.", "runtimeRoot": "read_population_manifest", "counterexample": "Resealed obsolete inventory key or dangling evidence/receipt binding.", "legitimateControl": "Closed key check at security_lifecycle_population.py:527 plus unchanged retention validators and inspected positive/negative tests.", "result": "supported"},
    {"id": "model-tool-detail", "invariant": "Retain current model-tool review detail without web_runs.", "runtimeRoot": "get_security_lifecycle_review", "counterexample": "Reintroducing web_runs causes both service and Research-tool equality owners to fail.", "legitimateControl": "Registered wrapper still delegates to live get_current_review, returning version/as_of/item with unchanged item projection.", "result": "supported"}
  ],
  "validation": [
    {"name": "Frozen package identity and scoped diff check", "status": "passed", "protects": "All 12 package entries and exact diff bytes; no Task 2 drift or whitespace errors."},
    {"name": "AST syntax and named-callee comparison", "status": "passed", "protects": "Nine present task files parse; six named cross-call functions are unchanged from base."},
    {"name": "JUnit artifact and node accounting audit", "status": "passed", "protects": "Corroborates stored 138P baseline, 10F/11P RED, 149P final and four mutation records; not a fresh execution claim."},
    {"name": "Generic FK-retention invariant, memory-only counterexample", "status": "failed", "protects": "Uppercase target bypass reproduced on profile/market in both base and snapshot; lowercase controls retain children."},
    {"name": "Fresh suite and whole-branch integration", "status": "skipped", "protects": "Not rerun per requested scope; belongs to the separate parent review."}
  ],
  "unknowns": [
    {"summary": "Complete Task 1/3 behavior and final whole-branch integration are not certified by this task package.", "decisionCritical": false},
    {"summary": "Prior test execution environment/code provenance and actual production store state were not independently inspected.", "decisionCritical": false}
  ],
  "evidencePlan": []
}
```
