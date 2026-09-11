# Tasks 3 + 4 Stored-Route Addendum

## Scoped Verdict

No actionable finding in the small GET integration cleanup. Read the live
`src/api/routes/sec_research.py:47` change, unchanged
`src/sec_research/service.py:182` implementation, and
`src/sec_research/store.py:158` metadata reader. This is an addendum, not a repeat
of the full review or a review of parent-owned CaptureStore changes.

- GET now calls `ResearchService(store, None, None).stored(cik)`, giving `.stored()`
  a real application consumer and removing the duplicated receipt/count query
  logic from the route. It is not an unused helper left by this cleanup.
- The service derives status from the current receipt's completed/pending/gaps,
  not retained old snapshot success. The route preserves its response envelope,
  receipt time/gaps/coverage and unavailable handling for absent or unobserved
  storage. Minor representation detail: `snapshot_counts` always includes both
  `catalog` and `facts`, with zero for an absent kind; the former SQL GROUP BY
  omitted an absent kind. This is not byte-for-byte payload equivalence.
- Counts come from materialized `Store.snapshots()` metadata lists: lengths for
  snapshot counts and summed `row_count` metadata for retained observation counts.
  GET exposes only the snapshot counts. No `Store.facts()`, `Store.catalog()` or
  capture-body reads occur. Metadata includes decoded historical-file metadata;
  this path is neither streaming nor paged and scales with retained snapshots.
- Existing missing-store/schema guards remain before service use. `.stored()`
  performs read-only store queries, with no installation, capture construction,
  profile/config access, refresh lease, preflight or provider dispatch. POST and
  application mounting are unchanged by this cleanup.

This supersedes the original review's description of GET as issuing SQL snapshot
counts directly. The earlier command-only installed-empty GET probe also forbade
`Store.snapshots()`; that implementation-specific restriction is obsolete, not
part of the no-fact/no-body-load contract. Its earlier pass is not claimed as
verification of this revision.

## Evidence

- Inspected supplied `stored-route-integration.xml`: 59 tests, zero failures,
  errors or skips, 2.630s. This is supplied integration evidence, not a new full
  scoped run by this reviewer.
- Fresh offline route-only run: **12 passed in 0.95s**, exit 0, using the existing
  `offline_pytest.py`, `env -i`, clean PATH
  `/home/hyl/.virtualenvs/llm_app/bin:/usr/bin:/bin`, disabled plugin autoload and
  bytecode writes, and unique workspace `review34-tests/rereview`.
  XML: `review34-tests/rereview-routes.xml`.
- No source/test edits, production data/config/provider access, network calls,
  agents or commits. Only this addendum and disposable test outputs were written.

Reviewed route SHA256:
`83e5f786d565e9964d8447e7d24e6648be4fd602fdc580fd92e0f0250caf53cd`.
Service and route-test hashes remain those recorded in `task34-review.md`.
