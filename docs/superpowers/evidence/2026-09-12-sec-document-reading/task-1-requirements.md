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

- [ ] RED named owners `test_directory_rejects_escape_and_cross_accession`,
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

- [ ] Verify RED from missing/new behavior, not fixture import failure. Parse
  directory JSON with the existing exact decoder; reject malformed lists, duplicate
  conflicting names, unsafe names and mismatched directory path. Directory-only
  entries are not fetchable. Size is advisory; missing/empty size is unknown, not
  zero and not a permission to truncate. Preserve source provenance.
- [ ] Stream existing admitted HTML/XHTML/plain/XML extraction primitives with
  explicit complexity limits. Preserve iXBRL visible content and exclude its hidden
  header/data. No remote entity/DTD expansion or fetched subresources. Unsupported
  MIME/PDF is a typed gap. Do not alter lifecycle default text/hashes.
- [ ] Recognize conservative10-K/10-Q form-aware Part/Item headings and common8-K
  numbered item headings from canonical lines. Duplicate/TOC ambiguity omits the
  ambiguous section, retains full text and reports the gap. Unknown forms still
  support whole-text reading. Check during parsing/indexing; avoid quadratic
  repeated prefix encoding. The specification guarantees only unambiguous indexes.
- [ ] Inverse owners: accept unsafe directory name; ignore nesting limit; choose
  a duplicate Item heading. Each must fail a named test and restore source hashes.
  Run shared reader/SEC parser suites; independent review then scoped commit.

