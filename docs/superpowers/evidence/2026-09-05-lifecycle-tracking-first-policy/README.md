# Tracking-First Listing Policy And Offline Effects

Date: 2026-09-05. Baseline: `0b66732b`.
Status: offline Tasks 0-2 are complete, with full backend regression, four
independent policy mutations and restored-focus verification. Not a sealed
release packet or a claim of production treatment.

Only synthetic responses, archived public test fixtures and temporary SQLite
stores were used. No production read/write, provider execution, schema migration
installation, App restart, commit, merge or push is part of this work.

## Changed Contract

- Listing authority and continuation are separate typed axes. All six required
  old-listing checks must succeed. Missing, ambiguous or candidate timelines do
  not invalidate independently complete listing evidence and do not prove that
  there is no successor. A candidate is not an alias.
- `ProviderCheckStore`, the actual scanner, worker bundle and write-time guard
  use that distinction. Timeline/successor errors have operation-specific codes;
  unknown or required-source errors still block. Raw codes remain in the receipt.
- The old unscoped `massive_not_found` is attributable only with all required
  checks complete, no timeline, no other continuation error and no other
  unscoped failure. It is not a general HTTP-404 bypass.
- Active/OTC observations, incomplete/stale material, identity conflicts and
  invalid/future dates continue to veto retirement. Identity comparisons cover
  non-null FIGIs and exact CIKs across the source material. Timestamp comparisons
  use UTC before applying the future-date boundary.
- Human acceptance cannot override a listing veto merely because a result
  contains `successor_check_unavailable`. Unknown transition kinds are rejected.
- Pre-2025 delisting and verified same-security continuation remain attended.
  Mutation disabled still permits decisions and proposals. Open positions are
  preserved; no acquisition-to-acquirer alias is created.
- The provider rule is revision `2`; automation policy is
  `trusted-lifecycle-automation-v6`. A real frozen V1 blocked receipt is re-entered
  once under this policy without rewriting its bytes or its prior run. A prior
  applied retirement is not repeated when the policy changes.
- With no active tracking sources, the decision reports the listing finding
  without requesting another mutation. Explicit rechecking of an already-removed
  ticker is not filtered out by the current-universe scan input.

The earlier test that required missing timelines to block the worker has been
deliberately replaced with decision/proposal/preview controls under both mutation
permission states. `test_changed_observation_or_policy_reenters_and_stales_old_result`
now derives a test-only next policy instead of assuming a fixed v6 is always newer.

The schema and migration files are unchanged. The Task 1 V2 snapshot/binary
rollback boundary still applies; do not deploy an old reader after new writes.
The new current-review DTO and compact UI are Task 7, not completed here.
Continuation follow-up currently survives in saved material and decision context;
that is not a claim that the old UI already presents the new axes appropriately.

## RED And Integration Evidence

- Initial four-file RED: `15 failed, 49 passed`.
- Full affected pre-fix RED: `15 failed, 1240 passed`.
- Additional RED controls exposed blocked old-policy re-entry, untracked
  listings requesting new effects, removed targets skipped by explicit scan,
  iterable source loss, timezone conversion and malformed identity handling.
- Six-file implementation focus: `161 passed` before the last boundary tests.
- Initial whole Lifecycle/identity/membership/universe focus: `1267 passed`.
  Two later approval-change controls are not retroactively included in that count.
- Final temporary-store terminal workflow plus price-workflow controls:
  `19 passed`. This includes three known-case-shaped tests using synthetic
  listing data; it is not a replay of current production snapshots.
- Price repair, repair routes and repair workflow together: `14 passed`.
- Complete backend suite on the product worktree: `5978 passed, 12 skipped,
  3 warnings in 509.62s`. Warnings are existing edgartools deprecations. The final
  explicit test-root and clock changes were subsequently checked with the
  `19 passed` workflow set; no product code changed after the full run.

The three-case workflow now starts from the actual offered decision. ARCH's
2025-01-15 event is policy-eligible with mutation permission disabled in the test;
LTHM's 2024-01-05 and TA's 2023-05-16 events first require human acceptance.
Each then uses the real preview/approval/apply service. Duplicate commands return
`already_applied` without adding removal events. Two subsequent real SA backend
refreshes plus the actual membership reconciler cannot resurrect the target.
Scheduled price and both news collectors resolve only the unaffected control.
SA history at application, old price/news rows and unrelated list memberships
are compared before/after; target membership history is archived, not erased.

Existing source-specific Former, Current overlap, alias, bootstrap, atomic
receipt/effect and governed reversal owners remain in the full focus. New
approval-change controls reject changed membership and new observation snapshots.

The price controls distinguish collector day-presence success from complete
session coverage. A one-bar response retains a partial-day gap and invalidates
the old repair preview. A simulated interruption after one ticker's committed
write leaves no false success receipt. Replanning selects only the remaining
ticker; explicit re-execution preserves earlier rows. This does not promise
automatic resume or zero repeated provider cost for responses lost before commit.

## Independent Mutations

Each mutation uses a separate code copy and the entire affected Lifecycle focus,
not just the file containing the named test. The first copy omitted public SEC
fixtures; those setup failures are excluded from the proof. Its initial unmutated
baseline was `1267 passed`. Later full SA-backend controls exposed implicit root
detection in the new test: the product checkout has `.git`, the mutation copy
does not. The fixture now passes its temporary base path explicitly. The expanded
disk baseline is `1269 passed`; M1 below ran after that correction. Price tests
also use an explicit clock.

One disk M2 attempt stopped progressing while its OS wait channel was
`jbd2_log_wait_commit`; it was interrupted and is not a mutation result. Only the
test database base directory was moved to a newly created `/dev/shm` directory.
The independent tmpfs baseline is `1269 passed in 33.15s`; M2-M4 and restoration
use it. The complete product backend run above still used the normal disk path.
`focused-nodes.json` records all 1269 nodes after implementation, not a pre-edit
baseline. No production database or filesystem setting was changed for this.

| Mutation | Result | Named owner |
| --- | --- | --- |
| Restore missing-timeline listing veto | 16 failed / 1253 passed | `test_no_timeline_listing_retirement_reaches_decision_proposal_and_preview`, both no-event permission cases; all three terminal workflow cases |
| Ignore provider error codes | 7 failed / 1262 passed | `test_unattributed_provider_failure_still_blocks_complete_material` (five errors); store/transport controls |
| Remove OTC veto and required OTC check | 4 failed / 1265 passed | `test_otc_continuation_vetoes_terminal_even_when_three_sources_report_delisted`; missing-OTC and human-veto controls |
| Restore reason-only human exception | 1 failed / 1268 passed | `test_old_reason_string_cannot_substitute_for_listing_authority` |

Final restored focus: `1269 passed in 27.50s`. The independent copy's restored
authority file has the same SHA-256 as the product worktree. The immutable V1
fixture still hashes to
`b065d0767c739cd9113d444ea4617d711228f6beb906db909c56fe0ac7b6e7b6`.
`files.sha256.json` identifies the changed/new product and test files at this
checkpoint. `focused-nodes.json` hashes to
`150d740b41120f36424425c59f34693245583bcebbc0276f6fa68ff6aa4b7901`.

## Remaining Operational Gates

1. Obtain fresh read-only scope for relevant profile tracking/position/evidence,
   SA observation and market coverage inputs. Do not inspect credential/token
   fields. Measure rather than reuse earlier universe or case counts.
2. Rehearse exact policy-bound effects in a private, consistent copy. List target
   removals, retained sources/history and any open-position veto. Do not relabel
   old evidence timestamps as fresh or reuse old action approval.
3. Derive price repair requests from the real top-up window and IBKR chunk plan,
   not missing-day counts. Each intraday chunk currently invokes one contract
   qualification and one historical request; incomplete/error results can lower
   the actual count but cannot authorize a retry. Live budget is still unissued.
4. Obtain separate backup/apply and provider permissions. Read back governed
   receipts, SA non-resurrection and actual stored-bar coverage afterwards.
5. Complete whole-case mapping, one-command confirmation, compact UI and bounded
   web investigation. No hand-test-ready or whole-feature completion claim yet.
