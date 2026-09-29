# SA Comment Acceptance

This is a bounded manual test harness, not a replacement production extension.
It exports the actual production capture functions and copies the same scrapers.
The generated package contains neither a native-host binding nor schedules.
The user chose signed-in Firefox. Chrome production code shares the same module;
Firefox live acceptance does not establish Chrome live acceptance.

## Build

From the repository root, using the project Python environment:

```sh
python -m tests.sa_comment_acceptance.build /home/hyl/ArkScope-Comment-Test/extension
```

The output directory must not already exist. Source hashes and a combined code
fingerprint identify the exact capture code. No extension is installed, no host
is registered and no website is opened by this command.

## First Observation

Version 1.0.5 adds **Recent 30 days + context** (default) and separate historical
expansion. Use the same scope for both sides of a new pair. The 120-second
**Initial** budget is independent of that selection. Older rows already loaded
by the page are kept; recent scope defers unnecessary older text expansion, not
old-parent traversal. Current production code remains a candidate until live
acceptance; do not repeat the old 1.0.4 campaign automatically.

1. Pause the normal SA extension's automatic collection for this test, or
   temporarily disable that extension. Leave the SA login intact.
2. In Firefox `about:debugging#/runtime/this-firefox`, load the generated
   `manifest.json` as a temporary add-on. It is named **ArkScope Comment Test**,
   ID `sa-comment-test@arkscope.local`, distinct from Company Test and production.
3. Open one Alpha Picks article. Wait until its body is readable; do not expand
   comments manually first. Click the Comment Test toolbar icon while on that
   article. A test panel opens; the article remains the selected target.
4. In version 1.0.3 keep **Legacy + candidate observation** and select
   **Initial / backfill (120 seconds)**, then click **Capture Selected Article**
   once. The target tab becomes active, as with the original collector. This
   uses the approved existing Deep profile: 140 rounds, 120 seconds,
   1.6-second settle and five stable-bottom rounds, plus the original
   2.5-second initial settle. It is a new paired baseline, not a relabeling of
   the earlier 45-second Manual run. No automatic retry is added.
5. The run exports JSON to the browser download directory under
   `ArkScope-Comment-Test/`. Return to the panel for status, then report completion
   to the developer. Stop on verification, login, restriction or capture errors;
   do not keep retrying.

The legacy mode retains legacy click selection, including its known risks, but
uses the new document/identity rejection guard. Do not run it over a list of
articles or interpret this diagnostic mode as an approved production option.

## Passive Structure Inspection

If an observed control's ancestry is insufficient to explain a selector
difference, **Export Loaded Comment Structure** reads the currently loaded
article without clicking, scrolling, reloading, or starting another capture.
Open the panel from the article's toolbar icon after reloading the test add-on;
do not reload the article just for this inspection. The export is named
`ARTICLE-structure-TIME.json`, distinct from a capture or paired-run result.
It records bounded control labels, ancestor/child structure and comment-row
counts, not article prose, comment text, form values or URL query parameters.
Already-expanded controls may have disappeared; absence in this later
inspection does not overturn the earlier same-DOM observation.

## Paired Candidate Run

Only after reviewing the observed controls, reload the same article and run
**Guarded candidate** with the same profile and otherwise unchanged environment.
After capture code changes, create a fresh **Legacy + candidate observation**
baseline using the updated package first, then reload for **Guarded candidate**.
Both exports must identify the same capture-code fingerprint; do not edit old
artifacts to relabel their source revision.
The selected profile and its limits are exported with each capture. For the
new first-capture pair, both runs must select Initial / backfill. The Routine
option retains the 12-second Quick profile and is a separate experiment, not
an interchangeable comparison partner.
Never compare two modes on one already-expanded document. The harness rejects
repeated captures of the same document, enforces 60 seconds between attempts and
allows at most six attempts in its own storage. It does not alter the production
15/60-second pacing policy. There are no automatic retries or reloads.

```sh
python -m tests.sa_comment_acceptance.compare BEFORE.json AFTER.json
```

The comparison checks source/period-of-test inputs, full text, parent links,
article body, counts and cost. `no_regression_observed` is a narrow paired result,
not proof of universal completeness or official comment count accuracy. Missing
or changed comments fail acceptance; different provider counts, changed bodies,
unknown totals, additional comments, truncated traces, or higher rounds/time are
inconclusive. Review elapsed-time differences rather than increasing budgets to
make a candidate pass. Synthetic IDs alone are not used as text identity.
The operator has explicitly approved a higher first-capture budget for the new
pair. That approval does not waive missing-text, parent or identity checks, and
does not establish that the increased runtime/work is acceptable in every
routine update. Per-round geometry now distinguishes cap exhaustion before
the bottom from a stable terminal scan.

## Incremental Maintenance Gate

Hermetic store/metadata-flow tests separately verify that identical comments
cause no row updates, new comments remain insertable, first capture is selected
per article, unchanged provider counts do not hide pending work, and partial
scans cannot advance a completion checkpoint. A six-hour retry delay and a
one-pending-article Quick batch prevent immediate repeated deep captures.
Explicit Deep Repair bypasses only that local retry delay.

These database tests do not establish a website incremental cursor. Reopening
SA may still load existing parent comments to discover replies, and seeing one
known comment is not an early-stop proof. A signed-in routine probe cannot by
itself prove that no new replies exist in older threads.

At least a nested-reply case and a larger thread remain required before adoption.
The initial one-article observation is deliberately not the whole acceptance.
Artifacts contain subscribed article/comment text: keep them local, do not
commit or upload them. After testing, remove this temporary add-on and restore
normal collection only when no test capture is running.

## Release Gates

- Offline adversarial and actual-browser tests cover known navigation paths,
  identity rejection and preservation of comments/checkpoints.
- A real installed Firefox package test checks dependencies, message handling
  and panel dimensions. It never signs into SA.
- The first signed-in Firefox observation exported successfully. It found two
  real **See More Replies** controls rejected as `outside_comment_controls` by
  the initial candidate. Passive inspection then established the sibling reply
  footer structure. Version 1.0.2 corrects that recognition, the `see` verb and
  unresolved-state reporting, with offline regression tests. Its independent
  paired run is **not accepted**: legacy captured 81 comments; guarded captured
  105 but missed two legacy comments and reached the existing 45-second cap.
  The 79 shared comments have identical text and parent relationships; that does
  not compensate for missing comments. Investigate traversal before another
  live pair; do not extend time limits, add retries or merge the exports to
  manufacture acceptance. See [the historical observation record](https://github.com/HYL-Dave/ArkScope/blob/220fe6d26fb366e421336ecba9e17b47f7d255da/docs/superpowers/evidence/2026-09-24-sa-comment-observation.md).
- The later 120-second small-thread pair kept all 81 baseline comments and
  added 26, but used more work/time: supporting evidence, not blanket acceptance.
- The large-thread 1.0.4 pair is **not accepted**: 259 legacy vs 218 guarded,
  206 shared unchanged, 53 missing and 12 added. Both timed out before bottom.
  All 53 missing comments were recent. New recency priority does not relabel it.
- Version 1.0.5 adds loaded-frontier traversal and recency/context priority.
  The new signed-in pair retains all 259 baseline rows, adds 93 and reaches
  stable bottom in 91.879 seconds versus the baseline's 121.271-second timeout.
  The strict comparator remains inconclusive for added coverage; five extra
  expansion clicks and the 352/353 count gap are explicitly not waived.
- Private 1.0.6 uses identical capture code with one separate routine slot.
  Its 12-second probe captures 105 rows, stops partial, and preserves all 107
  previously stored rows in isolated replay with zero comment row writes.
  This is not a complete capture or live new-reply test. See
  [the historical recent/routine evidence](https://github.com/HYL-Dave/ArkScope/blob/220fe6d26fb366e421336ecba9e17b47f7d255da/docs/superpowers/evidence/2026-09-24-sa-comment-recent-and-routine-acceptance.md).
  No existing failures are relabeled; raw subscribed artifacts stay outside Git.
- A final code freeze, complete backend/frontend/typecheck/build run and review
  are **pending**. Earlier revision results cannot stand in for these.
- No merge, production extension replacement or 180-company run is authorized
  by this harness.
