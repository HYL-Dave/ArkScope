# SEC Research Data And Tools

Status: proposed implementation contract, awaiting the user's written-spec review.
Base inspected: `30bb31c7`. The user approved the product direction on September
10, including useful tool access rather than collection without consumers.
This document is not evidence of implementation, migration, acquisition or live
validation. Rename automation and the macro scheduler fix are independent work.

## 1. Product Outcome

AI Research must be able to find a company's filings, retrieve financial facts
for specified periods, and read selected source passages with reproducible
citations. The same service must be usable by future Notes without another SEC
collector or a provider-specific agent implementation.

The complete first release includes persistence, acquisition, three tools,
four Research transports, safe result pagination, retained citations, Settings
status/scheduling and a portable export. A catalog-only mock or renamed old
event job is not completion.

This is research data. It does not create lifecycle cases, judge delisting,
modify ticker identities, change memberships or invoke an LLM in the collector.

## 2. Alternatives And Selected Shape

1. Retain only filing URLs: inexpensive, but offline research, fact queries and
   stable cited versions remain unsolved.
2. Download/parse every complete filing during every refresh: unnecessarily
   expensive and mixes acquisition breadth with model-context size.
3. Persist the catalog and structured facts; acquire selected original
   documents on demand. **Selected.** It provides useful numeric queries and
   source access without putting entire filings into a prompt.

The existing `SecTransport` and request governor remain the acquisition
foundation. `SECClient` supplies issuer/submissions/companyfacts access.
`PublicSourceReader` supplies guarded source reading and byte-bound passages.
Existing concept maps can be reused; current value-only selection cannot be
reused as a provenance-preserving fact result.

## 3. Boundaries And Existing Gaps

- New owner: `src/sec_research/`, split into schema/store, catalog, facts,
  documents and service modules. API and tool modules are thin adapters.
- There is no general durable filing catalog today. Lifecycle observations
  are not a substitute and remain untouched.
- The existing local `/sec/{ticker}` path can return the empty FileBackend
  metadata stub, while registered `sec_tools.get_sec_filings` calls EDGAR
  directly. Both must delegate to the new service after compatibility tests.
- The old parser reads only `filings.recent`, filters after `limit * 3`, uses
  filing date as report date, and guesses XML filenames. None becomes a new
  contract. Use actual `primaryDocument` and directory entries instead.
- Old edgartools document imports remain retired. No dependency bump or new
  external CLI is required.

## 4. Storage And Migration

Use separately owned, versioned `sec_research_*` tables in `market_data.db`.
Keep `financial_cache`, lifecycle observations and historical assessments
unchanged. The new tables contain:

- issuer resolution observations, including ticker, CIK, source and time;
- filings keyed by `(CIK, accession)`, with distinct filed/report/accepted
  timestamps, form, primary-document identity and observed metadata versions;
- immutable normalized fact observations and source-snapshot references;
- document/canonical-text captures, section ranges and citation references;
- refresh receipts with per-issuer result, coverage, counts and typed errors.

Original response/document bytes and canonical text are content-addressed under
the portable data root, using relative paths only. Citation IDs bind a snapshot,
not the mutable latest pointer. Never take an arbitrary local path from an LLM.

The market-store schema change must be explicit and idempotent, tested on a
fresh store and an existing populated store. Acquisition occurs outside write
locks. Publish immutable files atomically before a short database transaction;
an interrupted publication may leave a removable orphan, never a database row
pointing at an incomplete file. Parallel refreshes deduplicate by content hash.

Research's durable tool trace currently retains only an input and short preview.
Add optional closed SEC citation references to the existing result/event/trace
contract, with backward-compatible reads and tests for old conversations. A
truncated preview must never be the sole surviving citation.

Any required production migration, backup and activation has a separate rollout
checkpoint. Implementing migrations is not authorization to run them on the
user's stores. Export must use a consistent SQLite backup plus referenced
content objects and a versioned manifest; copying only the database is inadequate.

## 5. Catalog And Coverage

Resolve tickers to CIK without treating CIK as a same-security rename identifier.
Conflicting mappings return ambiguity. Explicit `CIK:##########` is supported.

Read submissions' recent arrays and historical-file pointers. Validate column
alignment before committing. Apply form/date filters before result-page limits.
Historical traversal has persisted continuation/coverage state; reaching a
request bound reports incomplete coverage, not an empty complete history.

First-release scheduled scope: current active-universe issuers, deduplicated by
CIK; forms 10-K, 10-Q, 20-F, 40-F and their amendments. On-demand catalog queries
can also request 8-K and 6-K and retrieve selected financial exhibits. Merely
seeing an 8-K/6-K does not mean it contains financial statements.

Preserve amendments as separate accessions. A `/A` filing does not automatically
replace every value or section of its predecessor. Missing historical pointers,
provider failures and removed/corrected sources remain visible in coverage.

## 6. Financial Facts

Persist namespace/concept, decimal value, unit, start/end, fiscal labels, form,
accession, filed date, frame where supplied, snapshot hash and JSON pointer.
Parse JSON numbers without introducing binary-float rounding into the stored
observation. Do not label every value USD or discard non-USD units.

The initial common metric projection covers revenue, net/operating income,
assets/liabilities/equity, cash, operating cash flow, capital expenditure,
reported EPS and shares, using reviewed existing concept alternatives.
Explicit namespaced concepts are also queryable.

Selection distinguishes instant, annual, quarterly and YTD observations.
Default results contain reported values, not invented standalone quarters.
Derived Q4/TTM and ratio calculation are excluded from this first release;
existing independent financial-analysis tools remain available. A later derived
value feature must cite compatible operands and its formula.

`as_of` constrains when a filing was available, not just its reporting-period
end. Latest-per-period selection is deterministic and does not destroy earlier
observations. Conflicting candidates or absent metrics return typed gaps, not
zero, guessed currency or an arbitrary first value.

Company Facts is not complete filing intelligence: custom concepts, segments,
footnotes and narrative can require reading the filing itself.

## 7. Document Reading And Citations

Resolve documents only from cataloged SEC accession directories and actual
directory entries. Primary documents and selected exhibits are distinct IDs.
Do not construct speculative `_htm.xml` names, fetch arbitrary URLs, follow
non-public redirects or expose filesystem paths to models.

Reuse the bounded source reader, declared SEC user agent, shared pacing,
cancellation and transport/decompression limits. Download size is independent
of tool-result size. Existing reviewed resource ceilings remain, and exhaustion
is an explicit unavailable/partial result; a document is never silently cut and
reported complete. HTML/iXBRL is supported, not excluded by extension. Unsupported
formats such as a PDF without an admitted parser return a typed format gap.

Persist original bytes and canonical text with versioned extraction and hashes.
Produce form-aware section indexes when unambiguous, plus literal-search and
cursor-based text access. If a section cannot be identified, expose that fact
and the pageable document; never substitute its first paragraph for that section.

Every passage carries source URL, accession, capture ID, exact UTF-8 byte range
and text/document hashes. Reopening a capture returns the same cited text after
refresh, restart and profile/data-root relocation. No generic terminal, host-file
reader or Python executor is introduced.

## 8. Three Tool Contracts

All tools return a closed envelope with `status` (`ok`, `empty`, `partial`,
`unavailable`), data, typed gaps, observation time, coverage and `next_cursor`.
Empty means the requested covered range contains no matches; unobserved does not.

```text
list_sec_filings(issuer, forms, filed_from, filed_to,
                 include_amendments=true, cursor, limit=20, freshness="auto")

get_sec_financial_facts(issuer, metrics, concepts, fact_ids, accession, as_of,
                        period="all", start, end, revisions="latest",
                        cursor, limit=40, freshness="auto")

read_sec_filing(filing_id, document_id="primary", section_id, query,
                capture_id, cursor, max_chars=6000, freshness="auto")
```

- Catalog results include stable filing IDs and available document identities.
- Fact results include stable fact IDs, units/periods and source citations.
- A text call without section/query/cursor returns document/section indexes
  and a `text_start_cursor` for whole-document paging; subsequent calls read
  exact chunks. `capture_id` pins the cited version. `fact_ids` reopens exact
  immutable numeric observations without applying latest-revision selection;
  it cannot be combined with metric/period filters.
- `freshness=stored` performs zero requests. `auto` reuses suitable local
  material and can acquire absent/stale data. `refresh` requests revalidation.
  Reopening a pinned capture never substitutes refreshed text.
- `limit` and `max_chars` are output page sizes, not document-input truncation.
  Pages contain whole fact/filing records and complete citation envelopes.
  Cursors bind filter and snapshot identity and expose continuation explicitly.
- Read-only HTTP views use stored mode; explicit refresh commands perform
  acquisition. Compatibility endpoints keep old response shapes where required,
  while new endpoints provide the full closed envelope.

Do not widen general bridge budgets just to fit a filing. Add citation-aware
per-tool result sizing that emits smaller whole pages before generic reducers.
The middle of a JSON result/citation must not be removed by a text reducer.

## 9. Research And Settings Integration

Register/invoke the same three contracts in OpenAI API, Anthropic API, ChatGPT
OAuth and Claude OAuth. Cover handwritten API adapters, registry, subscription
allowlists, cancellation and redaction. Availability in the registry alone is
not a completed four-channel integration. No task model/auth/effort defaults
change and no fallback between transports is added.

New schedule ID: `sec_research_filings`, default disabled, daily interval.
It refreshes catalog and structured facts incrementally. Historical backfill is
explicit and resumable; no old `sec_corporate_actions` enabled flag is copied.
User-started Research tool calls retain on-demand acquisition independently of
the schedule. No background LLM processing or full-document prefetch by default.

Settings replaces obsolete SEC Company Events controls with the new financial
data source once the complete workflow is ready. Show enabled state, next run,
latest attempt, complete/partial/failed results, issuer coverage, filing/fact
counts and gaps. Last successful acquisition is distinct from last attempted
acquisition. A failed issuer does not erase other issuers' committed data.

Old company-event acquisition must be uncallable through recurring scheduling,
Run Now or direct legacy entrypoints after retirement, with typed retired status.
Keep historical job records, lifecycle evidence and independent SEC financial
tools. Do not silently repurpose the old job ID.

## 10. Retention And Cost

Cache TTL expiry means refresh is due, not that a newer filing exists. Preserve
reporting periods, amendments and cited snapshots. No automatic deletion of
financial history, user notes or cited content. Unreferenced transport caches
and failed-publication orphans can have a separately tested cleanup policy.

SEC has no API-key requirement, but valid contact identification and fair-access
pacing still apply. Read it through profile configuration, not a new `.env`
fallback. No Massive/EODHD request or LLM spend belongs in this collector.

## 11. Acceptance And Rollout

Required offline owners:

1. Recent plus historical catalog traversal, sparse form filters, malformed
   arrays, report/filing-date separation and actual document locators.
2. Missing/ambiguous issuer identity, amendments, as-of queries and partial
   coverage without false empty success.
3. Units, exact numeric preservation, instant/quarter/YTD distinctions,
   alternative concepts, missing metrics and retained revisions.
4. Document/section/exhibit access, continuation, bounded transfer failures,
   unsupported formats and exact cited-byte reopening.
5. Four real adapter-to-tool invocation paths with mocked transports only;
   no missing allowlist entry, reducer-damaged JSON or silent fallback.
6. Research reload retains source references; old conversations still load.
7. Fresh/existing schema, interruption, duplicate refresh, short write locks,
   consistent export and moved-root capture reopening.
8. New schedule off by default, old-enabled flags not inherited, retired old
   entrypoints, empty clean refresh success and truthful partial/failure status.
9. Settings desktop/mobile en/zh-Hant, counters and on-demand document views.

After offline acceptance, derive a minimal named public-SEC canary budget from
these paths and obtain authorization before acquisition. A separate representative
Research live check can verify cited use through one permitted low-cost channel;
do not claim all four channels live-tested from that observation.

Then review merge, production backup/migration and user activation separately.
No phase is reported complete while tools, provenance or portability remain stubs.

## 12. Primary References

- [SEC EDGAR APIs](https://www.sec.gov/search-filings/edgar-application-programming-interfaces):
  submissions history, historical JSON pointers, companyfacts and its taxonomy/
  entity-wide scope, reporting contexts and update behavior.
- [Accessing EDGAR](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data):
  actual filing directories and JSON/XML indexes, declared user agent, fair access,
  and post-acceptance corrections.

References checked September 10, 2026. The proposed architecture above is an
ArkScope design decision, not a claim that SEC supplies these local contracts.
