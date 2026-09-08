# Lifecycle Investigation Agent And Bounded Follow-Up

Status: September 7 product intent confirmed: one button starts a complete,
adaptive investigation task, not one search/model request. The user accepts more
rounds and sufficiently generous bounds to avoid endless loops. Independent
task routing, Settings and the operator workflow belong in this amendment.
The earlier three-round/six-call proposal is superseded; it is not an approved
fixed schedule or permanent ceiling. Implementation and admission remain open.
This clarification makes no production migration, installation or new dispatch.
The subsequent source ruling explicitly includes already-collected local news:
this is a purpose-specific listing/rename investigation, not a general market
outlook or an SEC-document research task.
The user also permits replacing/removing the original lifecycle feature and
unneeded legacy case data. The old 36-item batch is retirement input, not a
permanent queue or a prerequisite that must be carried into the new agent.

## Implementation Progress

September 7 routing foundation is implemented and verified offline
in `docs/superpowers/evidence/2026-09-07-lifecycle-independent-task/`.
Full backend: 6,981 passed / 12 skipped; frontend: 1,610 passed. Nine backend
and four frontend selected mutants have named owners; 12 browser scenarios
exercise all four channels using temporary profiles and synthetic replies.
No full-agent live success or hand-test readiness follows from these results.

- [x] Independent `lifecycle_investigation` TaskId, profile route,
  save/reset/import/export and capability/auth admission on all four channels.
  Its built-in unsaved route is Anthropic / `claude-sonnet-5` / `high`, not a
  copy of or fallback to AI Research. A route-store read failure stops this task.
- [x] Bilingual Settings entry and explicitly labelled connection/schema check
  through the selected lifecycle adapter. This check is one tool-free submission
  under the existing 45-second test deadline, not a full investigation or an
  investigation runtime-budget setting. API-key test output is at most 8,192
  tokens bounded by the exact model capability; OAuth is provider-controlled.
  Other tasks and Spark's translation-only boundary remain intact.
- [ ] Independent target/identity entry and versioned journal/action binding.
  The existing case endpoint uses the new model route, but still requires an
  old case and uses the old two-call pipeline. Step 1 is therefore only partially
  complete; no target-independent launch is claimed.
- [ ] Local-news search/body snapshots, configurable whole-run runtime,
  adaptive orchestration, complete-agent UI and full-agent calibration.
- [ ] Legacy intake/projection retirement and scoped dependency-aware disposal.
  No production data, provider call, migration installation, restart or merge
  occurs in this routing foundation.

## Verified Pre-Amendment Bindings

The following inventory motivated the amendment. The two borrowed routing
bindings and three-task catalog are corrected by the foundation above; the
target, runtime, journal, local-news and retirement dependencies remain open.

- `src/api/routes/lifecycle_web.py::get_web_preflight` loads
  `task_route("ai_research")` and the general agent's `max_tokens`.
- `src/security_lifecycle_web_contract.py::validate_selection` also uses
  `ai_research` for execution admission and capability checks. Changing just the
  Settings label would leave the old task identity in both validation paths.
- `src/security_lifecycle_web_pipeline.py::investigate` requires exactly two
  host submissions; result types, preflight limits and the journal also bind one
  search followed by one analysis. Native searches inside a submission do not
  provide a loop that can react to the subsequent host-read evidence.
- `src/model_routing.py`, `src/model_effective.py`, frontend `ModelTask` and
  `settings/ModelRoutingSection.tsx` currently expose three product tasks. There
  is no independently configured lifecycle investigation task.
- The existing panel already has a background job, progress, stop, results and
  attended confirmation. Extend that workflow instead of creating a duplicate
  general Research application or a second credential store.
- `src/tools/news_tools.py` already exposes local keyword and ticker search,
  but its model-facing descriptions are reduced to 200 characters. The current
  `SqliteBackend.query_news_search` searches legacy title/description FTS and
  omits normalized full bodies. Those results are candidates, not a complete
  evidence read.
- The normalized news store has body text, content kind, body status, retrieval
  metadata and content digests; captured SA market news separately has
  `body_markdown` and observation times. `SaCaptureBackend.query_sa_market_news`
  exposes those bodies, but catches failures into an empty list. Likewise the
  ordinary local keyword wrapper returns an empty DataFrame on failure. A new
  investigation cannot treat these tolerant projections as proof of no news.
- `security_lifecycle_news_evidence.py` is a retired acquisition adapter. Local
  corpus access does not revive its former fact-extraction/automation authority.
- `LifecycleWebPreflight._material` still requires `get_case(case_id)` and an
  observation fingerprint; `_public_input` obtains issuer names from SEC cases
  or SA pick history. `lifecycle_web_runs.case_id` also references the old case
  table. An independent route alone does not make the investigation independent
  of the old case population.
- `compose_security_lifecycle` recreates virtual cases from surviving market
  observations and retains persisted cases without observations as
  `source_missing`/`unresolved`. Deleting either side alone does not retire the
  workflow. `data_scheduler.SOURCES` still registers `sec_corporate_actions`,
  whose collector can upsert those observations again.
- Transition/assessment/action data reference old cases. Case deletion can
  cascade into transitions and identity links or be rejected by dependencies.
  Physical cleanup needs an actual reference graph, not a blanket table delete
  or the assumption that every old row is unused.

## Retire The Legacy Workflow

The product may replace the old SEC-derived lifecycle screens, categories,
proposal stages and unused fields wholesale. Reuse components only when they
serve the agreed task or preserve real effects; do not maintain a parallel legacy
interface or fake old observations to satisfy inherited types/tests.

New investigation entry is target-oriented. The user selects a current security
from tracking/status or ticker detail; a review may preselect it, but an old
case, SEC observation, accepted assessment or SA pick is not a prerequisite.
Resolve the target's public listing identity from current metadata and, where
needed, bounded investigation lookup. Missing identity remains explicit until
resolved, never fabricated from a short ticker or a synthetic SEC case. Bind the
job, result and eventual approval to the target/listing snapshot, not an arbitrary
legacy case. Handle ticker reuse and independent security classes explicitly.

Use the versioned journal/action-boundary design to decouple new runs from the
old case FK and observation fingerprint. Legacy references may be retained as
internal historical provenance; they cannot remain a hidden launch requirement.
Retaining a small historical anchor needed by an actual receipt is not retaining
the old product workflow. Do not relabel a Web/news investigation as an invented
Massive/SEC observation merely to satisfy existing case-source constraints.

Retire legacy live intake as part of cutover, not just its UI rows. Disable/remove
the lifecycle-only SEC corporate-actions scheduling/case-projection path after
accounting for its in-flight jobs and pending actions. Optional targeted SEC
reading remains available to the new agent. Do not disable SEC financial data,
news/SA capture, price collection or unrelated scheduler sources. Old observation
refreshes, case composition or app restart must not repopulate a retired queue.

The legacy batch has three disposal outcomes, not three permanent UI buckets:

- An actual current listing/continuation question becomes a target-scoped work
  item under the new rule; old filing count, age or failure to bind an old SEC
  fact is not by itself a new investigation. No LLM request per legacy row.
- Actual applied/scheduled/pending/reversed operations retain or explicitly
  migrate only their necessary reference chain, source evidence and receipts.
  Pending/in-flight effects must be accounted for, not silently cancelled or
  replayed. Preserve effective identity links and source-specific suppression.
- Unrelated, duplicated, superseded or unused case/observation/evidence/translation
  material with no actual retained dependency may be deleted. Do not force it
  into a new history screen or retain every unused assessment indefinitely.

A one-time scoped disposal manifest records affected keys, reasons, real
dependencies and proposed effects. Its complete accounting is for review and
verification, not a new permanent case-processing obligation. Preserve sealed
engineering evidence separately without loading it as product state. The last
observed counts are historical measurements, not a substitute for the authorized
cutover inventory; do not hardcode 36 or 39.

Cleanup of obsolete investigation records is not removal of the securities they
mention. No healthy universe/watchlist membership, holding, price/news history,
Current/Former intent or effective tombstone changes merely because an old case
is deleted. Rehearse dependency-aware deletion/upgrade and exact unaffected-state
readback before a separately scoped production write. Avoid a global SA freeze;
reject changed affected material without treating unrelated capture as a new
lifecycle decision. Do not execute a broad production deletion based solely on
this product-direction agreement.

## Why Larger Search Limits Alone Are Insufficient

The September 7 instrument-scoping run used only two of twelve searches and five
of twenty-four HTTP attempts. It returned a non-actionable finding. Its CapEdge
8-K page explicitly supplied only a preview ending in Item 1.02. No transport or
RAM bound was reached. The visible original link led to a public SEC filing
index, whose typed primary-document row led to the full 8-K. That document
contained the relevant common-stock trading cessation paragraph in Item 3.01.
The host diagnostic, not the product agent, followed those references.

The two analysis-only follow-ups used the same current product prompt with the
additional captured document. One output failed the JSON contract without raw
output diagnostics; the next was valid JSON but still non-actionable. It put a
statement explicitly saying debt was NOT a contradiction into `contradictions`,
omitted the instrument-definition span from an event using `Company Stock`, and
had citation/date-support gaps. These are not successful user confirmations.
An explicitly hand-constructed, exact-quotation positive control passes against
the very same captured source and actual selected context. It is not presented
as model output. Full source capacity is not the bottleneck.

## Evidence Retrieval Policy

The purpose is to establish whether the exact tracked security still trades or
has changed symbol, with effective timing and a usable supported conclusion.
Do not expand this into predicting price reactions or producing an issuer-wide
investment thesis. Announced/planned events may explain context but do not by
themselves change collection status.

Default acquisition order:

1. Consume the structured Massive/EODHD checks with their actual timestamps and
   limitations. A discrepancy with newer public information is an investigation
   question; both APIs need not fail before the user can ask for investigation.
2. Search already-collected relevant news first. Use stored complete article
   bodies where available; do not repeat a network fetch simply because the
   evidence is local. This includes current provider news and captured SA market
   news, not private notes, holdings, comments or unrelated article collections.
3. When local content is absent, incomplete, stale or materially contradictory,
   use targeted public Web/news search, issuer/exchange announcements and original
   source links. A local hit or a fixed count of articles is not a stopping rule.
4. SEC has low default retrieval priority and is optional targeted supplementation
   for a specific unresolved date, instrument or condition. There is no SEC
   quota, mandatory SEC pass or automatic filing-history traversal. A relevant
   already-found filing with direct event evidence remains usable; low search
   priority does not mean discarding good evidence or pretending all filings
   concern only future events.

This is a cost/relevance acquisition order, not an absolute truth hierarchy.
The agent evaluates the exact security, event meaning, dates, original reporting
and later corrections. A complete issuer/exchange notice or sufficiently clear
reliable news report may support human confirmation without a matching provider
update or SEC citation. Do not label an unexplained API discrepancy as proven
provider lag. Keep the observations and dates visible, distinguish announcement
from effectiveness, and investigate substantive conflicts rather than guessing.
Syndicated copies, local/web copies of one article and reports quoting one
announcement are not independent corroborations.

### Local News Capability

Expose a host-owned, readonly search/read contract through the common agent
orchestrator. Extend the current data-access capability with closed projections
where needed; do not add a second news store or grant the model SQL/file access.
Local access is part of this task, not another mandatory Settings toggle or a
second button. Only selected relevant article passages and public bibliographic
metadata may cross the selected model boundary. No whole-profile/corpus export,
raw capture JSON, private annotations, credentials or unrelated SA history.

Search returns run-scoped candidate references, title/publisher/source/URL,
publication time and coverage metadata. Read resolves only an admitted candidate
against the actual local authority and snapshots its exact usable text plus
content digest, retrieval/read time and public provenance into the run. Keep DB
row IDs and filesystem paths internal. Reuse the current content-kind/body-state
information: `fetched` can describe a captured summary and is not alone proof
that it is a full article. A headline, 200-character tool preview or unknown
body must not be advertised as a complete read. Missing bodies remain explicit;
reading a candidate does not silently schedule recapture or spend a news API call.

Bind searches to the current public case identity, observed/proven aliases and
the relevant event interval, with optional issuer-name queries for mis-tagged
articles. A stored ticker association is a search hint, not proof of instrument
identity. Let the agent widen the date/query window when needed instead of
silently fixing every case to the existing 30-day search default. Return a
bounded page and explicit remaining coverage, not an unlabelled clipped set.
Distinguish a successful zero-result query from unavailable storage or a failed
query. An unavailable optional corpus is a disclosed gap, not a reason to block
all public research or to claim the event did not occur.

Use short readonly database snapshots; do not hold a DB transaction/collection
lock during model or HTTP work, modify the news/SA collectors, or require them
to pause. Preserve the selected text/digest for later confirmation even if the
news collector updates the original row. Public URLs remain source attribution,
not a requirement that a previously captured licensed body be fetched again.
Cached completeness and current-event freshness are separate dimensions.

Local reads consume their own recorded work/time/source budget, not fictitious
HTTP attempts. A sufficient local-only investigation still performs measured
model work, but must be allowed to finish with zero new Web/SEC/news-provider
requests. All four auth adapters receive the same evidence contract. General
Research's tolerant search behavior and the retired lifecycle adapter are not
silently changed in this amendment.

## Independent Task And Settings

Use a dedicated `lifecycle_investigation` task identity with its own
provider/model/effort route. Reuse the existing profile-backed `model_route`
store, provider credential selection and discovery/admission projections.
Saving this route must not change AI Research, Content Translation or Card
Synthesis, and changing those routes must not change an investigation's route.
The current Research selection may be offered as an unsaved initial draft, not
silently copied into the DB or kept as a live fallback. Resolve and display a
valid route for the new task before any dispatch. A running job keeps its
admitted route/authentication/credential binding; changing Settings must not
switch its model or billing source midway.

Settings adds one task entry, not a new provider setup screen:

- Provider, model and effort use the existing model picker and active credential
  authority, with task-specific compatibility and actionable unavailable states.
  Both API-key and OAuth channels remain required. Spark's translation-only
  admission does not become research eligibility merely by adding a task ID.
- Advanced runtime settings provide a generous finite whole-run deadline and
  model-submission/search/source-read ceilings. Count host model submissions,
  provider-native tool uses, unique sources and HTTP attempts as distinct
  quantities; do not describe all of them as an interchangeable "round".
  Values are configurable and snapshotted for a run, not buried in prompts or
  reset by a follow-up. Do not require the user to tune every value before use.
- Any model-output budget is per task and only configurable where that adapter
  actually enforces it. Show provider-controlled/not-applicable otherwise. Do
  not confuse provider context/output capability, supplied passage selection,
  source byte limits and a PC memory allowance, or silently truncate input.
- Settings save, reset, import/export, task testing and preflight must use the
  same closed task/runtime contract. A connectivity/schema test must be labelled
  separately from a complete investigation test; it cannot stand in for it.
  Merely opening Settings or changing a selection launches no model call.

Exact defaults and maximums must be derived from the replay/live failure cases
and documented before implementation, not mistaken for the old two-call user
requirement. Preserve cancellation, no-progress exit and finite total work even
when increasing the limits several-fold. Host-enforced and merely observed
provider bounds must remain distinguishable in consent and usage.

## Adaptive Agent Contract

An investigation is one durable, target-scoped job. The model may choose the next
useful research action from a restricted, typed tool surface based on the public
question, sources already read, remaining gaps and remaining budget. Actions
cover local-news search and body reads, targeted public search, reading/following
public references, inspecting captured passages and submitting a structured
assessment. It is not a fixed sequence of
three copies of search/read/analysis, nor unrestricted shell/file/MCP access.
Reuse the existing source reader, credential, cancellation and usage contracts;
keep orchestration and final-result semantics shared across all four transports.

- Keep one global call/search/source/HTTP/time budget for the entire run,
  including redirects, original-document hops and format/grounding corrections.
  Reserve/count work at the actual dispatch boundaries, not only in prompts.
  An extra search or a source reread is not automatically required for every
  analysis step, and a sufficient first result does not require another round.
- Successful but incomplete analysis may request a named follow-up: missing
  original source, missing instrument scope, or citation/format correction.
  A transport, auth, model-identity, timeout or quota failure still stops. An
  owned completed reply rejected for output shape may get a named, bounded
  correction only after the rejection and observed usage are retained. It is
  not an accepted finding and is not a transport retry. No model, credential or
  billing fallback. Follow-up reasons and every extra submission must be visible
  in the durable phase history.
- Give the next search the actual source coverage, remaining gaps and already
  visited URLs. Expose and follow explicit public original-document references
  with the existing pinned HTTPS/SSRF and source-byte protections. A source
  reference is not an HTTP redirect and must not be recorded as one. Do not log
  into the preview site, bypass its access gate, assume its preview is complete,
  or force SEC as the authority for every case.
- Stop on an action-ready supported finding, a supported active result, no new
  relevant source or improved grounding, or the run ceiling. Do not fill quotas
  just to use them, loop over the same URLs, or ask the user to repeat research.
- Keep stock, debt, preferred stock and option identities separate. Allow a
  source-bound definition/identity chain without treating issuer identity alone
  as security identity. Review the single-quotation identity requirement and
  defined-term handling against both genuine stock notices and misleading debt
  notices before changing it.
- Prefer source-bound passage references to making a model reproduce long
  whitespace-sensitive quotations. Any revised output shape must retain exact
  original text, coverage, date and instrument provenance, and legacy readback.
  Do not silently repair or discard an unsupported claim to make a run green.
- Restrict `contradictions` to genuinely incompatible facts about the target
  security. Irrelevant instruments and explanations of non-contradiction belong
  in neither a veto list nor a fabricated conflict. Keep optional announcement
  information separate from the evidence needed to decide collection status.

## Structured Result And Operator Workflow

Require a versioned closed output contract, not only free-form prose or a valid
JSON object. Separate typed continuation requests from final findings. A final
finding carries target instrument identity, listing/continuation outcome and
timing, old/new symbol when relevant, effective date when evidenced, a concise
explanation, captured-source passage references, real contradictions and
remaining material gaps. The host validates both shape and evidence binding.
Confidence or the model saying "finished" cannot grant mutation authority.

Keep the existing distinctions between active trading, completed listing end,
same-security continuation, scheduled/conditional events and unresolved status.
Stock, debt and option evidence cannot be substituted for one another. An
acquisition is not automatically a listing end or continuation. Allow definition
and event passages to jointly establish the same instrument without requiring
one enormous verbatim quote. Render quotations from captured passage references,
not model-reconstructed text. A rejected result remains recorded; a budgeted
correction creates a later candidate rather than rewriting the rejected one.

The target's tracking/status or detail view is the primary entry; an existing
review can link to the same task. One "Investigate" command, with explicit
model/auth and budget consent, launches the whole task without requiring an old
case row. No per-search approvals
or requirement that the user choose the next URL/repair a citation. Show the
selected route near the command with a link to its Settings entry; optional
per-run choices must be explicit snapshots, never another persistent authority.
Do not require the user to know a successor or distinguish a delisting from a
rename before asking the agent to establish the listing status; an optional
focused question may narrow work, not make that prerequisite mandatory.

During execution show current work, elapsed time, useful source counts and a
stop control. Reopening the target must read the same job, not start another one.
Present the final conclusion, effective date/next ticker where relevant,
essential sources and any actual unresolved gap first; leave call logs, usage
detail and source diagnostics expandable. Multiple internal calls do not mean
multiple unexplained buttons or a report in an unrelated Provider-status area.

The agent returns a proposed conclusion, never directly edits a watchlist or
tracking membership. A separate, clearly named removal/rename confirmation uses
the existing preview, current-state checks and atomic receipt path. The user
may acknowledge explicitly disclosed source gaps when the action's necessary
instrument/status evidence is supported; optional missing paperwork is not an
automatic veto. Do not use that permission to waive wrong-instrument evidence,
unresolved material contradictions or stale approval. A no-progress/budget stop
retains the findings and exact gaps; it is not a completed positive conclusion.

## Required Schema And Cross-Module Work

`lifecycle_web_calls.call_id` has a CHECK permitting only `search-1` and
`analysis-1`. The store, controller, usage ledger, consent/read DTO and tests also
bind those identities. Increasing only RunControl or an SDK turn limit would
break persisted accounting. A versioned schema/read contract is therefore real
work, not a silent constant bump. The adaptive job needs ordered call/step
identities, a cumulative ledger and independently recorded intermediate/rejected
assessments. Preserve old journals, including failed and
non-actionable runs, with explicit supported-version handling. The last
authorized production inventory found no installed Web journal; that is an
observation at that time, not permission to inspect or install now.

Adding a row to `model_route` alone requires no table migration: its task key is
TEXT without a task CHECK. That does not imply zero migration for the feature.
The new runtime-settings storage and versioned Web journal need an explicit
storage/upgrade design; do not add columns only to CREATE TABLE IF NOT EXISTS
or assume every profile has no journal. Do not reuse fixed-task-only timeout
semantics as if they already described a multi-step investigation's deadline.

## RED-First Delivery Order

1. Own the independent target/task across registry, resolver, save/import/reset,
   capability admission, all four auth adapters, frontend types and Settings.
   Prove positive route selection and two-way isolation from all three existing
   tasks; no fallback, implicit profile writes or provider calls from read paths.
   Own `test_investigation_can_start_without_legacy_cases_or_observations` and
   `test_manual_only_target_does_not_require_sa_pick_history`. A new job must not
   create a fake SEC/provider case to make either test pass. Unresolved identity
   remains a real lookup/gap rather than a made-up issuer.
2. Own the local-news search/read projection on temporary normalized, legacy
   and SA capture stores. Named RED owners include
   `test_local_news_full_body_supports_finding_without_web_or_sec_requests`,
   `test_news_preview_is_not_full_body_evidence`,
   `test_local_news_unavailable_is_not_an_empty_success`,
   `test_lifecycle_news_snapshot_survives_collector_update` and
   `test_syndicated_local_and_web_copies_are_one_source`. Include defined-term
   stock positives, same-issuer debt negatives, planned/cancelled events, old
   stories reissued today, and a clear completed event while structured snapshots
   have not reflected it. Zero Web reads must not be misreported as zero model
   usage. Prove no collector mutation, lock held across model work, leaked private
   fields or reactivation of the retired acquisition adapter.
3. Own the versioned journal/runtime contract, consent binding and adaptive loop.
   Test first-step completion, targeted second/later-step success, public
   preview -> original/index -> primary document, typed JSON/grounding correction,
   no-progress exit, cumulative budgets, partial/fatal failure, cancellation and
   restart readback. Include both same-source defined-term positives and
   wrong-instrument/issuer/date negatives. A manual positive control is not an
   end-to-end agent success.
4. Own the Settings/launch/progress/result/confirmation workflow against actual
   closed API payloads, including stale Settings or profile state, no duplicate
   dispatch, old-journal display, no-progress gaps and an independently tested
   successful user confirmation. Browser tests must cover desktop/mobile and
   both languages; do not show the full internal investigation on the main view.
5. Calibrate the actual complete agent through Claude OAuth first with the
   existing permitted Sonnet/Opus models, then validate the other three channels
   against the same task/result/tool contract. Retain exact provider/model/auth
   and measured calls/usage, rejected outputs and the source coverage trail.
6. Rehearse legacy retirement independently from listing mutations. Named RED
   owners include `test_retired_sec_intake_cannot_repopulate_attention_queue`,
   `test_unused_legacy_cases_can_be_removed_without_tracking_changes`,
   `test_legacy_cleanup_preserves_actual_receipts_identity_links_and_tombstones`
   and `test_new_investigation_works_after_legacy_cleanup`. Test one-sided stale
   inputs, restart, normal SEC financial/news/SA scheduling, unrelated concurrent
   writes and legitimate new target issues. Split the old
   `test_legacy_screened_cases_are_counted_and_reclassified_not_dropped` contract:
   retain complete one-time disposal accounting, remove mandatory permanent
   review/history placement. Record retired test contracts versus lost safety
   coverage. No silent cascade deletion, fabricated resolution or paid batch
   re-investigation of all old cases.

Run the full focused set, named reverse mutants, integration/backend and actual
UI parser/browser paths. Claude OAuth calibration remains first; the other three
transports must consume the same contract and must not be declared live verified
because Claude succeeds. Production migration, installation, adoption, restart,
merge and push remain separate actions.
