# SEC Document Reading And Pinned Citations Implementation Plan

Historical implementation record. The Settings reader and its GET/POST document
adapters below were superseded by the user-approved 2026-09-15 hand-test decision:
human full-document reading uses official browser links; model document tools
and the independent Research citation viewer remain. See the current
[hand-test checklist](2026-09-15-sec-current-runtime-hand-test.md).

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development. Execute RED-first, independently
> review each task and the complete integrated change.

**Goal:** Read selected cataloged SEC documents, retain original/canonical bytes,
and reopen exact cited passages through a usable local Settings reader.

**Architecture:** A pure document owner validates directory entries and extracts
bounded canonical text. The existing capture store accounts original/text objects;
immutable document records bind catalog/directory evidence and byte-range citations.
Stored GETs never acquire; explicit POSTs use shared SEC identity/pacing and one
document-acquisition lease per capture root. No unfinished Research tool replaces
the current tool until the broader first-release contracts are complete.

**Tech Stack:** Existing Python/SQLite/FastAPI, PublicSourceReader/SecSourcePolicy,
HTMLParser/defusedxml, React/TypeScript/lucide/Vitest. No dependency installation.

**Spec:** `docs/superpowers/specs/2026-09-10-sec-research-substrate-design.md`,
especially sections4/7/8/9/10/11. Base `3e98bda2`. This implements the already
approved document-reading subsystem, not a fresh product-design decision.

## Global Constraints

- Work only in `/tmp/arkscope-listing-sec-macro-convergence`. No real provider
  data call, production DB/config/token access, schema DROP/reset, install,
  App restart, merge or push. Disposable fixture installation is permitted.
- Preserve current prices/news/SA/financial_cache/lifecycle/research history,
  task model routes, all current tools and their four transport boundaries.
- Keep canonical mismatch explicit; no startup repair, migration chain or
  automatic discard. Recovery work SEC-RECOVERY-001/002 is registered separately.
- Original document limits:32MiB wire/128MiB decoded per response. Metadata
  directory remains16MiB, canonical UTF-8 text at most128MiB. Account both unique
  persisted objects through CaptureStore; preserve the adjustable100GiB budget.
- One explicit document acquisition per root across processes; short write locks
  only, no capture writer/market lock during network or parsing. Public reader
  gets one request and zero redirects per directory/document operation; no retry
  or fallback URL. Keep unrelated SecTransport metadata retry policy unchanged.
- Parser limits are separate: stream chunks, maximum markup buffer1MiB, nesting
  512 and2million parser events/fragments; fail with typed complexity gap, not
  truncated success. Test conservative resource bounds and cancellation, with
  a bounded synthetic memory probe; do not claim a whole-App4GiB/RSS guarantee.
- Exact cataloged accession identity is the only URL authority. CIK is a filer
  identifier, not proof of same-security continuity. Do not require accession's
  first ten digits to equal issuer CIK (filing agents can have another CIK).
- Directory URL is the cataloged accession root plus `index.json`; only actual
  safe file basenames from its observed item list are eligible. Explicit entry
  IDs use `file:<basename>`; `primary` is an alias resolved against catalog metadata
  and that directory. No arbitrary URL/path, guessed XML or symbol fallback.
- Stable capture IDs pin original bytes, canonical text, extraction version,
  catalog+directory evidence and observation. A new failed refresh does not make
  retained older text the current successful result. Explicit pinned reads remain
  valid independent of latest receipts/catalogs. Never render acquired HTML.
- Closed envelopes:status/data/gaps/observed_at/coverage/next_cursor. `empty`
  requires a fully observed selection. Missing/ambiguous sections are gaps plus
  access to the whole pageable document, never a substituted first paragraph.
- Literal search is case-sensitive, not a regex. Every returned passage records
  exact canonical UTF-8 start-inclusive/end-exclusive bytes, original/text hashes,
  source URL, accession and capture ID. Reopening after restart/relocation must
  return the identical bytes. Page size1..20000 characters, default6000, and whole
  encoded envelope<=256KiB. Cursors<=4096bytes, bind capture/document/filter/mode/
  max_chars and byte position; validate before storage. No fake receipt IDs to
  force document cursors into the existing structured-query integer anchor.
- No model-facing registration, automatic document prefetch, issuer resolution,
  Research trace integration, export, schedule or destructive recovery in this batch.

## Task 1: Bounded Document Core

**Files:** create `src/sec_research/documents.py`,
`src/sec_research/document_text.py`, `tests/test_sec_research_documents.py`,
`tests/test_sec_research_document_text.py`; narrowly modify
`src/lifecycle_public_sources.py` for an optional text extractor callback only.

**Interfaces:** `parse_filing_id(value)->(cik,accession)`;
`directory_url(filing_id)->str`;
`parse_document_directory(body, *, filing_id)->DocumentDirectory` with frozen
entries(name,document_id,url,size_bytes,source pointer/hash), original body digest.
`extract_document_text(body, content_type, *, check)->(text,mime)`;
`index_sections(text, form, *, check)->(sections,gaps)`, section entries containing
section_id,label,start_byte,end_byte. This pure core does not publish or request.
PublicSourceReader optional `text_extractor` receives the same body/content_type
and `check` as the existing extraction path; omitted means existing behavior.

- [x] RED named owners `test_directory_rejects_escape_and_cross_accession`,
  `test_directory_keeps_actual_document_ids_and_unknown_size`,
  `test_accession_filer_prefix_need_not_equal_issuer`,
  `test_sec_text_keeps_visible_ixbrl_and_hides_ix_hidden`,
  `test_sec_parser_limits_fail_without_truncation`,
  `test_ambiguous_toc_heading_does_not_fabricate_section`,
  `test_section_offsets_are_exact_utf8` and
  `test_default_public_reader_extraction_unchanged`.

```python
text = "ITEM 1. BUSINESS\nCafe\nITEM 1A. RISK FACTORS\nRisks"
sections, gaps = index_sections(text, "10-K", check=lambda: None)
section = next(row for row in sections if row["section_id"] == "item_1")
assert text.encode()[section["start_byte"]:section["end_byte"]].decode().startswith("ITEM 1.")
```

- [x] Verify RED from missing/new behavior, not fixture import failure. Parse
  directory JSON with the existing exact decoder; reject malformed lists, duplicate
  conflicting names, unsafe names and mismatched directory path. Directory-only
  entries are not fetchable. Size is advisory; missing/empty size is unknown, not
  zero and not a permission to truncate. Preserve source provenance.
- [x] Stream existing admitted HTML/XHTML/plain/XML extraction primitives with
  explicit complexity limits. Preserve iXBRL visible content and exclude its hidden
  header/data. No remote entity/DTD expansion or fetched subresources. Unsupported
  MIME/PDF is a typed gap. Do not alter lifecycle default text/hashes.
- [x] Recognize conservative10-K/10-Q form-aware Part/Item headings and common8-K
  numbered item headings from canonical lines. Duplicate/TOC ambiguity omits the
  ambiguous section, retains full text and reports the gap. Unknown forms still
  support whole-text reading. Check during parsing/indexing; avoid quadratic
  repeated prefix encoding. The specification guarantees only unambiguous indexes.
- [x] Inverse owners: accept unsafe directory name; ignore nesting limit; choose
  a duplicate Item heading. Each must fail a named test and restore source hashes.
  Run shared reader/SEC parser suites; independent review then scoped commit.

## Task 2: Durable Document Acquisition And Stored Passages

**Files:** create `src/sec_research/document_store.py`, `document_service.py`,
`document_queries.py`, tests `test_sec_research_document_store.py`,
`test_sec_research_document_service.py`, `test_sec_research_document_queries.py`;
modify `schema.py`, `capture_lock.py` and affected exact-schema tests.

**Interfaces:** `DocumentStore(store)` delegates connections/short writes to Store.
`DocumentService(store,captures, *, reader_factory, clock).refresh(filing_id,
document_id="primary", check=None)` explicitly acquires directory + chosen file.
`DocumentQueries(store,captures).read(filing_id, *, document_id="primary",
capture_id=None, section_id=None, query=None, cursor=None, max_chars=6000)` returns
the closed envelope. Pure `validate_document_query(...)` normalizes before I/O.
Reader factory receives limits, observer and bounded extractor, and returns a
PublicSourceReader-compatible instance. Production identity comes from explicit
profile configuration at the API boundary, never a new env fallback.

- [x] RED named owners for immutable original/text object registration, repeated
  capture, exact schema mismatch, unrelated-table preservation, missing/corrupt
  object rejection, interruption before publication and lock-free provider call.
  Add `test_document_primary_must_be_in_bound_directory`,
  `test_conflicting_catalog_primary_never_dispatches`,
  `test_failed_refresh_does_not_borrow_latest_capture`,
  `test_pinned_capture_survives_refresh_restart_and_relocation`,
  `test_document_cursor_binds_capture_filter_and_size`,
  `test_passage_offsets_preserve_multibyte_text`, and
  `test_capture_budget_blocks_document_request`.

```python
old = service.refresh(FILING_ID)
first = queries.read(FILING_ID, capture_id=old["capture_id"], query="needle", max_chars=80)
service.refresh(FILING_ID)  # generated different original body
again = queries.read(FILING_ID, capture_id=old["capture_id"], query="needle", max_chars=80)
assert again == first
```

- [x] Add immutable owned directory/document/attempt records and exact canonical
  verification. Records reference existing object/catalog snapshots with FKs;
  original/text/directory bytes go through CaptureStore, never ad hoc file writes.
  Capture identity includes immutable observation/provenance metadata. Keep
  structured receipt kind/anchors unchanged; new failed attempts retain history.
- [x] Resolve filing metadata only from receipt-bound catalog snapshots, using
  existing query binding/bounded-source mechanics. Ambiguous primary/form metadata
  is unavailable before document dispatch; pinned reads do not re-resolve it.
  A directory's observed safe file ID, not extension or arbitraryURL, grants
  acquisition. Capture root document lease is separate from the short writer lease.
- [x] Preflight quota/space before each request. Strict32/128MiB document and
 16MiB metadata limits; one attempt/no redirects; record actual wire/decoded sizes
  from reader observations. Keep body observer in memory until parsing succeeds;
  original bytes are after decompression, not wire bytes. Hash-check all bytes
  before publication. Cancellation calls request_stop and awaits the owned worker
  if an async/thread bridge is introduced; do not leave a writer running.
- [x] No section/query/cursor returns a bounded document/section index with a
  `text_start_cursor`; index continuation must expose all admitted entries without
  truncation. `data` contains document metadata, document entries, sections and
  passages as appropriate. Literal query searches only the requested section if
  supplied; paginate non-overlapping match starts with exact context citations.
  Unknown section is unavailable with its gap and whole-text start cursor.
  Pinned capture and cursor can never switch to latest. Stored reads acquire nothing.
- [x] Inverses: substitute latest for pinned capture; remove query cursor binding;
  fabricate primary file absence; mark truncated read complete. Each kills its
  named owner. Run all SEC/store/reader/lock tests, independent review and commit.

## Task 3: Stored Read And Explicit Acquisition HTTP

**Files:** modify `src/api/routes/sec_research.py`, add focused
`tests/test_sec_research_document_routes.py`, adjust exact route-count owners
`tests/test_api.py` and `tests/test_security_lifecycle_routes.py`.

**Interfaces:** GET `/sec-research/filings/{filing_id}/document` with exactly the
DocumentQueries operands. POST at the same path accepts strict
`{document_id:"primary"}` (extra fields forbidden). GET returns closed envelope;
POST returns attempt with status/gaps/capture_id and never pretends a timeout
failed before dispatch. Add two actual routes222->224, no other route removed.
Static segments cannot be captured by existing `/{cik}` routes.

- [x] RED query/cursor validation before absent/corrupt store handling, zero
  GET acquisition/implicit installation, invalid IDs and permission denial before
  mutation, exact profile identity use and small real-service integration.
- [x] Connect both real service paths. Profile-configured SecSourcePolicy handles
  each actual SEC request; no env credentials/providerfallback. POST may explicitly
  install a fresh schema but not repair old shapes. Use content-free typed errors.
  Validate malformed operands consistently422 even before installation; valid
  missing store/document is an unavailable envelope, not an empty document.
- [x] Tests preserve existing six SEC endpoints and current task/registry contracts.
  Run actual mounted route inventory, shared permissions and all SEC suites;
  independent review then scoped commit.

## Task 4: Settings Filing Reader

**Files:** extend `apps/arkscope-web/src/api.ts`, `settings/SecResearchPanel.tsx`,
`settings/secResearch.css`, English/zh-Hant Settings resources; add
`settings/SecDocumentReader.tsx`, adjacent focused tests and API helper tests.

**Interfaces:** a lucide read/open command on each catalog row opens the document
reader for that exact filing. Initial selection performs stored GET only. Explicit
acquisition POST uses a ten-minute client allowance and offers GET reread when
outcome is unknown, never auto-retries POST. View shows document choice, sections,
literal search, bounded page navigation, capture time and source citation link.

- [x] RED stored-only opening, original selected filing identity, conflict rows
  retained, stale async response ignored after changing filing/closing, exact
  Unicode text, current/pinned distinction and lostPOSTstate. Ensure pagination
  forwards unchanged cursor and filters and does not silently switch captures.
- [x] Use a side panel or unframed bounded reader beside/below the table, consistent
  with existing Settings. No fetched HTML rendering, unsafe links, nested cards
  or giant data dumps. Use actual available document entries, form-aware sections
  and plaintext passages. Stable control/table dimensions and mobile scrolling.
  Citation metadata remains available without making it the primary reading text.
- [x] Complete frontend/typecheck/i18n tests and fixture-only Playwright en/zh-Hant
  desktop/mobile through actual HTTP/service/store with generated transport bodies.
  Verify original/pinned reopening, next/back, section/search, unknown-section gap,
  lostPOSTreread and no unexpected requests. Inspect screenshots for overlaps.
  Independent review and commit; no production App/provider call.

## Final Gates

- [x] All four task reviews and final whole-change review approved; fix full
  findings lists with RED evidence, not successive undocumented partial reviews.
- [x] Fresh complete backend baseline8823nodes(8811P/12S); reconcile exact added/
  removed/executed nodes and unchanged skip identities. Freeze source identities
  during execution. Full frontend baseline1738; no guessed passing counts.
- [x] Mechanical census against the sealed query/Settings batch; report raw
  candidates, uncertainties, coverage/dependency/untracked drift honestly.
- [x] Archive logs, commands, inverses, reviews, source hashes and browser evidence.
  Update current spec/priority map with actual completed and remaining scope.
  Register SEC-RECOVERY-001/002 as open, not silently completed by this feature.
  No merge/push/production activation. Remove only this plan's disposable scratch
  after evidence is safely published and verified.

### Completion Record

Product checkpoint `02a0fff4`: four task reviews and final integrated review
approved. Complete backend9168P/12unchangedS reconciles9180nodes,+357/-0;
frontend1776P, typecheck/i18n and four real-service/store browser fixtures pass.
All1102product/test hashes remain frozen. Current17inverses yield63intended
failures, no errors. Census remains review_required (four newly observed
candidates have real consumers), with no coverage/dependency/untracked drift.
The archive contains785manifested artifacts, all verified against their source
hashes and exact Git-index bytes, plus the manifest. Initial normal staging
omitted compressed logs under existing `*.log.*`; only this named archive was
explicitly force-added, without changing ignore rules. Evidence, including failed
launches and review RED checkpoints, is under
`docs/superpowers/evidence/2026-09-12-sec-document-reading/README.md`.
Fixture server and agents are stopped. No merge/push or production activation.
The live product/current-doc diff passes whitespace checking. The full staged
archive check reports only original trailing blank lines in task-1/2/3-requirements.md;
these extracted briefs remain verbatim under their recorded hashes. This is an
archive-format warning, not a claim that the entire staged diff is whitespace-clean.

## Public Technical Sources

- https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
  documents actual accession directories/index.json and filer-agent CIK distinction.
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces
  distinguishes submissions metadata from extracted XBRL/companyfacts.
These are documentation reads, not authorizations for issuer/provider acquisition.
