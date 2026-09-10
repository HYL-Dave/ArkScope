# Final Review Fix: Scanner Queue Ownership

Worktree `/tmp/arkscope-listing-sec-macro-convergence`, immutable base `46ec6f31`.
Read `final-review.md` in this scratch directory, P3 only. C21 already owns
deferred SA news-density work; do not redefine it as a scanner fix.

Make one docs-only fix commit, restricted to these four files:
- `docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/README.md`
- that audit's `sec-retention-helper-cleanup/README.md`
- that checkpoint's `census-interpretation.json`
- `docs/design/PROJECT_PRIORITY_MAP.md`

Create a distinct named maintenance item `CENSUS-SQL-001` in the main audit:
scanner union-schema completeness before preparing SQL JOIN read observations;
owner `tests/repository_inventory.py` and `tests/test_repository_inventory.py`.
Acceptance: a dynamically declared joined table must not silently erase an
actual translation-reader observation; if preparation cannot be established,
retain an explicit uncertainty rather than authorizing deletion. This is queued
maintenance, NOT implementation or a passing-test claim. Preserve existing C21
and all other candidate dispositions unchanged. Point the three other files'
incorrect scanner C21 assignments to the distinct item. Historical discussion
can explain the old label was mistaken; C01-C21 references to the overall queue
are still correct and must not be mechanically renamed.

`census-interpretation.json` is a human interpretation, not the raw census.
Correct only its follow_up label, preserving measured values. Never alter raw
census, XML, test IDs, compressed artifacts, source, tests, schema or state.
No provider/production/config/credentials reads, App, tests rerun, subagents,
merge/push or broader cleanup. Parent owns plan/ledger/final report archival.

Verify the exact doc diff, JSON parsing, whitespace, preserved C21 row and
unchanged runtime/raw artifacts; no test execution is needed for a label fix.
Commit only these four files. Write `final-doc-fix-report.md` in scratch with
head, scope and checks; announce head immediately. Parent requests one scoped
re-review of this fix after your report.
