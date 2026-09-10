# SEC Intake And Entrypoint Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Complete each RED-first task and its review before proceeding.

**Goal:** Remove abandoned SEC company-event collection and case-scoped web execution without removing current target investigation or retained evidence.

**Architecture:** The current target-bound investigation owns its workers and confirmation request. Remove obsolete scheduler and HTTP/UI entrypoints, not permanent retired wrappers. Schema disposition is prepared from source ownership first; actual-store inspection and deletion remain separate authorized operations.

**Tech Stack:** Python, SQLite, FastAPI, React/TypeScript, pytest, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`, sections 3, 9 and 11; cleanup audit C01/C04. User approved advancing after first-batch review on September 10.

## Global Constraints

- Work only on `codex/listing-sec-macro-convergence`; base `df97352b`.
- No provider requests, credential reads, production DB reads/writes, App restart, merge or push.
- Preserve prices, news, SA records, financial tools/cache, selected auth/model routes, membership tombstones, accepted decisions and reversal/history readers.
- Delete abandoned entrypoints. Do not add forwarding aliases, empty successes or a second retirement gate.
- New SEC research is a separate feature. Keep the functioning `get_sec_filings` tool until its atomic three-tool replacement.
- No hypothetical old-install compatibility, but no automatic destructive schema reset either.
- Tests use isolated temporary stores and mocked provider boundaries. Archive RED/green and test-removal accounting.

## Task 1: Correct Current SEC Documentation

Files: `data_sources/API_SPECIFICATIONS.md`, `tests/test_sec_transport.py`, current SEC spec, `tests/test_abandoned_surface_cleanup.py`.

- [x] Add a current-document guard rejecting `pip install edgartools` / `from edgar import` and requiring the actual SEC owner names. Run it RED against current recommendations.
- [x] Replace the obsolete recommendation section and table entries with `SECEdgarDataSource`, `SECEdgarFinancials`, `SecTransport` and `SecRequestGovernor`, distinguishing existing access from the planned durable research service. Do not rewrite unrelated historical provider comparisons.
- [x] Rename the dormant-module test to reflect active transport/import protection and update the current spec reference. Preserve its assertions and the independent physical-absence owner.
- [x] Run `tests/test_abandoned_surface_cleanup.py tests/test_sec_transport.py tests/test_sec_user_agent.py tests/test_sec_tools.py`, inspect residual current recommendations, commit and review.

## Task 2: Delete Company-Event Collection

Files: delete `src/collectors/sec_corporate_actions.py`; modify `src/service/data_scheduler.py`, `src/security_lifecycle_investigation.py`, `src/service/security_lifecycle_automation_scheduler.py`, `src/lifecycle_investigation/retirement.py`; Settings backend-copy/cache, en/zh-Hant dictionaries and their tests. Test collateral includes `test_sec_corporate_actions.py`, `test_data_scheduler.py`, `test_security_lifecycle_migration.py`, `test_lifecycle_investigation_retirement.py`, current population/scheduler tests.

- [x] RED: assert physical collector absence, source absent from `SOURCES`/configuration projection, and `run_source("sec_corporate_actions")` returns ordinary `unknown_source` without dispatch, for journal-present/absent fixtures.
- [x] RED: fixture legacy SEC observations do not enter current queue even without installation journal; retained action history remains readable; listing-authority observations still enter. Background selection accepts only listing-authority cases without conditional cutover.
- [x] Remove the source definition, mapping, callable module, Settings copy and source-specific invalidation. Do not delete the SEC provider credential/identity configuration.
- [x] Replace conditional intake filtering with the current unconditional policy. Remove obsolete gate if it has no remaining callers; do not bypass current journal validation in target investigation. The one remaining gate belongs to the Task 3 router.
- [x] Keep complete raw case accounting separate from current queue admission: the existing population manifest must still account for every original SEC observation/case before disposal. Extract a read-only audit composition used by that operator manifest rather than add an `include_legacy` execution flag or silently omit its inputs. Update audit-specific test callers to this explicit read path; current queue tests must use current composition.
- [x] Remove tests solely exercising the deleted parser/collector. Move migration safety assertions to their actual retained schema writer. Preserve current financial, provider-check, scheduler, retained-history and ordinary unknown-source controls.
- [x] Run all affected pytest files and Settings/i18n Vitest tests, mutation-check the two admission owners, commit and review. Record actual test-count changes, not only passing counts. Commit `06511f44`: independent spec/quality review clean; 738 scoped backend, 94 frontend, parent 111 and reviewer 17 passed.

## Task 3: Give Current Investigation Its Own Execution Owner

Files: `src/lifecycle_investigation/controller.py`, `store.py`, `src/api/routes/lifecycle_investigation.py`, `src/api/app.py`; remove `src/api/routes/lifecycle_web.py`, `src/lifecycle_web_controller.py` and its case-scoped `src/lifecycle_web_preflight.py`. Relocate the closed exception-code projection to a current owner. Extract the synthetic credential/route fixture shared with current target tests before removing old preflight-only tests. Preserve the finding-validation and Claude tool-gate tests co-located in those files: their production owners are still used.

- [x] RED: `InvestigationController` has no legacy-controller base/import; current confirmation DTO has no old-router import; real App route inventory contains current target routes and no `/cases/{case_id}/web-*` or `/web-runs/*` routes.
- [x] Move only current worker initialization/start/cancel/close behavior into the current controller. Keep two-worker bound, durable idempotency, permission/credential rechecks, cancellation signalling before journal writes, shutdown joins and sanitized failures.
- [x] Move the confirmation request into the current route (or existing current DTO owner); preserve strict fields/date validation and acknowledgement semantics. Remove old router mount/shutdown hooks and executable controller; no replacement shim.
- [x] Delete the old preflight whose only runtime consumer was the removed router. Current target preparation must retain its independent route/auth/budget checks; do not copy the obsolete case lookup or two-call pipeline policy into it.
- [x] Move test coverage for shared live behavior to current controller/store fixtures. Remove old-only launch/projection tests, keeping retained journal/receipt/history tests that still prove real readers. Account for each removed test family.
- [x] Run current investigation controller/routes/adoption/review/history and affected source/model/journal tests. Mutation-check missing current-route mount and cancellation/permission guard; commit and review. Commit `83eeb5ef`: 951 scoped passed, 183 restored checks passed, four mutants caught; independent spec/quality review clean.

## Task 4: Remove Unmounted Legacy Screens

Files: `apps/arkscope-web/src/lifecycle/CurrentLifecycleView.tsx`, `CurrentLifecycleAudit.tsx`, `LifecycleWebPanel.tsx`, their tests, `LifecycleView.tsx`, old-only API client/schema/fixture exports and locale leaves as determined by exact consumer references. Python collateral: `test_lifecycle_web_frontend_contract.py` and the old review-list frontend vocabulary case in `test_security_lifecycle_current.py`, if their TS owners become unused and are removed. Preserve adjacent real backend history/vocabulary checks.

- [x] RED: source absence owner for the three unmounted screens; positive control that `LifecycleView` still exposes current `InvestigationView`.
- [x] Remove old components and their test-only translation helper export. Delete only old-only client/schema/fixture/locale members; retain any names consumed by current TrackingHistory/review/reversal.
- [x] Run current investigation/TrackingHistory tests, API contract tests, typecheck and i18n checks. A no-caller result alone does not justify deleting shared data types.
- [x] Verify unchanged current page framing with existing UI tests; this task introduces no new visible layout. Commit and review. `302106d2`: 1692 frontend passed, 161 scoped backend passed, two parser mutants caught; independent spec/quality review approved with unchanged baseline test warnings explicitly noted.

## Task 5: Source Ownership And Completion Evidence

- [x] Inventory remaining old SEC/web tables, indexes, triggers, settings prefixes and current readers/writers from tracked source. Explicitly name structures retained for current acceptance/history and helper code still to extract. Do not report historic case counts as current measurements. See `sec-schema-ownership.md` in the cleanup evidence.
- [x] Identify the existing backup/disposal operations and required actual-store manifest boundary. No table DROP, settings-row deletion or automatic startup cleanup in this task. The broad installation snapshot is explicitly unsuitable for the narrow statistics-only authorization boundary.
- [x] Re-run mechanical census against the original baseline; retain review-required differences and classify deleted coverage/remaining uncertainty. Run broad backend/frontend regression, keep raw results and classify skips/failures honestly. Disjoint backend partitions plus the corrected whole-API-file rerun cover all 7953 final collected IDs: 7941 passed, 12 live skips. Full frontend 1692 passed. Census exit2 is retained with 193 new review candidates, not represented as a clean sweep.
- [x] Update audit dispositions/priority map and this checklist incrementally. State which C04/schema work remains before the new SEC three-tool implementation; do not claim all old schema is gone. Source-only ownership includes the five remaining HTTP candidates. Production inventory/disposal and the research implementation remain separate; final broader review follows this completed bounded plan.

## Preflight Review

Task 1/2 share the absence-owner test: append distinct named tests, preserving previous owners. Task 2/3 share old-router gate references: remove the final gate only when Task 3 removes that router. Task 3/4 share the deleted HTTP contract: backend removal lands before deleting its unmounted client. Task 5 inventories retained schema; it is not a production migration or completion claim for the separate SEC research spec. Current spec's complete three-tool feature remains the next implementation plan, not an omitted deliverable of this entrypoint-removal slice.
