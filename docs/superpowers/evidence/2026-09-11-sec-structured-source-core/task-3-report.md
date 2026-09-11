# Task 3: Exact SEC JSON, CIK And Catalog Parsing

Current status: Task 3 pure parsing and the parent-approved frozen
`historical_files_observed` flag are implemented and ready for parent review.
Final focused result: **124 passed**. Both source files are stable; no mutations
remain. The original evidence and the flag's separate RED-first cycle follow.

## Scope

Implemented pure parsing only, not the complete SEC feature. Read the Task 3
brief and binding spec sections 3, 5, 6, 8 and 11. No provider/network calls,
production data/config/token reads, installations, subagents, commits, tool
registration, persistence, traversal or activation. Parent facts code/tests
were not edited or executed by this task. Existing shared worktree retained.

Owned source files:

- `src/sec_research/common.py`
- `src/sec_research/catalog.py`
- `tests/test_sec_research_common.py`
- `tests/test_sec_research_catalog.py`

## Verification Evidence

Direct pytest invocations used this command prefix, with only the named Task 3
test files or individual owners appended. Follow-up isolated mutation runs used
the same environment prefix with `python -c`, an in-memory pytest plugin and
`runpy.run_path` to execute this same offline harness; code is logged below.

```sh
env -i PATH=/home/hyl/.virtualenvs/llm_app/bin:/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-11-sec-structured-source-core/task-3-offline-5917 python .superpowers/sdd/2026-09-11-sec-structured-source-core/offline_pytest.py -q
```

- Initial assertion-based RED: **2 failed**, the common/catalog runtime-owner
  tests asserted their source files were missing. No import/collection errors.
- First focused GREEN: **120 passed** (58 common, 62 catalog).
- Inverse mutation 1: ordinary `float` in JSON decoding, **1 failed** in
  `test_decode_preserves_exact_decimal_and_large_integer`; restored immediately.
- Common-only post-restore check: **58 passed**. Parent notified that common
  was stable before remaining catalog-only mutations.
- Inverse mutation 2: filing date substituted for report date, **1 failed** in
  `test_catalog_preserves_report_filed_accepted_dates_separately`; restored.
- Inverse mutation 3: misaligned arrays returned successful empty filings,
  **6 failed, 4 passed** in the alignment owner; restored. Four passing cases
  were still-rejected non-array columns, not surviving alignment mutants.
- Original focused GREEN after all restores: **120 passed in 0.50s**.
- **3/3 mutations killed**, eight total expected assertion failures across
  mutation runs. Actual mutation output is in `task-3-mutations.log`.
- Original mutations were temporary source edits before the later
  plugin-mutation request; all were restored before parent integration.

Parent-approved observation-flag follow-up:

- Named owner `test_missing_historical_files_is_distinct_from_observed_empty`:
  **4 assertion-based RED failures** for the absent attribute. Cases distinguish
  missing `files`, explicit `[]`, populated files and a historical root.
- Sources stayed unchanged during the parent facts integration window. After
  the parent released it, only `catalog.py` needed a production edit.
- Follow-up focused GREEN: **124 passed** (58 common, 66 catalog).
- Four isolated per-process mutation runs: float decode **1 failed**; filing
  date as report date **1 failed**; malformed alignment as successful empty
  **6 failed, 4 passed**; always-observed recent files **1 failed, 3 passed**.
- **4/4 follow-up mutations killed**, nine expected assertion failures across
  those runs. Each plugin run emitted one pytest already-imported assertion-
  rewrite warning for the synthetic plugin, not a product/test failure. Exact
  executed code and output are in `task-3-followup.log`.
- SHA256 digests of both source files were identical before/after all four
  isolated mutations. None wrote to shared source files.
- Final unmodified focused GREEN: **124 passed in 0.50s**, no warnings.
- No full suite or parent facts tests run by this task. Parent independently
  owns the facts evidence, joint integration review and any commit.

## APIs And Decisions

- Shared APIs match the requested `date_value`, `accession_value`, `text_value`,
  `validate_payload_cik`, `SourceError`, frozen `SourceRef`, `decode_object`,
  `normalize_cik`, `source_ref` and `json_pointer` signatures.
- Decimal callback constructs `Decimal` directly from the original JSON numeric
  token; it does not use context rounding or a float intermediate. Invalid
  constants, Decimal exceptions/nonfinite results and integer conversion overflow
  produce `invalid_number` with root pointer. CPython's integer-string conversion
  limit is not disabled; exceeding it is an explicit typed failure, not truncation.
- Deferred object-pair materialization detects nested duplicate keys with full
  RFC6901 paths. Invalid UTF-8, syntax, roots and excessive recursion are typed
  errors. Error arguments contain only fixed code and pointer, never raw bodies;
  lower-level diagnostic display is suppressed on translated exceptions.
- CIK helper returns the ten numeric digits, without a display prefix. Recent
  payload CIK is required. Historical root CIK may be absent, but if present must
  match. Explicit historical filename must bind the same CIK and is retained as
  `CatalogSnapshot.historical_name`; no separate historical snapshot class.
- Catalog exposes `sha256`, `filings`, `historical_files`, `historical_name` and
  frozen `historical_files_observed`.
  It consumes `source_ref(body, "").sha256` exactly once per snapshot, reusing the
  digest in each immutable row reference. The test spies on real SHA256 calls.
- Filing pointers resolve to `/filings/recent/accessionNumber/<index>` or
  `/accessionNumber/<index>`; historical-file pointers resolve to their objects.
- Filing IDs are stable `CIK:accession` numeric-key pairs. Accession prefixes are
  shape-only validation, not an issuer identity test. Identical duplicate rows
  remain separate source observations; conflicting duplicates reject the entire
  snapshot, including conflicts in otherwise unprojected columns.
- All present columns must be lists of equal length. Historical root `cik` is
  identity metadata, not a column. Three required empty arrays establish truthful
  zero rows; missing arrays never imply successful empty results. Recent valid
  `files` lists, including `[]`, set `historical_files_observed=True`. An absent
  field or historical root yields False. Pointer tuples remain unchanged. This
  records observation, not complete history; present malformed `files` is still
  an error. No malformed row or file pointer is silently skipped.
- Dates require exact valid `YYYY-MM-DD`; optional null/empty dates stay None.
  Accepted timestamps require aware ISO date/time with seconds and at most six
  fractional digits, normalize to UTC `Z`, and reject overflow rather than
  truncating precision. Missing/empty optional document/timestamp stays None.
- Text accepts nonblank Unicode without Cc/Cf/Cs control, format or surrogate
  characters; it does not trim valid text or coerce scalars. Optional None stays
  None, but empty/whitespace text is invalid. JSON escaped astral pairs decode to
  valid Unicode scalars; text and pointer helpers reject unpaired surrogates
  with SourceError, preventing pointer-encoding UnicodeEncodeError.
- Actual document names use conservative ASCII basename validation
  `[A-Za-z0-9_-][A-Za-z0-9_.-]*`. Unsafe paths, encoded components and URL syntax
  are rejected rather than rewritten. No inferred XML suffix. Historical counts
  must be nonnegative integers, and supplied calendar date bounds cannot reverse.

## Review And Remaining Work

Self-reviewed against the brief/spec and exact shared API requirements; no
subagent review performed because expressly prohibited. Parent review/integration
and any commit remain parent-owned. This task makes no complete-history or
end-to-end SEC-service claim: acquisition, coverage continuation, canonical
storage/quota, fact selection, durable citations, three-tool replacement, exports
and Settings remain distinct work.
