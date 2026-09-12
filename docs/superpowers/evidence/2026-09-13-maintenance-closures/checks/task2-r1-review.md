# Task 2 R1 Scoped Re-Review

Reviewed `a4bf0a739fabba418138829f3ce501edc6dab5f8` through
`6cddc221c31ef6a1b21ac37e06273a2ef28b31ab` using the R1 report and supplied
two-file diff. HEAD matches the package, and current product/test SHA-256s match
the handoff's final restored hashes. The original Task2 diff was not re-reviewed.

## R1 Resolution

**Resolved.** At [src/service/provider_health.py:240](/tmp/arkscope-research-output-boundary/src/service/provider_health.py:240),
the copied provisional sync mapping has only `news` cleared before both
`Path(db_path).exists()` and `read_news_sync_status()`. Neither failure can now
return the legacy news row. A successful read still supplies current telemetry,
including `None` when absent. The existing degradation note, existence-result
semantics, non-news sync values and price authority remain intact. Provider/key
handling and IBKR's combined health calculation are unchanged by this delta.

## New Tests

- [tests/test_provider_health.py:504](/tmp/arkscope-research-output-boundary/tests/test_provider_health.py:504)
  adds legacy-news-present/absent cases using real disposable legacy telemetry,
  malformed current telemetry, nonempty articles/prices and `SqliteBackend`.
  The saved real legacy reader replaces the autouse stub locally. Assertions
  retain the acquisition error, exact price telemetry/authority, fundamentals,
  article visibility without publication fallback, IBKR success and DB bytes.
- [tests/test_provider_health.py:583](/tmp/arkscope-research-output-boundary/tests/test_provider_health.py:583)
  targets the earlier existence-probe failure. Its module-local `Path` replacement
  leaves the real legacy reader's probe unaffected, so the test reaches the
  intended ordering boundary and checks stale-news removal plus retained controls.
- Exactly three nodes are added; no existing assertions or test nodes are removed.
  The inspected existence RED and final inverse receipts fail on the seeded
  legacy-news assertion, not setup errors; the absent-legacy control stays green.

## Verdicts

**New issues:** None found in the scoped fix or new tests.

**Spec: PASS. Quality: PASS.** The correction addresses both R1 failure windows
without widening exception handling, introducing fallback, or changing unrelated
provider behavior. No further focused R1 test is requested.

## Evidence And Limits

Existing receipts inspected: `task2-r1-controller-green` reports 76 passed;
`task2-fix-r1-final-owned-restored` reports 332 passed. These are historical
receipts, not reviewer reruns. Current hashes match the restored bytes.
Full frozen integration checks and broad final acceptance remain controller-owned.

No tests, agents, network/private-data access, product changes or Git writes
were performed. Reads were limited to the R1 delta, directly relevant fixture/
probe context and current maintenance scratch. Only this review file was created
with apply_patch; the original review remains unchanged.
