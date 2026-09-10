# Statistics-Only Inventory Review

## Findings

**Disposition: two issues to resolve before the production read under the stated authorization.**

### P1: Read-only SQL does not establish the promised absence of production filesystem writes

Source: [inventory.py:82](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:82) and [inventory.py:213](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:213).

Both database URIs use `mode=ro`, and `query_only` plus the authorizer prohibit
application SQL writes. These do not prohibit SQLite's WAL coordination writes.
A read-only connection can create a missing `-shm` file in a writable directory
or update WAL-index shared-memory read marks when that sidecar is writable.
Those operations are outside the SQL authorizer. Consequently, the unconditional
`production_writes: false` cannot certify a literal no-production-writes boundary.
The supplied fixtures use ordinary rollback-journal databases, so their passing
write-denial checks do not establish WAL-sidecar safety.

Before running, either obtain explicit authorization for WAL coordination side
effects and describe the guarantee narrowly as no logical database writes, or
enforce a genuinely non-writable filesystem view of the databases and sidecars,
failing closed when a live WAL cannot be read that way. Do not bypass live WAL
with `immutable=1` or a copy of only the main database file. Add a synthetic live
WAL test, including committed but uncheckpointed rows and the chosen sidecar
write policy. No production WAL state was inspected during this review.

### P2: FK counts use ordinary SQL affinity instead of the parent key's FK affinity

Source: [inventory.py:140](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:140).

The generated `p.parent_column = c.child_column` comparison can apply the child's
numeric affinity to a TEXT parent key. SQLite FK matching instead applies the
parent key's affinity to the child value. For example, an owned parent with
`case_id TEXT PRIMARY KEY` containing `'01'` and an external child with
`case_id INTEGER REFERENCES security_lifecycle_cases(case_id)` containing `1`
is an orphan under FK semantics, but this join counts it as matched: ordinary
equality converts the parent's `'01'` to numeric `1`. Such pre-existing orphan
rows are possible with FK enforcement disabled, precisely the kind of state
this inventory attempts to classify. Both column names pass the allowlist.

Preserve parent-key comparison semantics, for example by removing the child
expression's affinity (`p.parent_column = +c.child_column`), or explicitly report
unsupported affinity combinations as unavailable. Add a synthetic TEXT-parent /
INTEGER-child case expecting zero matches and one orphan. The current reference
fixture uses TEXT on both sides and cannot expose this defect. This counterexample
is a static finding; no additional executable probe was run beyond the authorized
test command.

## Other Reviewed Boundaries

- The fixed inspection queries return counts and schema metadata, not raw body,
  credential, URL, prose, or unrelated settings values. Source/reference columns
  participate in SQL predicates without being returned as values. Relevant
  schema definitions are hashed before output. The two schedule queries count
  exact keys and never select settings values.
- Discovery reads table names and FK metadata to find inbound external
  dependencies. External row access is enabled only for allowlisted columns of
  an edge touching an owned table. The authorizer is defense in depth for this
  fixed one-time program, not an aggregate-only interface for arbitrary SQL;
  `authorized_column_reads` records authorizations, not physical row accesses.
- `BEGIN` spans the schema, counts, references, and classifications; closing the
  connection releases its read transactions on success or failure. There is no
  checkpoint, journal-mode change, or immutable/WAL bypass. The explicit
  `cross_database_atomicity: false` correctly avoids promising one simultaneous
  snapshot across the two stores. Live-WAL/concurrent-writer behavior is untested.
- Composite FK columns are grouped by FK id and sequence. `EXISTS` avoids join
  fan-out, and any NULL child component is classified as nullable, not orphaned.
  Explicit composite and external-child examples pass. Missing parents,
  out-of-scope column names, and implicit parent-key declarations are marked
  unavailable rather than silently zeroed; those branches lack dedicated tests.
- Absent owned tables, observed empty tables, and missing required columns are
  distinguished in the supplied tests. Query failures abort instead of becoming
  successful zero counts. A missing main database is not created.
- Reference enumeration covers declared FKs, plus the separate source-membership
  comparison, not all application-level accepted-history/digest dependencies.
  `source_membership.matched` counts observation rows, whereas `cases_only`
  counts case rows; these are not a single deduplicated identity partition.
  Nothing here establishes disposal eligibility or overrides the ownership
  checkpoint's retained-history and separate write-approval requirements.

## Parent Scope Clarifications

- `PROFILE` includes speculative `security_lifecycle_review_confirmations`
  ([inventory.py:29](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:29)).
  The parent reports that the real receipt is inside
  `ticker_identity_transitions.approved_preview` JSON. Remove the speculative
  table name in the parent's follow-up; an absent table is not evidence of zero
  review receipts. Do not read that JSON or infer receipt counts from transition
  row counts. Its location is parent-supplied context, not independently inspected
  source. This is a bounded-coverage correction, not permission to expand reads.
- The parent identifies `evidence_content_sha256` in the translations composite
  FK as nonsecret digest metadata. It is not in `FIELDS`, so
  [inventory.py:133](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/inventory.py:133)
  marks the whole edge `unavailable/reference_columns_out_of_scope`, without
  emitting misleading zero counts. That explicit gap is acceptable for bounded
  statistics, but cannot support a claim that translation references are absent
  or their retention closure is complete. Any follow-up allowlist addition should
  remain specific to this digest and have a synthetic composite-FK test.
- The parent subsequently source-verified two required old-runtime aggregates:
  profile `scheduler_state` restricted to `source='sec_corporate_actions'`, and
  profile `job_runs` restricted to `job_name='collect.sec_corporate_actions'`.
  The reviewed version does not issue either query; its settings-key counts are
  not substitutes. The parent will add these before production, after this
  initial review. Do not simply add these mixed-owner tables to `PROFILE`, since
  `store_inventory` would then count every row. Keep both queries exact-predicate
  aggregates with narrow key-column authorization and explicit missing-schema
  gaps. Related metadata is permitted; result, message, payload, and unrelated
  job/runtime contents or generic full-table counts are not. This is a required
  parent-owned coverage addition, separate from the two implementation findings.

No other blocking scope gap was identified within the permitted files. These
clarifications do not resolve the two pre-read findings above. No inspector or
test edits were made; the speculative-name correction and exact runtime
aggregates remain with the parent.

## Scope And Verification

Reviewed only `inventory.py`, `test_inventory.py`, and
`docs/superpowers/evidence/2026-09-10-pre-release-cleanup-audit/sec-schema-ownership.md`
in `/tmp/arkscope-listing-sec-macro-convergence`. The supplied baseline is
`8c8ac738`; Git metadata was not inspected. The reviewed inspector SHA-256 is
`266dcb09e4fe2394d216bc18a2640c35a63ac2d6311a5eccc48580efbae06e7f`.

Executed exactly the authorized synthetic suite:

```sh
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/hyl/.virtualenvs/llm_app/bin/python -B -m pytest -q --confcutdir=.superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup -p no:cacheprovider .superpowers/sdd/2026-09-10-sec-retention-inventory-and-helper-cleanup/test_inventory.py
```

Result: **12 passed in 0.49s**, exit code 0. These results do not cover either
finding above. No inspector `__main__` execution, production database access,
provider/configuration/credential access, application startup, subagents,
product edits, or Git index changes were performed. Only this report was added;
the parent's independent codec work was left untouched.
