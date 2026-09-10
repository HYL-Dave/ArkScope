# Task 2 Report

Status: implemented, verified and committed.
Commit: `06511f44` (`refactor(sec): remove abandoned company-event intake`).
Base: `0ee801cdbe3516a397658eef87b58e0f58e923d7`.
Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
Branch: `codex/listing-sec-macro-convergence`.

## Implementation

- Deleted the SEC company-event collector, its scheduler definition/provider mapping, obsolete Settings copy in both locales, and source-specific cache invalidation. The deleted source now takes ordinary `unknown_source` behavior, including when stale enabled settings remain. No retired wrapper, forwarding alias, or fallback was added.
- `compose_security_lifecycle` now excludes unretained `sec_edgar` cases unconditionally and retains cases referenced by ticker-identity transitions. Background `_load_cases` admits only `listing_authority`, even for retained SEC action history and without an installation journal.
- Extracted `compose_security_lifecycle_audit` as an explicit read-only complete composition. Population `_capture` uses it; the complete-case equality check remains unchanged. Both installed and uninstalled fixtures account for observation-only, persisted/matched, and source-missing SEC cases. No `include_legacy` runtime flag exists.
- Retained `cutover_active` because the old web router still calls it. Its docstring identifies that remaining owner. Task3 can remove the gate with that router. Target-investigation journal validation was not modified.
- Provider credentials/SEC identity configuration, financial clients/tools/cache, source observations, schemas, accepted decisions, membership tombstones, and transition/history readers were not deleted or altered.

## Verification Commands

All backend executions used the existing offline runner, empty process environment, temporary fixture stores, network/production-data denial, and this prefix from Task1:

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  /home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/offline_pytest.py -q
```

Final backend selection, followed by `--junitxml=.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task2-final-green.xml`:

```text
tests/test_abandoned_surface_cleanup.py
tests/test_data_scheduler.py
tests/test_security_lifecycle_migration.py
tests/test_lifecycle_investigation_retirement.py
tests/test_security_lifecycle_population.py
tests/test_security_lifecycle_investigation.py
tests/test_security_lifecycle_automation_scheduler.py
tests/test_security_lifecycle.py
tests/test_security_lifecycle_tools.py
tests/test_security_lifecycle_routes.py
tests/test_security_lifecycle_provider_store.py
tests/test_security_lifecycle_current.py
tests/test_sec_user_agent.py
tests/test_sec_tools.py
tests/test_sec_transport.py
tests/test_ticker_identity_scheduler.py
tests/test_ticker_identity_routes.py
tests/test_lifecycle_web_read.py
tests/test_lifecycle_web_review.py
tests/test_security_lifecycle_review.py
```

Frontend working directory: `apps/arkscope-web`. Empty environment with the same PATH and an isolated HOME under this SDD directory:

```bash
node ../../node_modules/vitest/vitest.mjs run \
  src/settings/settingsBackendCopy.test.ts src/settings/settingsReadCache.test.ts \
  src/SettingsProviderConfig.test.ts src/i18n/resources.test.ts \
  --silent=passed-only --reporter=default --reporter=junit \
  --outputFile.junit=../../.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task2-frontend-final.xml
node ../../node_modules/typescript/bin/tsc --noEmit
node scripts/i18n/visible-literal-scanner.mjs check
```

Final frontend: 94 passed across four files. Typecheck exited 0. Literal scan exited 0: candidateCount 37, signatureCount 20, debtSignatureCount 0, allowlistCount 20. Passed-test i18next debug output was suppressed; failures remained visible.

## RED / GREEN And Mutations

XML filenames below are relative to this SDD directory. All runs had zero collection errors and zero skips.

| Artifact | Observed result | Notes |
| --- | --- | --- |
| `task2-baseline.xml` | 419 passed | Parent's seven-file baseline, before edits. |
| `task2-red.xml` | 11 failed, 2 passed | Initial RED also exposed four invalid new-fixture cases. |
| `task2-red-valid.xml` | 11 failed, 2 passed | Scheduler fixture corrected; two history fixtures still needed valid receipt material/transaction closure. |
| `task2-red-confirmed.xml` | 10 failed, 3 passed | Correct feature failures before implementation: physical presence, registered source/configuration, execution dispatch, unconditional admission, missing audit composition, and installed manifest `population_composition_incomplete`. |
| `task2-frontend-red.xml` | 2 failed, 32 passed | Copy mapping and SEC-only cache invalidation before removal. |
| `task2-focused-green.xml` | 13 passed | Same focused backend selection after implementation. |
| `task2-first-regression.xml` | 50 failed, 513 passed | Exposed current service fixtures expecting fresh SEC admission. |
| `task2-collateral-regression.xml` | 3 failed, 441 passed | Remaining two market-vs-provider observation lookups and one historical worker fingerprint fixture. |
| `task2-broad-regression.xml` | 17 failed, 2699 passed | Lifecycle/identity domain expansion, 234.62s; failures restricted to old SEC web/identity route fixtures. Not a repository-wide run. |
| `task2-late-collateral-green.xml` | 113 passed | All four late-collateral files after corrections. |
| `task2-frontend-green.xml` | 2 failed, 92 passed | First four-file frontend regression exposed exact schedule-row and locale-leaf counts requiring adjustment. |
| `task2-mutation-current.xml` | 2 failed | Replaced current SEC filter with `if True`; both journal states leaked three old SEC cases and failed the exact listing-only assertion. |
| `task2-mutation-background.xml` | 2 failed | Removed background listing filter; both journal states selected retained `OLD` alongside `LISTED` and failed. |
| `task2-frontend-final.xml` | 94 passed | Final four-file frontend run, 3.87s. |
| `task2-final-green.xml` | 738 passed | Final 20-file affected backend run after both mutations were restored, 81.12s. |

Both mutants were applied and restored with `apply_patch`; neither remains in the working tree. The original complete-case manifest equality check was not weakened. No repository-wide final backend suite was started; Task5 owns that verification after Tasks3/4.

## Test Accounting

The parent's seven-file 419-case baseline becomes 402 cases in its six surviving files:

| File | Before | After | Disposition |
| --- | ---: | ---: | --- |
| `test_data_scheduler.py` | 132 | 136 | Four journal-present/absent source-removal cases added. |
| `test_security_lifecycle_investigation.py` | 37 | 37 | Historical projection callers use explicit audit composition; assertions retained. |
| `test_security_lifecycle_automation_scheduler.py` | 137 | 137 | Real current listing admission/identity hints; historical evidence-worker coverage remains separately injected. |
| `test_security_lifecycle_migration.py` | 16 | 16 | Real profile/market write denial checks retained; only the collector-only leg removed. |
| `test_lifecycle_investigation_retirement.py` | 7 | 10 | One installed collector-gate case replaced by four journal-independent admission/history cases. |
| `test_security_lifecycle_population.py` | 63 | 66 | Existing complete population case gains installed variant; two read-only raw-audit cases added. |
| `test_sec_corporate_actions.py` | 27 | 0 | 24 parser instances plus collector persistence and scheduler-adapter instances deleted; one live CIK-cache test moved intact. |

Outside those baseline files, `test_sec_user_agent.py` grows 4 to 5 solely from that move, and `test_abandoned_surface_cleanup.py` grows 6 to 7 with the independent physical collector-absence guard. Across these owned counts: 26 collector-only instances deleted, one moved, eight new instances in scheduler/population/absence tests, and the old retirement instance replaced by four (+3). The net change is -15. Other renamed or contract-adapted families have unchanged collected counts. A byte-for-byte diff of the relocated CIK test body against HEAD0 exited 0.

Frontend baseline 93 becomes 94: the unknown-source invalidation test gains a deleted-SEC-source variant. No frontend test was deleted. Ordinary schedule rows change 5 to 4; five macro rows remain. Each locale removes exactly two leaves: Settings 919 to 917, total 2984 to 2982. SEC provider/credential configuration assertions remain.

## Precise Collateral

- Current tool and route fixtures now persist real `ProviderCheckStore` observations instead of stubbing around current filtering. Their permission, materialization, translation, closed DTO, concurrency, provider-free read, and no-write assertions remain. Two existing isolated disposition fixtures use listing-source cases, not obsolete SEC admission.
- The old mocked SEC queue/candidate test now owns archived classification and the closed candidate DTO. Real persisted SEC diagnostics are verified through explicit audit composition; the same test checks current service/candidate counts stay zero. Fresh SEC admission is protected by the new real-store owner tests rather than mocked composition.
- The scheduler identity-hint test now exercises actual schemas, provider observation composition and `_load_cases`, removing its composition/schema stubs. The historical SEC evidence-worker test still exercises real bounded identity hints, worker persistence, and evidence loading, but no longer pretends historical SEC fixtures enter current background selection.
- Due-transition fixtures seed previously approved SEC receipts through `build_transition_preview` and the real `TickerIdentityTransitionStore.approve` writer. Subsequent service reads, due execution, permissions and reversal stay real. Current ticker-route fixtures use actual listing observations; the old accepted-assessment consent guard explicitly keeps its SEC fixture.
- Legacy web readback's eight auth/gap variants use current listing cases. The two fresh SEC web-adoption variants now assert `case_not_found`, unchanged tracking/store state, retained successful web findings, and raw-audit readability. Shared current acceptance/reversal and writer-forgery controls remain covered. No runtime web/controller/route implementation was changed for Task3.

## Exact Product Paths

Only these 31 source/test paths belong in the product commit:

```text
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/i18n/resources.test.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/settings/settingsBackendCopy.test.ts
apps/arkscope-web/src/settings/settingsBackendCopy.ts
apps/arkscope-web/src/settings/settingsReadCache.test.ts
apps/arkscope-web/src/settings/settingsReadCache.ts
src/collectors/sec_corporate_actions.py (deleted)
src/lifecycle_investigation/retirement.py
src/security_lifecycle_investigation.py
src/security_lifecycle_population.py
src/service/data_scheduler.py
src/service/security_lifecycle_automation_scheduler.py
tests/test_abandoned_surface_cleanup.py
tests/test_data_scheduler.py
tests/test_lifecycle_investigation_retirement.py
tests/test_lifecycle_web_read.py
tests/test_lifecycle_web_review.py
tests/test_sec_corporate_actions.py (deleted)
tests/test_sec_user_agent.py
tests/test_security_lifecycle.py
tests/test_security_lifecycle_automation_scheduler.py
tests/test_security_lifecycle_investigation.py
tests/test_security_lifecycle_migration.py
tests/test_security_lifecycle_population.py
tests/test_security_lifecycle_review.py
tests/test_security_lifecycle_routes.py
tests/test_security_lifecycle_tools.py
tests/test_ticker_identity_routes.py
tests/test_ticker_identity_scheduler.py
```

This report is `.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task2-report.md`, ignored and excluded from the product commit, as are the generated XML artifacts and temporary offline test state. The parent-owned plan, progress ledger and schema-ownership draft were neither edited nor staged by this task.

Local source/test diff review and `git diff --check` passed. Independent review is the parent's next checkpoint. No subagents, real provider/credential access, production DB access, data disposal, application restart, merge or push occurred.
