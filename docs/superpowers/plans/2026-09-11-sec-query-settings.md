# SEC Stored Queries And Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. Execute RED-first with independent
> task review and a final whole-change review.

**Goal:** Make retained SEC structured observations usable through snapshot-bound
queries and an explicit Settings management surface, without registering an
unfinished replacement Research tool.

**Architecture:** Immutable receipts bind each completed source to its exact
snapshot. Read-only queries anchor a cursor to one receipt and normalized filters;
refresh cannot silently change a page sequence. Thin HTTP adapters and a Settings
panel consume this service and the existing typed capture budget.

**Tech Stack:** Existing Python/SQLite/FastAPI and React/TypeScript/Vitest/lucide;
no new dependency or runtime upgrade.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`.
Base: `483e8f3e`. This is incremental structured-data administration, not the
complete first-release Research workflow. Explicit CIK remains the input authority
in this batch. Ticker resolution, original filing documents/citations, three
replacement tools/four channels, export and the disabled-by-default schedule
remain separate completion requirements. No obsolete SEC event control returns.

## Execution Status

| Task | Current gate |
| --- | --- |
| 1 | Complete at `7a1b9d99`; receipt read-shape R1 review passed. |
| 2 | Complete at `e07e459a`; independent review approved. |
| 3 | Complete at `420e4759`; 953 SEC/API tests and scoped R1 review passed. |
| 4 | Complete at `c6e2e435`; R1 review and desktop/mobile browser geometry passed. |
| Final | Whole-change review, fresh complete checks and evidence closeout pending. |

## Global Constraints

- Work only in the existing linked branch. No production store/config/token
  reads or writes, real provider calls, installs, restart, merge or push.
- Preserve prices/news/SA/financial_cache/lifecycle data and all live Research
  tool registrations. No old-schema repair/drop or schema migration chain.
- Keep the 107374182400-byte default and exact positive integer setting up to
  2**53-1; changing it cannot acquire, schedule, delete or invalidate old reads.
- Keep metadata acquisition bounds/transport policy from durable acquisition.
  Do not claim zero retry: the shared SEC transport owns its bounded 429 policy.
- Keep AUTOINCREMENT: receipt order is committed insertion order, not wall time.
  SQLite owns sqlite_sequence; SEC must neither verify it as private schema nor
  drop it. Disposable tests prove unrelated sequence state remains intact.
- New canonical receipt shape is validated exactly. The actual installation has
  not been activated by these offline changes; do not silently upgrade any store.
- Every query returns status/data/gaps/observed_at/coverage/next_cursor. `empty`
  needs an observed covered selection, never absence or an incomplete traversal.
- Cursor v1 binds CIK, query kind, normalized filters including page limit, receipt
  identity and the exact source-snapshot binding digest. Explicit immutable fact-id
  queries instead bind the requested ids and retained snapshot identities, without
  requiring a current receipt to bless historical observations. Decode strictly with a
  4096-byte cap. No secrets, arbitrary paths, SQL fragments or URLs in cursors.
  Cursor is a consistency token, not an authorization credential. Reads remain
  stable after restart/relocation/refresh; malformed or mismatched cursors fail.
- Page limits are 1..100 whole observations, with a 256 KiB encoded envelope
  ceiling. Oversized records produce a typed gap, never substring truncation or
  an endlessly repeated cursor. Source snapshots remain bounded at 100000 rows.
  Aggregate filtered-query working input is separately bounded to 100000 rows and
  64 MiB encoded metadata/rows across snapshots; stream/filter before retaining
  rows. Limit admitted sources to1024 as well. Exhaustion is partial with an
  explicit query_budget_exceeded gap (or unavailable if nothing was admitted),
  never an incomplete result advertised as complete. The cursor covers only the
  explicitly admitted selection. This is not a measured whole-process RAM cap.
- Follow current compact Settings conventions. The new section manages real
  structured observations only, not previews of absent future features. No
  schedule or model-facing admission is implied by showing local data.

## Task 1: Receipt Bindings And Catalog Pagination

**Files:** modify `src/sec_research/schema.py`, `store.py`, `service.py`;
create `src/sec_research/queries.py`, `tests/test_sec_research_queries.py`;
modify `tests/test_sec_research_store.py`, `test_sec_research_service.py`.

**Interfaces:** add immutable receipt `source_snapshots` JSON mapping each completed
locator to `{snapshot_id, observed_at}`. `Store.record_receipt` validates referenced
CIK/kind/locator before writing; service captures publish's return and carries the
mapping through resume. Direct old-style test receipts may omit bindings only as
explicitly unbound observations; they can never satisfy a covered public query.
`StoredQueries(store).filings(cik, *, forms=None, filed_from=None, filed_to=None,
include_amendments=True, cursor=None, limit=20)` produces the closed envelope.
The same class supplies validated receipt/cursor helpers consumed by Task 2.

- [x] RED: source binding survives repeated unchanged capture and restart;
  cross-issuer/kind/locator bindings fail; an interrupted new refresh cannot borrow
  an older successful snapshot. Add filter-before-limit, amendment and cursor tests.

```python
first = queries.filings(CIK, forms=['10-K'], limit=1)
refresh_with_new_catalog()
second = queries.filings(CIK, forms=['10-K'], limit=1,
                        cursor=first['next_cursor'])
assert first['coverage']['receipt_id'] == second['coverage']['receipt_id']
assert second['data'][0]['filing_id'] == original_second_filing_id
```

- [x] Run named RED owners through the isolated offline harness; expected missing
  binding/query behavior, not missing fixture dependencies.
- [x] Add binding validation and stable receipt reopening. Read only bound catalog
  snapshots; merge identical duplicate filing rows, flag conflicting metadata for
  the same filing instead of choosing arbitrary source order. Sort deterministically
  by filed_date descending then accession/filing identity. Normalize form sets;
  `10-K` includes `10-K/A` only when include_amendments is true. Apply dates/forms
  before pagination. Missing historical coverage stays partial even with zero rows.
- [x] Own `test_receipt_sequence_does_not_reuse_committed_ids` and
  `test_sec_schema_leaves_unrelated_autoincrement_sequence_owned_by_sqlite`.
  Inverse mutants: remove AUTOINCREMENT at max-id boundary, use latest receipt on
  cursor continuation, ignore cursor filter hash. Each must kill its named owner.
- [x] Run all existing SEC suites; independent review, fix findings and commit.

## Task 2: Exact Stored Financial Fact Queries

**Files:** create `src/sec_research/fact_queries.py`,
`tests/test_sec_research_fact_queries.py`; extend `queries.py` with a thin `.facts`
entry if needed. Do not duplicate receipt/cursor/envelope mechanics.

**Interfaces:** `StoredQueries.facts(cik, *, metrics=None, concepts=None,
fact_ids=None, accession=None, as_of=None, period='all', start=None, end=None,
revisions='latest', cursor=None, limit=40)`.

- [x] RED exact decimal, non-USD unit, unavailable versus observed-empty, filing
  availability `as_of`, amendment/latest/all, competing values, missing concepts,
  stable cursor, immutable fact-id reopen, and incompatible filters.

```python
page = queries.facts(CIK, concepts=['us-gaap:Assets'], as_of='2026-02-01')
assert page['data'][0]['value'] == '1234567890123456789.123'
assert all(row['filed_date'] <= '2026-02-01' for row in page['data'])
```

- [x] Reuse reviewed concept alternatives from INCOME_STATEMENT_MAPPING,
  BALANCE_SHEET_MAPPING and CASH_FLOW_MAPPING, not float-based selection code.
  Expose metrics revenue/net_income/operating_income/assets/liabilities/equity/cash/
  operating_cash_flow/capex/eps/shares and exact namespaced concepts. Alternative
  concepts are visible observations, not arbitrarily collapsed interchangeable
  values; missing requested metrics receive typed gaps.
- [x] Return reported values only. Distinguish instant/duration windows using the
  original start/end, fiscal labels and frame without deriving Q4 or TTM. Unknown
  period classification is a gap, not a fabricated quarter. Group revisions by
  concept/unit/start/end, take latest available filing date deterministically;
  competing different values at the same latest date remain visible with conflict
  gaps rather than arbitrary accession tie breaking. Preserve source references.
- [x] `fact_ids` reopens retained immutable rows without current/latest selection;
  reject simultaneous metrics/concepts/accession/as_of/period/start/end/revision
  filters. Bind pagination to the requested ids and immutable observation set.
- [x] Inverse mutants: float conversion, period-end instead of filed-date as_of,
  applying latest selection to fact_ids. Named owners must fail, then restore.
- [x] Run related suites; independent review and commit.

## Task 3: Management And Query HTTP Contracts

**Files:** modify `src/api/routes/sec_research.py`,
`tests/test_sec_research_routes.py`, `tests/test_api.py`,
`tests/test_security_lifecycle_routes.py`.

**Interfaces:** retain current GET `/sec-research/{cik}` and explicit POST refresh.
Add static GET/PUT `/sec-research/config` before generic CIK route, plus stored
GET `/sec-research/{cik}/filings` and `/facts`. Query list parameters are repeatable.
GET config returns `{capture_budget_bytes, capacity}`; capacity is null if no
canonical store, otherwise the CaptureStore.status accounting dict. PUT accepts
only strict `{capture_budget_bytes: int}`, persists through typed accessor and
returns the saved value. All query errors are closed 422 codes; storage failures
are unavailable envelopes without provider/body/path exception text.

- [x] RED: read routes cannot construct transport/install/recover; static config
  is not captured by CIK matching; all filter/cursor parameters reach the real
  stored query; permission denial occurs before any mutation owner construction.
  Quota reduction affects neither files nor schedule; invalid persisted config
  is explicit, not silently repaired. Existing refresh/resume still works.

```python
response = client.put('/sec-research/config', json={'capture_budget_bytes': 1})
assert response.json()['capture_budget_bytes'] == 1
assert existing_capture_bytes() == before
assert transport_calls == []
```

- [x] Connect thin adapters; no ticker guessing or hidden freshness/acquisition.
  Reconcile exact route counts from actual registrations (expected +4, 218->222),
  not by deleting count contracts. Query future freshness admission is not exposed.
- [x] Run API/permission/source suites; independent review and commit.

## Task 4: Real Settings Consumers

**Files:** modify `apps/arkscope-web/src/api.ts`,
`settings/DataStorageSection.tsx`, Settings registry/copy where required and the
English/Traditional Chinese Settings resource files; create
`settings/SecResearchPanel.tsx` and focused Vitest tests beside existing tests.

**Interfaces:** consume precisely Task 3 routes. Typed API helpers use existing
request/error handling. Panel uses explicit CIK input, local status, catalog/facts
tabs, bounded next/previous page navigation, refresh and resume commands, quota
edit/save and current object/reservation/orphan charges. No per-model controls.

- [x] RED: first render performs stored GET only; quota save exact bytes and error
  does not claim saved; refresh/resume distinct payloads; selected issuer/filter
  resets cursors; delayed old request cannot overwrite a new issuer; follow cursor
  unchanged; partial/unavailable/empty states display distinctly.
- [x] Build compact unframed section with existing components/lucide tooltips,
  labels/toggles/selects/tables and i18n. Avoid nested panels and explanatory
  feature copy. Show CIK explicitly instead of pretending ticker resolution exists.
  Preserve unsaved quota draft during data refresh; re-read confirmed setting after
  save. Long values and dates cannot overlap on narrow viewports.
- [x] Refresh uses an explicit ten-minute client wait allowance, not the generic
  15-second JSON helper default. Transport timeout is per request/read, so this is
  not a server wall-clock/cancellation guarantee. A disconnected/timed-out command
  is unconfirmed, offers stored-status reread and is never automatically retried.
- [x] Focused/full frontend tests, typecheck, i18n check and fixture-only Playwright
  desktop/mobile screenshots. Network must be mocked, not live backend/provider.
  Independently review UI and its API handling, then commit.

## Verification And Closeout

- [ ] Final independent whole-change review after all task fixes.
- [ ] Re-run backend with fresh isolated HOME/data/config/token/lock paths using
  the archived offline harness copied into this plan's own ignored workspace.
  Baseline is 8446 nodes (8434 pass/12 skip), reconcile added/removed nodes exactly.
  Do not mask runner failures by changing product contracts or historical tests.
- [ ] Re-run mechanical census against the existing audit baseline. Reconcile
  candidates/uncertainties/coverage changes; HTTP routes now have actual UI
  consumers. Keep foundation/wiring and cleanup owners explicit, no clean claim
  from a partial candidate list.
- [ ] Archive raw RED/GREEN/inverse/review/full suite evidence plus hashes,
  update spec/priority-map progress. Do not label SEC first release complete.
  News collector cleanup, actual old-schema disposition and SQLite upgrade remain
  open; no irreversible operation or merge is included in this work.
