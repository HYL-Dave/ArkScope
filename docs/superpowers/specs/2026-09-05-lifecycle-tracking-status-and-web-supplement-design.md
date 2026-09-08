# Lifecycle Tracking Status And Web Supplement

**Date:** 2026-09-05

**Status:** Product-direction amendment, including the user's authorization of
substantial Lifecycle redesign, read-then-confirm web-supported actions, and
reclassification of existing cases.
At the September 5 design checkpoint this amendment had changed no runtime policy,
production membership, provider execution or UI. Subsequent implementation and
separately authorized operations are recorded in
`../plans/2026-09-05-lifecycle-terminal-membership-completion.md`; this historical
checkpoint is not a claim that the current worktree is still design-only. The
agreement does not authorize unattended LLM spending or bulk acceptance of case
conclusions.

**Precedence:** This amendment changes the next delivery's product contract,
not the meaning of prior evidence or receipts. It supersedes the requirement to
prove absence of a successor before retiring a confirmed invalid old listing.
The existing census design and sealed packets remain historical evidence, not
constraints that force the old workflow, display or live case classifications
to survive. All existing cases are in scope, not just cases created after cutover.

## 1. Product Goal

Keep the symbols used for price/news collection correct. The main questions are:

1. Can this exact tracked listing still be collected under its current symbol?
2. Is a different symbol confirmed to represent the same security?
3. What change, if any, has actually been applied to local tracking?

An invalid old listing, an issuer's continued existence, and a successor relation
are different facts. Removing an invalid old symbol must not claim that the
company has disappeared or that no successor exists. An acquisition announcement
alone changes neither tracking intent nor collection eligibility.

The user accepts simplifying or replacing the investigation display. EODHD and
Massive are the primary structured sources; web investigation is for unresolved
questions, not a replacement for routinely available structured data. Broad SEC
filing research and arbitrary Seeking Alpha article acquisition remain separate
workstreams.

### Change Authority And Product Boundaries

The user permits substantial changes within Lifecycle when they improve tracking
correctness, clarity or maintainability. This includes its UI, case model,
evidence rules, approval stages, APIs, storage and implementation. Neither sunk
cost nor an old internal contract is a reason to retain an inferior design. This
is permission to choose the better solution, not a requirement to replace
everything: retain useful components, reshape awkward ones and remove unnecessary
ones according to their contribution to the product goal.

References to current modules and proposed mechanisms below are starting points,
not mandatory architecture. A better implementation may combine or replace them.
Tests must protect the agreed outcomes and unaffected consumers, not force
obsolete internal behavior to remain. Shared code may change, but its consumers
must be inventoried and unintended behavior changes prevented.

The intended cross-feature effects are explicit: a reviewed removal excludes its
agreed tracking sources from the universe/watchlists and future normal collection;
a reviewed continuation moves the agreed tracking identity. Outside those effects,
protect other tickers, Current/Former intent, SA raw history and synchronization,
portfolio accounting, price/news data and collectors, coverage calculations,
Research and Content Translation, and credential/billing behavior. The regression
plan must exercise these consumers, including positive controls for unchanged
tickers and sources, rather than only Lifecycle's own tests.

Routine in-scope implementation choices need no renewed product decision. Raise
material uncertainty with the user before accepting additional cost, reduced
evidence assurance, irreversible data loss, changed portfolio meaning, or an
unavoidable change to another feature. Explain the concrete benefit, risk and
alternative; do not quietly accept the risk or treat an early decision as an
unreviewable prohibition. Designing a migration is permitted; applying it or
running providers still follows the separately agreed operational approvals.

## 2. Removal And Continuation Are Independent

| Observed situation | Tracking treatment |
| --- | --- |
| Exact listing remains active, including active OTC trading | Keep collecting. Acquisition news does not remove it. |
| Old listing is explicitly inactive and current listing checks agree | Permit governed old-symbol retirement without an exhaustive successor timeline. |
| Same-security replacement is independently confirmed | Offer reviewed symbol continuation; do not equate an acquirer with the same security. |
| Listing evidence is incomplete, stale, unavailable, or contradictory | Keep current tracking until a supported decision is available; offer web investigation and attended review. A failed query is not delisting. |
| User explicitly removes a Former membership | Persist its source-specific removal; refresh, bootstrap and aliases cannot revive it. Other active sources remain independent. |

The initial structured automatic retirement plan uses the measured source
combination: exact-symbol/stable-ID binding, explicit Massive inactive record and
date, EODHD delisted confirmation, complete Nasdaq directory checks, and successful
active stocks/OTC checks. This is an evidence-backed starting point, not a permanent
requirement to retain a fixed number of sources. A proposed alternative must show
what it establishes, its coverage and failure behavior, with any material evidence
risk brought to the user. Positive active evidence vetoes automatic old-listing
retirement. The immediate supported change removes the unrelated demand for an
exhaustive ticker-event history, not the distinction between query absence and
positive delisting evidence.
The separate attended web-evidence lane in section 5 must not depend on the same
unavailable endpoint becoming successful before the user can confirm a supported
action. It is a different evidence/acceptance authority, not a weaker automatic
rule or a blanket bypass of identity and profile-integrity checks.

Ticker Events remains useful for discovering a replacement, but a 404, rate
limit, unsupported history, or unavailable timeline cannot mean "no successor."
Such a result can leave continuation unresolved while old-listing retirement is
independently supported. Preserve that unresolved continuation and its evidence
after retirement; do not bury it as an entirely resolved investigation.

Distinguish an absent timeline, multiple matching timelines, and a retrieved
timeline naming a different latest ticker without a proven old-to-new relation.
The last shape is a replacement candidate, not absence of evidence. Surface the
candidate and keep continuation unresolved. A candidate alone must not veto
independently supported retirement of the old listing; a material identity
contradiction or evidence that the old listing remains active still does.

Retirement must atomically achieve the agreed profile effects: archive applicable
manual/legacy membership, suppress accepted SA tracking, remove the old symbol
from the active universe, and retain the receipt. The existing transaction is a
reuse candidate, not a requirement to retain its internal structure. Daily
watchlists and ordinary scheduled price/news collection use that effective
universe. Historical records,
SA source observations, and portfolio accounting are retained. Open-position,
freshness, source-binding, and approval-digest guards remain in force. Already
dispatched jobs and explicit historical reads are not retroactively cancelled.

No separate "pause tracking" feature is introduced. Ordinary Former removal
and lifecycle retirement have different source scope; neither may silently
rewrite a source's raw history. A future genuinely independent SA recommendation
must not be blocked by a ticker-wide successor blacklist.

## 3. Current Code And Required Changes

- `src/security_lifecycle_provider_authority.py::classify_provider_listing`
  currently collapses a missing timeline into `unresolved`, even when listing
  checks are otherwise complete. However, `terminal_requires_attestation()` and
  `provider_transition_guard()` already admit human-accepted terminal treatment
  for exactly `successor_check_unavailable` with stored blockers contained in
  `{"massive_not_found"}`. Temporary-store integration tests and the prior
  separately authorized copy rehearsal exercise that attended write path. The
  missing offer is at `evaluate_provider_decision()`: every non-terminal state
  becomes `undetermined` and `action_blocked`. RED tests must reach the decision
  and proposal boundaries; a human-guard-only test already passes today.
- That unavailable-timeline reason also covers multiple matching timelines and
  a retrieved timeline with a different latest ticker but no event from the
  tracked ticker. The latter already reaches the human-attestation exception.
  Separate these meanings before relaxing classification. Replace the old
  reason-string exception with explicit listing evidence and approval authority;
  retain genuine automatic-versus-attended policy distinctions, including
  historical-event coverage, without leaving a second catch-all bypass.
- `src/security_lifecycle_provider_store.py` persists append-only observations;
  `src/tools/security_lifecycle_tools.py` projects detail and audit separately.
  New projections must distinguish listing evidence, continuation evidence, and
  actual collection state without relabeling old stored conclusions. The current
  store reader regenerates observations through the current classifier while
  validating saved snapshots. Changing classification alone can therefore reject
  an unchanged old snapshot with `provider_snapshot_digest`. Separate historical
  integrity validation from current-policy projection or explicitly version that
  binding; preserve tamper detection and old-snapshot readback.
- `src/ticker_identity_transition.py` already owns transactional membership
  treatment and receipts. Reuse, extend or replace the centralized governed write
  authority as needed; do not substitute ad hoc table edits or an LLM-owned write
  path. Inventory actual references before designing compatibility for identifiers
  such as `terminal_delisting`; empty action tables do not require invented
  historical-action decoders. They do not imply zero migration, either: the
  installed transition and membership schemas embed that value in CHECK
  constraints and validate exact DDL. Renaming it can require schema conversion
  even with zero action rows. Inspect installed schemas, references and consumers
  at cutover; preserve the meaning of any receipts that actually exist.
- `build_transition_preview()` currently rejects non-`listing_authority` cases
  when membership storage is installed. The apply-boundary `_provider_guard()`
  and compose-side source screen must also be addressed. Removing the source
  gate alone does not admit the legacy `symbol_or_venue_changed` outcome: the
  independent outcome guard still rejects it. Nevertheless, the new web lane
  needs fresh action-bound human authority, not a blanket promotion of old
  accepted assessments. Changing only the browser label would leave this path
  blocked; widening only a source or outcome allowlist is not sufficient either.
- `src/api/routes/security_lifecycle.py::accept_assessment` accepts an assessment
  and generates proposals, but deliberately does not apply a transition.
  `src/ticker_identity_service.py` separately previews, approves and executes.
  A single user command must own the action without turning an existing accept-only
  consumer into a surprise mutation path. The old endpoint and internal stages
  may be retired or replaced with deliberate caller updates and regression proof.
- `compose_security_lifecycle()` currently screens every legacy non-listing case
  out as `regulator_monitor_only` once membership storage is installed. That
  source-based rule is not a substitute for reclassifying every existing case
  under the new tracking/action contract.
- `apps/arkscope-web/src/lifecycle/LifecycleView.tsx` already lazy-loads audit,
  but its primary summary still organizes provider cases around filing/event
  fields. Removing raw prose alone does not fix that product mismatch.
- `src/agents/shared/server_tools.py` already wires provider-native web search
  for supported Research paths. `src/tools/web_tools.py::web_browse` reads a
  known URL; it is not a search engine or an admitted restricted investigation
  controller. Do not assume identical search support across authentication modes.

The RED-first plan must map these independent states through the writer, stored
observation, decision, preview, approval, revalidation, API and UI. Prefer existing
storage when it represents the facts honestly. If a new persisted enum or field
requires migration, present that migration separately; do not encode a new
meaning in an unrelated existing code to claim "zero migration."

## 4. Main Display

Use one compact exception table, with resolved history available separately.
Healthy listings belong in a coverage summary, not one attention item per
filing. An unresolved check stays visible even when it has no admitted fact.

Each row needs only:

- ticker and issuer;
- current collection state, distinct from the recommended action;
- one concrete finding: active, old listing inactive, replacement confirmed, or
  still unresolved;
- the next action, such as review removal, review symbol change, recheck, or web
  investigation; and
- last observation time and, when unresolved, the missing condition/next check.

The detail panel adds applicable dates, old/new symbols where relevant, and
concise provider results with observation time and source links. Do not render
an empty successor, SEC filing, M&A-terms, or translation field on every case.
Applied removal must read as applied, not merely suggested. A retired symbol
with an unresolved replacement remains discoverable as a pending follow-up.

Provide on-demand provenance and history needed to explain decisions, including
their source material and receipts; the existing audit view may be reused or
replaced. Do not retain useless fields merely to fill its old layout. Use closed
DTOs and runtime parsing for both
views; UI, API and AI Research must receive consistent current-state meanings.
Move duplicated, low-relevance and superseded prose out of the default view;
account for evidence dependencies of actual receipts and retained assessments
before deletion, and do not treat old material as a fresh observation. This does
not require preserving unused fields or hypothetical action history. Evidence
translation remains optional within audit, not a mandatory stage or a second
independent translation setting.

## 5. Web Investigation And Human Confirmation

### Independent Investigation Task

September 7 clarification: one button launches a complete, adaptive investigation
job. It does not mean one model request, one search, or a fixed pair of phases.
The agent may investigate, follow original sources, inspect relevant passages,
resolve gaps and correct its structured submission within generous finite
whole-run bounds. The earlier three-round/six-call suggestion is not the product
contract. Sufficient evidence, no progress, cancellation or the declared total
budget/deadline ends the loop; successful completion need not consume the limit.

Use an independent `lifecycle_investigation` task with profile-backed
provider/model/effort and runtime Settings. Reuse existing credentials, model
capabilities and the four transport adapters, not a second configuration store
or an unrestricted Research agent. The current implementation's borrowed
`ai_research` route and admission task must both be replaced. Saving this task
must not change Research, translation or synthesis, and their later Settings
changes must not change it. A running job is bound to its admitted configuration.

Settings exposes the task and optional advanced whole-run budgets with honest
adapter-specific control semantics. Do not call a native provider tool turn, a
host submission and a source HTTP attempt the same thing. Do not claim a token
setting works where the provider controls it. Generous configurable defaults
avoid requiring routine manual tuning without allowing unbounded execution.

The command belongs to the selected security's tracking/status or detail view,
with model/auth near it and a link to the task's Settings, rather than a new
top-level chat surface. An existing case may link to it, but is not a launch
prerequisite; a security with no SEC case or SA pick history must be investigable.
The job and result bind to the actual target/listing identity, not a fabricated
legacy observation or arbitrary old case. It starts an
asynchronous job with progress and cancellation; subsequent search/read/analysis
steps do not demand another click. Show a concise conclusion, key evidence,
dates/successor and material gaps, with technical details on demand. A versioned
closed result schema and source-bound validation feed the existing separate
human confirmation; generating the conclusion never mutates tracking itself.
Supported explicit source-gap acknowledgement remains available without waiving
instrument identity, genuine contradictions or stale approval.

This is an orchestration, Settings and persisted-job contract change, not an SDK
turn-limit tweak. The current journal's two-call CHECK needs explicit versioned
upgrade/readback, and task/runtime contracts need backend/frontend parity.
Approved direction does not mean the feature is implemented, tested or installed.
The delivery amendment is
`docs/superpowers/plans/2026-09-07-lifecycle-web-bounded-followup.md`.

### Entry And Execution

September 6 scope ruling: the user requires both API-key and subscription OAuth
execution in this delivery. The required matrix is OpenAI API key,
`chatgpt_oauth`, Anthropic API key and `claude_code_oauth`. An API-key-only first
release is not accepted. Reuse credential admission without broadening ordinary
Research or Spark Content Translation's tool surfaces. Each channel needs its
own restricted adapter and independently tested search, provenance, billing and
cancellation contract. An unavailable model/account remains explicitly unavailable;
it must not cause a switch to another credential or transport. Implementation
approval is not authorization for live calls, production migration or restart.

Start with an explicit per-security command for an unresolved listing or
continuation question. Opening a view, refreshing a list, or encountering provider downtime
must not silently invoke an LLM. Show the selected model/authentication path and
the bounded work before execution; unsupported search capability is a visible
state, not a reason to switch model, credential, or billing source.

Prefer Research's supported dispatch, authentication, usage/events and cancellation
contracts, with a restricted lifecycle purpose. Lifecycle may need a new adapter
or orchestration, but must not silently change general Research behavior. Do not
launch an unrestricted agent and rely on its prompt to avoid profile writes.
Only the minimum public case identity, relevant dates, unresolved question and
selected relevant news/source passages leave the profile. The September 7 user
clarification explicitly includes already-collected news, via a host-owned
readonly capability and closed projection. Do not send holdings, credentials,
watchlist contents, private annotations or raw private stores. No lifecycle
mutation tools, shell, general file access or ambient browser session are part
of this run.

Before implementation, derive and record the actual model-turn/search/page-read
envelope from the chosen adapter. Some hosted searches do not expose the same
per-request controls; an unenforceable bound must not be advertised as enforced.
Count actual calls and report partial, cancelled and budget-exhausted outcomes.
No hidden retry or cross-provider fallback; no unattended web-search scheduling
in the initial slice. This work and any live canary have their own plan/approval.

### Search And Evidence

1. Bind queries to issuer name, exact old ticker, security class/venue, known
   identifiers and relevant dates. Never search a short symbol such as `TA`
   alone and treat all results as that company. Provider identity anchors do
   not automatically become publicly searchable identifiers.
2. Massive and EODHD remain the primary structured checks, with actual observation
   times and limitations. For unresolved, stale or discrepant results, first
   search already-collected relevant news and read its captured body where
   available. Use targeted public Web/news search, issuer/exchange announcements
   and original links when evidence is missing or needs updating. SEC has low
   default retrieval priority: consult it only as useful targeted supplementation,
   never a required hop, filing-history sweep or publisher quota. Do not discard
   an already-found explicit completion notice merely because it is a filing.
   Judge exact security, actual trading/symbol change, event dates and later
   corrections, not the medium through which the source was obtained. A complete,
   clear issuer/exchange notice or reliable news report can support human review
   without waiting for an API update or SEC corroboration; a snippet cannot.
   Syndicated copies and local/Web duplicates do not become independent sources.
   Observed disagreement is not by itself proof of provider lag. This does not
   add an automatic news refresh, separate paid news API call or private-history
   access beyond the selected public news evidence.
3. Separate filing date, announcement date, expected date, effective
   listing-change date and observation time. Filing is not itself proof of
   effectiveness. Distinguish completed, scheduled, conditional and cancelled
   events. A recent article about an old event is not a new event;
   an acquisition or suspension is not automatically permanent delisting.
   Do not exclude the actual historical primary notice merely because it is old.
4. Return a short supported finding, cited source passages/URLs, identity match,
   dates and remaining contradictions. A search snippet or unsupported model
   assertion is not sufficient evidence. Failed access or partial coverage must
   remain distinguishable from no matching result.
5. Admit new public page fetching only with reviewed HTTPS/DNS/redirect safety
   and isolated retrieval; do not reuse the generic browser as a security
   boundary. Page instructions are untrusted data, not authority to change tools,
   credentials, budgets or the investigation goal.

### Already-Collected News

The purpose-specific agent can search current provider news and captured SA
market news through a host-owned local capability; it is not an unrestricted
financial research agent. Search produces admitted candidate references and
public metadata. A separate body read preserves exact text, publication and
capture times, content kind/completeness and digest. Do not substitute the current
200-character tool description for a body or treat `body_status=fetched` alone
as proof of full article coverage. A successful empty query and an unavailable
corpus have different typed results. Neither proves that an event never happened.

Query by target identity and relevant event window, expanding within the declared
work budget if needed; do not hardwire the ordinary 30-day default as an evidence
boundary. Read only relevant passages into the model context and preserve their
full local source snapshot for citations. All four auth channels use the same
closed source contract. A sufficient local-only result may finish without any
new public Web/SEC request, while still recording its model usage. A missing or
outdated local body can trigger public supplementation; it is not a permanent
blocker. No extra user button or mandatory source-setting toggle is needed.

Local access does not resurrect `security_lifecycle_news_evidence.py`'s retired
fact-extraction authority. It adds neither database writes nor collector pauses,
whole-corpus export, shell tools or reads of holdings/private notes. Preserve the
evidence used by a run across concurrent collector updates. The body/citation
and query/error projections need named positive/negative owners before they are
wired into the agent; existing tolerant search wrappers alone are insufficient.

September 7 capacity revision: permit 32 MiB of HTTP entity bytes before content
decompression and 128 MiB after decompression per selected source, subject to
offline resource verification. These are revisable PC safeguards, not SEC limits
or model token limits. Full readable text remains stored; the model receives
traceable relevant passages rather than an automatic copy of the whole download.
Use a 4 GiB RSS benchmark threshold across two local investigations, with storage,
readback and controller behavior included. A benchmark is not an OS-enforced
whole-App memory guarantee. No source limit authorizes silent clipping or an
extra model call. New confirmations bind a 180-second shared source-reading
deadline so the larger documents are not constrained by the previous 45-second
phase. The 180-second model timeout and request counts remain separate and
unchanged. Source-validating local result receipts may wait up to 180 seconds;
unrelated request defaults remain unchanged. Preserve the previous sealed
measurements as historical results.

### Read, Confirm, Apply

The user explicitly approves this workflow: when the returned evidence clearly
supports a concrete action, present the finding and effects, then let the user
confirm that action in the same place. Do not require manual re-entry of an
assessment or separate accept/proposal/approval screens. A clear rename shows
old and new symbols; a clear removal shows the affected tracking sources and
that future routine collection stops while history is retained. The command
must be action-specific, such as confirm removal or confirm symbol change,
rather than an unexplained generic acknowledgement.

"Clear" does not mean an LLM's confidence score or emphatic wording. It means
readable supporting sources, bound issuer/security identity, the actual listing
or symbol-change fact, applicable dates, and no unresolved material contradiction
that changes the proposed action. All required action fields must be extracted
and validated before offering confirmation. Missing data leaves an unresolved
case with a specific reason and an available investigation path. An unavailable
structured endpoint alone must not disable an otherwise supported attended
decision. The user should not have to fix missing machine evidence with forms.

September 7 attended-gap decision: an unread supplementary reference alone does
not block an otherwise complete, source-supported LLM conclusion. Show the concise
finding and explicitly list unread URLs with their read-failure reasons in the
result and last confirmation; unread content is not cited or claimed reviewed.
The host records these gaps separately from the model's material uncertainties.
If essential facts are still missing, sources contradict the action, or there is
no complete supporting source, keep the action unavailable. Human confirmation
is the final safeguard, not permission to guess missing identity, event or date.
Its digest must bind the exact gap disclosure as well as the conclusion and
profile effects. Legacy records without URL metadata disclose that absence;
malformed present metadata is never silently treated as an empty list.

The LLM remains the investigator, not the approving actor. Persist its model/run
and cited-source provenance independently from the human acceptance. Confirmation
creates a human-authorized action, not an automatically verified provider fact.
Web evidence may also nominate a replacement for a bounded provider recheck,
but that is not the only permitted completion path.

This new attended lane requires a confirmation record binding the human, reviewed
packet revision and exact action. Reuse or extend the existing approval record
if it carries that binding; a new table is not required merely by this rule.
An earlier `accepted` assessment, whether from legacy migration, automation or
an earlier human accept-only operation, is not consent to this new web action.
This requirement does not disable the separately governed deterministic
automation path or reinterpret its legitimate existing authority.

The backend must prepare a closed review packet containing the conclusion,
citations, exact action/effects and a revision-bound preview. One confirmation
command binds human approval to the validated action and governs its application.
The existing accept/propose/approve/apply stages may be combined or replaced;
their internal shape is not a product requirement. Do not make the frontend issue
a fragile sequence of existing write requests. Recheck the packet, current
profile/holdings, conflicting newer
evidence and prior disposition at the write boundary. If they changed, show a
refreshed preview and request confirmation again; never apply unseen effects.

Profile effects and their receipt must be atomic. Any staged acceptance/approval
state must be durable, recoverable and displayed truthfully. A repeated click,
lost response or worker restart must not duplicate effects or silently authorize
a changed action. Report applied only after readback verifies the receipt and
current tracking state. A future effective date is explicitly scheduled, not
reported as already applied. No new global unattended-mutation switch is enabled.

## 6. Legacy Retirement And Population Cutover

The user explicitly permits replacing/removing the original lifecycle feature
and unnecessary old content. The entire existing batch is retirement input, not
a protected legacy workflow or a requirement to recreate 36 items in the new
interface. New investigation cannot depend on an old SEC case or on completing
a one-by-one review of that batch. Retain useful shared tracking/receipt logic,
not old screens and classifications for their own sake.

There are concrete dependencies to remove: preflight currently requires an old
case and observation fingerprint, and the Web journal references that case.
Composition recreates cases from surviving market observations; deleting only
observations leaves persisted `source_missing` unresolved cases. The registered
`sec_corporate_actions` collector can add observations again. New target-bound
entry/storage and retirement of this lifecycle-only intake/projection are part
of replacement. A screen filter or one-table DELETE alone is insufficient.
Do not invent SEC/provider observations to preserve old schema assumptions, or
remove unrelated SEC financial collection and on-demand evidence-reading tools.

Reconcile three input populations at cutover: persisted profile cases, market SEC
observations including those not yet persisted as cases, and provider checks
projected into observations. Provider projection has latest/history filters;
neither one case per check row nor one case per ticker is a valid assumption.
Distinguish raw inputs, composed cases and UI-visible cases, since source and
queue filters can suppress composed cases. Neither the user's earlier count of
36 nor the review's inferred 39 is a newly measured display count here.

The follow-up review reports 36 market observations and 36 persisted SEC cases
with equal `(source, source_ref, ticker)` sets. That is a reported inventory,
not a production read performed for this amendment. The manifest must measure
both directional set differences, not just equal counts, and may legitimately
find no unpersisted observations. Do not assume an orphan exists or require
permanent equality: a later unpersisted observation is an admitted input that
must be accounted for, not an automatic cutover failure.

The current provider projection first selects tickers that have any historical
non-active check, then returns their latest observation. A latest active check
therefore remains projected after an unresolved check; an always-active ticker
has no projected provider observation. Two network-denied temporary-store probes
verify this distinction. The new view must retain recovered-case history without
putting every healthy ticker in the attention queue.

Provider cases may initially be virtual. Their first assessment upserts a
persisted case with the same provider case identity, distinct from a SEC case
for that ticker. The manifest must reconcile this write without counting a new
security, and handle both same-security duplicates and genuinely distinct
listings. Reading only profile case rows or only the composed view is insufficient.

Classify the old batch once for disposal and any genuine current work:

- Actionable invalid listing or confirmed same-security rename: use the new
  concise finding, effect preview and confirmation workflow.
- Actual unresolved listing/identity question: create or retain the minimum
  target-scoped issue with a visible reason and next action. Neither an old
  filing-only row nor its missing legacy evidence binding is itself a current
  issue. Conversely, deleting the old record does not prove the security active
  or resolve a genuine current question.
- Active security with no current listing/identity issue: retain tracking and
  remove the old filing-only alert from the attention queue.
- Duplicate, unrelated, superseded or unused material with no actual retained
  dependency: delete it when covered by the scoped cleanup plan. Do not require
  a permanent history entry or a new screen for every old document. Preserve a
  relevant source only when it serves a current finding or an actual operation.
- Already applied actions: display the actual receipt/current tracking state;
  do not reinterpret an old accepted assessment as fresh approval to apply again.

Every affected input must have an explicit disposal outcome in the one-time
manifest: current issue, required historical dependency or deletion. Complete
accounting does not require retaining every row or generating a permanent review
for it. Consolidation uses actual security/listing identity, not issuer name,
CIK alone or a reused ticker string.
Do not merge distinct share classes or unrelated historical uses of a symbol.
An unresolved replacement remains visible after old-symbol retirement.

This is a deliberate product-contract change: old case categories, fields, UI
sections and obsolete tests may change or be removed. Do not maintain a second
old interface for compatibility. Preserve or explicitly migrate dependencies of
actual operations and valid receipts, including necessary assessment/source
anchors. Pending, scheduled and in-flight effects require explicit disposition,
not silent cancellation. Old unused assessments do not all require retention.
Case FKs can cascade into transitions and identity links or block deletion, so
the plan must prove the actual reference graph before removing parents. Evidence retention follows relevance,
identity, event time, duplication and actual references; provider family or prior
HTTP spending alone does not decide value. A required schema change must be
designed and migrated explicitly rather than avoided by an unrelated enum value.
Keep sealed historical evidence accurate as historical evidence, not as the
current display's specification.

Retirement of investigation data is not removal of the securities those rows
mention. Preserve healthy universe/watchlist memberships, holdings, price/news
history, effective identity links and Current/Former suppression/tombstones.
The user need not individually resolve, acknowledge or pay to re-investigate all
old cases. Prepare dependency-aware dry-run deletion/migration effects before
production changes; retain rollback and prove idempotence, old-intake
non-resurrection, SA non-resurrection and unaffected collector behavior. New
task launch, final finding and confirmation must work with the old batch absent.

## 7. Delivery Order And RED Owners

Executable task breakdown:
`docs/superpowers/plans/2026-09-05-lifecycle-tracking-first-implementation.md`.
Its future test names are planned owners, not claims that those tests already
exist or that the amended behavior has been implemented.

1. Amend old-listing retirement semantics across the full binding. Put the RED
   at the decision/proposal boundary: otherwise-complete listing evidence plus
   unavailable events offers old-symbol retirement without claiming no successor.
   Preserve the agreed historical/automatic authority distinction; restore the
   old classification by mutation and require the named offer test to fail.
   Separately own absent, multiple and different-latest-ticker timeline shapes,
   visible continuation candidates, and rejection of the retired reason-only
   attestation bypass. Genuine missing/inactive ambiguity, active OTC evidence,
   conflicting identity, open positions and stale evidence must still block.
   A verified continuation remains the separate positive control. Read old
   snapshots with and without transport blockers after the classifier changes;
   legitimate readback must pass while altered payloads remain rejected.
2. Rehearse ARCH/LTHM/TA again on temporary stores under that policy, then obtain
   separately authorized production previews/receipts. Verify universe and all
   daily watchlists, scheduled price/news scope, SA refresh/alias non-resurrection,
   preservation of history/other sources and governed reversal.
3. Recompute and execute only the separately approved price-repair manifest.
   Distinguish missing/partial bars, legitimate non-trading sessions and unavailable
   history. Read stored bars back; removal alone does not repair historical gaps.
4. Retire the legacy workflow and dispose of the entire existing case set against real
   persisted shapes, not only new provider cases. Own all three input populations,
   virtual-to-persisted identity, composed-versus-visible counts, complete
   input-to-output accounting, duplicate versus distinct-security cases, stale
   accepted assessments and genuinely unresolved current targets. Preserve actual
   dependencies without mandatory history placement for every unused old row;
   reject virtual/source-missing case resurrection after retirement. New tasks
   must work without the old case/observation population. Cover EN/zh-Hant and
   desktop/mobile, no read-triggered provider calls or acknowledgements, healthy aggregate versus
   unresolved item, removal eligibility versus applied state, and continuation
   pending after retirement. Any existing receipts remain readable.
5. Implement the separately bounded web supplement after its adapter and budget
   contract is reviewed. Own short-symbol false matches, acquisition-but-active,
   stale/syndicated stories, partial search, prompt injection, cancellation, no
   credential fallback and no mutation before human confirmation. Include supported
   web-evidence-only removal and same-security rename as positive controls with
   the structured endpoint unavailable, on both legacy and new cases. Own one-click
   apply/readback, conflicting evidence, preview change, duplicate confirmation,
   interrupted execution and future-dated scheduled status. Persist representative
   legacy, automation and earlier human accept-only rows in temporary SQLite;
   prove none substitutes for confirmation of the new packet. Keep a valid fresh
   confirmation and unaffected deterministic automation as positive controls.
   Production-copy rehearsal is separately authorized, not a private-data
   dependency of ordinary tests. A live call requires separate authorization.

For each implementation slice, inventory affected shared consumers and add
regression owners proportional to its impact. Prove the intended target-only
universe/watchlist/collection changes and preservation of other sources, holdings,
history, synchronization, coverage, Research, translation and auth/billing behavior.
Changing a Lifecycle internal contract is permitted; breaking another feature is
not an acceptable unreported side effect.

The new search feature must not postpone completion of the current three-case
tracking and price problems. Historical packets are not re-sealed to imply that
these new rules have already passed. No fixed set of old cases guarantees future
provider coverage; unknown and drift remain observable operational states.
