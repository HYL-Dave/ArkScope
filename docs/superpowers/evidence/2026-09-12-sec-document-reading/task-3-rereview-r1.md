## Spec Compliance

PASS for diagnostics-only fix `2f84d2de..64a25c34`. Only the route-test file changes; production and both inventory-owner hashes remain unchanged (`task-3-fix-r1-diff.txt:6`; `task3-fix1-current-inverse-evidence.json:3`). Prior Task3 API verdict is retained, not reopened.

## Finding Resolution

- Prior Minor: Addressed. The per-fixture guard appends before raising ordinary `ForbiddenAccess`; the wrapped client request checks the same persistent ledger in `finally`, outside request execution (`tests/test_sec_research_document_routes.py:23`, `:35`, `:44`). A route catching the sentinel cannot erase the recorded call or bypass that assertion. All changed guard installations use the corresponding fixture closure; no ledger reset or weakened response assertion was introduced.
- Evidence confirms the formerly masked-response risk is detected: validation-order produces 17 outside-request ledger failures, GET-budget produces one ledger failure plus one unavailable-versus-ok failure, permission produces one ledger failure, and profile identity retains two actual-header failures. All four inverses have zero errors/skips and no portal-teardown diagnostic (`task3-fix1-inverse-validation-order-01/results.xml:1`, `task3-fix1-inverse-get-budget-01/results.xml:1`, `task3-fix1-inverse-permission-01/results.xml:1`, `task3-fix1-inverse-profile-identity-01/results.xml:1`).
- New breakage: None found. Critical/Important/Minor open findings: None in this fix scope.

## Verification

- Read the 236-line immutable diff once. Independently parsed manifest, per-run hash records, commands and JUnit; verified exact failing case identities, exit codes, mutation-file SHA256, and all four before/restored/current scoped hash maps. Evidence-helper inspection confirms process-local compilation and module restoration (`task3_fix1_inverse.py:45`, `:68`); it was not executed.
- Archived route gate: 81 passed. Archived focused gate: 234 passed with zero failures/errors/skips and exactly the same testcase-identity multiset as the original focused gate (`task3-fix1-green-01/results.xml:1`, `task3-fix1-precommit-01/results.xml:1`, `task3-precommit-01/results.xml:1`). Focused output is clean (`task3-fix1-precommit-01/output.log:6`).
- No suite rerun, probe, product/index edit, subagent, or Task1/2 internal inspection. Only this review artifact was written.

## Assessment

Spec: PASS. Quality: Approved. The prior diagnostics finding is closed without weakening forbidden-call detection; parent browser/full-integration acceptance remains separate.
