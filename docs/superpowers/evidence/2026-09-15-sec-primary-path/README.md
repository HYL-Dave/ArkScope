# SEC Primary-Document Relative Path Repair

Base: `a2b94530`, current-runtime isolated desktop hand test on 2026-09-15.
No production DB access, schema change, runtime switch or provider/model call
was needed to diagnose and test the repair. The user's completed SEC request
left its original response bytes in the isolated capture store.

## Observed Failure

- Receipt: `partial`, completed `companyfacts`, pending `submissions`.
- Gap: `{"source":"submissions","code":"source_invalid"}`.
- Financial observations admitted: 25,135; catalog snapshots: zero.
- Source: `https://data.sec.gov/submissions/CIK0000320193.json`.
- Original response: 164,091 bytes; SHA256
  `cb90ffafc5b6f997b60aa109e07008223ad35abe896ec7918fd43652b4057329`.
- Parsing these exact bytes failed with `invalid_document` at
  `/filings/recent/primaryDocument/0`, value `xslF345X06/form4.xml`.

The old parser required a basename even for catalog metadata. One valid relative
path therefore rejected the complete submissions source. No provider response
was trimmed or rewritten to obtain a smaller successful snapshot.

## Boundary

Catalog primary-document metadata now accepts literal safe relative components.
Every component retains the previous ASCII-basename validation; absolute paths,
empty/dot/traversal components, percent encoding, backslashes, URL schemes,
queries, fragments and control characters remain rejected.

Directory items, explicit `file:<basename>` reads and document-entry citation
validation continue to use the strict basename validator. Catalog metadata does
not authorize fetching nested files or guessing a basename by stripping XSL
prefixes. Nested primary-document acquisition remains subject to the existing
observed-directory rule and can return `document_not_in_directory`.

## Verification

- RED: 8 failed / 58 passed / 315 deselected before production changes.
  Failures cover recent/history paths, stored filing citations and durable
  resume with companyfacts already complete.
- Current runtime: 381 parser/store/citation tests passed; 653 additional
  document/route/query/four-channel/reference/export workflow tests passed.
- Prebuilt candidate: the same 1,034 case IDs passed in one run, without skips
  or failures. This comparison does not activate the candidate for the App.
- Independent static review found no production defect and requested one more
  citation-boundary regression. A consistently forged nested directory entry is
  rejected; the added case passed on both engines. An in-memory mutation that
  substitutes the broader metadata validator fails that case as expected.
  Including these supplemental runs, both engines cover the same 1,035 passing
  case IDs. This is aggregated coverage, not a single 1,035-case run.
- Offline replay of the exact source bytes now parses 1,000 filings, including
  658 nested primary-document paths, 11 `10-K` rows and one historical-file
  pointer. Replay was read-only and did not modify the hand-test receipt.
- [Archived test results](checks/summary.json) and JUnit XML in `checks/` preserve
  the RED failures and both engines' exact selected case identities.
- Full backend suite and complete live hand-test checklist were not rerun as
  part of this focused repair. The user must still resume acquisition and verify
  live catalog/document behavior. Existing `period_unknown` fact gaps are not
  repaired or relabeled by this change.
