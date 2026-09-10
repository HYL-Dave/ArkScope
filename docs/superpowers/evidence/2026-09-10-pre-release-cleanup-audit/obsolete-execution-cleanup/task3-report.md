# Task 3: Spent Operators And Duplicate Monitor Scheduler

Task 3 only. All work stayed in the shared linked worktree. `src/service/jobs.py`
was read-only to this task; its concurrent Task 2 cleanup was not staged here.
No shared plan/audit docs, product configuration, data, historical records,
dependencies or credentials were edited. No real-store operator, provider call,
restart, merge or push was performed.

Committed as `2f80f452` on parent `36dac28df44ee6edf98f48d3d10466daeaf06f37`.
Readback verified the commit changes exactly the ten owned paths below and their
working-tree status is clean. `task3-commit.txt` and `task3.patch` preserve the
commit metadata and reviewed patch; shared Task 1 changes remain outside it.

## Changed Paths

Deleted:
- `src/audit/sa_article_reconciliation.py`
- `src/audit/universe_retirement.py`
- `src/audit/ibkr_news_catchup_audit.py`
- `src/audit/__init__.py` (zero bytes, no remaining source members)
- `src/monitor/scheduler.py`
- `tests/test_universe_retirement_audit.py`
- `tests/test_ibkr_news_catchup_audit.py`

Modified:
- `tests/test_monitor.py`: remove five scheduler-only nodes and the now-unused
  AsyncMock import; preserve all 36 original non-scheduler tests; add one real
  engine-backed monitor tool control for normalized tickers and no notifications.
- `tests/test_legacy_agent_surface_retirement.py`: replace the scheduler/engine
  AST preservation owner with two real current-job/engine behavior cases. They
  cover explicit normalized tickers with a price alert and notification, default
  watchlist with no alerts, actual scan metrics, serialized results and a durable
  temporary job history row. All 14 unrelated original tests remain unchanged.

Added:
- `tests/test_spent_operator_cleanup.py`: four physical absence guards.

## Baseline, RED, Green And Mutation

All tests used the approved `offline_pytest.py` launcher with a fresh clean
environment and unique Task 3 workspace/JUnit artifact. `task3-runs.json` records
the exact commands and outcomes. Shared launcher unchanged. The scratch-only
`task3_support/conftest.py` adds node capture, additional access rejection, an
isolated tempfile root, and absent synthetic agent/monitor configuration paths.

| Run | Outcome |
| --- | --- |
| `task3-baseline-collect` | 68 owned nodes collected, including the config-reading node |
| `task3-baseline` | 273 passed, 8 blocked config reads, 1 deselected; scratch setup error |
| `task3-baseline-r2` | 281 passed, 1 deselected, zero denied accesses |
| `task3-red` | Exactly 4 file-present assertion failures; 19 positive controls passed |
| `task3-green` | 270 passed, 1 deselected, zero denied accesses |
| `task3-restore-mutation` | Exactly 4 file-present assertion failures |
| `task3-final-green` | 270 passed, 1 deselected, zero denied accesses after mutation removal |
| `task3-final-collect` | 57 owned nodes collected |

The first baseline setup redirected agent `_CONFIG_PATH`, but the actual loader
uses `_MAIN_CONFIG_PATH`; the guard rejected all eight attempted reads before
access. Correcting that scratch-only binding produced the clean baseline before
any product or owned-test edit. No product config or shared launcher was changed.

Deliberate exclusion throughout execution:
`tests/test_legacy_agent_surface_retirement.py::test_discord_runtime_config_and_dependency_are_absent`.
It reads repository config, remains unchanged, and is included in node collection.
The parent explicitly owns running it in the integration suite. No Node-dependent
tests were required here.

For the restore-file mutation, all four original module bodies were restored
with apply_patch, not stubs. `task3-mutation-restored.diff` is empty (git diff
exit 0), and `task3-mutation-restored.sha256` records their exact hashes. Each
absence owner failed at its file-exists assertion. All four files were removed
again before the final green run. No mutation is included in the source patch.

## Exact Node Accounting

`task3-node-accounting.json` contains every removed, new and retained node ID,
per-file counts, the migrated owner mapping and the broad before/after sets.

- 18 removed node IDs: 7 universe operator, 5 IBKR audit, 5 scheduler-only,
  and 1 obsolete preservation owner.
- 7 new node IDs: 4 absence cases, 2 current engine/job cases, 1 monitor tool case.
- Net -11: owned collection 68 -> 57; selected collateral baseline 281 -> 270.
- 50 owned node IDs retained, including all 36 non-scheduler monitor nodes.

No deleted audit reporting/conversion assertion is claimed as a current product
behavior. Current preservation coverage is the real SA reconciliation unit,
backend and schema suites; active universe/profile and Former membership suites;
normalized IBKR adapter and durable retry queue suites; monitor/jobs/history
controls. These all ran in both the baseline and final selections.

## References And Documentation Handoff

Before removal, all three audit modules had real argparse CLI main guards.
SA audit accepted `--db`, `--preview-legacy`, `--queue`, `--limit`; universe audit
exposed `preview/apply/export`; IBKR audit accepted market/profile DB paths,
`--as-of` and `--json-out`. These were inspected, never invoked on real stores.
`task3-baseline-source-references.log` confirms only exclusive tests imported the
universe/IBKR operators and independent scheduler; no live importer was found.

`task3-final-entrypoint-references.log` contains only the four new absence-guard
path strings across the searched code, shell and packaging roots. The broader
`task3-final-source-references.log` also records an unrelated generic repository
inventory fixture `src/audit/operator.py`, which is not an entrypoint and stays.
No package forwarding export or retired handler was added.

Current documentation handoff for the parent:
- `docs/design/DESKTOP_APP_VISION_DRAFT.md:246` still describes the reusable
  monitor modules as `engine/scheduler/notifiers/watchers`. Its current reusable
  component list should describe the engine and current service job, despite the
  document's dated draft introduction. This is a stale component description,
  not a live operator command recipe.
- No active command recommendation was found in README, PROJECT_STRUCTURE or
  searched current docs. The dated July 6 scripts/catch-up entries in
  `docs/design/PROJECT_PRIORITY_MAP.md` and archived plans/receipts stay historical.
- The parent owns updating current C14/C16 disposition/checkpoint text in the
  shared audit/plan docs; this task did not rewrite their dated findings.
- Repository `config/` was not searched or opened under the access restriction.

## Review And Scope Checks

The owned diff was reviewed against Task 3/C14/C16. All retained monitor test
bodies and unrelated legacy assertions are unchanged; current job dispatch and
engine source were not modified. `task3-preserved-source.diff` is empty for the
engine, exports, watchers, dedup, notifiers, tools, different live SA reconciliation
module/store/backend, active universe and Former membership source. `task3-diff-check.log`
is clean. Independent whole-slice review and the full backend suite remain with
the parent; neither is claimed by these focused results.
