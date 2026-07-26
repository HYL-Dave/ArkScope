# ArkScope Coverage v2 Session-Truth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:using-git-worktrees` before Task 0,
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task,
> `superpowers:test-driven-development` for every behavior change,
> `superpowers:requesting-code-review` before integration, and
> `superpowers:verification-before-completion` before any passing or complete
> claim. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Status: IMPLEMENTATION COMPLETE - INDEPENDENT REVIEW PENDING**

Review packet:
`docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md`.

**Goal:** Replace maximum-relative market-data coverage with an offline,
read-only XNYS/RTH slot-grid truth model, expose its closed semantic states in
Settings in both locales, and prevent unproven gaps from entering automated
price repair.

**Architecture:** A pinned offline calendar adapter and reviewed official
fixture manifest feed one calendar-health composer. A read-only SQLite
observation reader retains every row inside each real session window, while a
pure classifier alone decides exact slot matches, unmatched rows, ticker
states, and the ordered day state. A service projects those facts into one V2
DTO. The frontend only maps closed IDs to localized copy. The old
maximum-relative DTO and `missing_tickers` planner feed are retired atomically;
no replacement repair planner is introduced.

**Tech Stack:** Python 3.10, `exchange_calendars` 4.13.2, pandas 2.3.1,
NumPy 1.26.4, SQLite URI read-only mode, FastAPI/Pydantic, pytest, React 18,
TypeScript 5.9, i18next, Vitest, and Playwright/Chromium for release evidence.

---

## Design Authority

1. Product and behavior authority:
   `docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md`.
2. Grounded evidence:
   `docs/design/COVERAGE_V2_GROUND_TRUTH_INVENTORY.md`.
3. Sequence authority: `docs/design/PROJECT_PRIORITY_MAP.md`.
4. Small-issue disposition authority:
   `docs/design/ENGINEERING_ISSUE_REGISTER.md`.
5. Terminology authority: `docs/design/ARKSCOPE_TERMINOLOGY.md`.
6. Behavioral base: clean branch tip `7a4bf6da`. Commits after product base
   `f019f9fa` are docs-only.

If implementation needs to contradict any authority above, stop and amend the
authority before changing product code.

## Independent Spec-Review Resolution

Independent review returned GREEN with zero findings. One plan-level reminder
is binding:

- the new closed enums require bilingual resource leaves;
- this plan must state the exact delta;
- the existing resource inventory node must evolve in place without changing
  its node ID; and
- Settings `694` and total `1794` leaves per locale are grounded baselines,
  not values to copy without rederiving in Task 0.

This plan resolves the reminder with an exact `+32/-13` resource ledger, net
`+19`: Settings `694 -> 713` and total `1794 -> 1813` leaves per locale. The
existing node remains named:

```text
contains the reviewed remaining-surface namespace inventory in both locales
```

## Independent Plan-Review Resolution

Independent full-plan review returned substantive GREEN with two required
accounting-composition corrections and one narrative correction. All three
were verified against the current node/key sets rather than accepted from the
review prose alone:

1. `test_route_registered` exists before and after with the exact same node
   ID. It evolves in place. Therefore `test_trading_day_coverage.py` is
   `+14/-18`, not `+15/-19`.
2. The current 25-leaf coverage resource tree and reviewed 44-leaf target have
   a 12-path intersection. The real resource ledger is `+32/-13`, net `+19`,
   not `+19/-0`.
3. The old route suite is not wholly max-relative. Stable route, storage,
   alias, ordering, and diagnostic properties are carried by named V2
   successors; only the 18 obsolete node IDs are removed.

The plan-clearance node/resource targets do not move. At that checkpoint the
backend comm composition is `+68/-37`, net `+31`, rather than `+69/-38`. The exact clearance commit
containing all reviewed amendments is
`PLAN_REVIEW_CLEARANCE_COMMIT=f6cbcb6e2343c14cd185e0f7e766ce98e77cc8db`.
The following docs-only pointer commit changes no authority or product bytes.

## Task 6 Independent Review Resolution

Independent Task 6 review found that the first implementation preserved the
net collection target but left four unsafe legacy seams: the public schedule
route still required provider readiness, legacy state recognition was
best-effort, status projection exposed resumable planner metadata until a new
run, and continuation clearing preceded terminal audit. Review also identified
one stale operator instruction and two test IDs whose names asserted the
opposite of their evolved bodies.

The reviewed correction is binding:

1. `price_backfill` bypasses provider-readiness checks at both the route and
   scheduler boundaries while retaining the write-permission gate for durable
   telemetry.
2. Any durable row that cannot prove the closed V2 reason-code/result shape is
   `legacy_unproven_gap`; empty, unknown, malformed, and unreadable state fail
   closed.
3. Public status projects a fixed safe failure and never exposes legacy plan or
   continuation content.
4. Terminal job audit must succeed before legacy continuation state is cleared;
   audit failure preserves the previous row for retry.
5. `src/api/routes/schedule.py` is added to the reviewed modify set.
6. The two misleading historical node IDs are retired and replaced with
   behavior-accurate IDs. This changes Task 6 from `+5/-19` to `+7/-21`, and
   the backend comm from `+68/-37` to `+70/-39`, without changing final `4744`
   or focused `225`.

## Locked Implementation Decisions

1. Runtime calendar is pinned `exchange_calendars==4.13.2`, XNYS, offline.
2. Official NYSE fixtures outrank package output in tests.
3. Requirements own one reviewed Python solution, including NumPy/pandas and
   calendar transitive dependencies. An unreviewed major upgrade is a stop.
4. Calendar lookup uses explicit manifest start/end bounds; package defaults
   are not a release-horizon authority.
5. `market_scope="us_listed_equity_proxy"` and
   `coverage_session="rth"` are separate closed enum axes.
6. Slots are exact 15-minute starts in half-open `[open, close)`.
7. Observation reading filters only by session windows. It must retain
   off-grid rows so the classifier can count them.
8. The classifier is pure and receives an injected clock. No classifier helper
   may read wall-clock time.
9. Session completion is actual close plus the existing 30-minute settle
   buffer.
10. An absent exact observation is `unknown`, not `missing` with an unknown
    reason.
11. `unmatched_rth_row_count` counts physical in-window off-grid rows. Such a
    row fills no expected slot and changes no coverage state.
12. Day-state precedence is ordered and exclusive:
    `unknown` calendar, `non_trading`, `in_progress`, all-zero `unknown`,
    observed `partial`, `indeterminate_tickers`, then `complete`.
13. `partial` plus all-unknown tickers remains `partial`; unknown counts and
    IDs remain separately visible.
14. Unknown/provider-error tickers enter neither planner work nor exclusions.
15. Enum consumers use exact exhaustive matches. Prefix, substring, and prose
    parsing are forbidden.
16. The old max-relative facts, old status IDs, `missing_tickers`, and planner
    feed retire in one product checkpoint.
17. Legacy saved planner continuations fail closed with
    `legacy_unproven_gap`; they are never translated into V2 work.
18. This unit adds no repair, database schema, migration, provider call,
    Gateway call, PostgreSQL path, formatter change, or CSS by default.

## Grounded Baseline

All values below were rederived on clean `7a4bf6da` on 2026-07-26.

| Gate | Baseline |
| --- | ---: |
| Backend full collection | `4713` nodes |
| Backend full sorted node-list SHA-256 | `a3b91ea6eed808afb7aa7dc860a9f5f8e30de9dd770a9f06245c35d0f04a5d6a` |
| Backend focused collection/run | `4 files / 194`, green |
| Backend focused sorted node-list SHA-256 | `bc406d0a5c4e709c2204100a11b784e24692889a0824ce99e20bab2a07537ce7` |
| Frontend full collection | `95 files / 1063` nodes |
| Frontend full sorted relative node-list SHA-256 | `a93c02bc28d1924f23f7895338d723e968dcb389a494ff0e0f993e4c092019d4` |
| Frontend expanded focused collection/run | `7 files / 109`, green |
| Frontend focused sorted relative node-list SHA-256 | `3967dee8142aee9e60c488df37ef0f6157504140cd859a8c75e17be3af3f8318` |
| i18n resources per locale | Settings `694`; total `1794`; coverage subtree `25` |
| i18n scanner, two consecutive runs | `36/20/0/20`, scope `src/**` |
| Installed Python | `3.10.12` |
| Calendar package | absent |

Backend focused distribution:

```text
tests/test_trading_day_coverage.py    19
tests/test_market_data_direct.py      63
tests/test_scheduler_planner.py        9
tests/test_data_scheduler.py         103
                                      ---
                                      194
```

Frontend expanded focused distribution:

```text
src/SettingsPostPgExitStorage.test.ts        8
src/SettingsProviderConfig.test.ts           36
src/dataSourceSchedulePolling.test.ts         3
src/dataSourcesPresentation.test.ts           4
src/i18n/resources.test.ts                    14
src/marketDataDisplay.test.ts                 32
src/settings/settingsBackendCopy.test.ts      12
                                               ---
                                               109
```

The exact Settings test path must be rederived with `rg --files` in Task 0;
the table uses the Vitest-reported web-app-relative path. A path-layout drift
before edits is a stop, not permission to silently change the focused set.

### Baseline commands and hash recipes

Pytest hashes emitted `file::node` IDs as-is after bytewise sort:

```bash
pytest --collect-only -q > /tmp/coverage-v2-backend-full.txt
pytest --collect-only -q \
  tests/test_trading_day_coverage.py \
  tests/test_market_data_direct.py \
  tests/test_scheduler_planner.py \
  tests/test_data_scheduler.py \
  > /tmp/coverage-v2-backend-focused.txt

sed -n '/::/p' /tmp/coverage-v2-backend-full.txt | LC_ALL=C sort \
  | sha256sum
sed -n '/::/p' /tmp/coverage-v2-backend-focused.txt | LC_ALL=C sort \
  | sha256sum
```

Vitest hashes `web-app-relative-file<TAB>node-name` after bytewise sort. Use
the same JSON collector and `jq` recipe as I18N-6/SA Extension evidence; do not
hash raw absolute paths. Vitest 4 treats the token after `--json` as an output
path, so every focused filter must precede a final bare `--json`. Never run
`vitest list --json <filter>` or `--json=true`; either shape writes into a
repository path instead of emitting JSON to stdout.

```bash
cd apps/arkscope-web
npx vitest list --json > /tmp/coverage-v2-frontend-full.json
npx vitest list \
  src/SettingsPostPgExitStorage.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/i18n/resources.test.ts \
  src/marketDataDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts \
  --json \
  > /tmp/coverage-v2-frontend-focused.json

jq -r '.[] | [.file, .name] | @tsv' /tmp/coverage-v2-frontend-full.json \
  | sed "s#$(pwd)/##" | LC_ALL=C sort | sha256sum
jq -r '.[] | [.file, .name] | @tsv' /tmp/coverage-v2-frontend-focused.json \
  | sed "s#$(pwd)/##" | LC_ALL=C sort | sha256sum
```

## Exact File Map

### Create

```text
src/market_coverage/__init__.py
src/market_coverage/models.py
src/market_coverage/calendar.py
src/market_coverage/official_nyse_sessions_v1.json
src/market_coverage/observations.py
src/market_coverage/classifier.py
src/market_coverage/service.py
tests/test_market_coverage_dependencies.py
tests/test_market_coverage_calendar.py
tests/test_market_coverage_classifier.py
tests/test_market_coverage_observations.py
tests/test_market_coverage_boundaries.py
apps/arkscope-web/src/coverageV2Contract.test.ts
docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md
```

### Modify

```text
requirements.txt
src/market_data_direct.py
src/api/routes/market_data.py
src/api/routes/schedule.py
src/service/data_scheduler.py
tests/test_trading_day_coverage.py
tests/test_data_scheduler.py
apps/arkscope-web/src/api.ts
apps/arkscope-web/src/marketDataDisplay.ts
apps/arkscope-web/src/marketDataDisplay.test.ts
apps/arkscope-web/src/settings/DataStorageSection.tsx
apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts
apps/arkscope-web/src/SettingsProviderConfig.test.ts
apps/arkscope-web/src/dataSourceSchedulePolling.test.ts
apps/arkscope-web/src/dataSourcesPresentation.test.ts
apps/arkscope-web/src/settings/settingsBackendCopy.test.ts
apps/arkscope-web/src/i18n/resources/en/settings.ts
apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts
apps/arkscope-web/src/i18n/resources.test.ts
docs/design/ARKSCOPE_TERMINOLOGY.md
docs/design/ENGINEERING_ISSUE_REGISTER.md
docs/design/PROJECT_PRIORITY_MAP.md
docs/superpowers/specs/2026-07-26-coverage-v2-session-truth-design.md
docs/superpowers/plans/2026-07-26-coverage-v2-session-truth.md
```

### Delete

```text
src/scheduler_planner.py
tests/test_scheduler_planner.py
```

### Protected byte-identical families

- all schema, migration, and migration-marker files;
- `src/market_data_admin.py`, `src/scheduler_state.py`, and explicit generic
  price backfill/executor owners outside the two authorized source files;
- provider, collector, `prices_runtime`, data-source, query-tool, prompt, and
  agent owners;
- extension and Electron trees;
- `package.json`, npm lockfiles, and desktop package metadata;
- all four web CSS files and every formatter owner from
  `I18N_FORMATTER_INVENTORY.md`;
- profile and market database bytes during production read-only evidence.

Any required edit outside the create/modify/delete maps is a stop-and-amend
event. No file is admitted merely because a test can be made green by touching
it.

## Exact Test Ledger

### Backend

| Owner | Add | Remove | Final contribution |
| --- | ---: | ---: | ---: |
| `test_market_coverage_dependencies.py` | 6 | 0 | 6 |
| `test_market_coverage_calendar.py` | 10 | 0 | 10 |
| `test_market_coverage_classifier.py` | 18 | 0 | 18 |
| `test_market_coverage_observations.py` | 10 | 0 | 10 |
| `test_market_coverage_boundaries.py` | 5 | 0 | 5 |
| `test_trading_day_coverage.py` | 14 | 18 | 15 |
| `test_scheduler_planner.py` | 0 | 9 | 0 |
| `test_data_scheduler.py` | 7 | 12 | 98 |
| **Total** | **70** | **39** | **+31 net** |

Expected backend final collection: `4713 + 70 - 39 = 4744`.
Expected focused collection: `194 + 70 - 39 = 225`.

The trading-day suite is replaced as a contract, but
`test_route_registered` evolves in place with its exact ID. Exactly 18 old
node IDs are removed and 14 new IDs are added. Stable alias, ordering, route,
storage-availability, sanitized-503, and provider-diagnostic properties are
carried by named V2 successors; the nine planner nodes disappear with their
product owner. Exactly twelve scheduler nodes disappear: the ten retired
planner-consumer nodes plus two misleading historical IDs:

```text
test_price_backfill_uses_planner_scope_no_pg_no_mirror
test_p0c1_price_backfill_runs_prices_worker_with_planned_scope
test_v13_gate1_coverage_window_matches_planner_max_days
test_v13_gate2_provider_errors_exclude_unresolvable
test_v13_partial_when_deferred_and_writes_continuation
test_v13_attended_scheduler_skips_pending_continuation
test_v13a_manual_continue_consumes_saved_deferred_not_fresh_plan
test_v13a_manual_continue_carries_remainder_when_over_budget
test_v13_no_gaps_is_noop_success
test_v14_status_snapshot_exposes_durable_state_and_gap_planned
test_price_backfill_serializes_behind_ibkr_lock
test_price_backfill_empty_scope_fails_loud
```

Exactly seven scheduler IDs are added: the five contract replacements plus two
behavior-accurate successors:

```text
test_coverage_derived_price_backfill_is_deliberate_noop
test_unknown_tickers_and_provider_errors_never_reach_price_executor
test_legacy_unproven_gap_manual_continuation_is_rejected_without_worker
test_legacy_unproven_gap_scheduler_continuation_is_rejected_without_worker
test_status_snapshot_preserves_durable_state_without_planner_metadata
test_price_backfill_ignores_gateway_lock_but_keeps_source_lock
test_price_backfill_does_not_resolve_scope_for_deliberate_noop
```

### Frontend

| Owner | Add | Remove |
| --- | ---: | ---: |
| `marketDataDisplay.test.ts` | 6 | 2 |
| `SettingsPostPgExitStorage.test.ts` | 2 | 0 |
| `coverageV2Contract.test.ts` | 3 | 0 |
| **Total** | **11** | **2** |

Expected frontend final collection: `96 files / 1072` nodes.
Expected expanded focused final collection: `8 files / 118` nodes.

The two removed IDs are:

```text
renders backend coverage_status (UI does not re-derive completeness)
distinguishes weekend vs holiday for non_trading
```

Existing mounted, resource, backend-copy, locale-switch, and diagnostic nodes
evolve in place; none is renamed or removed. The resource inventory node named
in the review resolution keeps its exact ID.

## Exact Resource Ledger

Replace the current `settings.dataStorage.coverage` subtree of `25` leaves
with exactly `44` leaves per locale: `+32/-13`, net `+19`:

```text
base:       title, description, readOnly, lookback, lookbackLabel               5
facts:      universe, interval, marketScope, marketScopeValue, session,
            sessionValue, reviewedThrough, horizonMonths                        8
headings:   date, status, expectedSlots, complete, partial, unknown              6
status:     weekend, marketClosed, inProgress, complete, partial,
            indeterminateTickers, unknown, unavailable                          8
reasons:    calendarUnavailable, dateUnreviewed,
            observationUnavailable, noObservations                              4
health:     fixtureHorizonLow, dateUnreviewed, calendarUnavailable,
            marketDbMissing, marketDbUnreadable, pricesSchemaMissing             6
drilldown:  partialTitle, partialDetail, unknownTitle, unknownDetail,
            unmatched, providerIssues, sessionWindow                             7
                                                                                --
                                                                                44
```

Exactly 12 paths survive in place:

```text
title
description
readOnly
lookback
lookbackLabel
headings.date
headings.status
status.weekend
status.inProgress
status.partial
status.unknown
drilldown.partialDetail
```

Exactly 13 paths are removed:

```text
headings.covered
headings.maxBars
headings.missing
status.completeLike
status.holiday
status.missing
status.thin
drilldown.interval
drilldown.missing
drilldown.missingDetail
drilldown.partial
drilldown.providerError
drilldown.universe
```

Every other path in the 44-leaf inventory is one of the 32 additions.
`drilldown.interval -> facts.interval` and
`drilldown.universe -> facts.universe` are path migrations and therefore each
count as one removal plus one addition. The four retired status meanings and
three retired max-relative headings are semantic removals, not renamed keys.

Use labels followed by values instead of English pluralized sentence
fragments. Representative copy is fixed as follows:

```text
en description: Compares local observations with the expected 15-minute RTH grid; absent observations remain unknown without independent evidence.
zh description: 以正規交易時段的預期 15 分鐘格線比對本地觀測；沒有獨立證據時，未觀測到的格子只標為未知。
en readOnly: Read-only diagnostic; does not start a repair or supply planner work.
zh readOnly: 唯讀診斷；不會啟動修復，也不會產生 planner 工作。
```

`marketScopeValue` is "US-listed equity proxy" / "美國上市股票代理範圍".
`sessionValue` is "Regular trading hours (RTH)" / "正規交易時段（RTH）".
Add both pairs to `ARKSCOPE_TERMINOLOGY.md`. Do not localize ticker symbols,
source diagnostics, timestamps, or provider names.

## Stop Conditions

Stop, document evidence, and obtain reviewed scope amendment if any occurs:

1. Task 0 node counts/hashes differ before product edits.
2. The exact Python 3.10 dependency solution cannot be installed without an
   unreviewed major upgrade or a conflict with existing requirements.
3. Pinned XNYS disagrees with any official fixture.
4. The fixture cannot provide at least 12 reviewed forward months at release.
5. Calendar/session code needs Gateway, provider, PostgreSQL, or network I/O.
6. Accurate classification appears to require a database schema or migration.
7. Any absent slot is proposed as actionable `missing` without a separately
   reviewed evidence authority.
8. A legacy continuation would be resumed, translated, or silently discarded.
9. The frontend would need to infer state from counts/prose or parse enum
   prefixes/substrings.
10. Production evidence would write a database or trigger a repair/provider
    path.
11. A protected file must change.
12. Visual evidence finds overflow requiring CSS. Follow the reviewed CSS
    deviation protocol: record geometry and selector, add a RED named
    `ShellCss` node, authorize one exact hunk, rerun boundary triples, and
    revise accounting before editing CSS.

---

## Task 0: Clear Plan Review And Reproduce The Baseline

**Files:**
- Modify only review-authorized docs, including this plan.
- Do not modify product or test files.

- [ ] **Step 1: Read the independent plan review in full.**

Classify every point as required, adopted advisory, or rejected with grounded
reason. Do not implement recommendations from prose without verifying current
code.

- [ ] **Step 2: Fold accepted plan-review amendments into docs.**

Keep this task docs-only. Update the plan status to plan-review GREEN and add
an "Independent Plan-Review Resolution" section that records every decision.

- [ ] **Step 3: Reproduce all baseline counts and hashes.**

Run the commands in "Grounded Baseline", plus:

```bash
pytest -q \
  tests/test_trading_day_coverage.py \
  tests/test_market_data_direct.py \
  tests/test_scheduler_planner.py \
  tests/test_data_scheduler.py

cd apps/arkscope-web
npx vitest run \
  src/SettingsPostPgExitStorage.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/i18n/resources.test.ts \
  src/marketDataDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts
```

Expected: backend `194 passed`; frontend `7 files / 109 passed`; exact hashes
from the baseline table.

- [ ] **Step 4: Reproduce scanner and resource baselines.**

Run the repository scanner twice and the resource tests. Expected both scanner
runs: `36/20/0/20`, scope `src/**`; resources: Settings `694`, total `1794`,
coverage subtree `25`, key parity and non-empty gates green.

- [ ] **Step 5: Reproduce the reviewed dependency probe outside the repo environment.**

Resolve this exact solution under Python 3.10:

```text
exchange-calendars==4.13.2
numpy==1.26.4
pandas==2.3.1
pyluach==2.3.0
toolz==1.1.0
tzdata==2025.2
korean-lunar-calendar==0.4.0
python-dateutil==2.9.0.post0
pytz==2025.2
six==1.17.0
```

Verify XNYS reports:

```text
2025-01-09 closed
2025-07-03 close 13:00 ET
2025-11-28 close 13:00 ET
2025-12-24 close 13:00 ET
2026-07-24 close 16:00 ET
2026-11-27 close 13:00 ET
2026-12-24 close 13:00 ET
2027-11-26 close 13:00 ET
2027-12-24 closed
```

- [ ] **Step 6: Recheck production read-only witnesses and label them observations.**

On the production market DB, record path, file size/mtime, integrity/FK, the
current RTH complete-day witness, duplicate-key count, and off-grid in-window
count. Do not assert any dated ticker/count as a permanent test constant. Do
not open a write transaction.

- [ ] **Step 7: Record clearance authority.**

```bash
git diff --check
git status --short
git add docs/
git commit -m "docs: clear Coverage v2 implementation plan"
git rev-parse HEAD
```

Record the 40-character result in this plan as
`PLAN_REVIEW_CLEARANCE_COMMIT`. Product work may begin only after the commit is
confirmed docs-only and descends from `7a4bf6da`.

---

## Task 1: Pin The Calendar Solution And Official Fixture Authority

**Files:**
- Create: `tests/test_market_coverage_dependencies.py`
- Create: `src/market_coverage/official_nyse_sessions_v1.json`
- Modify: `requirements.txt`

**Accounting:** backend `+6/-0`; full `4713 -> 4719`; focused `194 -> 200`.

- [ ] **Step 1: Write the six dependency/fixture tests first.**

Use these exact IDs:

```text
test_reviewed_python_dependency_solution_is_exact
test_exchange_calendar_imports_on_supported_python
test_xnys_matches_reviewed_full_session_fixture
test_xnys_matches_every_reviewed_early_close_fixture
test_xnys_matches_extraordinary_closure_fixture
test_fixture_release_horizon_covers_twelve_calendar_months
```

The release-horizon node uses the reviewed evidence date
`date(2026, 7, 26)`, not the machine clock. Runtime aging is tested separately
with injected `as_of` dates so the suite does not become a time bomb while a
running build still reports its honest degraded state.

The fixture manifest must contain:

```json
{
  "schema_version": 1,
  "calendar": "XNYS",
  "reviewed_from": "2025-01-01",
  "reviewed_through": "2027-12-31",
  "ordinary_session": {"date": "2026-07-24", "open_et": "09:30", "close_et": "16:00"},
  "early_closes": [
    {"date": "2025-07-03", "close_et": "13:00"},
    {"date": "2025-11-28", "close_et": "13:00"},
    {"date": "2025-12-24", "close_et": "13:00"},
    {"date": "2026-11-27", "close_et": "13:00"},
    {"date": "2026-12-24", "close_et": "13:00"},
    {"date": "2027-11-26", "close_et": "13:00"}
  ],
  "extraordinary_closures": ["2025-01-09"]
}
```

Include source URLs in structured manifest metadata:

```text
https://www.nyse.com/trade/hours-calendars
https://www.nyse.com/publicdocs/ICE_NYSE_2025_Yearly_Trading_Calendar.pdf
https://www.nyse.com/publicdocs/nyse/markets/american-options/rule-interpretations/2025/National_Day_of_Mourning_20250102.pdf
```

- [ ] **Step 2: Run the tests and verify the intended RED.**

```bash
pytest -q tests/test_market_coverage_dependencies.py
```

Expected: six collected; RED because the reviewed requirements and fixture
owner do not yet exist. A network error, missing unrelated package, or malformed
test fixture is the wrong RED.

- [ ] **Step 3: Pin the complete reviewed solution.**

Replace bare `numpy` and `pandas` lines and add the exact calendar solution.
Do not leave duplicate unconstrained lines. The test must inspect installed
metadata and requirements text, proving both declaration and actual solution.

Install only the reviewed solution into the isolated implementation
environment, then verify the resolver:

```bash
python -m pip install \
  exchange-calendars==4.13.2 numpy==1.26.4 pandas==2.3.1 \
  pyluach==2.3.0 toolz==1.1.0 tzdata==2025.2 \
  korean-lunar-calendar==0.4.0 python-dateutil==2.9.0.post0 \
  pytz==2025.2 six==1.17.0
python -m pip check
```

Do not run an unconstrained upgrade. If `pip check` exposes a pre-existing
environment conflict, compare it with the Task 0 probe before attributing it
to this unit.

- [ ] **Step 4: Add the official fixture manifest and verify package output.**

Construct XNYS with explicit `start=reviewed_from` and
`end=reviewed_through`. Convert package timestamps at the adapter edge; never
serialize pandas objects as product DTO values.

- [ ] **Step 5: Run the focused checkpoint.**

```bash
pytest -q tests/test_market_coverage_dependencies.py
pytest --collect-only -q | tail -1
```

Expected: `6 passed`; backend collection `4719`.

- [ ] **Step 6: Commit.**

```bash
git add requirements.txt src/market_coverage/official_nyse_sessions_v1.json \
  tests/test_market_coverage_dependencies.py
git commit -m "test: pin Coverage v2 calendar authority"
```

---

## Task 2: Build The Offline Calendar Adapter And Sole Health Composer

**Files:**
- Create: `src/market_coverage/__init__.py`
- Create: `src/market_coverage/models.py`
- Create: `src/market_coverage/calendar.py`
- Create: `tests/test_market_coverage_calendar.py`

**Accounting:** backend `+10/-0`; full `4719 -> 4729`; focused `200 -> 210`.

- [ ] **Step 1: Write the ten calendar tests.**

Use these exact IDs:

```text
test_calendar_adapter_returns_typed_regular_session
test_calendar_adapter_returns_typed_early_close
test_calendar_adapter_returns_closed_without_named_holiday_claim
test_calendar_adapter_failure_is_typed_unavailable
test_fixture_review_membership_is_independent_of_forward_horizon
test_forward_horizon_uses_calendar_month_boundaries
test_calendar_health_is_ok_for_reviewed_dates_and_healthy_horizon
test_low_horizon_is_degraded_without_erasing_reviewed_history
test_unreviewed_date_is_degraded_and_unclassifiable
test_adapter_failure_makes_health_unavailable
```

`is_reviewed(date)` and `forward_horizon_months(as_of)` must be tested as
independent questions. A reviewed historical date remains reviewed when the
forward horizon is degraded.

- [ ] **Step 2: Run RED.**

```bash
pytest -q tests/test_market_coverage_calendar.py
```

Expected: ten RED nodes because typed models and adapter/composer do not exist.

- [ ] **Step 3: Implement closed models.**

`models.py` owns string enums and immutable dataclasses for:

```text
MarketScope.US_LISTED_EQUITY_PROXY
CoverageSession.RTH
CalendarAvailability.AVAILABLE / UNAVAILABLE
CalendarHealth.OK / DEGRADED / UNAVAILABLE
CalendarDayKind.OPEN / CLOSED / UNKNOWN
```

Represent session open/close as timezone-aware Python datetimes. Validate
`open < close`; reject naive datetimes.

- [ ] **Step 4: Implement `OfficialSessionFixtures`.**

Load the packaged JSON once. Own:

```python
def is_reviewed(self, day: date) -> bool: ...
def forward_horizon_months(self, as_of: date) -> int: ...
```

Use calendar-month arithmetic, not `days // 30`. The fixture manifest, not
the package's distant generation range, is the release-horizon authority.

- [ ] **Step 5: Implement `XnysCalendarAdapter`.**

It may import `exchange_calendars` only in this module. It returns typed
available/open, available/closed, or unavailable results. A closed day has no
invented holiday label. Exceptions become a stable safe code; raw exception
text stays diagnostic-only and is never a state classifier.

- [ ] **Step 6: Implement one `CalendarHealthComposer`.**

The adapter does not own health. The fixtures do not own health. The composer
combines both axes:

```text
adapter unavailable                  -> unavailable
requested date outside reviewed set  -> degraded; date unclassifiable
reviewed date + forward < 6 months   -> degraded; date still classifiable
reviewed date + forward >= 6 months  -> ok
```

- [ ] **Step 7: Verify GREEN and exact count.**

```bash
pytest -q tests/test_market_coverage_dependencies.py \
  tests/test_market_coverage_calendar.py
pytest --collect-only -q | tail -1
```

Expected: `16 passed`; backend collection `4729`.

- [ ] **Step 8: Commit.**

```bash
git add src/market_coverage tests/test_market_coverage_calendar.py
git commit -m "feat: add offline Coverage v2 calendar authority"
```

---

## Task 3: Implement The Pure Slot-Grid Classifier

**Files:**
- Create: `src/market_coverage/classifier.py`
- Create: `tests/test_market_coverage_classifier.py`
- Modify: `src/market_coverage/models.py`

**Accounting:** backend `+18/-0`; full `4729 -> 4747`; focused `210 -> 228`.

- [ ] **Step 1: Write all seven precedence tests first.**

Use these exact IDs and one fixture per unique path:

```text
test_precedence_calendar_unavailable_is_unknown
test_precedence_reviewed_closed_day_is_non_trading
test_precedence_pre_close_buffer_is_in_progress
test_precedence_completed_all_zero_is_unknown
test_precedence_observed_partial_ticker_is_partial
test_precedence_complete_observed_cohort_with_unknown_is_indeterminate
test_precedence_all_tickers_complete_is_complete
```

Each fixture must also satisfy a lower-priority condition where practical, so
the test proves precedence rather than merely mapping an isolated state.

- [ ] **Step 2: Write the remaining eleven classifier tests.**

```text
test_regular_session_grid_uses_exact_half_open_slot_starts
test_early_close_grid_uses_exact_half_open_slot_starts
test_early_close_buffer_changes_only_at_1329_1330
test_partial_plus_unknown_stays_partial_and_preserves_unknowns
test_completed_day_count_equations_hold
test_in_window_off_grid_row_is_counted
test_off_grid_row_does_not_fill_nearest_slot
test_alias_collision_fills_one_slot_only
test_extended_hours_rows_never_fill_rth_slots
test_uniform_truncation_is_partial
test_single_complete_outlier_does_not_hide_truncation
```

The 13:29/13:30 test uses an early close at 13:00 ET and an injected clock. It
must fail only because the classifier has not anchored the existing 30-minute
buffer to the real close.

- [ ] **Step 3: Run RED and inspect failure causes.**

```bash
pytest -q tests/test_market_coverage_classifier.py
```

Expected: exactly 18 RED nodes. The two unmatched tests must be separately
red: one requires counting; the other requires refusing nearest-slot fill.

- [ ] **Step 4: Implement exact slot construction.**

```python
def expected_slot_starts(open_at, close_at, interval):
    cursor = open_at
    while cursor < close_at:
        yield cursor
        cursor += interval
```

Do not encode 26, 14, or 20 as runtime constants. Reject intervals that do not
divide the supplied session in the supported V1 path.

- [ ] **Step 5: Implement pure ticker classification.**

For each canonical ticker, compare exact normalized timestamp identities:

```text
all expected starts observed -> complete
at least one but not all      -> partial
zero                          -> unknown
```

Deduplicate observations for slot occupancy, but count physical off-grid rows
in `unmatched_rth_row_count`. Alias collisions may fill one slot only.

- [ ] **Step 6: Implement ordered day classification.**

Use one explicit branch chain, in this order:

```python
if calendar_unclassifiable: UNKNOWN
elif closed: NON_TRADING
elif now < close + settle_buffer: IN_PROGRESS
elif observed_ticker_count == 0: UNKNOWN
elif partial_ticker_count > 0: PARTIAL
elif unknown_ticker_count > 0: INDETERMINATE_TICKERS
else: COMPLETE
```

No enum is named with a `complete_` prefix. No consumer may use
`startswith`, `in`, or regex matching for enum semantics.

- [ ] **Step 7: Enforce aggregate equations.**

For a classifiable open day:

```text
complete + partial + unknown == universe_size
observed_ticker_count == complete + partial
unknown_ticker_count == unknown
```

For closed/unclassifiable days, coverage counts are absent rather than fake
zeroes.

- [ ] **Step 8: Run GREEN and checkpoint.**

```bash
pytest -q tests/test_market_coverage_classifier.py
pytest --collect-only -q | tail -1
```

Expected: `18 passed`; backend collection `4747`.

- [ ] **Step 9: Commit.**

```bash
git add src/market_coverage tests/test_market_coverage_classifier.py
git commit -m "feat: classify Coverage v2 RTH slot truth"
```

---

## Task 4: Read RTH Observations Without Aligning Or Writing

**Files:**
- Create: `src/market_coverage/observations.py`
- Create: `tests/test_market_coverage_observations.py`
- Modify: `src/market_coverage/models.py`

**Accounting:** backend `+10/-0`; full `4747 -> 4757`; focused `228 -> 238`.

- [ ] **Step 1: Write the ten observation-reader tests.**

Use these exact IDs:

```text
test_missing_market_db_is_typed_unavailable
test_unreadable_market_db_is_typed_unavailable
test_missing_prices_schema_is_typed_unavailable
test_readable_empty_prices_table_is_ok
test_reader_is_read_only_and_preserves_database_bytes
test_reader_assigns_rows_by_utc_session_window_not_date_prefix
test_reader_excludes_extended_hours_rows
test_reader_retains_in_window_off_grid_rows
test_reader_maps_aliases_to_canonical_tickers
test_query_only_rejects_accidental_writes
```

Use temporary SQLite files. The read-only test records SHA-256, size, mtime,
integrity, and foreign-key results before and after. The session-window test
must include an Eastern session whose UTC boundaries make a date-prefix
shortcut demonstrably wrong.

- [ ] **Step 2: Run RED.**

```bash
pytest -q tests/test_market_coverage_observations.py
```

Expected: ten RED nodes because no reader exists. A test that drops the
off-grid row before the reader boundary is invalid and must be corrected.

- [ ] **Step 3: Implement typed observation availability.**

The result distinguishes:

```text
ok
unavailable / market_db_missing
unavailable / market_db_unreadable
unavailable / prices_schema_missing
```

A readable empty `prices` table is `ok` with no observations. Do not collapse
storage failure into an empty list.

- [ ] **Step 4: Open SQLite in enforced read-only mode.**

```python
conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
conn.execute("PRAGMA query_only=ON")
```

Validate the required `prices` columns structurally before querying. Read
aliases and `provider_sync_meta` only when their existing tables are present.
No table creation, migration, temp persistence, or fallback connection is
permitted.

- [ ] **Step 5: Query one bounded UTC span and assign by real windows.**

Bound by the earliest open and latest close for the request. Parse every
timestamp to aware UTC. Assign rows to sorted session windows with a bisect or
equivalent exact interval lookup:

```text
session.open_at_utc <= row.timestamp < session.close_at_utc
```

Do not use `substr(datetime, 1, 10)` to identify the market date. Do not test
grid alignment here.

- [ ] **Step 6: Return every in-window candidate row.**

The reader may canonicalize the ticker through the existing alias map. It may
not deduplicate slot identity or remove off-grid timestamps; those are
classifier responsibilities. Preserve enough row identity for the classifier
to count physical unmatched rows while deduplicating slot occupancy.

- [ ] **Step 7: Verify GREEN and mutation resistance.**

```bash
pytest -q tests/test_market_coverage_observations.py \
  tests/test_market_coverage_classifier.py
```

Expected: `28 passed`. Temporarily filtering off-grid timestamps in the reader
must make `test_reader_retains_in_window_off_grid_rows` RED before restoring.

- [ ] **Step 8: Verify exact checkpoint and commit.**

```bash
pytest --collect-only -q | tail -1
git add src/market_coverage tests/test_market_coverage_observations.py
git commit -m "feat: read Coverage v2 RTH observations"
```

Expected collection: `4757`.

---

## Task 5: Replace The Backend DTO Atomically

**Files:**
- Create: `src/market_coverage/service.py`
- Create: `tests/test_market_coverage_boundaries.py`
- Modify: `src/market_coverage/__init__.py`
- Modify: `src/market_coverage/models.py`
- Modify: `src/market_data_direct.py`
- Modify: `src/api/routes/market_data.py`
- Replace: `tests/test_trading_day_coverage.py`

**Accounting:** `test_trading_day_coverage.py +14/-18`, boundaries `+5/-0`;
task net `+19/-18`. Backend full `4757 -> 4758`; focused `238 -> 239`.

- [ ] **Step 1: Replace the old route suite with fifteen V2 contract tests.**

Evolve `test_route_registered` in place, remove the other 18 old IDs, and add
exactly these 14 new IDs plus that surviving node:

```text
test_service_dedupes_aliases_and_orders_requested_window
test_service_emits_exact_v2_contract_without_retired_fields
test_regular_session_uses_exact_rth_slots_despite_extended_rows
test_early_close_session_uses_derived_fourteen_slot_grid
test_provider_errors_remain_separate_diagnostics
test_calendar_unavailable_returns_unknown_days
test_unreviewed_date_is_unknown_while_reviewed_dates_classify
test_low_fixture_horizon_degrades_health_without_erasing_reviewed_days
test_missing_market_db_is_unavailable_not_empty
test_readable_empty_market_db_is_ok_with_unknown_days
test_route_rejects_unreviewed_interval_with_typed_422
test_route_wires_active_universe_and_v2_service
test_route_preserves_sanitized_active_universe_503
test_route_registered
test_route_coverage_path_is_pure_read_without_provider_scheduler_or_pg
```

The 14-slot early-close assertion is derived from exact expected starts and
the fixture close; it must not import a runtime `14` constant.

- [ ] **Step 2: Add five structural boundary tests.**

Use these exact IDs:

```text
test_market_coverage_package_has_no_provider_gateway_or_pg_runtime_dependency
test_market_coverage_package_exports_no_write_or_repair_operation
test_backend_v2_contract_and_source_contain_no_retired_coverage_fields
test_scheduler_has_no_planner_missing_feed_or_unknown_exclusion_path
test_coverage_enum_consumers_use_exact_exhaustive_matching
```

The retired-token gate scans product DTO/source for the V1 field names from
the spec. It must allow historical docs/tests only where explicitly listed.
The enum gate rejects `startswith`, substring membership, and regex parsing at
every Coverage v2 consumer.

- [ ] **Step 3: Run the 20 new tests and confirm the intended RED.**

```bash
pytest -q tests/test_trading_day_coverage.py \
  tests/test_market_coverage_boundaries.py
```

Expected: `20` collected and RED because the service/route still expose V1.
The structural scheduler test may remain RED until Task 6; document that one
bounded expected RED separately. All behavioral route tests must fail for V2
contract reasons, not import or fixture errors.

- [ ] **Step 4: Implement `TradingDayCoverageService`.**

Resolve `now_et` once, derive the requested dates, ask the fixture and adapter
separately, compose calendar health once, read available session windows once,
classify purely, and project the exact V2 DTO.

The top-level contract is:

```ts
{
  version: 2;
  market_scope: "us_listed_equity_proxy";
  coverage_session: "rth";
  interval: "15min";
  lookback_days: number;
  universe_count: number;
  generated_at_et: string;
  calendar_health: {
    status: "ok" | "degraded" | "unavailable";
    reason_codes: Array<
      "fixture_horizon_low" | "date_unreviewed" | "calendar_unavailable"
    >;
    reviewed_through: string;
    forward_horizon_months: number;
  };
  observation_health: {
    status: "ok" | "unavailable";
    reason_code:
      | "market_db_missing"
      | "market_db_unreadable"
      | "prices_schema_missing"
      | null;
  };
  days: CoverageDayV2[];
  provider_errors: ProviderSyncIssue[];
}
```

Each day follows Section 8.2 of the spec exactly. Counts are `null` for
non-trading and typed calendar/storage failure. `in_progress` exposes session
facts but no completed-session ticker classification.

- [ ] **Step 5: Replace the route implementation.**

Keep `GET /market-data/trading-days`. Resolve the current active universe via
the existing authority. Accept only `interval=15min`; any other interval gets
a typed safe 422. Preserve existing sanitized active-universe 503 behavior.
Do not catch typed health outcomes as transport failures.

- [ ] **Step 6: Retire V1 from `market_data_direct.py`.**

Remove only:

```text
_THIN_BAR_THRESHOLD
_COMPLETE_COVERED_RATIO
summarize_trading_day_coverage
its coverage-only helpers/imports
```

Keep explicit generic market-data executors and their existing 63 tests
unchanged. Update the module boundary comment so it no longer claims ownership
of coverage diagnostics.

- [ ] **Step 7: Prove the atomic DTO.**

Assert the serialized response has no:

```text
max_observed_bar_count, full, well_covered, covered, missing,
missing_tickers, session_complete, thin, complete_like
```

`partial_tickers` remains only with V2 fields
`ticker/observed_slot_count/expected_slot_count`; no `.bars` survives.

- [ ] **Step 8: Run the checkpoint.**

```bash
pytest -q \
  tests/test_market_coverage_dependencies.py \
  tests/test_market_coverage_calendar.py \
  tests/test_market_coverage_classifier.py \
  tests/test_market_coverage_observations.py \
  tests/test_trading_day_coverage.py \
  tests/test_market_data_direct.py \
  tests/test_market_coverage_boundaries.py
```

Expected: all except the single Task-6 scheduler structural assertion green;
the V2 service/route tests are green. Collection is `4758`.

- [ ] **Step 9: Commit.**

```bash
git add src/market_coverage src/market_data_direct.py \
  src/api/routes/market_data.py tests/test_trading_day_coverage.py \
  tests/test_market_coverage_boundaries.py
git commit -m "feat: replace trading-day coverage with V2 truth"
```

---

## Task 6: Retire Unproven Planner Work And Legacy Continuations

**Files:**
- Delete: `src/scheduler_planner.py`
- Delete: `tests/test_scheduler_planner.py`
- Modify: `src/api/routes/schedule.py`
- Modify: `src/service/data_scheduler.py`
- Modify: `tests/test_data_scheduler.py`
- Verify: `tests/test_market_data_direct.py`
- Verify: `tests/test_market_coverage_boundaries.py`

**Accounting:** planner `+0/-9`; scheduler `+7/-12`; task net `+7/-21`.
Backend full `4758 -> 4744`; focused `239 -> 225`.

- [ ] **Step 1: Add the five replacement scheduler tests first.**

```text
test_coverage_derived_price_backfill_is_deliberate_noop
test_unknown_tickers_and_provider_errors_never_reach_price_executor
test_legacy_unproven_gap_manual_continuation_is_rejected_without_worker
test_legacy_unproven_gap_scheduler_continuation_is_rejected_without_worker
test_status_snapshot_preserves_durable_state_without_planner_metadata
```

Use worker/provider spies and assert call count zero. The legacy tests must seed
the real persisted continuation shape, then prove stable failure code
`legacy_unproven_gap`, current continuation removal, a new durable audit
outcome, and no rewrite of historical job rows.

- [ ] **Step 2: Run the five tests and require the correct RED.**

```bash
pytest -q tests/test_data_scheduler.py -k \
  'coverage_derived_price_backfill or unknown_tickers_and_provider_errors or legacy_unproven_gap or status_snapshot_preserves_durable_state_without_planner_metadata'
```

Expected: five RED nodes because the planner path still exists. A worker call,
fresh plan, or accidental provider configuration lookup is evidence of the
legacy path and belongs in the assertion.

- [ ] **Step 3: Remove the ten old planner-consumer nodes and rename two
  contradictory historical IDs.**

Delete only the ten IDs listed in the Exact Test Ledger. Do not rename them to
make the ledger appear additive. Preserve every unrelated scheduler node.
Separately retire the two misleading IDs named in the Task 6 review resolution
and replace them with the two behavior-accurate IDs. This is a reviewed
`+2/-2` composition change, not an attempt to hide removed coverage.

- [ ] **Step 4: Delete planner owner and tests.**

Delete `src/scheduler_planner.py` and `tests/test_scheduler_planner.py` in the
same commit as consumer retirement. `rg` must show zero product imports,
`BackfillPlan`, `plan_price_backfill`, planner max-day constants, and V1
`missing_tickers` feed references.

- [ ] **Step 5: Make coverage-derived `price_backfill` an honest non-action.**

Keep the source ID for durable historical status compatibility, but replace
internal `gap_planned` with `coverage_repair_disabled`. Do not expose either
field in the public status DTO.

Behavior:

```text
no saved continuation:
  succeeded deliberate no-op
  collect.planned = 0
  reason_code = coverage_truth_read_only
  provider/worker/Gateway calls = 0

saved legacy continuation:
  failed
  code = reason_code = legacy_unproven_gap
  provider/worker/Gateway calls = 0
  current continuation cleared
  new audit outcome recorded
  historical rows unchanged
```

The source must not perform provider-config checks before this decision. It
still participates in existing source locking and durable job telemetry.

- [ ] **Step 6: Preserve explicit generic executor behavior.**

`tests/test_market_data_direct.py` remains `63/63` and byte-identical in node
identity. Explicit bounded market-data operations are not silently disabled;
only the scheduler's unproven coverage-derived planning is retired.

- [ ] **Step 7: Run planner isolation and full backend focused set.**

```bash
pytest -q \
  tests/test_market_coverage_dependencies.py \
  tests/test_market_coverage_calendar.py \
  tests/test_market_coverage_classifier.py \
  tests/test_market_coverage_observations.py \
  tests/test_market_coverage_boundaries.py \
  tests/test_trading_day_coverage.py \
  tests/test_market_data_direct.py \
  tests/test_data_scheduler.py

pytest --collect-only -q > /tmp/coverage-v2-backend-tip.txt
sed -n '/::/p' /tmp/coverage-v2-backend-tip.txt | LC_ALL=C sort | sha256sum
```

Expected: `8 files / 225 passed`, full collection `4744`. Record the final
hash; do not predeclare it before implementation.

- [ ] **Step 8: Re-run direct mutation probes.**

In disposable copies only:

1. route one `unknown_tickers` value to the old worker;
2. route one provider-error ticker to exclusions; and
3. allow one legacy continuation to reach the worker.

Each mutation must make a named scheduler or structural node RED. Restore and
rerun green.

- [ ] **Step 9: Commit and record the backend checkpoint.**

```bash
git add -A src/scheduler_planner.py tests/test_scheduler_planner.py \
  src/api/routes/schedule.py src/service/data_scheduler.py \
  tests/test_data_scheduler.py
git commit -m "refactor: retire unproven coverage planner work"
git rev-parse HEAD
```

Record the 40-character hash in evidence as `COVERAGE_V2_BACKEND_TIP`. The
frontend task may not mask backend ledger drift.

---

## Task 7: Replace The Frontend Contract And Localize V2 Presentation

**Files:**
- Create: `apps/arkscope-web/src/coverageV2Contract.test.ts`
- Modify: `apps/arkscope-web/src/api.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.ts`
- Modify: `apps/arkscope-web/src/marketDataDisplay.test.ts`
- Modify: `apps/arkscope-web/src/settings/DataStorageSection.tsx`
- Modify: `apps/arkscope-web/src/SettingsPostPgExitStorage.test.ts`
- Modify: `apps/arkscope-web/src/SettingsProviderConfig.test.ts`
- Modify: `apps/arkscope-web/src/dataSourceSchedulePolling.test.ts`
- Modify: `apps/arkscope-web/src/dataSourcesPresentation.test.ts`
- Modify: `apps/arkscope-web/src/settings/settingsBackendCopy.test.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/en/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources/zh-Hant/settings.ts`
- Modify: `apps/arkscope-web/src/i18n/resources.test.ts`

**Accounting:** frontend `+11/-2`; full `95/1063 -> 96/1072`; expanded
focused `7/109 -> 8/118`. Resources `+32/-13`, net `+19`: Settings
`694 -> 713`, total `1794 -> 1813`, coverage subtree `25 -> 44` per locale.

- [ ] **Step 1: Add the three compile-time contract tests.**

```text
exports the exact closed Coverage v2 enum catalogs
accepts the V2 DTO and rejects retired field fixtures
keeps every frontend coverage enum consumer exhaustive and exact
```

Use `satisfies`, literal tuples, exhaustive `never`, and `@ts-expect-error` to
prove old fields do not type-check. The test must reject a V1 fixture carrying
`missing_tickers`, `complete_like`, or `max_observed_bar_count`.

- [ ] **Step 2: Replace the two old display nodes with six V2 nodes.**

Remove the two IDs listed in the ledger, then add:

```text
maps every Coverage v2 day status in both locales and reserves positive tone for complete
maps non-trading closure reasons without backend prose
maps every Coverage v2 day reason in both locales
maps calendar and observation health without parsing diagnostics
keeps partial and unknown ticker facts independent
renders unmatched RTH rows as a separate data-quality warning
```

Use typed Settings `t` at the call site. No hardcoded user-facing literals and
no dynamic translation keys.

- [ ] **Step 3: Add two mounted Settings nodes.**

```text
keeps calendar degradation separate from reviewed-day coverage
keeps unmatched rows and provider issues separate from coverage state
```

Fixtures must exercise `partial + unknown`, `indeterminate_tickers`, low
horizon on an otherwise complete reviewed day, observation unavailable,
unmatched rows, and provider issues.

- [ ] **Step 4: Run bounded RED.**

```bash
cd apps/arkscope-web
npx vitest run \
  src/coverageV2Contract.test.ts \
  src/marketDataDisplay.test.ts \
  src/SettingsPostPgExitStorage.test.ts
```

Expected: 11 new nodes RED and the existing V1 nodes still green before their
intentional removal. Import/type errors unrelated to the contract are wrong
REDs.

- [ ] **Step 5: Replace `api.ts` contract exactly.**

Transcribe the closed types from spec Sections 8.1-8.2. Do not use `string` for
enum slots. Remove every retired V1 field in the same edit. Keep provider issue
diagnostics separate from coverage classification.

- [ ] **Step 6: Implement pure display presenters.**

Use exhaustive switches over:

```text
CoverageDayStatus
CoverageDayReason
CalendarHealth and its reason codes
ObservationHealth and its reason code
closure_reason_code
```

Only `complete` receives positive/success semantics.
`indeterminate_tickers` is neutral attention copy, never success. Unknown raw
IDs fail closed to generic localized copy; Developer Mode may show the stable
ID through the existing diagnostic owner, not through a new raw renderer.

- [ ] **Step 7: Replace the coverage subtree with exactly 44 leaves.**

Follow the Exact Resource Ledger. Preserve current zh-Hant copy unless the
ledger explicitly replaces V1 semantics or terminology authority requires the
change. Keep EN/ZH key sets identical, every leaf non-empty, and no source
content in resources.

The inventory test keeps its exact ID and changes only counts:

```text
Settings 694 -> 713
total    1794 -> 1813
```

- [ ] **Step 8: Remove planner metadata from frontend fixtures.**

Delete public `gap_planned` and V1 coverage fields from the three schedule/data
source fixtures. Do not add replacement planner chrome. Existing schedule
behavior nodes evolve in place only where fixture shape changed.

- [ ] **Step 9: Preserve locale-switch purity.**

Strengthen the existing mounted locale-switch node in place to seed:

- expanded coverage row;
- lookback input value;
- focused element and dataset identity marker; and
- an in-flight or resolved V2 response.

After `controller.setLocale`, chrome re-renders in place, expansion/value/focus
and node identity remain, and there is no coverage refetch. The locale PUT is
the only allowed request.

- [ ] **Step 10: Run frontend focused GREEN and count.**

```bash
cd apps/arkscope-web
npx vitest run \
  src/coverageV2Contract.test.ts \
  src/SettingsPostPgExitStorage.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/i18n/resources.test.ts \
  src/marketDataDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts
npx vitest list --json > /tmp/coverage-v2-frontend-tip.json
```

Expected: `8 files / 118 passed`; full collection `96 files / 1072`.

- [ ] **Step 11: Run typecheck, scanner, and build.**

```bash
npm run typecheck
npm run check:i18n-literals
npm run check:i18n-literals
npm run build
```

Expected: typecheck/build exit zero; scanner both times exactly
`36/20/0/20`, scope `src/**`; no manifest/allowlist change.

- [ ] **Step 12: Commit.**

```bash
git add apps/arkscope-web/src
git commit -m "feat: present Coverage v2 session truth"
```

---

## Task 8: Prove Static, Runtime, Visual, And Production Boundaries

**Files:**
- Create/modify evidence only after gates run:
  `docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md`
- Product changes are forbidden unless a gate exposes a reviewed defect and a
  documented deviation is approved first.

- [ ] **Step 1: Run backend canonical A/B from virgin archives.**

Archive `PLAN_REVIEW_CLEARANCE_COMMIT` and implementation tip separately. In
fresh environments, collect both node lists and run the same full suite.

Expected accounting:

```text
base 4713
head 4744
comm +70/-39
```

The 39 removals must be exactly 18 V1 route node IDs, nine planner nodes, ten
planner-consumer scheduler nodes, and the two contradictory scheduler IDs.
`test_route_registered` must be present at both sides with the same ID. Compare
existing environmental failure families by exact node ID: new failures `0`,
disappeared failures `0`. Do not convert baseline noise into an allowlist.

- [ ] **Step 2: Run backend focused and mutation gates.**

```bash
pytest -q \
  tests/test_market_coverage_dependencies.py \
  tests/test_market_coverage_calendar.py \
  tests/test_market_coverage_classifier.py \
  tests/test_market_coverage_observations.py \
  tests/test_market_coverage_boundaries.py \
  tests/test_trading_day_coverage.py \
  tests/test_market_data_direct.py \
  tests/test_data_scheduler.py
```

Expected: `225 passed`. Reprove:

- all seven precedence paths;
- 13:29/13:30 early-close transition;
- off-grid counted and not filled;
- unknown/provider diagnostics absent from planner and exclusions;
- legacy continuation refusal with zero worker calls; and
- `mode=ro`/`query_only` database byte preservation.

- [ ] **Step 3: Run frontend canonical A/B.**

Expected:

```text
base 95 files / 1063
head 96 files / 1072
comm +11/-2
focused head 8 files / 118
resources Settings 713 / total 1813 / coverage 44 per locale
```

Verify the two removed IDs and eleven added IDs exactly. Existing nodes retain
their names. Run typecheck, build, scanner twice, key parity, no-empty-leaf,
and dynamic-key gates.

- [ ] **Step 4: Run structural byte gates.**

Generate a file-by-file SHA-256 comparison from clearance to tip for every
protected family. Expected:

- schemas and migrations byte-identical;
- providers/collectors/prices-runtime/data-source/tool/prompt/agent owners
  byte-identical;
- extensions/Electron/package metadata byte-identical;
- all CSS and formatter owners byte-identical;
- scanner manifests and allowlist byte-identical; and
- only `requirements.txt` changes in dependency metadata.

Run:

```bash
python -m src.smoke.pg_unreachable_e2e
git diff --check PLAN_REVIEW_CLEARANCE_COMMIT..HEAD
```

Expected no-PG result: `"ok": true`, `"pg_attempts": []`.

- [ ] **Step 5: Run isolated API truth fixtures.**

Use an isolated copied/fresh market DB and injected calendar/clock fixtures.
Exercise through HTTP:

1. regular 26-slot complete session with extended-hours rows;
2. early-close 14-slot session at 13:29 and 13:30 ET;
3. uniform truncation;
4. one complete outlier among truncated tickers;
5. complete observed cohort plus unknown ticker;
6. partial plus unknown ticker;
7. in-window off-grid physical row;
8. readable empty DB;
9. missing/unreadable/schema-invalid DB;
10. low fixture horizon with a reviewed complete day;
11. unreviewed date; and
12. provider issue alongside otherwise complete coverage.

Assert V1 fields are absent from raw JSON. Monitor provider/Gateway/PG and DB
write spies: all zero.

- [ ] **Step 6: Run real browser Settings evidence in both locales.**

At `390`, `760`, `960`, and `1440` widths, render the worst credible
composition: long English copy, degraded calendar health, partial+unknown,
unmatched warning, provider issue, and expanded ticker lists together.

Verify:

- no document or element-level clipped text/overflow;
- state colors do not call `indeterminate_tickers` successful;
- source values remain original;
- normal mode has no raw diagnostics;
- Developer Mode has one diagnostic owner;
- no repair control exists;
- locale switch preserves expansion/lookback/focus/node identity; and
- switching makes no coverage data request.

If any CSS is required, stop and use the CSS deviation protocol; do not patch
layout during evidence collection.

- [ ] **Step 7: Run production read-only smoke.**

With the app otherwise idle, record market/profile DB path, size, mtime,
integrity, FK, and relevant row digests before and after. Use only the GET route
and Settings read surface. Do not click any scheduler/manual update/repair
control. Assert:

- no provider/Gateway/PG call;
- no DB byte/mtime change;
- current dated RTH witness is classified from session slots;
- off-grid count, if present, is shown separately; and
- production observations are recorded with date, never copied into tests.

- [ ] **Step 8: Stop every isolated process and prove ports closed.**

Do not leave uvicorn, Vite, browser, Gateway, or test processes running. Record
the port refusal proof in evidence.

---

## Task 9: Assemble Review Evidence And Stop At Review-Ready

**Files:**
- Create: `docs/superpowers/evidence/2026-07-26-coverage-v2-session-truth.md`
- Modify: `docs/design/ARKSCOPE_TERMINOLOGY.md`
- Modify: `docs/design/ENGINEERING_ISSUE_REGISTER.md`
- Modify: `docs/design/PROJECT_PRIORITY_MAP.md`
- Modify: spec and this plan status only.

- [ ] **Step 1: Write evidence from command output, not recollection.**

Include:

- clearance, every task checkpoint, `COVERAGE_V2_BACKEND_TIP`, and final tip;
- A/B node lists, hashes, counts, and exact removal/addition IDs;
- dependency solution and official-fixture/package parity;
- resource/scanner exact values and hashes;
- V1 field absence and scheduler/planner zero-reference proof;
- mutation probe output;
- isolated HTTP and browser matrices;
- byte-gate/no-PG results;
- production read-only before/after facts; and
- every deviation, including rejected proposed scope changes.

- [ ] **Step 2: Update terminology and issue disposition honestly.**

Add only the two reviewed canonical pairs for RTH and the US-listed equity
proxy. Mark the blunt `_THIN_BAR_THRESHOLD` issue resolved by V2 only after the
old owner is gone. Do not close future repair, listing/halt authority, scope
violation detection, or calendar maintenance work.

- [ ] **Step 3: Mark docs review-ready, not live.**

Set spec, plan, priority map, and evidence to implementation-complete / an
independent implementation review pending. Do not mark LIVE, merge, delete the
branch/worktree, or mutate production.

- [ ] **Step 4: Run final review-tip verification.**

```bash
pytest -q \
  tests/test_market_coverage_dependencies.py \
  tests/test_market_coverage_calendar.py \
  tests/test_market_coverage_classifier.py \
  tests/test_market_coverage_observations.py \
  tests/test_market_coverage_boundaries.py \
  tests/test_trading_day_coverage.py \
  tests/test_market_data_direct.py \
  tests/test_data_scheduler.py

cd apps/arkscope-web
npx vitest run \
  src/coverageV2Contract.test.ts \
  src/SettingsPostPgExitStorage.test.ts \
  src/SettingsProviderConfig.test.ts \
  src/dataSourceSchedulePolling.test.ts \
  src/dataSourcesPresentation.test.ts \
  src/i18n/resources.test.ts \
  src/marketDataDisplay.test.ts \
  src/settings/settingsBackendCopy.test.ts
npm run typecheck
npm run check:i18n-literals
npm run check:i18n-literals
npm run build
```

Expected: backend `225` focused, frontend `8/118` focused, full collections
`4744` and `96/1072`, scanner `36/20/0/20`, resources `713/1813`, and all
structural gates green.

- [ ] **Step 5: Commit review-ready evidence.**

```bash
git add docs/
git commit -m "docs: record Coverage v2 implementation evidence"
git status --short
git log --oneline --decorate PLAN_REVIEW_CLEARANCE_COMMIT..HEAD
```

Expected: clean worktree and linear history. Stop for independent
implementation review.

---

## Independent Implementation Reviewer Focus

1. Reproduce backend `+70/-39` and frontend `+11/-2` from virgin archives.
2. Confirm backend final `4744`, focused `225`; frontend final `96/1072`,
   focused `8/118`.
3. Verify every removed node is one of the 37 named legacy nodes, every added
   node matches the ledger, and `test_route_registered` evolves in place.
4. Verify resource comm `+32/-13`, Settings `713`, total `1813`, and coverage
   subtree `44` per locale, with the existing count node ID preserved.
5. Re-solve the exact Python 3.10 dependency set and compare installed
   metadata with requirements.
6. Compare pinned XNYS against every official full/early-close/closure fixture.
7. Prove the seven ordered day-state paths are unique and exhaustive.
8. Mutate 13:29/13:30 to prove the early-close buffer test owns the boundary.
9. Mutate off-grid handling twice to prove counting and non-filling are
   independently protected.
10. Confirm reader filters by session window only and cannot write.
11. Confirm no provider/Gateway/PG/network import or call exists in coverage.
12. Confirm `indeterminate_tickers` uses exact matching and never gains
    complete/success semantics by prefix.
13. Confirm partial+unknown stays partial while unknown facts remain visible.
14. Confirm max-relative DTO fields and status IDs are absent, not hidden.
15. Confirm unknown/provider-error inputs cannot enter planner candidates or
    exclusions through any route.
16. Confirm legacy continuation rejection is durable, safe, worker-free,
    redacted before the first V2 run, bypasses provider readiness, preserves
    historical audit rows, and clears state only after terminal audit succeeds.
17. Confirm explicit generic market-data executor behavior and its 63 tests
    remain intact.
18. Verify calendar-health composition has one owner and fixture review/horizon
    questions remain separate.
19. Verify normal-mode diagnostic boundary and Developer-only raw detail remain
    unchanged.
20. Re-run both locale/width matrices with worst credible composition and
    element-level clipping checks.
21. Verify CSS, formatters, schemas, migrations, extensions, Electron, package
    locks, and protected backend owners are byte-identical.
22. Verify production evidence was read-only and all isolated ports are closed.

## Post-Review Integration Protocol

Only after independent implementation review returns GREEN:

1. record the review resolution in docs and commit it;
2. fast-forward merge only;
3. rerun backend `225`, frontend `8/118`, both full collections, scanner,
   resources, typecheck/build, no-PG, and byte gates on the merged tree;
4. perform one production read-only Settings smoke with no scheduler/repair
   interaction;
5. mark spec/plan/evidence/map LIVE COMPLETE with merge hash;
6. commit docs-only closeout;
7. verify production databases unchanged; and
8. remove the worktree and branch only after `git branch -d` confirms all
   commits are merged.

No push is authorized by this plan.
