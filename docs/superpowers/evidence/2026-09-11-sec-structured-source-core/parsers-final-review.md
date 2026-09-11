# Independent Final Parser And Batch Review

## Gate And Findings

**PASS. No actionable source defect or concrete integration blocker identified.**
The parent may proceed with the planned offline full-backend verification.

| Scope | Spec verdict | Quality verdict |
| --- | --- | --- |
| Task 3: common decoding and catalog | PASS | PASS |
| Task 4: immutable Company Facts observations | PASS | PASS |
| Overall current batch integration | PASS | PASS |

These verdicts apply to the pure-parser batch and the exact snapshot below.
They are not full-backend, merge, production activation, complete SEC service,
coverage traversal, or user-data-integrity approval. No P1/P2/P3 finding is being
withheld pending full-backend execution.

## Snapshot Signature

Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
Base: `95ad149ea4bda2569030f1dfc95f93bf3c279738`.
Observed HEAD: `41ab878e9e57521e61d58500d8621c8c4025718a`.
Source signature initially checked at **2026-09-11T03:57:01Z**, and rechecked
unchanged immediately before **2026-09-11T03:59:59Z** (11:59:59 Asia/Taipei).
HEAD alone does not identify the staged parser additions; the patch hash does.

`batch-review.diff` SHA256:
`5b17c54189dd8d7fd908a3db8ac54ae990d0ddad18ea2396c7812d109c75bfdd`.

Both byte comparisons exited 0:

```bash
cmp .superpowers/sdd/2026-09-11-sec-structured-source-core/batch-review.diff <(git diff 95ad149ea4bda2569030f1dfc95f93bf3c279738 -- src tests)
```

SHA256 file signatures, unchanged across review:

```text
46354d9b83987b73faf12a89361bdb90ad41040512622b60fc1314e4c8906db2  src/sec_research/common.py
a3d40b51f8d4f12e29116516cc6d882de0449a9fb91d9b3556abfe1e03b2e9e0  src/sec_research/catalog.py
d91a2e8897762c332d244f4998f44f6c58aa2770fda3d0b5645852dde6946c0a  src/sec_research/facts.py
eaf3c440f641c97b90f1724fb3eaa266fff4631b56fc92fda4aecb01fc4cd9a9  tests/test_sec_research_common.py
d9881834f56a21162eb510d305fb3df335e3a44acc8373d1e6482cbd4f03ea53  tests/test_sec_research_catalog.py
b3c3a13b2dd5a34ffbd69710e70012625649d6ec378674beb66447fe8e46455c  tests/test_sec_research_facts.py
651f50ac0435797366055f965469e423f25aef149d55b0c196312b86624304b3  .superpowers/sdd/2026-09-11-sec-structured-source-core/offline_pytest.py
4c451c2fad8dc97efdd7139c1e420bb77565ec88f3363c401a1fbcd63f23c327  docs/superpowers/evidence/2026-09-11-sec-structured-source-core/sqlite_upsert_repro.py
```

## Task 3: Spec And Quality

Read the complete current implementation plan, especially Global Constraints and
the explicit completion boundary; spec sections 5/6 and supporting 3/11; both
worker reports; and every new parser source/test file in the supplied patch.

- `common.py:89`: bytes-only UTF-8 decoding uses Decimal directly from tokens,
  exact integer decoding, and duplicate-key detection before dict collapse.
  Nonfinite, overflow, invalid UTF-8, malformed/deep JSON and duplicate keys
  produce closed SourceError codes. RFC6901 paths escape slash/tilde correctly;
  surrogate keys cannot escape as UnicodeEncodeError during fact-ID encoding.
- `common.py:107`, `:118`, `:147`: explicit nonzero ASCII CIK normalization and
  payload matching do not infer ticker identity or confuse filing-agent
  accession prefixes with issuer CIK. No prefix-equality restriction is added.
- `catalog.py:76`: required arrays, every present column's list shape and
  alignment, all required scalar fields and conflicting repeated accessions
  are checked before a snapshot can return. Required explicit empty arrays
  establish zero rows; missing arrays do not. No malformed suffix is dropped.
- `catalog.py:99`: filed, report and accepted dates remain independent.
  Optional missing values stay None. Aware timestamps normalize to UTC, retain
  supported microseconds and reject overflow or excess fractional precision.
  No report date or document suffix is invented.
- `catalog.py:67`, `:111`, `:121`: actual conservative document basenames form
  issuer-directory URLs; traversal, encoded paths and query/fragment tricks
  are rejected. Historical names bind the requested CIK; optional exact integer
  counts and calendar bounds remain explicit, with reversed bounds rejected.
- `catalog.py:43`, `:151`, `:156`: historical_files_observed is present in the
  reviewed source. Missing files and historical roots are False; explicit empty
  or populated recent files are True. Malformed present files remain errors.
  This observation bit is not a completeness claim.
- `catalog.py:113`, `:116`: stable CIK/accession filing IDs coexist with exact
  original-byte hashes and row pointers; amendments stay distinct. Frozen
  records and tuple collections introduce no mutable snapshot alias.

Quality verdict: the shared validators have clear owners, hashing is once per
body, and validation never returns a partially successful snapshot. The modest
pure functions do not introduce storage, acquisition, configuration or registry
coupling. No blocking maintainability or regression concern found.

Task 3's finalized evidence was inspected, not described as independently
reexecuted mutations: 124 focused passes; separate presence-bit RED 4; four
isolated follow-up mutants killed (float decode, guessed report date, successful
malformed alignment, always-observed files). The last mutant fails the missing
case with 1 failure/3 passes, as expected. The common/catalog hashes recorded in
task-3-followup.log equal the reviewed hashes above; no shared mutation remains.

## Task 4: Spec And Quality

- `facts.py:94`: shared exact decoding and payload CIK validation are used;
  missing/malformed facts containers cannot become empty success. Explicit
  empty namespace/concept/unit containers are allowed without completeness
  inference. Every present observation is processed before returning.
- `facts.py:60`, `:80`: only finite Decimal or exact int values are admitted,
  never bool, float or numeric text. Decimal-to-text conversion preserves exact
  values under low precision/exponent contexts, including large integers,
  negative zero, trailing fractional zeroes and scientific notation.
- `facts.py:63`: real end/filed dates are required; start is optional and may
  not exceed end. Fiscal labels/frame remain optional, units and namespaces
  are preserved, and no YTD-to-quarter, currency or latest-value inference occurs.
- `facts.py:72`, `:127`: deterministic IDs bind the original-body hash and exact
  escaped observation pointer. Unicode scalar keys work; invalid text and lone
  surrogates fail with typed errors. Duplicate/contradictory values at distinct
  pointers remain distinct, as do original and amended observations.

Quality verdict: Task 4 consumes Task 3's existing interface without another
decoder, mutable record layer or selection mechanism. No cross-task ABI mismatch
or import-time I/O found. The parser returns immutable exact observations only.

Inspected Task 4 XML confirms its valid assertion-owner RED (1 failure, no
collection errors), float inverse (4 failures), overwrite inverse (2 failures),
and restored 54 passes. Earlier 53 setup errors are correctly not counted as
valid RED evidence. Fresh behavior verification is separately recorded below.

## Whole-Batch Integration

- Accepted task12-review.md as the independent retained-function/assertion audit:
  all 16 retained ASTs unchanged and its 459-test run passed. Did not redo the
  deleted-function audit. The current four-file Task 2 diff byte-matches
  task2-review.diff; its new absence/positive-control tests were freshly rerun.
- Reviewed current SQLite executable source as requested. Its only connect
  target is `:memory:` (`sqlite_upsert_repro.py:86`), with separate per-case
  databases, memory temporary storage, no DB-path interface, no app imports,
  and observed-signature classification (`:26`, `:45`). Task12's independent
  execution and six diagnostics remain the execution evidence, not a new run
  claimed by this reviewer. Exit 1 denotes the archived defect reproduction,
  not an application-integrity finding or this batch's parser gate failure.
- `git ls-tree -r refs/heads/master -- src/audit` still lists all four tracked
  audit files; master was `30bb31c779f26d5b691ceb29b0cabe91dcd9ff41`.
  Nothing was deleted from master or any source directory.
- The complete source/test diff and import-reference scan introduce no live
  SEC registration, schema/DB activation, schedule, Settings change, transport
  change or import-time config read. Existing lifecycle execution-date policy,
  quotas and document transfer policy are untouched. Future acquisition,
  storage/quota, whole-history traversal, selection, public paging, tools and
  Settings are intentionally not implementation requirements of this batch.
- Read census.log: 1100 read, 4311 candidates, 3352 uncertainties. The parent
  reports only new test-only catalog/facts modules and zero new uncertainty,
  reduction, dependency or untracked drift. That comparison was not independently
  recomputed. Test-only parser reachability is expected at this stage, not an
  accidental enablement or missing production-registration defect.
- Scoped `git diff --check` against the base for src/tests/new evidence passed.

## Independent Verification

Both commands ran in the reviewed worktree with login=false, clean env, distinct
WORK directories and the inspected current offline runner. No full suite ran.

```bash
env -i PATH=/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-sec-structured-source-core/parsers-final-review-20260911T0405 /home/hyl/.virtualenvs/llm_app/bin/python -I -B .superpowers/sdd/2026-09-11-sec-structured-source-core/offline_pytest.py -q tests/test_sec_research_common.py tests/test_sec_research_catalog.py tests/test_sec_research_facts.py tests/test_openai_sync_surface_cleanup.py --junitxml=.superpowers/sdd/2026-09-11-sec-structured-source-core/parsers-final-review-20260911T0405/focused.xml

env -i PATH=/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONDONTWRITEBYTECODE=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-sec-structured-source-core/parsers-final-synthetic-20260911T0401 /home/hyl/.virtualenvs/llm_app/bin/python -I -B .superpowers/sdd/2026-09-11-sec-structured-source-core/offline_pytest.py -q .superpowers/sdd/2026-09-11-sec-structured-source-core/test_parsers_final_diagnostics.py --junitxml=.superpowers/sdd/2026-09-11-sec-structured-source-core/parsers-final-synthetic-20260911T0401/diagnostics.xml
```

Results: **181 passed in 2.11s** and **54 passed in 0.07s**, both exit 0.
Scratch directory suffixes are unique labels; actual XML timestamps identify
execution time. Synthetic diagnostics are hand-built inputs, not SEC acquisitions.
Named additional owners include:

- test_closed_decoder_boundaries
- test_invalid_fact_text_is_typed_at_every_location
- test_unicode_source_pointer_resolves_and_binds_exact_bytes
- test_exact_values_under_restrictive_decimal_context
- test_invalid_numeric_last_row_cannot_be_partial_success
- test_historical_count_requires_exact_nonnegative_int
- test_optional_history_is_not_a_completeness_claim
- test_invalid_or_lossy_timestamp_rejects_entire_catalog
- test_valid_timestamp_retains_microseconds_and_changes_calendar_day
- test_conflicts_in_unprojected_columns_reject_whole_catalog
- test_contradictory_facts_and_empty_unit_arrays_are_not_rewritten

Independently parsed the parent's parsers-combined.xml: **332 tests, zero errors,
failures or skips**; console log reports 6.02s. Accounting is 178 new parser
tests, 126 existing config/path tests, 13 existing SEC tool tests, 10 transport
tests and 5 user-agent tests. This is inspected parent evidence, not a second
332-test execution by this reviewer.

Only this report, the synthetic diagnostic module and isolated runner artifacts
were written. No source/test patch edits, subagents, provider/network calls,
production/config/token reads, installation, commits or full-backend run.
Remaining gate: parent-owned full backend and final evidence/accounting; no
concrete source integration blocker was found in this reviewed snapshot.
