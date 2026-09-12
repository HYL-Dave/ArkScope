# Task 2: C11 Current News Routing Closure

Read the binding plan: docs/superpowers/plans/2026-09-13-news-routing-cleanup.md.
The controller has source-reviewed its scope and added the HTTP405 and IBKR
health clarifications. Read its entire owned-file and acceptance sections.

## Execution

You are the sole product writer and test runner ONLY after Task1 handoff. Work in
/tmp/arkscope-research-output-boundary. Controller will provide the exact base.
No other worktree, production DB/config/key, provider request, external CLI,
App process, install, merge/push, schema change or stored-key deletion. Do not
spawn agents. Do not stage/commit: controller owns Git. Use apply_patch manually.
Use the current workspace's copied offline harness, never older plan scratch.

Workspace: .superpowers/sdd/2026-09-13-maintenance-closures/
Runner: /home/hyl/.virtualenvs/llm_app/bin/python -B WORK/run_checks.py
  unique-run-name backend -q tests/...
  unique-run-name collect tests/...
  unique-run-name frontend test -- src/...
  unique-run-name frontend run typecheck
All commands/outputs are create-only receipts. Preserve failed runs and report
their reasons. Existing upstream runners use audit hooks, not a claimed OS
sandbox. Stay offline and disposable. Do not modify runner guards to pass tests.

First baseline the owned backend tests, capture exact pre-change collection.
Add actual disposable-profile false/malformed-old-setting regression owners
before product edits. Preserve assertions' RED outputs. Implement all callers
and test collateral, not forwarding aliases or ignored legacy kwargs. Capture
post-change collection and enumerate removed/added node IDs with replacement
owners. Run focused backend + frontend checks, typecheck. Controller will run
the single full suite after review and frozen product/test source.

Inverse mutations must independently reintroduce the obsolete value-validation
and telemetry suppression defects. Each named regression fails, then restore
exact reviewed bytes and rerun. No hidden expected-failure flags or weakening
current-setting validation. Report commands and product hashes around mutations.

## Concrete Preflight Notes

- resolve_news_write_route currently validates local_value/local_env but never
  uses them to choose the writer. Delete those args, constants, reads and all
  caller patches. Preserve normalized-required/current-setting blockers.
- read_news_write_route should read only the current normalized key. Missing
  profile remains uncreated, malformed/corrupt current config remains blocked.
- GET /news/status ALREADY reads actual telemetry. Remove its five obsolete
  fields; do not claim that this function previously suppressed sync reads.
- PUT /news/settings disappears. GET /news/{ticker} means that exact literal
  path gets405 for PUT; no404 stub. GET status and normalized setter survive.
- read_news_sync_status actual rows/runs/meta are the news ingest authority.
  overlay_news_sync_status must replace only news, including None when there
  is no current telemetry. Keep non-news sync entries and error semantics.
- Provider health Massive/Finnhub must use actual provider_sync last_success,
  never latest article publication. IBKR combined price/news market-health is
  not controlled by this old switch; retain it and its tests unchanged.
- test_provider_health autouse fixture currently sets old flag false to rely
  on publication dates. Replace that dependency with real disposable sync-run
  fixtures. Keep stale/healthy/key-precedence expectations, plus explicit absent
  telemetry controls. Do not turn useful healthy tests into no_signal cases.
- test_market_data_admin has a helper-flag False/True branch; preserve price
  authority and current news controls while removing obsolete branch selection.
- test_news_normalized_routing has a redundant18-case matrix. Removing old
  dimension is legitimate only with separate actual stored-old-value no-effect
  owners; keep current malformed-value controls explicitly named.
- test_news_settings_route test named completed_audit_marker/409 actually never
  checks409. Transfer its useful normalized/direct contract with accurate name.
- Route count223->222 for exactly the removed PUT. No other route changes.
- Locale removal only five obsolete newsStorage.routing leaves; write/read/
  authority subtrees and similarly named macro fields remain.

## Handoff

Write WORK/task2-report.md. Include paths, commands/counts, red/inverse results,
node ledger, source absence and positive controls, remaining issues, and confirm
all owned subprocesses stopped. Do not alter issue register/priority map/plans;
controller owns those. Conclude with succinct status/report path. No full suite
until controller freezes and owns it. Stop if resolving a concern would require
production access, changing a guard, or a new destructive/security policy.
