# Tracking-First Authorized Read-Only Inventory

## Authority And Scope

The user's authorization in this turn covers a read-only inventory of tracking
sources, ARCH/LTHM/TA evidence and open-position vetoes, SA synchronization, and
price gaps. It does not authorize a backup, production write, provider request,
migration, restart, commit, merge or push. No credential or token fields were
selected. The worktree is based on `0b66732b`; `source-manifest.json` binds the
actual reader/classifier/worker files, including uncommitted policy work.

The inventory ran from `2026-09-05T15:33:44Z` to `15:34:01Z`. The narrowly scoped
SA follow-up ran at `15:36:16Z`. Both completed with zero provider requests and
zero production writes. This is new observation evidence, not a rewrite of the
earlier census, stored provider decisions, or private backup rehearsal.

`scripts/inventory.py` opens only the authorized profile, market and SA SQLite
databases through exact `mode=ro` URIs and `query_only`. Its authorizer restricts
both tables and columns and rejects writes, attachment and out-of-scope reads.
It does not select position quantities, account balances, credentials or tokens.
The production runner also denies network calls, child processes, ambient auth
files and raw database file reads, and runs with a clean environment. Held
connections' `data_version` and database file identities were unchanged across
each read interval. A detected change invalidates the result before publication;
this is not a multi-database backup or an application-time state lock.

Full ticker/gap/effect inputs remain in private `0700`/`0600` temporary artifacts.
The repository contains closed aggregate projections and the three reviewed
target symbols, not full tracking lists, membership IDs, raw URLs or source
payloads. The public files identify the private summaries by digest. Losing a
private artifact requires a fresh authorized inventory, not reconstruction of
approval from its public summary.

## Three-Case Findings

| Target | Old listing end | Required evidence rows | Current sources | Open position | Memberships to suppress |
| --- | --- | --- | --- | --- | --- |
| ARCH | 2025-01-15 | 6 | Former Alpha Picks only | no | 1 |
| LTHM | 2024-01-05 | 6 | Former Alpha Picks only | no | 1 |
| TA | 2023-05-16 | 6 | Former Alpha Picks only | no | 1 |

Each target has complete Massive/EODHD/Nasdaq listing material. The amended
classifier returns `listing_state=inactive` without listing blockers, separately
from `continuation_state=unavailable` / `successor_check_unavailable`. The stored
historical state remains `unresolved`; its `massive_not_found` observation is
retained, not erased or reinterpreted as proof that no successor exists.

At inventory time, all three fresh checks can support preparation of a new
attended action. `ready_for_new_attended_preview` is not application authority:
freshness, membership state, open positions and all actual write-time guards must
still be revalidated. Evidence timestamps are never changed to make it fresh.

No target is already hidden, and no target transition exists. The exact proposed
scope has zero manual-list archives, zero legacy-seed archives, zero Current
source removals, and one Former membership suppression per target. No successor
alias is proposed. After separately authorized application, the expected active
universe is 183 rather than 186, with every other source edge preserved. This
inventory only computed that hypothetical projection; it did not apply it or
create assessments/approvals/receipts. Historical SA/price/news data must remain.

## SA Synchronization

The initial projection reports synchronization `pending`. The follow-up compared
105 current observations with 105 stored bindings using the real canonical
observation digest. All 105 differences are timestamp-only; there are zero
unbound lineages, changed anchors/content, or bindings missing a current
observation. ARCH/LTHM/TA each have the same timestamp-only result.

The follow-up observation digest equals the first inventory's digest. No
reconciliation was performed and `pending` was not cleared. A private rehearsal
must reconcile and bind the resulting current inputs before an action preview;
timestamp-only does not justify disabling the stale-preview guard. A permanent
test distinguishes unchanged, timestamp-only, content-changed, anchor-changed and
unbound cases; weakening that distinction fails its named owner.

## Coverage And Unexecuted Budget

As of 2026-09-05, the last completed session is 2026-09-04. Calendar and stored
observation health are `ok`. These are current-universe retrospective windows,
not reconstructed historical memberships or listing dates.

| Window | Current 186: missing / partial ticker-days | Hypothetical 183: missing / partial | Repair tickers | Qualification + history | Data-call ceiling |
| --- | --- | --- | --- | --- | --- |
| 5 days | 15 / 0 | 0 / 0 | 0 | 0 + 0 | 0 |
| 15 days | 223 / 0 | 190 / 0 | 32 | 32 + 32 | 64 |
| 120 days | 2951 / 438 | 2702 / 438 | 183 | 366 + 366 | 732 |

ARCH/LTHM/TA are the three currently blocked contracts. Removing them does not
manufacture the remaining historical bars. The 15-day and 120-day envelopes are
alternatives, not additive grants: the latter includes the former. The actual
fetch spans are August 21-September 4 and May 8-September 4 respectively.

The simulation drives `_fetch_rows_for_gaps` and the actual IBKR historical
chunker against a non-network fake bridge, counting qualification and historical
calls separately. The current 60-day offset produces up to 61 inclusive calendar
days per chunk; each 120-day ticker therefore needs two chunks. The existing
worker fetches its complete window, not just dates shown as missing. Counting
only historical requests would understate this budget by half. Zero calls were
actually sent. Gateway connection/handshake/heartbeat traffic is not included in
the data-call count; no quote, retry or alternate-provider call is proposed.

These ceilings are derived budgets, not an admitted live execution harness.
Before live authorization, add enforceable dispatch accounting, bounded pacing,
durable per-item progress and interruption recovery. The existing worker buffers
fetches before its write phase, so the existing write-interruption tests do not
prove recovery of fetched-but-uncommitted data. Do not silently repeat spending
after an unknown dispatch outcome. Its current `0.5s` chunk delay is recorded,
not endorsed as a sufficient long-run pacing policy. Empty/failed responses may
use fewer calls and leave visible gaps; only stored-bar readback proves repair.

## What The Gap Shapes Establish

The 120-day missing history belongs to 36 tickers before their first local bar:
31 start on August 31, one on August 27, one on August 12, one on July 29, and two
on July 14. These are local storage boundaries, not IPO dates or proof that older
history is unavailable. The 15-day gap involves the first two groups (32 tickers).

The 438 partial ticker-days are concentrated in three regular sessions:

| Date | Partial tickers | Stored slots per ticker | Expected slots |
| --- | --- | --- | --- |
| June 5 | 145 | 143 have 6; 2 have 7 | 26 |
| June 25 | 146 | all have 5 | 26 |
| June 26 | 147 | 146 have 3; 1 has 19 | 26 |

All three have zero unmatched RTH rows. This is sparse stored-session data, not
a weekend/holiday accidentally counted as a regular session. The 2702/438 totals
also match the earlier same-day private rehearsal. Neither fact proves why the
rows are missing, identifies their original provider, or rules out a later
deletion. No unsupported historical root-cause claim is made.

## Verification

Before production reading, the new harness passed 32 tests. Adding full-read
concurrency and SA-content distinction controls brings it to 34. The complete
affected focus passes 216 tests; the independent mutation copy's final restored
result is `216 passed in 10.50s`, with all three script hashes equal to canonical.

| Independent mutation | Result across full 216-test focus |
| --- | --- |
| Allow out-of-scope SQL reads | 2 failed / 214 passed |
| Ignore a concurrent database change | 2 failed / 214 passed |
| Omit qualification calls from the total | 8 failed / 208 passed |
| Call changed SA content timestamp-only | 1 failed / 215 passed |

`verification.json` names the failing owners and full focus. Setup failures
(missing new module, an initially shallow mutation-copy path, a calendar-boundary
test expectation, and SQLite metadata virtual-table initialization) were fixed
offline and are not counted as product-defect RED evidence. The readonly
metadata initialization did not grant DDL/write authority. Mutation copies never
touched production or canonical scripts. The earlier product backend result
`5978 passed / 12 skipped / 3 warnings` belongs to the preceding offline policy
slice; the entire backend was not rerun for this maintenance-only follow-up.

## Remaining Boundary

Next request: a consistent private backup and rehearsal, followed only on exact
matching inputs by the three explicitly attended dispositions. Stop if evidence,
positions or effects have changed; do not refresh evidence or enlarge effects
under this inventory grant. Reconcile SA inputs through the governed path and
verify target-only receipts/source changes plus non-resurrection. Writers must
be quiescent and the executing code compatible with the versioned snapshot
reader; the preceding V2 rollback/backup boundary remains in force.

Price metering/resumption must be ready before separately requesting provider
execution. No price repair, whole-case population census, new confirmation UI or
web investigation was completed here. The feature is not yet ready for the
requested end-to-end hand test. No migration, restart, merge or push occurred.
