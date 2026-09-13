# Task 7 Report

Source: `936ede10f04c370bf2322ee70833f9e0f29b7a44` on `codex/sec-research-integration`.
BASE: `d2f491c130f10c738b2158e76e3e536df207e927`.
[Commit and exact scope](task7-commit.json): 17 production files, 11 test files; 1499 insertions/45 deletions. All committed source hashes match the verified files. Controller docs/evidence remain unstaged.

## Delivered Contracts

- `sec_research_filings` defaults disabled, interval 1440 minutes, `writes_market_db=True`, `universe_tickers=False`. Existing enable/interval/Run Now controls and scheduler exclusion are reused. No old SEC enabled key, identity/env inheritance, provider fallback, generic job lock or job_runs enum expansion.
- Every run reads authoritative membership: valid empty succeeds without credentials, transport or a new acquisition timestamp; unavailable/malformed membership fails without dispatch and retains prior rotation. Observed symbols are distinct from SEC identifiers: up to 100000 members, trim/uppercase only, 1-256 printable characters each. `BRK B` stays `BRK B`, unresolved with `sec_issuer_invalid`, while `ONE` acquires. Missing/ambiguous symbols retain typed outcomes; canonical CIKs deduplicate. SEC parsing and URL/CIK admission remain unchanged.
- Scheduled receipts explicitly use `scope="recent"`: only current submissions and Company Facts, no historical traversal or document prefetch. Default on-demand `full` receipts select their own continuation. Stored latest reads see recent data with honest `historical_not_requested` coverage; exact receipt/capture/cursor pins remain immutable.
- Bounds are 500 issuer dispatches, 1001 admitted source attempts (at most one map plus two per issuer), 900 seconds, injectable downward. Checks run before each source and through existing governor/body checkpoints; timeout is at most 30 seconds and the remaining budget. No rate-limit retries. Metadata keeps the 16 MiB per-response ceiling, not a 12 MiB aggregate batch ceiling. Synchronous in-flight work safely unwinds; instantaneous deadline preemption is not claimed.
- Append-only running/terminal checkpoints persist admission, attempted/confirmed/failed/deferred CIKs, unresolved symbols, receipt/map bindings and remaining rotation. Fresh membership intersects continuation before map work. Waiting survivors precede new CIKs; each attempted CIK moves behind waiting members, including failures. Failed map observations retain unresolved continuation without dispatching stale resolutions.
- Batch states are `running/succeeded/partial/failed`. Incomplete work with committed sources is partial; incomplete work without acquisition is failed. A confirmed issuer requires successful recent submissions plus facts. Last attempted batch, last successful issuer acquisition and last fully completed batch are independent; valid empty completion does not advance acquisition. SEC partial stays partial in scheduler status, with audit `failed/sec_schedule_partial`; malformed adapter output becomes `failed/sec_schedule_result_invalid`. News/macro contracts are unchanged.
- Filing/fact counters count source-bound normalized observations for 10-K/10-Q/20-F/40-F and amendments, not new rows, unique securities or provider HTTP confirmations. Raw source bytes/hashes and Decimal precision are unchanged. `request_count` means admitted attempts, including map attempts, not confirmed HTTP.
- Canonical schema adds receipt scope and `sec_research_schedule_batches` plus immutable triggers. Payloads are bounded to 16 MiB, outcomes to 500, each outcome count to 100000 and batch counts to 50000000. Validators enforce terminal accounting, SQLite-safe receipt/map IDs, hidden reference existence/scope/counts and SQL-column/payload agreement. Export/admin verify every checkpoint; `schedule_batches` counts checkpoint rows, not distinct batches. Older schema mismatch is explicit; no migration/reset.
- Stored-only `GET /sec-research/schedule-status` precedes the dynamic CIK route. API envelopes map succeeded to ok, partial/running to partial, failed to unavailable; absent/corrupt stores have typed unavailable states and nullable timestamps, without schema installation/acquisition. An existing operation lock may be created on an absent-store read.
- Actual Settings uses its existing shared schedule provider. Terminal SEC changes refresh local status/capacity only, preserve dirty/saving budget drafts, pinned readers and cursor snapshots, and ignore unrelated source completion. Budget PUT never enables or dispatches. Next eligible time is not guaranteed provider dispatch time.

Required adjacent boundaries: `store/service/queries/tool_service` separate acquisition scope from latest stored reads; `operations._verify_database/_COUNTS` include new hidden batch references. These were approved preflight interfaces. No Task6 publication-repair logic was edited.

## Verification

| Final receipt | Result |
| --- | --- |
| 79 backend | 2448 passed across 43 focused SEC/scheduler/universe/transport files; zero failures/errors/skips |
| 81 frontend | 449 passed across 28 actual Settings, scheduler, citation, API and locale owners |
| 82 build | TypeScript and Vite passed |
| 83 literals | 37 candidates, 20 signatures, 0 debt, 20 allowlist entries |
| 80 browser | en/zh-Hant, 1280x960 and 390x844; four workflows passed, 16 screenshots |
| 63-78 inverses | Eight final-source mutants failed as intended; every exact restoration passed |

[All 83 runner receipts](task7-receipts.json) retain commands, logs, hashes, counts, failures and dispositions, including all 39 nonzero exits. Small RED/GREEN cycles include scope, bounds, runtime/API, Settings, integrity (52/53) and controller-found mixed-membership failure (61/62). No failure was suppressed and no runner guard changed.
[Test inventory](task7-test-inventory.json): +63 backend and +3 frontend cases, no removals; two frontend title renames explicitly reconciled. Locale inventories remain exact: +23 leaves/language, settings 1037, total 3009.
No full backend suite was run; the controller owns the frozen full run and independent review.

[Inverse stages](task7-inverse-proof-stages.json) distinguish ten checkpoint executions from eight post-integrity/post-membership final-source executions. [Final recipes](task7-final-inverses.json) and [checkpoint recipes](task7-inverse-recipes.json) retain all 40 original/mutant source files, exact replacement recipes, selectors and red/restored commands. Hash-only proof is not used. Runs 34 and 46 caught scope violations before historical dispatch; runs 48 and 65 actually dispatched the injected historical pointer and failed the exact URL inventory.

## Browser And Inventories

[Final browser results](task7-80-browser-final-membership/browser/browser-results.json), [API requests/bodies](task7-80-browser-final-membership/browser/api-requests.json), and [source/body inventory](task7-80-browser-final-membership/browser/source-inventory.json) retain real local route/service/store responses, generated source bytes, lengths/hashes and typed failures. The complete [source/evidence inventory](task7-source-inventory.json) lists changed files, guard/helper hashes and every final screenshot/body file.

Workflows cover enable then disable, interval 720 then 1440, real shared Run Now with partial acquisition, catalog paging, explicit document pinning and dirty budget 150 across completion. Pins/text/catalog hashes and read-request inventory remain stable; schedule completion dispatches no document/history request. Measurements show no panel overlap/clipping or document overflow. The existing shared table scrolls horizontally on mobile; both control sides are captured.

All 168 loopback API responses were 200; no page/console errors or external browser requests. Fixture totals: 23 metadata attempts, two seed-only document attempts, 20 generated response bodies and five typed failures. Scheduled portions admit exactly five metadata attempts per case. The seed's separate failed historical attempt is not a scheduled request or an invented successful response.

Run23's unrelated price request-error/Loading noise came from omitted fixture endpoints, not a demonstrated product defect. Neutral generated unrelated responses removed it in31/59/80; endpoint omissions and scope are explicitly listed in browser-results. Only SEC/shared-scheduler behavior is verified, not whole Settings/provider health. The existing generic Run Now "started" notice is retained. Worker visually inspected final80 desktop/mobile status, controls and pinned screenshots; controller previously inspected31.

## Residual Risks And Handoff

- No live provider, production universe sizing, throughput or instantaneous 15-minute preemption was tested. No production DB/config/.env/credential access, installation, App restart, destructive rollout, merge or push occurred.
- Append-only checkpoint metadata grows; no automatic compaction or actual-store schema rollout is included.
- Frontend81 retained 37 React act-environment warnings; baseline attribution was not independently established. Build82 retained the 1201.53 kB minified / 360.97 kB gzip bundle warning. No unrelated diagnostic suppression or budget-button restyling.
- [Final evidence audit](task7-84-final-audit/command.json) verifies hashes, mutation replay equivalence, generated body integrity, browser measurements and stopped runners/servers. Hooks and signing were disabled only for the commit command, not global configuration. Owned worktree clean, index empty, controller files unstaged; no active worker runner/server.
