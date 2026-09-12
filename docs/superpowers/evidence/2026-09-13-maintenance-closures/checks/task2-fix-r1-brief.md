# Task2 Review Fix R1

Read task2-review.md R1. Current source a4bf0a73; source/test worktree clean,
controller docs dirty. No full backend run has started. Prior final-named gates
are historical pre-review-fix receipts, not final acceptance after this change.

Root cause confirmed by controller: provider_health assigns legacy read_sync_meta
to sync, then attempts current read. Its exception handler adds a note but does
not clear the now-unauthorized legacy news slice. The final local_market.sync
can therefore expose it alongside missing current provider telemetry.

You own ONLY src/service/provider_health.py and tests/test_provider_health.py,
and current WORK report/receipts. No Git writes, agents, docs/product expansion,
provider/private data/config/App or other test runner. Controller remains docs
writer only. Reuse original offline runner unchanged; fresh run names.

RED first: implement review's named test with a real valid legacy sync news row,
malformed current provider_sync_runs table and real read_sync_meta (override the
autouse empty stub locally). Nonempty distinct prices/non-news telemetry must
survive; assert degradation note, no old news timestamp/counters and no provider
publication fallback. Consider failed current read when legacy news is absent as
a second parametrized case if it protects same exception shape. No mocks replacing
the actual failing current query. Preserve current error reporting, DB existence,
all other health/IBKR/key controls.

Fix at the provisional news acquisition boundary: retire legacy news before the
current read can fail. Avoid clearing unrelated sync data or swallowing errors.
Run named RED, implement narrow fix, focused GREEN + original329 owner command
(now with the additional node(s)). Inverse restoring original ordering must fail
the new owner; restore exact bytes and rerun. Controller owns full suite later.

Write task2-fix-r1-report.md with commands/counts, final diff/hash, exact added
nodes, root cause and any nonzero dispositions. Keep old reports/receipts intact.
All own processes stop before handoff; no stage/commit or finalfull run. Return
concise status/report path. No new policy decision is required for this fix.
