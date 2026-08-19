# Security Lifecycle Investigation and Action Proposal Design

**Status:** DRAFT FOR INDEPENDENT REVIEW
**Date:** 2026-08-19
**Base:** `be263855` (`master`; not pushed by this design)
**Priority owner:** `PROJECT_PRIORITY_MAP.md` P0-E, Slice 2
**Scope:** Design only. This document does not authorize product-code edits,
production-data migration, external web calls, profile mutations, merge, or push.

## 1. Problem and authority

The current security-lifecycle surface records SEC observations, then exposes two
manual labels (`inactive_confirmed` and `renamed_or_transferred`). Clicking a
label changes the displayed status, but it does not answer the user's actual
questions:

1. What happened?
2. Does it directly affect the tracked security, indirectly affect its issuer,
   or have no established relationship?
3. What evidence supports that conclusion?
4. Should ArkScope keep tracking, notify, hide, archive, remap, or ask the user
   to inspect a real portfolio position?
5. Can the evidence be reused by AI Research, future research notes, and future
   alerts without binding the product to one search provider or agent harness?

Slice 1 established the safety invariant that a Form 25 class description is
evidence, not a relevance or severity decision. Slice 2 owns the missing
investigation and disposition layer.

### 1.1 User rulings carried into this design

- Direct events affecting a tracked security, including delisting, venue
  transfer, symbol change, and acquisition, must remain visible and may justify
  an explicit remove, remap, notify, or later bounded-automation action.
- An event involving another security of the same issuer is not discarded. It
  remains issuer-related evidence because it may still affect the company and
  therefore the tracked investment.
- Web search may be used to investigate, but Tavily, OpenAI-hosted search,
  Anthropic-hosted search, and future providers are replaceable adapters. The
  normalized case/evidence contract is the product asset.
- Text, image, and PDF evidence are useful, but binary/document understanding is
  a separate Document Intelligence workstream. This design may expose an opaque
  integration point; it may not pretend that ingestion already exists.
- The desired end state may include unattended research and alerts. The first
  implementation remains attended and reviewable because permission enforcement,
  alert product design, and cross-store action execution are not complete.

## 2. Grounded current state

These are observed facts at the design base, not future claims.

### 2.1 Storage and production projection

- `src/security_lifecycle.py` stores provider observations in
  `security_lifecycle_observations` and possible M&A pairs in
  `corporate_action_relationships`.
- `event_type` and `lifecycle_state` are SQLite `CHECK` vocabularies.
- `lifecycle_state` currently mixes provider observation with conclusion-like
  values. `read_security_lifecycle()` then overlays `reviewed_state` on top of
  the observed value for display.
- The read-only production query on 2026-08-19 returned `integrity_check=ok`, 37
  observations, and zero relationship rows:

| Observation event | Raw state | Review state | Count |
|---|---|---|---:|
| `acquisition_completed` | `review_required` | null | 5 |
| `listing_removal_notice` | `pending_delisting` | `renamed_or_transferred` | 2 |
| `listing_status_review` | `review_required` | null | 1 |
| `listing_status_review` | `review_required` | `renamed_or_transferred` | 2 |
| `merger_agreement` | `review_required` | null | 21 |
| `merger_proxy` | `review_required` | null | 6 |

- The current collector no longer emits `pending_delisting`. The value survives
  only in schema, tests, frontend copy, and two rows that have not yet been
  re-observed.
- Thirty-two M&A observations coexist with zero relationship rows. The current
  narrow phrase extractor is not an investigation owner.

### 2.2 API and UI

- `GET /market-data/security-lifecycle` is a local read and performs no provider
  work.
- `PUT /market-data/security-lifecycle/events/{id}` only stores one of two review
  labels (or clears it). It explicitly does not change Universe membership.
- The Settings table exposes `Confirm inactive`, `Mark renamed/transferred`, and
  `Clear review`. It has no investigation run, evidence list, impact statement,
  successor symbol, consideration terms, or action result.
- The current Settings placement is an operational/data-health surface. A
  portfolio-relevance investigation is a Universe workflow, not a Settings
  mutation form.

### 2.3 Active-universe and symbol ownership

`src/active_universe.py` combines four independent source owners:

```text
manual_lists
portfolio_open
sa_alpha_picks_current
legacy_config_seed
```

`ticker_meta.hidden_at` can suppress a ticker from the combined projection, but
that is a broad profile-state action. Archiving a ticker only archives its
manual watchlist memberships. A real portfolio position cannot be removed by a
lifecycle workflow. SA and legacy sources also retain their own truth even when
the combined projection is hidden.

The read-only production check found `QBTS`, `HAPN`, `V`, and `LLY` in the
manual `Core` list and in none of the other three source families. That is an
observation about today's profile, not a general action rule.

`market_data.db.ticker_aliases` is a price/news/fundamental spelling and history
canonicalization table. It includes static seeds such as `LC -> HAPN`; it is not
a reviewed corporate-action authority and must not receive investigation output
directly.

### 2.4 Search, model, permission, and downstream capabilities

- `src/tools/web_tools.py` exposes direct Tavily search/fetch and Playwright
  browse functions. The generic functions return provider-shaped payloads and
  catch broad exceptions; they are not a lifecycle evidence owner.
- The OpenAI and Anthropic agent paths also have provider-hosted web-search
  tools. Those calls are embedded in an agent response rather than exposed as a
  common deterministic search-result API.
- `src/api/permissions.py` declares `external_web_access`,
  `external_browser_automation`, `db_write`, and `profile_state_write`, but its
  ASK/auto-approve enforcement is not implemented. It currently audit-logs only.
- AI Research and the central `ToolRegistry` are live. Ticker notes are live.
  The future Notes and Alerts product surfaces are not live owners for this
  workflow.
- The current monitor subsystem is an older watcher/router implementation. This
  design does not make it the lifecycle-alert authority.
- `ARKSCOPE_SEC_USER_AGENT` is currently unset. Live SEC work must not be used
  as an implementation admission gate until the operator supplies a valid
  contact value through the existing provider setting.

### 2.5 Document Intelligence boundary

The referenced `firecrawl/pdf-inspector` project can classify PDFs and expose
native-text extraction plus pages needing OCR. Whether it is accurate enough
for ArkScope's multilingual, table, chart, and image cases requires its own
grounding spike. Slice 2 stores a document reference and extraction status; it
does not vendor the project, choose an OCR model, upload binaries, or claim PDF
understanding.

## 3. Product model

The system must separate facts, investigation work, judgments, and side-effect
proposals.

### 3.1 Observation

An **observation** is an append-stable provider fact such as an SEC filing. It
owns source identity, filing metadata, source URL, bounded description, and
first/last observed timestamps. It does not own portfolio relevance, severity,
or a user action.

Re-observation may refresh bounded source fields and `last_observed_at`; it may
not overwrite an accepted assessment.

### 3.2 Case

A **case** is the durable investigation identity for one observation. Its ID is
derived from the canonical UTF-8 bytes of the observation's existing unique key:

```text
SHA256("security-lifecycle-case-v1" NUL
       source NUL source_ref NUL ticker NUL event_type)
```

The public form is `slc_` plus the lowercase 64-character digest. Values are the
validated, stored observation values, not a second normalizer. The ID therefore
exists before any user-state row is written. An untouched
observation projects as an unresolved case without causing a read-side write;
the profile case row is created only when investigation state is first stored or
when a legacy review is migrated.

All four components must reject embedded NUL before hashing. Migration stops on
such a value rather than changing or ambiguously encoding an existing identity.

The first implementation is strictly one case per observation. Grouping several
filings into one transaction may be useful, but automatic date/name similarity
must never merge cases. Case merge is a separately reviewed follow-on.

The case's visible workflow state is derived:

```text
unresolved       no accepted conclusive assessment
investigating    latest run is queued or running
evidence_ready   evidence exists and no conclusive assessment is accepted
resolved         a conclusive assessment is accepted
```

These labels are projections, not another mutable truth column.

### 3.3 Investigation run

An **investigation run** records one bounded attempt to gather external evidence.
Its closed status vocabulary is:

```text
queued | running | succeeded | failed | cancelled
```

It records trigger, adapter, query plan, start/finish timestamps, bounded usage,
and a typed failure code. A failed retry never clears evidence from a prior
successful run.

The first implementation permits only `trigger=attended_user`. Scheduler,
automatic retry, and alert-triggered runs are out of scope.

### 3.4 Evidence

An **evidence item** is immutable, bounded, and source-addressable. Its initial
kind vocabulary is:

```text
web_search_result
web_page_excerpt
manual_url
manual_text
document_reference
```

Required provenance includes `case_id`, source URL when applicable, title,
publisher/domain, source/published/retrieved timestamps when known, adapter,
bounded excerpt, content hash, MIME type when known, and the originating run.
Missing fields remain null; they are not inferred.

Provider-generated answers and relevance scores are leads, not evidence. A
claim must cite one or more URL-addressable or user-supplied evidence items.
Full third-party pages are not copied into the database; only bounded excerpts
and provenance are retained.

`document_reference` stores only its external reference/provenance and one of:

```text
not_inspected | extraction_needed
```

The current slice creates no binary artifact store. A later Document
Intelligence owner may add `extracted` and `extraction_failed` only when it also
owns the artifact and extraction records; v1 does not reserve dead status values.

### 3.5 Assessment

An **assessment** is a versioned judgment over cited evidence. Draft and accepted
assessments are distinct; accepting a revision supersedes the prior accepted
revision without deleting history.

Assessment status:

```text
draft | accepted | superseded
```

Relevance:

```text
undetermined
direct_tracked_security
issuer_related
unrelated
```

Outcome is multi-valued because one event can both change a symbol and end a
listing:

```text
undetermined
listing_ended
venue_transfer
symbol_changed
symbol_or_venue_changed
acquisition_cash
acquisition_stock
acquisition_mixed
acquisition_terms_unknown
issuer_security_change
no_tracked_security_change
other
not_applicable
```

Confidence:

```text
unknown | low | medium | high
```

Queryable transaction fields are nullable and remain null when evidence does
not establish them:

```text
counterparty_name
counterparty_ticker
counterparty_cik
successor_ticker
destination_venue
effective_date
consideration_currency
cash_per_security_decimal
exchange_ratio_decimal
```

Monetary amounts and ratios are canonical decimal strings, never binary floats.
The assessment's prose may explain more complex terms, but names, successor
identity, venue, date, cash, and exchange ratio may not exist only inside prose
when known. These fields replace the useful intent of the empty legacy
relationship table without reviving its regex-derived candidate authority.

An accepted, resolved assessment must:

- use relevance other than `undetermined`;
- use at least one non-`undetermined` outcome;
- cite at least one provider observation or profile evidence item;
- include a bounded conclusion and impact summary; and
- identify the author as `human` or `legacy_review`.

The first implementation has no model assessment writer. A later model-assisted
assessment feature must write only `draft` revisions under a separately added
author value; confidence never grants permission to mutate profile state.

`symbol_or_venue_changed` exists only to preserve the old UI's deliberately
ambiguous `renamed_or_transferred` judgment. New UI/API assessments cannot create
it; they must select the precise outcome or remain undetermined.

### 3.6 Action proposal

An **action proposal** is a reviewable recommendation derived from an assessment
and an active-universe source snapshot. It is not the action itself.

Initial action vocabulary:

```text
notify
keep_tracking
archive_manual_memberships
hide_from_active_universe
review_portfolio_position
remap_symbol
no_action
```

Initial proposal status is:

```text
proposed | dismissed
```

The separately reviewed action-executor slice decides whether to extend this
vocabulary or add an execution ledger. V1 does not reserve status values that
have no writer.

Each proposal stores the assessment revision, source ticker, optional
replacement ticker, the literal active-universe source snapshot, bounded reason,
and any block reason. It therefore remains intelligible even if the live
Universe changes later. `Investigate` is a case workflow command, not an action
proposal: an unresolved case has no accepted assessment revision from which an
action proposal could honestly be derived.

## 4. Storage design and migration

Storage follows the existing durability boundary:

| Store | Lifecycle owner |
|---|---|
| `market_data.db` | Provider observations and company-event metadata |
| `profile_state.db` | User-triggered investigation runs, external/manual evidence, assessments, and proposals |

The API composes the two explicit stores by stable case ID. It never treats one
store as a fallback for the other: if either required store is unavailable, the
case projection is typed unavailable.

Applying a proposal mutates other, existing profile tables in a separate future
operation. The investigation tables do not become another watchlist authority.

### 4.1 Observation table correction

`security_lifecycle_observations` is rebuilt transactionally to remove:

```text
lifecycle_state
reviewed_state
reviewed_at
```

The provider-owned event fields and row IDs remain unchanged. `event_type`
continues to classify the source observation; it does not select a case result.

This rebuild explicitly retires `pending_delisting` from product schema and UI.
It also removes `inactive_confirmed` and `renamed_or_transferred` from the
observation table because they are assessments, not observations.

### 4.2 New tables

The implementation plan must define deterministic DDL in `profile_state.db` for
at least:

```text
security_lifecycle_cases
security_lifecycle_investigation_runs
security_lifecycle_evidence
security_lifecycle_assessments
security_lifecycle_assessment_outcomes
security_lifecycle_assessment_evidence
security_lifecycle_action_proposals
```

`security_lifecycle_cases` stores the deterministic case ID and the literal
observation unique-key components; it contains no copied filing prose. An
untouched observation needs no row. Foreign-key relations inside
`profile_state.db`, unique case/observation ownership, bounded text lengths,
closed vocabularies, and stable sort orders are required. SQLite cannot enforce
an FK into `market_data.db`; the case-to-observation reference is instead
validated by the composition layer, migration coordinator, and admission gates.

Assessment citations distinguish `observation` references (the stable case's
provider fact in `market_data.db`) from profile evidence IDs. JSON may hold a
bounded source snapshot or adapter diagnostic, but it may not replace fields
that drive filtering, joins, or permissions.

### 4.3 Legacy review migration

Every existing observation obtains a deterministic projected case identity. The
observation itself is the first evidence reference; its filing fields are not
duplicated into profile state. Rows with no `reviewed_state` remain projected,
unresolved cases and create no profile row during migration.

`inactive_confirmed` migrates to an accepted `legacy_review` assessment with
`direct_tracked_security + listing_ended` and an explicit note that the old UI
captured no supporting rationale.

`renamed_or_transferred` migrates to an accepted `legacy_review` assessment with
`direct_tracked_security + symbol_or_venue_changed`. The old label expressed an
OR, so migration must not turn it into evidence that both events happened. It is
preserved, not silently made more precise.

No action proposal is synthesized from a legacy label.

### 4.4 Corporate relationship table

`corporate_action_relationships` has no production rows and no successful owner
for the 32 M&A observations. The implementation retires the narrow relationship
extractor and table; relationship conclusions move into cited assessments.

The production migration must hard-stop before any schema change if the table is
non-empty at the migration snapshot. A non-empty table requires an amendment
with an explicit row-preservation mapping; it must not be dropped or guessed.

### 4.5 Migration protocol

The implementation plan must include:

- a fresh read-only preflight of schema, row IDs, row counts, review-state
  vocabulary, relationship count, and `PRAGMA integrity_check`;
- complete Desktop, sidecar, scheduler, and collector quiescence before the live
  schema operation;
- timestamped local backups of both SQLite files plus a SHA-256 manifest outside
  ephemeral `/tmp`, with verified per-file restore and a coordinated rule that
  neither restored database is reopened until both are back in place;
- an explicit two-store migration coordinator rather than a false claim of one
  cross-database atomic transaction;
- phase 1: one `profile_state.db` transaction that writes the four legacy case
  rows/assessments plus a migration receipt keyed by the market snapshot hash;
- phase 2: one `market_data.db` transaction that rebuilds the observation table
  after phase 1 is verified;
- phase 3: mark the profile migration receipt complete only after both stores
  and their cross-store case keys verify;
- row-ID preservation, count equality, foreign-key checks, and post-migration
  `integrity_check`;
- idempotent resume or restoration from both backups after interruption at any
  phase; lifecycle writes remain unavailable while the receipt is incomplete;
- rollback on any unknown review value, missing source field, count mismatch, or
  non-empty relationship table; and
- pre/post production manifests proving that only the authorized lifecycle
  tables in `market_data.db` and `profile_state.db` changed.

An application-startup migration may be implemented only if the same resumable
coordinator is directly testable and uses each store's real writer lock. The live
admission still follows the quiesced protocol; startup is not permission to
mutate active production databases during tests. No compatibility read fallback
to old review columns remains after a complete migration.

## 5. Investigation architecture

### 5.1 Selected shape

Use a domain-owned `LifecycleSearchAdapter` protocol. The lifecycle orchestrator
owns query planning, permission calls, budgets, normalization, persistence, and
failure semantics. An adapter owns only provider transport and provider-response
decoding.

Conceptual input:

```text
case identity
issuer/ticker/CIK
observation type/date/form/accession
known evidence URLs
bounded query and result budgets
```

Conceptual output:

```text
adapter identity
queries issued
typed attempt status/usage
normalized search results and source URLs
optional fetched excerpts
```

No adapter returns or writes an accepted assessment.

### 5.2 First concrete adapters

The first implementation supports:

1. `manual`: always available; adds an HTTPS URL or bounded user text without
   network access.
2. `tavily`: the first network adapter because the repository already has a
   direct search/fetch client shape that can be normalized without running a
   generic agent loop.

The lifecycle adapter must not call `ToolRegistry.execute("tavily_search")` as
its domain boundary. It may reuse the underlying library/configuration, but it
must add typed failures, permission calls, bounded persistence, and secret-safe
diagnostics instead of inheriting the generic tool's broad exception payload.

`openai_hosted_search` and `anthropic_hosted_search` are deferred adapters. Each
requires a real-account canary proving that cited sources, query attempts,
provider identity, usage, and failure states can be normalized without parsing
free-form prose. Existing hosted-agent tool availability is not that proof.

`web_browse` is excluded from this slice because it requires the distinct
`external_browser_automation` permission.

### 5.3 Query plan and source priority

The orchestrator uses bounded deterministic query families rather than asking a
model to invent an unbounded browsing plan:

1. official filing/exchange/issuer identity and event query;
2. symbol, venue, delisting, and successor query; and
3. acquisition/merger consideration query for M&A observations.

Official SEC, exchange, and issuer sources are preferred, followed by reputable
reporting. Search rank never becomes source authority. Conflicting evidence is
preserved and forces `undetermined` until a reviewer accepts a conclusion.

Default run bounds are three queries, five results per query, and five selected
fetches. The implementation plan may tighten these values but may not remove
the bounds.

### 5.4 Permission and failure boundary

- Every network run calls `external_web_access` before egress.
- An adapter that incurs separately metered spend also calls `metered_spend`.
- Because real ASK enforcement is absent, v1 additionally requires an explicit
  user click for every run. Focus, mount, refresh, polling, and case opening must
  issue zero external requests.
- No scheduler or background retry may start an investigation.
- HTTPS URLs only; local/private/link-local targets and unsafe redirects are
  rejected before fetch.
- Search snippets and fetched excerpts are untrusted data. HTML/script content
  is removed before persistence, and any later model prompt places excerpts in
  an explicitly delimited evidence block whose contents cannot authorize tools,
  permissions, or instructions.
- Adapter failures use a closed reason set such as `adapter_unavailable`,
  `credential_missing`, `permission_denied`, `rate_limited`, `network_error`,
  `no_results`, `extract_failed`, and `unsupported_content`.
- Raw provider exception text, API keys, private paths, full response bodies,
  and model chain-of-thought never enter product records.

## 6. API, tools, and UI

### 6.1 Local API

The implementation plan may refine route names, but the behavioral surface must
cover:

```text
GET  /security-lifecycle/cases
GET  /security-lifecycle/cases/{case_id}
POST /security-lifecycle/cases/{case_id}/investigations
GET  /security-lifecycle/investigations/{run_id}
POST /security-lifecycle/cases/{case_id}/evidence
POST /security-lifecycle/cases/{case_id}/assessments
POST /security-lifecycle/assessments/{assessment_id}/accept
POST /security-lifecycle/action-proposals/{proposal_id}/dismiss
```

Case/evidence/assessment writes are additive analysis records and call
`db_write` even though their durable store is `profile_state.db`; permission
class follows behavioral meaning, not filename. Any future tracked-universe
action calls `profile_state_write` separately.

The old event-review and relationship-review routes retire atomically with their
frontend consumers. No compatibility alias or hidden fallback remains.

### 6.2 Agent-facing tools

Add exactly two initial local read tools to the central registry and both live
agent bridges:

```text
list_security_lifecycle_cases
get_security_lifecycle_case
```

They return observations, evidence refs, accepted/draft assessment metadata, and
proposals from local storage. They perform no network access and no writes.

There is no agent-facing `apply_lifecycle_action` tool in this slice. Generic AI
Research may cite case evidence and may suggest a draft in prose, but it cannot
silently convert that prose into a profile mutation.

### 6.3 Product surface

The lifecycle workflow moves to a `Lifecycle` view under `Universe`:

- one compact triage table for cases;
- filters for workflow state, relevance, event type, and proposal type;
- a detail drawer showing source observations, current active-universe source
  membership, investigation history, evidence, assessment, and proposals;
- `Investigate` to open the case, followed by an explicit
  `Search web with <adapter>` command that names the external provider and
  performs the only network-triggering click;
- `Add evidence` for manual URL/text;
- explicit assessment controls with cited evidence selection; and
- proposal rows that explain what would change and why they are not yet applied.

Settings retains only a compact storage/health summary and a link to the
Universe lifecycle view. It does not retain review buttons.

The old `Confirm inactive`, `Mark renamed/transferred`, and `Clear review`
commands retire. Migrated legacy assessments remain visible in the drawer with
their limited provenance.

The UI must never describe `review_required` as a delisting conclusion. The new
primary labels are `Unresolved`, `Investigating`, `Evidence ready`, and
`Resolved`.

## 7. Source-aware action policy

Investigation and action application are separate transactions. The proposal
engine snapshots `sources_by_ticker` and follows this matrix:

| Active source | Permitted proposal | First-slice application |
|---|---|---|
| `manual_lists` | archive memberships, keep, notify, remap | proposal only |
| `portfolio_open` | review position, notify | never auto-remove or auto-hide |
| `sa_alpha_picks_current` | keep, notify, broad hide | proposal only; do not mutate SA truth |
| `legacy_config_seed` | keep, notify, broad hide | proposal only; do not rewrite seed here |
| mixed sources | union of safe proposals with all sources displayed | proposal only |

Proposal generation is deterministic over the accepted assessment and source
snapshot; an LLM does not choose an action. The minimum mapping is:

| Accepted assessment | Proposal direction |
|---|---|
| `issuer_related` | `notify` + `keep_tracking` unless the user decides otherwise |
| `unrelated` | `no_action` |
| direct `symbol_changed` or `venue_transfer` | `notify` + `remap_symbol` |
| direct `listing_ended` without successor | source-aware archive/hide/position review |
| direct acquisition outcome | `notify`, then remap/archive/position review according to successor and consideration evidence |

Rules:

- `hide_from_active_universe` is broad suppression, not deletion. It must display
  every source it would mask.
- If the active-universe projection is unavailable, evidence collection may
  continue but proposal generation is blocked with
  `source_context_unavailable`; it never assumes that the ticker is untracked.
- `archive_manual_memberships` affects manual lists only.
- An open portfolio position blocks any hide/remap proposal and produces
  `review_portfolio_position` instead.
- `remap_symbol` requires an accepted direct assessment, a successor ticker,
  cited evidence, and a future cross-owner executor. It must not write directly
  to the static `ticker_aliases` seed.
- No action type places orders, closes a broker position, edits SA capture truth,
  or rewrites historical market rows.
- Later automation must be separately approved, source-aware, idempotent, and
  reversible. Model confidence alone is never an automation gate.
- A future executor must re-read the active-universe sources and reject a stale
  proposal rather than trusting its historical source snapshot.

## 8. Integration boundaries

### 8.1 AI Research and future Notes

The two local read tools are the stable integration contract. AI Research may
ask for a case and its evidence without knowing the search provider. A future
research note stores case/evidence IDs rather than duplicating or silently
refreshing the investigation.

No lifecycle result is injected into every research prompt. The caller requests
it by ticker/case or follows an explicit scoped entry point.

### 8.2 Future Alerts and unattended work

An accepted assessment or newly opened case can later emit a normalized local
event containing case ID, ticker, relevance, outcomes, evidence refs, and
timestamp. Alert routing and transports, including Discord, remain owned by the
future Alerts design. This slice does not import the old monitor router or bind
to a transport.

Unattended web investigation waits for all of:

1. real external-web and metered-spend permission enforcement;
2. explicit scheduler policy and budgets;
3. typed retry/dedup ownership; and
4. user-approved alert/action behavior.

### 8.3 Document Intelligence

Text can enter as bounded `manual_text`. A URL may enter as `manual_url` or
`document_reference`. Images and PDFs remain references until a separately
approved Document Intelligence adapter produces bounded extracted evidence.

That workstream decides native-text extraction, page-level OCR routing, vision
model selection, tables/charts, multilingual behavior, privacy, and artifact
retention. Slice 2 does not select `pdf-inspector` or an OCR model on its behalf.

## 9. Alternatives considered

### A. Keep the current table and add a search button

Rejected. It preserves the false model in which a review label is both evidence
and conclusion, and it still cannot explain or apply an action.

### B. Launch generic AI Research and treat its answer as the case

Rejected as the storage owner. It couples lifecycle truth to a harness/provider,
does not guarantee normalized citations, and cannot safely drive profile state.
AI Research remains a consumer of the stable case/evidence tools.

### C. Add class-based Form 25 relevance heuristics

Rejected. Real listed tickers can represent common stock, ADS, units, preferred
stock, warrants, rights, or debt. Class text cannot establish whether the filing
is direct or issuer-related.

### D. Autonomous search plus automatic remove/remap

Rejected for the first implementation. Permission enforcement, provider budgets,
portfolio ownership, cross-database identity migration, and alert policy are not
ready. The design preserves proposals so automation can be added without
replacing the evidence model.

### E. Case/evidence kernel plus attended investigation and proposals

Selected. It solves the user-visible dead-end now, keeps providers and harnesses
replaceable, and leaves action execution and richer document intelligence behind
explicit boundaries.

## 10. Implementation sequence

The later implementation plan must be RED-first and split at these semantic
boundaries:

1. **Case kernel and migration**: rebuild observation truth, migrate legacy
   reviews, create case/evidence/assessment tables, retire the empty relationship
   extractor/table and dead UI vocabulary.
2. **Attended investigation**: manual evidence plus Tavily adapter, typed run
   lifecycle, permissions, budgets, and source normalization.
3. **API and local tools**: case detail, evidence/assessment writes, two read-only
   agent tools, no action executor.
4. **Universe workflow**: lifecycle triage view and drawer; Settings becomes
   health/link only; old review buttons retire.
5. **Admission**: migration recovery, mutations, full backend/frontend suites,
   real-browser explicit-click ledger, sanitized startup, no-production-open
   proof, and live provider canary only after operator configuration and separate
   approval.

Follow-on lines, not hidden tasks in this implementation:

- source-aware action executor and reviewed symbol-identity transition;
- model-assisted assessment drafts;
- OpenAI/Anthropic hosted-search adapter canaries;
- Document Intelligence and binary artifact ingestion;
- Alerts/unattended investigation; and
- broader corporate relationship graph/dedup.

## 11. Verification contract

The implementation plan must pin exact owners and staged identities, but at
minimum it must prove:

1. A source observation can be written without any relevance, severity, or
   portfolio conclusion.
2. Every existing observation ID and source field survives the transactionally
   rebuilt production-shaped schema.
3. The four current legacy reviewed rows migrate to visible accepted
   `legacy_review` assessments; 33 untouched observations project as unresolved
   cases without read-side writes at the current snapshot.
4. `pending_delisting`, `inactive_confirmed`, and
   `renamed_or_transferred` have zero product/schema/UI use after migration,
   except bounded migration tests naming retired inputs.
5. A non-empty legacy relationship table aborts migration without changing any
   byte of the source database.
6. Form 25 class text survives as evidence and cannot alter case relevance,
   outcome, or proposal.
7. Opening, focusing, refreshing, polling, and switching views issue zero web
   requests. One explicit investigate click issues exactly one bounded run.
8. Adapter failure leaves the case and prior evidence intact and exposes only a
   typed safe error.
9. Conflicting or unknown evidence cannot produce a conclusive accepted
   assessment without explicit human action.
10. The two agent tools compose the explicit market observation and profile case
    stores with zero network and zero writes.
11. Investigation writes touch only the new lifecycle case tables in
    `profile_state.db`. They do not mutate observations, watchlist membership,
    `ticker_meta`, portfolio, SA, market history, or a production provider.
12. `portfolio_open` context can produce `review_portfolio_position` but cannot
    produce an executable remove/hide path.
13. The UI shows source, evidence, conclusion, impact, and proposal as separate
    concepts at desktop and mobile widths without overflow.
14. External URL handling rejects local/private targets and unsafe redirects.
15. Full canonical backend/frontend admission remains green with deterministic
    collection identities and byte-restored mutations.

## 12. Hard stops

Stop and amend before continuing if any of these occurs:

- production relationship rows are non-zero at migration time;
- an existing review value cannot be mapped literally;
- preserving observation IDs or source evidence requires guessing;
- a search adapter must parse free-form model prose to discover its sources;
- a provider/harness-specific field enters the case, assessment, or action
  contract;
- investigation requires browser automation, binary upload, OCR, or arbitrary
  file access;
- any attended investigation starts without an explicit user command;
- any test or investigation opens a production database outside the authorized
  lifecycle writer protocol;
- any proposal is applied as a side effect of search or model inference;
- action execution needs to mutate a portfolio position, SA truth, legacy seed,
  static ticker alias seed, or more than one database;
- UI completion requires inventing a Notes or Alerts product owner;
- live SEC evidence is required while `ARKSCOPE_SEC_USER_AGENT` remains invalid;
  or
- schema/identity/runtime counts differ from the implementation plan's fresh
  grounding.

## 13. Design handoff

Independent review should focus on:

1. whether observation, case, assessment, and proposal remain non-overlapping;
2. whether legacy review migration preserves truth without promoting weak labels;
3. whether the first Tavily adapter can be replaced without data migration;
4. whether active-universe source ownership makes every proposal honest;
5. whether the migration is recoverable under an external-writer environment;
6. whether the first implementation is useful without pretending that action
   execution, hosted search, Document Intelligence, Notes, or Alerts already
   exist; and
7. whether any current product path can still turn class wording into relevance.

Only a GREEN design review unlocks the RED-first implementation plan.
