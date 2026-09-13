# Task 1 Report: Validated References And Exact Reopening

Status: implementation, focused verification, broad SEC verification, self-review,
and owned-file commit complete. Independent review and the complete backend suite
remain controller-owned. No test runner is active at handoff.

## Commit And Scope

- Worktree: `/tmp/arkscope-research-output-boundary` (used directly).
- Branch: `codex/sec-research-integration` (preserved, no merge or push).
- Starting HEAD: `f12663af147876a01784c9548c58cd541528585e`.
- Commit: `899b4098731fbd570c7a46d9a6353f0b95889b2a`.
- Subject: `feat(sec-research): add durable citations and exact source reopening`.
- Eight files, 1221 insertions and 3 deletions.

Committed files:

1. `src/sec_research/citations.py`
2. `src/sec_research/references.py`
3. `src/api/routes/sec_research.py`
4. `tests/test_sec_research_citations.py`
5. `tests/test_sec_research_references.py`
6. `tests/test_sec_research_document_routes.py`
7. `tests/test_api.py` (route count only)
8. `tests/test_security_lifecycle_routes.py` (route count and exact route set only)

The controller's docs-only amendment in
`docs/superpowers/plans/2026-09-13-sec-research-citations.md` remains unstaged and
unmodified by this worker. This report and the runner receipts are in the task's
ignored scratch directory, not in the product commit.

No existing source models, SQLite schema, profile iterator, event producers,
`output_events` schema, UI, SDK infrastructure, or acceptance infrastructure were
changed. No subagents were spawned. No production data, configuration, credentials,
provider sessions, installation, cleanup, reset, restart, merge, or push was used.
All manual edits used `apply_patch`; all tests used the supplied isolated runner.

## Public Interfaces

All citation interfaces below are in `src.sec_research.citations`:

```python
validate_citation(ref) -> dict
sec_citations_from_envelope(tool_name, envelope) -> list[dict]
sec_citations_from_result(tool_name, result) -> list[dict]
citation_event_fields(tool_name, result) -> dict
encode_citation_query(ref) -> str
decode_citation_query(token) -> dict
read_sec_citation(store, captures, *, citation) -> dict
```

`CitationError` extends `ValueError` and exposes `.code`; its message is only the
closed code. `CITATION_GAP_CODES` contains:

```text
sec_citation_invalid
sec_citation_result_invalid
sec_citation_query_invalid
sec_citation_missing
sec_citation_integrity_failed
```

Validation returns a copied, closed reference without coercion or storage access.
Required fields cannot be omitted, and extra fields are rejected. The union is:

```text
document:
  kind="document", filing_id, document_id, capture_id, accession, source_url,
  original_sha256, text_sha256, extraction_version, start_byte, end_byte,
  match_start_byte, match_end_byte

fact:
  kind="fact", cik, fact_id, snapshot_id, source_sha256, source_pointer,
  source_url, observed_at

filing:
  kind="filing", filing_id, snapshot_id, source_sha256, source_pointer,
  source_url, observed_at
```

Both match fields must be present. They are either both null or a strict nonempty
subrange of the passage. Numeric offsets must be integers, not booleans. CIKs,
IDs, lowercase hashes, RFC 6901 pointer escaping, canonical UTC timestamps, and
SEC HTTPS source locations are validated. Source URLs are evidence bindings, not
fetch instructions. Document IDs are resolved `file:` IDs, not the `primary`
alias. An exact passage is nonempty, at most 80000 UTF-8 bytes (the existing
20000-character tool cap's maximum UTF-8 size), and within the existing 128 MiB
object bound. Actual character boundaries are checked on reopening.

### Whole-Result Parsing And Event Projection

Only `list_sec_filings`, `get_sec_financial_facts`, and `read_sec_filing` are owned.
Name normalization removes at most one leading `mcp__ark__`, then at most one
leading `tool_`. Other provider prefixes and repeated arbitrary prefixes are not
accepted. Unknown tools return `[]` from derivation and `{}` from event projection
without inspecting the result.

Accepted inputs are the complete six-field dictionary, plain JSON, the owned
`<tool_output tool="NAME">\nJSON\n</tool_output>` wrapper, actual MCP text-block
lists, MCP result dictionaries with `content`, and SDK `CallToolResult` /
`TextContent` instances. Every text block must contain a whole admitted envelope.
Mixed non-text blocks, duplicate JSON keys, nonfinite JSON, malformed source rows,
wrong wrapper ownership, contradictory structured content, and invalid document
index evidence fail with a typed result error. If MCP `structuredContent` is
present, it must agree with the single text envelope. Prose, repr strings, and
`output_preview` are never searched for citations.

Fact references come from the actual row's nested `source` and snapshot metadata.
Filing references come from every actual `sources[]` entry, preserving conflicting
variants and duplicate filing IDs with distinct provenance. Document references
come only from whole passages, with agreement against the document metadata and
the passage's actual UTF-8 length. Exact duplicate references are deduplicated in
query order; whole envelopes are never mutated or given a seventh field.

The event helper returns exactly one of:

```python
{"sec_citations": [validated_ref, ...]}
{"sec_citation_gaps": ["sec_citation_result_invalid"]}
{}
```

`{}` is legitimate for unknown tools, valid SEC unavailable/empty results, and
valid document indexes or searches with no passage. Malformed owned evidence is
not converted to `{}` and no partial citation list escapes an invalid result.
Call this helper on the whole post-security result before preview/reduction.
Security admission itself remains with the existing producer boundary.

## HTTP Query Encoding

New route: `GET /sec-research/citation?ref=TOKEN`, registered before the dynamic
`/sec-research/{cik}` route. Existing router/application authentication is
unchanged. Exactly one `ref` parameter is accepted. Missing, duplicate, extra,
malformed, noncanonical, or oversized query parameters fail before store access:

```json
{"detail":{"code":"sec_citation_query_invalid"}}
```

HTTP status is 422. Rejected operands are not echoed.

The shared canonical encoding is precisely:

```python
raw = json.dumps(
    validate_citation(ref),
    sort_keys=True,
    ensure_ascii=True,
    allow_nan=False,
    separators=(",", ":"),
).encode("ascii")
token = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
```

- `MAX_CITATION_BYTES = 6144` limits canonical reference JSON.
- `MAX_CITATION_QUERY_BYTES = 8192` limits the encoded token.
- Individual source URL and pointer strings are limited to 2048 characters.
- Only `[A-Za-z0-9_-]+` is accepted on the wire; no base64 padding or whitespace.
- The decoder rejects duplicate members, validates the closed union, and requires
  re-encoding to produce the identical token. Alternative JSON spacing/key order,
  number spelling, padding bits, and Unicode escape spellings are not canonical.
- Frontend code must match `ensure_ascii=True`, including non-ASCII pointer
  values; ordinary UTF-8 `JSON.stringify` plus base64 is not equivalent for them.

There is no arbitrary file path, acquisition URL, write permission requirement,
configuration read, quota read, or provider construction on this GET.

## Exact Read Shapes

Every result has the existing six top-level fields. Successful fact/filing read:

```python
{
    "status": "ok",
    "data": {"citation": validated_ref, "observation": exact_stored_row},
    "gaps": [],
    "observed_at": validated_ref["observed_at"],
    "coverage": {"complete": True},
    "next_cursor": None,
}
```

`exact_stored_row` has the native `FactObservation` or `Filing` fields, nested
`source={sha256,pointer}`, plus `snapshot_id`, `observed_at`, `source_url`, and
`object_sha256`. Fact `value` stays exact Decimal TEXT. Query-derived `metrics`
and `period` annotations are not invented on this exact observation read; the
native start/end/fiscal/form metadata is available.

Successful document read:

```python
{
    "status": "ok",
    "data": {
        "citation": validated_ref,
        "text": exact_canonical_utf8_slice,
        "document": {
            "capture_id": ..., "accession": ..., "filing_id": ...,
            "document_id": ..., "form": ..., "source_url": ...,
            "original_sha256": ..., "text_sha256": ...,
            "extraction_version": ..., "mime_type": ...,
        },
    },
    "gaps": [],
    "observed_at": capture_observed_at,
    "coverage": {"complete": True},
    "next_cursor": None,
}
```

Missing/corrupt retained evidence is HTTP 200 with the unavailable domain envelope:

```python
{
    "status": "unavailable",
    "data": None,
    "gaps": [{"code": "sec_citation_missing"}],  # or sec_citation_integrity_failed
    "observed_at": None,
    "coverage": {"complete": False},
    "next_cursor": None,
}
```

The existing route-level not-installed case uses `sec_research_not_installed` and
`coverage={}`. Other route-level store failures use a content-free integrity gap.
Direct domain calls with a malformed reference raise `CitationError` before I/O.

Reopening verifies actual registered capture bytes, source SHA, snapshot identity,
canonical source URL, native source parsing, exact row/ordinal/count agreement,
and the specific pointer/observation ID. A receipt may establish a later
reobservation time for unchanged source bytes. A snapshot's first-publication
time also supports receipt-free retained fact-ID queries. No latest substitution
is used. Document reads additionally validate the immutable capture/directory
metadata identities, duplicate catalog provenance, every required catalog source,
the directory's real entries, original and text hashes/sizes, extraction-version
binding, and half-open UTF-8 passage/match boundaries. They do not re-extract old
documents with the current extractor.

Exact reads do not expand unrelated receipt members. In particular, a later
receipt adding unrelated corrupt catalog/fact bytes cannot invalidate a valid
retained observation. A document read needs its supporting catalog sources, not
unrelated companyfacts bytes from its receipt. Closure is intentionally stricter
and retains/verifies those receipt members.

## Closure Shape And Scaling

`src.sec_research.references.sec_reference_closure(store, *, citations) -> dict`
accepts an iterable of validated-reference-shaped dictionaries. It raises a
closed `CitationError` for malformed references or missing/corrupt reachable
nodes; it never returns a silently incomplete closure.

```python
{
    "capture_ids": ["secdoc_...", ...],
    "directory_ids": ["secdir_...", ...],
    "snapshot_ids": ["secsnapshot_...", ...],
    "receipt_ids": [1, 2, ...],
    "fact_ids": ["secfact_...", ...],
    "filing_ids": ["CIK:ACCESSION", ...],
    "fact_observations": [
        {"snapshot_id": "secsnapshot_...", "ordinal": 0, "fact_id": "secfact_..."},
    ],
    "filing_observations": [
        {"snapshot_id": "secsnapshot_...", "ordinal": 0, "filing_id": "CIK:ACCESSION"},
    ],
    "object_sha256s": ["lowercase-sha256", ...],
    "object_keys": ["objects/lowercase-sha256", ...],
}
```

ID/hash/key lists are unique and sorted. Receipt IDs sort numerically; observation
lists sort by `(snapshot_id, ordinal)`, preserving distinct catalog variants.
Empty input over an installed store returns all the same keys with empty lists.
No absolute filesystem paths are returned.

A document root retains its directory, all catalog sources, and all members of its
bound receipt, including companyfacts. A fact/filing root retains its exact source
and every matching receipt binding for its source snapshot/observation time, then
all members of those receipts. Each snapshot retains all native observations and
its raw object. Missing unrelated members of such a *closure* fail explicitly.
No profile enumeration, export, deletion, cleanup authorization, or schema reset
is performed here.

The initial draft incorrectly imposed cumulative 256 MiB/200000-node limits and
cached parsed row payloads across snapshots. The controller identified that
integration problem; both cumulative limits and the row-payload cache were
removed before commit. Final traversal uses the existing per-object 128 MiB and
per-snapshot admission rules, streams SQLite rows, verifies/processes one source
at a time, and retains compact verified metadata plus result identities. There is
no new whole-store byte, row, or root ceiling. The returned identity graph itself
necessarily grows with retained identities; source parsers still parse one whole
bounded source at a time.

Named scale owner:
`test_closure_aggregate_exceeds_per_object_budget_with_bounded_source_processing`.
It lowers the synthetic object limit to 64 KiB, creates 60 real retained sources
totalling over 30 times that limit, checks complete sorted output, and requires
traced peak processing memory below 12 times the per-object limit. The initial
draft failed at 2435533 traced bytes; the corrected implementation passes the
786432-byte bound. This is a synthetic scaling regression test, not an actual
100 GiB store benchmark.

## Verification Receipts

Every directory below contains `command.json`, `output.log`, and `results.xml`
under this report's directory. Logs and failed checkpoints were retained.

| Run | Outcome | Purpose |
| --- | --- | --- |
| `task1-baseline-01` | 491 passed | Existing real document/query/capture/route owners |
| `task1-red-01` | 103 failed, 81 deselected | Missing citation/closure behavior and citation route; assertion failures, not fixture/import errors |
| `task1-route-count-red-01` | 2 failed | Actual 222 routes versus requested 223 before implementation |
| `task1-green-01` | 186 passed | First implementation and both route-count owners |
| `task1-self-review-red-01` | 10 failed, 17 passed, 91 deselected | Invalid no-passage document metadata/status and conflicting MCP structured content were ignored |
| `task1-scale-red-01` | 4 failed, 5 passed, 7 deselected | Accumulated payload memory and unrelated-receipt exact-read coupling |
| `task1-scale-green-01` | 31 passed, 89 deselected | Scalable closure and isolated exact binding verification |
| `task1-self-review-green-01` | 208 passed | All citation/reference/document-route owners after fixes |
| `task1-broad-green-01` | 1534 passed | All existing SEC research test files plus actual application route-count owners |

Exact invoked commands (all from the worktree above):

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-baseline-01 backend -q tests/test_sec_research_document_queries.py tests/test_sec_research_document_store.py tests/test_sec_research_queries.py tests/test_sec_research_fact_queries.py tests/test_sec_research_captures.py tests/test_sec_research_document_routes.py tests/test_sec_research_routes.py
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-red-01 backend -q tests/test_sec_research_citations.py tests/test_sec_research_references.py tests/test_sec_research_document_routes.py -k 'citation or closure or corrupt_metadata or duplicate_catalog or whole_query or whole_results or conflicting_filing or unknown_tools or closed_fact or closed_document or malformed_owned or no_reference or document_index_and_empty or bound_hash or identical_bytes or canonical_query'
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-route-count-red-01 backend -q tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes tests/test_security_lifecycle_routes.py::test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-green-01 backend -q tests/test_sec_research_citations.py tests/test_sec_research_references.py tests/test_sec_research_document_routes.py tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes tests/test_security_lifecycle_routes.py::test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-self-review-red-01 backend -q tests/test_sec_research_citations.py tests/test_sec_research_references.py -k 'malformed_no_passage or no_evidence_status or conflicting_mcp or escaped_json_pointer or missing_pins or every_union or exhausted_closure or missing_or_corrupt_retained_object'
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-scale-red-01 backend -q tests/test_sec_research_references.py -k 'aggregate_exceeds or later_unrelated or missing_or_corrupt_retained_object'
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-scale-green-01 backend -q tests/test_sec_research_references.py tests/test_sec_research_citations.py -k 'aggregate_exceeds or later_unrelated or missing_or_corrupt_retained_object or closure or corrupt_metadata or duplicate_catalog or reopens_exact or tampering or reobserved or escaped_json_pointer'
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-self-review-green-01 backend -q tests/test_sec_research_citations.py tests/test_sec_research_references.py tests/test_sec_research_document_routes.py
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-broad-green-01 backend -q tests/test_sec_research_*.py tests/test_api.py::test_local_runtime_lifespan_starts_scheduler_and_enumerates_routes tests/test_security_lifecycle_routes.py::test_app_mounts_the_exact_lifecycle_route_surface_and_retires_old_review_routes
```

The broad receipt records the fully expanded list of test files and measured
1534 passing executions in 95.44 pytest seconds (97.028 runner seconds). Actual
application HTTP inventory increased from 222 to 223. No full backend, census,
browser, or frontend run was performed; no package-wide run followed the broad
GREEN checkpoint. Two newly drafted aggregate-budget test cases were removed
when the controller rejected that policy, and replaced by the scale/isolation
owners. No existing baseline test owner was removed.

`git diff --cached --check` passed before commit. The staged name list was checked
and contained exactly the eight owned files, not the parent plan.

## Self-Review And Handoff

- Confirmed closed unions, scalar validation before exact-read I/O, canonical
  encoding, no latest substitution, and no arbitrary path/URL acquisition.
- Confirmed real captured bytes and native parsers remain the authority; exact
  read tests do not mock the verifier. Original HTML and canonical text have
  distinct hashes in the citation fixture, so corruption checks are independent.
- Covered exact Decimal TEXT, escaped JSON pointers, conflicting filing variants,
  reobserved timestamps, refresh/relocation, missing pins, raw-object corruption,
  stored-row/receipt corruption, and duplicate document catalog provenance.
- Fixed the 10 self-review parsing failures with focused RED/GREEN receipts.
- Fixed the controller's scale/isolation finding with named RED/GREEN owners;
  no whole-store budget or parsed-row payload cache remains.
- Preserved the existing six-field model envelopes, authentication placement,
  provider admission, SDK behavior, immutable store schema, and capture budget.
- No known unresolved blocking finding remains from this worker's self-review.
  This statement is not independent review approval or full-suite approval.

Next consumers: Task 2 should use `citation_event_fields` on whole admitted output
and extend the separate closed `output_events` schema as the controller noted.
Task 3 owns `iter_research_sec_citations(profile_connection)` and durable JSON
roots; it is intentionally absent here. Task 4 can consume the HTTP encoding and
read shapes above. Later operation leases/export/cleanup are still required
before any actual maintenance operation; this closure does not authorize deletion.

## Committed File SHA-256

```text
909f848be6d83a29293eac71f6a53376d44a26ccf38b58382f3a8902072e1ea6  src/sec_research/citations.py
f24381ed677e43a5c8b86d1df945df4e45acf42e5f5b50f8f30e1eba513a5b40  src/sec_research/references.py
ba5a86525630b3f5af9ee302e1102b9de5e9231306a835814c2ecd7d2d9cee7b  src/api/routes/sec_research.py
eb588f4edbfa950ea79f1f72ffc6fa51fcd8ca8b47fcf213f6030571b277750c  tests/test_sec_research_citations.py
11892f2edf7b73b3f02339ef8932ffc86bed3311a9b4077e7ff7b5689adfe2ce  tests/test_sec_research_references.py
8915ccdf00d480a768a1f93e3b5eee29053cdaa5ab31e217d3b1c25e484a3ec6  tests/test_sec_research_document_routes.py
cb555cc247cc1fe92d56daa945636ea9e70d8580a940220dc4538ee86128a166  tests/test_api.py
bb0491b6b33cd60d275974288e74e7558dd89f004ce1fcb778823f6409215c1a  tests/test_security_lifecycle_routes.py
```

## Fix Round 1: Native Observation Validation

Review P2 addressed in `89509a31e49266533068ca8b21229dcb439a9ffd`, based on
controller docs-only `f5cbbbe46841cea73bb18a926a7b6c513a7d214c`. Only
`src/sec_research/citations.py` and `tests/test_sec_research_citations.py` are in
the fix commit; the parent acceptance/plan documents were not changed or staged.

`_observation_shape` now checks fact fiscal-year strict integer/range, nullable
fiscal-period/frame text, normalized nullable start, and start/end ordering.
Filings validate normalized report date, acceptance timestamp, document basename,
and the exact document-derived primary URL (including null pairing). Existing
`date_value`, `text_value`, `_accepted_at`, `_primary_document`, and `directory_url`
validators are reused. No model, API encoding/read/closure shape, exact binding,
per-object limit, or whole-store traversal policy changed; no new store cap.

Named RED owner `test_complete_native_row_mutations_are_closed_gaps` covers 31
mutations of complete real query rows, each after a valid row. Every case requires
the closed `sec_citation_result_invalid` exception and event gap with no partial
refs. The 8 controls in `test_native_nullable_facts_preserve_query_annotations`
and `test_native_nullable_filings_preserve_normalized_fields` use real parsed,
captured, published sources and queries: omitted/null fields, normalized empty
source values and offset timestamps, fiscal-year bounds, open text, equal period
dates, and unchanged query annotations remain admitted.

| Isolated Receipt | Result |
| --- | --- |
| `task1-fix1-red-01` | 31 expected failures (`DID NOT RAISE CitationError`), 8 passed, 104 deselected |
| `task1-fix1-green-01` | 430 passed, 0 failures/errors/skips |

GREEN JUnit owner counts: citations 143 (including all 39 new cases), catalog 66,
facts 54, queries 72, fact queries 95. Exact commands, from the existing worktree:

```bash
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-fix1-red-01 backend -q tests/test_sec_research_citations.py -k native
/home/hyl/.virtualenvs/llm_app/bin/python -B .superpowers/sdd/2026-09-13-sec-research-citations/run_checks.py task1-fix1-green-01 backend -q tests/test_sec_research_citations.py tests/test_sec_research_catalog.py tests/test_sec_research_facts.py tests/test_sec_research_queries.py tests/test_sec_research_fact_queries.py
```

Self-review checked the diff against native catalog/fact constraints and the
all-or-gap event behavior; no additional issue found. `git diff --check` and
`git diff --cached --check` passed; the committed scope and clean tracked worktree
were verified. No broad 1534-test/full-suite rerun, other runner, subagent, network,
or production access. Scoped independent re-review remains with the controller.
