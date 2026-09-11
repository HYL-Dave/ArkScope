# Independent Whole-Batch Review

## Assessment

**Verdict: NEEDS FIX. Ready to merge/complete: No, with fixes required.** One
Important/P2 integration defect remains. Readiness after its correction is
conditional on the parent's completed full backend run, exact execution/collection
and skip reconciliation, source identity verification, and verification of the
correction. A passing backend run alone does not close the frontend finding.
The parent run was still unfinished at review close (last inspected log: 88%).

## Complete Findings List

### Critical

None found.

### Important

**I1 / P2: Conflicting catalog variants share React keys and leak stale rows across pages.**

- Location: `apps/arkscope-web/src/settings/SecResearchPanel.tsx:101`.
- Cause: every catalog row is keyed solely by `filing_id`, but the new backend
  deliberately preserves multiple metadata variants of that same filing
  (`src/sec_research/queries.py:397`, `src/sec_research/queries.py:406`). This is
  a supported partial result, not malformed input; the backend conflict test
  explicitly checks both variants. `nextPage` changes the page without unmounting
  the Records renderer (`SecResearchPanel.tsx:231`), so duplicate keys reach React
  reconciliation when moving between nonempty pages.
- Demonstrated impact: rendering a 20-row catalog page containing two variants
  of one filing, then a one-row next page, leaves **two DOM rows**: the expected
  next-page row plus a stale first-page variant. The displayed table no longer
  matches the cursor-bound response. This is observable data presentation
  corruption, not merely a console warning. No stored-data corruption was found.
- Bounded evidence: `final-review-probe.cjs` extracts the unchanged Records and
  its three render helpers with the installed TypeScript AST/compiler and runs
  them with the installed React 18.3.1/jsdom. Only translation/date presentation
  is substituted. It makes no HTTP request or product mutation. The duplicate
  fixture returns 2 instead of 1 row; the unique-key control returns exactly 1.
  `final-review-probe-result.json` retains the rows, duplicate-key warning,
  source SHA-256 and failing exit code 1. This is a renderer probe, not a new
  end-to-end browser run.
- Required correction: give each retained catalog variant a unique rendering
  identity, not just filing identity, without dropping conflicting observations.
  Add a panel regression that pages forward/back through a conflict-bearing
  response and asserts exact DOM rows and no duplicate-key warning. The existing
  browser fixtures have unique filing IDs and do not cover this composition.

### Minor

None found. No additional findings are deferred or reported separately.

## Strengths And Plan Alignment

- Receipt publication, decoded read validation, exact source binding and resume
  agree across Store/service/query callers. Fresh failed intent does not obtain
  authority from retained older snapshots. Explicitly unbound observations are
  preserved without satisfying covered queries.
- Ordinary cursors bind issuer, normalized filters/limit, receipt and bindings;
  immutable fact IDs use the distinct shared-codec kind and insertion watermark.
  Shared domain validation precedes storage availability checks. Exact values,
  filing-date availability, conflict gaps and bounded partial results are retained.
- HTTP adapters remain stored-only for reads and budget-only for settings writes;
  mutation permission calls precede mutation owners. UI read/issuer/acquisition/
  save ownership, exact budget conversion, null capacity/data handling and explicit
  lost-POST reread behavior are consistent with the plan.
- The prior receipt-shape, pre-storage-validation, icon containment, nullable
  typing and human-readable column corrections are present in the integrated
  patch. This review does not reopen their earlier unmerged revisions.

## Scope And Evidence

- Reviewed all 31 files in frozen `final-diff.txt`, once in sequential sections,
  recovering tool-clipped fragments only. Range:
  `483e8f3e2acde8d5ccc81b25eda286789d0ace3e` through
  `97a1aba680c5654d0f723bcf53a7e6e8c4665dff`.
  Frozen review artifact SHA-256:
  `876b04632e23f6a1680310363059142d53bdd63a0a68a1856d2c7935f72e477c`.
- Read the final brief, binding plan, progress decisions/task gates, draft README
  and approved task/R1 reviews. Their approvals were supporting evidence, not
  substitutes for reviewing implementation and tests. README final-gate
  placeholders are appropriate while execution/review remain open.
- Independently compared all **1088** paths in `source-before.json` to current
  bytes: zero differences. Its source-only patch hash is
  `96681417839d40d9b02893d6e6cb28be9e96acffec52c574b13806aa0682e49c`,
  distinct from the review artifact hash above. Tracked worktree status was clean.
- Inspected parent command/log evidence: frontend **121 files / 1737 passed**;
  typecheck and i18n exit 0; i18n 37 candidates/20 signatures/zero debt/20 existing
  allowlist entries; final collection **8823**. These are inspected archived
  executions, not suites rerun by this reviewer. Backend final success, exact
  added/removed nodes and the twelve skip identities remain parent completion gates.
- Read browser harness and fixture authority boundaries, all four result records
  and response captures. Each locale/viewport records 28 HTTP requests, seven
  generated fixture dispatches, no page errors, contained arrow rectangles and
  480px table height. Exact 21-digit strings survive 40/5-row fact pagination and
  subsequent reads after a one-byte quota save. Absent-store invalid period is
  422. Visually inspected `en-390-facts-first.png` and
  `zh-Hant-1280-catalog.png`; these show useful columns and contained controls.
- Inspected the parent's final-source inverse log failures: float changes the
  exact decimal, period-end as-of admits the later value, and latest selection
  removes an explicitly requested historical ID. The restoration log has 3 passes.
  Read `verification.py`'s hash/JUnit/node reconciliation requirements; did not
  execute it before the parent's full run finishes or independently rerun inverses.
- Inspected compressed RAW census and reconciliation: 1119 source reads, 4360
  candidates, 3444 uncertainties; 53 new candidates (44 i18n/7 CSS/2 HTTP), 248
  new uncertainty IDs, no coverage/dependency/untracked-path drift. The supplied
  reconciliation identifies 186 location-only metadata-equivalent IDs; this
  review did not recompute that cross-baseline equivalence. Dynamic URL helpers
  have real browser consumers, but RAW remains review_required, not deletion
  permission or a clean inventory. No whitelist/artifact rewrite is proposed.

## Adjacent Reads And Limits

Focused adjacent reads addressed these named risks only:

- Numeric/date/provenance assumptions: `facts.py`, `common.py`, Store publication,
  and the existing financial mapping/import declarations.
- Snapshot watermark immutability and no implicit migration: snapshot schema,
  immutable triggers, publication transaction and schema verify/install owners.
- Budget-only mutation and observational accounting: `config.py`, CaptureStore
  status/admission, profile dependency and permission helper definitions.
- UI key lifecycle and button ownership: shared `Tabs.tsx`, `Button.tsx`, and
  focused Records/pagination line reads for I1.

No agents, heavy/full test run, browser rerun, production data/config/token read,
provider/live-App call, install, product/test/index/branch mutation, merge or push
was performed. Writes are this report and its minimal scratch probe/evidence.
Arbitrary database corruption, all concurrency interleavings, process RSS and
native Windows/macOS packaging are not exhaustively certified.

Issuer resolution, documents/citations, tools/four transports, export/schedule,
C11/C12, old-schema disposition and SQLite upgrade remain explicitly unfinished
outside this batch. They are not findings or claims of completed first release.
