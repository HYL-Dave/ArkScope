## Spec Compliance

- PASS for Task3, range `1f964efe..2f84d2de`, bound only by approved plan lines 23-66 and the supplied Task3 requirements/notes. All four specified files have corresponding changes; no extra product surface (`task-3-diff.txt:6`).
- Pre-I/O validation and content-free 422s are implemented before path resolution; GET opens storage without profile/config/budget authority or acquisition (`src/api/routes/sec_research.py:212`, `:239`, `:263`, `:270`). POST requires the exact primary body, checks shared write permission, validates budget/profile identity before installation, supplies explicit policy, and returns the service attempt without inventing non-dispatch (`src/api/routes/sec_research.py:280`, `:287`, `:291`, `:300`, `:309`).
- Fresh installation and refusal to repair old/corrupt shapes are exercised by the new route tests; their successful archived cases are in `task3-precommit-01/results.xml:1`. Actual mounted inventory assertions preserve all six original SEC routes and add only GET/POST document routes, total 224 (`tests/test_api.py:169`, `tests/test_security_lifecycle_routes.py:464`). Both inventory cases passed in that archive.
- Cannot verify from this diff alone: inherited parser/resource limits, cross-process lock implementation, relocation durability, whole-application preservation and four transport boundaries. Task1/2 internals were not reopened; parent browser/full-integration remains required, not a Task3 defect (`docs/superpowers/plans/2026-09-12-sec-document-reading.md:25`, `:35`, `:49`).

## Strengths

- HTTP integration uses actual service/reader/policy/parser/storage with generated wire bodies; verifies both profile-identity headers, exact UTF-8 provenance, literal search and pinned rereads (`tests/test_sec_research_document_routes.py:229`). Archived generated examples corroborate the reported attempt, closed envelopes and byte offsets (`task3-precommit-01/pytest/test_real_post_get_search_and_0/interface-examples.json:1`).
- Failure responses preserve service dispatch evidence rather than fabricating an attempt; the archived timeout, invalid-report refresh, busy-root and missing/corrupt-object cases passed (`src/api/routes/sec_research.py:309`, `:315`; `task3-precommit-01/results.xml:1`).

## Issues

- Critical: None.
- Important: None.
- Minor: `tests/test_sec_research_document_routes.py:23` uses `pytest.fail` inside TestClient request execution. Under deliberate inverses this produces secondary `RuntimeError: This portal is not running` teardown noise: 17 validation-order errors, one GET-budget error and one permission error (`task3-inverse-validation-order-01/results.xml:1`, `task3-inverse-get-budget-01/results.xml:1`, `task3-inverse-permission-01/results.xml:1`). The intended behavioral failures are independently visible, so this is nonblocking. Prefer recording forbidden calls, raising an ordinary sentinel exception, and asserting the recorded calls are empty outside request execution; retain those assertions so broad route catches cannot hide violations.

## Verification

- Read the immutable diff exactly once in nonoverlapping chunks 1-230, 231-460, 461-688. No outside-diff product-code inspection, subagents, test reruns, generated probes, provider/config access, installs or product/index edits.
- Parsed archived JUnit/command records: RED 63 failures; GREEN 63 and 83 passes; final focused 234 passes and regression 1627 passes, both zero failures/errors/skips. Ordinary logs have no warnings (`task3-red-routes-01/results.xml:1`, `task3-green-routes-01/results.xml:1`, `task3-green-boundaries-01/results.xml:1`, `task3-precommit-01/output.log:6`, `task3-regression-01/output.log:25`). Regression inventory includes the reported SEC, permissions, task/model/tool control selections (`task3-regression-01/command.json:1`).
- All four inverse archives show the intended boundary failures, including actual wrong identity headers (`task3-inverse-profile-identity-01/results.xml:1`). Current route SHA256 matches the reported restored value `bcefb3040c18809967acd58a56fbb8e641848883a999d3b954c11a8a33076bde`; final focused artifacts are clean. Historical per-inverse four-file hash restoration remains a report claim, not independently established by those test archives (`task-3-report.md:84`).

## Assessment

Task quality: Approved with one minor test-diagnostics finding. Spec compliance: PASS within Task3 scope; no blocking cross-task concern identified. The API adapters preserve owner contracts and have substantive offline integration coverage; parent browser/full-integration acceptance is still pending.
