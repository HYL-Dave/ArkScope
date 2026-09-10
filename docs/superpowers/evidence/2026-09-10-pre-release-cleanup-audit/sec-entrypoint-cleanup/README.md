# SEC Intake And Entrypoint Cleanup

The bounded implementation plan is complete on
`codex/listing-sec-macro-convergence`, starting at `df97352b`. The final broader
review of `df97352b..6220ba27` found no actionable patch-introduced findings or
integration blockers. [Final review](final-review.md) records its exact scope
and evidence checks. This is separate from the completed first-leaf cleanup.
No merge, push, App restart, provider call or production-store access is
authorized by these source changes. No stored data or schema has been deleted.

## Completed Checkpoints

| Commit | Scope | Verification |
| --- | --- | --- |
| `0ee801cd` | Replace the live API specification's abandoned edgartools recommendation with actual EDGAR source/financial/transport owners; rename the active transport/import guard without weakening it | 32-case baseline; new documentation owner fails RED; final 33 passed; independent review clean |
| `06511f44` | Delete company-event collector, scheduler mapping and dedicated Settings copy/cache path; current admission excludes unretained SEC cases without a cutover flag; background admits listing authority only; raw operator accounting is independent | 738 affected backend passed; 94 frontend passed; typecheck/literal scan passed; two admission mutants each fail both journal states; independent spec/quality review clean with 17 fresh passed; parent separately ran 111 passed |
| `83eeb5ef` | Current controller owns worker lifecycle and strict confirmation DTO; old case-web router/controller/preflight and last cutover flag deleted; current routes mounted before the retained generic historical reader | 951 affected backend passed; 183 restored checks passed; four mutants caught; independent spec/quality review clean |
| `66b53ee5` | Correct the second exact App route-count test from 228 to 221 after deleting seven old HTTP entries | Parent broad regression exposed it; focused RED reproduced the count mismatch; complete API file then passed 25 cases. Only one assertion value changed |
| `302106d2` | Remove unmounted UI, old-only clients/parsers/fixtures and 122 locale leaves per language; move current start/gap validation to current contracts | 1,692 full frontend passed; 619 affected frontend passed; 161 scoped backend passed; two parser mutants caught. Independent spec/quality review approved |

These selections overlap and are not additive. They are not a repository-wide
test result. Source implementation and final regression/census are recorded
below; the final broader review independently reconciled those artifacts and
the integration boundaries, without re-running the suites. The Task3 review's
sanitizer verdict is intentionally bounded: the
trusted exception classes still accept short lowercase/underscore codes, as
before. This is not a universal secret redactor or an exhaustive code allowlist.

Whole-frontend baseline after Task 2: 126 files / 1,850 passed in 13.40s,
`task4-full-frontend-baseline.xml`. This precedes old-screen removal, so it does
not stand in for final frontend validation after Task 4.

## Current Data And Capability Boundary

The existing `get_sec_filings`, SEC financial/identity configuration, provider
checks, prices/news/SA data and current target investigation remain. The new
three-tool SEC research service is not implemented by this cleanup.

`compose_security_lifecycle_audit` reads all original inputs for the disposal
manifest; it does not admit old SEC work into current execution. Its equality
check still requires every observed/persisted/source-missing case to be counted.
Current composition separately preserves transition-referenced history. Keeping
that read obligation is not keeping the abandoned collector as a fallback.

Actual old schema disposition remains gated on a narrowly authorized current
store inventory, reference closure, backup and approved disposition digest.
`../sec-schema-ownership.md` records source-level ownership without inventing
production counts or classifying all lifecycle-prefixed tables as abandoned.

## Test Accounting

Task 1 adds one documentation guard; the renamed transport guard is unchanged
in behavior. Task 2 deletes 26 collector-only instances, moves one live CIK-cache
test intact, adds eight scheduler/population/absence instances, and replaces one
old installed-gate instance with four journal-independent cases. Task 2 net:
**-15 backend instances, +1 frontend instance**. The old pipeline/fixture
assumptions were not simply suppressed: current route tests use real listing
observations; old SEC facts remain covered by the explicit audit read.

Task3's accounted test universe grows from 361 to 380 cases (**+19**). The report
names every moved, added and deleted family. Its 951-case broader selection is
not added to that accounting. The old TypeScript receipt roundtrips remain at
this checkpoint because frontend removal is Task4; their later removal must be
accounted separately if the old UI parser no longer has a real consumer.

Parent final backend verification is partitioned: A excludes all lifecycle,
security_lifecycle, absence and direct frontend-source tests; B runs those on
the final frontend tree. Final collected IDs equal the recorded union.
The initial A route-count failure is preserved, not rewritten as a clean run;
the separate complete API-file rerun supersedes that file's failed result.

Task4 removes 204 old-only frontend cases, adds 46, and renames four retained
cases while removing their old-only branches: **1,850 -> 1,692 (-158)**. Its
literal node-ID diff is 208 removed / 50 added; the four rename pairs and exact
IDs are archived in `task4-test-census.json.gz`. The five Python removals are
the obsolete TS run/usage contract's four cases and the old review-list parity
case. Backend history/receipt/current-vocabulary checks remain. Whole-backend
collected count therefore reconciles with the previous leaf checkpoint:
7,953 + 1 (Task1) - 15 (Task2) + 19 (Task3) - 5 (Task4) = **7,953**.

## Final Regression And Census

Code checkpoint: `302106d2`. `verification-summary.json` records:

- A: 5,488 passed, 12 skipped, one stale route-count failure; all 25 API cases
  rerun successfully with identical IDs after `66b53ee5`.
- B: 2,452 passed, no errors/failures/skips.
- Final collection: **7,953 unique nodes**, zero overlap, zero missing or
  unexpected nodes. Combined result: **7,941 passed / 12 skipped**. The skipped
  cases explicitly require live SEC or IBKR; they were not bypassed cleanup tests.
- Only three Python test files changed after A began: its API file was rerun,
  and the two removed/trimmed TS-collateral files are in B. Python runtime
  sources did not change between partitions.
- Frontend: **1,692 passed / 119 files**. Typecheck and production build exit 0.
  Vite reports a main JS chunk of 1,155.31 kB and its >500 kB warning; that warning
  is not hidden by increasing a threshold or unrelated bundle restructuring.
- The Task4 reviewer matched the 112 stderr-bearing frontend cases against the
  baseline: identical React `act(...)` warnings, no new/changed stderr cases.
  i18next debug output also remains. Passing does not mean warning-free; these
  inherited test-harness/debug issues remain separately scoped work.

`final-census.json.gz` compares with the original preserved mechanical baseline:
1,097 source files read, 4,320 candidates, 3,389 uncertainties. The 30 coverage
reductions are actual removed source/test files. No dependency metadata or
main-worktree untracked-name drift was observed. It deliberately exits **2**
with `review_required=true`, not a clean-repository verdict:

- **193 new unique candidate IDs:** 88 CSS selectors (EIR-001), 100 bilingual
  locale leaves (50 per locale; remaining helper/dynamic-consumer checks), and
  five HTTP endpoints whose old UI clients were removed (C04, exact paths in
  `../sec-schema-ownership.md`). These are remaining review work, not silently
  accepted deletions or claims that all are unreachable.
- **188 new uncertainty IDs:** removing only ID/line/column from comparison
  reduces the actual added multiset to two escaped translation bindings in the
  new Settings test. The other apparent additions are position churn; the raw
  report and uncertainty are retained, not rewritten to zero.
- No new Python-orphan or dependency-removal candidate was introduced. This
  does not discharge pre-existing candidates or unresolved dynamic references.

All intermediate failed runs remain distinguishable in the Task 2 report and
compressed XML. Initial RED fixture errors were corrected before the feature
RED result (10 failed / 3 passed). A broad lifecycle/identity expansion had
17 failures from old SEC fixtures; the final 20-file affected selection includes
those corrected files and passes 738/738. That is not relabeled as a rerun of
the earlier 2,716-case expansion.

## Offline Runner

Tests use an empty inherited environment, isolated temporary store/HOME/lock
paths, an inactive `.env` loader, disabled plugin autoload and explicit AnyIO.
The temporary runner denies real production-store/config reads and external
network, permits loopback fixtures and bundled-binary `--version`, and permits
fake CLI launchers only inside its own resolved fixture root. It is not an OS
sandbox or a live provider validation. No product behavior/test expectation was
changed to exempt a real provider launcher.

`offline_pytest.py.txt` and `collection_manifest_plugin.py.txt` archive the exact
temporary runner/collection hooks as evidence, not product modules. The runner's
relative ROOT calculation assumes its original ignored SDD location recorded in
the reports; the archival `.txt` copy is not advertised as a runnable relocated
tool. The final collection hook uses pytest's own JUnit name mapping, including
parameter IDs, to check partition coverage without an ad-hoc node-ID parser.
The four `task4-*.mjs.txt` files likewise archive the exact temporary AST
inspection/editing scripts reviewed with the locale/reference evidence; they
are not retained executable maintenance entrypoints.

The report files preserve their original reviewed commit and scope. Source
links refer to that reviewed tree; XML artifacts are archived alongside this
record rather than depending solely on the ignored execution workspace.

Final closeout only changes documentation and archives the review/ledger; the
tested runtime remains `302106d2`. The reviewer also matched the archived source
hashes and reconstructed the seven removed HTTP routes. The execution scratch
directory is disposable after archival; the named worktree and branch remain
available for inspection. Integration, actual-store inventory/disposal and the
remaining shared-helper/endpoint cleanup are not completed by this closeout.
