# Task 1 R1 Scoped Re-Review

**Gate verdict: PASS for R1.** The original Important P2 receipt JSON-shape
finding is closed. No Critical, Important or Minor findings remain within this
scoped correction. This is not approval of the whole patch or active follow-on work.

## Scope And Identity

- Read `task-1-report.md` only from its appended Fix Round 1 section and read the
  complete frozen `task-1-r1-diff.txt` once. Reviewed receipt read validation,
  adjacent relationships, explicit unbound mappings and exception handling only.
- Base: `e207b3ad495729958f0f2340cb0a012c6272a521`.
- Head: `7a1b9d9933919e327701c3ed713272a6e1da0348`; parent identity verified.
- Frozen diff SHA-256:
  `4fb95e2d7173b272bc988c709f98431e22633fdf25658f05e6c6846c351bf5b5`.
- Exactly three scoped files: `src/sec_research/store.py`,
  `tests/test_sec_research_store.py`, `tests/test_sec_research_queries.py`.

## Finding Resolution

- `src/sec_research/store.py:70`: shared `_receipt` validates decoded values
  before either latest or pinned receipt reads return them. JSON `null`, numbers,
  booleans, arrays and strings cannot masquerade as the binding mapping. Invalid
  JSON syntax also reaches the closed binding error.
- `src/sec_research/store.py:56`: `_receipt_fields` shares existing writer rules
  with reads. Lists and locator element types are checked before set operations;
  duplicate states, completed/pending overlap, invalid or foreign issuer locators,
  and non-dictionary gap entries are rejected without unsafe operations on them.
- `src/sec_research/store.py:75`: receipt ID/CIK, JSON TEXT field inputs,
  timestamps, nonempty mapping-to-completed equality and exact inner binding
  shape are validated. Snapshot issuer/kind/locator validation remains at the
  existing bound-snapshot consumer, not replaced by shape checks.
- `src/sec_research/store.py:86`: the empty mapping is deliberately exempt from
  nonempty binding coverage equality. Explicit unbound `{}` remains readable
  with empty or nonempty completed lists; it grants no snapshot authority.
  Valid existing list/gap shapes and bound-receipt behavior remain supported.
- `src/sec_research/store.py:91`: only `ValueError` and `RecursionError` are
  translated to `sec_research_receipt_binding_invalid`, already handled by the
  unchanged query adapter. There is no broad `Exception`, `TypeError` or
  `AttributeError` swallowing, coercion, schema repair or mutation on read.

## Evidence Checked

- Read raw `task-1/r1-green.log`, `r1-inverse.log`, `r1-green-final.log`, and the
  relevant beginning of `r1-red.log`; parsed all four corresponding JUnit files.
- Archived RED: 52 failures and 17 controls passing across 69 new cases.
  Archived focused GREEN: 238 passing (store 115, service 51, queries 72).
  Archived final GREEN: 644 passing, including all 69 new cases. Each archive
  has zero collection errors and zero skips. No captured noise nodes appear in
  final JUnit; intentional inverse failures are not baseline warning failures.
- The two inverse owners fail for the relevant reasons: direct Store read no
  longer rejects JSON null when validation is bypassed, and the query again
  raises the original NoneType iteration error. Both owners are included in
  the subsequent green archive.
- Direct Store tests cover latest and pinned reads, invalid field types,
  relationships, inner binding shapes and both explicit unbound controls.
  Query tests cover the original null/integer failure and adjacent list fields;
  the binding-shape owner seeds a valid older receipt before the invalid/unbound
  latest one, preventing an accidental old-snapshot fallback from passing.
- Independently hashed all three frozen head blobs and matched
  `r1-hashes-committed.json`. `r1-hashes-before.json` and
  `r1-hashes-restored.json` match the same values.

## Limits

No concrete unanswered doubt remains for this gate, so no additional probe or
suite was run. Test results above are checked archived evidence, not a fresh test
execution. Exhaustive malformed-database behavior and whole-change integration
are not claimed. No active API/frontend/facts changes were read or assessed.
No source, test source, index, branch, production data/config/token files or
frozen artifacts were modified; no agents or provider calls were used. The only
write in this re-review is this report.
