# EIR-006 Fixture Classification Collateral

The first frozen full run at `6cddc221` ended 10,310 passed / one failed /
12 unchanged skipped. Collection and execution both contain exactly 10,323
nodes. Source, runtime and runner identities are unchanged. This is a failed
integration run, not an environment/interference failure or acceptance.

The existing closed census scans `market_sync_meta` in tests as well as runtime.
The new R1 controls in `tests/test_provider_health.py` intentionally create a
real disposable legacy table and corrupt current telemetry table. This newly
discovered test consumer was missing from `_TEST_FIXTURES`. Its role is a test
fixture, not an alternate production storage authority.

The correction adds exactly that filename to `_TEST_FIXTURES` in
`tests/test_eir006_retired_data_boundaries.py`. Discovery patterns, exact verdict
uniqueness, rejection of unclassified paths, stale-authority checks, production
source and all existing/new behavior assertions remain unchanged. No whole
directory or generic path exemption is introduced; no new test node is added.

## Fresh Checks

- `collateral-eir006-red`: standalone 1 failed / 1 passed, same assertion as full.
- `collateral-eir006-green`: census, health, sync and routing owners, 78 passed.
- `collateral-eir006-inverse`: remove only the new fixture classification;
  1 failed / 1 passed, same named census owner.
- `collateral-eir006-restored`: restore the one line; all 78 passed.

Final hashes equal the pre-inverse hashes:

| Path | SHA-256 |
| --- | --- |
| `tests/test_eir006_retired_data_boundaries.py` | `db84a8ffdff17b4b637014cfbc455ee704df12c26665c332e3e75dae630fcf1f` |
| `tests/test_provider_health.py` | `2bf1b078f2e39446844f458b9d019c2f0176a1c7c98a4eea113a676257072df6` |
| `src/service/provider_health.py` | `e01866ee0d3060b2ad33bdf9f775e0088a2937a0372ab52852df2988f37b550e` |

Independent scoped review, a new source freeze/collection/census and a fresh
single full suite follow. The earlier failed run and validation are retained
without overwriting them or combining partial successes into a passing total.
