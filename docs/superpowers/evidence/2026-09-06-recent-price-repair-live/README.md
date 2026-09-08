# Recent Price Repair: Authorized Live Result

## Outcome

The separately authorized repair finished on September 6 at 09:03 Asia/Taipei.
All 32 approved targets succeeded. Exactly 32 qualification and 32 history
calls were measured, with one read-only Gateway connection and one socket
connection. The journal contains 64 reservations and 64 received responses;
there are no unknown outcomes, retries or provider fallbacks.

Exactly 4,940 approved 15-minute RTH rows were inserted, filling 190 missing
symbol-days. All eleven trading days from August 21 through September 4 now
have all 183 current symbols complete: zero missing, partial or unresolved.
Weekends remain non-trading days, not fabricated complete sessions.

`master-readback.json` is a separate provider-free process using the unchanged
`master` source tree at `0b66732b`, not just the execution result. It confirms
the same coverage at the original approved clock. The readback command rejects
other database paths, credential-table reads, writes, subprocesses and network.
No App restart was needed to make inserted prices readable by master.

`result.json` is a closed aggregate projection of the private operation result.
No old target row changed and no new target row outside the approved slots was
observed. The guarded writer independently measured the same 4,940 inserts.
The universe stayed at 183 and target source memberships were unchanged.
This command made no profile or SA writes and did not freeze other writers.

## Authority And Artifacts

The user's explicit approval to execute and investigate causes follows this bound:
32 qualification + 32 history requests, one read-only Gateway attempt, a
consistent market backup before dispatch, approved-slot-only insertion and
readback. It also authorizes bounded diagnosis of recent price failures.
It does not authorize older-data cleanup, unrelated source changes, automatic
retry, provider fallback, migration, App restart, merge or push.

Approved plan SHA-256:
`907a6f80ff8593db7134203d9807b06fee1692d9c2b7e96b84b6a5676c9289e5`.
The original scope is in the unchanged sibling packet
`../2026-09-06-recent-price-repair/request-manifest.json`.

Before the only connection, the command created a consistent 3,743,113,216-byte
SQLite backup including committed WAL rows. Its quick check passed, and its
post-execution SHA-256 still equals the recorded preflight digest. Raw request
results, inserted keys, the private plan and full database backup stay outside
this public packet. Backup/journal directories are mode 0700 and their inspected
data files are mode 0600. `private-artifacts.json` records content hashes without
production paths, the target list, contract IDs or raw provider responses.

Only the configured IBKR host/port/client-ID fields were read from the profile.
No `.env`, API key or token was read or injected. The Gateway endpoint was bound
to that exact profile configuration and rechecked after backup. An initial
loopback-only assumption stopped during preflight, before backup/connection;
a RED test exposed it, and the command now admits the explicitly configured
numeric endpoint rather than assuming a local Gateway. This was a maintenance
assumption, not a discovered price-provider failure.

The admitted `run_repair.py` hash is
`58818663c22bd8063c452fb753858cff0c164b7aa0f3f53a6f0ecc7e235e43d5`.
It is unchanged after the independently executed mutation campaign and live run.
The live process ended during a context interruption; its terminal console exit
code is not retained here. Durable result/journal accounting and independent
main-tree readback, not a guessed exit code, establish completion.

## Cause Investigation

`job-history.json` contains only SQL-projected price-job counters and typed
error metadata for August 21-September 6. Of 26 rows, twenty succeeded and six
were marked failed. No raw result blob, raw error string or credential is
exported. A missing counter remains missing, not an invented zero.

| Observed group | What is established | What is not established |
| --- | --- | --- |
| One Gateway failure | August 31 07:21 Taipei: `ibkr_gateway_unavailable`, 16 seconds, no scanned symbols | The retained result cannot distinguish a stopped Gateway, login/session state or a connection-path problem |
| Two generic failures | September 3 23:28 and September 4 08:08 Taipei: `ValueError`, target count 187, a zeroed failure envelope | Zeroed envelope counters do not prove no bars were written; original traceback/request arguments are absent |
| Three partial collections | All 186 scanned; 183 succeeded; only ARCH/LTHM/TA failed. One run inserted 4,758 rows | Whole-job `failed` must not be read as 186 symbols all failing |
| Recent historical gaps | 31 Former-only targets begin locally on August 31, one manual/Current target on August 27; source scope expanded from 151/152 to 187 | First local bars are neither IPO nor membership-start evidence |

The ordinary collector's five-calendar-day default predates the Former-source
change in `ae137494`. It was not newly shortened. The existing real-worker
regression proves that expanding the collection universe and doing only a
five-day top-up can leave a fifteen-day retrospective window incomplete, even
when every requested provider call succeeds. Scope/first-bar observations are
consistent with that explanation. Historical dispatch parameters and insertion
times were not retained, so an exact reconstruction is not possible. Today's
successful older-bar responses prove availability today, not past uptime.

The new owner
`test_invalid_footnote_ticker_can_mask_completed_writes_in_old_worker_summary`
reproduces another specific mechanism: including `SMCI*` in an otherwise
completed partial worker result makes ticker validation raise `ValueError`;
the outer failure projection then reports zero scanned/inserted. Its positive
control with only ARCH/LTHM/TA retains the 183 successes and 4,758 inserts.
This fits the two generic failures and the user's screenshot, but it is an
inference, not proof that those historical exceptions came from that line.
Ticker validation was not weakened and the already completed footnote-ingress
cleanup was not reversed.

The three inactive symbols were retired in the previous authorized operation.
This price operation neither repeats those dispositions nor changes any alias.
Historical failed jobs and source telemetry were not rewritten into successes.
A later regular collection may update current job health; it must do so through
the real scheduler, not by fabricating a successful job for this maintenance run.

## Verification

- Fifteen maintenance tests cover the exact plan, SQL/write scope, backup/WAL,
  environment/network boundary, dispatch accounting and before-connect guards.
- Seven independent mutations each run the entire 443-test price focus and fail
  named owners. Baseline and restored runs both pass 443. Their exact failures
  and restored source hashes are in `mutation-results.json`.
- Read-only diagnostics have four tests, including the historical-summary
  reproduction and credential/write/network refusal controls.
- Final combined verification: 447 passed over 29 files. This run occurs after
  live execution and independent master readback.
- The earlier unchanged product source had 1,765 integrated passes and a full
  backend result of 6,021 passed / 12 skipped / three existing warnings. All 100
  prior manifest files still matched before this packet's documentation update.
  The full backend was not rerun in this maintenance-only turn.

`verification.json` binds actual test counts/XML digests and distinguishes the
initial 13-pass file misleadingly named `*-red.xml` from the actual one-failure
RED run. `source-manifest.json` seals the current scripts, product dependencies,
tests and updated plans. Earlier evidence packets were not modified or resealed.

## Remaining Work

The authorized recent data repair is complete. June/older 120-day deficiencies
stay deferred and visible; no older bars were deleted. The normal five-day
collector is unchanged, so new universe members do not automatically receive
a larger historical bootstrap. Such traffic must remain explicit and budgeted.

Operator-facing repair resume/status, the remaining lifecycle case/UI/web
redesign and the separate integration/merge decision remain open. This result
does not declare the entire feature ready for the user's final hand-test batch.
No new production schema, frontend source, App restart, commit, merge or push is
part of this maintenance turn.
