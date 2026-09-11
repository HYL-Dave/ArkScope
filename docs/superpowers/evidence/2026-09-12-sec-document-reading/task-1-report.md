# Task1 Report: Bounded Document Core

## Status And Scope

Implemented Task1 only in `/tmp/arkscope-listing-sec-macro-convergence`, based on
`98499d653e60e4e0a194fa46d89fb7705376ebfe`. Authority: original execution notes,
`task-1-requirements.md`, previously read global constraints, approved spec section7,
and the adjacent preflight ledger. Corrected parent baseline:884P; the earlier
exit4/no-tests typo is not counted as a baseline or RED.

Initial commit: `195a486e62ddf85f42d1735e0cadccd15dfaaec7`,
`feat(sec-research): add bounded document parsing core`. Committed only the five
listed product/test files after the granted sole index window and completed checks.
Initial review range: `98499d653e60e4e0a194fa46d89fb7705376ebfe..195a486e62ddf85f42d1735e0cadccd15dfaaec7`.
At that initial commit the tracked worktree/index were clean and the source hashes
matched the original pre-inverse manifest. Scratch evidence and this report remain available in place
for the parent's evidence archive rather than being added to the product commit.
Independent review belongs to the parent; this report is a self-review, not approval.

Current status: I1 and I2 were closed by the parent's round1 re-review of
`6cad56cf55a08955f389644ecae9cb0d64d875df`. Its new Important R1-1 is implemented in
fix round2, committed as `b07eba2bfaec64488f5f68eed523d5f1bf724211` after final
verification. The tracked worktree/index are clean; all five source hashes match
the round2 restoration manifest. Parent's scoped R1-1 re-review is pending. The
initial namespace-alias limitation and duplicate-as-body-transition assumption
were not approved and are superseded. This is self-review evidence, not approval.

Product/test scope is exactly:

- `src/sec_research/documents.py`
- `src/sec_research/document_text.py`
- `src/lifecycle_public_sources.py` (optional extractor argument/selection only)
- `tests/test_sec_research_documents.py`
- `tests/test_sec_research_document_text.py`

All own logs/probes/manifests are in `task-1/` or create-only `task1-*` run directories
beside this report. No subagents, dependencies, provider calls, private data/config,
other tasks/docs, schema changes, or production activation. Parent integration
fixtures were not modified or represented as Task1 evidence.

## Exact Public Types

`documents.py` exports frozen dataclasses (all collections are tuples):

```python
DocumentEntry(
    name: str,
    document_id: str,                 # "file:" + observed literal basename
    url: str,
    size_bytes: int | None,
    source: SourceRef,                # frozen SourceRef(sha256: str, pointer: str)
)
DocumentDirectory(
    filing_id: str,
    cik: str,                        # exact cataloged ten-digit nonzero CIK
    accession: str,                  # NNNNNNNNNN-NN-NNNNNN, independent filer CIK
    url: str,                        # bound accession directory's index.json
    sha256: str,                     # SHA256 of unmodified supplied body bytes
    entries: tuple[DocumentEntry, ...],
)
parse_filing_id(value: str) -> tuple[str, str]
directory_url(filing_id: str) -> str
parse_document_directory(body: bytes, *, filing_id: str) -> DocumentDirectory
```

Entry `source.pointer` is `/directory/item/<original-list-index>` and the hash is
the original directory digest. Conflicting duplicate names reject the entire
directory; identical duplicate rows retain the first pointer. Missing/null/empty
size is `None`, true numeric zero remains zero, and size never authorizes truncation.
Directory-only `dir`/`directory` rows are not returned as fetchable entries.
Basenames use the existing catalog validator; directory JSON uses `decode_object`.
The directory's `name` must exactly match the canonical accession path, without a
trailing slash or origin. Errors are existing `SourceError(code: str, pointer: str)`.

`document_text.py` exports these return shapes (TypedDict records are plain dicts):

```python
EXTRACTION_VERSION = "sec-document-text-v3"  # changed in fix round2
extract_document_text(
    body: bytes, content_type: str, *, check: Callable[[], object]
) -> tuple[str, str]                 # canonical text, admitted MIME

class Section(TypedDict):
    section_id: str
    label: str
    start_byte: int
    end_byte: int

class SectionGap(TypedDict):
    code: str
    section_id: str | None

index_sections(
    text: str, form: str, *, check: Callable[[], object]
) -> tuple[list[Section], list[SectionGap]]
```

MIME admission: `text/plain`, `text/html`, `application/xhtml+xml`, `application/xml`,
`text/xml`. HTML uses the existing `_SourceTextParser` owner with SEC skip tags and
bounds; normalization reuses `_normalize_text` in bounded chunks. XML uses the
existing defused parser/C14N primitives without DOM construction or DTD/entity work.
The new extractor intentionally does NOT admit directory JSON; directory acquisition
must keep the existing reader's JSON extraction path and parse original observed
bytes with `parse_document_directory`. PDF and other unsupported MIME types raise
`SourceReadError("source_format_unsupported")`.

Other content-free `SourceReadError` codes: `source_document_complexity`,
`source_decoded_body_too_large`, `source_text_too_large`, `source_document_invalid`,
`source_encoding_unsupported`, `source_text_empty`. Reader cancellation/deadline
codes propagate. No failure returns successful truncated text.

The optional `PublicSourceReader(..., text_extractor=None)` callback is invoked as
`extractor(body: bytes, content_type: str, check=reader._remaining) -> tuple[str, str]`.
It runs before the existing document observer and digest/publication path.
Omitted/None selects the unchanged `_page_text` function; no lifecycle defaults,
transport behavior, canonicalization, hashes, or retry policy were changed.

Section IDs:10-K `item_1`, `item_1a`, etc.; Parts `part_i`..`part_iv`;10-Q
`part_i_item_1`, `part_ii_item_1`, etc.;8-K `item_1_01`, `item_9_01`, etc.
Amendment suffix `/A` is admitted. Labels preserve the trimmed canonical heading.
Byte ranges are exact UTF8 start-inclusive/end-exclusive; Part ranges contain their
Items, Item ranges stop at the next recognized heading or EOF. Section results
remain in document order. Gaps are `section_ambiguous` with a specific ID, or
`section_index_unsupported` / `section_index_unavailable` with `section_id=None`.

## RED And GREEN

Every test execution used the required isolated runner prefix:

```text
/home/hyl/.virtualenvs/llm_app/bin/python -B
.superpowers/sdd/2026-09-12-sec-document-reading/run_checks.py NAME backend -q PATHS
```

Each run directory retains exact `command.json`, `output.log`, and `results.xml`.
The original logs were never overwritten or renamed.

| Run | Result | Purpose |
| --- | --- | --- |
| `task1-red-core-01` | 87F/1P, exit1 | All eight named owners reach behavioral failures against minimal interfaces; no collection/import errors. Default reader case passes, custom callback case fails. |
| `task1-green-core-01` | 88P | Initial two-file focused suite. |
| `task1-red-encoding-01` | 6F, exit1 | Self-review: non-text codecs and surrogate output must be typed encoding gaps. |
| `task1-green-core-02` | 4F/94P, exit1 | Retained failed iteration: empty-byte decode skips the codec admission check. |
| `task1-green-core-03` | 98P | Text-codec registry gate and UTF8 validation resolve all six cases. |
| `task1-probe-01` | 10P | Bounded synthetic allocations, cancellation, default event ceiling and normalization checks. |
| `task1-regression-01` | 1130P, no skips | All SEC research, public reader, wire and additional relevant shared suites. |
| `task1-precommit-01` | 99P | Fresh98-test core plus raw evidence/owner-count/source-restoration verification. |

The two focused paths are `tests/test_sec_research_documents.py` and
`tests/test_sec_research_document_text.py`. Named original RED owners are:
`test_directory_rejects_escape_and_cross_accession`,
`test_directory_keeps_actual_document_ids_and_unknown_size`,
`test_accession_filer_prefix_need_not_equal_issuer`,
`test_sec_text_keeps_visible_ixbrl_and_hides_ix_hidden`,
`test_sec_parser_limits_fail_without_truncation`,
`test_ambiguous_toc_heading_does_not_fabricate_section`,
`test_section_offsets_are_exact_utf8`,
`test_default_public_reader_extraction_unchanged`.

The regression command expanded `tests/test_sec_research_*.py`, plus:
`tests/test_lifecycle_public_sources.py`, `tests/test_lifecycle_public_sources_wire.py`,
`tests/test_lifecycle_source_compatibility.py`, `tests/test_lifecycle_source_capacity.py`,
`tests/test_lifecycle_web_sec_sources.py`, `tests/test_sec_transport.py`,
`tests/test_sec_edgar_financials.py`, `tests/test_sec_user_agent.py`,
`tests/test_security_lifecycle_sec_admission.py`,
`tests/test_security_lifecycle_sec_evidence.py`. Exact expansion is in command.json.
1130 total includes the corrected884 baseline,98 Task1 tests and148 additional
shared regression nodes. This is not a full-backend/frontend or integration claim.

## Inverse Evidence

| Run / Mutation | Owner Path | Result |
| --- | --- | --- |
| `task1-inverse-unsafe-name-01`: bypass basename validator | `tests/test_sec_research_documents.py::test_directory_rejects_escape_and_cross_accession` | 13F/3P; all unsafe names escape, the three cross-directory cases still reject. |
| `task1-inverse-nesting-01`: disable HTML and XML nesting guards | `tests/test_sec_research_document_text.py::test_sec_parser_limits_fail_without_truncation` | 2F/3P; `html-nesting` and `xml-nesting` fail at513 levels. |
| `task1-inverse-duplicate-item-01`: clear duplicate ambiguity, choosing first heading | `tests/test_sec_research_document_text.py::test_ambiguous_toc_heading_does_not_fabricate_section` | 1F; ambiguity gap disappears and first duplicate becomes selectable. |

All failures are behavioral assertions, not imports. Each mutation was restored by
`apply_patch`; `sha256sum -c task-1/source-before-inverses.sha256` verified all five
scoped files after EACH inverse before the next mutation. Full original/mutated/
restored owner hashes and changed statements are in `task-1/inverses.json`.
No product/test source changed after those restorations or during the full regression.

## Resource Evidence

Probe source: `task-1/test_resource_probe.py`; raw measurements are JUnit testcase
`measurement` properties in `task1-probe-01/results.xml`. Input bodies are created
before tracing. Values below measure Python parser allocations, not process RSS.

| Input Bytes | MIME | Output UTF8 Bytes | Peak Traced Bytes |
| --- | --- | --- | --- |
| 1086025 | HTML | 1060005 | 2185487 |
| 1086025 | XML | 1086025 | 2253239 |
| 4344025 | HTML | 4240005 | 8533885 |
| 4344025 | XML | 4344025 | 8718279 |

Cancellation on a1400013-byte synthetic body stops exactly at check50 for plain,
HTML and XML, with measured times0.038668s,0.000449s and0.000310s respectively.
The default event-limit probe rejects a16000015-byte comment stream with a typed
complexity error; no limit was patched for that probe. The12296050-byte UTF8 section
index probe uses7676 peak traced scratch bytes and preserves exact section offsets.
The chunk normalization probe checks100 deterministic plaintext/HTML cases against
the existing helper with seven-byte chunks. No whole-App4GiB/RSS guarantee is made.

## Self-Review And Limitations

- Self-review covered authority binding, exact provenance, unknown size, unchanged
  lifecycle selection/digests, typed errors, cancellation, parser/fragment bounds,
  TOC ambiguity and single-pass byte offsets. The codec issue was reproduced with
  retained RED, fixed, and reverified. That initial self-review missed I1 and I2;
  both accepted findings and their corrections are recorded in fix round1 below.
- Limits are separate:16MiB directory metadata;128MiB input document and canonical
  UTF8 text;1MiB pending markup;512 levels;2million combined parser/feed/fragment
  budget ticks. Counting feed/fragment work is deliberately conservative.32MiB wire
  accounting, acquisition concurrency, persistence, quotas, and cursors belong to
  the later service/store task and are not implemented here.
- The source body and final text are necessarily in memory for these interfaces.
  The synthetic probe is bounded, does not cover every adversarial shape, and is
  not an OS containment or whole-App memory certification. The supplied runner is
  an audit hook with isolated paths, not OS containment.
- Section recognition is deliberately limited to single canonical lines of at most
  240 characters, the admitted form/item sets, standard Part numbering and explicit
  TOC/duplicate ambiguity. It is not a complete SEC layout/TOC recovery engine.
  Unknown forms retain whole-text access. Unrecognized/missing requested IDs must
  be surfaced by the later query owner as gaps, never substituted paragraphs.
- HTML/XHTML uses the existing tolerant HTML parser and inherited hidden attributes,
  now with scoped iXBRL namespace bindings as specified in fix round1. The earlier
  namespace-alias limitation was rejected, not an approved scope reduction. This
  remains plaintext extraction, not browser/CSS layout, OCR, or HTML rendering.
- This pure parser does not verify that a syntactically valid filing ID was actually
  cataloged, resolve `primary`, acquire, publish, or render HTML. The durable owner
  must supply receipt-bound catalog identity and a separately observed directory.
- XML depends on the same installed defused/C14N primitives as the old owner; the
  bounded refinement uses Expat byte positions and default C14N flush behavior.
  No package/dependency version was changed. Parent independent review is pending.

## Review Fix Round1

Authority: the full accepted I1/I2 list in `task-1-review.md`, its unchanged
`task-1/test_independent_review_probe.py`, and the parent's scope/memory clarifications.
Fix base: `195a486e62ddf85f42d1735e0cadccd15dfaaec7`. Only
`src/sec_research/document_text.py` and `tests/test_sec_research_document_text.py`
are changed in the product/test fix. No extra review or subagent was requested;
the parent will perform one scoped re-review of both findings.

Fix commit: `6cad56cf55a08955f389644ecae9cb0d64d875df`,
`fix(sec-research): bind inline namespaces and retain TOC uncertainty`.
Fix review range: `195a486e62ddf85f42d1735e0cadccd15dfaaec7..6cad56cf55a08955f389644ecae9cb0d64d875df`.
Full Task1 range: `98499d653e60e4e0a194fa46d89fb7705376ebfe..6cad56cf55a08955f389644ecae9cb0d64d875df`.
Only the two stated files were staged/committed under sole index permission after
verification. The report and raw fix evidence remain in this plan's scratch for
the parent's archive. No merge, push, or provider/production operation occurred.

### Corrections

I1: the SEC HTML refinement now resolves element/default namespace declarations
before classifying `header`, `hidden`, `references`, or `resources`. URI admission
is exact membership in `http://www.xbrl.org/2013/inlineXBRL` and
`http://www.xbrl.org/2008/inlineXBRL`, not a regex, substring, or casefolded match.
These identities were supplied by the parent from official specification section2.3;
no new browse, document/provider acquisition, or dependency was used.

An active binding map holds only the effective declarations. Each open element
retains only its own declaration delta, not a clone of inherited bindings. Exits
restore prior bindings using the existing tolerant parser stack, including nested
rebinding, self-closing/void elements and parent-close unwinding of descendants.
Declaration and restoration work consume the existing cancellable parser budget.
Conflicting declarations in one element raise `source_document_invalid` rather
than choosing an arbitrary namespace. All four iXBRL hidden element kinds are
excluded through aliases while visible facts remain visible. Unrelated namespaces
and exact-URI lookalikes remain ordinary content. Legacy undeclared `ix:` exclusion
is retained ONLY when there is no active declaration for `ix`; even an explicit
empty binding disables that compatibility path until its scope exits.

I2: a duplicate heading no longer clears TOC uncertainty. Once the explicit
`TABLE OF CONTENTS` marker is encountered, later recognized headings remain
ambiguous through EOF because this task has no independently proven body-transition
mechanism. They are omitted from selectable sections and receive specific
`section_ambiguous` gaps. The complete extracted text remains available to the
whole-text reader. Duplicates without a TOC still omit only their ambiguous IDs;
other unambiguous sections remain selectable. No speculative recovery engine was added.
The original test expecting `item_2` after a TOC duplicate was corrected as part of
I2, not as an unrelated expectation change. The two literal iXBRL fixtures now
declare their intended namespace; separate coverage retains genuine undeclared-ix
compatibility and proves that it cannot override explicit unbinding.

### Task2 Interface Delta

- No function signatures, dataclass fields, TypedDict fields, MIME admission,
  section-ID formats, or gap-code shapes changed.
- `EXTRACTION_VERSION` changed from `sec-document-text-v1` to
  `sec-document-text-v2`. Task2 must persist the current version with canonical
  text/hashes and must not label new extraction as v1. No existing stored capture
  was rewritten; durable capture implementation is outside Task1.
- Canonical HTML/XHTML text now excludes namespace-aliased hidden content and
  retains unrelated explicitly bound content even if its prefix is `ix`.
- Section coverage can be smaller after a TOC marker, including `sections=[]`
  with explicit per-ID ambiguity gaps. This is not an empty or truncated document.
  Task2 must retain whole-text paging as already required.
- The shared `PublicSourceReader` file and its lifecycle default are byte-identical
  to the previously tested Task1 version. Directory interfaces are unchanged.

### Fix RED And GREEN

Every run used the same required create-only isolated runner. Exact commands,
full output and JUnit remain in the named run directories; original evidence was
not replaced. The original evidence verifier remains tied to the initial snapshot;
the new `task-1/test_fix_r1_evidence.py` verifies this fix snapshot separately.

| Run | Result | Purpose |
| --- | --- | --- |
| `task1-fix-r1-red-01` | 39F/56P, exit1 | Ported both review probes; alias, scope, unrelated-namespace and TOC behavior RED before production edits. |
| `task1-fix-r1-red-scope-work-01` | 4F, exit1 | Explicit unbinding, declaration budget and cancellation RED before production edits. |
| `task1-fix-r1-after-i1-01` | 3F/96P, exit1 | Namespace cases pass; only the three expected I2 TOC owners still fail. |
| `task1-fix-r1-green-core-01` | 152P | 149 Task1 tests plus all3 unchanged independent review probes. |
| `task1-fix-r1-probe-01` | 12P | Previous10 bounded resource checks plus2 namespace-delta memory checks. |
| `task1-fix-r1-regression-01` | 1181P, no skips | Same full relevant shared regression path set as the original1130 run, plus51 added Task1 nodes. |
| `task1-fix-r1-precommit-01` | 153P | Fresh149 Task1 tests,3 unchanged independent probes, and1 fix evidence/source-restoration check. |

The initial RED owners include
`test_namespace_aliased_ixbrl_does_not_publish_hidden_facts` and
`test_duplicate_inside_toc_does_not_authorize_later_toc_only_item`, ported directly
from the supplied probe into `tests/test_sec_research_document_text.py`.
Further RED owners cover both rebinding directions, default namespace clearing,
empty/malformed element scope restoration, exact URI identity, all four hidden
local names in unrelated namespaces, conflicting declarations and current-report
TOC uncertainty. Failures are behavioral, not collection/import errors.

### Fix Inverses And Resources

All five inverses modify only `src/sec_research/document_text.py` and are restored
with `apply_patch` before the next mutation. After EACH restoration,
`sha256sum -c task-1/fix-r1-before-inverses.sha256` passed for all five Task1 files.
The restored parser SHA256 is
`da1e0b23f71ccb154e4e71f2d5e2b6d44a928bcdb91e348f3e6b5c4cdd8b7c8a`.
Exact mutated hashes, changed statements, full owner paths and counts are retained
in `task-1/fix-r1-inverses.json`; each run has its own raw log/JUnit/command record.

| Inverse Run | Guard Removed | Result And Owner |
| --- | --- | --- |
| `task1-fix-r1-inverse-alias-01` | Namespace-resolved hidden exclusion | 4F in `test_namespace_aliased_ixbrl_does_not_publish_hidden_facts`. |
| `task1-fix-r1-inverse-namespace-identity-01` | Exact namespace admission, using local names alone | 18F in unrelated-namespace and exact-URI positive controls. |
| `task1-fix-r1-inverse-scope-restoration-01` | Restoring declaration deltas | 10F across both rebinding directions and empty/unwound scopes. |
| `task1-fix-r1-inverse-map-clone-01` | Delta-only storage, copying inherited maps instead | 1F/1P in the resource probe; depth400 reaches60212914 traced bytes and fails the8MiB bound. |
| `task1-fix-r1-inverse-toc-transition-01` | Persistent TOC uncertainty, treating a duplicate as a transition | 3F in the old corrected TOC owner and two newly ported/extended owners. |

Resource probe source: `task-1/test_fix_r1_resource_probe.py`. With4097 root namespace
declarations, the unmutated parser measures3745333 peak traced bytes at depth32
(117022-byte input), and3749381 at depth400 (121070-byte input). Input allocation
is outside tracing. The nearly equal peaks and the map-clone inverse support the
specific inherited-map multiplication guard; they do not certify all adversarial
inputs, process RSS, or whole-App memory. Prior cancellation/default event-limit
and UTF8-index scratch probes also pass on the fixed sources.

Fix-scope self-review confirms that bindings restore with the owner's stack,
URI matching remains exact, explicit unrelated bindings override undeclared-ix
compatibility, errors/cancellation do not return partial text, and TOC uncertainty
cannot be cleared by a duplicate. No lifecycle/default, directory, storage, API,
fixture-service, or frontend product changes were made. Parent re-review remains
pending; passing the supplied probes is not represented as reviewer approval.

## Review Fix Round2

Authority: Important R1-1 only in `task-1-rereview-r1.md`, the unchanged
`task-1/test_rereview_r1_prefix_case_probe.py`, and the parent's QName, scope and
resource clarifications. The parent closed original I1/I2; neither is reopened.
Fix base: `6cad56cf55a08955f389644ecae9cb0d64d875df`. Only
`src/sec_research/document_text.py` and `tests/test_sec_research_document_text.py`
are changed.

Fix commit: `b07eba2bfaec64488f5f68eed523d5f1bf724211`,
`fix(sec-research): preserve XHTML QName case in namespace scopes`.
Fix review range: `6cad56cf55a08955f389644ecae9cb0d64d875df..b07eba2bfaec64488f5f68eed523d5f1bf724211`.
Full Task1 range: `98499d653e60e4e0a194fa46d89fb7705376ebfe..b07eba2bfaec64488f5f68eed523d5f1bf724211`.
Only these two files were staged/committed under sole index permission after all
checks and self-review. Post-commit tracked worktree/index are clean and the five
Task1 source hashes match the round2 manifest. This report and raw evidence remain
in plan scratch for the parent's archive, outside the product commit.

### Correction And Compatibility

`application/xhtml+xml` selects a narrow `_DocumentXHTMLParser` refinement of the
existing bounded SEC/HTML parser. It reads actual source start-tag spelling using
`HTMLParser.get_starttag_text()` and the installed parser's own
`tagfind_tolerant`/`attrfind_tolerant` lexical matchers. Original attribute names
are paired in token order with the values already decoded by HTMLParser. Only
exact `xmlns`/`xmlns:` declaration names enter the namespace binder. Source names
are not guessed from lowercased callback names, and no ix/IX special case is added.

The source QName and case-preserving declaration names reach namespace binding,
same-scope duplicate detection, and namespace/local-name lookup before folding.
The shared structural stack receives the original QName. Real closing QNames are
read from the original end-token buffer before delegation; self-closing tags use
their same original start QName for the synthetic close. Both paths retain exact
case for stack matching and declaration-delta restoration. Case-distinct prefixes,
local names, default declarations, and unqualified element names remain distinct.
An end tag differing only in case cannot prematurely restore another element's
bindings. End-token context is cleared after each parse attempt, including partial
tokens and failure. Namespace URI admission and delta-only storage are unchanged.

This is NOT strict XML reinterpretation: existing fragments, tolerant unmatched
element handling, unquoted attributes, named HTML entities, and void elements stay
admitted. HTML display classification (skip/break/void) is separately case-insensitive
through `_HTMLDisplayNames`; it does not fold structural or namespace identity.
The existing normalized presentation attributes still reach the shared helper,
preserving uppercase HIDDEN/ARIA-HIDDEN controls. No whole-parser copy, generalized
renderer, dependency, or lifecycle-owner change was needed. Existing control tests
were not rewritten to permit a stricter parser.

Source-token inspection ticks the existing budget before tag work and for each
attribute, including non-namespace attributes. Namespace binding/restoration
retains its existing ticks. Temporary declaration lists belong only to the current
bounded token; open elements still retain only their own namespace deltas, not
inherited-map clones. Nesting, token, document, text and event ceilings are unchanged.

### Task2 Interface Delta

- `EXTRACTION_VERSION`: `sec-document-text-v2` -> `sec-document-text-v3`.
  Task2 must persist v3 with newly extracted canonical text/hashes; XHTML bytes
  can now yield different text or become readable after prior false rejection.
  No stored captures were rewritten and no integration/storage implementation
  is claimed here.
- No public function signatures, dataclass fields, TypedDict fields, MIME set,
  section IDs, or error/gap-code shapes changed. Exact current public types appear
  above. Section indexing and the closed conservative I2 behavior are untouched.
- The private `_DocumentHTMLParser.handle_starttag` gains optional keyword-only
  `namespace_attrs=None` so XHTML can supply raw declaration identity separately
  from normalized display attributes. `_DocumentXHTMLParser` and `_HTMLDisplayNames`
  are private refinements, not new public interfaces.
- `text/html`, plain text, XML and the omitted-extractor lifecycle default retain
  their existing paths. Directory types and shared reader source are byte-identical
  to the round1 snapshot.

### RED And GREEN Evidence

All tests used the required create-only runner. Every listed run retains its exact
command/environment, full `output.log`, and JUnit. Earlier RED/GREEN/inverse artifacts
and historical evidence verifiers are unchanged; `task-1/test_fix_r2_evidence.py`
checks the round2 snapshot and its run results separately.

| Run | Result | Purpose |
| --- | --- | --- |
| `task1-fix-r2-red-01` | 17F/27P, exit1; 77 deselected | Before product edits: 20 new XHTML cases plus 24 old XHTML controls selected by `-k xhtml`. |
| `task1-fix-r2-red-review-probes-01` | 2F, exit1 | Both unchanged reviewer probes; run separately because the first run's selector deselected them. |
| `task1-fix-r2-green-core-01` | 174P | 169 Task1 tests, 3 original review probes and both R1-1 probes. |
| `task1-fix-r2-probe-01` | 19P | Prior 12 resource controls plus 7 XHTML-specific memory/cancellation/limit controls. |
| `task1-fix-r2-regression-01` | 1201P, no skips | Same full relevant SEC/shared lifecycle/wire/security path set as round1, plus 20 new nodes. |
| `task1-fix-r2-precommit-01` | 182P | Restored source: 169 Task1 tests, all 5 review probes, 7 XHTML resource controls, and round2 hash/evidence verifier. |

Both supplied reproductions were ported into named product tests:
`test_xhtml_case_distinct_nested_prefix_does_not_rebind_inline_namespace` and
`test_xhtml_case_distinct_namespace_declarations_are_not_conflicting`. Each covers
ix/IX, fact/Fact and F/f, with ElementTree expanded-name checks independent of the
product extractor. Other named RED owners cover namespace/local-name case,
case-distinct nested QName restoration, premature mismatched-case closes,
quote/entity/chunk boundaries, and source-attribute work/cancellation. All failures
are behavioral, not import/collection errors. The two empty-element controls and
the tolerant display control were already positive on the base and stayed positive;
their purpose is preservation, not a claimed new RED.

### Inverse Evidence

Each mutation changed only the extractor, ran the named behavior owners, and was
restored with `apply_patch`. After EACH restoration, all five Task1 hashes passed
`sha256sum -c task-1/fix-r2-before-inverses.sha256`. The final restored extractor is
`2c61f2804360c67300963ece25caf4bf50b6df8734d048c22ff59d18ec385361`.
`task-1/fix-r2-inverses.json` records each exact mutation hash, guard, full test owner
path, count and restoration. The precommit verifier also records restored hashes
in JUnit properties. There are no retained product mutations.

| Inverse Run | Guard Removed | Result |
| --- | --- | --- |
| `task1-fix-r2-inverse-declaration-case-01` | Original attribute case before namespace binding/duplicates | 9F: both ported owner families, declaration-name control, and both unchanged reviewer probes. |
| `task1-fix-r2-inverse-start-qname-01` | Original start QName before lookup/stack identity | 4F: nested-prefix owners and the inline local-name control. |
| `task1-fix-r2-inverse-end-qname-01` | Original real closing QName | 4F: case-distinct nested restoration and mismatched-case close owners. |
| `task1-fix-r2-inverse-empty-qname-01` | Original synthetic closing QName | 2F: both self-closing scope-restoration controls. |
| `task1-fix-r2-inverse-token-work-01` | Per-attribute source-token budget/cancellation tick | 2F: source-attribute work and cancellation owners. |

### Resources And Self-Review

New probe: `task-1/test_fix_r2_resource_probe.py`. With 4098 root declarations
(including 2048 case-distinct prefix pairs), plus one local declaration at each
alternating Scope/scope level, depth32 uses 3753858 peak traced bytes for a
124087-byte body; depth400 uses 3825400 for a 139843-byte body. Both are below 8MiB,
and both return exact visible text while omitting hidden facts. A 1400015-byte
XHTML stream cancels exactly at callback50 with 132796 traced peak bytes and no
returned text. Input allocation is outside tracing. These are bounded synthetic
parser-allocation checks, not all-input/process-RSS/whole-App guarantees.

The new path also passes exact depth512 admission, depth513 rejection, oversized
markup rejection and UTF8 text-limit rejection without truncation. All previous
resource probes, lifecycle default text/hash owners and relevant regressions pass.
Self-review covered the full two-file diff, raw-token/value alignment, both close
paths, case-sensitive map keys/stack keys, exception cleanup, declaration deltas,
budget work and unchanged display behavior. `git diff --check` is clean.

Limitation: this remains the existing tolerant HTML extraction family, not a full
XHTML/XML validator or renderer. The narrow refinement depends on the installed
stdlib HTMLParser's lexical facilities; parser-version changes should rerun these
token/chunk/identity controls. It does not reinterpret previously admitted source
shapes through strict XML, and no broader parsing/canonicalization guarantee is
claimed. No blocking ambiguity or scope expansion was required. No subagent,
additional reviewer, provider, network fetch, private data, installed-skill change,
or parent fixture mutation occurred. Parent's one scoped R1-1 re-review remains
pending; these results are not reviewer approval.
