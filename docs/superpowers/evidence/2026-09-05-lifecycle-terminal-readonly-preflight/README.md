# Lifecycle Terminal Read-Only Preflight

Status: authorized read-only preflight completed; production cutover, provider
reads, disposition and price repair have NOT been performed.

Observed at: `2026-09-05T09:29:58+00:00` (17:29:58 Asia/Taipei).

This is a separate production observation, not an amendment to the preceding
[offline verification packet](../2026-09-05-lifecycle-terminal-membership-offline/README.md).
That packet's provider-free/production-free verification claims remain scoped
to its own run. No product code was changed by this preflight.

## Authorization And Method

The user's authorization covered production schema, scheduler state, tracking
sources, open-position presence and price gaps, read-only, without credentials
or provider calls. It did not authorize installation, disposition or backfill.

- Opened only `profile_state.db`, `sa_capture.db` and `market_data.db` using
  SQLite URI `mode=ro` and `PRAGMA query_only=ON`.
- Used table/column allowlists and a SQLite authorizer. Selected only the four
  lifecycle automation settings and the specified collection schedule settings,
  not arbitrary profile settings or credential rows.
- Used local universe/SA readers, `TradingDayCoverageService` and the pure
  `preview_price_repair` function. Did not instantiate write-capable stores.
- Runtime audit hooks rejected network connections, child processes, and
  credential/config-file opens. The completed run had zero denied operations,
  zero provider calls and no SQL writes to production.
- Price inspection used ticker/timestamp/interval and typed provider-error
  metadata, not price values. No raw articles, account numbers, quantities,
  credentials or complete private ticker inventory are published here.
- The App was not stopped by this operation. Each database was read in a
  transaction; there is NO atomic snapshot spanning all three databases.
  These findings are not a cutover approval digest. Re-read under the approved
  stopped-writer cutover before binding any write.
- Schema identification compared lifecycle DDL to the exact V3/V4 definitions.
  This is not a full integrity/foreign-key check, backup or migration rehearsal
  against the production files.

The first harness attempt rejected SQLite's first initialization of the
`pragma_table_info` virtual table: its authorizer reports internal
`SQLITE_UPDATE sqlite_master` events even under read-only/query-only access.
A separate fixture reproduced this with `total_changes == 0`; the second
metadata query did not emit those events. The corrected harness primes the
metadata table after enabling query-only and before installing its authorizer,
asserts zero changes, and retains the authorizer for all substantive reads.
The final run succeeded. This was a harness initialization issue, not a product
coverage failure or an authorized production schema write.

## Installation State

| Observation | Result |
| --- | --- |
| Lifecycle schema | V3 |
| Membership/binding/event tables | All three absent |
| Automation enabled | false |
| Automation applies profile transitions | false |
| Automation interval / batch | 5 minutes / 2 |
| IBKR price collection | enabled; interval 720 minutes |
| IBKR news collection | enabled |
| Latest durable IBKR price status | partial, updated 2026-09-05T03:58:43+0000 |
| Existing lifecycle cases | 36, all SEC-origin |
| Existing automation runs | 60 blocked / 6 failed / 10 succeeded |
| Existing identity transitions | 0 |

The latest price job began at `2026-09-05T03:56:36+0000`. No lifecycle or identity
scheduler row was returned by the selected durable-state query; absence is not
evidence that a process is stopped.

The current universe contains **186** tickers. Source counts overlap:
manual lists 148, open positions 10, Current Alpha Picks 45, Former Alpha Picks 56.
Current non-stale SA observations contain **105 lineages**: 46 current and 59
closed. Lineages and unique tickers are different units. Do not bootstrap from
the earlier 106-lineage inventory or reuse an older 187/189-symbol denominator.

## Three Target Cases

Each of `ARCH`, `LTHM` and `TA` has the same relevant shape:

- Present in collection scope, solely through Former Alpha Picks.
- One former lineage, no current lineage.
- No open position and no active manual-list membership.
- Not hidden; no identity link, lifecycle case or identity transition.

This explains why the prior census alone did not stop collection: it was
evidence, not an installed disposition. An IBKR miss still does not establish
delisting. The persisted error for each target is
`security_definition_unavailable`, observed at `2026-09-05T03:58:43+00:00`.
Fresh authoritative evidence and governed transition receipts remain required.

## Price Coverage Findings

Both the calendar and local observation reader returned `ok`. Calendar review
extends to 2027-12-31 with a 15-month forward horizon. The five completed sessions
from **2026-08-31 through 2026-09-04** each have 26 expected RTH slots, 183 complete
tickers, zero partial tickers and three unknown tickers: ARCH/LTHM/TA. There were
zero unmatched RTH rows on those sessions. Weekends are correctly non-trading.

This does not identify a trading-calendar fault on the inspected dates. It also
does not make unavailable historical prices complete.

### Recent Window

The 15-calendar-day lookback spans 2026-08-21 through 2026-09-05, inclusive:

- 35 gap tickers and 223 completely missing ticker-days; no partial ticker-days.
- ARCH/LTHM/TA account for 33 of those missing ticker-days and are blocked from
  price repair because their contracts are unresolved.
- The other **32** tickers account for **190** missing ticker-days. Their first
  local 15-minute bar dates are 2026-08-31 (31 tickers) and 2026-08-27 (one ticker).
- The pure repair preview therefore selects 32 tickers, IBKR only, no fallback.

First local bar date is NOT a listing date or historical tracking-start date.
These reads do not establish that rows were deleted or that the securities
were recently listed. They establish absence before the first local bar.

### Older Window

The 120-calendar-day lookback spans 2026-05-08 through 2026-09-05, inclusive,
with 83 completed trading sessions:

| Gap class | Tickers | Missing whole ticker-days | Partial ticker-days |
| --- | ---: | ---: | ---: |
| Before first local bar | 36 | 2702 | 0 |
| No local history: the three targets | 3 | 249 | 0 |
| Existing but partial observations | 147 | 0 | 438 |

The partial observations are concentrated on three dates:

| Date | Partial tickers | Observed / expected slots |
| --- | ---: | --- |
| 2026-06-05 | 145 | 143 have 6/26; two have 7/26 |
| 2026-06-25 | 146 | All have 5/26 |
| 2026-06-26 | 147 | 146 have 3/26; one has 19/26 |

Those partial sessions are missing 9,329 expected slots. The 36 pre-history
tickers include the recent 32 and four whose first bars fall in July/August.
The full-window preview selects 183 tickers, not 32.

The [Coverage v2 inventory](../../../design/COVERAGE_V2_GROUND_TRUTH_INVENTORY.md#44-known-truncation-witnesses),
observed 2026-07-25, already records the June 25/26 sparse-bar shapes. Today's
universe/counts differ, but those failures demonstrably predate this lifecycle
implementation. Their original cause cannot be established from timestamps
alone; the prices table lacks per-row provider provenance. Do not label every
old gap a new regression or blame a provider without supporting records.

### Repair Boundary

The routine collector defaults to a five-calendar-day lookback
(`src/prices_runtime.py`, `src/market_data_direct.py`). These older gaps are
outside that window and will not self-heal merely by waiting for its next tick.

The explicit repair worker fetches the completed-day range for each approved
ticker; it does NOT issue one request per missing ticker-day. Existing rows are
preserved. For the currently observed 15-day window, 32 tickers imply 32
historical-data requests and 32 contract qualifications in the existing IBKR
chunk loop, excluding Gateway connection/setup traffic. This is a source-derived
estimate, NOT a live request measurement or authorization.

Repairing that recent window will NOT fix June's partial bars or the complete
120-day history. The older window must remain a separate, visible repair scope.
After disposition, derive its exact current ticker/date manifest and request
budget, with stop/resume behavior, before asking to run it. Do not request a
blind full-universe re-download or hide historical dates to obtain a green UI.
Any provider limitation or absent result remains explicitly unresolved after
re-reading persisted bars; successful dispatch is not successful coverage.

## Remaining Gates

- [x] Authorized narrow production read-only preflight.
- [ ] Coordinated integration/cutover: commit/merge authorization, stopped App
  and other writers, freshly bound profile/SA approval, private create-only
  backup, atomic V3-to-V4 migration/bootstrap, integrity and receipt validation.
  Keep both automation switches false. Do not restart V4 code on a V3 database.
- [ ] Fresh three-target evidence: at most 15 Massive + 2 Nasdaq + 2 EODHD
  requests, shared directories, 12.5-second Massive spacing, zero retry/fallback,
  and measured attempts. Read only the required profile credentials for this
  separately authorized provider step, without publishing them.
- [ ] Attended historical disposition after reviewing the three exact previews.
  Missing exhaustive successor history is not automatic permission. Open
  positions, active OTC, contradictory evidence or changed state veto the item.
  Verify source-specific terminal suppression survives local SA reconciliation;
  preserve source history and create no acquisition-to-buyer alias.
- [ ] Separately approved IBKR repair for recent and older gaps, followed by
  persisted coverage checks and honest reporting of any remaining limitations.
- [ ] Production verification, then user hand testing. Push is not included.

## Private Evidence

Full local artifacts are in `/tmp/arkscope-terminal-preflight-efgkav4q/` (directory
mode 0700, files 0600). They are not part of the public repo. `measurements.json`
contains only aggregates and the user-named targets, with hashes binding the
private local files. The harness is `/tmp/arkscope-terminal-readonly-preflight.py`.
The snapshot/preview hashes are dated observations, not approval to execute
against later state. No production credentials were read in this run.
