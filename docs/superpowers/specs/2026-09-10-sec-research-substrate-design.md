# SEC Research Data And Tools

Status: proposed implementation contract, awaiting the user's written-spec review.
Base inspected: `30bb31c7`. The user approved the product direction on September
10, including useful tool access rather than collection without consumers.
Last implementation-tree review: `28e67e33`. On September 10 the user selected
a **100 GiB adjustable capture budget**, replacing the proposed 20 GiB default.
This revision records that capacity decision and the verified review corrections;
the complete revised spec still needs review before an implementation plan.
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

The existing `SecTransport` and `SecRequestGovernor` remain the acquisition
foundation. `data_sources/sec_edgar_source.py::SECEdgarDataSource` owns
`get_cik`, `fetch_submissions` and `fetch_company_facts`.
`SECEdgarFinancials` is the higher-level financial mapper using that source;
there is no `SECClient` class to extend. `PublicSourceReader` supplies guarded
source reading and a document-observer hook. Existing concept maps can be
reused; current value-only selection and float-decoded responses cannot be
reused as provenance-preserving exact fact observations.

## 3. Boundaries And Existing Gaps

- New owner: `src/sec_research/`, split into schema/store, catalog, facts,
  documents and service modules. API and tool modules are thin adapters.
- There is no general durable filing catalog today. Lifecycle observations
  are not a substitute and remain untouched.
- The existing local `/sec/{ticker}` path can return the empty FileBackend
  metadata stub, while registered `sec_tools.get_sec_filings` calls EDGAR
  directly. Retained Python/HTTP compatibility surfaces must delegate to the
  new service after compatibility tests. Remove `get_sec_filings` from all
  model-facing surfaces in the same change that admits the three new tools;
  do not expose two overlapping catalog tools with different truth envelopes.
- The old parser reads only `filings.recent`, filters after `limit * 3`, uses
  filing date as report date, and guesses XML filenames. None becomes a new
  contract. Use actual `primaryDocument` and directory entries instead.
- `data_sources/sec_filings.py` remains a dormant file with a module-level
  `edgar` import; it is not physically removed. The existing
  `tests/test_sec_transport.py::test_all_active_sec_http_callers_use_shared_transport_and_dormant_edgartools_is_unreachable`
  scans all `src/**/*.py`, including the new owner, to prohibit imports of that
  module. Keep that guard; do not reactivate `SECFilingsClient`, add edgartools
  to requirements or introduce an external CLI.

## 4. Storage And Migration

Use separately owned, versioned `sec_research_*` tables in `market_data.db`.
Keep `financial_cache`, lifecycle observations and historical assessments
unchanged. Rechecked through `28e67e33`: `ce17e9e7` changed cache UI copy and
frontend tests only, not financial-cache storage or backend reads/writes.
The new tables contain:

- issuer resolution observations, including ticker, CIK, source and time;
- filings keyed by `(CIK, accession)`, with distinct filed/report/accepted
  timestamps, form, primary-document identity and observed metadata versions;
- immutable normalized fact observations and source-snapshot references;
- document/canonical-text captures, section ranges and citation references;
- refresh receipts with per-issuer result, coverage, counts and typed errors.

Introduce `SecResearchPaths` in the new owner; there is no existing common
portable-data-root abstraction. Resolve the effective market DB using the same
path authority as the market DAL. For resolved DB path `P`, derive the capture
root as `P.parent / (P.name + ".sec-research")`. Including the DB filename keeps
two stores in the same parent separate. Do not change the independent market,
SA, profile or lock path authorities or introduce a new `.env` path override.

Original source bodies and canonical UTF-8 text are content-addressed beneath
that capture root. Store only validated relative object keys; reject absolute
paths, traversal and symlink escapes. "Original" means the unmodified document
body after HTTP content decompression, before text extraction, not the compressed
wire representation. Record wire and decoded sizes separately. The reader's
document-observer hook supplies these original document-body bytes. Citation IDs
bind a snapshot, not the mutable latest pointer. Never take an arbitrary local
path from an LLM. Relocation moves the DB and its capture directory together;
export restoration resolves the destination root through the same owner.

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
user's stores. The capture-budget setting is persisted in the profile DB using
the existing typed-configuration patterns, with explicit migration if required;
the new SEC tables have their separate market-store migration.

Portable SEC export and validated restoration are new work, not an existing
exporter to configure. Reuse `src/market_data_direct.py::backup_market_db` with
`overwrite=False` for the WAL-safe SQLite backup primitive. Enumerate referenced
objects from that backup, protect them from cleanup while exporting, and publish
the complete bundle with a versioned manifest and object hashes. Do not overwrite
an existing destination. Validate schema, hashes and relative keys before
restoring into a new destination; a missing/corrupt object must not produce a
successful export or restoration. Copying only the database is inadequate.
Export and moved-root reopening need separate acceptance owners.

## 5. Catalog And Coverage

Resolve tickers to CIK without treating CIK as a same-security rename identifier.
Conflicting mappings return ambiguity. Explicit CIK input accepts a case-insensitive
`CIK:` prefix followed by one to ten ASCII digits, with surrounding whitespace
removed and a nonzero numeric value. Canonical output uses uppercase `CIK:` and
exactly ten zero-padded digits; store/request the ten-digit numeric component.
Reject signs, embedded whitespace, non-ASCII digits and longer identifiers.

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
observation: decode raw response bytes with `json.loads(parse_float=Decimal)`
and reject non-finite constants. Preserve integers exactly; store numeric values
as decimal `TEXT`, not SQLite `REAL`, and expose an exact decimal string in the
new tool envelope. Do not convert a previously decoded float into Decimal and
claim exactness. The existing `SecResponse.json()` uses ordinary JSON decoding;
provide a narrow exact-decoding path for this new service without changing old
financial consumers. Do not label every value USD or discard non-USD units.

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

Reuse the bounded source reader, declared SEC user agent, shared pacing and
cancellation. Bind SEC identity/governor handling through the existing
`SecSourcePolicy` integration. The new persisted document path explicitly adopts
**32 MiB wire-body bytes and 128 MiB decoded-body bytes per response**. These
are different counters, neither a task-wide nor a storage-wide allowance.

This is a policy change for SEC research document acquisition, not a claim that
existing SEC ceilings were already this large. The existing
`SECEdgarDataSource.fetch_filing_document_text` defaults to 1 MiB with a 5 MiB
hard ceiling; `SecRequestBudget` is a separate optional request/document budget.
Do not route the new document tool through that 5 MiB method or globally raise
unrelated SEC metadata/financial limits. The 32/128 MiB values also occur in the
per-URL lifecycle public-source reader, but that non-persisting use is not proof
of safety for a durable capture store. Persistent accounting is specified in
section 10; the implementation plan must also own parser memory, concurrency
and cancellation separately from disk capacity.

Download size is independent of tool-result size. Measure observed wire and
decoded bytes rather than equating an encoded Content-Length with decoded text
length. Exhaustion or incomplete transport yields an explicit unavailable/partial
result; a document is never silently cut and reported complete. HTML/iXBRL is
supported, not excluded by extension. Unsupported formats such as a PDF without
an admitted parser return a typed format gap.

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
  while new endpoints provide the full closed envelope. A legacy shape that
  cannot represent partial/unavailable must fail explicitly rather than return
  a misleading empty list; only complete covered emptiness maps to an empty list.

Do not widen general bridge budgets just to fit a filing. Add citation-aware
per-tool result sizing that emits smaller whole pages before generic reducers.
The middle of a JSON result/citation must not be removed by a text reducer.

## 9. Research And Settings Integration

Register/invoke the same three contracts in OpenAI API, Anthropic API, ChatGPT
OAuth and Claude OAuth. Cover handwritten API adapters, registry, subscription
allowlists, cancellation and redaction. Availability in the registry alone is
not a completed four-channel integration. No task model/auth/effort defaults
change and no fallback between transports is added.

The same implementation commit must replace the old catalog tool at all of:

- `src/tools/registry.py`: registration and schema ownership;
- `src/agents/openai_agent/tools.py`: imports, wrappers and returned tool list;
- `src/agents/anthropic_agent/tools.py`: schemas, imports and dispatch;
- `src/auth_drivers/chatgpt_oauth_driver.py`: explicit read-only allowlist;
- `src/auth_drivers/claude_code_sdk_driver.py`: its independent reviewed allowlist;
- `src/agents/shared/subagent.py`: `deep_researcher.tool_names`, admitting all
  three new SEC tools and removing `get_sec_filings`.

Both subagent filters silently discard unavailable names. There is already a
registry-membership owner inside
`tests/test_subagent.py::TestSubagentRegistry::test_code_analyst_uses_existing_data_tools_without_python_execution`:
it checks every configured subagent tool against the registry. The review probe
passed unchanged and failed when only `get_sec_filings` was removed from the
registry in memory. Extract that assertion into a clearly named independent
test rather than duplicate it or claim it is missing. Also test the actual
Anthropic/OpenAI filtered inventories and dispatch of the three SEC contracts;
registry membership alone does not prove adapter availability. Keep intentionally
disabled optional tools distinguishable from required SEC wiring omissions.

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
Also expose capture budget, stored bytes, in-flight reservations and a distinct
capacity/disk-space block. Changing the budget does not enable the schedule or
start a download. Do not call the 100 GiB budget a token or memory limit.

Old company-event acquisition must be uncallable through recurring scheduling,
Run Now or direct legacy entrypoints after retirement, with typed retired status.
Keep historical job records, lifecycle evidence and independent SEC financial
tools. Do not silently repurpose the old job ID.

Today `src/lifecycle_investigation/retirement.py::cutover_active` checks the
installed profile schema/journal, and the legacy collector already returns
`status="retired", reason="legacy_lifecycle_intake_retired"` when that gate is
active. The scheduler and legacy API also consume that lifecycle gate. Do not
add a competing SEC-retired setting or redefine that shared function as the
new research schedule's enabled flag. Once this complete replacement ships,
make the old collector permanently return the existing typed retired result
before creating a client or issuing a request, even for profiles without the
lifecycle journal. Recurring/Run Now entrypoints must respect that retirement.
Keep the shared lifecycle gate's other case/API semantics unchanged and test
both journal-present and journal-absent profiles.

## 10. Retention And Cost

Cache TTL expiry means refresh is due, not that a newer filing exists. Preserve
reporting periods, amendments and cited snapshots. No automatic deletion of
financial history, user notes or cited content. Unreferenced transport caches
and failed-publication orphans can have a separately tested cleanup policy.

### Capture Capacity Policy

The user selected a **100 GiB default** (`107374182400` bytes), adjustable in
Settings and persisted in the profile DB. It is an application storage budget,
not preallocated space, a measured typical filing requirement or a maximum value
that Settings must prohibit exceeding. Allow both increases above 100 GiB and
decreases; reject invalid/non-positive or unrepresentable values explicitly.
No source body is truncated to fit the remaining budget. Scheduled work still
fetches only catalog/facts; this budget does not authorize full-universe document
prefetch or imply that downloaded documents enter an LLM prompt in full.

Account capacity per capture root across processes/tasks/providers, not separately
for each request. Charge unique persisted original-body snapshots (including
retained structured-source snapshots), canonical text and other capture objects,
plus staged bytes and the unused portion of outstanding write reservations.
Convert reserved bytes to actual usage atomically without counting the same bytes
twice. Referencing an existing object does not charge it twice, but transient
duplicate downloads still occupy staging space until deduplicated. Retained
failed-publication orphans remain
charged until cleanup. Reserve capacity before writes, extend reservations before
additional writes, reconcile interrupted workers on restart, and prevent concurrent
writers from each spending the same remaining capacity. Never hold a market DB
write lock while waiting for a provider response.

Reject already-known capacity or disk-space blocks before a new provider request.
At budget exhaustion return a typed `capture_budget_exceeded` gap and stop new
capture writes; completed captures, local queries, cited text and historical
facts remain readable. If a call already contains valid results it is partial,
not complete; a capture that cannot finish must never be published as complete.
Reducing the setting below current usage is allowed: show the over-budget state
and block further growth without deleting content. Raising it allows subsequent
explicit/previously scheduled work, not a hidden immediate acquisition. Offer
clear recovery actions: increase the budget, relocate the store, or explicitly
clean eligible unreferenced objects. Cleanup must recheck citation/pin/export
references; no automatic deletion of cited or user-pinned material is permitted.

Budget remaining is not filesystem space remaining. Check destination free space
before reserving/writing and handle ENOSPC or other write failures even after a
successful preflight. Return typed `storage_space_insufficient` or write-failure
gaps, preserve complete objects, and never claim a successful capture/export from
partial files. A generous configured budget must not override these checks.

The 100 GiB figure does not cap the entire shared `market_data.db`, its WAL,
profile data or export bundles. Show capture accounting separately from those
actual file sizes. The plan must name metadata/fact transaction and WAL staging
budgets plus export destination-space preflights and interrupted-write tests;
do not promise a whole-application disk ceiling from a content-store quota.

SEC has no API-key requirement, but valid contact identification and fair-access
pacing still apply. Read it through profile configuration, not a new `.env`
fallback. No Massive/EODHD request or LLM spend belongs in this collector.

## 11. Acceptance And Rollout

Before changing runtime code, write a RED-first implementation plan naming test
files, individual tests, expected RED failures, positive controls and inverse
mutations. Separate storage/export/quota and adapter integration tasks; do not
hide them inside a single broad acceptance item. Do not invent passing counts
before executing the tests. Required offline owners:

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
10. Capture quota default/conversion/profile persistence, increases/decreases,
    existing-object deduplication, concurrent reservations, restart recovery,
    quota/full-disk rejection and preserved cited/local reads. Use small fixtures
    and injected capacity counters; tests must not allocate 100 GiB.
11. Independent subagent registry-membership protection plus actual required SEC
    tool inventory/invocation, with intentionally optional tool omissions as a
    separate control. Preserve the dormant-edgartools import guard.

At reviewed HEAD there are **17 tool-count assertions across eight test files**.
Replacing one registered tool with three gives registry/schema/status 54 -> 56
and the current bridge fixture 55 -> 57, not 58. These numbers apply to the
reviewed fixture configuration, not every optional-tool runtime configuration.
The plan must cover every site in the same integration change:

| Test file | Assertions at reviewed HEAD |
|---|---|
| `tests/test_agents.py` | lines 115, 409 (55); 705, 719 (54) |
| `tests/test_analyst_tools.py` | line 286 (54) |
| `tests/test_api.py` | line 417 (`tools_registered`, 54) |
| `tests/test_memory_tools.py` | line 340 (54) |
| `tests/test_portfolio_tools.py` | line 195 (54) |
| `tests/test_sa_tools.py` | lines 755, 766, 772, 2347 (54); 788 (55) |
| `tests/test_sec_tools.py` | line 150 (54) |
| `tests/test_tools.py` | lines 196, 234, 245 (54) |

`GET /status` computes `tools_registered` from the actual registry; keep that
truthful rather than treating 54 as an immutable API value. Count assertions
supplement, not replace, exact-name and real dispatch tests. No claim of zero
collateral tests is valid from checking only the new SEC test files.

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
