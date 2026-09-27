# SA Article Relationships And Full-Text Classification

Status: proposed written design for review, not implemented. The operator wants
article relationships visible and editable in the App, separate selection/sale
articles, useful portfolio commentary, and a dedicated selectable-model task.
Routine use must not require manually reviewing every article. Existing browser
collection must continue independently, without classification calls from alarms.

## Existing Behavior And Gaps

The App's News/SA analysis list displays Entry/Exit/Related provenance but has no
relationship editor. The extension's advanced review queue handles unresolved
events only; it is not a complete history. There is no classifier or classifier
model route. Changing the research/translation model does not enable one.

Retain the existing lineage identity `(symbol_key, picked_date)` and distinct
exit dates, accepted-link/rejection history, and deterministic reconciliation.
Captured membership row IDs are not stable event identities. Related coverage
can currently come from provider or legacy ticker metadata without an accepted
entry/exit link. Never rewrite provider identity to represent a model opinion.

The retained article reader already exposes body hashes and continuation, but
its HTTP wrapper returns only the default first 3,500 characters. A classifier
must not use that truncated response as full text. `snapshot_id` also includes
comments/associations, so it cannot be the sole model-result reuse key.

## Selected Delivery

Use an App article workbench plus a dedicated fixed-output classification task.
Two independently testable parts share the relationship authority:

1. App article/event browsing, retained text, accepted links, pending candidates,
   evidence/history, manual accept/reject/replace/revoke/restore, and coverage.
   This works without any model account or classification call.
2. Explicit single-article or selected-batch classification, a dedicated model
   selector, persistent progress/results, and optional application of eligible
   new relationships. Do not reuse the research chat manager as a batch runner.

Extension-only expansion would keep the main workflow hidden from App research.
A single-article-only classifier would be simpler but still require repetitive
operation on the historical backlog. The selected batch is a finite, explicitly
chosen list, processed one article at a time; it is not unattended collection or
an unbounded scan of all history.

## App Workflow

Open the workbench from News/Seeking Alpha and the corresponding pick's related
articles. Show publication date separately from selection/removal date, the
actual stored body/coverage, association role, origin and supporting text.
Provide views for related articles, unresolved events, accepted relationships
and decision history. Existing accepted links must be accessible, not omitted
because the reconciliation queue only shows unresolved work.

Prioritize current Alpha Picks members and recent team commentary by default.
Older entry/exit articles remain reachable. A missing or unusable body is shown
as needing collection, not as an article the model has read. Existing collection
controls remain independent; opening this view never fetches SA pages.

Keep article kind separate from company/event association. Kinds distinguish
company analysis, portfolio/team review, broader market commentary, mixed and
uncertain content. One portfolio review can relate to several companies without
being any company's entry or exit article. Mere company mentions are not proof
of changed conviction or of a selection/removal event.

Manual event decisions reuse the existing lineage/date identity and replacement
history. Company-level Related associations do not invent a pick date. Store
explicit company annotations separately from event-role links and union them
into the existing exact-ticker association reader; retain source provenance.
Do not add another ticker-prefix or short-query substring matching path.

## Classifier Input And Route

Add the fixed task `sa_article_classification` to the existing model-routing,
capability, effective-route, runtime and Settings systems. Select provider/model/
effort/auth channel explicitly for this task; do not silently inherit research
or translation settings. Display the route that will run separately from the
route that produced an older saved result. Reuse existing configured accounts;
do not provision credentials or introduce a new provider SDK.

Preflight reads all retained usable narrative under a consistent local snapshot,
verifies length/body hash, and supplies dated pick/event context and known
company identities. It records coverage as all retained text, not proven
provider-complete content. Charts remain URLs/captions unless a separately
authorized image-reading path exists. Context overflow, missing body or unknown
model capability blocks that article before dispatch; never substitute a title,
summary, copied pick report or silent prefix truncation.

Treat article text as untrusted source data, not instructions. This fixed task
has no browsing, acquisition, trade, arbitrary-code or configuration tools.
Freeze input, route/auth binding, parameters and output schema before dispatch.
Validate source and model-route changes between preview and start. There is no
provider/model/credential fallback and no hidden paid format-repair retry.

## Execution And Cost Controls

Preflight is local-only. It shows selected articles, reusable results, missing
bodies, model route, charge channel and estimated input size. Existing applicable
runtime/spending policy still applies; unknown monetary cost is labelled unknown,
not zero. Do not invent an additional daily quota for this feature.

Starting execution explicitly authorizes the frozen selection. Use one dispatch
per uncached article, serial execution, idempotent request identities and visible
per-article progress. Cancellation stops new dispatches; an in-flight provider
request may already have consumed quota. A process interruption retains completed
results and labels an uncertain in-flight outcome; do not automatically rerun it
or restart a batch on App startup. Resuming/rerunning is a separate user action.

Reuse requires the article/body hash, supplied metadata/event-context digest,
provider/model/effort/auth-channel/adapter identity, prompt hash, output schema,
validator version and generation parameters. Comment additions alone do not
invalidate a body classification. Reuse neither calls the model nor reapplies
rejected/revoked decisions. Each actual execution retains its usage/outcome.

## Evidence And Application

Model output separates article kind, company-related interpretations, and
proposed entry/exit associations. References name existing supplied identities;
the model cannot create a ticker, lineage or exit event. Supply stable passage
IDs from narrative text, excluding headline/disclosure/legal boilerplate as sole
support. The server materializes exact source quotations and verifies their
body version and positions. Quote existence establishes traceability, not the
truth of the model's interpretation; do not present numerical model confidence
as a measured probability.

Offer explicit application modes at execution start: suggest only, or apply
eligible new associations. This avoids mandatory per-article human review while
keeping mutation authority visible. Automatic application requires validated
source/quotation bindings, non-conflicting exact company identity, a unique
supported event for entry/exit, explicit role evidence, unchanged source/context,
and no prior rejection or active conflicting link. Date proximity alone cannot
establish an event; inconsistent launch/backfill dates remain review-only.
Model-labelled uncertainty and ambiguous candidates remain proposals.

Automatic application does not replace any existing accepted link. Replacements
require an explicit user decision with the expected active link identity checked
in the same transaction. Preserve all history and the legacy entry projection.
Mark automatically applied model links with distinct LLM provenance, never
`user` or deterministic-rule `auto`. A human accepting a model proposal retains
both the human decision and its model evidence reference.

Revocation must suppress silent relinking by later deterministic reconciliation
or cached-model reuse; restore is an explicit audited decision. Provider-derived
ticker observations remain stored even when an editable relationship is revoked.
Explain that distinction instead of pretending revocation changed the source.

## Storage And Ownership

Use a reviewed migration after current SA schema 7 for classification runs,
proposals/evidence, editable company associations, distinct LLM link provenance,
and decision history. Keep article/comment collection owners unchanged. Reuse
existing event acceptance/replacement logic through one shared service used by
both App HTTP actions and native extension review, not duplicate writers.

Retain one content-addressed copy of each body version actually dispatched,
deduplicated across reruns, with its context and prompt/schema identities. This
permits old quoted evidence to reopen after a provider body changes without
copying every article/comment snapshot on each run. It is not a new full SA
archive or an authorization to delete old captures. Future retention must honor
active evidence dependencies.

Audit logging alone is not dispatch permission: the current generic permissions
helper is audit-oriented. The preflight/start boundary must enforce explicit
execution and application modes, duplicate-request exclusion and route binding.
Stored GETs, view mounting, source selection, collection and cache misses never
dispatch models or mutate relationships.

## Verification And Integration

Prove manual browsing/editing without a model; exact entry versus exit identity;
multiple exit dates/re-entries; multi-company commentary; accepted-link history;
and consistent exact-ticker results across App, tools and extension reads.

Classifier cases include evidence after character 3,500, changed bodies mid-read,
missing/boilerplate-only text, oversized context, wrong/missing quotation IDs,
provider identity conflicts, event-date ambiguity, concurrent replacement,
model-route changes, duplicate starts, interruption after dispatch, cancellation,
comment-only updates, prompt/model changes and revoked-link reuse. Reject forged
application requests server-side. Test every admitted auth channel with fixtures;
live model execution requires its own explicit operator start and is not implied
by a unit-test pass.

Use independent commits for App manual review, classifier execution, and model
application. Freeze and run full regression before product merge. Schema cutover
requires a separate short stop-write window; no production migration or model
call is authorized merely by this design's presence. Review this written design,
then the implementation plan, before implementation.
