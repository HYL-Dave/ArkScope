# Seeking Alpha Collection Guide

For button-by-button instructions in Traditional Chinese, see the
[Traditional Chinese guide](SA_COLLECTION_GUIDE.zh-Hant.md).

This guide describes the implemented controls, not future functionality.
For acquisition policy and technical limits, see
[Data Acquisition And Updates](DATA_ACQUISITION_AND_UPDATES.md).

## Before Collecting

- Use the formal extension, not an `ArkScope ... Test` add-on. Firefox loads
  `extensions/sa_alpha_picks/build/firefox/manifest.json`; Chrome loads
  `extensions/sa_alpha_picks/` as an unpacked extension. See the
  [installation instructions](extensions/sa_alpha_picks/FIREFOX.md).
- Keep the selected browser open and signed in to SA, with the subscription
  required by the requested content. A saved API key or working native host does
  not establish SA login or Premium/Alpha Picks entitlement.
- Chrome and Firefox share acquisition logic. Select one installation as the
  collector with **Use these settings here**. Stop automation in other
  installations before switching; there is no automatic browser failover.
- Keep the App open for audit delivery. The native host can save captures while
  the App is closed, but **Audit pending** means its job receipt is not delivered
  yet. Saving and recording a job are separate outcomes.

## Choose The Work

| Need | Control | Expected result |
| --- | --- | --- |
| Routine recommendations and new analysis | **Auto-sync Alpha Picks** | Runs at the selected interval; enabling it is not an immediate run. |
| Immediate recommendation update | **Quick Update** | Refreshes membership and a small newest-first detail batch, at most four distinct article pages. Not a historical backfill. |
| Routine market news | **Auto-sync Market News** | Independent recurring schedule, using the shared collector and restrictions. |
| Immediate market news | **Sync Latest News** | Refreshes the list and eligible details. Existing items may need no new detail page. |
| Financial tables for the App watchlist | **Financial statement updates** | Select **All App watchlist targets**, statements and periods; inspect supported/unsupported targets and estimated work before enabling **Scheduled financial updates**. |
| Save financial settings without starting work | **Save only** | Saves the selected scope with the financial schedule off. It does not start a one-time update; use **Enable updates here** to enable the selected schedule. |
| Repair missing article bodies | **Article body repair**: **Preview body repair**, then **Start repair** | Preview is local-only. One explicit start repairs the selected missing bodies over successive background turns. |

The watchlist comes from the App, not a hardcoded two-company test list. Unsupported
symbols must remain visible; they are not silently mapped to another company.
Scheduled collection walks eligible supported targets over time. Check the queued
scope and progress rather than expecting all companies to open simultaneously.

The financial page gap is adjustable in advanced controls, including 15 seconds.
It is a local pacing preference, not an SA-approved safe rate or a completion
promise. Routine work takes priority between background pages. Restrictions,
login pauses and shared cooldown still apply. Optional page-count limits are
separate: an uncapped installation remains uncapped unless explicitly changed.

## Body Repair And Discussion Scope

In **Settings > Data sources > Article acquisition**, the defaults are:

| Setting | Default |
| --- | --- |
| Articles per job | 0, unlimited |
| Article age in days | 0, unlimited |
| Article body scope | All retained articles, including Former history |
| Discussion scope | Current holdings only |

Saving settings does not start collection or delete content. Preview reports
selected, eligible, held and excluded counts; its short title list is a sample,
not a five-article limit. Start freezes the selected IDs. A changed preview
requires a new preview, not a silent replacement of the target list. Changes to
scope while running can skip newly ineligible work, but never expand that job.
To select a new set, cancel the old job, preview, and explicitly start again.

One article runs per shared queue turn; news and financial work can run between
articles. There is no whole-job 30-minute deadline. Individual page deadlines,
accepted page spacing, optional shared quotas and cooldown still apply. Closing
the popup does not cancel work. Browser restart preserves intent, but Firefox
temporary add-ons must be loaded again with the same identity before continuing.

`saved` requires a stored body and native receipt. `skipped` can mean already
present or out of scope; it is not a new save. `partial` means terminal work
includes failures. `waiting` includes pacing, cooldown and an occupied collector.
Cooldown resumes automatically; login, challenge and access pauses need the user
to handle the source and explicitly **Resume**. **Cancel job** is durable, not a
temporary pause. Offline cancellation remains pending until native confirmation;
do not clear browser storage to get past it. A stopped page with uncertain cleanup
must use the existing stopped-capture recovery, never a guessed timeout release.

A valid nonstale Current position wins ordinary Closed history for the same
established security: partial sales and re-entry still receive discussion updates.
Stale Current rows do not win. Former discussions stop by default, but existing
articles, associations, entry dates and comments stay stored. Permanent exclusions
and distinct companies reusing a ticker remain separate. This release does not
delete permanently retired content or perform LLM Entry/Exit classification.

With a nonzero age limit, current entry candidates retain priority; undated
non-entry articles are held rather than assigned an invented publication date.
All retained scope plus zero age can recover older retained original articles,
without claiming that their Entry/Exit roles have already been verified.

## Check The Result

### Updating During A Financial Fill

Use this maintenance procedure only after the isolated upgrade gate passes and
the operator approves the interruption. Disable the selected add-on in the
browser's extension manager without uninstalling it. Do not use Save only,
Cancel queued update or collector activation as a pause: they can change intent.
Confirm capture tabs are closed and native ownership is idle, then close the App.

Back up the stores and extension state. Compare ordered pending IDs, successful
captures, intent revisions, collector identity, policies and schedules before
and after replacing the same-path, same-ID package. Firefox temporary-addon
Reload may also enable it. On first adoption of an existing installation, the new
version holds acquisition at **Upgrade paused: queue verification pending**, even
when pacing deadlines expire or the extension reloads again. After equality is
confirmed, reopen the App and press **Resume after upgrade check** immediately.
This releases only the maintenance hold, not restrictions, cooldowns or saved
schedules. Require a stored
financial receipt for a previously pending scope, followed by a new body-job
receipt after explicit preview/start; counts and green badges are insufficient.

For rollback, cancel the new body job and confirm cleanup before loading the
old same-ID package. Keep newer captures and journal history; do not overwrite
them with an older whole-database backup. The baseline has a browser timer-call
defect fixed in this version, so verify actual continuation after rollback.

### Reading Outcomes

Inspect the popup's running task, saved/pending/failed counts and next attempt,
then the App's source health and job history. A tab closing alone proves nothing.
Use the arrow buttons under body-job outcomes to inspect later pages, including
failed articles. The current article is displayed separately from the selected page.

| State | Meaning |
| --- | --- |
| Complete | The run met its defined completion contract; not proof that every historical article or comment was collected. |
| Saved with pending work / deferred | Useful work can already be stored. A remaining comment scan, pacing or other deferral is not automatically a failed save. Inspect the specific reason. |
| Failed / degraded | At least one required operation failed. Do not equate the job record itself with a successful capture. |
| Audit pending | The browser has not delivered its receipt to the App. Check again with the App running. |
| Login or verification required | Stop automatic attempts and resolve the signed-in page or challenge yourself. Do not repeatedly click update. |

**Paused: sa_company_layout_unrecognized** means the financial table did not
pass the current layout validation and the financial queue is paused. That code
alone does not prove missing company data or insufficient subscription access.
Report the ticker, statement, Annual/Quarterly view, error time and a screenshot
including headers, units and row names. Preserve the queue while diagnosing it;
do not cancel it, reselect the collector or restart the entire watchlist to clear
the error. Stored observation counts do not prove the fill is complete.

For an older interrupted task, first stop its work and close its capture tabs.
If the popup reports stopped work, click **Review stopped capture**, check
**Previous capture stopped; its acquisition tabs are closed.**, then click
**Recover stopped capture**. The checkbox acknowledges what you have already
stopped; it does not close tabs. Do not check **Recheck all selected scopes,
including reusable data.** merely for recovery. Do not clear acquisition
storage, quotas or browser permissions to make
a blocked task disappear. Follow the
[routine recovery procedure](extensions/sa_alpha_picks/FIREFOX.md#activate-or-restore-routine-collection).

## Find Article Relationships

In the App, open **News**, select **Seeking Alpha** and analysis articles, widen
the date range when looking for an older selection/sale, then search the exact
stock symbol. Inspect each article's association details, not just its primary
ticker or headline. A known-symbol query uses exact associations; quoting a query
forces text search. Date filters and pagination still apply.

- **Entry** links concern the original selection for a particular pick date.
- **Exit** links concern a sale/removal event; this can be a different article.
- **Related** means company coverage without a confirmed entry/exit role.
- Provenance and evidence codes distinguish automatic rules, user decisions,
  provider observations and legacy ticker assignments. They are not calibrated
  confidence scores and do not prove that a full investment thesis was read.

The extension's **Article link review (advanced, optional)** is an unresolved
candidate review queue, not the complete article history. Manual review is not
required to use generic related articles. No stored event link means "not linked
here," not "no selection or sale happened."

**Not implemented:** a separate LLM task that reads the full local article and
classifies event roles/commentary, with its own model selector. Current links use
rules and optional manual decisions. Changing the AI research or translation
model does not turn on a classifier. A new classifier must reject missing bodies,
validate quotations and retain model/prompt provenance before creating links.
The proposed [App workbench and classification design](docs/superpowers/specs/2026-09-27-sa-article-workbench-and-classification-design.md)
separates manual browsing/editing from explicit model execution and optional
application of eligible relationships. It awaits review and is not a description
of controls available in the current release.

Article text can retain original image URLs, labels and captions. These are not
offline image files, OCR or evidence that a text-only model inspected the chart.
