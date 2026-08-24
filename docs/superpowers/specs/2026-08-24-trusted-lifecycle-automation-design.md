# Trusted Security Lifecycle Automation Design

**Status:** Reviewed design authority. Implementation proceeds only through a
reviewed RED-first plan. Provider calls and live migration remain separately
authorized operations.

**Date:** 2026-08-24

**Base:** `64af5092dd22523c672b8c42e3b84eaba04bec1f`

## 1. Goal

Turn security-lifecycle investigation into an evidence-first automation path:

1. detect listing, delisting, venue, symbol, and issuer events from SEC data;
2. acquire relevant source-language evidence without asking the user to paste it;
3. corroborate identity facts with IBKR market-infrastructure data and the
   existing professional-news corpus;
4. automatically accept only machine-verifiable conclusions;
5. fully prefill every other case for focused review; and
6. schedule or apply only the already-supported reversible ticker transition
   when its action policy passes.

Manual text and URL evidence remain an explicit low-frequency supplement, not
the primary workflow.

## 2. Product Decisions

### 2.1 Two decision tiers

Every successful automation run produces exactly one tier:

- `verified_automatic`: required facts were deterministically extracted from
  cited source-language evidence and the risk-specific corroboration policy
  passed. The assessment is accepted automatically.
- `review_suggested`: the system presents a complete draft with structured
  fields, original excerpts, conflicts, missing corroboration, and proposed
  actions. Nothing is accepted or scheduled until a person acts.

Provider failures, unavailable evidence, parse failures, and source conflicts
are typed run outcomes. They are not a third conclusion tier and cannot be
rendered as an unexplained unresolved case.

Decision tier and action readiness are orthogonal. Every run also returns one
of `not_applicable`, `waiting_effective_date`, `waiting_market_confirmation`,
`transition_eligible`, or `action_blocked`. A verified conclusion may therefore
notify immediately while its profile mutation waits and retries automatically;
missing pre-effective market confirmation does not manufacture human work.

### 2.2 Decision and mutation are separate

An automatically accepted assessment does not imply a profile mutation.

- Venue-only changes, tracked-security-unaffected issuer events, and clear
  asset acquisitions may resolve without a ticker transition.
- A verified simple symbol continuation may create and approve the existing
  `symbol_continuation` transition.
- A verified terminal delisting may create and approve the existing
  `terminal_delisting` transition only after its stricter policy passes.
- Cash, stock, mixed, spin-off, security-class-change, and ambiguous
  transactions never become simple ticker transitions automatically.

### 2.3 Reuse the transition state machine

Do not add `verified_pending_effective`. Existing `status='approved'` plus
`execute_on` already means validated and scheduled for the effective date. The
new dimension is approval authority and rule provenance, not another status.

### 2.4 General web search is fallback, not a live gate

General web search is useful for historical reconstruction, a typed evidence
gap, and pre/post-event impact analysis. It is not mandatory for a live event
that regulator and market-infrastructure evidence have already verified.

This slice emits typed search reasons and a provider-neutral query context for
a later hosted-search adapter. It does not restore Tavily as the default or
make general search a dependency of ticker continuation.

## 3. Grounded Baseline

The approved base contains 36 lifecycle observations, 37 observation kinds, 32
unresolved cases, four resolved cases, four accepted legacy assessments, and
an exact ticker-identity schema. At the last approved live preflight there were
zero investigation runs, evidence rows, ticker transitions, and transition
attempts.

The 36 stored SEC URLs remain valid acquisition pointers. A read-only spike
fetched all 36 primary documents; readable text length was 1,882 to 49,246
characters with an 11,795-character median. Evidence content was not lost; it
was never persisted as normalized evidence.

The same spike found local professional-news and IBKR-news coverage for all 36
cases in a bounded filing-date window. News remains one evidence family no
matter how many vendors syndicate one underlying report.

The historical shadow corpus is deliberately small:

- HAPN: real `LC -> HAPN` symbol continuation and NYSE-to-Nasdaq transfer;
- QBTS: same symbol, NYSE-to-Nasdaq transfer;
- CCL: issuer reorganization where tracked CCL remains CCL; and
- BLBD: asset acquisition without registrant identity change.

HAPN is the only real historical A-to-B example, and its production case is
already keyed by the successor. Passing shadow evaluation is not broad A-to-B
coverage. The first future live A-to-B must therefore be prominently visible
and reversible.

## 4. Source and Time Model

### 4.1 Typed source families

Corroboration evaluates a set of source families, never article/provider count:

| Family | Meaning | Examples | Role |
|---|---|---|---|
| `regulator` | First-party regulatory/exchange evidence | SEC filing, exchange notice | Official event facts |
| `market_infrastructure` | Operational instrument/venue state | IBKR contract details | Mutation corroboration |
| `publisher` | Issuer or professional reporting | IBKR news, SA, Polygon, Finnhub | Context; whole family counts once |
| `general_web` | Hosted-search citation | Future adapter | Gap/context only in v1 |
| `manual` | User-supplied text or URL | Paste or reference | Supplement only |

Different providers and article hashes inside `publisher` do not become
independent votes. `canonical_article_hash` remains dedupe, not corroboration
authority.

### 4.2 Live path

The live path optimizes for low latency:

1. SEC submissions and filing documents establish official facts.
2. The filing chain is joined by normalized CIK, date, accession, form,
   security class, and known ticker aliases.
3. IBKR contract data confirms current symbol/venue identity when available.
   `conId` continuity is strong evidence when present, not a universal premise.
4. Local professional news enriches explanations and exposes conflicts.
5. General web search is asynchronous fallback only for a typed gap.

Future-effective events are assessed and notified immediately. If all action
evidence is already available, the transition is stored as `approved` with
`execute_on`; otherwise action readiness waits for its date/market confirmation
and the automation worker retries without reopening the accepted conclusion.
The existing transition scheduler applies no earlier than the date and
revalidates first.

### 4.3 Historical path

Historical reconstruction may use wider date windows and more context because
latency is no longer primary. It uses the same evidence/fact contracts, so a
later search adapter cannot create a second truth model.

### 4.4 Identity query context

Ticker plus date is insufficient because ticker is the changing field. Every
plan records `case_id`, normalized CIK, issuer, case ticker, known aliases,
known conIds, filing/effective dates, event kinds, accession/URL, and bounded
date window.

The primary filing-chain window is 30 days before through 45 days after the
case filing date. If required identity facts are absent, SEC may widen once to
120 days. Every action is recorded; no provider query is unbounded.

### 4.5 Shared SEC transport authority

SEC's [current fair-access guidance](https://www.sec.gov/about/developer-resources)
limits one user to ten requests per second in total, regardless of how many
machines issue them. The existing
`SECEdgarDataSource` limiter is per instance, so it is not an admissible
authority once the collector, automation worker, financial clients, and CLI
can overlap.

Before the automation worker is enabled, every app-owned SEC request must use
one transport governor shared by all `SECEdgarDataSource` instances. It has an
in-process lock and a fail-closed cross-process `flock`/state-file twin under
the configured ArkScope lock directory. Request starts are spaced by at least
200 ms across the installation. No profile or market transaction may be held
while waiting for the governor. An unavailable, corrupt, or unsupported shared
governor produces `sec_governor_unavailable`; it never degrades to an
instance-local limiter.

This is an installation-wide guarantee, not a distributed lease. Two ArkScope
installations that share one declared SEC identity must not run SEC collectors
concurrently unless they are placed behind a separately reviewed shared
coordinator. This deployment constraint reflects the SEC's user-wide limit
rather than pretending a local file lock coordinates different machines.

One lifecycle automation run is bounded to 16 SEC HTTP attempts, including
retries, at most 12 filing documents, at most 1 MiB per document, and at most
12 MiB of response bodies in aggregate. One scheduler tick starts at most two
cases. A 429 may receive at most one bounded retry, honoring `Retry-After` only
up to 30 seconds; recursive retry is forbidden. Exhaustion is recorded as
`sec_request_budget_exhausted` or `sec_rate_limited`, never as absent evidence.

The shared transport validates a configured, non-placeholder
[declared User-Agent](https://www.sec.gov/about/webmaster-frequently-asked-questions)
before any network syscall. Missing or placeholder identity yields
`sec_identity_unconfigured`; 403, transport failure, and an unavailable
document remain separately typed. Diagnostics may record the configuration
source and outcome but never the contact value. The authority is the
app-managed `sec_edgar/user_agent` setting with the existing explicit legacy
environment aliases.

## 5. Evidence Acquisition

### 5.1 SEC

The worker fetches the observation primary document and a bounded same-CIK
chain. Identity-relevant forms are Form 25/25-NSE, 8-K/8-K/A Item 3.01,
8-A12B, and 8-K12B. M&A forms remain evidence but do not imply continuation.

Persist only bounded source-language excerpts needed for structured facts,
plus filing URL/form/accession/time/section locator, source-document SHA-256,
excerpt SHA-256, retrieval time, and extractor/rule version. Observation
`description` stays compact and is never the sole automation input.

### 5.2 Internal data and IBKR

Search local news first by identity context and bounded dates. This makes no
network call and counts as one `publisher` family.

When IBKR is configured, resolve contract details under the existing gateway
lock and persist a bounded infrastructure snapshot: symbol, local symbol,
conId when present, security type, primary/valid exchanges, currency, and
retrieval time. The worker never rewrites provider-owned values.

Gateway unavailable, missing contract, ambiguity, and entitlement failure are
distinct typed outcomes; none silently becomes "no result."

### 5.3 Original evidence and translation

Every citation renders the verbatim source-language excerpt. On-demand
translation is a derived artifact shown beside, never instead of, the original.
It is labeled machine-generated, keyed by evidence hash and locale, records
provider/model/harness provenance, never satisfies an automatic evidence gate,
and may fail without changing case state.

Reuse card-translation routing/runtime limits, not the analysis-card object
model.

## 6. Deterministic Fact Layer

The extractor emits a fact only with a cited source span. Fact types are:
`source_ticker`, `successor_ticker`, `source_venue`, `destination_venue`,
`effective_date`, `security_class`, `issuer_cik`, `transaction_structure`, and
`tracked_security_effect`. Each stores normalized value, evidence ID, source
span, extraction rule ID, and rule version.

A model may later classify or summarize facts, but cannot be the only source of
ticker, venue, date, CIK, or security class.

Two current cited sources asserting incompatible values for one field create a
typed conflict. Confidence or article majority cannot erase it; the result is
`review_suggested`.

### 6.1 Simple symbol continuation

Automatic acceptance requires all of:

1. regulator evidence explicitly binds old symbol, new symbol, and effective date;
2. normalized CIK matches the case issuer;
3. the cited security class is the same tracked security before and after;
4. no cash-out, ratio, spin-off, acquisition consideration, or new class exists;
5. `market_infrastructure` corroborates successor symbol and venue state;
6. no current fact conflict exists; and
7. the existing transition preview is eligible and unblocked.

If the case is already keyed by the successor, the assessment may be accepted
but no `A -> A` transition is created.

### 6.2 Venue transfer

Explicit regulator evidence plus non-conflicting venue facts may be accepted
automatically. It notifies and keeps tracking; it never remaps a symbol.

### 6.3 No tracked-security identity change

Explicit regulator evidence that the tracked security keeps its identity, or
that an event is an asset acquisition unrelated to issuer identity, may resolve
automatically without a transition. News may enrich it but does not authorize a
mutation because none occurs.

### 6.4 Terminal delisting

Regulator evidence for the tracked security, deterministic effective date, and
no successor in the bounded SEC chain are sufficient to accept the conclusion
and notify before the date. Profile-mutation approval additionally requires
post-effective-date market-infrastructure confirmation, no open portfolio
position, and an eligible unblocked preview. Until then action readiness is
`waiting_effective_date` or `waiting_market_confirmation`, not review.

Only user-owned memberships/visibility are archived or hidden. Broker
positions, provider history, notes, research, prices, and aliases remain.

### 6.5 M&A ambiguity

Cash, stock, mixed, unknown-term, spin-off, and class-changing events never
become simple rename rules. Known terms are prefilled and the run returns
`review_suggested` unless a non-mutating rule is independently proven.

## 7. Assessment and Authority

`security_lifecycle_assessments.author` gains `automation`. Automatic results
are never recorded as `human` or `legacy_review`.

Generation and acceptance are separate:

- `author`: `human | legacy_review | automation`;
- `automation_method`: `deterministic_rule | model_assisted` for automation;
- `acceptance_authority`: `human | automation_policy | legacy_migration` on an
  accepted assessment;
- `automation_run_id`, `rule_id`, and `rule_version` for automation; and
- canonical provenance digest bound to cited facts/evidence.

`model_assisted` is provenance, not permission to bypass deterministic payload
validation. This slice implements deterministic automation and leaves an honest
destination for a separately reviewed model adapter.

- `verified_automatic` creates an automation assessment accepted by
  `automation_policy`.
- `review_suggested` creates an automation draft. Accepting it unchanged uses
  human acceptance authority while retaining automatic authorship.
- Editing a suggestion creates a new human revision; it never rewrites the
  automatic draft.
- Existing legacy rows migrate to `legacy_migration` without invented
  automation provenance.

Changed observation/evidence/facts/rule version/conflicts make an automatic
result stale and re-enter it for automation/review. Auto-resolved cases remain
queryable and manually reopenable.

## 8. Automation Runs

One durable run key comprises case ID, observation fingerprint, automation
policy version, and mode (`live | historical`). A terminal run is not repeated
unless inputs change or a retryable provider outcome reaches its retry time.

The bounded app-owned worker selects changed cases, records running state,
acquires SEC outside profile write transactions, reads local news, optionally
resolves IBKR under its shared lock, atomically persists validated evidence and
facts, produces the tier/assessment, and creates proposals plus an approved
transition only for eligible `verified_automatic` results.

Provider, parser, schema, and internal failures remain distinct. Program errors
are never relabeled as network errors.

Run diagnostics include SEC attempts, documents, bytes, throttling wait,
retries, and remaining budget. Counts come from the shared transport, not from
caller estimates, and are bounded integers with no URL, contact, or body data.

Runs may emit `sec_evidence_insufficient`, `market_confirmation_missing`,
`source_conflict`, or `impact_context_requested` plus their bounded query
context. A later hosted-search adapter consumes that contract and stores
`general_web` citations; it cannot silently alter a completed decision.

### 8.1 Storage contract

The profile authority uses these concrete shapes:

- `security_lifecycle_automation_runs`: run identity, mode, fingerprints,
  policy version, status, decision tier, action readiness, retry time, typed
  blockers, bounded query context, usage/diagnostics, and timestamps.
- `security_lifecycle_automation_facts`: one normalized fact per row with run,
  case, evidence, source span, extractor rule/version, and value JSON.
- evolved `security_lifecycle_evidence`: required `source_family`, optional
  source-document digest and source locator, plus closed trusted adapters.
- evolved `security_lifecycle_assessments`: automation author/method,
  acceptance authority, run/rule identity, and decision-provenance digest.
- `security_lifecycle_evidence_translations`: evidence hash, locale, translated
  text, model execution provenance, and timestamp; never cited as evidence.
- evolved `ticker_identity_transitions`: approval authority, policy/rule
  version, and decision digest.
- `ticker_identity_transition_activity`: append-only applied/reversed events
  with explicit `acknowledged_at`.

Database constraints enforce closed values, SHA-256 lengths, author/provenance
coherence, accepted-assessment authority, and original-evidence references.
Application code additionally validates cross-row family sets and fact spans.

## 9. Transition Authority and Visible Activity

An approved transition records `attended_user | automation_policy` authority,
policy/rule version, and decision digest independently of transition status.

Every applied or reversed transition creates an append-only activity row. The
Lifecycle view shows unacknowledged automatic changes as a persistent first-view
band, not a toast. Each item includes old/new ticker or terminal action,
effective/applied time, user-owned rows changed, provider-owned rows retained,
assessment/evidence links, rule/version, and the current Reverse action or exact
reason reversal is unsafe.

Rendering never marks an item seen. A person explicitly acknowledges it.
Acknowledgement dismisses prominence but is not consent and does not shorten
reversal availability. Reversal remains governed by exact post-state, lineage,
and later-transition guards; there is no arbitrary time expiry.

## 10. UI Contract

The case drawer shows decision tier/provenance; structured old/new symbols,
venues, date, security class, relevance, confidence, event type, and proposed
action; evidence grouped by family; verbatim source-language citations with
links/timestamps; optional adjacent translation; and typed missing/conflicting
evidence. Manual supplement controls are secondary.

`review_suggested` is fully prefilled. A person can accept unchanged, edit into
a new human revision, add supplemental evidence, or leave pending. Facts already
extracted from citations are never retyped merely to accept them.

No fallback label maps an unknown enum to another known outcome/action. Closed
mappings remain compile-time exhaustive in TypeScript, with a truthful unknown
presentation at untrusted boundaries.

The activity band appears before the triage table. Acknowledged items remain in
history and ticker detail.

## 11. Schema Evolution and Live Cutover

This is a new profile-schema migration, not incidental DDL:

1. Rebuild `security_lifecycle_assessments` for honest automation authorship and
   acceptance provenance while preserving four accepted legacy rows exactly.
2. Evolve investigation/evidence storage with typed source family,
   source-document digest/locator, scheduler triggers, and trusted adapters.
3. Add automation-run and cited-fact storage.
4. Add ticker-transition approval provenance and append-only activity storage
   to the currently empty ticker-identity component.
5. Add derived evidence translations separately from authoritative evidence.

Migration code has no default production path. Live cutover requires fresh
read-only preflight, exact mapping for every lifecycle row, an app-quiesced
durable profile backup, scratch restore probe, explicit digest authorization,
locked digest revalidation, and post-migration foreign-key/integrity checks.

Old and new apps use different exact schema authorities. Cutover order is:

1. stop app/scheduler;
2. approve live preflight;
3. create and probe durable backup;
4. migrate with reviewed feature-tree authority;
5. fast-forward reviewed product tree;
6. run merged-tree gates; and
7. start the app.

This migration removes the rollback independence of the prior additive ticker
schema migration. Rebuilding `security_lifecycle_assessments` and adding exact
lifecycle objects causes the old authority to reject the new profile schema.
Under this design a code-only rollback is unsupported: rollback means stopping
the new app, restoring the explicitly authorized pre-migration profile backup,
then starting the old product tree. A forward/down-conversion migration is not
implicitly available. Restoring that backup also discards profile writes made
after cutover, and the live authorization packet must state that consequence.

Before live authorization, the restore probe must do more than compare bytes.
It restores the approved backup to a scratch path, clones that exact restored
state, and boots base `64af5092` against explicit scratch profile and market
paths with schedulers disabled and provider/network access denied. The old
schema verifier and old lifecycle read surface must succeed, including the four
accepted legacy assessments. The probe must prove no production path was
opened. Failure blocks migration; a successful new-code gate is not evidence
that old-code rollback works.

Implementation, merge, provider canary, and live migration approvals remain
separate decisions.

## 12. Verification

### 12.1 Offline fixtures

Fixtures cover:

- HAPN: `LC -> HAPN`, venue transfer, and date;
- QBTS: venue transfer with unchanged symbol;
- CCL: no transition for tracked CCL;
- BLBD: asset acquisition without registrant identity change;
- synthetic A-to-B: eligible preview and automation approval;
- synthetic terminal delisting: only after date and no open position;
- one press report through several providers: one publisher family;
- conflicting successor/date: `review_suggested`;
- provider unavailable: typed retryable result; and
- source citation plus translation: original remains authoritative.
- two concurrent SEC clients: one shared start schedule below the aggregate
  limit;
- a second process contending for the SEC governor: serialized or typed
  fail-closed, never instance-local fallback;
- missing/placeholder SEC identity: zero network calls and
  `sec_identity_unconfigured`; and
- request, retry, document, and byte budget boundaries, including a terminal
  429 with no recursive retry.

### 12.2 Scratch execution

A scratch profile runs:

```text
observation
-> evidence/facts
-> verified automatic assessment
-> proposals
-> automation-policy approval
-> due scheduler application
-> visible activity
-> acknowledgement
-> exact reverse
```

Reverse compares user-owned rows byte-for-byte and proves acknowledgement did
not remove reversal availability.

### 12.3 Shadow evaluation

The four grounded cases run without production writes or provider mutations:

| Case | Expected assessment | Expected transition |
|---|---|---|
| HAPN | symbol + venue change, already normalized | none; `HAPN -> HAPN` forbidden |
| QBTS | venue transfer | none |
| CCL | no tracked CCL identity change | none |
| BLBD | asset acquisition; no registrant identity change | none |

The report states A-to-B historical coverage is `n=1`; it does not claim broad
precision from four examples.

### 12.4 Admission

- Exact RED precedes every behavior implementation.
- Focused parser, family, policy, assessment, transition, scheduler, migration,
  API, and UI tests pass.
- Full backend collection/execution passes.
- Frontend tests, typecheck, visible-literal scan, and production build pass.
- Route/tool inventories match reviewed changes.
- A bilingual desktop/mobile browser matrix has no overlap, console errors, or
  source/translation substitution.
- Offline admission makes zero provider/network calls.

## 13. Non-Goals

- Automatically executing acquisitions, cash-outs, stock exchanges, spin-offs,
  or ambiguous security changes as ticker renames.
- Treating model prose, translated text, article count, or confidence score as
  an independent identity fact.
- Rewriting broker positions, provider history, prices, research, notes, or
  archived evidence.
- Making general web search mandatory for live SEC/IBKR-confirmed events.
- Shipping an OpenAI, Anthropic, Grok, or Tavily hosted-search adapter here.
- Claiming one HAPN example proves broad A-to-B accuracy.
- Modifying/rebasing `64af5092`; prior live migration authority remains bound
  to that exact tree.

## 14. Tavily Disposition

The lifecycle Tavily button, route, adapter, and query-plan path retire before
trusted-source automation is exposed. A fresh migration preflight must prove no
stored investigation/evidence row uses `adapter='tavily'`; otherwise retirement
stops for an explicit data decision.

The generic agent `tavily_search` and `tavily_fetch` tools retire in the same
pre-stage because the user has no planned local-model consumer. Generic
compressor/minifier coverage that merely uses a Tavily-shaped fixture is
retargeted to a surviving tool rather than deleted. Registry/bridge counts and
all exact tool inventories are updated mechanically.

Removing an unused `TAVILY_API_KEY` from the private environment remains a
separate user-owned secret action. Product code stops reading it; this design
does not print, modify, or delete its value.

## 15. Delivery Decomposition

Implementation has five independently rejectable stages:

1. **Tavily retirement:** lifecycle and generic-agent surfaces, exact inventory
   repairs, and a no-stored-Tavily preflight condition.
2. **Evidence/fact kernel:** schema authority, migration tooling, SEC chain,
   shared SEC transport authority and budgets, internal-news/IBKR adapters,
   typed families, facts, and fixtures.
3. **Decision automation:** two-tier policy, honest assessment authorship,
   complete prefill, staleness, proposals, and scheduler witnesses.
4. **Reversible visibility:** transition authority, activity/history,
   acknowledgement, scratch apply/reverse, translation, and UI.
5. **Grounded admission:** four-case shadow evaluation, bilingual browser
   matrix, full gates, and a separately authorized live migration packet.

General hosted search and model-authored lifecycle judgments are later provider
adapters against these contracts, not hidden work inside these stages.
