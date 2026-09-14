# C12 News Client And CLI Cleanup

**Status: C12 code/entrypoint cleanup CLOSED.** This is not a claim that all
project cleanup, the complete recent-collection policy or SQLite activation is
finished. [Plan](../../plans/2026-09-14-news-client-cleanup.md),
[current policy](../../../design/RUNTIME_AND_RECENT_COLLECTION_POLICY.md).

## Source And Scope

- Base: `8c64f884`, following the shared fourteen-day request target at `8b468771`.
- Product checkpoint: `5eed189eb116ea8accff1c585176bea016bf8971`.
- Final tested source: `c30c5bb89e55e2da8ade503f98e52b715bb2c2d2`; the latter
  changes only the stale brand-copy test allowance found by the first full run.
- Worktree: `/tmp/arkscope-research-output-boundary`, branch
  `codex/sec-research-integration`. Master remains an ancestor, with `0 / 162`
  unique commits before this documentation receipt. No merge or push.

The live Massive/Finnhub transport, parser, rate-limiter and credential owners
now live in `src/news_clients/`. Both current factories use them. The old
`src/collectors` news modules and their custom-date/full-history/checkpoint/
Parquet/global-cursor CLI owners are physically absent, with no forwarders.
Durable `polygon`/`finnhub` source identities remain unchanged. News source
definitions no longer advertise the unused old adapters; the generic adapter
mechanism still serves SEC research.

`daily_update --status` reads current SQLite news telemetry once. It reports
recorded attempts/successes and rows added by the recorded run, not archive
counts or inferred completeness. Missing, unavailable, partial and meta-only
failure states stay distinct; stored diagnostic errors use the existing
diagnostic redactor. Current collection dispatch, source/market/Gateway locks,
writer routing, active-universe exclusions and price status remain intact.
Collected files/databases were not opened or deleted.

## Verification

Each complete backend invocation was one `-q tests` process. No other pytest,
scanner, reviewer or product edit ran concurrently. Commands use the existing
offline launcher with isolated HOME/stores, external-network and production
path guards, explicit plugins and Node PATH. No paid/provider calls occurred.
Archived helpers preserve the original workspace-dependent execution context;
they are not standalone commands at their archival location.

| Check | Result |
| --- | --- |
| Cleanup RED | 6 expected failures |
| Client controls | 244 passed |
| Current status RED | 19 expected failures, 31 passing controls |
| First combined check | 263 passed, 2 invalid-fixture failures |
| Stored diagnostic RED | 2 expected credential-output failures |
| Unused telemetry-wrapper RED | 1 expected absence failure |
| Complete focused acceptance | 427 passed |
| First complete backend | 11,167 passed / 1 failed / 12 skipped |
| Brand-allowance correction controls | 79 passed |
| Final complete collection | 11,180 nodes |
| Final complete backend | **11,168 passed / 12 skipped / 0 failures/errors** |

The invalid fixture used `content_kind="headline"`; it was corrected to the
actual `headline_only` schema value without weakening product validation. The
first full failure was `test_massive_brand_surface`'s exact lowercase-copy set:
its old CLI docstring allowance had not moved with the new client. The three-line
test-only correction preserves exact-set checking. Both failed runs remain
archived; final success is a fresh complete run, not combined subset results.

Final wrapper elapsed time: **1,419.277 seconds**; pytest reports 1,415.15 seconds.
[Final reconciliation](checks/final-validation.json) verifies all checks:

- All 11,180 collected identities executed once; no duplicate nodes.
- Compared with the prior 11,114P/12S run: 69 added, 15 removed, net +54.
  The removals are thirteen old-CLI nodes plus two renamed scheduler parameter
  IDs, not fifteen dropped safety properties. See
  [deleted-test ownership](checks/deleted-test-ownership.md).
- The twelve skip identities are unchanged; retained safety, SEC operation and
  citation owners all ran and passed.
- All 1,161 frozen source paths, selected package/runtime identities and runner
  hashes are unchanged before/after. Source collection SHA256:
  `72334fb784a6eaa3eed11c75493f0f09b68c9095b0e147e3e40616f0c0fa63a3`.
- [Relocation proof](checks/relocation.json): sixteen client AST comparisons
  pass, excluding docstrings and explicitly removed storage configuration;
  `daily_update.main` and price-status helper are exact-source identical.

Two scoped independent read-only reviews and the follow-up allowance review
found no actionable regressions; [review receipts](checks/reviews.md) distinguish
their scope from parent-executed tests. Frontend source did not change and its
suite was not rerun in this C12 change.

## Census And Retained Work

[Same-scanner comparison](checks/census.json.gz): 1,177 files read, 4,306
candidates, 3,284 uncertainties. No new candidates, dependency metadata or
untracked-path changes. Four intentional deleted-file coverage reductions and
seventeen new uncertainty IDs retain exit **2** / `review_required: true`.
[Every difference is attributed](checks/census-review.md): sixteen location
replacements, including six CLI help strings misread as SQL, and one deliberate
fresh-import test loader. The candidate total is not confirmed dead code.

Five mixed C15 modules, C20 retained-row/schema disposition and broader census
findings remain open; C21 remains deferred. Account-limit reporting, durable
initial-interval retries and SA Open-first targeting are separate work. The
shared fourteen-day target does not prove account access or returned coverage.

Observed Python-linked SQLite remains **3.37.2**. This change did not install or
activate a runtime, read production configuration/stores, mutate schema, restart
the App or run live services. Actual SQLite packaging/admission and the later
stopped-writer backup/integrity/switch window remain open. Cross-platform and
Python sandbox implementation are not included.

## Artifact Inventory

[Manifest](checks/manifest.json) records size/SHA256 for 53 selected artifacts;
all hashes were read back after sealing. Logs and JUnit XML are losslessly gzip
compressed with deterministic metadata. Fixture databases, credentials, HOME,
temporary caches and other plans' scratch are excluded. Commands, both source
freezes, both full results, their reconciliations and explicit limitations are
retained. The plan-local temporary workspace is disposable after this receipt.
