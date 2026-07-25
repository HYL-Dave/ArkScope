# ArkScope SA Extension Reliability and Control-Clarity Design

> **Status: INDEPENDENT REVIEW GREEN - PLAN REVIEW GREEN - IMPLEMENTATION CLEARED**
>
> Written against clean `master` at `38178f65` on 2026-07-25. This document
> is the design authority for the bounded Seeking Alpha browser-extension
> reliability batch that follows the completed app-wide i18n line. Product
> implementation is authorized only on the isolated branch after the separate
> RED-first implementation plan received independent GREEN. The plan is
> `docs/superpowers/plans/2026-07-25-sa-extension-reliability-control-clarity.md`.

## Review Resolution (2026-07-25)

Independent review returned GREEN with one required control-bound amendment
and three advisories. The underlying finding is adopted: the third Alpha
Picks action was named too narrowly and omitted its expensive article-list
and detail behavior. It is renamed `Deep Repair Scan`, and Section 8 now
states every fixed bound plus the absence of a global Alpha article-detail
cap.

One factual part of the review is corrected rather than copied: `18`, `30`,
and `80` are Market News detail budgets in
`MARKET_NEWS_DETAIL_TOTAL_LIMITS`/`MARKET_NEWS_PROFILES`; they do not cap the
Alpha Picks `doRefresh()` path. Alpha normal missing-body work is bounded by
the returned article-list work set, not by a separate numeric detail limit.
Writing the Market News values into the Alpha action rows would create the
same misleading-control defect this unit exists to remove.

All three advisories are adopted: legacy `detail_not_saved` prose cannot seed
four-state outcomes, the reviewed historical manifest uses no-age
recorded-ID repair rather than the 168-hour incident window, and the
implementation plan must audit every consumer affected by mapping degraded
extension runs to database `failed`.

Implementation-plan grounding also closes one ordering ambiguity in the
written draft: routine capture outcome and telemetry persistence are separate
axes. The extension must derive capture truth before it can POST that truth,
so telemetry delivery cannot be an input phase of the same derivation. A
locally complete capture with pending telemetry is shown as exactly that and
cannot become a durable healthy anchor until the row lands. Repair remains
stricter: durable audit creation is a precondition to start and terminal audit
finalization is part of repair completion.

## Post-Merge Contrast Deviation (2026-07-25)

The merged popup passed its original geometry, clipping, keyboard, label, and
description gates, but user inspection found that the normal action labels
were difficult to read. Browser computed-style evidence proved a real cascade
defect: five legacy ID selectors still supplied saturated action backgrounds,
while the newer `.action-button` class supplied dark-blue text. The resulting
text contrast ranges from `1.12:1` to `2.03:1`.

Expanding every disclosure and exposing conditional controls found the full
bounded repair set:

- all five normal action buttons fail text contrast;
- both auto-sync helper lines are `4.11:1`, and the resolved-window hint is
  `2.85:1`;
- the partial status is `3.46:1`;
- `Review recovery scope` is the only recovery control without a matching
  button variant and renders as white text on the browser's light button face;
- `Fetch and review` is `3.08:1`; and
- after the normal actions return to white backgrounds, their current
  `#b9c6d4` border would provide only `1.74:1` non-text contrast.

One external-review claim is explicitly rejected after full selector and DOM
binding verification: `incidentRecoveryBtn`, `resumeRecoveryBtn`, and
`cancelRecoveryBtn` are descendants of `.recovery-actions`, and
`retryRecordedFailuresBtn` is named in the same rule. Those four controls
already render white on `#315f7d` at `6.85:1`. Only
`reviewRecoveryScopeBtn` lacks the variant.

The user approved one bounded post-merge repair before LIVE closeout:

1. delete the five obsolete ID-specific action background and hover rules;
2. make the normal action owner white with `#174b72` text and a control border
   of at least `3:1` against white (`#7b93ab` is the reviewed value);
3. give `Review recovery scope` a matching contrast-safe outline treatment;
4. keep filled recovery and reconciliation actions explicit, and make the
   manual action use the existing neutral filled-action treatment rather than
   warning orange;
5. render helper text with `#666`, partial status with `#b45309`, and disabled
   labels with a dark foreground that remains readable on `#bdbdbd`;
6. add one computed-style regression node that enumerates every text-bearing
   control, opens `<details>`, exposes conditional controls, drives all status
   variants, and checks normal text `>=4.5:1`, large text `>=3:1`, and required
   control boundaries `>=3:1`;
7. prove that node RED by removing each load-bearing repair class in a
   disposable copy, then run real Chrome and Firefox popup visual gates; and
8. add one operator note inside `What these actions do`: scans may activate
   and scroll Seeking Alpha tabs, so switching tabs in the same browser during
   a run is unsupported and may reduce capture completeness.

This deviation changes no scraper, capture budget, auto-sync cadence, native
protocol, database, or web-app behavior. `#b45309` on `#fff3e0` is accepted at
`4.58:1`; any future change to either color must rerun the computed-style gate.
The gate gap itself is part of closeout evidence: the original visual matrix
checked geometry and visible labels but did not expand hidden states or audit
contrast.

## 1. Purpose and Authority

The Firefox extension build loaded on 2026-07-19 omitted
`article_identity.js`. Both article-list and article-detail injection require
that file, so Alpha Picks list capture remained partly usable while detail
capture silently failed. Separately, 25 Market News runs between
`2026-07-19T11:45:38Z` and `2026-07-20T14:02:20Z` each reported
`detail_failed=18` but were persisted with `job_runs.status='succeeded'`.
The combination hid roughly 26 hours of failed detail work behind a green
outer status.

The immediate manual copy/reload restored capture, but it did not close the
structural defects:

1. the Firefox installer can still build an incomplete extension;
2. aggregate status can still contradict nested detail results;
3. repair operations are not durable, resumable, or audited;
4. routine Market News catch-up is bounded to 24 hours and cannot recover a
   longer interruption;
5. the popup's five controls do not state their operational bounds; and
6. supported recovery still risks becoming a console-only workflow.

This design closes those defects in one reviewed unit. Authority order is:

1. this document owns packaging completeness, structured extension outcomes,
   Market News recovery, popup control semantics, and the incident-repair
   procedure;
2. [`SA_EXTENSION_ROADMAP.md`](../../design/SA_EXTENSION_ROADMAP.md) continues
   to own the broader extension roadmap and recent-window product direction;
3. [`SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md`](../../design/SA_EXTENSION_HEALTH_SETUP_BOUNDARY.md)
   continues to own browser/native-host/sidecar setup boundaries;
4. [`2026-07-20-app-wide-i18n-decision.md`](2026-07-20-app-wide-i18n-decision.md)
   owns the localized-surface boundary: the extension popup is explicitly
   English, while durable human-facing health in the web app is localized;
5. the Alpha Picks reconciliation design continues to own comment-continuity
   state and the terminal authority of its Backfill mode; and
6. existing `job_runs` and `sa_capture.db` ownership rules remain in force.

### 1.1 Grounded baseline

At `38178f65`:

- `extensions/sa_alpha_picks/install_firefox.sh` rebuilds
  `build/firefox/` and copies `scrape*.js`, but that glob does not include
  `article_identity.js`;
- `background.js` injects `article_identity.js` before both
  `scrape_articles_list.js` and `scrape_detail.js`;
- the manually repaired current Firefox build contains `article_identity.js`,
  but rerunning the installer would delete the build and omit it again;
- `tests/test_extension_install_paths.py` checks host paths and popup script
  dependencies, but not service-worker injection dependencies or exact build
  contents;
- `classifyExtensionJobOutcome()` marks a result failed only for a thrown
  error or top-level `result.status === 'error'`;
- Market News can therefore return `status='ok'`, `detail_failed=18`, and be
  persisted as `succeeded`;
- `job_runs.status` is constrained to `running`, `succeeded`, or `failed`;
  this unit does not add a fourth database status;
- `JobRunsLocalStore` already supports durable `create_run()` and
  `finish_run()`, so a resumable repair manifest does not require a new
  `sa_capture.db` schema version;
- native-host extension telemetry is a best-effort POST to the sidecar and its
  persistence outcome is currently discarded by the popup;
- Market News routine backfill candidates are restricted by
  `_SA_MARKET_NEWS_BACKFILL_PUBLISHED_WINDOW_HOURS = 24`;
- the visible Market News catch-up budget is 12 current details plus up to 6
  known missing details, with a total cap of 18;
- internal Market News `backfill` still uses the same 24-hour candidate
  predicate, so its larger numeric budget does not make it a historical
  recovery feature;
- `sa_market_news_health` treats the latest database `succeeded` timestamp as
  the extension-health anchor, even when the nested run was degraded or
  skipped;
- Settings already has a localized SA Extension Health panel, but its
  `telemetry_last` segment reports only outer status and the UI deliberately
  ignores backend prose detail; and
- the popup already has one unrelated disclosure,
  `Advanced: specify article URLs`, proving that a native `<details>` pattern
  is available without adding another help page.

### 1.2 Incident target observation is not a constant

The initial incident review described 27 out-of-window Market News rows.
A fresh read-only reconstruction on 2026-07-25 found:

- 25 affected extension runs;
- 450 failure records across those runs;
- 118 unique failed `news_id` values;
- 88 of those IDs now have bodies; and
- 30 of those IDs currently remain without bodies.

This drift is expected after manual and automatic activity and proves why
neither `27` nor `30` may become an acceptance constant. The implementation
must derive a fresh read-only preview, freeze the actual target manifest, and
stop for user approval if the target set differs from reviewed evidence.
Article titles, URLs, bodies, and other licensed content must not be committed
to the repository or ordinary evidence logs.

## 2. Scope

### 2.1 In scope

- a deterministic Firefox packaging step and completeness gate;
- exact dependency discovery for manifest scripts, popup scripts, and every
  literal `chrome.scripting.executeScript({files: [...]})` dependency;
- one structured extension-run result protocol;
- aggregate run outcome derived from phase and item outcomes;
- four-state Market News repair items with stable reason codes;
- persisted, hashed, resumable repair manifests in existing `job_runs` rows;
- routine 24-hour catch-up, recorded-ID retry, and capped incident recovery;
- an honest split between known missing details and newly rediscovered
  metadata;
- grouped, renamed, bounded popup controls with accessible descriptions;
- contextual retry and an Advanced recovery disclosure;
- localized durable degraded health in the existing Settings/System app
  surface, derived from stable codes and counts;
- a fresh, separately approved, audited repair of the remaining incident set;
- Firefox and Chrome regression evidence; and
- documentation and priority-map closeout.

### 2.2 Out of scope

- a server-side Seeking Alpha scraper;
- an embedded browser or migration of the external-extension session into the
  desktop app;
- a generic arbitrary-date Market News backfill;
- a claim that Seeking Alpha exposes every item in a seven-day interval;
- automatic translation or localization of the extension popup;
- a second locale preference in the extension;
- a new `job_runs` status or a `sa_capture.db` schema migration;
- changing Alpha Picks comment-continuity state or Backfill terminal rules;
- changing Market News auto-sync density windows;
- `/sa/feed` missing-database empty-versus-unavailable semantics;
- Settings diagnostic-sanitizer alignment;
- calibration Anthropic-refusal normalization;
- Coverage v2; and
- unrelated popup visual redesign.

## 3. Locked Decisions

1. The implementation order is packaging gate, derived outcomes, recovery
   windows, hybrid popup UI, then the audited incident repair.
2. The packaging gate lands first because every later extension change is
   delivered through the installer it verifies.
3. `job_runs` is the durable repair-manifest and audit owner. `sa_capture.db`
   remains the captured-content owner. Neither duplicates the other's data.
4. `job_runs.status` remains the existing three-value database enum.
   `result.derived_outcome` carries `complete`, `degraded`, `failed`, or
   `skipped`; database status maps from that value.
5. Aggregate status is computed from required phase and item results. Callers
   cannot independently choose a contradictory status.
6. Market News repair items use exactly four states:
   `repaired`, `already_present`, `unavailable_at_source`, and
   `failed_retryable`.
7. Every item state carries a stable reason code. Raw exception prose is not a
   state or a user-facing reason.
8. `unavailable_at_source` requires explicit provider evidence. A trustworthy
   HTTP 404/410, if the transport exposes it, or a reviewed SA removed marker
   qualifies. HTTP 403, paywall, entitlement, login redirect, modal, timeout,
   empty DOM, parser failure, and soft-404 do not qualify.
9. Access restriction remains `failed_retryable` with its own reason code. It
   may be parked until access changes; retryable does not mean hot-looping.
10. A run is derived-complete only when every required phase succeeded and no
    item remains `failed_retryable`.
11. Only a derived-complete, non-skipped Market News sync may become the
    `last healthy run` anchor.
12. Legacy `succeeded` rows without the structured protocol are not
    retroactively trusted as healthy anchors.
13. Routine Catch Up remains 24 hours. It does not silently become a seven-day
    operation.
14. Recorded-failure retry is ID-addressed and has no age cutoff.
15. Incident recovery starts at the latest derived-complete run and ends at
    the current preview time, capped by the named constant
    `MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS = 168`.
16. Seven days is an attempted-recovery bound, not a completeness guarantee.
17. Incident recovery reports existing-metadata detail work separately from
    newly rediscovered metadata. A discovered count is not a claim about the
    total amount missed.
18. The popup keeps five normal controls. Retry appears contextually only when
    recorded retryable failures exist. Low-frequency incident recovery lives
    under Advanced and is promoted into the status area when a real gap is
    detected.
19. Supported synchronization, retry, and repair never require F12. Any
    supported emergency/console entry must call the same audited command and
    cannot bypass manifest creation or terminal recording.
20. The extension popup stays English. The web app owns localized durable
    health prose. Both consume the same stable structured state.
21. Hover, focus, and assistive-technology descriptions share one description
    element per control. A duplicate `title` string is forbidden.
22. The unit does not add `help.html`; the inline disclosure is the complete
    control reference.

## 4. Packaging Completeness

### 4.1 Canonical build step

`install_firefox.sh` must stop hand-maintaining a list of copied runtime
files. A small deterministic build helper owns Firefox assembly:

1. parse `manifest.firefox.json` as JSON and collect every supported local
   asset reference, including background scripts, `action.default_popup`,
   icons, content-script JS/CSS, and web-accessible resources when present;
2. parse each referenced local HTML root for script, stylesheet, image, and
   other shipped local-asset dependencies;
3. parse every literal `files: [...]` array used by
   `chrome.scripting.executeScript()` in `background.js`;
4. reject dynamic or non-literal file construction rather than silently
   omitting it;
5. require every dependency to be a basename inside
   `extensions/sa_alpha_picks/`, with no traversal, query, fragment, or remote
   URL;
6. require every referenced file to exist;
7. build into a temporary directory;
8. inject `compat_firefox.js` into the generated popup exactly once;
9. verify generated manifest and HTML dependency closure;
10. compare the generated file set with the computed runtime dependency
    closure plus the two generated roots (`manifest.json` and transformed
    `popup.html`); and
11. atomically replace `build/firefox/` only after every check succeeds.

The helper may use strict, fixture-tested parsing for the deliberately narrow
classic-script syntax. It must fail when source syntax moves outside that
contract. It must not require Node dependencies or a web-app `npm install` to
run the Firefox installer.

### 4.2 Build invariants

The gate must prove all of the following:

- `article_identity.js` is present because the injection graph requires it;
- deleting or renaming any manifest, HTML, stylesheet, image, popup-script,
  content-script, or injected-script dependency makes the
  build fail before replacing the previous known-good build;
- adding a new literal injected dependency includes it automatically;
- a dynamic `files` expression fails with an actionable build error;
- generated `popup.html` loads `compat_firefox.js` before `popup.js` and does
  not duplicate it;
- stale files cannot survive from an older build;
- the generated manifest references only generated files; and
- the Chrome source-directory load remains valid because the same dependency
  graph is checked against source files.

`tests/test_extension_install_paths.py` evolves from popup-only parity into
the durable packaging contract. The implementation plan may split focused
tests into a new file, but there must remain one command that builds a fresh
Firefox artifact and verifies exact closure.

### 4.3 Installer behavior

The native-host registration behavior remains unchanged. Build failure occurs
before destructive replacement of `build/firefox/` and before reporting a
successful install. The installer prints the failed dependency and exits
nonzero. It never attempts a partial fallback copy.

## 5. Structured Run Outcomes

### 5.1 Protocol shape

Every new Alpha Picks or Market News run returns a versioned structured result:

```json
{
  "schema_version": 1,
  "operation": "market_news_sync",
  "mode": "quick",
  "derived_outcome": "complete",
  "phases": {},
  "counts": {},
  "item_outcomes": []
}
```

Allowed operations are closed and explicit:

- `alpha_picks_sync`;
- `alpha_picks_manual_fetch`;
- `market_news_sync`;
- `market_news_retry_recorded`; and
- `market_news_incident_recovery`.

Unknown operation, schema version, phase state, item state, or reason code
fails validation. The popup may show a fixed protocol-error message; it must
not guess from English text.

### 5.2 Phase states

Required phases use `complete`, `failed`, or `skipped` with stable reason
codes. For Market News these include list navigation, list scrape, metadata
save, detail queue, detail fetch, and final capture readback. For Alpha Picks
these include current picks, closed picks, article metadata, detail/comment
work, and reconciliation readback.

Routine telemetry delivery is not a capture-result phase: its persistence
state is the separate contract in Section 5.5. Repair audit creation and
finalization are lifecycle gates under Sections 6.1 and 6.4, not circular
inputs to the pre-POST capture derivation.

Review-required article links are not failures. A scheduled `not_due` event is
`skipped`, not complete, and cannot advance the healthy anchor.

### 5.3 Four-state Market News item contract

Each repair target has:

```json
{
  "news_id": "stable provider id",
  "state": "failed_retryable",
  "reason_code": "detail_timeout",
  "attempt_count": 1,
  "evidence_code": null
}
```

The closed state meanings are:

| State | Meaning | Terminal for this manifest |
| --- | --- | --- |
| `repaired` | Body was absent at manifest freeze and is present by terminal reconciliation. | yes |
| `already_present` | Body was already present at manifest freeze. | yes |
| `unavailable_at_source` | Explicit provider evidence proves the source item is gone. | yes |
| `failed_retryable` | The target remains unresolved without terminal source evidence. | no |

At minimum, reason-code families include:

- `body_saved`, `body_present_at_freeze`, and `body_present_during_run`;
- `source_http_404`, `source_http_410`, and `source_removed_marker`;
- `access_restricted`, `login_required`, `modal_blocked`,
  `navigation_timeout`, `detail_timeout`, `dom_not_ready`, `parser_empty`,
  `native_host_unavailable`, `detail_save_failed`,
  `extension_dependency_missing`, `interrupted`, and `unknown_failure`.

Run/phase-level reasons additionally include `not_due`,
`operator_cancelled`, `protocol_invalid`, `manifest_invalid`, and
`telemetry_unavailable`. The implementation plan must publish the complete
closed enum; this list is a semantic floor, not permission to accept arbitrary
strings.

State-specific validation rejects incompatible pairs. In particular,
`access_restricted`, `login_required`, `dom_not_ready`, and `parser_empty`
cannot accompany `unavailable_at_source`.

### 5.4 Derived aggregate rules

One pure derivation function consumes phases and item outcomes:

- `complete`: every required phase is complete, every item is terminal, and
  `failed_retryable_count == 0`;
- `degraded`: required list/metadata work completed, but one or more detail
  items are `failed_retryable`, or a nonfatal required readback failed;
- `failed`: a required list/navigation/save/protocol/manifest phase failed;
- `skipped`: no capture work was due or admitted.

Database mapping is fixed:

| `derived_outcome` | `job_runs.status` | Healthy anchor eligible |
| --- | --- | --- |
| `complete` | `succeeded` | yes, only for a real sync |
| `degraded` | `failed` | no |
| `failed` | `failed` | no |
| `skipped` | `succeeded` plus typed skipped result | no |

The extension request no longer controls persisted status independently. The
sidecar derives or validates the mapping from the structured result and
rejects a contradiction. The popup and sidecar derivations use the same
fixture corpus so cross-language behavior cannot drift.

Mapping `degraded` to database `failed` is deliberate. Before implementation,
the plan must inventory `/jobs/status`, `/jobs/history`, health summaries,
failure counters, alerts, and scheduler/backoff consumers. It must prove that
extension-pushed rows do not accidentally enter scheduler retry/backoff
control, and it must explicitly evolve every display/count that previously
treated all `failed` rows as equivalent.

Alpha Picks is included in aggregate derivation even though its item-level
historical repair remains outside this unit. `details.failed > 0`, a detail
error, a failed required current/closed scope, or reconciliation persistence
failure can no longer produce a green extension run.

### 5.5 Telemetry persistence is visible

Routine capture remains allowed when the sidecar telemetry POST is
unavailable, but the popup must retain and display the persistence result:

- `persisted`: durable `job_runs` row exists;
- `pending`: terminal record is queued locally for a bounded retry; or
- `unavailable`: persistence failed and no durable audit exists yet.

The telemetry payload is stored in a bounded `chrome.storage.local` outbox
before native messaging. It is removed only after the sidecar confirms the
recorded run ID. Startup, popup open, and the next extension job retry pending
records idempotently. Each record has a stable client-generated event ID so a
retry cannot duplicate `job_runs` history. The sidecar endpoint deduplicates
that event ID.

No uniqueness schema is added for this. The local `job_runs` owner performs
event lookup and insert in one `BEGIN IMMEDIATE` transaction, matching the
canonical event ID stored in `payload`; a duplicate returns the existing run
ID without inserting. This is a new atomic store operation, not a
`list_runs()`-then-insert race. If implementation grounding proves that exact
transactional contract cannot be provided by the active local store, this
design stops for amendment rather than weakening idempotence or adding an
unreviewed schema change.

Outbox failure never changes the derived capture outcome. The popup shows both
facts, for example `capture complete / audit pending`; the run cannot become a
durable healthy anchor, while the web health surface naturally remains stale
until the record lands. The outbox has a bounded count/age policy recorded in
the implementation plan; eviction is itself surfaced, never silent.

Audited repair is stricter than routine capture: if a durable running
`job_runs` row cannot be created, the repair does not start.

## 6. Durable Repair Manifest

### 6.1 Existing storage, no new schema

Repair uses a dedicated job name, `sa_market_news_repair`. Starting a repair
creates one `job_runs.status='running'` row through the sidecar-owned API.
`payload` contains the immutable input manifest; `result` contains terminal
item outcomes and discovery results. `sa_capture.db` stores only the bodies
and metadata it already owns.

The native host continues not to open `profile_state.db`. It proxies the
domain request to the sidecar, preserving the established app-state write
boundary.

### 6.2 Canonical manifest and hash

The immutable manifest contains:

- protocol and algorithm versions;
- repair kind: `recorded_failures` or `incident_window`;
- canonical interval when applicable;
- sorted initial targets containing only `news_id`, canonical SA pathname,
  published timestamp, and baseline body-presence bit;
- source failure run IDs for recorded-failure repair;
- discovery limits and stop rules for incident recovery; and
- the named 168-hour cap.

The SHA-256 manifest hash covers canonical JSON of those fields. It excludes
run ID, creation timestamp, progress, and terminal outcomes. URLs are reduced
to validated `https://seekingalpha.com` pathnames with no query, fragment,
credentials, or alternate host.

The response and `job_runs.payload` expose `run_id`, `manifest_hash`, target
count, and scope counts, but ordinary UI and logs do not expose titles or full
URLs.

### 6.3 Resumption and concurrency

At most one Market News repair row may be running. Starting another returns
the existing run ID and manifest rather than creating a competing operation.
The popup offers Resume for that row. Running-row lookup and conditional
creation occur in one `BEGIN IMMEDIATE` store transaction; a
`list_runs()`-then-`create_run()` check is forbidden because two callers could
both pass it.

After browser or sidecar interruption, resumption uses the same run ID and
manifest hash. It re-reads current body state and skips already-satisfied
targets without changing the original baseline. A body absent at freeze but
present at terminal reconciliation is `repaired`, even if another normal run
filled it during the interruption.

Cancel is explicit and terminalizes the run as failed with
`operator_cancelled`; closing the popup does not cancel background work.
An old running row is never auto-promoted to success. Startup reconciliation
may mark it interrupted/retryable while preserving its manifest for Resume.

Normal Market News sync and repair share one extension-side mutex. Neither can
interleave tab navigation with the other.

### 6.4 Finalization

The sidecar validates that every frozen target has exactly one final outcome,
rechecks current body presence, derives counts and aggregate outcome, computes
a result hash, then calls `finish_run()` once. Missing item results become
`failed_retryable/interrupted`; they are never omitted.

A repair is persisted as `succeeded` only when every target is terminal. Any
remaining `failed_retryable` item makes the row `failed` with
`derived_outcome='degraded'`. This preserves retryability while keeping the
database enum unchanged.

## 7. Three Recovery Layers

### 7.1 Routine current sync

`Sync Latest News` keeps the existing recent-list behavior: three list scrolls
and up to 18 current-list detail fetches. It does not search historical missing
details.

### 7.2 Routine 24-hour catch-up

`Catch Up News (24h)` keeps the existing bounded split:

- up to 12 current-list details;
- up to 6 known missing details whose published/fetched timestamp is within
  the last 24 hours;
- unused current quota may be reassigned under the existing total cap; and
- total detail attempts remain at most 18.

The label contains `24h`, and its description states that it does not repair
older details or prove interval completeness.

### 7.3 Retry recorded failures

`Retry Recorded Failures` operates on the exact `news_id` values in the latest
structured retryable result (or a separately frozen reviewed historical run
set). It has no age predicate. Before starting, the popup states:

```text
N recorded IDs; no time-window cutoff
```

The control appears only when at least one unresolved ID exists. If all IDs
are already satisfied, the preview states that fact and does not create a
no-op run.

### 7.4 Incident recovery, capped at seven days

Incident recovery derives:

```text
start = latest derived-complete Market News sync
end   = preview timestamp
start = max(start, end - 168 hours)
```

If no derived-complete run exists after protocol activation, Advanced may
preview the trailing 168 hours but must say that no verified healthy anchor
exists. It cannot imply that an older interval is covered.

The UI displays the actual interval and duration, for example:

```text
Attempt recovery: 2026-07-19 11:30 -> 2026-07-20 17:40 (30h 10m)
```

It does not display only `up to 7 days`.

The incident operation has two independent legs:

1. **Known detail repair**: metadata exists locally and body is missing. These
   are ID-addressable frozen targets.
2. **Metadata rediscovery**: the list scanner attempts to reach the interval
   start and records newly discovered metadata. Its stop evidence includes
   reached-window-start, stable/no-growth rounds, source-bottom evidence,
   elapsed time, and hard caps.

Preview reports the exact known-detail candidate count. Metadata absent from
the local DB is unknowable before source discovery and is shown as unknown,
not zero. Terminal results separately report:

- initial known-detail targets;
- repaired/already-present/unavailable/retryable detail counts;
- newly discovered metadata count;
- newly discovered items whose detail was saved;
- whether the scanner reached the requested interval start; and
- the unresolved interval, if any.

`newly_discovered_metadata_count` means only what this bounded attempt found.
It is never labeled total missing metadata. If the source does not expose the
requested depth, the run may finish its known target set but remains honest
about incomplete discovery.

### 7.5 Zero-candidate behavior

The preview treats ID targets and discovery work as separate executable
scopes:

- recorded-failure retry with zero unresolved IDs starts no run;
- incident recovery with zero known IDs but a nonempty unverified interval is
  not a zero-work operation: the preview says `0 known IDs`, shows the exact
  discovery interval, and requires confirmation before running bounded
  rediscovery; and
- only when both the known-ID set is empty and there is no discovery scope
  does the popup state `No recovery work found` and start no run.

If an admitted discovery run finds no new metadata, that is a real audited
attempt, not a no-op. Its terminal result reports zero discoveries plus the
scanner's reach/stop evidence and any unresolved interval. It may not claim
that the interval contained no missing items.

## 8. Popup Information Architecture

### 8.1 Normal controls

The popup groups controls by function:

**Alpha Picks**

1. `Quick Update`
2. `Full Article Scan`
3. `Deep Repair Scan`

**Market News**

4. `Sync Latest News`
5. `Catch Up News (24h)`

Auto-sync controls remain under their respective group. The existing article
link review and `Advanced: specify article URLs` remain owned by Alpha Picks
reconciliation and do not move into Market News recovery.

### 8.2 One description owner per control

Each normal button has one description element. The button references it with
`aria-describedby`. The same element becomes visually available on pointer
hover and keyboard focus. There is no duplicate `title` copy.

Touch and persistent-reference needs are served by the inline
`What these actions do` disclosure. Its table contains:

- action;
- exact scope and current hard bounds;
- when to use it; and
- a required `Does not guarantee` statement.

The description and table derive from one presentation action catalog, so
button labels, accessible descriptions, and disclosure rows cannot drift.
Fixed extension limits live in that catalog. Native configuration values,
including the Full/Deep comment-recovery batch caps, arrive as structured
numeric action-limit fields and are interpolated into the same rows. If those
values are unavailable, the popup says `configured limit unavailable`; it
does not silently substitute a default and present it as the active value.

### 8.3 Required action semantics

| Action | Scope | Does not guarantee |
| --- | --- | --- |
| Quick Update | Current/closed picks; five article-list load rounds; all normal missing-body and changed-count work returned by that scan, with no separate global Alpha article-detail cap; at most 4 extra reconciliation-enrichment items; each comment scan capped at 12 scrolls/12 seconds. | Full article history, a fixed request budget, or complete comments. |
| Full Article Scan | Current/closed picks; available article list up to 200 load rounds; all normal detail work returned by that scan, with no separate global Alpha article-detail cap; at most 12 extra reconciliation-enrichment items; each comment scan capped at 80 scrolls/60 seconds; configured additional recovery batch shown at runtime (default 10), excluding parked pending rows. | Lifetime completeness or terminal treatment of unreachable comment history. Runtime grows with the returned work set. |
| Deep Repair Scan | Current/closed picks; available article list up to 200 load rounds; all normal detail work returned by that scan, with no separate global Alpha article-detail cap; at most 20 extra reconciliation-enrichment items; each comment scan capped at 140 scrolls/120 seconds with five stable-bottom rounds; configured additional recovery batch shown at runtime (default 50), including parked pending rows. | Market News repair, a fixed request budget, or every historical comment. This is the deepest and potentially longest Alpha Picks action. |
| Sync Latest News | Three list scrolls and up to 18 current-list details. | Older missing details. |
| Catch Up News (24h) | Three list scrolls, 12 current details plus up to 6 known missing details within 24 hours, total cap 18. | Details older than 24 hours or interval completeness. |

The implementation plan must verify these values against source constants and
the native configuration projection. It must also prove that the Market News
`18/30/80` budgets are not rendered as Alpha Picks bounds. If behavior
changes, the action catalog and tests change in the same reviewed commit. Copy
must not silently outlive the limits it describes.

### 8.4 Last-run status and contextual actions

Alpha Picks and Market News each have a last-run region. It displays:

- operation and mode;
- time;
- derived outcome;
- meaningful phase/item counts;
- telemetry persistence state; and
- stable reason labels for degraded/failed results.

The region uses `role='status'` for ordinary completion and an appropriate
alert role only for a newly actionable failure. Reopening the popup does not
reannounce stale history.

Market News displays `Retry Recorded Failures` beside a real retryable count.
It does not render a disabled or no-op retry button when no failures exist.

When a gap longer than 24 hours is derived, the status area displays the exact
gap and an action that opens/focuses the Advanced recovery preview. It does
not duplicate the recovery command implementation.

### 8.5 Advanced recovery tools

`Advanced recovery tools` is collapsed by default. It contains:

- the incident interval preview;
- known target count;
- metadata-discovery limitation;
- current active/resumable repair state;
- `Recover Missed News` only when a nonzero or discoverable scope exists; and
- a confirmation step that repeats scope, limits, and non-guarantees.

The disclosure is not persisted. Opening it performs a read-only preview.
Preview failure shows a stable reason and does not start work.

No arbitrary date-range input ships. A future range picker requires a new
reviewed decision because it would imply provider-history knowledge this unit
does not have.

### 8.6 Console boundary

There is no console-only product operation. Public background actions for
retry or recovery always create or resume the durable manifest first. An
emergency operator wrapper, if retained for diagnostics, invokes that same
action and returns the same run ID/hash. Lower-level unaudited functions are
not exposed through runtime messages.

## 9. Durable Web Health

### 9.1 Structured state, localized prose

The extension popup owns immediate English prose. The web app owns durable
localized health prose. Both consume stable codes and counts, not each
other's sentences.

`GET /sa/extension-health` evolves its telemetry segment to expose sanitized
structure such as:

```json
{
  "key": "telemetry_last",
  "state": "warn",
  "code": "detail_failures_recorded",
  "counts": {"failed_retryable": 18, "attempted": 18},
  "run_id": 16417,
  "occurred_at": "2026-07-19T11:45:38+00:00"
}
```

Backend prose detail is not rendered by the web app. Settings maps the closed
codes through bilingual resources and shows the relevant counts. Unknown
codes fail closed to a generic localized warning. Developer Mode may expose
only a bounded stable code that passes the new health presenter's identifier
validation; arbitrary backend detail is not admitted to this surface. The
separate backlog to align older Settings diagnostics with the newer
fail-closed sanitizer remains outside this unit.

### 9.2 Healthy-anchor correction

`sa_market_news_health` no longer calls any database `succeeded` row a healthy
extension run. It selects the latest structured `market_news_sync` whose
`derived_outcome` is `complete` and whose trigger was not skipped.

Before the first such run, capture-side timestamps remain visible but the
extension-run signal is unavailable/unverified. Legacy rows are not rewritten
or inferred complete.

Provider Health applies the same rule when deriving Seeking Alpha last
success. A degraded detail run updates last attempt and warning state but not
last success.

### 9.3 Recovery visibility

Durable health reports:

- latest derived-complete sync;
- latest actual run and its derived outcome;
- unresolved retryable detail count when observable;
- active/resumable repair run ID and manifest hash prefix;
- last repair terminal counts; and
- telemetry unavailable/pending state where known.

The web app does not execute extension repair because browser login/session is
extension-owned. It may direct the user to open the extension popup. It does
not duplicate popup action copy.

## 10. Historical Incident Repair

### 10.1 Fresh preview and approval

The historical repair is a production-data operation performed only after the
product implementation is merged and verified. Before repair:

1. stop extension auto-sync and any competing SA capture;
2. create retained 0600 SQLite online backups of `sa_capture.db` and
   `profile_state.db`;
3. reconstruct affected failed IDs from the reviewed incident run range;
4. compare each ID with current body state;
5. write a redacted preview containing counts, run IDs, interval, and manifest
   hash, but no titles, bodies, or full URLs;
6. report the fresh target count to the user; and
7. obtain explicit approval of that exact hash/count.

The earlier `27` and current read-only `30` observations are historical
evidence only. Any fresh count is acceptable if the derivation is explained;
unexplained drift is a stop condition.

All 450 historical failure entries currently carry only the generic legacy
value `detail_not_saved`. That value is evidence that an attempt failed, not
evidence for any four-state outcome or modern reason code. Preview and repair
must re-evaluate each target; they may not infer `unavailable_at_source`,
access restriction, or another terminal classification from the old prose.

### 10.2 Execution

The approved set runs through `market_news_retry_recorded` using the same
durable manifest path as future repairs. It is not a special console script
with a different outcome model.

This historical manifest is an exact recorded-ID repair and therefore has no
age predicate. `MARKET_NEWS_INCIDENT_RECOVERY_MAX_HOURS = 168` applies only to
interval rediscovery; it must not filter, truncate, or silently omit IDs in
the approved historical manifest.

The repair may proceed in bounded resumable batches, but every batch references
the same parent manifest hash and finalization covers every target. Browser
closure or sidecar loss leaves a resumable running record, not a synthetic
success.

### 10.3 Terminal evidence

Closeout reports each target as exactly one of the four states with a reason
code, plus aggregate counts derived from those rows. Licensed source content
stays out of committed evidence.

The terminal evidence includes:

- approved manifest hash and result hash;
- target count and four-state counts;
- exact opaque IDs in the durable audit row, while committed evidence uses
  stable redacted hashes only;
- explicit source-unavailable evidence codes;
- `job_runs` run ID/status/derived outcome;
- pre/post body-presence count for the target set;
- database integrity/FK checks; and
- idempotent replay showing no duplicate rows or altered body for already
  present targets.

An unresolved item is an honest repair result. The run is not relabeled
complete merely to close the incident.

## 11. Verification Contract

### 11.1 RED-first layers

The implementation plan must provide explicit node accounting and RED-first
coverage for:

1. packaging dependency discovery and exact build closure;
2. missing `article_identity.js` reproduction;
3. dynamic injection dependency rejection;
4. item-state/reason validation;
5. aggregate derivation, including `detail_failed > 0`;
6. JS/Python fixture parity for persisted status mapping;
7. telemetry outbox idempotence and visible failure;
8. durable manifest hash, duplicate-start, resume, cancel, and finish;
9. 24h/recorded-ID/168h window boundaries;
10. last-derived-complete health selection;
11. popup action catalog, grouping, descriptions, resolved native limits,
    Alpha no-global-detail-cap disclosure, and Advanced behavior;
12. localized Settings degraded health without raw backend prose; and
13. incident preview/apply proof on copied databases before production.

### 11.2 Adversarial outcome fixtures

Fixtures must include:

- top-level `ok` with 18 retryable detail failures;
- partial success with repaired and failed targets;
- paywall/403/login/modal/timeout/empty DOM/parser failures;
- explicit 404/410/removed evidence;
- incompatible state/reason pairs;
- skipped auto-sync;
- legacy unstructured succeeded rows;
- telemetry POST failure and duplicate retry;
- interruption after some bodies were saved but before job finalization;
- zero recorded IDs with no discovery scope;
- zero known IDs with a nonempty discovery scope;
- an admitted discovery attempt that finds zero new metadata;
- an interval older than 168 hours;
- scanner unable to reach the requested interval start; and
- unknown protocol/reason values.

### 11.3 Popup interaction gate

Run mounted Chrome and Firefox popup gates proving:

- five normal buttons, grouped 3+2;
- exact labels;
- no sixth permanent recovery button;
- each button's hover and keyboard focus reveal the same described element;
- every button has one valid `aria-describedby` target and no `title` copy;
- disclosure scope/non-guarantee rows exist for all five actions;
- contextual Retry appears only with retryable IDs;
- Advanced recovery is collapsed normally and promoted from a real gap;
- confirmation repeats the actual interval, known-ID count, and discovery
  scope;
- zero-executable-scope preview starts no job;
- active repair resumes the same run ID/hash;
- popup close/reopen preserves active background work and last-run truth;
- long English descriptions wrap without clipping at the shipped popup width;
- keyboard order, focus restoration, Escape/browser-popup behavior, and
  screen-reader names remain coherent; and
- no supported flow requires DevTools.

An element-level clipped-text census is required. Document-level overflow
alone is insufficient because I18N-6 proved that fixed-width children can
clip while the document remains bounded.

### 11.4 Runtime reliability gate

Against isolated DB copies and a fresh Firefox build:

1. prove the build contains every computed dependency;
2. run a healthy quick sync and observe derived-complete telemetry;
3. inject one detail failure and observe failed DB status plus degraded
   structured result;
4. prove last healthy does not advance;
5. remove the fault, invoke contextual retry, and prove it targets the exact
   ID without a time cutoff;
6. interrupt and resume a repair under the same run ID/hash;
7. run a 30-hour incident preview and prove the displayed range is 30 hours,
   not a generic seven-day label;
8. run a greater-than-seven-day preview and prove the 168-hour cap and
   unresolved older interval;
9. prove known-detail and metadata-rediscovery counts remain separate;
10. break telemetry and prove capture stays usable while popup/web health are
    honest; and
11. restore telemetry and prove outbox replay is idempotent.

### 11.5 Protected boundaries

Unless a reviewed implementation-plan amendment says otherwise:

- no new dependency;
- no `sa_capture.db` or `profile_state.db` schema change;
- no Market News auto-sync cadence change;
- no Alpha Picks comment-state transition change;
- no extension localization or locale IPC;
- no `/sa/feed` semantic change;
- no source/generated content in app resources;
- no title/body/full URL in committed evidence;
- no server-side SA request; and
- no unrelated web-app IA or CSS change.

Popup CSS may change only for the grouped controls, shared descriptions,
status region, and disclosures authorized here. Any broader visual change is a
stop-and-amend event.

## 12. Expected File Ownership

### Extension and packaging

- `extensions/sa_alpha_picks/install_firefox.sh`
- `extensions/sa_alpha_picks/background.js`
- `extensions/sa_alpha_picks/popup.html`
- `extensions/sa_alpha_picks/popup.js`
- one new deterministic Firefox build helper under
  `extensions/sa_alpha_picks/`
- existing scraper files only if a stable removed-source evidence marker must
  be emitted; otherwise byte-identical

### Backend and health

- `src/sa_native_host.py`
- `src/api/routes/jobs.py`
- `src/api/routes/seeking_alpha.py`
- `src/service/job_runs_store.py` only for idempotent client-event recording or
  running-repair lookup, not schema changes
- `src/service/sa_extension_health.py`
- `src/service/sa_market_news_health.py`
- `src/service/provider_health.py`
- `src/tools/data_access.py`
- `src/tools/backends/sa_capture_backend.py` only for read/query support needed
  by recovery preview and final reconciliation

### Web app

- `apps/arkscope-web/src/api.ts`
- `apps/arkscope-web/src/settings/DataSourcesSection.tsx`
- Settings copy/presenter/resource owners needed for structured localized
  health
- no extension popup strings in app resources

### Tests and docs

- `tests/test_extension_install_paths.py` and focused packaging fixtures
- existing extension/background fixture harness or a bounded new fixture
- `tests/test_job_runs.py`
- `tests/test_sa_native_host_telemetry.py`
- `tests/test_sa_extension_health.py`
- `tests/test_sa_market_news_health.py`
- `tests/test_sa_tools.py` / backend tests as required
- focused web Settings/API/resource tests
- this design, implementation plan, evidence ledger, priority map, and SA
  roadmap

The implementation plan must refine this map after test-layer grounding.
Unexpected product owners are a stop condition, not an implicit scope grant.

## 13. Implementation Sequence

### Stage 1: Packaging gate

- add RED fixtures reproducing the missing dependency;
- add deterministic build helper;
- route Firefox installer through it;
- verify fresh build and exact file closure; and
- record a packaging checkpoint before changing runtime behavior.

### Stage 2: Derived outcomes and observability

- define structured result protocol and fixtures;
- derive aggregate outcomes;
- make sidecar persistence validate/derive status;
- add idempotent telemetry event IDs/outbox;
- correct last-healthy selection; and
- render localized durable health.

### Stage 3: Recovery model

- add durable running manifest lifecycle;
- add recorded-ID preview/retry;
- add 24h and 168h boundary tests;
- add bounded interval rediscovery and dual-axis results; and
- prove resume and terminal reconciliation.

### Stage 4: Popup clarity

- group and rename five controls;
- establish one action catalog;
- add shared hover/focus descriptions and inline disclosure;
- add last-run structured state;
- add contextual Retry and Advanced recovery; and
- run Chrome/Firefox accessibility and clipping gates.

### Stage 5: Incident repair

- merge only after independent implementation review and user approval;
- create backups and fresh preview;
- obtain approval of exact manifest hash/count;
- run through the shipped audited repair path;
- verify terminal evidence; and
- close the historical incident without converting unresolved items to
  success.

## 14. Stop Conditions

Stop and amend this design or plan if:

1. dependency discovery cannot enumerate every runtime script without a
   hand-maintained silent fallback;
2. a fresh Firefox build requires Node/npm state not declared by the installer;
3. repair requires a new database table or schema version;
4. the sidecar cannot durably create/resume a running repair row;
5. persisted status can still be supplied independently of item/phase truth;
6. any paywall, 403, login redirect, empty DOM, or soft-404 is classified
   `unavailable_at_source`;
7. last healthy still reads generic `last_success_at` without protocol
   validation;
8. routine Catch Up exceeds 24 hours;
9. incident recovery accepts arbitrary user dates;
10. UI or telemetry claims metadata completeness from a bounded rediscovery
    attempt;
11. zero executable scope creates a successful no-op repair run, or zero known
    IDs suppress a real nonempty discovery scope;
12. a supported recovery path bypasses audit or requires F12;
13. popup and web app maintain competing prose as the canonical explanation of
    one condition;
14. repair starts while audit persistence is unavailable;
15. fresh incident preview drift cannot be explained;
16. licensed content would enter committed fixtures/evidence;
17. Alpha Picks continuity transitions change;
18. extension locale authority or localization enters scope; or
19. an unexpected product/CSS/backend owner must change.

## 15. Acceptance Checklist

- [ ] A fresh Firefox build cannot omit `article_identity.js` or any other
      manifest/popup/injection dependency.
- [ ] Failed build leaves the previous known-good build intact.
- [ ] Structured outcomes and reason codes are closed, validated, and
      fixture-parity tested.
- [ ] `detail_failed > 0` cannot coexist with persisted `succeeded`.
- [ ] Alpha Picks nested failure counts also cannot hide behind success.
- [ ] Paywall/403/login/modal/timeout/parser/soft-404 remain retryable, not
      source-unavailable.
- [ ] Aggregate status is derived only from phase/item truth.
- [ ] Last healthy means latest real derived-complete sync, never generic
      `succeeded` or `skipped`.
- [ ] Routine Catch Up remains visibly and mechanically 24h-bounded.
- [ ] Recorded-ID retry has no age cutoff.
- [ ] Incident recovery displays the actual interval and caps it at 168 hours.
- [ ] Known missing details and rediscovered metadata are separate result axes.
- [ ] Zero recorded IDs start no retry; zero known IDs do not hide a real
      metadata-discovery interval.
- [ ] Rediscovery never claims total interval completeness.
- [ ] Repair manifests are immutable, hashed, resumable, and terminally
      audited in `job_runs`.
- [ ] Any unresolved item prevents complete status.
- [ ] Routine telemetry failure is visible and replayed idempotently.
- [ ] Repair does not start without durable audit persistence.
- [ ] Popup has five normal controls grouped 3+2 with the approved labels.
- [ ] Every normal control has one accessible description owner and one
      explicit non-guarantee.
- [ ] Contextual Retry exists only for real recorded failures.
- [ ] Advanced incident recovery is normally collapsed and automatically
      surfaced when relevant.
- [ ] No arbitrary range picker or sixth permanent recovery button ships.
- [ ] No supported workflow requires F12; emergency wrappers use the same
      audited command.
- [ ] Web health renders stable structured state through bilingual resources.
- [ ] Popup remains explicitly English with no second locale authority.
- [ ] Fresh incident target N/hash is separately approved before production
      repair.
- [ ] Production repair produces four-state per-item evidence, integrity/FK
      checks, and idempotent replay proof without committing licensed content.
- [ ] Calibration refusal, `/sa/feed` semantics, Settings sanitizer, Coverage
      v2, and other standing backlogs remain outside this unit.
