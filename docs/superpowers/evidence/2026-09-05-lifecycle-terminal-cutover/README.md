# Terminal Cutover And Fresh Evidence Check

Status: **V4 and memberships installed; fresh evidence check incomplete**.
No terminal disposition, price backfill, App restart or push occurred.

## Authorization And Actual Effects

The user authorized committing and fast-forwarding the repair, stopping the App,
private backups and V4/membership installation, and at most 19 HTTP requests:
15 Massive, two EODHD and two Nasdaq. These provider limits are independent;
unused Massive requests cannot be reassigned to another provider.

- The App's supervisor, Electron, Vite and sidecar were stopped. Other projects
  and the browser's independently running SA capture were not terminated.
- The production profile migrated from V3 to V4. The 23 existing lifecycle,
  identity, watchlist and portfolio tables retain their original rows.
- There are 105 accepted local memberships and 105 bindings, each with an
  attended bootstrap receipt. The 59 lineages with closed portions and 46
  current-only lineages coexist with 52 currently observed lineages: six have
  both Current and Former sources.
- All 186 universe tickers and **every source edge** were preserved. No membership
  was removed and no identity transition was approved or applied.
- Both automation switches remain valid and false. Integrity and foreign-key
  checks pass. Repeating installation is a no-op and creates no second backup.
- The consistent V3 backup is private (directory `0700`, file `0600`), with
  independently checked SHA-256
  `ed9ba71373a70e08134042e297e52fd505db0b58eb24e8d2618bc4d9db77467e`.
  Backup location is in the user's private ArkScope maintenance directory, not
  this public packet. No credential row or raw SA capture is published here.

## Two Pre-Write Stops

The first backup rehearsal found a real implementation defect: choosing Closed
over Current for a partially closed pick removed four tickers' Current source
edges, although the ticker count remained 186. No production migration ran.
The correction stores Current independently. Removing Former retains an existing
Current source; after that Current source ceases, refresh/bootstrap/alias cannot
reactivate a removed membership. A terminal transition stops both sources, and
its governed reversal restores the exact previous intent, including earlier
Former removal.

The next rehearsal passed. Before its approval digest was used, the independently
running SA capture updated all 105 observation timestamps. No ticker, pick date,
source flag or profile state changed. The stale preview was rejected before
backup or production write. A new backup rehearsal and immediately checked
approval digest then installed successfully. The guard was not weakened and
capture timestamps were not rewritten to make an old approval pass.

## Fresh Check Attempt 1

The measured HTTP boundary sent **four requests**: two Nasdaq and two EODHD,
each exactly once. All returned HTTP 200 and complete response bodies. The
directory stage returned a parser blocker, so the harness stopped before the
first Massive request. There is no fresh completed case, no persisted provider
check and no terminal-authority conclusion from this attempt. The remaining
15 Massive requests were not used.

The v1 harness preserved request reservations, statuses, byte counts and body
hashes, but did not persist the returned parser code or replayable bodies before
its early stop. That is a harness observability defect. **The original failing
parser failure code and exact response cause cannot be reconstructed from these hashes alone.**
This packet does not assert that EODHD parsing succeeded or that there was only
one incompatibility. The original receipt is retained unchanged.

Independently, a deterministic local defect is proven: the production parser
accepted only the old adapter/fixture footer `mmddyyyy|HHMMSS`, whereas Nasdaq's
published format places `mmddyyyyHH:MM` in field one followed by empty delimited
columns. The official-shaped positive control failed before the fix. The prior
shadow census used a different `_nasdaq_symbols` reader that skipped the footer;
its success therefore did not exercise this production parser contract.
Source: [Nasdaq Symbol Directory Definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs).

The repair accepts the published shape with exact column count, valid time and
the existing freshness boundary. It retains the previous encoding for historical
evidence replay; no sealed fixture or earlier packet is rewritten. Invalid
columns/time, stale/future dates and other directory guards remain fail-closed.

The v2 maintenance harness additionally preserves typed directory failures and
bounded complete response bodies privately, after checking for credential
echoes. Bodies are not included in this public packet. Its real-transports/real-
parsers tests now use official-shaped Nasdaq footers and include terminal,
continuation and unavailable-timeline controls. No v2 live request is claimed.

## Verification

`verification.json` records exact counts, failed mutation owners and report
hashes. The corrected dual-source stage passed the full backend (5847 passed,
12 skipped), full frontend (1395 passed), and 112 cross-module tests. The final
backend is **5856 passed, 12 skipped**, including the nine new footer contract
cases. The three warnings remain the existing Edgar deprecations.

Targeted reverse mutations were confined to a private copy:

| Mutation | Focused Result | Named Owner |
| --- | --- | --- |
| Drop overlapping Current observation | 1 failed / 111 passed | `test_cutover_preserves_dual_source_lineage_from_real_capture_rows` |
| Permit tombstoned Current reactivation | 1 failed / 111 passed | `test_former_tombstone_preserves_existing_current_but_cannot_reactivate_it_later` |
| Terminal does not clear Current | 2 failed / 110 passed | `test_terminal_suppresses_dual_current_source_and_reverse_restores_exact_intent` |
| Remove published-footer admission | 3 failed / 171 passed | published shape and typed stale/future owners |
| Ignore published-footer column count | 2 failed / 172 passed | `test_published_nasdaq_footer_still_requires_exact_shape_and_valid_time` |

Restored copies return 112/112 and 174/174 respectively. The broader footer focus
passes 323 cases. Archived v2 harness tests pass 19 cases with no network or
production access. They cover all three actual scanner/parser paths, measured
cross-case pacing, unique requests, budgets, reserve-before-dispatch, redirects,
401/403/429, unknown dispatch outcome, replay capture, secret rejection and typed
parser-failure visibility.

Two discarded test-harness attempts are not counted as guard evidence: an early
new migration test lacked its temporary portfolio tables, and the first mutation
copy had stale source files. The current-copy baselines passed before mutations.
A v2 test initially expected a bare JSON MIME type while its fixture included a
charset; the recorder now emits a closed normalized content type, not an arbitrary
provider header.

## Remaining Boundary

Additional **two Nasdaq and two EODHD** requests have been requested, not presumed
authorized. They would combine with the still-unused 15-request Massive envelope;
there is no automatic retry and no permission to reuse the first directory budget.
Successful fresh checks must precede any requested attended ARCH/LTHM/TA
application. IBKR historical repair has its own preview and authorization gate.
The user should not be sent back to hand-testing as if those steps were complete.
