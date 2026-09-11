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

- [ ] RED named owners for immutable original/text object registration, repeated
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

- [ ] Add immutable owned directory/document/attempt records and exact canonical
  verification. Records reference existing object/catalog snapshots with FKs;
  original/text/directory bytes go through CaptureStore, never ad hoc file writes.
  Capture identity includes immutable observation/provenance metadata. Keep
  structured receipt kind/anchors unchanged; new failed attempts retain history.
- [ ] Resolve filing metadata only from receipt-bound catalog snapshots, using
  existing query binding/bounded-source mechanics. Ambiguous primary/form metadata
  is unavailable before document dispatch; pinned reads do not re-resolve it.
  A directory's observed safe file ID, not extension or arbitraryURL, grants
  acquisition. Capture root document lease is separate from the short writer lease.
- [ ] Preflight quota/space before each request. Strict32/128MiB document and
 16MiB metadata limits; one attempt/no redirects; record actual wire/decoded sizes
  from reader observations. Keep body observer in memory until parsing succeeds;
  original bytes are after decompression, not wire bytes. Hash-check all bytes
  before publication. Cancellation calls request_stop and awaits the owned worker
  if an async/thread bridge is introduced; do not leave a writer running.
- [ ] No section/query/cursor returns a bounded document/section index with a
  `text_start_cursor`; index continuation must expose all admitted entries without
  truncation. `data` contains document metadata, document entries, sections and
  passages as appropriate. Literal query searches only the requested section if
  supplied; paginate non-overlapping match starts with exact context citations.
  Unknown section is unavailable with its gap and whole-text start cursor.
  Pinned capture and cursor can never switch to latest. Stored reads acquire nothing.
- [ ] Inverses: substitute latest for pinned capture; remove query cursor binding;
  fabricate primary file absence; mark truncated read complete. Each kills its
  named owner. Run all SEC/store/reader/lock tests, independent review and commit.

