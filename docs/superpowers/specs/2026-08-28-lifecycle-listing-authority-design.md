# Security Lifecycle Listing Authority Design

**Status:** Approved for RED-first implementation. Provider calls, production
database reads or writes, migration, merge, live cutover, and push remain
separate authorization gates.

**Date:** 2026-08-28

**Base:** `fda1641fa35eeef9d8ff2b582e99faefcf774c34`

**Supersedes only:** the use of `publisher` evidence as an automated lifecycle
decision input in
`docs/superpowers/specs/2026-08-24-trusted-lifecycle-automation-design.md`
and
`docs/superpowers/specs/2026-08-26-lifecycle-resolution-and-translation-continuation-design.md`.
All other approved evidence, transition, reversal, acknowledgement, and
translation contracts remain in force unless this document says otherwise.

## 1. Goal

Make Security Lifecycle a bounded watchlist-maintenance system rather than a
second news reader.

The system must answer the operational questions that can change the tracked
Universe:

1. Is the tracked symbol still current on its venue?
2. Did the same security move to another venue without changing symbol?
3. Did the same security continue from `A` to `B`?
4. Did an exchange-listed security continue OTC?
5. Did the tracked security actually cease to be current with no verified
   successor?

The result should be automatic when regulator identity facts and current
listing authority agree. It should remain Monitoring when a source is missing,
stale, or merely silent. Human review is reserved for contradictory identity,
security-class ambiguity, or transaction terms that change what is being
tracked.

## 2. Source Roles

### 2.1 SEC EDGAR: event and identity authority

SEC remains the authority for:

- issuer CIK;
- the tracked security and security class;
- announced old/new symbols and venues;
- Form 25 and related filing-chain state;
- explicit effective dates; and
- explicit completion, cancellation, withdrawal, or no-identity-change facts.

SEC absence is not a negative fact. An 8-K headline or an
`acquisition_completed` event label alone does not prove that the tracked
security disappeared.

### 2.2 Nasdaq Trader: keyless current NMS directory

The scheduler may download exactly these public HTTPS files:

- `https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt`
- `https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt`

They require no API key and provide one bounded current-directory snapshot for
Nasdaq-listed and other NMS-listed symbols. The adapter must preserve the file
creation timestamp, complete-document SHA-256, row count, exact matching row,
and parser version.

Inclusion in a successfully parsed current snapshot is positive evidence of a
current symbol and venue. Absence is only `not_found`; it is never silently
converted to `delisted`.

### 2.3 Massive: configured reference-data fallback

Polygon.io is now Massive. The official service exposes the new
`https://api.massive.com` base while continuing parallel support for
`api.polygon.io`. ArkScope keeps the durable provider ID `polygon` and the
existing `POLYGON_API_KEY` setting for compatibility, but user-facing Settings
labels it **Massive (Polygon)**.

No second secret field or environment variable is added. Existing news and
market-data code may continue using its durable `polygon` identifiers; the new
lifecycle adapter is named `massive_reference` and reads the same effective
credential.

Massive is queried only when at least one typed condition is true:

1. SEC indicates an OTC destination;
2. the SEC candidate is absent from a complete Nasdaq Trader snapshot;
3. a terminal decision needs explicit `active=false` / `delisted_utc`
   corroboration; or
4. the public directory is unavailable, stale, or internally inconsistent.

The free Stocks Basic contract is sufficient for the reference endpoints, but
the adapter must obey a hard maximum of four requests per scheduler tick and a
one-request-per `(ticker, expected_active_state, market)` dedupe. Pagination over
the all-tickers endpoint is not allowed in lifecycle automation. Use
`GET /v3/reference/tickers` with an exact `ticker` filter and the explicit
`active=true` or `active=false` required by the decision. Massive's ticker
overview endpoint is not used for terminal state because its own documentation
directs delisted lookups to All Tickers with `active=false`.

Missing Massive configuration is not a global failure. It becomes a typed,
retryable blocker only for a case whose decision actually needs the fallback.
Nasdaq Trader and Massive share the durable `listing_authority` source family,
but their component states remain distinct. An NMS case may complete with
Nasdaq alone; an OTC continuation or terminal decision may require Massive.
The scheduler and UI must not turn an optional Massive miss into a global
listing-authority failure.

### 2.4 IBKR: optional broker-contract corroboration and veto

IBKR is not listing authority. A missing contract or quote never proves a
delisting, and a stale or frozen price never proves continued listing.

When the remotely configured Gateway is available, its exact contract identity
may:

- corroborate the SEC/listing-authority result;
- expose a conflicting symbol, class, or venue; or
- block a mutation while an open position exists.

IBKR unavailability does not block a decision already established by SEC and
listing authority. A positive conflicting IBKR contract does block automatic
mutation and creates a typed exception.

### 2.5 FINRA and OTC public pages

FINRA OTC pages are public and no-fee, but FINRA has required authentication for
Equity Query API datasets since 2022. They therefore do not satisfy the approved
"no API key" automation constraint and are not implemented as a runtime
adapter in this slice.

The product may expose an official FINRA OTC link for attended verification,
but scraped UI internals, legacy FTP endpoints, and undocumented browser APIs
must not become automated authority. Massive reference data is the approved
fallback for OTC state.

### 2.6 News, web search, models, and translations

Publisher/news evidence is removed from the lifecycle acquisition path and from
the active Lifecycle evidence UI. Existing rows are preserved for historical
integrity; they are not deleted or rewritten.

News remains available in News and AI Research, where ticker aliases, issuer
identity, and bounded event dates can drive a separate search. General web
search remains a future typed fallback and is not part of this slice.

Models and translations never count as source families. This slice makes no LLM
call. SEC free-text evidence remains translatable on demand. Structured listing
directory snapshots are rendered as localized fields and do not show a
translation command. The translation preparation boundary must reject
`listing_directory_snapshot` before resolving a model route or invoking a
provider; hiding the button is not the authority.

The storage/read service remains complete. Hiding legacy `publisher` and
inactive `general_web` rows is an outward active-case projection only; mutation,
transition, audit, and historical read paths retain the full stored record.

## 3. Durable Evidence Contract

### 3.1 Closed vocabulary

Schema v3 adds, without removing any v2 value:

```text
source_family: listing_authority
adapter:       nasdaq_symbol_directory | massive_reference
kind:          listing_directory_snapshot
```

The v2 values `publisher`, `internal_news`, and `publisher_excerpt` remain legal
legacy values. New automation must never produce them.

### 3.2 Listing status

Every normalized listing record has exactly one status:

```text
active | inactive | not_found | unverified
```

- `active`: the authority positively identifies the ticker as current.
- `inactive`: only an authority with an explicit inactive/delisted field may
  emit it. Nasdaq directory absence cannot.
- `not_found`: a complete, current lookup did not contain the exact candidate.
- `unverified`: the response cannot support a listing claim because access,
  freshness, completeness, or schema validation failed.

### 3.3 Evidence locator

Each listing evidence row stores a bounded locator with these fields:

```json
{
  "authority": "nasdaq_trader | massive",
  "candidate_ticker": "B",
  "listing_status": "active | inactive | not_found | unverified",
  "market": "stocks | otc",
  "primary_exchange": "XNAS",
  "security_type": "CS",
  "issuer_cik": "0000000000",
  "composite_figi": null,
  "delisted_utc": null,
  "source_as_of": "2026-08-28",
  "snapshot_complete": true,
  "source_document_sha256": "...",
  "adapter_version": "..."
}
```

Fields unsupported by an authority are `null`; they are never guessed. The
persisted excerpt is one canonical compact record, not the full directory or API
response. `content_sha256` hashes the exact stored excerpt. For Nasdaq data,
`source_document_sha256` hashes the complete downloaded file. For Massive, it
hashes the exact bounded response bytes accepted by the parser.

### 3.4 Facts

Listing adapters may emit only deterministic, cited facts:

- an active queried SEC successor may emit `successor_ticker`,
  `destination_venue`, and `security_class`;
- an active queried source symbol may emit `source_ticker`, `source_venue`, and
  `security_class`; and
- Massive may emit `issuer_cik` only when present and valid.

The adapters do not discover an arbitrary successor by fuzzy name search. SEC
provides the candidate. Listing authority confirms or rejects that candidate.
`not_found` and `inactive` remain evidence locator states; they are not encoded
as invented identity facts.

Every producer output is fed through the real fact-kernel validator in contract
tests. Producer self-consistency is not sufficient.

When more than one listing record is available, current material is selected
independently per `(adapter, candidate_ticker, expected_active_state, market)`.
Different authorities are never collapsed into one global latest record. An
equal-time disagreement within one component is fail-closed, and only selected
current SEC, Nasdaq, Massive, and positive IBKR material participates in
conflict checks. Legacy publisher/general-web facts and stale receipts cannot
veto a v4 decision.

## 4. Acquisition and Budgets

### 4.1 One public snapshot per scheduler tick

Nasdaq files are fetched once before the bounded case batch and shared read-only
by all selected cases. Per-case downloads are forbidden.

The transport must enforce:

- exact HTTPS host/path allowlists;
- redirects disabled unless the final URL remains the same allowlisted origin;
- connect/read timeouts;
- at most two Nasdaq requests per tick;
- at most 8 MiB per file and 12 MiB total;
- expected text content type or a typed mismatch;
- strict headers, footer/file-creation record, row width, symbol syntax, unique
  symbol identity, and bounded row count; and
- freshness against the latest completed U.S. trading session using the
  repository's market-session authority.

An empty, truncated, stale, redirected, or schema-drifted file is unavailable,
not an empty market.

### 4.2 Massive budget

The Massive transport enforces:

- exact host `api.massive.com` and exact `/v3/reference/tickers` path;
- at most four requests per scheduler tick;
- at most one request per normalized `(ticker, expected_active_state, market)`;
- at most 1 MiB per response and 4 MiB total;
- no unbounded `next_url` traversal;
- typed handling for missing credential, 401/403, 404, 429, malformed JSON,
  provider error status, and transport failure; and
- no secret in URLs persisted to diagnostics or evidence.

Massive's documented REST example authenticates with the `apiKey` query
parameter. The transport may attach that parameter only at the final request
boundary. It must construct and persist a separate canonical source URL with no
credential, redact request exceptions before they leave the transport, and
prove by tests that the key is absent from locators, diagnostics, and error
messages.

### 4.3 Shared SEC and remote IBKR behavior

The existing shared SEC governor and budgets remain unchanged. The existing
remote IBKR host/port/client-id settings and gateway lock remain authoritative.
No localhost assumption and no second IBKR client are introduced.

## 5. Decision Matrix

### 5.1 `A -> B` on an NMS venue

Automatic acceptance requires:

1. SEC explicitly supplies old symbol, new symbol, same issuer CIK, compatible
   security class, and effective date;
2. the current Nasdaq directory contains `B` on the expected or non-conflicting
   destination venue;
3. no current listing authority marks `B` inactive;
4. no IBKR result contradicts symbol, class, or venue;
5. the effective date has arrived; and
6. the existing transition preview is eligible.

Before the date, use `waiting_effective_date`. On or after the date, schedule
the reversible `A -> B` transition. The new symbol is not inserted into aliases
or the Universe before the transition authority applies it.

### 5.2 `A -> B` to OTC

The SEC identity requirements are the same. Massive must positively return
`B` with `active=true` and `market=otc`; Nasdaq absence is supporting context,
not the deciding fact. Apply the same effective-date, IBKR-conflict, position,
preview, visibility, and reverse rules as an NMS continuation.

### 5.3 Same symbol, new venue

SEC supplies the venue change and effective date. Current listing authority
must show the same symbol on the destination venue. Notify and update venue
presentation where supported, but do not remove/re-add the Universe member.

### 5.4 Explicit terminal delisting

Automatic terminal action requires all of:

1. the tracked-security Form 25/25-NSE chain is complete;
2. SEC supplies the exact source symbol, security class, issuer CIK, and
   effective date, with no successor;
3. the date has arrived;
4. a complete current Nasdaq snapshot does not contain the source symbol;
5. Massive explicitly returns `active=false` with a non-future
   `delisted_utc`, or an equally explicit reviewed authority is added later;
6. no source presents an active successor or conflicting current identity;
7. there is no open portfolio position; and
8. transition preview is eligible.

Without item 5 the result remains Monitoring. Absence from two directories and
an IBKR miss are not promoted into explicit inactive status.

### 5.5 Completed issuer event with unchanged current ticker

An `acquisition_completed` observation may move to History as
`no_tracked_security_change` when:

1. deterministic SEC facts bind the filing to the tracked issuer and establish
   that the registrant/current tracked security continues or that the issuer is
   the acquirer rather than the disappearing target; and
2. current listing authority positively shows the same ticker, compatible
   security class, and non-conflicting venue after the completion date.

An active ticker alone cannot decide transaction roles. A completion label alone
cannot decide security continuity. If either side is missing, keep Monitoring or
produce a fully prefilled exception according to existing M&A rules.

### 5.6 Conflict and uncertainty

Any disagreement in ticker, issuer CIK, security class, active/inactive state,
or destination venue becomes `listing_authority_conflict` and blocks automatic
mutation. A required-but-unavailable source becomes a retryable typed blocker.
Normal pending dates and a clean `not_found` remain Monitoring, not attention.

## 6. Policy and Retry

This behavior is a semantic policy change. Advance:

```text
AUTOMATION_POLICY_VERSION = trusted-lifecycle-automation-v4
```

Do not use `AUTOMATION_EXECUTION_REVISION` to represent the policy change. The
existing execution revision remains a deployment replay mechanism for unchanged
semantics.

Existing v3 automation drafts remain stored and readable but are stale. The v4
scheduler creates a new run from SEC/listing-authority evidence. It does not
rewrite, relabel, or accept a v3 draft. Existing human and legacy accepted
assessments remain historical records.

Retry behavior:

- public directory or Massive rate/access/transport failures use typed bounded
  retry;
- missing Massive configuration retries only when that case requires Massive;
- `not_found` with no explicit inactive authority rechecks on the existing
  dated Monitoring cadence;
- a new SEC observation or changed listing snapshot changes the run input
  identity and reopens a stale conclusion; and
- operational failures use the existing execution-revision mechanism, not a
  manufactured policy bump.

## 7. Schema V3 and Migration

The exact v2 schema authority must remain available in code for preflight,
scratch migration, and rollback verification. Current schema authority becomes
v3 only after a dedicated migration implementation exists.

The v2-to-v3 migration:

1. is explicit and never runs at startup;
2. binds an approval digest to the exact v2 owned schema and rows;
3. creates a durable backup and scratch restore probe;
4. rebuilds the owned lifecycle tables in one `BEGIN IMMEDIATE` transaction so
   SQLite CHECK constraints and child foreign keys remain exact;
5. maps every existing cell byte-for-byte, including all legacy publisher rows,
   translations, facts, assessments, citations, acknowledgements, and
   proposals, and explicitly preserves hidden lifecycle `rowid` values and the
   lifecycle-owned `sqlite_sequence` values used by AUTOINCREMENT tables;
6. adds no synthetic listing evidence;
7. leaves unchanged ticker-identity tables physically intact while proving
   their schema and row digests are unchanged;
8. runs integrity, foreign-key, per-table count, explicit-rowid, sequence, and
   per-row digest checks;
9. proves old code starts against the restored v2 backup; and
10. records the accepted source/target authorities and row mapping in the
   migration packet.

After migration, rolling code back to a v2 binary requires restoring the bound
v2 backup. Code-only rollback is not supported.

## 8. API and UI

### 8.1 Active case detail

The default evidence area shows only:

- SEC filings;
- Listing authority;
- IBKR contract corroboration when queried; and
- explicitly supplied manual evidence.

Active detail and source-family status use this same four-family allowlist.
Legacy `publisher` and inactive `general_web` rows are excluded. They remain
queryable only through internal storage/integrity paths; no deletion occurs.

Listing evidence is compact. Each item shows source, ticker, active/inactive/not
found state, venue/market, source-as-of date, and a source link. Raw JSON and the
full symbol directory are not rendered. `not_found` must read as "Not found in
this completed snapshot", never "Delisted".

### 8.2 Automation explanation

The detail view names which deterministic rules produced the disposition and
which source family supplied each material field. It must make SEC, Nasdaq,
Massive, and IBKR roles distinguishable. It must not label deterministic output
as model-authored.

### 8.3 Settings

The existing `polygon` row becomes **Massive (Polygon)** in both English and
Traditional Chinese. Its API-key field, masked storage, import behavior,
effective-source display, and durable provider ID remain unchanged.

The user-triggered connection test moves to the official Massive base and uses
one free bounded reference request. No automatic test occurs on render or save.

## 9. Admission

Implementation is admitted only after all of these offline checks pass:

1. real-shaped Nasdaq directory fixtures cover Nasdaq, NYSE/NYSE American,
   NYSE Arca, Cboe/BATS, IEX, file footer, stale file, truncation, duplicate
   symbol, and schema drift;
2. Massive fixtures cover active NMS, active OTC, inactive with
   `delisted_utc`, 404/not-found, missing key, 401/403, 429, pagination refusal,
   malformed JSON, and CIK/class conflict;
3. adapter output is fed through the real fact-kernel validator;
4. policy fixtures cover NMS `A -> B`, OTC `A -> B`, same-symbol venue transfer,
   explicit terminal delisting, active unchanged acquisition, conflicting
   authority, and unresolved absence;
5. mutations prove that Nasdaq absence cannot become inactive, IBKR missing
   cannot become delisted, a price cannot become listing authority, and
   publisher evidence cannot affect a v4 decision;
6. API tests prove publisher rows are hidden while stored rows and foreign-key
   integrity remain unchanged;
7. browser tests cover English and Traditional Chinese, desktop and mobile,
   concise listing evidence, source distinction, Monitoring, History, visible
   automatic transition, acknowledgement, and reverse;
8. Settings tests prove one masked `POLYGON_API_KEY` authority and the
   **Massive (Polygon)** label;
9. v2-to-v3 scratch migration and reverse restore preserve every legacy row;
10. backend, frontend, typecheck, and production build gates pass twice with
    identical collection counts; and
11. the evidence packet declares provider calls, production DB operations,
    merge, cutover, and push as zero rather than pretending unexecuted scenarios
    were measured.

After offline GREEN, these remain separate user decisions in order:

1. read-only production v2 inventory;
2. bounded live Nasdaq/Massive/IBKR canary;
3. production migration preflight, backup, restore probe, and migration;
4. merge;
5. App restart/cutover; and
6. push.

## 10. Out of Scope

- provider procurement or account creation;
- FINRA authenticated Query API integration;
- scraping undocumented OTC/FINRA browser endpoints;
- general web search as a default lifecycle source;
- LLM-authored lifecycle facts or acceptance;
- deletion of historical publisher evidence;
- automatic handling of cash, stock, mixed, spin-off, or class-changing M&A
  without a separately reviewed deterministic policy; and
- changing News or AI Research storage beyond documenting that those surfaces
  remain the place for event-news research.
