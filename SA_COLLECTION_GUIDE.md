# Seeking Alpha Collection Guide

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
| Save financial settings without starting work | **Save only** | Saves the selected scope and schedule switch as shown. It does not start a one-time update. |
| Repair missing article bodies | **Article body repair**: **Preview body repair**, then **Start next up to 5** | Preview is local-only. Starting explicitly queues a bounded repair batch; it does not run the whole historical corpus. |

The watchlist comes from the App, not a hardcoded two-company test list. Unsupported
symbols must remain visible; they are not silently mapped to another company.
Scheduled collection walks eligible supported targets over time. Check the queued
scope and progress rather than expecting all companies to open simultaneously.

The financial page gap is adjustable in advanced controls, including 15 seconds.
It is a local pacing preference, not an SA-approved safe rate or a completion
promise. Routine work takes priority between background pages. Restrictions,
login pauses and shared cooldown still apply. Optional page-count limits are
separate: an uncapped installation remains uncapped unless explicitly changed.

## Check The Result

Inspect the popup's running task, saved/pending/failed counts and next attempt,
then the App's source health and job history. A tab closing alone proves nothing.

| State | Meaning |
| --- | --- |
| Complete | The run met its defined completion contract; not proof that every historical article or comment was collected. |
| Saved with pending work / deferred | Useful work can already be stored. A remaining comment scan, pacing or other deferral is not automatically a failed save. Inspect the specific reason. |
| Failed / degraded | At least one required operation failed. Do not equate the job record itself with a successful capture. |
| Audit pending | The browser has not delivered its receipt to the App. Check again with the App running. |
| Login or verification required | Stop automatic attempts and resolve the signed-in page or challenge yourself. Do not repeatedly click update. |

For an older interrupted task, first stop its work and close its capture tabs.
Then use the explicitly acknowledged **Recover stopped capture** control if
needed. Do not clear acquisition storage, quotas or browser permissions to make
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
