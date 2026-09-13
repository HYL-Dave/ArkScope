**R1: Protect every Task6 output from the observed profile SQLite namespace - ADDRESSED.**

- [maintenance.py:358](/tmp/arkscope-research-output-boundary/src/sec_research/maintenance.py:358) reserves both databases and their `-journal`, `-wal`, and `-shm` names before destination admission. Direct cleanup obtains the actual query-only connection's main path before checking its receipt at [maintenance.py:436](/tmp/arkscope-research-output-boundary/src/sec_research/maintenance.py:436); schema apply does the same before admitting either receipt or backup at [schema_admin.py:37](/tmp/arkscope-research-output-boundary/src/sec_research/schema_admin.py:37). Neither creates an output before these checks.
- [__main__.py:52](/tmp/arkscope-research-output-boundary/src/sec_research/__main__.py:52) resolves the profile path once, checks both preview destinations and all apply receipt/backup destinations, then opens that same path read-only/query-only. `_new_destination` only inspects the destination namespace; it does not create output. The changed helper signatures have no unadapted callers in the scoped symbol search.
- The retained GREEN/covering evidence includes all 32 reserved-name/output combinations: direct cleanup receipt, direct schema receipt/backup, and both CLI previews plus all CLI apply outputs. Rejection checks preserve market/capture state and call the real separate-profile rollback-journal writer at [test_sec_research_maintenance.py:63](/tmp/arkscope-research-output-boundary/tests/test_sec_research_maintenance.py:63). Both successful CLI workflows also exercise that writer at [test_sec_research_cli.py:19](/tmp/arkscope-research-output-boundary/tests/test_sec_research_cli.py:19).

**R2: Keep failure audit and resource close inside the original exclusive SEC lease - ADDRESSED.**

- Cleanup acquires its original exclusive context into an `ExitStack` at [maintenance.py:439](/tmp/arkscope-research-output-boundary/src/sec_research/maintenance.py:439); schema apply does so at [schema_admin.py:43](/tmp/arkscope-research-output-boundary/src/sec_research/schema_admin.py:43). Failure finalization at [maintenance.py:488](/tmp/arkscope-research-output-boundary/src/sec_research/maintenance.py:488) and [schema_admin.py:100](/tmp/arkscope-research-output-boundary/src/sec_research/schema_admin.py:100) completes before each `finally` closes the stack. LIFO registration closes the audit, then capture descriptors, then the originally acquired lease. No release/reacquire occurs.
- The unchanged lease releases ownership only on context exit at [capture_lock.py:112](/tmp/arkscope-research-output-boundary/src/sec_research/capture_lock.py:112). The short market transaction at [maintenance.py:409](/tmp/arkscope-research-output-boundary/src/sec_research/maintenance.py:409) unwinds, including rollback and writer-lock exit, before failure-audit publication; the fix does not extend it around audit I/O or resource close.
- Five retained failure-stage controls cover cleanup transaction/unlink and schema backup/transaction/post-backup stale refusal. The barrier at [test_sec_research_maintenance.py:147](/tmp/arkscope-research-output-boundary/tests/test_sec_research_maintenance.py:147) requires the original lease to remain entered, denies a different-owner SEC operation, and permits an actual unrelated market insert. The exit trace also excludes release/reacquire. Two admission-negative controls retain no lease, audit, or output. Resource-close ordering was verified from source; the barrier itself observes failure publication.

**C1: Correct the two Task5 locale inventory expectations - ADDRESSED.**

- The immutable diff changes only `research: 224` to `236` at [resources.test.ts:757](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/i18n/resources.test.ts:757) and total `2974` to `2986` at [resources.test.ts:842](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/i18n/resources.test.ts:842). Exact per-namespace `.toBe(count)`, total equality, and surrounding inventory guards are unchanged.
- A source-only TypeScript AST count found 236 nonempty string leaves and identical Research key paths in EACH locale. The six named families (`maintenance`, `protectionPlatform`, `protectionPath`, `protectionConfiguration`, `protectionSpace`, `protectionUnavailable`) each have Title/Detail leaves at [en/research.ts:201](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/i18n/resources/en/research.ts:201) and [zh-Hant/research.ts:201](/tmp/arkscope-research-output-boundary/apps/arkscope-web/src/i18n/resources/zh-Hant/research.ts:201). Those are 12 leaves per locale, leaving 224 other leaves: `224 + 12 = 236`, `2974 + 12 = 2986`; the seven expected namespace counts also sum to 2986. Locale modules were parsed, not executed.
- The retained `task6-final-frontend/output.log` identifies the two old-count assertions in the single inventory failure, with 1829 passed / 1 failed overall. `task5-collateral-green-01/command.json` records the focused resources test only, exit 0; its log records 14 passed, 468ms Vitest / 0.830s runner. This does not relabel the historical full run as passing or claim a new full frontend gate.

## New Breakage In The Fix Diff

None identified. No new Critical, Important, or Minor finding within this fix boundary.

## Checks And Retained Evidence

- Read the brief, controller preflight, prior R1/R2 findings, appended Fix Round1 report, and C1 handoff. Read `task6-fix1-review.diff` once in three non-overlapping chunks: BASE `e495d664087e3201b44c3b78b44b64f47c1df77c`, HEAD `78157e62f0526b90898a2a4b77c1d6ffe6a9a15b`, two commits, seven changed files. Did not regenerate a diff or rerun git commands.
- Outside-diff source reads were limited to named fix dependencies: observational profile/path admission, create-only destination behavior, audit/capture close and lease release, short transaction unwinding, changed-signature callers, the reused separate-profile/market-writer fixtures, and C1's current locale leaves/counting semantics. No fresh Task6, Task5, or broad frontend review.
- Parsed all five fix-round JUnit receipts and their command JSON; checked retained log summaries against them:

| Retained Run | Exit | Result |
| --- | --- | --- |
| `task6-fix1-red-01` | 1 | 29 failed, 10 passed, 104 deselected; 3.50s |
| `task6-fix1-green-01` | 0 | 41 passed, 102 deselected; 2.69s |
| `task6-fix1-inverse-profile-outputs-01` | 1 | 24 assertion failures, 8 passed; 2.66s |
| `task6-fix1-inverse-failure-audit-lease-01` | 1 | 5 assertion failures, 2 passed; 1.06s |
| `task6-fix1-covering-frozen-01` | 0 | 1064 passed; log 112.61s, runner 113.57s |

- All five parsed receipts have zero errors/skips. The covering command names all 22 covering files, including the three amended Task6 files. Inverse failures target the profile sidecar/output assertions and original-lease exit assertion, not collection/setup failures. Both inverse restoration receipts' product/test hashes match current scoped files; CLI and collateral-test hashes also match their reports, as do the retained collateral command/log hashes.
- No tests, suites, inverses, fixtures, application entrypoints, subagents, providers, actual databases, credentials, configuration, installations, or deployment operations were run/accessed. No product/test, index, or git state was mutated. The only file written by this review is `task6-rereview-1.md`.

## Out-of-Scope Observations

None. Existing dependency acceptance and controller-owned release/runtime gates remain outside this scoped re-review.

## Verdict

**Fix round: All findings addressed, no new Critical/Important breakage. R1, R2, and C1 are closed for source-only Task6 acceptance plus the two-line Task5 inventory collateral. This is not full-release, deployment, actual-store operation, or master-merge approval.**
