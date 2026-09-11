# Spec Compliance

- **Issues found:** malformed domain operands and cursors bypass the required closed HTTP 422 boundary when storage is absent. `src/api/routes/sec_research.py:133` returns before domain validation at line 135. See Important finding I1.
- The remaining inspected Task 3 requirements match the frozen four-file change: static config ordering, strict byte budget, typed persistence, admission before mutation owners, stored-only delegation, unchanged refresh, and four additional mounted routes. Evidence is detailed below.
- **Outside this verdict:** aggregate query semantics owned by Tasks 1/2 and frontend visual behavior. The parent-reported offline live-HTTP browser passes across four locale/viewport combinations were not rerun; the separate visual fix is not part of this diff.

## Strengths

- `src/api/routes/sec_research.py:51` uses a strict bounded integer model with extra fields forbidden; lines 56 and 72 register static config routes before the generic CIK route at line 82. GET distinguishes invalid persisted config from profile/storage failure instead of substituting a default.
- `src/api/routes/sec_research.py:74` calls write admission before obtaining the profile owner. PUT invokes only the typed setter and returns the saved integer at line 76; it neither opens capture storage nor performs acquisition or scheduling.
- `src/api/routes/sec_research.py:39` checks SEC ownership case-insensitively and verifies canonical schema read-only. Config uses actual capture accounting at line 66, returns null only for an absent/unrelated installation, and closes capacity failures at line 68.
- `src/api/routes/sec_research.py:146` and line 157 forward every declared operand to the real stored service, including repeated lists, dates, revisions, IDs and cursors. No adapter filtering, metric registry, source rewriting or float conversion is introduced.
- `tests/test_api.py:167` and `tests/test_security_lifecycle_routes.py:467` retain the census contracts and existing route assertions, changing 218 to 222 and explicitly adding exactly four SEC routes. Frozen diff scope is exactly the four authorized files; existing status/refresh registrations remain.
- Archived real-store HTTP tests exercise exact decimal strings, EUR units, SourceRef keys, pagination, immutable historical IDs, quota reduction and corruption. Both final JUnit artifacts contain all ten real-facts cases without skip/failure children; this supersedes the report's historical Task 2 dependency caveat.

## Issues

### Critical

- None found.

### Important

- **I1 / P2: Storage availability suppresses malformed-input rejection.** `src/api/routes/sec_research.py:133` returns `sec_research_not_installed` before calling `StoredQueries` at line 135. Only the HTTP-level scalar validators have run at that point. Consequently, on an absent store, `/filings?cursor=!`, `/facts?cursor=!`, `/filings?forms=` and `/facts?period=unknown` all return HTTP 200/unavailable instead of a closed 422 input error. The same inputs are rejected when installed, so the public validation contract changes with local storage state. This violates the plan's "All query errors are closed 422 codes" requirement (`docs/superpowers/plans/2026-09-11-sec-query-settings.md:164`). The archived malformed-domain/cursor tests all require the installed-store fixture and do not cover this branch.
  Fix by running shared, storage-independent domain operand validation and cursor syntax validation before the installation early return. Keep validation in the domain boundary rather than duplicating filter/cursor rules in the HTTP adapter; preserve read-only schema verification and unavailable responses for valid requests against absent/broken storage. Receipt-dependent cursor checks can still require storage. Add absent-store rejection cases and retain valid absent-store controls.
  Reproduction: `task-3-review-probe/test_absent_validation.py:8`; failure assertion at line 36. One isolated seven-case run produced **4 failed, 3 passed**, exit 1, in 0.87s. The four failures are exactly the requests above; strict `limit=1.0` rejection and both valid absent-store reads pass. Assertions also confirm no market DB or capture root was created. Raw evidence: `task-3-review-probe-run/output.log:1`, `command.json:1`, `results.xml:1`.

### Minor

- None found.

## Checks And Boundaries

- Reviewed the brief, approved plan Global Constraints/Task 3, Task 1 handoff, and the complete Task 3 report including the latest genuine-integration and serialized-commit appendices. Authoritative change: frozen `task-3-diff.txt:1`, base `e07e459a3deb1236af9687a3ed4216786114d3ca`, head `05edf925293c1b096503526782f1350b1beefe83`, four files, 485 insertions/12 deletions.
- Read the frozen diff in one review pass. The tool truncated a small middle test section; recovered that excerpt with narrow surrounding context. No changed product file was separately read, and no git commands were run.
- **Named outside-code risk: hidden writes or fallback through config/accounting helpers.** Focused inspection of `src/sec_research/config.py:25` and line 43 confirms default-only-on-absent parsing and setting-only persistence. `src/sec_research/store.py:127` and line 131 show a side-effect-free constructor and SQLite read-only/query-only connections. `src/sec_research/captures.py:33` and line 49 show construction without acquisition and SELECT-only real accounting. Together with the route's explicit error handling and archived corruption tests, this answers that risk without a new probe.
- **Named outside-code risk: validation precedence and delegation contract.** Focused inspection of `src/sec_research/queries.py:59`, line 83, line 309 and line 318 confirms shared strict dates, cursor syntax validation before receipt access, actual facts delegation, and domain operand validation. The adapter's earlier installation return bypasses those checks, motivating only probe I1; no broader domain-code crawl was performed.
- Read both final `command.json` and complete `output.log` artifacts, and parsed their JUnit XML with the standard XML parser. `task-3-green-after-task-2/output.log:6` reports **271 passed in 21.42s**; `task-3-green-before-commit/output.log:6` reports **271 passed in 19.19s**. Both command records have exit 0 and no selection exclusions; both XML suites have 271 tests, zero failures/errors/skips. Logs contain no warnings. These are inspected archived results, not reviewer reruns.
- Read `run_checks.py:17` and `offline_pytest.py:17` to verify isolation before the single focused probe. Executed only `run_checks.py task-3-review-probe-run backend -q .superpowers/sdd/2026-09-11-sec-query-settings/task-3-review-probe/test_absent_validation.py` under the specified clean environment. The probe mounts only this router on a disposable FastAPI instance, forbids profile/provider/capture owners and installation, and uses isolated paths. No live application, production database/config/token, real provider, package/full-suite rerun, subagent, index or branch operation was used.
- All review writes are this report and disposable probe/evidence under the specified plan directory. No product changes were made.

## Assessment

**Task quality: Needs fixes.** The adapters are small and preserve domain ownership, and the archived genuine integration evidence is substantive. I1 is a reproducible public input-contract violation not exercised by the existing installed-store rejection cases; resolve it before approving this task.
