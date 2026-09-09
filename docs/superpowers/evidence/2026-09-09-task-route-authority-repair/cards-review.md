# Task 2 Review

**Spec compliance: Compliant within the reviewed Task 2 scope, with the verification limits below.**
**Code quality: Approved for this task-scoped gate.**

## Findings

- **Critical:** None found.
- **Important:** None found in the Task 2 implementation.
- **Minor:** No new Task 2 defect identified. The inherited test-order defect below remains a nonblocking test-hygiene item, not a Task 2 regression.

### Inherited Test-Order Defect

The implementer's qualification at `.superpowers/sdd/2026-09-09-task-route-authority-repair/task-2-final-report.md:3` is material: the final 720-pass result does not establish order-independent integration success. The alternate five-file order reportedly produced 2 failures and 188 passes. The affected tests are `test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes` and `test_old_integer_event_and_relationship_routes_are_absent`.

The controller subsequently supplied an exact-order comparison against an immutable export of Task 2 BASE `1284c28e0d80a26279913fd2e503005e5582d5e2`: **2 failed / 188 passed in 11.85s**, with the same two tests and the same `portfolio -> ib_insync -> eventkit` no-current-event-loop stack. This establishes that this specific defect predates Task 2. It does not excuse independent changed-code risks or establish full integration success. Retain it in the integration ledger; no Task 2 change or repeat run is requested for this issue. I did not independently execute the controller's comparison.

## Spec Checks

| Requirement | Code evidence and assessment |
| --- | --- |
| Capture the complete selection once | `src/api/routes/analysis_cards.py:129` captures before gathering; `src/card_execution.py:35` holds frozen task/provider/model/effort fields and a repr-excluded binding. `src/card_synthesis.py:580` resolves only when no execution was supplied, and `src/card_synthesis.py:591` activates that execution around admission and synthesis. |
| Pin translation model and effort | `src/api/routes/analysis_cards.py:325` captures one execution and passes it into translation. `src/card_synthesis.py:845` centralizes translation admission/dispatch using that execution's model and effort. `src/api/routes/security_lifecycle.py:321` also captures and forwards the selection in the directly affected evidence caller; its surrounding lifecycle policy is not changed. |
| Preserve explicit API provider overrides | `src/api/routes/analysis_cards.py:127` validates the explicit provider; `src/card_execution.py:58` preserves same-provider routes and deliberate cross-provider synthesis defaults. The positive API control at `tests/test_card_execution_authority.py:457` checks the actual sent model and key after environment mutation. |
| Closed, public execution receipt | `src/card_execution.py:15` defines exactly provider/model/effort/auth_mode, forbids extra fields, freezes the DTO, and explicitly describes ArkScope's sent selection rather than provider attestation. `src/card_execution.py:42` constructs it without credential identifiers or binding contents. Generation/list/detail expose it outside the card payload at `src/api/routes/analysis_cards.py:204`, `:110`, and `:246`. |
| Preserve typed admission and bounded failures | `src/api/routes/analysis_cards.py:87` maps route-read failure and auth-capture failure to separate closed 503 details. `src/api/routes/analysis_cards.py:175` preserves timeout/admission handling and sanitizes generation errors with the captured binding after activation exits. Translation emits its closed failure classification at `src/api/routes/analysis_cards.py:344`, without logging the exception or traceback. |
| Keep legacy provenance independent of Settings | `src/card_runs.py:149` reads stored receipt rows or retains historical run provider/model with unknown effort/auth. `src/api/routes/analysis_cards.py:319` returns an all-null legacy translation receipt when none was stored; it does not copy generation metadata onto translations. `tests/test_card_execution_authority.py:282` guards history/cache reads against route and credential selection. |
| Preserve cache, refresh explicitly, and distinguish no-op | `src/api/routes/analysis_cards.py:80` defaults refresh to false. `src/api/routes/analysis_cards.py:318` returns cache before route/auth resolution; `:322` returns an explicit null-receipt no-op before capture or writes. Only successful translation reaches `:361`. The refresh/failure/reopen control is at `tests/test_card_execution_authority.py:255`; the empty-prose control is at `:298`. |
| Additive metadata and atomic output/receipt persistence | `src/card_runs.py:51` adds the receipt/version tables without changing the old result payload. `src/card_runs.py:255` inserts the generation receipt before committing the run. `src/card_runs.py:348` serializes translation read/merge/write; `:355` archives an unversioned legacy cache before replacement, and `:365` appends the new output and receipt in the same transaction as the compatible cache update. Read snapshots start at `:307` and `:329`. |
| Preserve earlier successful translations across reopen/failure | `tests/test_card_execution_authority.py:343` constructs a real legacy SQLite schema and verifies original result JSON and both translation versions after reopen. `:373` uses abort triggers to test rollback of output/receipt writes. `:435` checks that missing selected OAuth tokens neither bill a replacement key nor delete/invent legacy translation history. |
| Keep scope and existing restrictions | The immutable change contains the three required production files, the permitted selection helper, the directly affected evidence caller, relevant tests, and the implementer's report. No registry/task-ID, UI, limit, lifecycle-policy, or shared Task 1 helper change is present. `tests/test_card_execution_authority.py:420` checks typed retirement, Fable OAuth rejection, and negative Spark task/auth admission through the API. No retry/fallback branch is added by the reviewed diff. |

The documented Task 3 property names and optional refresh/no-op shapes agree with `src/card_execution.py:15` and `src/api/routes/analysis_cards.py:318`. Python callers retain their existing return shapes and receive an additive optional execution argument; the new receipt-bearing HTTP shape is not substituted into the existing card JSON.

## Strengths

- The selection helper is narrowly scoped: 72 lines, one frozen execution value, one closed public DTO, and no new transport framework (`src/card_execution.py:15`, `:35`, `:50`). The fixed dispatch and persistence layers have distinct responsibilities.
- The main authority matrix tests the real API and fixed functions at the SDK boundary, not only mocked synthesis return values. It covers both providers, both auth families, same-provider model/effort mutation and cross-provider changes, exact outbound credentials/destinations, one route read, receipts, and reopen (`tests/test_card_execution_authority.py:191`, `:220`, `:236`, `:249`).
- Persistence tests verify failure behavior as well as success. They check legacy-byte preservation, prior-version retention, and rollback using SQLite triggers (`tests/test_card_execution_authority.py:343`, `:373`). The store's explicit read transactions also avoid pairing a cache from one snapshot with metadata from another (`src/card_runs.py:307`, `:329`).
- The failure tests deliberately use a nonstandard selected-key sentinel and inspect both API output and captured logs after activation exits; they also reject attached tracebacks (`tests/test_card_execution_authority.py:327`). Original-ID OAuth refresh and refresh failure have explicit positive/negative controls (`:502`).

## Cannot Verify

- **Reported execution results:** I inspected the test implementations and the complete implementer report, but did not rerun the reported suites or independently reproduce the reported RED/GREEN, 720-pass, or whitespace-check results. These remain attributed execution evidence, not reviewer-run results. The controller's BASE comparison resolves attribution of the two disclosed order failures, not full integration.
- **Unchanged admission/adapter internals:** Positive exact Spark entitlement behavior, the complete four-task registry contract, and all shared adapter branches are not established by this Task 2 diff alone. The report says the relevant existing controls were included in the 720-test run. The negative API admission tests are visible at `tests/test_card_execution_authority.py:420`; broader adapter/registry verification remains with the controller, not a reason to expand this task review.
- **Provider and operational behavior:** No real provider identity, live OAuth grant, production database state/migration, or implementation-time operational history was independently verified. Such access was prohibited. The receipt intentionally makes only the sent-selection claim (`src/card_execution.py:16`); the synthetic SQLite tests do not constitute a production rollout.
- **Full integration/UI:** Whole-branch behavior and Task 3 rendering are outside this gate and remain pending. This approval is not merge or deployment approval.

## Review Evidence And Boundaries

- Reviewed BASE `1284c28e0d80a26279913fd2e503005e5582d5e2` to HEAD `84ff0cd3` from the supplied immutable package: commit list, stat, and full diff, read once in nonoverlapping chunks. No git commands were run.
- **Changed-file exception:** Read only `src/card_synthesis.py:58-153` and `:239-312` beyond the diff. The relevant hunks cut off `_require_task_route`, `ModelExecutionTimeout`, and `_subscription_structured_output_if_active` mid-function. The supplemental slices were needed to verify model/auth admission staging, the closed timeout detail, and exception propagation after the subscription call. They showed that actual auth is checked at the transport boundary, timeout details contain selection/limit fields rather than raw exceptions, and the subscription catch does not log the exception.
- **Named dependency risk: captured auth must survive downstream resolution.** One focused source check covered `src/auth_drivers/runtime_binding.py` and the resolver/synchronous-client portion of `src/auth_drivers/live_resolver.py`. The context is restored in `finally`; the resolver returns the bound credential ID; synchronous clients use the bound client; the sanitizer accepts the captured binding explicitly. Combined with the visible token-store forwarding at `src/card_synthesis.py:286`, this supports the Task 1 handoff without reselecting auth.
- **Named dependency risk: removing unconditional environment loading could break genuine environment defaults.** One focused definition check covered `task_route`/`get_agent_config` in `src/agents/config.py` and `CredentialStore.list` in `src/model_credentials.py`. `src/agents/config.py:501` calls `ensure_env_loaded()` before route resolution and subsequent auth capture. No additional environment-loading fix is indicated.
- No focused test was run: the code review and permitted dependency checks did not leave a new concrete doubt requiring execution beyond the supplied evidence. No reported suite or alternate order was rerun; raw pytest was never invoked.
- No subagents/review helpers, provider/production/credential access, restart, merge, push, or code/index/HEAD edit was performed. The only write was this review report via `apply_patch`.

## Assessment

**Task quality: Approved.** The changed paths implement the requested selection, receipt, refresh, and history contracts without a confirmed Task 2 correctness or maintainability defect. The inherited order-sensitive test failure and the explicitly unverified integration/operational items remain controller responsibilities, not silently cleared by this task approval.
