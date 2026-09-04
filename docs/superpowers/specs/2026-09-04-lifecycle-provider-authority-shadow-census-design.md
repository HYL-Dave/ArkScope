# Security Lifecycle Provider Authority Shadow Census Design

**Status:** Provider-free preflight and the separately authorized read-only
Alpha Picks identity census are complete. Offline implementation, any
credential read, provider request, further production database read or any
production write, migration, runtime authority change, App restart, merge,
and push remain separate gates.

**Date:** 2026-09-04

**Base:** `a5b5b9eaac706139c0f28b33313aee1ae7ae2b7b`

**Relationship to existing authority:** This document does not change the
running lifecycle policy. It freezes the experiment required before deciding
whether the SEC-first authority in
`docs/superpowers/specs/2026-08-28-lifecycle-listing-authority-design.md`
should be replaced. A weak or unavailable provider result is a valid census
result and must not be reinterpreted as sufficient authority after the call.

## 1. Goal

Determine, with bounded read-only evidence, which structured providers can
reliably answer four different questions:

1. Is an exact tracked security currently listed?
2. Did the same security change from one ticker to another?
3. Did holders of one security receive a different security in a merger or
   acquisition?
4. Did the tracked security terminate without a verified successor?

These questions must remain separate. A provider that proves listing status
does not thereby prove a successor, and a symbol-change feed does not thereby
prove an economic merger conversion. An acquisition observation also does not
prove that the tracked security has stopped trading and does not revoke the
user's tracking intent. ArkScope keeps the target security tracked while it is
active. Only an independently confirmed terminal listing state or an explicit
user removal may stop its active collection.

## 2. Current Runtime Boundary

The current system remains SEC-first:

- `src/security_lifecycle_investigation.py::compose_security_lifecycle` creates
  live cases from `read_market_observations()` only;
- `src/security_lifecycle_decision_policy.py` requires regulator-derived
  `source_ticker`, `successor_ticker`, `effective_date`, `security_class`, and
  `issuer_cik` before an automatic continuation can be considered; and
- Massive and Nasdaq currently corroborate a candidate produced by SEC. They
  do not discover a successor independently.

The current acquisition handling is split across two incompatible layers. The
assessment vocabulary already represents acquisition outcomes, and
`derive_action_proposal_specs()` currently proposes manual-membership archive
and active-universe hiding for those outcomes when no portfolio position is
open. The profile mutation layer, however, admits only
`symbol_continuation` and `terminal_delisting`; an acquisition outcome receives
`outcome_not_executable` and cannot become an identity transition. Therefore
the current runtime does not automatically apply an acquisition transition,
but it does emit a misleading stop-tracking proposal. The redesign corrects
that proposal without inventing a third identity-transition kind.

The census must not import its adapters into the scheduler, write lifecycle
facts, create proposals, or mutate profile membership. It is a detached
measurement surface.

## 3. Provider Contracts Found During Preflight

### 3.1 Massive All Tickers

`GET /v3/reference/tickers` is included in all Stocks plans and is updated
daily. Exact ticker lookups can return `active`, `cik`, `composite_figi`,
`share_class_figi`, `primary_exchange`, `type`, `delisted_utc`, and
`last_updated_utc`. `active=false` means the asset has been delisted.

The Basic plan exposes only two years of history. Paid Stocks plans expose all
history, with provider records dating back to 2003-09-10. The canary must
record the actual entitlement/coverage result rather than assume the current
credential has all-history access.

This endpoint is a candidate authority for exact listing state and stable
identity. It is not an old-to-new relationship by itself.

Official contract:
`https://massive.com/docs/rest/stocks/tickers/all-tickers`.

### 3.2 Massive Ticker Events

`GET /vX/reference/tickers/{id}/events` is experimental. Its formal contract
currently supports only `ticker_change`. The identifier can be a case-sensitive
ticker, CUSIP, or Composite FIGI. A ticker query describes the entity currently
represented by that ticker; historical entities must be queried through a
stable identifier obtained from reference data.

The endpoint is included in all Stocks plans, but the Basic plan again exposes
only two years of history. Broad knowledge-base prose mentions delistings,
mergers, and acquisitions, but the formal endpoint schema is the admission
authority for this experiment. No result outside the formal `ticker_change`
shape may be treated as a supported contract.

This is one candidate source for same-security ticker changes. It is not
pre-approved as authority for merger consideration or economic successors.

Official contract:
`https://massive.com/docs/rest/stocks/corporate-actions/ticker-events`.

### 3.3 EODHD Exchange Symbol List

`GET /api/exchange-symbol-list/US` is available in all plans. `delisted=0` and
`delisted=1` return disjoint active and inactive sets. The `symbols` parameter
accepts a comma-separated exact set and silently omits unknown symbols, so the
adapter must compare every requested symbol against returned `Code` values.
The endpoint has no pagination and each request is documented as one API call.

This endpoint can corroborate current/delisted state. Its documented result
does not provide a successor relationship or delisting date.

Official contract:
`https://eodhd.com/financial-apis/exchanges-api-list-of-tickers-and-trading-hours`.

### 3.4 EODHD Symbol Change History

`GET /api/symbol-change-history` starts on 2022-07-22, covers US exchanges,
and returns `old_symbol`, `new_symbol`, `company_name`, and `effective`. It is
available only in All World Extended and All-In-One packages, not the free
plan. The documentation describes a five-call charge per ticker while the
endpoint accepts a date window rather than an exact ticker filter. That billing
shape is not sufficiently bounded for an automatic wide-window canary.

This endpoint is a second possible same-symbol-change source, but it is not
currently an executable ArkScope lane: EODHD has no profile-database credential
authority, and the legacy `data_sources/eodhd_source.py` reads an environment
variable through a broad client that does not meet this census contract.

Official contract:
`https://eodhd.com/financial-apis/us-stock-symbol-rename-history-api`.

### 3.5 Contract conclusion

No formally documented Massive or EODHD endpoint found in this preflight
provides a general old-security-to-new-security merger-conversion relation.
There are two candidate symbol-change feeds, but only Massive is both included
in all plans and already backed by an ArkScope profile credential. Neither may
be presumed to resolve the known merger cases before measurement.

## 4. Frozen Known-Case Oracle

The expected answers are fixed before any provider request:

| Case | Required answer |
| --- | --- |
| `LC` | Return an exact same-security `ticker_change` from `LC` to active `HAPN`, with stable-identity agreement. |
| `ARCH` | Independently establish that the old `ARCH` security is terminal/inactive. Any observed relation to `CNR` is an acquisition/conversion classification, is not terminal evidence by itself, and must not create an identity alias. |
| `LTHM` | Independently establish that the old `LTHM` security is terminal/inactive. Any observed relation to `ALTM` is an acquisition/conversion classification, is not terminal evidence by itself, and must not create an identity alias; `ALTM` is evaluated independently. |
| `TA` | Establish terminal/inactive state without creating a successor alias. |
| `AAPL` | Establish active state and return no unrelated rename or terminal event. |
| `SMCI` | Establish exact canonical `SMCI` as active; no provider-marker variant may satisfy the match. |

`LC -> HAPN` is the positive same-security rename canary. `ARCH -> CNR` and
`LTHM -> ALTM` are merger/conversion relationships in their primary-source
histories, not simple ticker renames. Even if a provider reports those
relationships, ArkScope must not redirect identity, move history or holdings,
or create an identity alias to the acquiring or economically different
security. The acquisition alone also must not archive or hide the old tracked
security. A separately confirmed terminal state may stop active collection for
the old security while retaining its history. The acquiring or combined
security may be offered as an independent attended tracking suggestion; it is
added only after explicit user confirmation. The legacy cases still need
attended cleanup in this delivery stage if the structured provider cannot cover
their dates.

`TA` is a common English token. Structured-provider matching must therefore be
bound to an exact requested ticker and stable identifier. A text-search false
positive rate is outside this census; no free-text search is allowed.

The pass line must not be weakened after observing provider output. Failure to
resolve a known answer is a successful experiment outcome that rejects the
proposed authority for that axis. Listing-state authority and same-security
ticker-change authority pass independently; an economic successor is never an
automatic alias.

## 5. Closed Result Vocabulary

Every provider/case/axis result is exactly one of:

- `confirmed`: the exact expected relation or state is present and all identity
  checks pass;
- `contradicted`: a complete response asserts an incompatible state or
  relationship;
- `coverage_limited`: the endpoint or current plan cannot cover the required
  date, event type, or history;
- `not_entitled`: the credential is valid but the endpoint/period is not in its
  plan;
- `credential_unavailable`: the required profile-backed credential is absent;
- `provider_unavailable`: the bounded request cannot produce a valid complete
  response;
- `ambiguous`: identifiers, duplicate rows, incomplete exact-symbol coverage,
  or conflicting providers prevent a unique answer.

Only `confirmed` is positive authority evidence. The other six values are
visible, useful results and must never be converted into `not_found`,
`delisted`, or a successor inference.

## 6. Stage 2 Known-Case Request Budget

Stage 2 is separately authorized and has zero retry, zero redirect, zero
fallback, and zero runtime writes.

### 6.1 Core request envelope

The maximum core envelope is 18 HTTP requests:

- Massive All Tickers: nine exact expected-state lookups for `LC`, `HAPN`,
  `ARCH`, `CNR`, `LTHM`, `ALTM`, `TA`, `AAPL`, and `SMCI`;
- Massive Ticker Events: five stable-identifier lookups for positive rename
  canary `LC`, acquisition/terminal controls `ARCH`, `LTHM`, and `TA`, and
  negative control `AAPL`;
- EODHD Exchange Symbol List: one exact-symbol active request and one
  exact-symbol delisted request for the nine-symbol manifest; and
- Nasdaq Trader: the two existing complete current-directory files.

If an exact Massive reference row lacks a usable Composite FIGI, its event
result is `ambiguous`; the runner must not spend another request by silently
falling back to the potentially reused ticker identifier.

The EODHD lane executes only after EODHD has a profile-database credential
authority. The census resolves the key directly from that authority and never
from `config/.env` or an ambient process variable. Until then, both planned
requests resolve locally to `credential_unavailable` and make zero HTTP
requests. The legacy environment client is prohibited. Whether the project's
general explicit shell-environment escape hatch remains available to other
EODHD call sites is a separate credential-authority decision.

### 6.2 Paid EODHD history gate

EODHD Symbol Change History is outside the 18-request core envelope. Before it
can run, a separate authorization must accept both the paid-plan requirement
and a reviewed cost interpretation. Any approved probe must use narrow frozen
event-date windows, never the full 2022-present history, and must state its HTTP
request and provider call-unit ceiling before execution.

### 6.3 Evidence boundary

The packet records only:

- provider and endpoint family;
- exact normalized requested identifiers and expected state;
- request count, response byte count, HTTP status family, and elapsed time;
- response-body SHA-256 and closed parsed fields needed by the oracle;
- observation time and the closed result code; and
- an aggregate comparison table.

It must not retain API keys, authorization headers, query strings containing a
key, raw response bodies, provider user/account data, unrelated returned rows,
or production database content.

## 7. Stage 3 Full-Universe Census

Stage 3 is allowed only for an axis whose known-case canary passes. The most
recent recorded active-universe projection contains 186 symbols after removal
of the `SMCI*` provider marker, but the runner must build a fresh read-only
manifest under separate production-read authorization and bind its exact row
count and SHA-256. It must not hardcode either 186 or the earlier 187.

The census is split so later costs are known before they are incurred:

1. active-state pass: exactly one Massive exact-active request per manifest
   symbol, two Nasdaq files, and the two EODHD filtered lists if admitted;
2. review checkpoint: freeze the exact missing/ambiguous set and its digest;
3. inactive/event pass: separately authorize exact inactive and event requests
   only for that frozen subset.

No pagination over an unfiltered Massive universe is allowed. No Ticker Events
request is made for an ordinary active symbol. Request budgets are derived from
the sealed manifest and missing subset, not chosen after execution.

## 8. Alpha Picks Identity Feasibility Result

The separately authorized production read used SQLite `mode=ro` with
`PRAGMA query_only=ON` and emitted only aggregate counts and closed shape
classifications. It made no provider request and retained no URL, raw payload,
article text, credential, or token.

The census found 118 persisted pick rows across 106 lineages. All 118
`detail_url` values were ticker-bound `/symbol/<ticker>` URLs with a query or
fragment; none contained a provider Alpha Picks article ID. The URL ticker
matched the persisted symbol for 115 rows. The only three mismatches were the
known `ARCH`, `LTHM`, and `TA` legacy cases. Removing `section_asset` and other
suffixes therefore leaves a ticker-shaped value that changes on exactly the
identity axis this design must repair.

Post-ingestion `canonical_article_id` links covered 89 of 106 lineages with no
current collision, but they are derived through the existing date-bounded
reconciliation after lineage creation. Seventeen lineages, including all
three legacy cases, have none. Pick date is also not unique: seven lineages
occupy shared dates, with as many as five lineages on one date. The database
retains current/closed projections rather than complete historical snapshots,
so this census cannot prove temporal stability for any inferred URL or row
fingerprint.

Consequently, a normalized URL, article link, pick date, or composite of those
fields cannot become the root lineage identity. The previously considered
`source_ref` migration is rejected.

Any later source-membership redesign must satisfy these invariants:

1. SA current and closed rows are provider observations, not active-universe
   membership authority by themselves.
2. Both `sa_alpha_picks_current` and `sa_alpha_picks_former` are projected from
   locally accepted memberships. Ordinary genuinely new Current picks may be
   admitted automatically.
3. A new Current observation is held as a candidate when an exact recent
   lifecycle relation connects its ticker to an existing predecessor and its
   pick anchor matches that predecessor. A broad successor-symbol denylist is
   prohibited because it would also block a genuinely new later pick in the
   acquiring company.
4. A provider-confirmed same-security ticker change may attach a new ticker
   alias to the existing membership. A merger, acquisition, or other economic
   conversion never creates that alias.
5. An acquisition or merger observation does not revoke tracking intent. While
   the old security remains active, its accepted membership and price/news
   collection continue unchanged. Acquisition classification alone cannot
   generate archive or hide actions.
6. A separately confirmed terminal listing state may stop active collection
   for the old security while preserving its membership provenance, history,
   and acquisition relation. It never transfers those records to the acquirer.
   The acquirer or combined security is an independent attended tracking
   suggestion, and acceptance creates a distinct membership.
7. A previously accepted Current membership that is later observed as closed
   becomes Former automatically. A closed row first observed after an ArkScope
   capture gap remains a visible attended candidate rather than silently
   entering or disappearing from tracking.
8. Removing a Former membership records a durable source-specific suppression
   tombstone and append-only provenance. Refresh, bootstrap, and alias
   application cannot clear it; only an explicit Restore command can.
9. Bootstrap admission records actor, time, source observation set, and a
   digest-bound receipt. It is not a directly editable fact table.
10. Identity aliases are resolved before ticker-level `hidden_at` filtering in
   the current implementation. An acquisition alias would therefore redirect
   an old source to the acquirer before the old hidden ticker is removed. The
   no-acquisition-alias rule and membership-level suppression are load-bearing,
   not documentation preferences.
11. Acquisition remains an assessment/relationship state, not a profile
    transition kind. The only source-hiding transition kinds are the closed set
    `symbol_continuation` and `terminal_delisting`. Preview construction must
    test membership in that explicit set rather than treating every non-null
    current or future transition kind as source-hiding.

The exact membership schema and migration are intentionally deferred until
the provider census determines which structured relations can drive rules 3
and 4. These invariants are fixed regardless of storage shape. Any later
related-security suggestion belongs to the membership/advisory surface and
must not require an acquisition identity transition.

## 9. Existing SEC-Seeded Cases

The repository records a prior 36-observation snapshot, including four
resolved/accepted historical outcomes and 32 unresolved cases. A live preflight
must recount these values; this document does not claim they remain current.

If provider authority changes, the semantic migration is fixed as follows:

1. Preserve every original SEC observation, evidence row, fact, assessment,
   run, and activity record for audit. Do not delete or rewrite source history.
2. Preserve already applied transitions as historical activity. Do not reverse
   them automatically; existing attended reversal/readiness rules remain in
   force.
3. Freeze and revalidate every approved but unapplied transition before
   cutover. An old SEC-only decision is not grandfathered into new authority.
4. Mark unresolved legacy cases as requiring one current-policy projection.
   A provider-confirmed event/status can produce a new current assessment
   linked to the legacy observation.
5. If no qualifying structured event exists, remove the legacy candidate from
   the operational automation queue while retaining it in candidate audit with
   an explicit `legacy_candidate_no_current_trigger` reason.
6. `ambiguous`, `contradicted`, `coverage_limited`, or unavailable outcomes go
   to attended review; they do not remain silently active and do not become
   terminal.
7. `ARCH`, `LTHM`, and `TA` are completed in this delivery stage rather than
   deferred. If current structured coverage cannot reach their event dates,
   the already reviewed primary-source listing/delisting evidence, independently
   of the acquisition relation, drives attended terminal transitions after the
   existing open-position guard. No successor alias is created, acquisition
   alone cannot archive or hide the old security, and no application table is
   edited by hand. Any proposal to track an acquirer or combined security is a
   separate attended action and creates a distinct membership only after user
   confirmation.

The storage mechanism for this meaning change is intentionally not selected
before the census. A schema migration, policy-versioned derived projection, or
another mechanism must be reviewed against actual census results. The behavior
above is not optional even if the implementation mechanism changes.

## 10. Decision Outcomes

The census can produce three honest architectures:

1. **Listing status passes; ticker change fails.** Use structured provider data
   for active/inactive monitoring and terminal corroboration. Keep ticker
   changes attended, with SEC/issuer documents as primary-source prompts and
   citations rather than mutation authority.
2. **Listing status and exact same-security ticker change both pass.** Design a
   structured provider-first authority with independent stable-identity
   agreement and an active successor requirement for ticker changes only.
   Economic merger/acquisition successors remain separate securities and
   never become aliases. Acquisition alone neither terminates nor removes the
   tracked target; independently confirmed listing state controls terminal
   retirement. SEC remains supporting provenance and conflict evidence.
3. **Structured status also fails or is unavailable.** Retain SEC candidate
   reminders and attended review; do not perform an authority inversion.

No outcome permits an IBKR miss, stale price, news string, issuer-name match, or
incomplete provider response to authorize a rename or terminal retirement.

## 11. Explicit Non-Goals

This preflight does not:

- change SEC candidate admission, extraction, translation, or the lifecycle UI;
- add an EODHD credential or runtime provider;
- call Massive, EODHD, Nasdaq, SEC, IBKR, or any model;
- perform another production database read or any production write;
- delete the 36 observations or the known `ARCH`, `LTHM`, and `TA` histories;
- change scheduler intervals, request budgets, or automation authority; or
- authorize a migration, App restart, merge, or push.
