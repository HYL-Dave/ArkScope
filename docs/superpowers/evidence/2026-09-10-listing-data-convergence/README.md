# Listing, Financial Freshness And Macro Verification

Base: `30bb31c7`. Worktree: `codex/listing-sec-macro-convergence`.
This record covers implementation and synthetic/offline verification, not a
production listing decision, provider canary, deployment, merge or push.

## Scope And Status

- [x] Same-security automatic rename policy and financial-cache copy implemented.
- [x] Rename review findings reproduced before their fixes.
- [x] Independent rename/macro review findings corrected and reviewed again.
- [x] Final combined backend regression run complete.
- [x] Macro scheduler and named-job result handling complete and reviewed.
- [x] SEC research design written separately; implementation awaits user review.

The SEC document is
`docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`.
It specifies catalog/facts/source storage, three usable Research tools, durable
citations, all four transports, portable exports and a separate default-off
schedule. No SEC storage, tools, migration or replacement collector is claimed
implemented by this packet.

## Rename Contract

Unattended renames require an exact ticker event, a matching Composite FIGI,
current successor trading evidence and all existing old-listing checks. The
event must be inside the established automation window starting 2025-01-01.
Conflicts, open positions, missing checks and reactivation of an archived
successor membership require review. A shared FIGI alone does not authorize a
rename; acquisitions do not create an acquirer alias.

Policy v7 / provider rule 3 reevaluates prior review-only decisions while keeping
their receipts. The existing transition path owns preview, approval, application
and reversal. Former removals remain suppressed after aliasing and SA refresh;
manual and legacy membership removals cannot be automatically reactivated.
Explicit attended review remains available.

Four independent-review findings are part of the change, not residual risks:

1. The original attended apply path reactivated archived successor memberships.
   Automatic preflight and transactional approval/apply now read those exact
   memberships; they do not trust replayed preview effects.
2. The scanner originally stored successor directory checks in a different row.
   Related fresh observations now participate in scan, bundle and transaction
   decisions. This adds no provider requests. Newer observations replace their
   own lookup, not another provider's conflicting evidence; equally timed
   contradictions remain visible. Provider error codes reach policy evaluation.
3. An obsolete v6 approval could mask a subsequently applied v7 replacement.
   Current presentation ignores only superseded automatic work for the same
   event; old receipts remain in history and current/attended pending work stays
   visible.
4. A captured successor-query error could persist after fresh complete recovery,
   preventing a valid continuation from being recognized. Only the derived error
   is cleared after every exact successor recovers; original source errors,
   missing/stale recovery and old immutable receipts remain intact. A real worker
   test covers failure, recovery, fresh source observation and applied rename.

## Macro Results

All six macro named jobs share one closed result normalizer, also used by the
five recurring macro sources. Returned ingestion errors yield partial/failed,
not success. Empty successful queries remain success. Failure does not advance
the last-success timestamp. The existing job-audit schema has no partial state,
so it records failed with partial detail retained in the result; no migration is
introduced for status vocabulary.

False returns from FRED metadata/release/observation writes become errors.
Raw provider error strings do not enter persisted scheduler/job summaries.
Macro ingestion can commit incrementally: the Settings cache invalidates on
changed terminal failed/partial/succeeded results, not only on complete success.
Non-macro jobs retain their existing behavior.

## Financial Cache

Expiry is a cache TTL, not evidence of a new financial filing. Status now says
`reusable` / `refresh due`, counts cache entries rather than companies, and calls
the timestamp a cache timestamp. Expired entries are not returned by the normal
cache read; a refresh of the same key replaces that cached value. No cache row
was deleted and no archival financial-fact claim is made.

## Verification Method

Focused backend commands use the existing
`2026-09-08-automation-modes-gpt6/offline_check.py` harness. Final full suites use
`bwrap --unshare-net --clearenv`: root/worktree are read-only, `/tmp` and data
roots are disposable, main-worktree config/data and the real home are hidden,
and only the Python environment and Node installation are rebound. The tracked
worktree configuration catalog stays visible; there is no worktree `config/.env`.
Only loopback is available. Temporary SQLite stores and fake HTTP responses
exercise the real scanner/parsers and transition writes. These test harnesses
are not new product sandboxes or packaging dependencies.
`commands.json` records the final full-suite/build/literal-check argument vectors
and working directories, including the isolation mounts.

`mutation_check.py` changes functions only in the isolated test process; it
does not edit tracked production files. It requires a green baseline and a
test-failure exit and specific named failing owners for each negative control.

`browser_check.py` uses the actual Settings component, intercepted synthetic
responses, English/Traditional Chinese and 1280x960 / 390x844 viewports. It checks
mode persistence, visible cache wording, page/label overflow and browser errors.
Images and JSON output are local under `/tmp/arkscope-listing-data-browser`.
The temporary Vite server has no production sidecar.

## Initial RED Evidence

- Automatic rename: 12 failed / 8 passed before the policy implementation.
- Archived successor: 12 failed / 4 passed before membership guards.
- Separated successor material: 7 failed / 4 passed before related observations
  were included; the failing apply actually changed the temporary universe.
- Initial macro result handling: 130 failed / 23 passed before normalization.
- Macro controller partial invalidation: 6 failed / 8 passed before the first
  controller correction. Subsequent review also found committed metadata on
  failed attempts and the separate named-job entrypoint; final results below
  must cover those paths rather than reusing these initial counts.

## Completed Verification

- Final rename baseline: **71 passed** across four new files.
- Frontend: **1,849 passed / 126 files** with the app's Vitest config.
- `npm run build`: TypeScript and Vite pass; existing large-chunk warning remains.
- `npm run check:i18n-literals`: pass, no new literal debt.
- Browser: four locale/viewport contexts, one synthetic mode write each, zero
  browser errors and no page or mode-label overflow; screenshots inspected.
- Full backend: **7,916 passed / 12 skipped / 3 existing edgar deprecation
  warnings**, 553.59 seconds, exit 0. No deselections.

Final in-memory mutation results on the same 71-test set:

| Mutation | Failed / Passed | Named owner failed |
| --- | --- | --- |
| `review_only` | 35 / 36 | yes |
| `ignore_readiness` | 12 / 59 | yes |
| `ignore_successor_conflict` | 5 / 66 | yes |
| `skip_transaction_gate` | 6 / 65 | yes |
| `skip_successor_material` | 11 / 60 | yes |
| `drop_provider_codes` | 1 / 70 | yes |
| `reactivate_membership` | 12 / 59 | yes |
| `prefer_obsolete_pending` | 2 / 69 | yes |
| `keep_recovered_error` | 1 / 70 | yes |

`mutation-results.json` records actual failing node IDs and expected/observed
exit codes. Each mutation runs in its own process; product files are never
temporarily changed by these controls.

## Verification Corrections And Boundaries

Test ledger relative to the base's recorded verification:

- Backend: 7,628 passing nodes plus 71 rename and 217 macro nodes equals the
  verified 7,916 passing nodes, with the same 12 skips. No tests removed.
- Frontend: 1,835 plus two locale-copy and 12 macro-invalidation nodes equals
  1,849, in the same 126 files. Existing expectations change with the approved
  policy/copy; they are not deleted.

The first backend command omitted `tests/` and collected archived evidence
scripts, producing five collection errors (old imports and duplicate filenames).
The canonical full suite is `python -m pytest -q tests -p no:cacheprovider
--tb=short`; archived evidence was not edited to make that mistaken command pass.

The first canonical backend run finished **2 failed / 7,914 passed / 12 skipped**.
Both failures were unchanged worker tests hardcoding
`/tmp/claude-1001/nonexistent-profile.db`, whose parent does not exist in a clean
namespace. Both now use pytest `tmp_path`; their focused rerun is **2 passed**.
Neither worker nor production provider configuration changed for this repair.

The initial frontend mount whitelist omitted scripts and then `index.html`;
those missing-fixture failures were harness issues. One failure was a genuine
stale cache-copy expectation in `SettingsLocalStorage.test.ts`, corrected to the
new wording. The final 1,849-test run includes both restored fixtures and that
updated expectation, with no deselections.

Independent final rename/macro reviews reported no remaining findings after the
documented corrections. A separate read-only SEC-spec review found no actionable
contradictions or missing release-critical consumers; that review does not
replace the user's approval or prove implementation.

No provider request, production-store read/write, live listing event, SEC
migration, schedule activation, App restart, merge or push belongs to this
packet. Synthetic automatic-rename application is not a live provider canary.

## Commit Scope

The following commits precede this documentation-only verification record:

| Commit | Scope |
| --- | --- |
| `a47f6538` | SEC written design, not implementation |
| `04b9c6c8` | Verified automatic rename and owned review corrections |
| `ce17e9e7` | Rename-mode and cache-freshness wording with locale owners |
| `4358617f` | Macro scheduler/named-job/producer/UI result correctness |
| `0b02a16d` | Two existing worker tests use isolated temporary DB paths |

All work remains on `codex/listing-sec-macro-convergence`. The user's main
worktree and its preexisting untracked documents are unchanged.
