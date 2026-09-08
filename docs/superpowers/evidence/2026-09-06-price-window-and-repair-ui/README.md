# Fifteen-Day Price Window And Repair Status

## Scope

The September 6 user amendment changes routine price backfill from five to
fifteen calendar days. The direct collector and actual scheduled worker share
one Python default. The coverage API, repair preview and Settings also default
to fifteen; explicit caller/UI windows remain supported. This is a deliberate
contract change, not a claim that the old collector always used fifteen days.
The old five-day reproduction remains an explicit-override regression.

The coverage view includes its anchor date. An unfinished session is diagnostic
information, not an eligible repair gap. This is not fifteen trading days and
does not automatically bootstrap every new member's entire price history.
Existing prices are not overwritten and older windows remain explicit work.

Task 4 now exposes bounded, paginated repair history from existing private
request journals. A read-only SQLite transaction keeps manifest validation,
request counts and cached responses on one snapshot. History never creates a
journal, launches a worker, reads credentials or dispatches a provider call.

Completion comes from actual price coverage at the original plan's clock,
not a successful worker summary or a matching number of received responses.
Missing responses are described as unrecorded, not proof of an orphan worker.
Local collection activity is separate and becomes unknown if its read fails.
One corrupt journal remains unavailable without hiding healthy operations.

## Resume Contract

- Resume is explicit and confirmed against the original scope and maximum
  remaining new requests. Reloading the page never submits a write.
- Received but uncommitted bars can resume with zero new provider requests.
  Empty responses or already-written partial data do not offer useless resume.
- Unknown or failed requests are not reissued under an old plan. Independent
  unattempted targets can still resume within their remaining request budget.
- Removed target scope blocks resume. Unrelated SA/current-universe additions
  do not change an existing repair or require global capture control.
- The POST boundary repeats both write permissions, scope and actual coverage.
  Already-complete work returns `nothing_to_repair` without starting a thread.
- Backend-owned serialized fixtures also exercise the frontend runtime parser.
  Raw responses, contract IDs, paths and plan seals are not public history DTOs.
- Completion is read by the selected operation's exact ID, not by scanning the
  first history page. A returned ID mismatch is rejected. This keeps older
  paginated operations verifiable without extra page traversal or dispatches.

## Verification

The full backend passes 6,043 tests with 12 skips and three existing edgartools
deprecation warnings. The 73-file lifecycle/price/maintenance integration passes
1,806 tests. Results are bound in `verification.json`, with exact node manifests,
report hashes and independently restored mutation reports. All nine backend
mutations fail named owners in the 494-test price focus, and all seven frontend
mutations fail named owners in the 138-test UI focus. Both complete focuses
restore to green. The full frontend passes 1,432 tests, with runtime DTO, reload,
confirmation, exact-ID completion and locale coverage. Typecheck, production
build, the i18n literal check and `git diff --check` must also pass before sealing.
The existing Vite large-chunk warning is not a new build failure.

The actual Settings components were rendered with only intercepted fixture
APIs in Chromium, not a running ArkScope backend. Eighteen scenarios cover
English/Traditional Chinese, 1440/390/320-pixel widths, normal completion,
lost POST responses and malformed history. There are thirty screenshots,
including confirmation dialogs. All tested screens are nonblank and pass
control overlap/clipping, text overflow and page-error checks. Opening/reloading
does not write; confirmation makes exactly one fixture POST. Provider calls: 0.
See `browser/results.json` and the screenshot files.

RED artifacts distinguish implementation failures from harness mistakes.
The route RED was repeated with a harmless thread recorder after the first
version's `pytest.fail` stub also caused AnyIO teardown errors. The full backend
then found a second exact-route inventory still expecting 199 routes; both
inventories now explicitly own both new GETs and expect 201, without weakening
the retired-route guards. A late pagination review added separate RED owners
for exact-ID reads and old-operation completion. The intermediate full backend
was deliberately interrupted after 3661 passes/12 skips to finish that fix;
it is not counted as full-suite admission. A bare root `pytest` command additionally collected
historical sealed maintenance scripts that reference a retired policy symbol.
Those artifacts were not rewritten. The current full backend command is
`python -m pytest -q tests`; active maintenance owners are included separately
in `integration-files.json` and the mutation focus.

Final sealing also stopped on TypeScript TS2345: the nested polling function
passed nullable React state to the exact-ID reader. `check-failure.json` retains
that actual command failure. Capturing the already-validated ID in a local
string fixes the boundary without a non-null assertion or a wider API type.
Frontend tests, mutations, browser scenarios and build checks are rerun after
that change; the Python product/test inputs are unchanged.

Reproduce offline with the test files in `integration-files.json` and
`ui-focus-files.json`. `scripts/run_mutations.py` requires new staging/temp
directories outside the repo, copies source without production data or `.env`,
and restores each independent mutant before the next one. Its backend focus
contains 31 files; its UI focus contains eight. `scripts/run_browser.py` starts
and stops an isolated fixture preview on an unused loopback port. It never
starts the App or permits unrecognized API/provider requests.

## Authority And Remaining Work

This slice makes no production DB read/write, live provider request, migration,
App restart, commit, merge or push. No new persisted Settings field is needed;
the existing request-journal schema is unchanged.

The earlier authorized live result remains in
`../2026-09-06-recent-price-repair-live/`: 64 measured requests, 4,940 insert-only
RTH bars and independently confirmed complete coverage for 183 symbols on all
eleven August 21-September 4 sessions. It was not rerun or resealed here.
Old failed jobs were not erased. The cause assessment remains bounded:
five-day collection after universe expansion explains the reproduced gap,
but missing historical traces prevent proving every old failure's exact cause.

Tasks 5-9 of the lifecycle redesign remain open: whole-case reclassification,
governed one-command confirmation, concise UI/Research projection, explicit web
investigation and final cutover. This price slice does not declare that larger
feature complete or request the user's final hand-test batch.
