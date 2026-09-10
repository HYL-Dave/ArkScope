# Task4: Old Frontend Surface Removal

## Result And Boundary

- Commit: `302106d2ec33f7c7e097f167b7144f00b45376f1` (`refactor(frontend): remove unmounted lifecycle surfaces`).
- Diff base: `66b53ee523fc9bdb3f7d2688341ae17decf6c3a3`, including the parent-owned API count correction. Task4 did not change `tests/test_api.py`.
- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`; branch: `codex/listing-sec-macro-convergence`.
- Commit contains 34 Task4 code/test files, 162 insertions and 3,904 deletions. No docs, plan, ledger, evidence, CSS, backend production, schema, provider functionality or current UI layout changes were committed.
- No agents, installs, provider/live LLM requests, production DB/config/token reads, app start/restart, merge or push. No production DB approval was assumed. All frontend requests were mocked; the small backend run used the existing offline runner with a Task4-owned workspace.
- Used the applicable executing-plans, TDD, verification-before-completion, systematic-debugging and finishing-a-development-branch skills. Self-review completed before commit; independent final backend B and reconciliation remain parent-owned.

## Implemented Scope

Deleted the unmounted `CurrentLifecycleView.tsx`, `CurrentLifecycleAudit.tsx`, `LifecycleWebPanel.tsx`, their old-only drawer/section and source-check hook, old web fixtures/parser module, and obsolete tests. `LifecycleView.tsx` now exports only the actual current `InvestigationView` implementation; its old translation helper export is gone.

Removed the seven old web clients, four old review-list/detail/readback clients, case-audit reader, evidence-translation client and case automation dispatcher. Removed their exclusively owned audit parsers, evidence/translation/audit types, old review-list types/constants and old receipt timeout. Shared case, assessment, automation, history and vocabulary types were not deleted based merely on an empty UI caller list.

Moved current start-receipt validation to `investigationContract.ts::parseInvestigationStart`: nonempty, NUL-free run ID, actual boolean `created`, and private-field projection are unchanged. Current packet source gaps now belong to private `currentReviewContract.ts::parseReviewSourceGaps`: exact keys, nullable HTTPS URL without userinfo, bounded machine reason, null/empty distinction, and malformed nested-input rejection remain enforced. Failures use their current contract's error owner.

Removed 122 string leaves per locale, represented by 80 selected property/subtree removals in each of en and zh-Hant. Every candidate was checked against actual old and current consumers; no dictionary was deleted wholesale. The resulting lifecycle inventory is 662 leaves, Explore 1,219 and total bundled inventory 2,860 per locale. Current labels and historical authentication/error/effect copy remain.

## RED And Intermediate Results

Counts below are read from XML testcase elements, not inferred from filenames. All runs listed have zero errors and zero skips. `task4-full-frontend-green.xml` contains two failed testcases and three failure elements because one testcase has multiple soft assertion failures.

| Artifact | Cases | Passed | Failed | Interpretation |
| --- | ---: | ---: | ---: | --- |
| `task4-baseline.xml` | 306 | 306 | 0 | Provided lifecycle baseline, 15 files |
| `task4-full-frontend-baseline.xml` | 1850 | 1850 | 0 | Provided full frontend baseline, 126 files |
| `task4-red.xml` | 58 | 30 | 28 | Initial RED also exposed incorrect positive URL/label expectations |
| `task4-red-confirmed.xml` | 58 | 33 | 25 | One overbroad route-heading selector still needed correction |
| `task4-red-final.xml` | 58 | 34 | 24 | Expected pre-removal absence/current-owner/barrel failures; all 12 Universe cases passed |
| `task4-red-final-with-locales.xml` | 71 | 45 | 26 | Pre-removal RED plus bilingual absence and source-gap controls |
| `task4-first-green.xml` | 197 | 196 | 1 | Intermediate FAILURE: new barrel test's heading expectation |
| `task4-full-frontend-green.xml` | 1692 | 1690 | 2 | Intermediate FAILURE: two locale inventory cases |
| `task4-final-frontend.xml` | 1692 | 1691 | 1 | Intermediate FAILURE: remaining aggregate locale total |
| `task4-final-affected.xml` | 619 | 618 | 1 | Intermediate FAILURE: same aggregate locale total |
| `task4-contracts-restored.xml` | 59 | 59 | 0 | Corrected current guards and locale inventories, two files |
| `task4-mutated-parsers.xml` | 45 | 43 | 2 | Intentional mutants caught, not a passing verification run |

RED targets were `src/lifecycle/legacySurfaceRemoval.test.ts`, `src/lifecycle/InvestigationView.test.tsx` and `src/Universe.test.tsx`. Source absence, obsolete exports, current parser ownership, barrel and locale assertions were exercised before production removal. The final pre-removal RED had 25 guard failures plus the barrel export failure. Its later heading assertion was initially hidden behind that export failure; after removal, the test was corrected to the unchanged actual heading, `Lifecycle Investigation`. Other current UI assertions were likewise corrected to existing labels and exact selectors, not by changing production UI.

Self-review corrected parameterized array fixtures to one argument per row so `[]` and nested malformed source gaps were actually passed to the parser. Mutation checking then temporarily (1) coerced `created` with `Boolean(...)`, and (2) removed the source-gap HTTPS requirement. The string-valued start case and HTTP gap case each failed. Both production mutations were restored before the final runs below.

## Final Verification

| Artifact / Check | Final Result |
| --- | --- |
| `task4-verified-frontend.xml` | 1,692 passed / 119 files, zero failures/errors/skips; exit 0 |
| `task4-verified-affected.xml` | 619 passed / 45 files, zero failures/errors/skips; exit 0 |
| `task4-backend-green.xml` | 161 passed across six scoped Python files, zero failures/errors/skips; exit 0 |
| TypeScript `--noEmit` | Exit 0, no diagnostics |
| Visible literal scanner | Exit 0: 37 candidates, 20 signatures, 20 allowlisted, zero debt signatures |
| Unstaged and staged `git diff --check` before commit | Exit 0; en/zh-Hant trailing whitespace and Python final blank line corrected |

Final frontend commands, from `apps/arkscope-web`:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin ../../node_modules/.bin/vitest run --silent --reporter=junit --outputFile=../../.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task4-verified-frontend.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin ../../node_modules/.bin/vitest run src/lifecycle src/Universe.test.tsx src/LifecycleCaseApi.test.ts src/LifecycleAutomationApi.test.ts src/CardApiTimeout.test.ts src/apiError.test.ts src/Settings.test.tsx src/settings src/i18n --silent --reporter=junit --outputFile=../../.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task4-verified-affected.xml
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin ../../node_modules/.bin/tsc --noEmit
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin node scripts/i18n/visible-literal-scanner.mjs check
```

Scoped backend command, from the worktree root:

```sh
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task4-test-state /home/hyl/.virtualenvs/llm_app/bin/python .superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/offline_pytest.py -q tests/test_security_lifecycle_current.py tests/test_security_lifecycle_current_routes.py tests/test_security_lifecycle_web_contract.py tests/test_lifecycle_web_usage_journal.py tests/test_lifecycle_investigation_review.py tests/test_ticker_identity_history.py --junitxml=.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task4-backend-green.xml
```

No additional broad backend run was started. Parent reported partition A as 5,488 passed / 12 skipped plus the already-corrected count failure, superseded by its full `tests/test_api.py` 25 passed. That is parent evidence, not a Task4 full-backend pass claim. Parent owns excluded B and the final combined node-ID reconciliation on this commit.

## Test Accounting

Frontend: 1,850 -> 1,692 cases (net -158), 126 -> 119 files. This consists of 204 removed old-only cases and 46 added cases. Literal XML node-ID comparison is 208 removed / 50 added because four retained tests were renamed while removing their old-only branches. All exact IDs and rename pairs are in `task4-test-census.json`.

| Frontend Owner | Before | After | Disposition |
| --- | ---: | ---: | --- |
| `CurrentLifecycleAudit.test.tsx` | 29 | 0 | Removed old audit UI |
| `LifecycleCurrentView.test.tsx` | 36 | 0 | Removed old list/detail UI |
| `LifecycleWebPanel.test.tsx` | 23 | 0 | Removed old web UI |
| `useLifecycleSourceCheck.test.tsx` | 11 | 0 | Removed old-only hook |
| `webApi.test.ts` | 16 | 0 | Removed abandoned clients |
| `webContract.test.ts` | 26 | 0 | Removed old parser |
| `webUsageContract.test.ts` | 20 | 0 | Removed old parser usage projection |
| `currentReviewPresentation.test.ts` | 2 | 0 | Removed old-only review-list labels |
| `currentReviewContract.test.ts` | 86 | 50 | Removed 36 old branches; current packet/confirmation/history/privacy remain |
| `LifecycleCaseApi.test.ts` | 18 | 13 | Removed five audit-only cases; detail/candidate vocabulary remains |
| `InvestigationView.test.tsx` | 13 | 14 | Added current mounted-barrel/UI control |
| `legacySurfaceRemoval.test.ts` | 0 | 45 | New absence, current start, gaps, locale and provider-confirmation guards |

The lifecycle-only baseline reconciles from 306 / 15 files to 153 / 8 files within the final full suite. Existing Universe route/selected-target/localization coverage was strengthened without changing its 12-case count. Timeout and API error tests now exercise the retained card translation path. The due-automation test retains its attended POST control; its case-dispatch leg alone was removed. Historical web auth/reason tests remain and no longer depend on removed web-run vocabularies.

Python: five cases removed, zero added. `test_lifecycle_web_frontend_contract.py` contained one old state/vocabulary parity case and three parameterized old run/usage roundtrips (`None`, `sources`, `lost`). Only `test_current_backend_frontend_vocabulary_has_exact_bidirectional_parity` was removed from `test_security_lifecycle_current.py`. Adjacent actual backend closed-vocabulary enforcement, persisted current projections, retained journal integrity and ticker history remain.

## Whole-Tree Dependencies And Self-Review

`task4-whole-tree-refs.json` records exact identifier/module references for 68 removed declarations or owners, derived from TypeScript AST differences rather than name prefixes, across 1,004 current source files and baseline sources. Python and other cross-language source tests were included. Docs/evidence references are separately inventoried by filename; config/data, dependencies, generated output and ignored SDD artifacts were excluded from runtime-source scanning and were not read as configuration or stores.

- Removed frontend names have no remaining runtime consumer. Their intentional source references are the new absence guards, with two important identity exceptions: `LifecycleView` remains the export name of the actual current implementation, and `CURRENT_REVIEW_REASONS` / `CURRENT_ACTION_STATES` remain live backend constants in `src/security_lifecycle_current.py`. Only their obsolete TS list-parser owners were removed.
- Current route: `Universe.tsx` -> `lifecycle/LifecycleView.tsx` -> `InvestigationView.tsx`. Production content of Universe, InvestigationView, TrackingDecision, LifecycleActivityBand, Settings and DataStorageSection is unchanged from `66b53ee5`. Tests prove current header, selected target, history disclosure and route/locale retention; no browser/app server was started.
- Current review has both `confirmLifecycleReview` for provider packets and `confirmInvestigation` for LLM packets. Both clients remain, and current UI tests retain the distinct request path, explicit consent, source-gap acknowledgement, dirty-preview and failure controls.
- Settings and `settings/DataStorageSection.tsx` still call `listSecurityLifecycleCases`; its list response and shared case types remain. The full frontend suite also includes Settings local-storage coverage.
- `TrackingHistory` retains `LifecycleActivityBand` -> `TrackingDecision`, activity read/acknowledge/reverse calls and current history/confirmation parsers. Existing provenance, authenticated model labels, partial history, stale reversal, failed reversal and projection/privacy tests remain.
- `currentReviewCopy` remains used by InvestigationView's source checks, pending actions, review and history. `webCopy` remains used by InvestigationView and TrackingDecision; `webReason` remains used by TrackingDecision and investigationPresentation. Shared auth/errors/events/effects/security/effective/successor/removePrompt/unavailable dictionaries remain, including dynamically selected keys.
- Per-member locale proof is in `task4-locale-removals.json` (122 leaves, 80 selected properties per locale) and `task4-consumers-before.json`, `task4-consumers-after-code.json`, `task4-consumers-final.json`. Only candidates with proven old ownership and no current consumer were pruned. Pre-existing unrelated dictionary/helper debt was not swept.
- `tests/fixtures/lifecycle_current_v1.json` remains shared by actual current packet/confirmation/activity tests and backend current-projection checks. `tests/fixtures/ticker_history_decisions_v1.json` and real history/integrity/vocabulary owners remain. The current investigation test now builds its own synthetic version-2 finding instead of importing the deleted old run fixture.
- Pre-existing adjacent orphan clients/helpers such as `getSecurityLifecycleCase`, `listSecurityLifecycleSecCandidates`, `getSecurityLifecycleInvestigation` and `lifecyclePresentation.ts` were not swept into this removal merely for lacking a mounted UI caller. Shared schemas, backend services and unrelated dead CSS remain outside Task4; this is not a claim that all old schema/helper code is gone.
- Historical source snapshots, mutation scripts, plans and current cleanup documentation still name removed owners. Their exact files are retained in the documentary census for the parent; they were not edited or staged. Ignored Task4 reports/scripts also intentionally name those owners.

Before commit, the staged inventory was checked explicitly and contained only Task4's 34 code/test files. After commit, working-tree changes consisted solely of parent-owned docs/evidence. The branch/worktree are preserved for parent B and review. No decision blocker remains for this bounded task.
