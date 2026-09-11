# Independent Task 1 Review

**Verdict: revise.** One Important closed-envelope defect; no Critical findings.
Review concerns only the frozen Task 1 artifact, not active frontend work.

## Patch Identity

- Repository: `/tmp/arkscope-listing-sec-macro-convergence`.
- Base: `0658ebf097813875895ecfb7561522860dbfdf69`.
- Head: `e207b3ad495729958f0f2340cb0a012c6272a521`.
- Authoritative input: `task-1-diff.txt`, read once in contiguous chunks.
- SHA-256: `71010a06b4f8612e915aa6329626d348fe342866738054b20e055690cf50b9d8`.
- Seven files: schema/store/service/queries and their three named test modules.

## Findings

### Critical

None found.

### Important

1. **P2: valid JSON with an invalid receipt shape escapes the unavailable boundary.**
   `src/sec_research/store.py:61` decodes receipt JSON without validating its
   resulting shape. `src/sec_research/queries.py:128` assumes `source_snapshots`
   is iterable, while the exception boundary at `queries.py:261` does not convert
   the resulting `TypeError` into a closed unavailable envelope. In a canonical
   disposable database, inserting a receipt with `source_snapshots='null'` or
   `'1'` makes `StoredQueries.filings` raise respectively
   `'NoneType' object is not iterable` or `'int' object is not iterable`.
   The schema accepts these TEXT values and schema verification still succeeds.
   This violates the stated closed storage-failure/query-envelope contract.
   Normal `Store.record_receipt` calls do not emit these shapes; this is a bounded
   corrupt/noncanonical-row availability defect, not a provider-triggerable
   bypass or proof of incorrect normal acquisition authority.

   Validate decoded receipt fields and their canonical relationships at the read
   boundary, returning an existing closed binding/storage error on invalid shape.
   Preserve the explicitly permitted unbound `{}` case. Prefer validation over
   broadly swallowing all `TypeError`/`AttributeError` exceptions. Extend the
   corruption regression beyond invalid JSON syntax to valid JSON wrong types.
   Independent frozen-code probe: **2 failed, 2 passed**, zero collection errors;
   `{}` and invalid JSON syntax are the passing controls. Evidence:
   `task-1-review-probe/test_receipt_shape.py` and `task-1-review-probe/result.xml`.

### Minor

No additional actionable findings.

## Spec Compliance

- Receipt writes bind completed locators exactly to snapshot identity and a
  normalized observation timestamp; issuer, kind and historical locator are
  checked. Omitted bindings remain explicitly unbound. The read-shape exception
  above is the outstanding canonical-shape/closed-envelope gap.
- Fresh intent is checkpointed without old bindings before dispatch. Resume
  preserves acquired bindings and reacquires unbound completed sources.
  Unchanged publication identity can retain a newer receipt observation time.
- Continuations reopen the named receipt, not latest. Canonical cursor decoding
  binds issuer, kind, normalized filters including limit, receipt and bindings
  digest. Restart/relocation/refresh coverage and inverse evidence support this.
- Schema remains exact and immutable; there is no migration/repair path.
  AUTOINCREMENT and SQLite ownership of `sqlite_sequence` are preserved, not
  newly fixed. Their initially green characterization owners are legitimate:
  explicit inverse mutations fail at max-rowid and unrelated-sequence ownership.
- Forms/dates filter streamed rows before aggregate admission and pagination.
  Aggregate row/encoded-byte/source limits stop traversal with explicit gaps;
  incomplete traversal does not become observed empty. Companyfacts-only pending
  work does not invalidate an otherwise covered catalog selection.
- Identical selected filing metadata merges provenance; conflicting selected
  variants remain visible with counted gaps. Ordering is deterministic.
- Pagination measures the actual whole encoded envelope, limits whole rows,
  and advances past oversized observations with typed gaps. No substring loss
  or unbounded hypothetical cursor reserve was found.
- Existing catalog/facts/snapshots interfaces remain, and the service receipt
  caller is updated. No current caller or live tool registration is removed
  by this diff. Task 2 facts selection and subsequent HTTP/UI work are not claimed.

## Quality

The store/service/query ownership split is coherent, with shared cursor and
envelope helpers ready for Task 2. Read connections are explicitly read-only;
early-stop observation iterators close their connections. Resource accounting
correctly describes encoded admitted input rather than claiming a process-RSS
cap. The extra source-count bound is justified by aggregate metadata admission.
The concrete weakness is trusting decoded receipt types at the read boundary.

Impact if that defect occurs is query unavailability through an uncaught
exception. Likelihood is low for validated writer output but demonstrated for
malformed retained state. Confidence in this finding is high. Fixing read
validation needs no schema mutation; reverting this entire task after installing
its new schema would encounter the deliberate exact-schema mismatch and is not
a transparent rollback. No merge or activation is authorized by this review.

## Evidence Checked

- Read the review brief, task brief, implementation report and approved plan
  globals/Task 1. Later plan sections appeared in the same initial read but were
  not assessed as part of Task 1.
- Parsed archived JUnit: baseline 95 pass; initial RED 59 fail/97 pass; edge RED
  7 fail; envelope RED 1 fail; aggregate RED 5 fail; final focused 169 pass;
  final SEC/collateral 587 pass. All these archives have zero errors/skips.
  Final focused breakdown is store 64, service 51, queries 54; collateral 418.
- Read raw RED/inverse failure evidence and baseline/final green logs. Inverse
  AUTOINCREMENT/latest/filter/sequence-owner/aggregate runs have 1/1/5/1/1 named
  failures. One filter mutant fails with the wrong closed code; four wrongly
  admit changed filters. These are meaningful assertion failures, not collection
  failures. No baseline/final debug or deprecation noise appears in these checked
  logs, and final JUnit contains no captured noise nodes; none is counted as a
  newly introduced failure.
- All seven frozen commit blob SHA-256 values match `hashes-committed.json`.
  `hashes-before.json` and all five restoration manifests match those values.
  The 587 result is verified archived evidence, not a newly rerun suite.
- The only new execution was the four-case receipt-shape probe through this
  plan's `offline_pytest.py`, fresh `env -i`, bytecode/cache disabled and unique
  `task-1-review-probe/work` fixture/HOME/database paths. It loads schema/store/
  queries directly from the frozen commit into memory. No broad suite ran.

## Additional Reads And Limits

- Concrete schema ownership/immutability risk: read frozen `schema.py` to check
  `_owned`, `verify`, `install` and immutable triggers beyond the diff context.
- Concrete caller compatibility risk: scoped frozen `git grep` in
  `src/sec_research` and `src/api/routes/sec_research.py` for receipt and existing
  observation interfaces; checked the service call sites. No frontend inspected.
- Concrete corrupt-receipt risk: reopened frozen schema/store/queries for the
  four-case probe and a narrow numbered store excerpt for the finding reference.
- Evidence safety/integrity: read `offline_pytest.py`, `task-1/run.py`, the named
  logs/JUnit/hash manifests; obtained frozen blobs only to verify byte hashes.
- Unanswered: broader malformed field combinations were not exhaustively probed;
  the proposed read validation should cover them without schema repair. Full
  backend, HTTP and UI integration remain parent-owned and outside this review.
- No product/test source, index, branch, production store/config/token files or
  frozen artifact was modified. No agents or provider network were used. Writes
  are limited to this report and its disposable scratch probe/evidence.
