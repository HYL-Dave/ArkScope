# Task 3 Report

Status: implemented, verified and committed; parent independent review pending.
Commit: `83eeb5ef` (`refactor(lifecycle): give current investigation its own execution owner`).
Base: `06511f44552deeaa2cafd202c8dbb0cc41e94207`.
Worktree: `/tmp/arkscope-listing-sec-macro-convergence`.
Branch: `codex/listing-sec-macro-convergence`.

## Implementation

- `InvestigationController` now directly owns initialization, its two-worker bound, durable start/replay, local status, cancellation signalling, and shutdown joins. Its existing target-agent execution, credential generation/selection checks, permission rechecks, heartbeat, source/step recording, recovery and result projection remain unchanged. Thread-start failure writes directly through the current store's `finish`; the old inherited-contract-only `InvestigationStore.fail` adapter is removed.
- Current `ConfirmRequest` owns the exact former confirmation fields, canonical date validator, forbidden extra fields and strict booleans. The current route's generic failure stays `investigation_unavailable`; `safe_code` now owns the same typed, length/character-limited exception projection and current known-code set without importing an old controller. Existing public `web_*` codes are preserved where current behavior uses them; no execution shim or forwarding endpoint was added.
- Deleted `src/lifecycle_web_controller.py`, `src/lifecycle_web_preflight.py`, and `src/api/routes/lifecycle_web.py`, their App router/shutdown wiring, and the final `cutover_active` gate. `retained_action_cases` remains unchanged in behavior.
- Extracted synthetic credentials/routes and current worker fixtures into `tests/lifecycle_investigation_fixtures.py`. Successful worker fixtures call the real current agent with a fake model boundary, persist real call terminals, steps, source passages and a validated conclusion, and pass the store's existing success/receipt checks. No old execution controller or pipeline was recreated in test helpers.

## Bounded Collateral

The real App tests exposed a pre-existing route-ordering defect hidden by single-router fixtures: the retained `GET /security-lifecycle/investigations/{run_id}` reader intercepted current `targets`, `runtime`, and `actions` GETs. The specific current router is now mounted first. The historical reader is retained, the exact route census still includes it, and the current HTTP tests now use `create_app()` with dependency overrides but never enter the App lifespan.

The Python-to-TypeScript receipt contract test was another consumer of the removed `run_pipeline` fixture. Its three receipt roundtrips now use direct stored success/failure/unknown-outcome receipts. No frontend file was edited. The shared `completed` journal fixture accepts an optional usage receipt; it still uses the real retained journal writer and keeps its original default behavior.

Shared schemas, review/adoption/transition/history readers and source/model contracts remain. In particular, current agent `_read_one` and retained store `WebInvestigationOptions` still come from `security_lifecycle_web_pipeline`; that genuinely shared module was not blanket-deleted or copied. Current target preparation retains its own runtime, route/auth and journal checks, without the old case lookup, mandatory issuer-name rule or two-call budgets. Schema cleanup and any future helper extraction remain outside this task.

## Verification

All pytest executions used this empty-environment prefix, the existing runner, isolated fixture stores/HOME and network/production-store denial:

```bash
env -i PATH=/home/hyl/.nvm/versions/node/v22.14.0/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  ARKSCOPE_OFFLINE_TEST_WORKSPACE=/tmp/arkscope-listing-sec-macro-convergence/.superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/task3-implementation-state \
  /home/hyl/.virtualenvs/llm_app/bin/python -B \
  .superpowers/sdd/2026-09-10-sec-intake-entrypoint-cleanup/offline_pytest.py -q
```

The complete affected selection was:

```text
tests/test_abandoned_surface_cleanup.py
tests/test_lifecycle_investigation_*.py
tests/test_lifecycle_web_*.py
tests/test_lifecycle_source_*.py
tests/test_security_lifecycle_web_*.py
tests/test_ticker_identity_history.py
tests/test_security_lifecycle_routes.py
tests/test_security_lifecycle_review.py
```

This is 49 complete files and 951 passing cases, not a full backend run. It includes current controller/routes/agent/runtime/target/review/provider/history, retained adoption/source/receipt integrity, model/transport gates, journal/migration readers and four real TypeScript receipt-contract cases. Parent owns the later full backend suite after Task4.

All artifacts below are relative to this report's SDD directory. All completed runs have zero collection errors and zero skips.

| Artifact | Actual Result | Meaning |
| --- | --- | --- |
| `task3-baseline.xml` | 221 passed | Parent's 11-file Task3 baseline. |
| `task3-preflight-baseline.xml` | 33 passed | Parent's additional four-file baseline. |
| `task3-red.xml` | 7 failed, 1 passed | Before production edits: controller/DTO ownership, physical old execution files, old routes and gate fail; current mount inventory passes. |
| `task3-worker-preservation.xml` | 1 failed, 24 passed | Before production edits: new direct current worker characterizations pass against inherited behavior; only the intended ownership guard fails. |
| `task3-first-collateral.xml` | 10 failed, 309 passed | Three real App route-shadow failures; four new fixture-clock freshness failures; three invalid constructor fixtures for the no-argument `ModelRouteUnavailable`. No provider or store-integrity regressions. |
| `task3-route-collateral-green.xml` | 57 passed | Complete current route/store files after bounded mount ordering and fixture corrections. Error-class matrix changed from 21 to 18 plus one dedicated route-code case, avoiding three invalid constructor instances. |
| `task3-scoped-green.xml` | 951 passed | Complete 49-file affected selection, 108.81s. |
| `task3-mutation-route-mount.xml` | 1 failed | Removing the actual current router mount fails the real App current-route inventory. |
| `task3-mutation-cancel-guard.xml` | 1 failed | Removing the post-credential stop check invokes the runner after cancellation; the preserved cancellation variant catches it. |
| `task3-mutation-permission-guard.xml` | 1 failed | Removing the post-credential permission recheck invokes the runner after revocation; the preserved permission variant catches it. |
| `task3-mutation-cancel-signal.xml` | 1 failed, 1 passed | Removing local cancellation signalling fails the stop-before-failed-write assertion; the independent shutdown-join variant remains green. |
| `task3-restored-green.xml` | 183 passed | Complete current controller/routes/store, absence guards, retained gap/acknowledgement and exact App census route files after restoration and unused test-import cleanup, 42.81s. |

Every mutant was applied/restored with `apply_patch`. After restoration, source SHA-256 values exactly match the pre-mutation green tree:

```text
399765c5a1c4a58c48f6e1d01db6a30c1154e36abd7e3f681b77b9407756e91d  src/api/app.py
47e7358f3161f3cad393d3d46ab86a5789c5d458a59b2509f69747a2e225c9b3  src/lifecycle_investigation/controller.py
```

## Test Accounting

The combined parent baseline is 254 cases in 15 files. Its 11 surviving files now contain 248 cases (-6); four old-only execution/preflight test files are removed. The following table also lists every changed test file outside that baseline. Counts are collected cases, not function counts.

| Test File (Under `tests/`) | Before | After | Family Disposition |
| --- | ---: | ---: | --- |
| `test_lifecycle_investigation_controller.py` | 3 | 25 | Existing post-load cancellation/credential/permission variants preserved; ownership, four channels, durable replay, two slots, five interval cases, failed thread startup, sanitized failure, two remote-terminal cancellation cases, two failed-write stop/join cases, per-step permission, body-free progress, restart and lease failure added. |
| `test_lifecycle_investigation_routes.py` | 9 | 31 | Existing current review/reversal/runtime/provider/action tests preserved on real App; three ownership/inventory guards, eleven strict confirmation cases, three start-override cases, one credential-refresh factory case and four end-to-end channels added. |
| `test_lifecycle_investigation_review.py` | 6 | 6 | Synthetic credential fixture extraction only; atomic adoption, consent conflicts and retained source history unchanged. |
| `test_lifecycle_investigation_routing.py` | 22 | 22 | Route-unavailable projection and dedicated factory tests now exercise current target preflight. Other model/auth/route tests unchanged. |
| `test_lifecycle_web_controller.py` | 14 | 0 | All ten families rehomed to current execution: four-channel provenance/readback (4), replay (1), credential failure (1), generation change (1), stop during refresh (1), terminal-vs-ack cancellation (2), dispatch permission (1), restart (1), lease failure (1), shutdown under failed journal writes (1). Old case-launch fixture removed. |
| `test_lifecycle_web_routes.py` | 11 | 0 | Six families rehomed: four-channel workflow (4), selected-credential reconfirmation (1), forbidden start overrides (3), sanitized generic failure (1), no automatic journal install (1), selected expired-token factory refresh (1). Current route/target tests own these behaviors. |
| `test_lifecycle_web_usage_journal.py` | 35 | 23 | Five obsolete pipeline-integration families removed: source-failure channel usage (4), unreported analysis (2), accepted phase totals (4), unreported counters (1), inconsistent pipeline total (1). All retained receipt/projection families remain. |
| `test_lifecycle_web_gaps.py` | 51 | 49 | Removed only the old controller gap-url pipeline family (2). Five malformed/omitted acknowledgement HTTP cases now use the current route; all direct acceptance, integrity, active-listing veto and disclosure tests remain. |
| `test_lifecycle_web_claude.py` | 31 | 32 | Mixed-model durable failure now runs through current controller/agent; the live twelve-search tool-gate case moved intact in behavior from the deleted budget file. All adapter/tool/terminal tests remain. |
| `test_lifecycle_source_progress.py` | 13 | 12 | Old controller polling branch removed and current progress covered in its owner. Historical projection polling remains; terminal integrity uses the real historical reader. All transaction, contention, cursor, snapshot and caller-atomicity families remain. |
| `test_lifecycle_web_attended_concurrency.py` | 26 | 26 | Only the final worker-starvation family changes to a real current store/controller sharing the profile with retained attended confirmation. Other consent, receipt, transaction, permission and source-validation cases unchanged. |
| `test_lifecycle_web_preflight.py` | 11 | 0 | Finding identity-validation family (2) moved to finding owner. Old case-bound auth/public identity (4), fixed source-capacity binding (1), exact SA-name fallback (1), mandatory issuer absence (1), credential reconfirmation (1), no ambient fallback (1) retired; current target owners preserve applicable behavior without restoring the old mandatory identity/case policy. |
| `test_lifecycle_web_investigation_budget.py` | 9 | 0 | Deleted old two-call channel limits (4) and old expanded-budget reconfirmation (4); live Claude tool gate (1) moved. Current runtime remains independent. |
| `test_lifecycle_investigation_target.py` | 5 | 14 | Current no-case/manual-target/provider-identity cases retained; four channels with independent saved budgets, three reconfirmation dimensions, inactive credential/no ambient fallback and noninstalling preflight added. |
| `test_lifecycle_investigation_runtime.py` | 8 | 8 | Unmodified positive control included in the parent's baseline and affected run. |
| `test_abandoned_surface_cleanup.py` | 7 | 11 | Three old executable-file absence cases and gate-absence/retained-reader control added; Task1/2 owners untouched. |
| `test_lifecycle_investigation_store.py` | 7 | 26 | All original journal/success/ownership/recovery cases retained; 18 typed/raw exception cases plus one dedicated route-unavailable projection case added. |
| `test_security_lifecycle_web_finding.py` | 38 | 40 | Two genuine unknown security-class/venue validation cases moved from old preflight; existing findings untouched. |
| `test_lifecycle_web_store.py` | 10 | 10 | Existing retained completed-receipt fixture accepts optional usage report; test bodies unchanged. |
| `test_lifecycle_web_frontend_contract.py` | 4 | 4 | Three TypeScript receipt roundtrips now consume saved journal receipts directly; vocabulary and parser assertions retained. |
| `test_security_lifecycle_routes.py` | 41 | 41 | Exact App census removes seven deleted HTTP routes: 228 -> 221. Current routes and historical investigation reader remain required. |

Across this accounted universe (including the unchanged eight-case runtime control), 361 cases become 380 (+19). This is distinct from the 951-case affected regression selection. The new `lifecycle_investigation_fixtures.py` contains no collected tests.

Retained usage-journal families specifically include: unknown historical scope (1), cross-call/duplicate/malformed receipt rejection (7), usage-only failure receipt (1), malformed saved usage (5), correctly hashed but wrongly bound remote identity for success/failure/unknown outcomes (3), aggregate agreement on read (1), and malformed historical usage pairs (5). All 23 remain; the last two integrity families seed real receipts directly instead of invoking removed execution.

## Product Paths

Only these 29 source/test paths belong to the product commit:

```text
src/api/app.py
src/api/routes/lifecycle_investigation.py
src/api/routes/lifecycle_web.py (deleted)
src/lifecycle_investigation/controller.py
src/lifecycle_investigation/retirement.py
src/lifecycle_investigation/store.py
src/lifecycle_web_controller.py (deleted)
src/lifecycle_web_preflight.py (deleted)
tests/lifecycle_investigation_fixtures.py (new)
tests/test_abandoned_surface_cleanup.py
tests/test_lifecycle_investigation_controller.py
tests/test_lifecycle_investigation_review.py
tests/test_lifecycle_investigation_routes.py
tests/test_lifecycle_investigation_routing.py
tests/test_lifecycle_investigation_store.py
tests/test_lifecycle_investigation_target.py
tests/test_lifecycle_source_progress.py
tests/test_lifecycle_web_attended_concurrency.py
tests/test_lifecycle_web_claude.py
tests/test_lifecycle_web_controller.py (deleted)
tests/test_lifecycle_web_frontend_contract.py
tests/test_lifecycle_web_gaps.py
tests/test_lifecycle_web_investigation_budget.py (deleted)
tests/test_lifecycle_web_preflight.py (deleted)
tests/test_lifecycle_web_routes.py (deleted)
tests/test_lifecycle_web_store.py
tests/test_lifecycle_web_usage_journal.py
tests/test_security_lifecycle_routes.py
tests/test_security_lifecycle_web_finding.py
```

The ignored report, XML artifacts and isolated state are excluded from the product commit. All parent-owned plan/progress/docs/evidence/schema drafts were neither edited nor staged. No additional subagents, provider requests, production store/config/.env/credential reads, App lifespan/start/restart, destructive schema work, merge or push occurred. Local source/test diff review found no additional issue after the bounded route ordering correction; parent owns independent review and later full-suite evidence.

`git diff --check` and staged diff checks passed. The commit contains exactly the 29 paths above; parent-owned dirty documents/evidence remain outside it.
