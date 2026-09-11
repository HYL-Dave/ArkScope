# Task 1 Scoped Re-Review

Disposition: **P2 closed. No new load-bearing findings in this follow-up.**
The receipt-ordering fix and canonical index are approved within Task 1 scope.
This does not approve the whole acquisition change or production activation.

## Closure Evidence

- `src/sec_research/store.py:214`: latest receipt is selected by
  `receipt_id DESC LIMIT 1`, constrained to the normalized CIK. Neither timestamp
  participates in selection. The unchanged INTEGER PRIMARY KEY AUTOINCREMENT and
  explicit write transaction provide durable append ordering for Store writes;
  recording time remains diagnostic metadata.
- `src/sec_research/schema.py:42`: the canonical receipt lookup index is
  `(cik, receipt_id DESC)`, matching the query. Exact DDL verification remains
  authoritative; there is no migration, automatic repair, or old-index fallback.
- `tests/test_sec_research_store.py:341`: the original old-complete/new-pending
  clock-rollback scenario now selects the newer receipt, including through a new
  Store instance. The test checks reversed recording timestamps, later observation
  time, increasing IDs, and retention of both rows.
- `tests/test_sec_research_store.py:363`: index_xinfo verifies both key columns
  and their ordering. Existing backdated-observation and equal/fractional-clock
  owners still pass.
- `tests/test_sec_research_store.py:394`: separate receipt row/byte-limit owners
  reject before the writer lock, assert exact error arguments and no receipt,
  then prove a valid append succeeds after restoring the limits. These are
  additional admission coverage, not a change to runtime capacity policy.

## Fresh Independent Verification

1. **399 passed**, exit 0, 5.96 seconds: store, catalog, facts, common, paths,
   config, and service tests. This is the 352-test focused set plus 47 service
   tests, not an additional disjoint 399 tests.
2. **50 passed**, exit 0, 1.26 seconds: the 48 store cases plus two in-memory
   reviewer probes. The probes establish that:
   - Replacing only the fixture receipt index with the former timestamp-based
     definition makes both verify and install reject with
     `sec_research_schema_mismatch`, without changing schema or retained receipts
     and without leaving an active transaction.
   - Repeated canonical installation retains the exact new index definition;
     EXPLAIN QUERY PLAN uses that index without a temporary sort.

XML evidence, relative to this report directory:

- `review1-tests/rereview/focused-service.xml`
- `review1-tests/rereview/canonical-index.xml`

Both runs used the existing `offline_pytest.py`, clean `env -i`, disabled plugin
autoload/bytecode, and
`ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review1-tests/rereview`.
The interpreter and PATH match the prior reviewed runner invocation. The second
run injected the two probes through pytest collection after installing the
runner audit fence and fixture environment; it did not edit tests or source.
The worker's reported RED and inverse counts were read, not independently rerun.

## Boundaries And Source Identity

Reviewed the Task 1 report update, the original P2 finding, both implementation
files, and the relevant test changes. No public pagination/latest-history
requirement was added. No fresh full-backend, capture/routes review, production
DB/config access, network activity, agents, staging, or commits were performed.
Existing parent staging was left untouched. This report is the only authored
file; tests generated disposable fixtures/XML within the review workspace.

The three source hashes matched the worker report before verification and were
unchanged afterward:

```text
a51a61c18dd49dfba8853a619ed6e747e1638eef4dd74c74f3c26bf76d081e7c  src/sec_research/schema.py
b38f3466883611f9822eba62179d6870af953dab27991542b6ba72f2513d5c80  src/sec_research/store.py
27ae01a2cf490e4b7cba835aacc5d7f338c7184ce5940dd7da1cc63ebf502525  tests/test_sec_research_store.py
```
