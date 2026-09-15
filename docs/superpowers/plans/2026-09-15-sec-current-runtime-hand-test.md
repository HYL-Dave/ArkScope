# SEC And Current-Runtime Hand Test

Run after the cleanup branch's final acceptance is recorded. This checklist is
for the existing interpreter, before replacement-runtime selection/activation.
Do not switch Python, install a SQLite library, supply a source archive, or run
schema reset/cleanup just to start this check. Production restart remains a
separately agreed user action; verify the App is actually running the tested
branch, not the old master worktree.

C20's old query table and two rows have now been removed under separate user
authorization. Do not restart old master for this check: its old store
initialization can recreate an empty legacy table. No interpreter switch or
automatic App restart accompanied that removal.

The first isolated hand test exposed a submissions parser defect: a valid
`xslF345X06/form4.xml` primary-document path rejected the whole catalog while
companyfacts succeeded. See the [repair evidence](../evidence/2026-09-15-sec-primary-path/README.md).
After restarting the corrected hand-test sidecar, use Resume once to continue
the pending submissions source. Keep the already completed companyfacts capture;
do not clear/reset the store. A pending receipt stays pending until actual
acquisition/persistence succeeds, regardless of the parser repair.

The user subsequently confirmed catalog/fact display and pagination on the
isolated current-runtime App. Filtering required an unrelated-looking Read Local
button, and the embedded reader exposed 27 ambiguous sections for the selected
2025 Apple 10-K. These were not accepted as a usable completed workflow. The
user approved local automatic filters, removal of the full Settings reader,
official browser links and continued backend/citation validation. Retest the
revised workflow below; do not restore the discarded reader to follow the old plan.

## Settings And Local Data

1. Open Settings > Data & Sync > SEC structured data. Verify capacity, stored
   state and daily acquisition status load. A fresh install has a 100 GiB
   configurable budget; reading Settings must not enable the daily schedule.
2. Enter one issuer CIK (for example `0000320193`). Use Read Local first. If no
   capture exists, expect unavailable/unobserved rather than fabricated empty
   coverage. Use Update Structured Data once with a valid existing SEC identity.
   Check the receipt, observed time, coverage and any typed gaps.
3. After Read Local selects the CIK, browse filings/facts and edit a date/form/
   concept filter. After typing settles, the local results must update without
   another Read Local click or any SEC acquisition. Check next/back where
   available. IDs, accessions, URLs and precise values remain intact. Changing a
   filter starts page 1 with a fresh cursor chain; stale responses cannot restore
   a previous selection. Merely typing a different CIK does not start acquisition.
   The revised form control is a multi-select dropdown: options come from the
   full locally observed catalog, not just the visible page. Select two types,
   then All, and verify both queries. Incomplete options retain an explicit
   partial/unavailable state rather than claiming complete source coverage.
4. Use the SEC original link to open the official filing in the browser. No
   full-document reader remains in Settings. Verify retained passages through
   the Research citation flow below, not by restoring a retired Settings route.
   In an isolated HOME, verify its browser handler independently of the normal
   desktop default. A successful opener exit does not prove the child browser
   loaded the document. The current hand-test profile uses a separate Chrome
   profile; do not loosen production filesystem access to run Snap Firefox.

## Research And Existing Workflows

1. Use one selected inexpensive task model; no need to rerun every model. Ask for
   the issuer's latest annual filing and one reported financial value with a
   filing passage as evidence. Confirm the selected route and SEC tool results,
   then revisit the conversation and reopen its saved SEC citation.
   Section extraction v5 applies to new captures. Old pinned captures retain
   their original index and exact bytes; they may still require literal search
   or the whole-text cursor when their historical section index is unavailable.
   Any new acquisition must be a deliberate user/model task, not an automatic
   side effect of opening a stored citation or changing a Settings filter.
2. In the SA extension, run the usual incremental synchronization once. Confirm
   native-host communication, article/market-news views and body status still
   work. The 33,000-ID and integer-boundary stress cases are automated tests,
   not a requirement to create that much live data for hand testing.
3. Revisit an existing report/memory and a current Research conversation. Confirm
   they remain readable. The disposed `agent_queries` table was separate from
   current conversations; do not restore it or repeat disposal as a test step.
4. Optionally run one SEC daily job manually and inspect attempted/confirmed/
   failed/deferred counts. A partial result must not masquerade as complete.
   Enabling a recurring schedule is optional and not implied by saving capacity.

Record the active branch revision, selected provider/auth/model/effort, action,
expected versus actual result, and any visible error code. Do not include tokens,
API keys or private filing/research content in diagnostic screenshots/logs.

Export/restore, orphan cleanup and schema reset have automated disposable-store
coverage. Never test destructive maintenance or restore over production data;
use a separate fixture directory and explicit approval when needed.

Passing this checklist validates current Linux workflows, not prebuilt-runtime
admission, Windows/macOS support or the planned Python sandbox.
