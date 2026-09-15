# SEC Settings Hand-Test Repair

Base: `f36a7b336aad35d49c043547815e0f28dee463ff`. The user approved this
bounded redesign after testing the isolated current-runtime Desktop on
2026-09-15. This is not a runtime switch, merge or complete live Research
acceptance. No production database was opened for this repair.

## Approved Change

- Once Read Local selects an issuer, settled filter edits automatically query
  local filings/facts after 300 ms. Pages/cursors and stale responses are
  invalidated immediately. Changing a CIK still requires an explicit local
  read. Source refresh/resume remains explicit and separate.
- Remove the full Settings document reader, its two HTTP endpoints, dedicated
  client types/adapters, tests, styles and translations. The table retains the
  official primary-document browser link, labelled SEC original.
- Keep `read_sec_filing`, full-text cursors, literal search, exact retained
  passages and the independent Research citation viewer/API. Improve verified
  section indexing, without choosing an arbitrary duplicate heading.

## Observed Document

Filing: `0000320193:0000320193-25-000079`, `aapl-20250927.htm`.
The user had already downloaded this source into the isolated hand-test store:
`https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl-20250927.htm`.
This repair performs no additional provider request or model call.

- Original bytes: 1,520,208; SHA256
  `548ae59778cf08ee0f2ee088e7ece20d947076c3c01f74d2d65db4c2777e436a`.
- Extracted text: 207,845 bytes; unchanged SHA256
  `6c6372dc63236ef8831c6cfb3ff8d3180f5ecd0a47b52282ff365b0bd81f758a`.
- v4: no verified TOC range, zero sections, 27 `section_ambiguous` gaps.
- v5: verified TOC bytes `[5288, 6576)`, 27 sections, no section/structure gaps.

The TOC title is a div/span label followed by a linked table inside an empty
div. Item labels, titles and page links occupy separate cells; Item 12 puts its
terminal period outside the anchor. The old observer supported semantic
headers/captions and a directly adjacent table, not this observed shape.

The new shape requires explicit safe inline descendants in a plain div/p label,
an adjacent closed linked table, only empty valid div wrappers between them,
and distinct same-document item links. The only permitted unlinked suffix to a
plain item label is its terminal period. Intervening text, unknown/block
descendants, malformed/foreign wrappers, unclosed tables and duplicated body
headings remain negative controls. Unsupported indexing does not remove full
text, search or citations. Text normalization and source bytes are unchanged.

Extraction version v5 applies to **new captures**. Existing v4 captures and
citations are never rewritten or automatically reacquired. A pinned old capture
can still have an unavailable section index, with its original search/text
cursors intact. The replay is not a persistence or live-model acceptance test.

## Reproduction

`replay.py` reads only the explicitly supplied, SHA-verified original object and
the recorded base module from Git. It compares the baseline and current parser
without opening a DB or fetching a URL. Run from this worktree under a read-only,
network-disabled process, passing the locally retained object path:

```sh
bwrap --ro-bind / / --dev-bind /dev /dev --unshare-net \
  env -i PATH=/usr/bin:/bin HOME=/tmp PYTHONDONTWRITEBYTECODE=1 \
  /home/hyl/.virtualenvs/llm_app/bin/python -I -B \
  docs/superpowers/evidence/2026-09-15-sec-settings-usability/replay.py \
  /path/to/retained/objects/548ae59778cf08ee0f2ee088e7ece20d947076c3c01f74d2d65db4c2777e436a
```

The original HTML is not copied into the repository. CI uses the compact
structural fixture in `test_sec_research_document_plain_toc.py`; the exact-file
replay requires that independently retained public source object.

## Removed Endpoint Ownership

Removed GET/POST `/sec-research/filings/{filing_id}/document` had no remaining
consumer after removing the Settings reader. They are not used by model tools.
Their private route/parser/acquisition scaffolding is deleted rather than left
as a forwarding alias. The exact API route inventory decreases from 224 to 222.

The seven existing citation HTTP cases move to
`test_sec_research_citation_routes.py`, plus GET/POST 404 guards which also
forbid credential/store access. Retained service and tool owners include:

- `test_sec_research_document_service.py`: observed-directory authority, quota,
  interruption, lock boundaries, content-free errors and request accounting.
- `test_sec_research_document_queries.py`: no-write/no-acquisition stored reads,
  cursor/filter binding, UTF-8 offsets and capture relocation.
- `test_sec_research_tool_service.py` and `test_sec_research_tool_adapters.py`:
  validation/permission before acquisition, captured authority and four-channel
  dispatch. These do not use the removed HTTP endpoints.
- `SecCitationView.test.tsx`: document, filing and fact citations still reopen
  through their independent GET API. Its product implementation is unchanged.

## Verification

RED-first checks covered missing settled queries and stale pages (13 frontend
failures), removed locale keys (one failure), source-link labels (three
failures), the real plain-title shape (11 failures), terminal punctuation (one
failure), and the two reader endpoint absence assertions. Independent static
review requested stronger descendant checks: 16 non-inline and 28 void-element
cases failed before the corresponding repairs. Those reports are retained.

The final 282 document cases pass on current Python 3.10.12 / SQLite 3.37.2 and
test-only prebuilt Python 3.10.21 / SQLite 3.53.1. `backend-candidate.xml.gz`
records the earlier 2,160-case SEC/API checkpoint before the last guard
refinements; it is not claimed as a final full candidate-runtime run.
The final current-runtime SEC/API run passes **2,217 cases**, with no failures,
errors or skips. Candidate aggregate case identities (checkpoint plus the
final document run) equal that set; the final 282-case document sets also agree.
The full frontend suite passes 1,818 cases in 124 files, plus typecheck and
production build. The build still reports the existing >500 kB chunk warning.

Actual Electron inspection then identified the source link's pre-existing
default dark-blue color and inconvenient position in narrow layouts. The final
frontend polish puts SEC original immediately after Filed date, uses theme
foreground and supplies hover/focus states. Five targeted assertions failed
before this polish and 61 panel cases pass afterward. An actual-browser color
assertion also failed on the default `rgb(0, 0, 238)` before the new bundle.
The final frontend total includes one additional contrast/focus regression;
the earlier full run had 1,817 cases. Backend code is unchanged by this polish.

The final reviewer found no remaining defect after both guard refinements.
Review was read-only and did not substitute for executing the tests. The source
link validator's pre-existing HTTP(S) host policy was noted; canonical SEC
catalog data remains its authority. The exact-file fixture availability limit
is documented above rather than claimed as portable full-document CI coverage.

Final results and scoped review are recorded with the test artifacts in
`checks/`. Backend runs are sequential, read-only outside private scratch,
network-disabled, with no other pytest session on this worktree. Frontend
tests also disable file parallelism and use private Vite cache mounts.
An initial shell invocation expanded the SEC file glob from the wrong cwd and
collected no tests; that runner error is not a passing or product-failure run.
The earlier 223-case synthetic GREEN did not cover the real file's terminal
period; exact-file replay caught it and produced the separately archived RED.

This repair does not claim a fresh full-backend run or live-model Research
acceptance. The revised remaining user checklist is
`docs/superpowers/plans/2026-09-15-sec-current-runtime-hand-test.md`.
