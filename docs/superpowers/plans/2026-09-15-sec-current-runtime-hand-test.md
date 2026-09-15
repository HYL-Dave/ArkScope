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

## Settings And Local Data

1. Open Settings > Data & Sync > SEC structured data. Verify capacity, stored
   state and daily acquisition status load. A fresh install has a 100 GiB
   configurable budget; reading Settings must not enable the daily schedule.
2. Enter one issuer CIK (for example `0000320193`). Use Read Local first. If no
   capture exists, expect unavailable/unobserved rather than fabricated empty
   coverage. Use Update Structured Data once with a valid existing SEC identity.
   Check the receipt, observed time, coverage and any typed gaps.
3. Browse filings and financial facts, apply one date/form/concept filter, then
   next/back where available. IDs, accessions, URLs and precise values must remain
   intact. Changing a filter must start a fresh page chain, not reuse a cursor
   from a different query.
4. Open a filing's document-reader icon. Acquire/read that one document, inspect
   a section or search result, close it and reopen. Verify the cited capture and
   text still agree. Missing or ambiguous sections must be explicit, not guessed.

## Research And Existing Workflows

1. Use one selected inexpensive task model; no need to rerun every model. Ask for
   the issuer's latest annual filing and one reported financial value with a
   filing passage as evidence. Confirm the selected route and SEC tool results,
   then revisit the conversation and reopen its saved SEC citation.
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
