# SA Body Recovery Continuation

Status: direction approved; this written design awaits operator review.
September 28 review adds configurable scope and a retired-content boundary.
No runtime changes, production migration, or collector restart are authorized by
this document alone. Review the implementation plan separately after this spec.

## Outcome And Scope

Start one finite recovery job and let it repair all eligible retained articles,
in priority order, without repeated five-article clicks. Preserve successful
captures, make progress inspectable, and allow cancellation at any time. Popup
closure must not stop the job; browser restart must retain unfinished work.
The browser must be running and the same extension installed to acquire pages.
Firefox temporary add-ons disappear on browser restart: the operator must reload
the add-on before any continuation. The native journal can retain work, but does
not reinstall the extension. If collector identity changes, explicit ownership
selection and task reconciliation are required; automatic transfer is forbidden.

Default to no article-count limit. An optional limit belongs in App Settings,
not a constant in the extension. Retain existing shared pacing, restrictions,
collector ownership and navigation budgets. Do not change financial first-fill
targets, news/Alpha schedule frequency, paid consent, or LLM classification.

Keep current-holding entry articles/candidates first, followed by eligible current
follow-ups and other selected retained articles. Make membership scope and article
age configurable instead of retaining a hidden 365-day limit. An explicit new
preview/start can include older articles; a running job cannot acquire articles
outside its frozen selection or pick up future discoveries automatically.
Preview must distinguish eligible, available, retired, unresolved and out-of-scope
counts. Lack of an established article association is not proof of retirement.
Finishing a job does not certify the entire article archive as complete.

## Verified Starting Point

- `background.js` currently caps a batch at five articles and 30 minutes.
  Saved browser state lacks the target URLs/digests needed to resume safely.
  A lost event page turns unfinished items into interrupted/cancelled outcomes.
- `src/sa_native_host.py` separately returns five preview targets to bound native
  messages. Removing the product limit must not create unbounded native replies.
- The native collector admits body repair only with a manual trigger. Automatic
  continuation needs an explicit contract tied to an existing manual job.
- Current entry articles/candidates already bypass the 365-day age cutoff. The
  retained NUE/VLO/COP/SMCI cohorts are closed, with no confirmed entry links;
  enabling older content must not invent entry associations for them.
- `DataAccessLayer.save_sa_articles_meta` selects pending/expired comment work
  across retained articles without a common retired-membership exclusion.
- `company_refresh.js` already demonstrates persisted intent, alarm wakeups and
  cancellation revisions. `acquisition_client.js` reconciles native task receipts.
  Reuse these patterns and the existing shared queue, not a second collector.

## Membership And Retention Boundary

Use one local eligibility decision for body repair and discussion acquisition,
with different policies for the two operations. Read confirmed current/former
memberships and permanent exclusions, resolving established identity transitions.
Do not equate a missing list observation, stale snapshot, uncertain association,
API failure or renamed ticker with a confirmed exit or terminal delisting.
If membership/exclusion state is unavailable, return a typed blocked decision;
do not treat an unreadable store as an empty exclusion list.

Default discussion acquisition to current Alpha Picks memberships. Do not keep
refreshing confirmed former-only or permanently excluded discussions just because
they remain pending in an old queue. Apply the decision to Quick, Full, Deep,
enrichment, initial detail capture and comment retry paths, and recheck before
comment traversal. Scope-excluded work is skipped with a reason, not reported as
an acquisition failure or an endlessly pending backfill. Unknown ownership is
held for review, never treated as retirement or a reason to delete content.

A shared article remains eligible when it also belongs to an eligible current
membership. Match article/lineage identities and established aliases, not ticker
prefixes or title guesses. Re-entry of the same ticker can create a different
cohort; an old cohort exclusion must not suppress a legitimate new one. General
market news and company-financial acquisition are outside this retention policy.

The operator permits deleting unneeded analysis bodies and discussions belonging
exclusively to removed Alpha Picks targets. Keep this as a separately reviewed
cleanup operation, not an automatic side effect of refresh or a new purge timer.
Before applying it, preview exact targets, article/comment counts, reference
dependencies and shared/unresolved exclusions; revalidate that preview under the
stop-write boundary and take a recovery backup. Do not delete shared content or
assume a missing ticker proves exclusive ownership. Preserve minimal identity,
entry/exit facts and exclusion/deletion markers so old list metadata and pending
jobs cannot silently reacquire purged content. Update affected local indexes and
owned raw copies; retained links/readers must report deliberate removal rather
than a broken reference or missing capture. Do not purge unrelated research output.

Cleanup scope still needs one operator decision: retain Closed/Former history and
purge only permanently removed targets, or also purge former-only content once it
leaves Current. Until that decision, preserve Closed/Former content. The first
delivery implements eligibility and stops unwanted acquisition; destructive
cleanup has its own inventory, verification and approval, independent of SEC
retirement. ARCH/LTHM/TA permanent exclusion facts survive either choice.

## Chosen Ownership

Keep browser alarms and page capture in the extension. Keep the authoritative
finite job, target snapshot, intent revision and per-item outcomes in a narrowly
owned recovery journal in the existing `sa_company_refresh.db`. Browser storage
caches job identity and wakeup information, not a conflicting second result log.
The journal contains acquisition metadata, never duplicate article bodies.

This is a small recovery-specific journal, not a general job platform. It avoids
cursor drift as saved bodies disappear from the live manifest, and lets native
admission verify continuation after browser restart. A browser-only queue would
require separately durable native intent anyway. An endless in-memory loop cannot
meet restart and cancellation requirements.

Preview remains local-only and read-only, returning complete counts and a bounded
sample rather than pretending that sample is the whole job. Start revalidates the
preview identity, reads the configured policy, and atomically records selected
targets before any navigation. If the preview changed, return a refresh-required result;
do not silently acquire a different target set. Repeated start requests with the
same request identity return the existing job, not a second job.

Each target retains its article ID, validated SA URL, expected body digest and
priority. Native replies paginate metadata using job-bound cursors and a byte
budget. Pagination is a transport constraint, not a user-facing article cap.
Only explicit start installs the journal; status/preview reads never install it.

## Execution And Recovery

1. Persist the manual intent with profile/collector identity and generation.
   Bind each continuation to its job ID, revision and article. Native admission
   rejects unrelated, cancelled, completed or wrong-owner jobs; alarms cannot
   create repair intent or impersonate a fresh manual start.
2. On each wake, reconcile any prior acquisition receipt before selecting work.
   Use the shared queue for at most one article acquisition per turn, then release
   the collector. Routine work keeps its priority; ready financial/background
   work must not starve behind the entire recovery job.
3. Before navigation, revalidate the target against retained data, current
   eligibility and any later exclusion/deletion marker. Preserve usable bodies;
   skip changed/out-of-scope targets with reasons. Keep the existing exact article
   identity and expected-digest save
   checks. A page parse must not overwrite a newer or already usable body.
4. Persist attempt identity before work. Keep the native lifetime connection only
   for the active page task; wait using alarms, not an indefinitely open port.
   Preserve finite page-operation timeouts, but remove the whole-job 30-minute
   expiry. Every page still passes native navigation admission and shared pacing.
5. After save, persist the outcome and close the owned tab before releasing its
   reservation. If a crash separates save from checkpoint, read back the retained
   body and receipt before retrying. An already repaired target needs no new page.
6. After event-page suspension or browser restart, resume pending work only when
   the previous task is proven terminal and cleanup is confirmed. Unknown active
   navigation/reservations require existing explicit recovery; age alone cannot
   release them. Ownership changes pause the job instead of transferring it.

Per-item states are pending, running, saved, skipped or failed. Parse/save failures
remain visible and are not retried indefinitely; the job proceeds to other items
when cleanup is confirmed. A new preview can include still-missing failed bodies.
Job completion with any failed items is partial, not complete. Skipped reasons and
remaining archive gaps are visible even when all selected work has been processed.

## Wait, Pause And Cancel

| Condition | Required behavior |
| --- | --- |
| Pacing, capacity or higher-priority work | Preserve pending work; wake at the authoritative next eligible time. |
| Rate limit with a cooldown deadline | Persist waiting state; resume admission after that deadline, never bypass it. |
| Login, human verification or subscription/access restriction | Pause; require the existing explicit handled/resume action after operator intervention. No repeated challenge attempts. |
| Host unavailable or cleanup uncertain | Stop navigation; reconcile on availability. Never clear an unverified reservation automatically. |
| Cancel | Persist cancellation/revision before acknowledging; invalidate future wakes and admissions, finish cleanup of any active page. |

Cancel remains effective while waiting, paused or after browser restart. An
in-flight valid save may finish and remains recorded; cancellation must never
discard saved data or resurrect the job. Start, cancel, checkpoint and alarm races
must resolve by persisted job/revision checks, not just an in-memory flag.
When the host is unavailable, persist a local cancellation intent, suppress all
wakes and synchronize it before any later admission; show cancellation pending
until the authoritative journal acknowledges it. A restriction leaves the current
item pending for resume, not silently failed or removed from the job.

## Settings And Operator Surface

Add the following under App Settings > Data Sources > Seeking Alpha, using the
existing profile-setting validation and save/undo patterns:

| Setting | Proposed default and meaning |
| --- | --- |
| `max_articles_per_job` | `0`: no count cap; otherwise a positive safe integer. |
| `body_scope` | `all_retained`: eligible retained articles, including former/unassigned history; alternatively `current` for established current memberships/candidates only. Permanent exclusions/deletion markers always apply. |
| `body_lookback_days` | `0`: no age cutoff; otherwise a positive safe integer for dated non-entry articles. Selected entry articles/candidates remain age-unlimited. Unknown dates are explicitly reported, not given invented ages. |
| `comment_scope` | `current`: stop former-only discussion updates; `tracked` explicitly includes accepted, non-removed former memberships. Permanent exclusions/deletion markers always apply. |

An unassigned article is allowed for body acquisition under `all_retained`, not
for automatic discussion refresh or destructive cleanup. Source-identity conflicts
remain unresolved; a broad scope setting cannot override integrity guards. With an
age limit, undated non-entry articles are held; with no age limit their missing
date is disclosed and does not itself block capture. Selecting former content
does not classify its articles as Entry/Exit or restart its discussions.

Invalid saved settings block start with a repairable error, not an unlimited
fallback. Saving settings performs no navigation. A job snapshots its selected
scope and limit; changes apply to the next explicit start, never silently widen
an existing job. A target that becomes ineligible or is purged must be excluded
before the next corresponding acquisition, including already queued work; this
also applies to narrower discussion policy. Show the effective policy and any
unselected eligible remainder.

The popup retains Preview and one Start command, with Cancel for any unfinished
job and Resume only where intervention is required. Show selected total, saved,
skipped, failed, remaining, current item, wait reason and next eligible time when
known. App status reads use the same journal summary. Do not show a false exact
completion estimate or label waiting as failure. Update both operation guides
and action descriptions when the implementation ships, not before.

Old five-item batch history stays readable. It lacks sufficient intent/targets
for automatic migration into a new job: show interrupted history and require a
fresh preview/start. Detect extension/native protocol mismatch before acquisition.
Do not reset collector configuration, existing queues, schedules or ownership.

## Acceptance And Cutover

- More than five eligible articles finish after one start; virtual elapsed time
  beyond 30 minutes does not terminate the job. Priority and finite scope hold.
- Restart/suspend between items, during acquisition and after save-before-checkpoint
  causes no duplicate repaired-body navigation, silent loss or false completion.
- Cancel-versus-wake/save races, duplicate starts, stale cursors/digests, changed
  membership, ownership changes and old/malformed journal state have regressions.
- Cooldown resumes only when eligible; login/challenge/access never auto-clears.
  A failed page is retained in results without blocking all other eligible work.
- Shared routine/financial work progresses, page pacing remains enforced and
  popup closure does not stop acquisition in isolated Firefox and Chromium gates.
- Settings cover default/unlimited, explicit caps, invalid values, saved roundtrip
  and native agreement. Preview/status/settings reads make no provider requests.
- Cover old current entries, opt-in current-only scope, former/unassigned articles,
  age limits and missing dates without inventing Entry/Exit associations. Cover
  current-to-closed changes, permanent exclusions, re-entry, shared articles and
  unresolved ownership across all comment acquisition paths and queued work.
- Prove that purged/excluded targets cannot be silently requeued; leave destructive
  cleanup unapplied until its exact content scope and reference handling are reviewed.
- Rehearse a mid-fill upgrade with financial pending scopes, intent revisions,
  successful receipts and ownership intact, and continuation of remaining work.
  Include Firefox temporary-add-on reload and collector-identity mismatch cases.
- Run the complete backend regression with browser gates enabled, frontend tests
  and build, plus responsive Settings/popup checks. Preserve meaningful assertions;
  do not weaken old timeout tests without replacement lifecycle coverage.

Implement on an isolated branch. Never replace the formal native host or extension
during active acquisition. It is not necessary to wait for the entire financial
first-fill to finish: after review and regression, an operator-approved brief
pause may be used if queue-preserving upgrade/rollback has passed rehearsal.
The existing financial Cancel and configuration-change paths clear pending scopes;
they are not interchangeable with a non-destructive pause. Back up the affected
native stores, settings and extension queue/intent state at a confirmed idle
boundary, update compatible components together, then request immediate restoration.
Verify the same pending financial work and stored success progress, plus new formal
job receipts. Offline tests alone do not certify the live cutover, and this design
does not request that the operator pause the ongoing fill now.

## Separate Retirement Follow-up

SEC/lifecycle retirement remains a later independent batch: decouple retained SA
tool paths first and preserve an actual SA invocation regression without the SEC
package. Keep ARCH/LTHM/TA excluded after migration; test provider conflict,
permissions and OTC continuation as well as rename detection. Preserve the four
API checks, symbol search and applied outcomes. Evidence helpers must move before
their directories are deleted; local deletion still needs an exact reviewed list.

The questioned worktree commit `ebe4c051` is already patch-equivalent to master
commit `53bd4087`: `git cherry master ebe4c051` reports `-`, and all four changed
files have identical contents at those commits. No second cherry-pick is needed.
This establishes no missing patch, not permission to delete the worktree's ignored
files or other backups. Future automatic listing actions need their own explicit
decision; this body-recovery design does not change them.
