# Fresh Listing Checks And Attended Rehearsal

Status: **three fresh checks persisted; private attended rehearsal passed;
production dispositions and price repair still pending**. The App and both
automation switches remain off. No App restart, push or IBKR request occurred.
The parser repair is committed as `a6475044`; it has not been merged to master.

## Authorization And Measured Requests

The user added two Nasdaq and two EODHD requests to the preceding authorization.
The unused original Massive ceiling remained 15, restricted to ARCH/LTHM/TA,
their response-bound FIGI timelines and at most one observed successor each.
Provider budgets are independent and cannot be reassigned.

| Fresh-Check Stage | Nasdaq | EODHD | Massive | Outcome |
| --- | --- | --- | --- | --- |
| Prior attempt 1, separate unchanged packet | 2 | 2 | 0 | Directory parsing stopped the run |
| Authorized attempt 2 | 2 | 2 | 0 | Four HTTP 200 bodies preserved privately; Nasdaq parser rejected |
| Offline replay plus unused Massive remainder | 0 | 0 | 12 | Nine HTTP 200 listing replies, three HTTP 404 timeline replies |

This authorization consumed **16 requests**, or **20 across the two fresh-check
authorizations**, against a cumulative ceiling of 23. Three Massive slots were
unused. Every dispatch has one durable reservation and one outcome; each has
`attempts=1`. No automatic retry, redirect, fallback, or 429 occurred. The minimum
measured spacing between Massive dispatches was **12.501830 seconds**.

`request-observations.json` contains only closed metadata and hashes. Complete
bounded bodies are private, mode `0600` in a `0700` maintenance directory; they
are not included in this public packet. Profile credentials were neither sourced
from the environment nor copied into provider locators, logs or public evidence.

## What The Actual Directory Bodies Proved

The previous fix correctly parses the 5,592-row Nasdaq Listed file. The 7,596-row
Other Listed file exposed three additional assumptions:

- Its footer has **seven fields**, while its data header has eight. The published
  Other Listed example has this shape too. Only the two reviewed Other Listed
  footer shapes are accepted; Nasdaq Listed still requires eight. Nonempty footer
  tails, malformed times, stale files and future dates remain rejected.
- 384 ACT identifiers contain `$`, the documented preferred-security suffix.
  Those identifiers are retained exactly in the private directory index. They
  are not stripped into common-stock symbols, mapped to another notation, or
  admitted as new profile/Massive ticker syntax.
- One row uses an unsupported exchange code but explicitly has `Test Issue=Y`.
  Test rows cannot assert a live listing. Such rows must still have a valid
  single-letter exchange shape; unknown exchanges on non-test rows still reject
  the snapshot. No new live exchange mapping was invented.

Primary contracts: [Nasdaq Symbol Directory Definitions](https://www.nasdaqtrader.com/trader.aspx?id=symboldirdefs)
and [Nasdaq symbol conventions](https://www.nasdaqtrader.com/trader.aspx?id=CQSsymbolconvention).
The row counts and shape observations above come from the privately retained
authorized responses, not from additional directory requests.

After the RED-first correction, those **same bytes and hashes** parse completely.
ARCH/LTHM/TA are absent from both current directories, while AAPL and SMCI are
active positive controls. The EODHD pair independently reports all three targets
delisted. A new replay transport has no network session: it binds 14 saved files,
checks identities/status/completeness/digests/freshness, and retains the original
directory observation time. An exclusive create-only claim prevents spending the
remaining Massive budget twice, including by selecting another destination.

The original attempt-1 packet is immutable. All four later bodies match its
recorded byte counts and SHA-256 digests, so those inputs are now recovered.
Replaying them at the original observation time with the original parser from
`f1f2e72e` reproduces `listing_directory_schema_mismatch` in `_file_creation`.
`attempt-one-recovery.json` records the input and code bindings. This is a new
offline reconstruction, not a claim that the original harness recorded that
failure code or retained its bodies. No additional provider call was made.

## Three-Case Result

| Ticker | Source Listing End Date | Fresh Listing Checks | Same-Security Timeline | Product State |
| --- | --- | --- | --- | --- |
| ARCH | 2025-01-15 | Massive inactive; no active stocks/OTC match; EODHD delisted; Nasdaq absent | HTTP 404 | Unresolved; attended review available |
| LTHM | 2024-01-05 | Same complete listing checks | HTTP 404 | Unresolved; attended review available |
| TA | 2023-05-16 | Same complete listing checks | HTTP 404 | Unresolved; attended review available |

These are end dates for the queried ticker's listing, not a claim that an issuer
ceased to exist or that a successor never traded. A missing timeline is **not**
proof of no successor. Each persisted check has six evidence records, the typed
provider code `massive_not_found`, and the sole missing authority condition
`successor_check_unavailable`. None authorizes an automatic terminal transition.
No acquisition-to-buyer alias is created.

The production profile contains exactly three provider checks and zero identity
transitions. All 186 tickers and every source edge are unchanged, as are the 26
other domain tables. The 105 memberships, bindings and bootstrap events remain;
zero memberships are removed. Integrity is `ok` and foreign-key violations are
zero. `fresh-check-summary.json` and `production-state.json` record these checks.

## Private Rehearsal, Not Production Approval

A read-only SQLite backup of the installed profile was used to exercise the real
assessment, acceptance, proposal, transition preview, approval and application
services. All simulated human decisions are explicitly marked rehearsal-only.
Production profile/market/SA connections were restricted to read-only URIs; all
network connections and child processes were denied.

In the copy, all three governed terminal transitions applied, changing the exact
universe from 186 to 183 with every other source edge preserved. Reconciliation
against the current SA capture did not restore any target. No alias was created,
and all three reverse-readiness checks remained true after reconciliation. The
production profile was checked again and remained unchanged. Private previews
and receipts contain internal IDs and therefore are not published here.

The first rehearsal launch stopped before even creating its backup: the audit
hook treated SQLite's byte-encoded pathname as a string representation. Four
positive controls reproduced this harness error. The corrected hook decodes the
native path and passes 22 read/write/network boundary tests; it does not widen
production write permissions. The successful rehearsal is a separate artifact.

## Price Repair Is Still Unexecuted

Read-only coverage of the hypothetical post-disposition 183-ticker universe:

| Lookback | Tickers Requiring Repair | Missing Ticker-Days | Partial Ticker-Days |
| --- | --- | --- | --- |
| 5 days | 0 | 0 | 0 |
| 15 days | 32 | 190 | 0 |
| 120 days | 183 | 2,702 | 438 |

Calendar and observation health are both `ok`. The 15-day gaps precede the first
locally stored bar for 32 tickers. The 120-day view contains 36 such histories and
147 tickers with partial observations. These gaps were not turned into complete
days and no prices were deleted, overwritten or fetched. Exact digest-bound
repair previews are private; the public aggregate is
`price-repair-readonly-summary.json`. A fresh production preview must still be
validated after actual disposition and before separately authorized IBKR work.

## Verification And Remaining Gate

- Full backend: **5876 passed, 12 skipped**, three existing Edgar deprecation
  warnings. The increase from 5856 is the 20 added parser cases.
- Eight-file listing/provider/terminal focus: **348 passed**.
- Prior bounded harness: **19 passed**; new remainder harness: **23 passed**;
  private-rehearsal read/write boundary: **22 passed**. These maintenance tests
  are separate from the full backend count.
- Final parser plus all three maintenance harnesses: **163 passed** after the
  evidence review, without any provider call.
- Five isolated reverse mutations fail named owners: seven-field footer (7),
  preferred-ID stripping (3), test-exchange handling (7), replay-body digest (1),
  and reuse of the remainder authorization (4). Restoring the tested source
  returns **141 passed**. Production code and credentials were never mutated.
- No frontend code changed. The preceding cutover's 1395 frontend results are
  historical evidence, not a claim that this turn reran them.

Source hashes identify the content actually used; the parser commit was created
after the live check, with identical file content. `verification.json` records
report hashes and named failures. The prior packet and user-owned untracked files
remain untouched. Fast-forward merge, actual attended ARCH/LTHM/TA disposition,
IBKR price repair, App restart and push remain separate authorization boundaries.
Do not ask the user to hand-test as if those operations have already completed.
