# Recent Price Repair

## Scope

The user prioritized recent missing data and deferred older deficiencies.
This slice investigates and prepares August 21-28 repair for the remaining
183-symbol universe. June data are neither deleted nor hidden. Existing
ARCH/LTHM/TA attended receipts and other source memberships remain unchanged.
No provider request, production price write, migration, restart, merge or push
is included in offline implementation or this diagnostic packet.

## Diagnosis

The immutable post-disposition inventory records 32 affected symbols and 190
missing symbol-days. Thirty-one symbols have only the Former Alpha Picks source
and first local bars on August 31; one has manual/Current sources and first bars
on August 27. All five completed sessions August 31-September 4 are complete.
These are local facts, not proof of an IPO date, tracking start or provider
failure. The default worker requests five calendar days, while the screenshot
inspects fifteen. A real-worker regression reproduces that mismatch without a
provider failure; its full-window positive control fills the missing sessions.

The existing private backup records 151-symbol collection scopes through
September 1, 152 on September 2 and expansion to 187 on September 3. The Former
collection change is present in commit `ae137494`. This supports a collection
scope/window explanation, not a demonstrated IBKR outage. `provider_sync_runs`
does not retain request parameters, its start time is the commit-phase start,
and price rows have no insertion timestamp. Do not invent exact historical
dispatches, IPO dates or membership start dates from those records.

The bounded metadata inspector reads only the existing backup and inventory,
not live credentials or provider data. `diagnosis.json` contains aggregates;
private ticker rows and production paths are not part of this public packet.

## Implemented Boundary

- `src/price_repair_execution.py` owns explicit execution outside the read-only
  coverage package. It reuses the IBKR adapter, canonical price writer and real
  calendar/coverage reader. Ordinary five-day collection remains unchanged.
- A sealed plan binds the original coverage clock, targets, exact per-ticker
  windows, RTH slots, actual IBKR request arguments and derived request budget.
  Worker validation occurs before provider configuration is loaded.
- A private per-operation SQLite journal records each dispatch before calling
  IBKR, and seals responses against their request. This artifact is not a
  profile/market migration or a replacement price authority. Received results,
  including qualification, survive a later interrupted price write.
- The same journal never repeats a dispatched request. Unknown outcomes remain
  unknown, while other authorized targets may finish. Known errors and incomplete
  responses are not silently retried. A new operation needs a new explicit
  authorization; a new ID must not be used to pretend to resume the old budget.
- There is at most one Gateway connection attempt per execution, no internal
  reconnect, no provider fallback, and at least one second between new requests
  in addition to the adapter's existing pacing. Clock rollback stops execution.
- Writes insert only approved missing/partial RTH slots, preserve existing bars,
  use the existing market lock and a transaction-bound alias check, and reject a
  removed target. Unrelated memberships, SA capture, profile data and historical
  prices are not rewritten. A missing market database is never created.
- Completion requires real coverage readback at the approved original clock,
  both in the executor and scheduler. A successful provider response is not a
  coverage verdict. Typed failures and measured request counts survive the job
  projection instead of being replaced by a generic success.
- The existing start endpoint now prepares the journal. The new resume endpoint
  uses the same DB/profile write gates and the original plan. This slice does
  not add a resume button or journal browser; that operator workflow remains
  part of the pending UI work.

## Proposed Live Scope

`request-manifest.json` is derived without provider calls from the previously
authorized immutable post-disposition inventory. The full private plan is kept
with that operation's backups; its SHA-256 is
`907a6f80ff8593db7134203d9807b06fee1692d9c2b7e96b84b6a5676c9289e5`.

| Item | Exact bound |
| --- | --- |
| Targets | 32 existing affected symbols, not all 183 universe members |
| Dates | August 21-28 for 31 symbols; August 21-26 for one |
| Missing / partial | 190 / 0 symbol-days |
| Data requests | At most 32 qualification + 32 history = 64 |
| Gateway connection | At most one read-only attempt per execution |
| Price writes | At most 4,940 approved 15-minute RTH slots; insert only |
| Automatic retry / fallback | Neither |

Gateway connection/protocol traffic is separate from the 64 data calls. Existing
or concurrently completed gaps may reduce actual dispatches and inserts. The
32-target real-shaped offline control measures exactly 64 calls and 4,940 inserts,
while preserving unrelated existing rows. These are test measurements, not a
claim that production has been repaired.

Before live execution: obtain this scope's explicit approval, create a consistent
market backup, revalidate the prepared target scope, and execute with the same
journal. Afterwards read back actual filled, missing, partial and unavailable
counts. Normal SA capture continues. Older June/120-day gaps stay deferred.

## Verification

Final gates are 1,765 integrated passes and a complete backend result of 6,021
passes, 12 skips and three existing deprecation warnings. The measured results
and exact named mutant failures are in `verification.json` and
`mutation-results.json`. The 26-file price focus has 428 tests; each of the 16
independent mutations runs that entire focus, fails its named owner, and is
restored. Baseline and restored runs both pass all 428. The wider integration
manifest also covers lifecycle, memberships, receipts and runtime startup.

Two initial on-disk large runs were explicitly interrupted while waiting in the
filesystem journal, not in IBKR. They are incomplete, not passes. Final large
runs use separate tmpfs test-data directories. Product SQLite durability remains
`synchronous=FULL`; tmpfs tests do not prove survival of an OS/power failure.
Earlier on-disk focused/cache tests also passed. The first complete backend run
found one obsolete route-count assertion; it was updated from 198 to 199 with
the resume route explicitly named, and the full suite was rerun.

Frontend source is unchanged; this packet contains no new browser test claim.
The previous production-disposition packet remains sealed and is not rewritten
to match this later source revision.

## Still Open

- Actual IBKR repair authorization, dispatch, production insert and readback.
- Operator-facing resume workflow and remaining lifecycle case/UI/web redesign.
- Separate merge/restart approval; push remains the user's action.

No production price has been inserted by this slice. Do not call the recent
gaps, the entire feature, or the next hand-test batch complete from offline gates.
