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

1. Pause the normal SA extension's automatic collection for this test, or
   temporarily disable that extension. Leave the SA login intact.
2. In Firefox `about:debugging#/runtime/this-firefox`, load the generated
   `manifest.json` as a temporary add-on. It is named **ArkScope Comment Test**,
   ID `sa-comment-test@arkscope.local`, distinct from Company Test and production.
3. Open one Alpha Picks article. Wait until its body is readable; do not expand
   comments manually first. Click the Comment Test toolbar icon while on that
   article. A test panel opens; the article remains the selected target.
4. Keep **Legacy + candidate observation** and click **Capture Selected Article**
   once. The target tab becomes active, as with the original collector. It uses
   the existing Manual limits: 60 rounds, 45 seconds, 1.2-second settle, plus the
   original 2.5-second initial settle. It does not increase retries or limits.
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
  the candidate. The selector also lacks `see` for reply expansion. Adoption is
  **blocked pending correction and paired evidence**, not validated by this
  successful export. See [the observation record](../../docs/superpowers/evidence/2026-09-24-sa-comment-observation.md).
- A final code freeze, complete backend/frontend/typecheck/build run and review
  are **pending**. Earlier revision results cannot stand in for these.
- No merge, production extension replacement or 180-company run is authorized
  by this harness.
