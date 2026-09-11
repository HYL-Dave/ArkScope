# Task 1 Read-Only Review

Disposition: one load-bearing P2 finding; return to the Task 1 owner before
approval. No source/test edits, staging, commits, agents, production DB/config
access, or network calls. This report is the only authored file; pytest generated
disposable fixtures and XML under the requested unique review workspace.

## Finding

### P2: Wall-clock rollback selects an obsolete continuation receipt

Location: `src/sec_research/store.py:218`, specifically the ordering at line 219.
Related write: `src/sec_research/store.py:207`.

`latest_receipt()` orders primarily by `recorded_at`, which is sampled from the
adjustable wall clock. The AUTOINCREMENT receipt ID is only a tie-breaker. If the
clock moves backward between writes, a newer committed checkpoint is hidden by
an older checkpoint until the wall clock catches up. Fixed-width microseconds
solve lexical timestamp ordering but do not establish commit ordering.

Reproduced against the unchanged source with an in-memory pytest owner:
`tests/test_sec_research_store.py::test_review_latest_receipt_survives_clock_rollback`.

1. Record receipt 1 at `2026-09-11T01:00:00.000000Z`: status `ok`, completed
   submissions/companyfacts, no pending sources.
2. Move the injected store clock back to `2026-09-11T00:00:00.000000Z` and record
   receipt 2: status `unavailable`, neither source completed, both pending.
3. Receipt 2 has the larger durable ID and a later caller observation time, but
   `latest_receipt()` returns receipt 1 with its obsolete successful coverage.

This affects the current acquisition consumer, not a hypothetical public query
tool. `src/sec_research/service.py:87` resumes from this result and line 93
short-circuits if that old receipt has no pending sources. Lines 180 and 189
also use it for the refresh result and stored coverage. A fresh incomplete or
failed attempt can therefore appear complete, and resume can skip its work.

Use durable insertion order as continuation authority, for example descending
`receipt_id`, retaining `recorded_at` as audit metadata. Align the canonical
receipt lookup index if changing the query. No schema migration is requested.

Existing owners at `tests/test_sec_research_store.py:315` and line 327 cover
backdated observation times, zero-fraction timestamps, and equal wall times;
neither exercises a decreasing recording clock. Add a regression that records
old complete then new pending state across a backward clock step and requires
the second receipt to remain latest, including after reopening the Store.

Minimal owner body, using the existing store/modules/monkeypatch fixtures:

```python
times = iter([
    datetime(2026, 9, 11, 1, tzinfo=timezone.utc),
    datetime(2026, 9, 11, 0, tzinfo=timezone.utc),
])
class Clock(datetime):
    @classmethod
    def now(cls, tz=None):
        return next(times)
monkeypatch.setattr(modules[1], "datetime", Clock)
old = store.record_receipt(
    "320193", status="ok", completed=["submissions", "companyfacts"],
    pending=[], gaps=[], observed_at="2026-09-11T00:00:00Z")
new = store.record_receipt(
    "320193", status="unavailable", completed=[],
    pending=["submissions", "companyfacts"], gaps=[],
    observed_at="2026-09-11T00:00:01Z")
assert new["receipt_id"] > old["receipt_id"]
assert store.latest_receipt("320193") == new
```

## Verification

Reviewed the approved Task 1 plan, the linked substrate spec (especially canonical
storage, preservation, provenance, and coverage), all three scoped files, and
read-only service call sites needed to establish the finding's runtime impact.

Fresh focused run: **348 passed**, exit 0, 3.47 seconds. Files: store, catalog,
facts, common, paths, and config tests. This independently reproduces the worker's
focused count; the worker's inverse runs and the parent's combined count were
not rerun or claimed as independent review evidence.

Additional in-memory pytest owners ran alongside all 44 unchanged store tests:
**51 passed / 1 failed**, exit 1, 1.14 seconds. The sole failure is the clock
rollback owner above. Passing additional probes:

- Five separate explicit-rowid REPLACE conflicts, one per immutable table.
  Other natural keys were made fresh where applicable; the old rows survived.
- Object-key UNIQUE conflict with a different SHA, preserving the original row.
- Receipt row/byte limit rejection with a forbidden market writer lock.

The seven passing probes and one failing owner were injected through
`pytest_collection_modifyitems` with `pytest.Function.from_parent`; no test file
or implementation was changed. The existing runner's audit fence and fixture
environment were installed before tests executed.

Evidence, relative to this report directory:

- `review1-tests/focused.xml`
- `review1-tests/adversarial.xml`

Environment/runner used for both runs:

```text
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=.superpowers/sdd/2026-09-11-sec-durable-acquisition/review1-tests /home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-11-sec-durable-acquisition/offline_pytest.py
```

The focused run appended the six test files, `-q`, and its XML path. The
adversarial run wrapped the same runner with `runpy` and the in-memory collection
plugin, selecting the store test file and its own XML path.

## Other Scoped Conclusions

No additional load-bearing issue found in exact owned DDL validation, unexpected
owned-object rejection, transactional/idempotent installation, preservation of
populated unrelated tables, connection closure/read-only mode, row immutability,
exact decimal TEXT, amendments, retained source snapshots, registered source-hash
binding, publication rollback, or normalized admission limits before writer locks.
These conclusions combine source inspection with the named test suite/probes;
they are not a full backend, production, or exhaustive SQL-adversary validation.

Catalog/facts reopening intentionally returns retained immutable observations.
No latest-global-history, filtering, or public pagination requirement was imposed.
Original-byte verification remains the capture owner's responsibility, not an
additional body-read requirement on Store.publish. The current service owns
coverage-status derivation; this review does not invent whole-issuer completeness
from a partial request or require Store to infer it from locator lists.

## Reviewed Source Identity

All three hashes matched the worker report at review time:

```text
02b81dfed9b8a50bd4f2b646dce5e58b5503ed566a16657d581425a9f1c43327  src/sec_research/schema.py
56ca3a493f11d6283c53caadcf8dcc362a760d208cfd65de622fb7dd152f99ed  src/sec_research/store.py
4afb7692b645809125e118b07d7b161e9584e46af1c85686437a10ce44eef2b2  tests/test_sec_research_store.py
```
