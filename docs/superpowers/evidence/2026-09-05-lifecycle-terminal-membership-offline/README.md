# Terminal Tracking And Price Coverage: Offline Verification

Status: implementation and offline verification, **not a production cutover**.
Base: `master@9d8cc860`; worktree: `codex/lifecycle-terminal-membership`.
Changes remain uncommitted. No merge, push, production DB read/write, provider
request, migration, or production App restart was performed for this slice.
The pre-existing user-owned untracked evidence and delegation document in the
main worktree were left intact.

## Implemented Contract

1. Provider-first cases do not depend on a SEC sentence being extracted. A
   terminal decision requires explicit inactive evidence, current stock and OTC
   checks, EODHD confirmation, complete Nasdaq directories and a matching security
   timeline. Any active listing, incomplete observation, stale proof, changed
   preview or open position prevents automatic application. Renames remain
   attended; an acquisition never creates an alias to the buyer.
2. Former tracking intent is stored separately from SA capture history. Removal
   belongs to a local membership, precedes alias resolution, and survives later
   observations, bootstrap and verified renames. Manual-list and position sources
   remain independent. Ordinary Restore cannot undo a terminal transition; the
   governed transition reversal retains its existing state checks and receipts.
3. New closed lineages without a recognized membership are candidates. A new
   current pick related to an existing security at the same pick date is also a
   candidate; a genuinely independent later recommendation is not blacklisted.
   Capture gaps are observable, not silently accepted. Accepted membership and
   provider snapshot receipts are append-only.
4. SEC observations remain accessible for investigation/audit, but cannot supply
   mutation authority after the provider/membership cutover. Missing listing
   checks appear in the primary case summary through a closed DTO shared with
   research. A missing ticker history is not labelled an automation crash.
5. Coverage retains the current-universe retrospective denominator. It separates
   absent/late local history, partial bars and contract-definition failures.
   The first stored bar is not claimed to be the listing or tracking start date.
6. A repair preview is read-only. Confirmation binds exact tickers, calendar
   window, interval and gap digest. The repair is IBKR-only with no provider
   fallback; scope is checked again after the Gateway lock. Stored bars are read
   again after collection. An accepted job or collector return code does not
   establish complete coverage, and another job cannot satisfy its receipt ID.

## Historical Cases Are Not An Automatic Positive Control

The archived ARCH/LTHM/TA census has ticker-event 404 results. Those are **not**
proof that a same-security successor does not exist. The offline historical
workflow uses their archived identifier/date shapes with **synthetic fresh
provider responses**, not new live observations. A human-accepted historical
assessment can proceed only when current stock/OTC, inactive, EODHD and Nasdaq
checks otherwise agree and the remaining gap is the unavailable successor
history. Its authority is explicit human attestation, not a relabelled automatic
success. Pre-2025 delistings also require attended handling.

Separate synthetic complete-timeline fixtures exercise the real worker's
automatic approval and the real transition service's application. The paired
missing-timeline fixture leaves tracking unchanged and shows the missing check.
Neither fixture authorizes modifying the three production cases.

## Verification

- Full backend: **5,834 passed, 12 skipped**, zero failures/errors. The final
  JUnit report contains 5,846 collected cases; `verification.json` records its
  digest and counts.
- Full frontend: **111 files, 1,393 passed**, zero failed/pending tests.
- Build: `tsc --noEmit` and Vite passed. The existing bundle-size warning remains.
- Browser rehearsal: 3 real component surfaces x 2 locales x 2 viewports
  (1440x1000 and 390x844), 32 screenshots. Temporary SQLite producers supply real
  closed case DTOs and memberships. All external hosts are blocked by the harness.
  It exercises removal, refresh without resurrection, Restore, preview without
  writes, explicit repair confirmation and a partial repair outcome. There are
  16 expected local mutation requests, zero page errors and zero unexpected
  requests. This is not a live provider or production App test.
- Visual inspection found and fixed unstyled membership inputs and a misleading
  case summary that hid the specific missing successor check in audit details.
- The full frontend run initially caught three old copy assertions. They now
  state that diagnostics are read-only and backfill requires separate
  confirmation. The no-dispatch-before-confirmation owners remain in place.

### Representative End-To-End Owners

- `test_reviewed_legacy_delisting_stops_shared_scope_and_sa_sync_cannot_resurrect`
  (ARCH, LTHM, TA): real assessment/preview/approval/application, persistent
  tombstone, retained history and zero acquisition aliases.
- `test_actual_worker_and_transition_service_require_proof_before_automatic_retirement`:
  automatic positive control versus missing timeline; the primary blocker belongs
  to the current observation and disappears when that observation changes.
- `test_even_a_replayed_preview_cannot_apply_after_listing_authority_changes` and
  `test_a_new_open_position_vetoes_even_an_approved_provider_terminal`.
- `test_former_removal_survives_sync_bootstrap_and_renamed_observation` paired with
  `test_unremoved_membership_follows_verified_alias_without_rewriting_origin`.
- `test_upgrade_preserves_real_v3_evidence_translations_identity_and_unowned_sql`,
  `test_membership_bootstrap_is_atomic_with_the_schema_upgrade` and
  `test_cutover_requires_stopped_app_and_exact_sa_observation_set`.
- `test_real_http_parsers_and_scan_obey_one_attempt_pacing_and_terminal_vetoes`:
  real transport/parser orchestration with fixture HTTP responses.
- `test_real_price_worker_fills_missing_and_partial_sessions_then_coverage_proves_completion`:
  one existing bar is retained, 51 missing bars are written through the actual
  worker/collector, then two complete 26-slot sessions are proven from SQLite.
- `test_explicit_ibkr_only_repair_never_falls_back_even_after_an_empty_response`:
  both lazy and injected fallback paths remain unused.

### Reverse Mutations

Mutations were made only in an isolated source copy, never in the feature or main
worktree. The first five used a 178-case focused set; the budget mutation expanded
it to 315 cases. These are targeted ownership checks, not exhaustive mutation
coverage. The restored expanded copy passed all 315 cases.

| Removed or Weakened Guard | Result | Owner |
| --- | --- | --- |
| Membership `removed_at IS NULL` filter | 3 failed / 175 passed | removal + related-current + sync projection |
| Active OTC veto | 1 failed / 177 passed | `test_otc_continuation_vetoes_terminal_even_when_three_sources_report_delisted` |
| Scoped conflict handling replaced by `INSERT OR IGNORE` | 1 failed / 177 passed | `test_invalid_provider_payload_is_not_silently_ignored_as_if_published` |
| FIGI/query/completeness fields removed from digest binding | 3 failed / 175 passed | `test_listing_identity_and_query_assertions_must_be_bound_to_the_evidence` |
| Disabled/valid automation installation gate | 4 failed / 174 passed | `test_provider_upgrade_requires_valid_disabled_automation_before_backup` |
| Legacy canary budget allowed to start the new scan | 1 failed / 314 passed | `test_legacy_canary_budget_cannot_start_the_new_provider_scan` |

The first expanded-copy budget run also failed because that temporary copy lacked
the tracked `resources/skills` directory. After copying those resources, the only
failure was the intended budget owner. That harness failure is not counted as
guard coverage. The earlier browser process needed cleanup; the final recorded
browser run exited normally with all assertions passing.

## Production Gates Still Required

1. **Read-only preflight authorization:** schema/automation switches, current
   SA observations and membership anchors, the three targets' independent sources
   and open positions, current price gaps. Do not read credential values. This
   establishes actual counts and the plan digest, not an inferred old universe.
2. **Cutover authorization:** stop the App and other profile writers; both
   automation switches false; approve the exact profile/SA digest; create a
   private, create-only backup; atomically migrate V3 to V4 and bootstrap accepted
   memberships; verify integrity/foreign keys and receipts. The new code rejects
   V3, so merge/restart must be coordinated with this cutover, not done first.
3. **Fresh provider-read authorization:** bounded targeted checks, not another
   190-request universe pass. Each exact target can issue at most 4 Massive
   listing requests plus 1 timeline request. One shared directory pass needs
   2 Nasdaq and 2 EODHD requests. Thus a three-target pass has a ceiling of
   **15 Massive + 2 Nasdaq + 2 EODHD = 19 HTTP requests**. Use 12.5-second Massive
   spacing across sessions, zero retry/fallback, and record actual attempts.
   Re-derive the budget if the preflight changes the target set.
4. **Three-case disposition authorization:** present fresh evidence and exact
   preview for each target. If its only remaining gap is unavailable successor
   history, obtain explicit attended acceptance. Apply through the existing
   transition service; open positions, active OTC or changed evidence stop that
   item. Verify absence from collection scope, retained history, no buyer alias,
   and continued suppression after a local SA reconciliation.
5. **Price-backfill authorization:** after terminal treatment, derive the current
   affected tickers/dates and actual collector request budget. Exclude unresolved
   contracts. Preserve existing prices, run approved IBKR-only repair, and verify
   the stored RTH slots. Report remaining provider/history limits as unresolved;
   never remove dates or symbols merely to make coverage look complete.
6. Only after these checks request a user hand test. Merge, production restart,
   opening unattended automation and push remain separately authorized actions.

No new production evidence, claim of repaired production coverage, or assertion
that ARCH/LTHM/TA have already stopped collection is made by this packet.
