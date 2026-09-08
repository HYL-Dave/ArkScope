# Lifecycle Investigation Completion Review

Status: implementation, final offline verification and all three source-bound
Claude OAuth live controls are complete for review. The final backend passes
7,114 tests, frontend 1,633, and all 31 mutation owners fail with green restored
baselines. After the measured quota reset, a new explicitly selected Opus 5
Web-TA run succeeds; it does not resume or silently switch the failed Sonnet run.
Earlier live failures and test-only module-load/contention diagnostics are
retained, not replaced with a successful rerun claim.
There is no production installation, legacy-row deletion, App restart,
merge or push in this delivery. Earlier sealed evidence remains immutable.

Review index: [verification](completion-r1/verification.json),
[source manifest](completion-r1/source-manifest.json),
[test-node changes](completion-r1/node-changes.json) and
[file hashes](completion-r1/files.sha256.json). The create-only producer verifies
these inputs independently before publishing its final hash manifest.

## Product Scope

- Investigations start from a tracked ticker, not an old SEC case or SA pick.
- Saved Massive/EODHD/listing observations are shown first. An explicit source
  check and a source-confirmed removal/rename review need no LLM credential.
- The independent `lifecycle_investigation` task has its own model route and
  profile-backed whole-run Settings. Existing Research, card generation and
  Content Translation routes are unchanged.
- A bounded adaptive agent can search/read local collected news, search the Web,
  follow public originals and inspect retained passages. SEC is an optional,
  lower-priority supplement, not a mandatory filing sweep.
- The result is a concise finding with cited passages, source timing and gaps.
  Announced acquisitions, debt events and trading suspensions are not ordinary
  stock delistings. Same-security renames do not move tracking to an acquirer.
- No LLM finding applies itself. Human confirmation uses the existing atomic
  transition writer, preserving historical prices/news/SA records and requiring
  fresh identity, affected-state and open-position checks.
- Tracking history supports separate acknowledgement and confirmed reversal.
  Later changes to the affected state can block reversal; unrelated ticker edits
  do not. Reopening an adopted finding never offers it as a new action.

## Bounds And Authentication

Defaults are 24 model submissions, 24 native Web actions, 32 source reads,
96 HTTP attempts, 20 local queries, 1,800 seconds per investigation and
600 seconds per model submission. Limits are cumulative across all follow-ups,
configurable, and not a quota the agent must spend. Source reads admit up to
32 MiB transmitted / 128 MiB decoded content; retained source text defaults to
512 MiB per run. This does not claim to enforce a Python process RSS limit.

All four existing auth adapters share the investigation contract. API output
limits are model-bound; OAuth output is explicitly provider-controlled. Exact
selected models, credentials and billing channels are preserved. An auth,
transport or quota failure does not retry through another model, key or channel.
Correcting a completed but invalid finding is an explicit subsequent agent step
inside the same run budget, not a hidden transport retry.

Only Claude OAuth is authorized for this round's live acceptance. The other
three channels have offline tests; their full-agent live behavior is not claimed
from Claude's results. Earlier failed calibrations are retained alongside any
later successes, including the measured five-hour quota rejection.

## Verification

Final offline acceptance passes **7,114 backend tests / 12 skipped** and **1,633 frontend
tests**. The skips are the existing manual SEC/IBKR live tests, not investigation
failures. Typecheck and the production build pass; the three existing package
deprecation warnings and Vite chunk-size warning remain.

The 31 named negative mutations run individually against all 2,675 backend focus
nodes or all 1,633 frontend nodes, with green baseline/restored checks and
independently verified original/copy source hashes across 25 copied workspaces.
Mutation coverage is a named sample of important contracts, not an exhaustive
proof of all guards.
Frontend baseline/mutant/restored suites use one worker and unchanged test
timeouts; the command is recorded with each result. No test is skipped to avoid
the earlier shared-host contention failures.

The definition-removal mutant produces eight direct named failures and nine
expected setup assertions in route fixtures that require a successful finding.
Those nine are not hidden or relabelled as passing tests: the packet admits only
their exact nodes, assertion and originating fixture, while every other mutant
must have zero setup errors. The report producer has a separate replayable check:
one positive case and seven negative cases reject altered nodes, exceptions,
assertions, fixture provenance, missing errors/owners and another mutant name.
Unmutated and restored baselines have zero failures or setup errors.

The previous independent-task packet's 205 sealed files are unchanged. Relative
to that packet, backend nodes increase by 133 with none removed. Frontend adds
25 nodes and deliberately replaces two old Universe navigation owners with
independent-target and investigation-Settings equivalents. Locale and Settings
navigation remain covered; these are not unexplained missing tests.

The browser exercise uses the real API, strict client parsers and atomic writer
with temporary stores and synthetic model replies. Both languages are checked at
1440, 390 and 320 pixels. It covers reload without redispatch, cancel, incomplete
findings, Settings save, source-gap acknowledgement, explicit execution dates,
provider-only review without an LLM, real tracking changes and both reversal
paths. It makes no provider requests.
All six locale/viewport scenarios pass, producing 96 screenshots.

### Successful Pre-Definition-Repair Claude OAuth Controls

Each control binds the same 55 execution-source files at that checkpoint, before
the definition-scoping correction. Init and aggregate model usage contain only `claude-sonnet-5`,
and every init records the literal `apiKeySource=none`. The tests make no
production tracking changes and never switch a model, credential or billing
channel after failure.

| Control | Result | SDK submissions | Native Web actions | Source HTTP attempts | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Local-news TA | Completed common-stock trading end; removal review available | 3 | 0 | 0 | 52.213 |
| Public-Web TA | Completed common-stock trading end; removal review available | 14 | 4 | 5 | 367.307 |
| Active SMCI | Active common-stock listing; no tracking action | 15 | 4 | 5 | 240.670 |

The local-news case replays the previously captured original public notice
through the real normalized local-news reader; it is not a new provider
observation. The Web case actually searches and reads public originals. Its
final result cites an SEC filing after a BP URL failed, and retains that source
gap. SEC was not mandatory: the earlier Web calibration succeeded from BP's
notice alone. The final active control correctly keeps SMCI tracked.

### Current Source-Bound Controls

| Control | Exact selected model | SDK submissions | Native Web actions | Source HTTP attempts | Seconds |
| --- | --- | ---: | ---: | ---: | ---: |
| Local-news TA | `claude-sonnet-5` | 1 | 0 | 0 | 13.434 |
| Public-Web TA | `claude-opus-5` | 4 | 5 | 1 | 131.333 |
| Active SMCI | `claude-sonnet-5` | 7 | 2 | 2 | 80.113 |

All three bind the same current 55 execution files. Their 12 init records contain
the exact selected model and literal `apiKeySource=none`; aggregate model usage
matches each selection. Local-news TA uses one real normalized local search/read
of the captured public notice with no Web/HTTP call. Active SMCI keeps common
stock distinct from SMCIP preferred shares and proposes no action.

Web TA actually searches and reads a public SEC 8-K, confirming completed
common-stock trading cessation dated 2023-05-15, not merely a merger announcement.
The finding also cites conversion of the shares into cash rights. It explicitly
retains the lack of a separate Nasdaq notice or subsequent OTC-record check;
this is a one-original-source finding for human review, not a claim of new
multi-provider consensus. SEC is an available original, not a mandatory source.
The earlier 16-submission Sonnet Web run remains a quota failure with no action;
the final Opus run is a separately selected new run after the observed reset.

### Calibration History

All fifteen authorized runs are retained, including six failures. They consumed
**161 SDK submissions**: 156 Sonnet and five explicitly selected Opus submissions.
The three current successful controls account for twelve. Six earlier successes
are genuine observations but do not replace final-source acceptance.

| Earlier runs | Submissions | Outcome |
| --- | ---: | --- |
| Two initial TA runs | 24 + 24 | Incomplete at the run budget |
| Sonnet and separately selected Opus | 19 + 1 | Five-hour quota rejection; no fallback |
| First local-news replay after recovery | 7 | No-progress stop; host selection/feedback defect |
| Intermediate local TA / Web TA / active SMCI | 3 + 7 + 16 | Successful, but superseded by the final source-bound trio |
| Pre-definition local TA / Web TA / active SMCI | 3 + 14 + 15 | Successful; retained and independently revalidated offline after the definition repair |
| Current local TA / active SMCI | 1 + 7 | Successful on the current execution manifest |
| Current Web TA | 16 | Five-hour quota rejection; no final action |
| Final Web TA, explicitly selected Opus after reset | 4 | Successful on the current execution manifest |

Calibration exposed real host defects, not missing public evidence: a short
notice had 262 HTML fragments and its initial 12 omitted the decisive event;
useful read-query/date-hint arguments were rejected; error feedback displaced
already-discovered URLs and grounded candidate details. RED tests now own
complete short-notice selection without changing citation IDs, consumed query
arguments, honest publication-date hints and durable correction context.

The SMCI control additionally exposed a nominal-value qualifier being mistaken
for a separate share class. Normalization now removes only that qualifier;
Class A/B, preferred shares and debt remain distinct. Original source wording
is preserved. The final responses also use the requested language explicitly.

The interrupted mutation baselines and earlier verification numbers remain
documented in the completion plan. None substitutes for the final campaign.

Further review reproduced a definition-scoping defect: `Company`, `Exchange`,
another instrument's `Securities`, or another share class's `Shares` could borrow
a common-stock identity. The repaired helper accepts only an explicit alias
directly qualified by the exact class description, optional nominal value and
exact venue. Eight negative RED cases and eight positive controls cover both
active and ended events. The three successful findings above also pass offline
revalidation under this rule. Current local, active and Web controls all pass;
older source revisions are still labelled as calibrations, not final acceptance.

## Isolated Preview

The review server is `http://127.0.0.1:5187/investigation-preview` (add
`?locale=en` for English). It uses fresh temporary databases and synthetic
findings, with the real UI, API, journal and atomic writer. It does not use the
production profile, execute a provider, or change the running App.

`OLD` exercises the completed finding and human-confirmation workflow; `LIVE`
represents a still-traded control; `CACHED` exercises source-confirmed review
without an LLM requirement. The Settings button opens the actual budget editor
backed by the temporary profile. These synthetic symbols are not market evidence.

## Legacy Cutover

Installing the v2 journal is explicit. It disables only the legacy lifecycle SEC
intake and queue projection; SEC financials, normal SA/news capture and prices are
not retired. Old rows are not automatically transferred into another work queue.

Deletion is a separate, dependency-aware, digest-bound operation. The manifest
retains actual pending/applied action dependencies, receipts, identity links and
membership tombstones. Private backups precede mutation. Profile cleanup must
produce its receipt before market cleanup can start. An unknown external
dependency is retained; unrelated collector changes do not invalidate the entire
batch. Synthetic 36-row rehearsals exercise completeness, continuation and
rollback, not authority to delete today's production rows.

The operator entrypoint is `python -m src.lifecycle_investigation`:

- `install-preview` / `install`: explicit profile path, approved digest and backup.
- `disposal-preview` / `disposal-stage`: explicit profile/market paths, approved
  manifest and backup; profile stage precedes market stage.
- Write commands require an explicit stopped-App assertion. No command selects a
  default production database, starts a provider, or restarts the application.

## Remaining Deployment Authority

After code/evidence review, production deployment still needs separate approval
for merge, stopped-App installation and the current dependency manifest's exact
cleanup. The temporary review URL is not the installed application and its
synthetic findings must not be treated as market evidence. Push remains with the
user after their hand test.
