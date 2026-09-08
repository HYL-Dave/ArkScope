# Settings Hand-Test Repair

Base: `68d2010efee83af84b4bed85ea7a2c53b8125e7b`.
Branch: `codex/settings-handtest-repair`.

## Scope And Observation

The user authorized the three hand-test repairs and a narrowly scoped production
read: the IBKR/15min sync metadata for XYZ, ZETA, ZM, ZS, and the four task-route
rows. No credentials or token store were inspected. No provider, broker, or App
LLM calls, production writes, migration, App restart, merge, or push were performed
for this repair. The preceding tracking-history branch was already merged.

- All four metadata rows had `last_error = null`, last success/update
  `2026-09-08T05:28:13+00:00`, and last bar `2026-09-04T19:45:00+0000`.
  This agrees with the user's successful manual fetch. It does not recover or
  establish the original failure cause; there is no retained prior error here.
- There was no `lifecycle_investigation` row in the route table. The other three
  routes existed, including Spark/xhigh for translation. The earlier impression
  that investigation xhigh had persisted was not supported by this snapshot.
- Offline reproduction established that ib_insync's non-strict request errors
  can turn a failed qualification request into an empty result and the misleading
  "unknown contract" category. This is a reproducible mechanism, not proof that
  it caused the specific prior incident.

## Contracts

### Lifecycle Settings

- Primary navigation to investigation and the existing run-due command are at
  the top. Background schedule and last outcome are separate facts.
- Interval, batch size, and automatic application are in one disclosure;
  raw case/source-integrity counts are in a separate diagnostic disclosure.
- Incidents, invalid configuration, failures, and current progress remain visible;
  turning background checks off does not erase them. Existing polling and write
  guards are unchanged. No automation policy or scheduling semantics changed.
- Remove the obsolete static provider list rather than inventing a claim about
  which provider supplied a result. Result provenance remains in investigation
  and tracking history. Coverage controls also wrap correctly on narrow screens.

### Price Diagnostics

- Strict IBKR errors are enabled only around actual qualification/history
  dispatch on the existing dedicated sequential connection, and restored in
  `finally`. Journal cache reads do not dispatch or toggle the setting.
- A qualification request failure is `ibkr_contract_qualification_failed`;
  empty/ambiguous qualification and qualification error 200 still indicate no
  unique contract. History request failures retain their own phase. None proves
  a delisting. Existing ib_insync history-timeout-to-empty behavior is unchanged.
- Coverage reads only matching IBKR/provider/interval metadata. Error type and
  recorded time are shown separately from coverage completeness/generated time.
  No age-based hiding, clearing on GET, or inference from complete bars is added.
- The ordinary successful price-fetch path already clears its matching sync
  error. Repair-journal failures preserve typed codes and are never redispatched;
  this patch does not add repair-success metadata clearing or a retry policy.

### Task Routes And Discovery

- An edited save sends only changed tasks, so changing investigation effort does
  not revalidate or rewrite an unchanged Spark route. Explicitly saving unchanged
  defaults retains the existing persist-defaults behavior.
- Validate every requested route before writing; commit a multi-task save in one
  SQLite transaction. A later SQL failure rolls back every requested task.
- A closed, exact DB receipt or matching DB readback acknowledges a write.
  Confirmed write plus refresh failure says saved/refresh failed. Missing response
  plus unconfirmed readback says outcome unknown, not failed or saved. Recovery is
  GET-only, never an automatic second PUT or provider call.
- Readback adopts newer untouched task settings without turning old drafts into
  new edits. A superseded acknowledged route displays the current effective state.
  Pending user edits and unacknowledged submitted drafts survive repeated reads.
- Only reviewed localized rejection codes enter product copy, never raw errors.
  Feedback is beside Save. Discovery is a searchable read-only model list, with
  no synthesis/translation buttons or task-specific mutation callbacks.

## Verification

Frozen staged code/test diff digest against the base:
`90ec2224bc04ecef50f5a289be1a9115817d07f600fad1a47151f93c8ea2b321`
(`git diff --cached --binary -- apps data_sources src tests | sha256sum`).

- Full backend: **7180 passed, 12 skipped**, 3 existing edgartools deprecation
  warnings, 745.35 seconds. Backend files remained unchanged throughout this run.
  Command: `/home/hyl/.virtualenvs/llm_app/bin/pytest -q tests`.
- Final focused backend after in-memory negative controls: **132 passed**.
- Final full frontend: **1685 passed / 124 files**; `npm exec -- vitest run --silent=true`.
- TypeScript/production build passed. The existing large-chunk advisory remains.
- Visible-literal check passed: 20 allowed signatures, zero migration debt.
- Browser checks use real React components and exclusively synthetic intercepted
  responses, at 1280x960 and 390x844 in both locales. Lifecycle controls, coverage,
  discovery search and absent task buttons, xhigh save, and GET-only recovery are
  exercised. Each scenario sends exactly one synthetic route PUT; no external
  request, page error, or horizontal overflow is permitted.

The repository-root `pytest -q` command initially collected archived evidence
copies and failed with five collection errors. It is not the reported full-suite
result; the correct application suite is explicitly `tests/`. Earlier frontend
iterations also failed obsolete copy/placement assertions and exposed a render
initialization-order regression; all were fixed before the final full run.

### Negative Controls And Review

RED-first owners covered request-error classification, transactional rollback,
route-save outcomes, read-only discovery, timestamped diagnostics, and lifecycle
panel states. Review additionally reproduced stale untouched drafts, acknowledged
supersession, and repeated readback losing an unacknowledged draft. The last case
was observed RED in the actual React test before its fix. A final narrow review
reported no remaining findings; it did not claim independent full-suite execution.

In-memory mutations changed no source files:

| Mutation | Named owner | Result |
| --- | --- | --- |
| Disable strict request errors | `test_qualification_request_error_is_not_an_unknown_contract` | 2 failed |
| Commit task routes separately | `test_batch_save_rolls_back_every_route_when_a_later_write_fails` | 1 failed |
| Commit task routes separately | `test_multi_task_route_save_api_rolls_back_on_late_sql_failure` | 1 failed |

The mutation harness and logs are included. Browser fixtures are synthetic; no
production rows, account labels, credentials, or raw broker responses are copied.
Captured logs have trailing whitespace and extra final blank lines normalized;
test results and diagnostics are otherwise unchanged.

## Attended Check After Merge

1. Settings: open investigation from the reorganized panel. Expand check settings;
   confirm the same stored interval/batch/apply values. Do not enable background
   mutation solely to test layout.
2. Change investigation Sonnet effort high to xhigh and Save. Expect success, then
   refresh/reopen to confirm xhigh. Spark translation must remain unchanged.
3. Revalidate/list models from either entry point. The result list has search and
   model facts, no per-task assignment buttons; choose routes in task settings.
4. Coverage: recovered XYZ/ZETA/ZM/ZS should no longer have sync warnings. A future
   failure should identify the last request/error time, not assert delisting;
   previously collected complete days can still remain complete.
5. The already merged tracking-history explanation can be checked in the same
   restart. This branch does not change those receipts or lifecycle decisions.
