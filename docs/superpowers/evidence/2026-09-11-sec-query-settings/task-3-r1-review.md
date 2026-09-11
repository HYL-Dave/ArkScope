# Spec Compliance

- **Approved for R1: I1 resolved.** `src/api/routes/sec_research.py:132` invokes shared validation before path resolution, Store construction and installation checks. Malformed domain operands and cursor syntax/request mismatches therefore reach the existing closed 422 handler independently of storage availability.
- Scope is I1 plus new breakage introduced by frozen `task-3-r1-diff.txt:1`: base `c6e2e435970c47252970767c9e40300f79ddba23`, head `420e475960bf8a4cacc2f14d4866315c118085ff`, exactly five authorized Python/test files, 162 insertions and 24 deletions. No unrelated requirement or original finding was reopened.
- **Separate gates remain pending:** the parent's final live-HTTP browser and full-backend verification. This task-scoped approval does not certify those gates or whole-batch completion.

## Strengths And Checks

- **One domain rule set:** `src/sec_research/queries.py:71` extracts the existing filings normalization without changing defaults or accepted values; `src/sec_research/fact_queries.py:52` retains the prior facts rules with explicit defaults. `queries.py:93` shares these rules with HTTP and domain callers, with no adapter-side selector or cursor reimplementation.
- **Normalized filters drive real selection:** `src/sec_research/queries.py:351` consumes normalized forms and dates; `src/sec_research/fact_queries.py:194` consumes the normalized facts filter dictionary. Strict boolean/limit values remain unchanged. No observation, decimal, currency, SourceRef or paging-selection rewrite appears in the extraction.
- **Cursor checks retain their ownership:** `src/sec_research/queries.py:85` reuses the existing decoder/hash rules for issuer, query kind and normalized filters, including limit. Line 93 selects the separate `fact_ids` cursor kind. Receipt lookup and binding checks remain at line 130; retained-snapshot watermark validation remains at line 160. Valid requests with storage-dependent bindings still return unavailable when storage is absent/corrupt, rather than being prematurely rejected.
- **Regression tests exercise real boundaries:** `tests/test_sec_research_routes.py:505` covers 60 absent/corrupt/installed cases, forbids path resolution on invalid input and checks unchanged DB bytes/no capture root. Line 537 obtains real catalog/facts/fact-ID cursors and covers 12 valid-unavailable versus changed-limit mismatch cases. `tests/test_sec_research_fact_queries.py:84` covers three pure normalization cases with Store construction/read methods forbidden.
- **Adjacent named risk, stale callers after `_filters` rename:** a focused caller search limited to `src/sec_research` and `tests/test_sec_research*.py` found no remaining references to the removed facts helper. The only normalization entry references are the extracted helpers and shared validator (`src/sec_research/queries.py:97`, line 99).
- **Adjacent named risk, lazy-import cycle/owner construction:** `src/sec_research/queries.py:99` imports the facts normalizer only inside the already-defined validator; `src/sec_research/fact_queries.py:194` calls it at query execution, not module initialization. The inspected existing metric-import entry (`data_sources/sec_edgar_financials.py:46`) imports definitions, and R1 introduces no provider/profile/capture constructor call. Archived forbidden-owner and pure-validation cases supply execution evidence; no transitive provider audit was broadened from this check.

## Issues

- **Critical:** None found.
- **Important:** None remaining in this scope; original I1 is closed.
- **Minor:** None found.

## Archived Verification

Artifact paths below are relative to this plan directory. Results were inspected, not rerun.

| Evidence | Verified Result |
| --- | --- |
| `task-3-r1-red/results.xml:1` and `command.json:1` | 57 failed, 18 passed, 171 deselected; exit 1. Failures group as 48 forbidden-owner/path-resolution failures, six HTTP 200-versus-422 failures and three missing-validator assertions. |
| `task-3-r1-green-focused/output.log:7` | 318 passed in 7.10s; exit 0. Includes all 75 new R1 cases. |
| `task-3-r1-review-probe-green/output.log:3` | Original seven-case reviewer probe: 7 passed in 0.81s; exit 0. Probe source at `task-3-review-probe/test_absent_validation.py:8` still matches the original cases and assertions. |
| `task-3-r1-green-sec-api/output.log:16` | 953 passed in 32.76s; exit 0. |
| `task-3-r1-green-before-commit/output.log:16` | 953 passed in 33.05s; exit 0. Final serialized-commit evidence. |

- Parsed all five archived JUnit files and command records with standard JSON/XML parsers. Every GREEN suite has zero failures/errors/skips and no selection exclusions; RED has zero errors/skips. Inspected GREEN logs are clean, with no warnings; the RED log also contains no warning noise.
- The final 953-case XML includes the existing receipt/cursor binding and refresh/restart/relocation owners, alongside all 75 new R1 cases. This supports retaining storage-dependent continuation checks rather than merely passing the original malformed-input probe (`task-3-r1-green-before-commit/results.xml:1`).
- Read the R1 report and serialized-commit appendix (`task-3-report.md:307`, line 432) and reviewed the frozen diff once. Line references were derived from the retained diff. Outside-code exploration was limited to the two adjacent named risks above; no additional probe or test run was warranted by an unanswered risk.
- Only this report was written. No product, index, branch, original probe or archived evidence was modified; no git command, provider/production access, live application, subagent or heavy test run was used.

## Assessment

**Task quality: Approved for R1.** Shared pure validation closes I1 before any storage-dependent early return, and real query execution consumes the same normalized rules. No new regression or blocking quality issue was found in this narrowly scoped diff; parent browser/full-backend gates remain separate.
