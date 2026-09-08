# Target-Scoped Attended Disposition

## Authority And Correction

The user authorized consistent backup, private rehearsal and only ARCH/LTHM/TA
attended retirement. After the v1 preflight stopped on capture timestamps, the
user explicitly rejected making unrelated SA crawling a maintenance dependency.
This packet amends that operational contract. It does not replace or re-seal the
v1 stop packet, silently accept a changed target, or authorize provider calls.

Only each target's Former membership and old-symbol suppression may change,
through the existing assessment/preview/attended transition/receipt services.
No acquirer alias, holdings, manual/Current memberships, history, credential,
price data, global SA reconciliation or unrelated case is authorized to change.
Background capture, ordinary reconciliation and unrelated profile/price writers
remain independent. Global SA synchronization may truthfully remain pending.

## Mechanism

- Preserve the six required listing observations, exact evidence/effect hashes,
  known listing-end dates, freshness and no-open-position gates.
- Bind the target's profile dependencies, membership/lineage anchors, connected
  identity relationships and observed SA material. For an existing binding,
  compare the actual observation using its already-recorded timestamp; this
  admits time-only refresh without rewriting the binding or ignoring changes to
  the pick's contents. Missing, new-unbound or current target observations stop.
- Pin three WAL read snapshots while briefly reserving writers. Release all
  writer reservations before SQLite backup copying and private rehearsal.
  Unsupported journal modes stop; the command never reconfigures a live DB.
- Reuse installed transaction/schema validation. Within each profile writer
  transaction, compare protected rows before committing this command's changes.
  This is not a preflight/global-state veto: an unrelated actor's prior commit is
  part of the baseline, while another actor cannot commit during that transaction.
  Non-owned changes roll back. SQL authorization separately excludes credentials,
  history, bindings, schema changes, deletes and unsupported write columns.
- Reserve SA only during each actual approve/apply validation and commit; record
  those hold durations. File publication occurs after releasing the reservation.
  Artifacts remain private/create-only, and approved preview, backup/WAL, paths
  and execution code remain bound to the rehearsed plan.
- Full-source reconciliation runs only on a separate disposable rehearsal copy.
  It must not resurrect the three removed memberships. Production never performs
  that global write merely to make synchronization display current.
- An interrupted attempt retains real partial receipts and its started marker.
  It cannot be blindly rerun; readback distinguishes approved from applied.

## Verification

The original v1 command fails five new concurrent-capture/scope owners while six
target-change controls pass. The replacement's initial local suite passes 38
maintenance tests plus one cross-date price control. The full affected focus
passes 1543 tests; its independent-copy/tmpfs control also passes 1543.
Six independent mutations fail their named owners (1/3/1/1/1/1 failures), and the
restored affected focus passes all 1543 tests. The mutated copy was restored
byte-for-byte. A separate clean-environment process smoke also prepares and applies
all three temporary cases without provider calls. `verification.json` records
offline evidence only; actual production results are separate below.

The initial RED file was called `test_disposition.py`; it is now named
`test_target_disposition.py` so pytest can collect it together with the immutable
v1 test file. No old owner was deleted to obtain the new behavior.

## Actual Result

At 2026-09-06 01:03 Asia/Taipei, all three authorized attended transitions are
applied. Each suppresses its one Former membership and old symbol; no alias,
manual/Current source change or portfolio change was made. Actual universe is
183, and its source-edge digest equals the original inventory's other-183 digest.
All three original provider-check digests are unchanged. SA capture and bindings
were not reconciled by this command; synchronization remains honestly pending.

Consistent three-DB backups are private (`0700` directories, `0600` files).
Private rehearsal survives a later full SA reconciliation. The current master
successfully reads both the rehearsal and actual production receipts, including
applied projections and present reverse-readiness. Reversal remains state-bound,
not an unlimited guarantee. The six actual SA approve/apply reservations lasted
935.827-952.152 ms each; copying and rehearsal did not hold source writer locks.
See `production-result.json` for phase-specific readbacks and measured durations.

The production inventory ran again at 01:03:42-01:03:58 Asia/Taipei, against the
actual post-disposition universe, not a hypothetical filtered universe:

| Lookback | Missing ticker-days | Partial ticker-days | Current-worker simulated data requests |
| --- | ---: | ---: | ---: |
| 5 days | 0 | 0 | 0 |
| 15 days | 190 | 0 | 64 (32 qualification + 32 history) |
| 120 days | 2702 | 438 | 732 (366 + 366) |

These are alternative current-worker budgets, not authorization or an optimized
resumable repair plan. Gateway connection traffic is excluded. There were zero
actual provider requests or price writes. June 5/25/26 still contain the same
145/146/147 partial-symbol groups; `price-gap-shapes.json` preserves the fresh
aggregate. No historical root cause is inferred solely from those dates/counts.

## Multi-Day Price Scope

`tests/test_price_coverage_multiday_regression.py` proves that a complete latest
five-day window cannot conceal older missing dates or June 5/25/26-style partial
sessions in a 120-day report/repair preview. These synthetic sessions reproduce
the observed shape, not private price values or an asserted historical cause.
The existing worker integration tests retain partial-provider-result and
interrupted-write controls. Collector success is day presence, not proof of all
regular-session slots. Fetched-but-uncommitted recovery, live pacing/metering,
authorized actual repair and post-repair coverage remain separate work.

No provider backfill, migration, App restart, merge or push occurred. Multi-day
price repair and the remaining case/UI/web workflow are not complete; this packet
does not declare the full feature ready for hand testing.
