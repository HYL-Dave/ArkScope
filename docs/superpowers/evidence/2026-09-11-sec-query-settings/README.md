# SEC Stored Queries And Settings

Base: `483e8f3e`. Plan:
`docs/superpowers/plans/2026-09-11-sec-query-settings.md`.
This records the completed query/Settings batch and its verified boundaries.
It is **not the complete SEC Research first release or production activation**.

## Implemented

- Immutable receipts bind each completed source locator to its exact snapshot
  and observation timestamp. A failed new refresh cannot borrow an earlier
  successful source; repeated unchanged bodies retain the correct observation
  checkpoint. Explicit unbound receipts remain readable but grant no authority.
- Stored catalog queries filter forms, amendments and filing dates before paging,
  preserve conflicting metadata and partial historical coverage, and pin cursors
  to CIK/filter/page limit/receipt/snapshot-binding identity. New refreshes cannot
  alter a continued page. Whole observations are not truncated.
- Stored financial queries retain exact decimal TEXT, source hashes/JSON pointers,
  accession/unit/period identities and revisions. Availability uses filed_date,
  not reporting-period end. Competing values/concepts remain visible with gaps;
  unsupported period classification stays unknown. No ratios, inferred Q4, TTM,
  default currency or financial_cache changes occur.
- Explicit fact IDs reopen the retained original rows independently of current
  receipt success. Their shared-codec cursor kind pins an issuer-specific source
  insertion watermark and immutable snapshot digest, not a fabricated receipt.
- Four additional HTTP routes provide config GET/PUT and catalog/facts reads;
  the original stored-status/refresh pair remains. All six have actual Settings
  consumers. Malformed domain/cursor inputs reject before storage inspection;
  valid absent/broken stores stay unavailable without implicit installation.
- Settings manages the exact adjustable 100 GiB default, actual capture charges,
  explicit CIK local reads, catalog/facts filters/pages and refresh/resume. Quota
  reductions preserve existing objects and reads. Save requires confirmed readback.
  Lost POST outcomes remain unconfirmed and never trigger an automatic POST retry.

## Review Corrections

The initial task reviews were not uniformly clean. All raw RED/GREEN reports
are retained, including these corrected findings:

1. Valid JSON with wrong receipt field shapes (null/integer instead of mappings)
   escaped as TypeError. Shared decoded read validation now closes those failures
   without broad exception swallowing; explicit unbound controls still pass.
2. Absent/corrupt storage returned early before domain/cursor rejection. One pure
   validation owner now serves both queries and HTTP. The original reviewer probe
   changed from four failures/three controls to seven passes, with 75 new owned
   cases covering storage states, real cursor matching and no-storage validation.
3. A descendant-span selector widened the pagination icon wrappers and displaced
   arrows outside their buttons. The direct counter selector, computed-style RED
   owner and actual SVG/button rectangle checks fix the demonstrated defect.
4. Query TypeScript envelopes now admit the actual unavailable `data: null`;
   mobile tables prioritize concept/value/unit/end and retain complete IDs last,
   with bounded scrolling. Capacity copy describes accounting, not a fee.
5. The final integrated review found conflicting catalog variants had duplicate
   React keys. Both its isolated renderer probe and the parent's actual
   HTTP/store Playwright run demonstrated two DOM rows for a one-row next page.
   The correction at `5d03c57e` retains both variants, gives stateless catalog rows
   unique page-local rendering keys, and passes forward/back exact-row plus
   duplicate-warning owners. The
   original failure evidence is preserved; a prior clean task review did not
   prove this cross-layer case.

All four task reviews and the final scoped correction review are approved with
no residual findings. The original whole-batch NEEDS FIX verdict and its RED
evidence remain archived alongside `final-rereview.md`; approval is not rewritten
into the earlier report. This does not authorize integration or certify the
unfinished complete SEC first release.

## Verification

Final backend: **8811 passed / 12 skipped**, 867.58 seconds. Collection and
execution are the identical 8823-node set versus the preceding sealed 8446;
377 added, zero removed, and all twelve skip identities unchanged. The complete
run finished before the frontend-only final-review correction. Its original
source freeze and reconciliation are retained, not rewritten after the fix.

Fresh post-fix parent frontend: **121 files / 1738 passed**, versus 119/1692 initially:
37 initial additions, eight R1 additions and one final pagination owner, zero
removed cases. Typecheck and
i18n checks exit 0; i18n remains 37 candidates/20 signatures/zero debt with the
same 20 existing allowlist entries. Existing debug/React warnings are retained.

Parent browser-post-fix uses the actual FastAPI routes, queries, service, SQLite
and capture store under disposable paths. Only SEC transport bodies and the audit
callback are substituted. Four cases cover English/Traditional Chinese at
1280x960 and 390x844. Each records 33 local HTTP requests, ten **fixture** source
dispatches, no page errors, contained pagination arrows and actual table geometry.
The scenarios cover absent-store 422 rejection, config-only mount, partial refresh,
resume-only pending source, stable back/next pages, filters/observed empty, exact
21-digit values, lost POST/GET reread, quota reduction and preserved local reads.
The final fixture includes conflicting recent/history catalog variants, exact
20->1->20->1 displayed rows, cached navigation and zero duplicate-key warnings.
Earlier browser-final has the pre-conflict fixture (28 requests/seven dispatches);
those earlier results are retained as earlier checkpoints, not the final gate.
Screenshots were visually inspected; only browser-local Vite assets were fetched.

Source freeze covers **1088 tracked source/test/frontend paths**, patch SHA256
`96681417839d40d9b02893d6e6cb28be9e96acffec52c574b13806aa0682e49c`.
The completed reconciliation verified every path unchanged during the full run.
The later frontend-only correction is separately bound by
`post-fix-verification.json` and `source-final.json`; all **798 backend paths**
remain byte-identical and exactly the component/test pair changed. Final source
patch SHA256 is `c4603ccf2f249cfc2c0c48f65c9e9920b736f874a4713b1971d7588afec1a0a9`.
`final-gates.json` binds the completed post-fix frontend/browser commands/logs
and verifies all1088 finalpaths unchanged. The backend suite was not redundantly
rerun after a frontend-only fix and is not claimed to have been.
Task 1's five inverses, its read-shape correction inverse and Task 2's three
inverses fail named owners and retain restored/in-memory source hash evidence.
These are additional executions, not additions to the repository's test count.
After the final shared-validation extraction, the parent reran all three facts
inverses against the final code: one owned assertion failure each, then three
normal owners passing. Mutations affect only loaded globals in separate processes,
never source files or the concurrently running full suite. The new hash files bind
those checks to the final source freeze, not merely the earlier Task 2 checkpoint.

Runner observations are not hidden as product fixes: an initial frontend runner
used UTC and failed four existing Asia/Taipei timestamp expectations; changing
only the runner timezone restored the untouched 1692-test baseline. Initial
browser assertions assumed a newest-first fact order, while the specified order
is deterministic but not newest-first; raw response/screenshot evidence shows
exact values preserved on their actual pages. The fixture assertion was corrected.
The first census launcher omitted Node from its closed PATH and failed before
publication; the supplied complete PATH succeeded. No product workaround followed.

## Census And Cleanup

Final source census (`census-post-fix`): **1119 read / 4360 candidates / 3444 uncertainties**.
Against the previous sealed census: 53 new candidate IDs (44 locale leaves,
seven CSS selectors, two HTTP routes), 248 new uncertainty IDs (216 frontend,
32 SQL), zero coverage reductions, dependency changes or new untracked names.
Of the 248 new uncertainty IDs, 186 have identical previous metadata after
removing only id/line/column. That comparison explains location churn; it does
not silently erase the raw uncertainty records. Exit remains **2 / review_required**.

The previous status/refresh HTTP candidates are now syntactically consumed.
The new `/filings` and `/facts` routes are real consumers despite the scanner's
failure to resolve the helper-built query URL. The browser captures every actual
request. Shared translator props account for the 44 new locale candidates, and
runtime state/shared-control selectors for the seven CSS candidates; the frozen
component, rendered text, state cases and screenshots provide the separate use
evidence. Nothing is deleted or whitelisted merely to make the census green.

Follow-on scanner maintenance belongs to `tests/repository_inventory.py` and its
frontend helper/tests: resolve composed query URLs and typed shared translator
bindings, preserving explicit uncertainty when resolution is impossible. The
existing removed-surface locale queue remains CENSUS-I18N-001, CSS EIR-001 and SQL
union-schema preparation CENSUS-SQL-001. This batch does not clear those queues.

## Rulings And Remaining Boundaries

- Preserve AUTOINCREMENT for committed receipt ordering and exhaustion behavior.
  SQLite owns sqlite_sequence; private SEC verification/teardown must not touch
  it. Changing the policy later requires an explicit ordering design, not merely
  removing the keyword. Official references: https://www.sqlite.org/autoinc.html
  and https://www.sqlite.org/fileformat.html#the_sqlite_sequence_table .
- This is incremental structured-storage administration with explicit CIK, not
  guessed ticker identity or the complete Research UI. The tradeoff is a temporary
  less ergonomic issuer input until reviewed resolution is connected.
- Query working admission is bounded to 100000 filtered rows, 64 MiB encoded
  metadata/rows and 1024 sources; envelopes to 256 KiB and 1..100 whole rows.
  Exhaustion yields a typed partial result, or unavailable if no rows can be
  admitted. Cursors cover only the admitted selection; narrowing is sometimes
  needed. These are not measured whole-process RSS limits.
- Historical fact IDs deliberately do not depend on current receipts; their
  distinct cursor kind shares the codec. Conservative period classification may
  remain unknown when comparative or YTD context cannot be established.
- The ten-minute client wait is not a total server deadline or cancellation
  guarantee. Receipt timestamps are observation checkpoints, not last-success
  claims for every source. Parallel workers had disjoint code ownership and
  parent-serialized index permission; final integration remained a shared gate.

Still open: issuer resolution, original filing reads/citations, three model-facing
tools/four transports and subagents, persisted Research citations, portable export,
the default-disabled schedule, C11/C12 news/collector boundaries and actual old
schema disposition. Existing Research tools were not removed ahead of replacement.
SQLite runtime upgrade remains after the main cleanup/SEC work. POSIX fixture
success does not certify native Windows/macOS packaging. No new backup helper.

No real provider-data call, production DB/config/token read/write, actual schema
activation/drop, dependency install, App restart, merge or push was performed.
The offline harness blocks production paths and provider network in its own
process and isolates child environment; it is not an OS sandbox. Temporary Vite
served only browser fixture verification, not the user's running application.

## Replay And History

Scripts retain root derivation for `.superpowers/sdd/2026-09-11-sec-query-settings/`
under an isolated worktree. Restore only this batch's scripts/needed evidence to
that layout for replay; do not execute them directly from the evidence directory.
`run_checks.py` records complete commands, environments, logs and exit codes.
No fixture database, HOME, token file, cache or captured user content is archived.
The browser fixture uses generated source bodies and the already-installed local
Playwright Chromium; it never needs production credentials. `artifact-manifest.json`
binds every sealed file; compressed logs are explicitly tracked despite ignore rules.

Implementation history before evidence closeout:
`0658ebf0` plan; `e207b3ad` receipt/catalog queries; `7a1b9d99` decoded receipt
validation; `baecc18c` Settings consumers; `e07e459a` financial queries; `05edf925`
HTTP/config adapters; `c6e2e435` frontend review fixes; `420e4759` pre-storage
validation; `97a1aba6` task gate documentation; `5d03c57e` final catalog rendering
fix. These are ten commits, not a single change. Final documentation and evidence
closeout commits are listed in the branch history separately. No merge occurred.
