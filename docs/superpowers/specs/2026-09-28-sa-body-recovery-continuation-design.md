# SA Body Recovery Continuation

Status: direction approved; this written design awaits operator review.
No runtime changes, production migration, or collector restart are authorized by
this document alone. Review the implementation plan separately after this spec.

## Outcome And Scope

Start one finite recovery job and let it repair all eligible retained articles,
in priority order, without repeated five-article clicks. Preserve successful
captures, make progress inspectable, and allow cancellation at any time. Popup
closure must not stop the job; browser restart must retain unfinished work.
The browser must be running and the same extension installed to acquire pages.

Default to no article-count limit. An optional limit belongs in App Settings,
not a constant in the extension. Retain existing shared pacing, restrictions,
collector ownership and navigation budgets. Do not change financial first-fill,
news/Alpha schedules, source selection, paid consent, or LLM classification.

The existing manifest determines eligibility and priority: current-holding entry
articles/candidates first, then eligible recent follow-ups and other articles.
This change does not silently expand to held older articles or future discoveries.
Preview must distinguish eligible, already available, and held/out-of-scope counts.
Finishing a job does not certify the entire article archive as complete.

## Verified Starting Point

- `background.js` currently caps a batch at five articles and 30 minutes.
  Saved browser state lacks the target URLs/digests needed to resume safely.
  A lost event page turns unfinished items into interrupted/cancelled outcomes.
- `src/sa_native_host.py` separately returns five preview targets to bound native
  messages. Removing the product limit must not create unbounded native replies.
- The native collector admits body repair only with a manual trigger. Automatic
  continuation needs an explicit contract tied to an existing manual job.
- `company_refresh.js` already demonstrates persisted intent, alarm wakeups and
  cancellation revisions. `acquisition_client.js` reconciles native task receipts.
  Reuse these patterns and the existing shared queue, not a second collector.

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
sample rather than pretending that sample is the whole job. Start revalidates the preview identity,
reads the configured limit, and atomically records the selected ordered targets
before any navigation. If the preview changed, return a refresh-required result;
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
3. Before navigation, revalidate the target against retained data and current
   eligibility. Preserve usable bodies; skip changed/out-of-scope targets with
   reasons. Keep the existing exact article identity and expected-digest save
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

Add `max_articles_per_job` under App Settings > Data Sources > Seeking Alpha,
using the existing profile-setting validation and save/undo patterns. Value `0`
means unlimited and is the default; otherwise require a positive safe integer.
Invalid saved settings block start with a repairable error, not an unlimited
fallback. Saving settings performs no navigation. A job snapshots its selected
scope and limit; changes apply to the next explicit start, never silently widen
an existing job. Show the effective limit and any unselected eligible remainder.

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
- Run the complete backend regression with browser gates enabled, frontend tests
  and build, plus responsive Settings/popup checks. Preserve meaningful assertions;
  do not weaken old timeout tests without replacement lifecycle coverage.

Implement on an isolated branch. Do not replace the formal native host or extension
while the current financial fill is running. After review and regression, request
a brief stop-write window, back up the exact affected stores/settings, rehearse the
upgrade and rollback on copies, update compatible components together, then ask
for immediate restoration. Verify new formal job receipts and continued financial
progress after restart; offline tests alone do not certify the live cutover.

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
