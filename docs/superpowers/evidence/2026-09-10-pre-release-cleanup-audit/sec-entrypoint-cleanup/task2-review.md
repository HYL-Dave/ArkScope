# Task 2 Independent Review

## Findings

No reportable spec-compliance or code-quality findings in the reviewed source/test diff. No product or test changes are requested. File/line evidence for the admission, accounting, and preservation conclusions follows below.

## Verdict

- **Spec compliance: PASS for Task 2.** Reviewed Task 2 and the global constraints first, then the relevant SEC design boundaries. Physical deletion, unconditional current admission, complete read-only operator accounting, retained transitions, and test-removal accounting match this slice.
- **Code quality: APPROVE**, scoped only to commit `06511f44552deeaa2cafd202c8dbb0cc41e94207` relative to `0ee801cdbe3516a397658eef87b58e0f58e923d7`, under `src`, `tests`, and `apps`.
- Remaining old web-router/controller and `cutover_active` removal belongs to Task 3, not a Task 2 defect. This is not approval of Tasks 3-5, new SEC research, schema disposal, or parent-owned documentation.

## Exact Scope

- Worktree: `/tmp/arkscope-listing-sec-macro-convergence`; branch: `codex/listing-sec-macro-convergence`.
- Command reviewed: `git diff 0ee801cd 06511f44 -- src tests apps`. All 31 changed paths inspected: 339 insertions, 1267 deletions, including the collector and its old test file.
- SHA-256 of that command's patch output: `e0ef3371c46a9c37732ad03a5d6b44b9658d52e0c24a7324fff1129403fc8b53`.
- The initial uncommitted patch, resulting commit patch, and final working-tree patch from the base have the same scoped hash. Final HEAD is `06511f44552deeaa2cafd202c8dbb0cc41e94207`; `git diff 06511f44 -- src tests apps` is empty. **No remaining source/test drift.** Parent-owned docs are excluded and untouched.

## Spec And Quality Evidence

| Boundary | Independent review evidence |
| --- | --- |
| Collector/source deletion | The collector is physically deleted, not wrapped. No active `sec_corporate_actions` reference remains under `src` or frontend runtime source. [tests/test_abandoned_surface_cleanup.py:29](/tmp/arkscope-listing-sec-macro-convergence/tests/test_abandoned_surface_cleanup.py:29) owns absence; [tests/test_data_scheduler.py:169](/tmp/arkscope-listing-sec-macro-convergence/tests/test_data_scheduler.py:169) checks configuration and stale enabled settings in both journal states. The ordinary early return at [src/service/data_scheduler.py:1044](/tmp/arkscope-listing-sec-macro-convergence/src/service/data_scheduler.py:1044) precedes provider preflight, dispatch, locks, and result persistence. |
| Current admission versus retained history | [src/security_lifecycle_investigation.py:2034](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_investigation.py:2034) always excludes unretained SEC cases, while keeping transition-referenced cases through the existing retention owner. [tests/test_lifecycle_investigation_retirement.py:50](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_investigation_retirement.py:50) covers persisted, observation-only, and source-missing SEC exclusions plus positive listing admission; line 70 covers readable SEC transition/assessment history in both journal states. |
| Background selection | [src/service/security_lifecycle_automation_scheduler.py:567](/tmp/arkscope-listing-sec-macro-convergence/src/service/security_lifecycle_automation_scheduler.py:567) admits only `listing_authority` before identity-hint loading. Retained SEC history cannot reenter selection. The real listing/identity-hint test at [tests/test_security_lifecycle_automation_scheduler.py:1529](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_automation_scheduler.py:1529) now removes composition/schema stubs and exercises actual provider observations. |
| Complete operator accounting | [src/security_lifecycle_investigation.py:2056](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_investigation.py:2056) exposes explicit raw audit composition without an execution flag. Population capture uses it at [src/security_lifecycle_population.py:77](/tmp/arkscope-listing-sec-macro-convergence/src/security_lifecycle_population.py:77); the exact composed-case equality check at line 586 is unchanged. [tests/test_security_lifecycle_population.py:122](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_population.py:122) enforces read-only connections, query-only operation, all three SEC input populations, and unchanged store hashes. |
| Settings and financial identity | Only the obsolete source's schedule copy/cache branch and two locale leaves per language are deleted. Four non-macro source rows and five macro rows remain; deleted SEC IDs now use ordinary unknown-source copy/invalidation. SEC provider and user-agent copy remain at [apps/arkscope-web/src/settings/settingsBackendCopy.ts:180](/tmp/arkscope-listing-sec-macro-convergence/apps/arkscope-web/src/settings/settingsBackendCopy.ts:180) and line 212. The provider definition at [src/data_provider_config.py:139](/tmp/arkscope-listing-sec-macro-convergence/src/data_provider_config.py:139), functioning SEC tools, financial clients/cache, and price/news/SA production owners are unmodified. |
| Existing safety owners | [tests/test_security_lifecycle_migration.py:177](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_migration.py:177) still checks both retained profile and market writers against an incomplete migration receipt; only the deleted collector leg is removed. Current target/store journal validation remains at [src/lifecycle_investigation/target.py:97](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/target.py:97) and [src/lifecycle_investigation/store.py:65](/tmp/arkscope-listing-sec-macro-convergence/src/lifecycle_investigation/store.py:65). No destructive schema operation or new compatibility gate was introduced. |

## Collateral And Accounting

- Current route/tool fixtures use real `ProviderCheckStore` observations, not mocked admission: [tests/test_security_lifecycle_routes.py:89](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_routes.py:89), [tests/test_security_lifecycle_tools.py:172](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_tools.py:172), and [tests/test_ticker_identity_routes.py:14](/tmp/arkscope-listing-sec-macro-convergence/tests/test_ticker_identity_routes.py:14). Original permission, no-write/no-network, source-missing history, DTO, transition, and reversal assertions remain. Historical projection/classification tests use audit composition deliberately; they do not replace current queue guards.
- [tests/test_ticker_identity_scheduler.py:118](/tmp/arkscope-listing-sec-macro-convergence/tests/test_ticker_identity_scheduler.py:118) seeds an already-approved SEC receipt through the real preview/transition store, then retains actual due-service checks. This avoids depending on now-prohibited fresh SEC approval. The historical SEC evidence-worker fixture remains injected separately from current listing selection.
- [tests/test_lifecycle_web_read.py:29](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_web_read.py:29) keeps all eight auth/gap readback variants on listing cases. [tests/test_lifecycle_web_review.py:189](/tmp/arkscope-listing-sec-macro-convergence/tests/test_lifecycle_web_review.py:189) now checks fresh SEC adoption denial, unchanged state, retained successful findings, and raw-audit readability. Existing applied-receipt reversal and anti-forgery tests remain. The accepted-SEC-assessment consent guard explicitly retains its SEC fixture at [tests/test_security_lifecycle_review.py:398](/tmp/arkscope-listing-sec-macro-convergence/tests/test_security_lifecycle_review.py:398).
- Reconciled baseline and final XML class counts: scheduler 132 -> 136; investigation 37 -> 37; automation scheduler 137 -> 137; migration 16 -> 16; retirement 7 -> 10; population 63 -> 66; deleted collector file 27 -> 0. The original seven-file baseline totals 419; its surviving six files total 402.
- Inspected the entire deleted test file at the base: 24 parser instances plus collector persistence and scheduler-adapter instances are retired-only coverage. The remaining CIK-cache test moved unchanged to [tests/test_sec_user_agent.py:4](/tmp/arkscope-listing-sec-macro-convergence/tests/test_sec_user_agent.py:4); direct text comparison exited 0. Including that move and the new physical-absence owner gives **net -15 backend instances** across the accounted files. Frontend is **93 -> 94**, solely adding the deleted-source unknown-invalidation variant; no frontend test was deleted. These are scoped counts, not a repository-wide census.

## Verification

Fresh reviewer execution on the committed tree: **17 passed, 0 failed/errors/skipped, 2.66 seconds**. Artifact: [task2-review-verification.xml](/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task2-review-verification.xml). The inspected existing offline runner was invoked with `env -i`, disabled plugin autoload/bytecode, and a new reviewer-only `ARKSCOPE_OFFLINE_TEST_WORKSPACE` under this SDD directory. Selection: physical absence; both scheduler removal tests; both retirement admission/history tests; complete manifest and raw read-only composition tests; real listing identity hints; moved CIK lookup; incomplete-receipt write denial; and missing-current-journal rejection. No provider execution or real data/config/credential reads were used.

Independently inspected archived XML, not represented as fresh reviewer runs:

| Artifact | Recorded result |
| --- | --- |
| `task2-red-confirmed.xml` | 10 failed, 3 passed; failures match absence, dispatch, admission, missing audit composition, and installed manifest completeness. |
| `task2-final-green.xml` | 738 passed, zero failures/errors/skips across 20 affected backend files. |
| `task2-frontend-final.xml` | 94 passed, zero failures/errors/skips across four Settings/i18n files. |
| `task2-late-collateral-green.xml` | 113 passed, zero failures/errors/skips. |
| `task2-parent-verification.xml` | Parent-independent 111 passed, zero failures/errors/skips. |
| `task2-mutation-current.xml`, `task2-mutation-background.xml` | Each 2 failed, zero errors/skips. Failure bodies show SEC leakage and retained-SEC background selection respectively, in both journal states; final source has both guards restored. |

`git diff --check 0ee801cd 06511f44 -- src tests apps` exited 0. Archived selections overlap and must not be added into a unique passing-test total.

## Limitations

No full suite, broad-domain rerun, frontend rerun, browser check, or live-provider validation was performed by this reviewer. Typecheck and literal-scanner success are implementer-reported, not independently rerun. Earlier broad-domain failures are not relabeled as a final broad pass; the final affected-file runs and inspected fixture corrections are the available regression evidence. Unchanged financial-cache, price/news/SA, auth/model, and current target execution owners were checked for scope preservation, not comprehensively re-audited. No product/tests, parent ledger/plan, or implementer report were edited; no agents, application restart, data disposal, merge, or push were used.
