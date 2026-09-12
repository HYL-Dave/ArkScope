# SEC Integration And Cleanup Continuation

This is not a complete SEC release or a master merge. No production database,
private configuration, provider or running application was accessed by the
integration tests. SQLite preparation is separate from runtime activation and
actual-store integrity assessment.

## Preservation And Integration

- `ba4f2619` preserves the 45 modified SEC paths, four new code/test files and
  eight source-only analysis files: 57 paths total. Both previously untracked
  product modules are recoverable from git. Its commit explicitly records the
  historical 4-failure/758-pass result, not a release-ready claim.
- Security base: `41682675`, product candidate `ff7c4d75`. The user's supplied
  Opus review reports an independent 10166-pass/12-skip run and successful
  credential, all-cut-point stream and public-content checks. This is attributed
  external review, not a new local run or a rewrite of sealed security evidence.
- `codex/sec-research-integration` starts at that security base and replays SEC
  as `3fef138d`. Original branches remain intact; master was not changed.
- Against common base `18d46062`, nine files overlap and five have textual
  conflicts, not seventeen independently overlapping SEC core changes.

## Integration Repairs

1. SEC registrations declare a closed validator through shared `ResultPolicy`.
2. OpenAI preserves async handler identity and awaits it inside the sanitized
   exception boundary; the sync wrapper returned unawaited SEC coroutines.
3. Anthropic SEC dispatch now uses the common argument/error boundary.
4. SEC owns OAuth stop/join/deadline. A second bridge timer raced and replaced
   its closed timeout result. Other tools retain their original deadline logic.
5. The historical SEC-only redactor is deleted. All four channels use identical
   canonical serialization and wrapping. Typed rejection never silently changes
   a cited passage. Domain-specific whole-page budgeting remains.

## Verification

Commands/JUnit are in this plan's scratch workspace:
`.superpowers/sdd/2026-09-12-sec-research-release-integration/`.
The copied offline runner uses disposable stores and a closed environment. Its
Python audit hook blocks production paths/providers but is not an OS sandbox.

| Run | Actual result | Meaning |
| --- | --- | --- |
| integration-red-01 | exit 4, no tests | Wrong test filename; invocation error, not RED evidence |
| integration-red-02 | 40 failed / 38 passed | Missing policy and unawaited async callback |
| integration-red-03 | 7 failed | Named policy, byte-equivalence and async owners |
| integration-green-01 | 4 failed / 414 passed | Two obsolete serializer monkeypatches, old tool count/name owners |
| integration-green-02 | 1133 passed | SEC, eight count files, skills/subagent, both OAuth drivers, output/key/card guards |
| integration-timeout-red | 2 failed / 8 passed | Both OAuth timers lose closed SEC timeout; document bytes agree |
| integration-timeout-green | 187 passed | Stop/join/timeout, adapters and OAuth regressions |
| integration-review-red | 12 failed | Actual Anthropic SDK stream loses all three SEC results; governor-stop dispatches for both CIK and ticker; transport has no cancellation callback |
| integration-review-green-01 | 2 failed / 233 passed | New owners pass; old in-flight fixture records dispatch after cancellation |
| integration-review-green-02 | 994 passed | Actual native stream, governed cancellation, body/retry closure, SEC and security/agent regressions |

Separate runs are not an additive total or a complete backend result. Successful
runs contain no warnings. Unawaited-coroutine warnings remain in pre-fix evidence.
The shared security inventory is additional count collateral: 56 tools comprise
49 ordinary JSON, 3 closed SEC JSON and 4 text policies.

## Remaining Work

Task2 review reproduced two defects after the adapter checks: nested
`asyncio.run` in the actual Anthropic streaming caller and metadata dispatch
after cancellation while waiting for the SEC governor. Fixes now await the
SEC worker in the actual stream and propagate the task's cancellation check
through metadata/map acquisition to the existing cooperative governor, dispatch,
body and retry boundaries. Legacy callers without a check keep their retry
behavior. Actual producer tests compare the entire result sent back to the
model with canonical service output. The old in-flight fixture now records
its first request before waiting, retaining its one-request/context/stop/join
assertions. Scoped re-review is pending. Tasks1/4 were already reviewed, not
restarted.
Tasks3/5/6/7 remain open: durable Research citations/reopening, operation leases
and export/restore, orphan cleanup/schema reset, default-disabled scheduling.
Settings and backend citations do not imply these workflows are complete.

C03 old catalog tool/forwarders/empty HTTP route are removed here. C10-C13,
C15/C20 data disposition, i18n/CSS/SQL census queues and production SQLite
admission are not marked complete. C21 remains an explicit deferred capability.
Actual data deletion still requires bounded inventory, backup and approval.

## C09 Checkpoint

The unused EODHD/Alpha Vantage/Finnhub standalone source classes and unified
factory are physically removed. Current Polygon/EDGAR/IBKR exports, Finnhub
news/calendar and EODHD census/Settings credentials remain. Current docs no
longer advertise removed adapters; dated provider comparisons are historical.
No stored data or keys were inspected or changed.

The worker observed 6 failed / 190 passed before product deletion, then
196 passed; restoring a removed leaf made its named owner fail. Controller
run `c09-controller-green` independently returned 196 passed. Seven test IDs
were added and none removed. This commit preserves the implementation; remaining
inverse checks and independent review are pending, not cleanup-wide acceptance.
