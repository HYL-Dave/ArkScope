# Task2 Report: Durable Document Acquisition And Stored Passages

Fix round1 is complete at `1f964efe`; its concise delta and current verification
are appended at the end. The initial implementation report/examples below describe
`eeffb971` and remain historical evidence.

## Status

DONE. Commit `eeffb971` (`feat(sec-research): persist document captures and pinned passages`).
No blocking concerns identified in self-review. Parent owns independent review,
browser acceptance and the final integrated backend run. Sole-index work is done.

Scope: three document owners, their three test files, canonical schema and
root acquisition lease. Base b07eba2b. No parent/product edits included.
No external calls, credentials, installs, subagents, browser work or independent
reviewers. Implementation, self-review, final focused verification and scoped
commit are complete. Post-commit git status --short is empty; ignored evidence
and this report remain available at this plan's .superpowers/sdd path.

## Interface Shapes

`DocumentService(store, captures, *, reader_factory, clock)` is synchronous.
`refresh(filing_id, document_id="primary", check=None)` returns an append-only
attempt dictionary: `attempt_id`, `filing_id`, `document_id`,
`resolved_document_id`, `primary_document`, `acquisition_id`, `status`,
`capture_id` (nullable), `observed_at`, `outcome`,
`gaps`, `requests`. Each request entry has `operation` (`directory`/`document`),
`url`, and `report = {requests, observations}` from the actual reader.
`clock()` supplies a timezone-aware ISO string. No new environment identity.

`reader_factory(limits, *, document_observer, text_extractor)` returns a fresh
PublicSourceReader-compatible reader for each operation. The fixture supplies
an explicit SecSourcePolicy, declared fixture identity, and offline governor.
Limits: directory 16/16 MiB; original document 32/128 MiB wire/decoded;
one request, zero redirects, finite timeout.

`DocumentQueries(store, captures).read(filing_id, *, document_id="primary",
capture_id=None, section_id=None, query=None, cursor=None, max_chars=6000)`
returns exactly `status/data/gaps/observed_at/coverage/next_cursor`.
`data` has `document`, `documents`, `sections`, `passages`, `text_start_cursor`.
Passages have `text` and `citation`; citations include `filing_id`, resolved
`document_id`, `capture_id`, `accession`, `source_url`, `original_sha256`,
`text_sha256`, `extraction_version`, `start_byte`, `end_byte`, and nullable
`match_start_byte`/`match_end_byte`. Byte ranges are half-open UTF-8 ranges.
The whole-text start cursor resets section/query operands and retains max_chars.

Document metadata retains directory hash/observation, catalog receipt ID,
complete admitted catalog source set, original selected-row provenance,
primary binding, form, extraction version, sections/gaps and reader observations.
Directories/documents/source associations/attempts are separate immutable owned
tables with FKs to objects, receipts and catalog snapshots. Existing structured
receipt kinds and integer query anchors are unchanged.

## RED Evidence

- `task2-red-core-01`: 65 collected tests failed against missing Task2 owners.
- `task2-red-behavior-01`: 13 failed / 30 deselected against callable unavailable
  stubs, including absence/admission, conflicts, quota, pinned passages and sizing.
- `task2-green-core-01`: 64 passed / 1 failed. The failure was an incorrect fixture
  expectation of an available section index from an exhibit with no headings;
  fixture now includes an independently identifiable Item 1 heading.
- `task2-red-boundaries-01`: 4 failed / 4 passed / 43 deselected. Three implementation
  failures cover known directory cost before dispatch and primary/resolved latest
  aliases. One fixture expectation used the wrong catalog JSON pointer; corrected
  to `/filings/recent/accessionNumber/0` and `/accessionNumber/0`.
- Runner: this plan's `run_checks.py`, backend installed Python only.

## Verification Scope

All tests use this plan's offline runner with unique task2-* evidence directories.
Only installed Python/dependencies were used. No actual source/provider calls,
profile credentials, installs, reset/drop of real stores, merges or pushes.
SQLite integrity/mismatch checks operate exclusively on disposable fixtures.

## Focused Verification Progress

- `task2-green-core-02`: 73 passed, 0 failed (14.29s pytest time).
- `task2-red-error-boundary-01`: 1 failed / 11 passed; unknown RuntimeError from
  storage preflight escaped the closed acquisition boundary. Cross-process lease
  exclusion/release, malformed cursors and section bounds passed.
- `task2-red-boundary-final-01`: 2 failed; unknown stored-read RuntimeError leaked
  content and an unnecessary 800-character ID restriction rejected a safe observed
  filename whose URL remains within PublicSourceReader's existing limit.
- Service/read exception boundaries now sanitize unexpected Exception values while
  preserving BaseException interruption; the arbitrary filename ceiling is removed.
- `task2-green-core-03`: 86 passed, 0 failed (15.65s).

## Planned Inverses

All mutations were manually applied and restored through apply_patch. Each ran
only its named owner through this plan's offline runner and exited 1 for the
expected behavioral assertion. All eight owned source/test SHA-256 values were
checked after each restoration; every comparison matched the pre-inverse baseline.
The complete baseline and mutant hashes are in `task-2/inverse-hashes.json`.

| Inverse | Named owner | Evidence directory | Observed failure |
| --- | --- | --- | --- |
| Substitute latest for pinned capture | test_pinned_capture_survives_refresh_restart_and_relocation | task2-inverse-latest-01 | Reopened envelope differs after changed original body |
| Remove query cursor filter binding | test_document_cursor_binds_capture_filter_and_size | task2-inverse-query-binding-01 | Changed query did not raise cursor mismatch |
| Fabricate primary absence | test_only_receipt_bound_catalog_is_authority | task2-inverse-primary-absence-01 | Observed bound primary becomes unavailable |
| Mark truncated transport complete | test_incomplete_or_unsupported_capture_is_never_published[truncated] | task2-inverse-truncated-complete-01 | Incomplete response returns ok instead of unavailable |

`task2-green-after-inverses-01`: 86 passed, 0 failed (15.91s).
`task2-regression-01`: 1292 passed, 0 failed (47.88s); the single relevant
SEC/store/public-reader/wire/lock regression. Exact expanded file list and command
are in its command.json. No full backend run and no repeated Task1 regression.

Final self-review found a single oversized index entry could prevent reaching
subsequent choices. `task2-red-index-oversize-01` failed on the missing continuation.
The one-line fix advances past the explicitly gapped, un-emittable entry; no entry
text is truncated and later choices remain reachable. This follows the existing
structured-query principle of explicitly gapping an indivisible oversized record.
The new test and that one line are the only changes after the regression/inverse
baseline. `task2-precommit-01` is the final focused verification of those changes.

## Concrete Provenance Fields

`DocumentStore(store).capture(capture_id)` yields relational keys plus `metadata`
and `directory` dictionaries. `metadata.sources` contains the complete selected
filing rows returned by read_bound_sources (including `snapshot_id`, `source`
with sha256/pointer, `observed_at`, `source_url`, `object_sha256`).
`metadata.catalog_sources` includes every admitted catalog snapshot, even those
with no selected row: `locator`, `snapshot_id`, `object_sha256`, `observed_at`,
`source_url`. `metadata.receipt_id` is the original structured catalog receipt.
Remaining metadata fields: `primary_document`, `form`, `filing_id`, `document_id`,
`original_sha256`, `text_sha256`, `observed_at`, `refresh_observed_at`,
`directory_sha256`, `directory_id`, `source_url`, `observation_id`,
`extraction_version`, `mime_type`, `sections`, `section_gaps`, `catalog_gaps`,
`requests`, `text_bytes`, `original_bytes`.

Attempt rows append interruption markers before catalog resolution and again once
primary/resolved aliases are known, followed by the result. All rows for one call
share `acquisition_id` (also metadata.observation_id); there is no update-in-place.
`outcome`: complete, failed (actual request dispatched), no_dispatch, interrupted.
Lease failure returns an unavailable attempt with attempt_id=null and does not
write into another acquisition's history. Latest reads match primary/resolved
aliases, but cursors retain their original exact document operand.

## Consumer Examples

```python
from src.lifecycle_public_sources import PublicSourceReader
from src.lifecycle_web_sec_sources import SecSourcePolicy
from src.sec_research.document_service import DocumentService
from src.sec_research.document_queries import DocumentQueries, validate_document_query

# API owner obtains profile_identity explicitly from profile configuration.
def reader_factory(limits, *, document_observer, text_extractor):
    return PublicSourceReader(
        limits, sec_policy=SecSourcePolicy(user_agent=profile_identity),
        document_observer=document_observer, text_extractor=text_extractor,
    )

service = DocumentService(store, captures, reader_factory=reader_factory, clock=clock)
attempt = service.refresh("0000320193:0000950170-26-000001")
reads = DocumentQueries(store, captures)
index = reads.read("0000320193:0000950170-26-000001",
                   capture_id=attempt["capture_id"], max_chars=80)
text_page = reads.read("0000320193:0000950170-26-000001", max_chars=80,
                       cursor=index["data"]["text_start_cursor"])
search = reads.read("0000320193:0000950170-26-000001", query="needle",
                    capture_id=attempt["capture_id"], max_chars=80)
```

`validate_document_query` accepts the same operands as read and returns a dict
containing document_id/capture_id/section_id/query/cursor/max_chars (not filing_id).
It preserves literal/case-sensitive values and raises a content-free ValueError
before I/O for malformed operands/cursors. It never manufactures a receipt slot.
Cursor mismatch/invalid codes are `sec_research_cursor_mismatch` and
`sec_research_cursor_invalid`; other operand failures are `sec_research_query_invalid`.

`data.document` contains capture_id, filing_id, resolved document_id,
primary_document, form, source_url, original_sha256, text_sha256,
extraction_version, mime_type, text_bytes, original_bytes, directory_sha256.
`data.documents` entries have name/document_id/url/size_bytes/source; source has
sha256/pointer. `data.sections` entries are unchanged Task1 section dictionaries.
`coverage` has capture_id, receipt_id, mode, catalog_complete, complete; index
pages additionally expose index_total and index_offset. A failure before opening
a capture has null document, empty lists, null text_start_cursor, and coverage
`{capture_id: null, complete: false}`.

Search emits one complete literal match with bounded context per page and advances
to its end byte, so match starts do not overlap. Every text/search page is bounded
by Unicode characters; every citation uses canonical UTF-8 bytes. `next_cursor`
means more pages, while coverage.complete is false for continuation/gapped pages.
Unknown section returns unavailable plus section_unavailable and the whole-text
cursor; consume that cursor with section_id/query omitted and the same max_chars.
Unsupported forms preserve whole-text access and expose section_index_unsupported
on the index. A match longer than the page yields document_page_size_insufficient
without a partial match or stuck continuation. All encoded envelopes stay at or
below 256 KiB, and cursors at or below 4096 bytes.

## Requirement Review

| Requirement | Implementation/evidence |
| --- | --- |
| Exact immutable owned schema and unrelated preservation | Four new tables, FKs, lookup index, UPDATE/DELETE/REPLACE guards; document-store parametrized tests and existing Store tests |
| CaptureStore-only byte publication/accounting | Directory put before document request accounts known cost; original/text puts verified by hash/readback before atomic document/source rows |
| Original bytes are decompressed, not canonical text or wire bytes | Real PublicSourceReader gzip fixture asserts original and exact wire/decoded observations |
| Immutable observation/provenance identity | secdoc_/secdir_ SHA-256 identities include observation UUID/time, metadata, receipt, sources and reader reports |
| Receipt-bound catalog authority | open_query/read_bound_sources; conflict and source-budget cutoff prevent all dispatch; pending unrelated history retains gaps without a global veto |
| Exact directory admission | Only observed safe file IDs can dispatch; primary must exist; extension-free IDs and explicit long safe names use existing reader rules |
| Independent root lease | document_acquisition reuses _lease with a distinct name; in-process writer probes and cross-process owner termination/reacquisition pass |
| Cancellation/interruption and failure history | Synchronous service; reader request_stop in finally; BaseException leaves durable interruption markers; failed current reads never borrow earlier text |
| Stored integrity and portability | Capture/directory identity and FK/source associations verified; all original/text/directory/catalog objects hash-read; missing/corrupt fixtures and moved DB/root reopening pass |
| Bounded index and literal text/search | Character-sized pages, UTF-8 citations, whole-text fallback, all normal index entries reached across pages, oversized-entry gap with continuation |
| Closed cursor/no latest substitution | Canonical v1 token, no fake receipt anchor, capture/filing/document/filter/mode/size binding, exact byte boundary/section bounds, pure pre-I/O validation |
| Four planned inverses | Four named behavioral failures and all-eight-file hash restorations recorded above |
| Scope and integration | No Task1 signature/source changes, no route/UI/model-tool registration, no Store/CaptureStore source changes, no production schema mutation |

## Self-Review And Limits

Self-review examined all five product files and three tests, request/publication
ordering, schema/FKs/triggers, reader cleanup/reports, alias semantics, hash and
cursor validation, resource/page bounds and the final diff. No known blocking
defect remains. Parent independently reviews and runs browser/full integration.

The service intentionally has no async/thread bridge. An API owner that chooses
one must implement stop-and-await ownership; this implementation never starts a
document worker that could outlive its caller. The reader's existing bounded DNS
and timer lifecycle are unchanged.

Stored pages reverify complete referenced objects; this favors integrity over
large-capture paging speed. This task makes no whole-App RSS/4-GiB guarantee.
CaptureStore may retain charged complete objects after later publication failure;
there is no cleanup/pruning/export/recovery feature in Task2. Canonical schema
mismatches stay explicit: existing older owned SEC schemas are not migrated,
repaired, dropped or recreated at startup. Actual-store rollout is separate.

No existing exact-schema test required collateral edits: existing verification
owners already exercise the canonical schema as a whole. The eight staged paths
are the three new product modules, schema.py, capture_lock.py and the three new
test files. This report and task2 scratch/evidence remain outside the commit.

## Final Verification And Concrete Envelope

- `task2-precommit-01`: 87 passed, 0 failed (16.20s), after the oversized-index fix.
- `task2-inverse-latest-final-01`: final-source pinned/latest inverse killed, 1 failed.
- `task2-inverse-query-binding-final-01`: final-source filter-binding inverse killed, 1 failed.
- `task2-final-inverse-restored-01`: 4 passed, 0 failed (1.12s): both affected owners,
  oversized-index continuation, and an offline interface-example generator.
- `task-2/final-inverse-hashes.json`: final current eight-file hash snapshot and both
  final query mutant/restoration checks. Service SHA-256 is unchanged from its two
  earlier inverses, so those were not duplicated. No mutations remain.
- `git diff --check` and `git diff --cached --check`: passed.

The following is an actual index returned by the offline example generator, not a
hand-built response. Full refresh/index/text/search outputs with unshortened IDs,
cursors and request reports are in
`task2-final-inverse-restored-01/interface-examples.json`. Directory size_bytes is
an observed directory hint, independent of measured original_bytes.

```json
{
  "status": "ok",
  "data": {
    "document": {
      "capture_id": "secdoc_9cc130407524a5b67004d4f45465b302a16dacd2065513067c5c7830f476ee28",
      "filing_id": "0000320193:0000950170-26-000001",
      "document_id": "file:actual.htm",
      "primary_document": "actual.htm",
      "form": "10-K",
      "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000095017026000001/actual.htm",
      "original_sha256": "63aaffb1419acfc38f5a8cb09b65cacf721ed773db812bdc259542b9b2e9206c",
      "text_sha256": "122d4716b6849e5891cbfe148581a437dbc1c11c4da64f09f33c9b6f2c3d3a38",
      "extraction_version": "sec-document-text-v3",
      "mime_type": "text/html",
      "text_bytes": 38,
      "original_bytes": 53,
      "directory_sha256": "0dd9b5c8f43f213e809ab40880ec51d4be2cc239d61b31f2d870ced4960c48ad"
    },
    "documents": [
      {
        "name": "actual.htm",
        "document_id": "file:actual.htm",
        "url": "https://www.sec.gov/Archives/edgar/data/320193/000095017026000001/actual.htm",
        "size_bytes": 1,
        "source": {
          "sha256": "0dd9b5c8f43f213e809ab40880ec51d4be2cc239d61b31f2d870ced4960c48ad",
          "pointer": "/directory/item/0"
        }
      },
      {
        "name": "exhibit.xml",
        "document_id": "file:exhibit.xml",
        "url": "https://www.sec.gov/Archives/edgar/data/320193/000095017026000001/exhibit.xml",
        "size_bytes": 1,
        "source": {
          "sha256": "0dd9b5c8f43f213e809ab40880ec51d4be2cc239d61b31f2d870ced4960c48ad",
          "pointer": "/directory/item/1"
        }
      }
    ],
    "sections": [
      {
        "section_id": "item_1",
        "label": "Item 1. Business",
        "start_byte": 0,
        "end_byte": 38
      }
    ],
    "passages": [],
    "text_start_cursor": "eyJjYXB0dXJlX2lkIjoic2VjZG9jXzljYzEzMDQwNzUyNGE1YjY3MDA0ZDRmNDU0NjViMzAyYTE2ZGFjZDIwNjU1MTMwNjdjNWM3ODMwZjQ3NmVlMjgiLCJkb2N1bWVudF9pZCI6InByaW1hcnkiLCJmaWxpbmdfaWQiOiIwMDAwMzIwMTkzOjAwMDA5NTAxNzAtMjYtMDAwMDAxIiwiZmlsdGVyc19oYXNoIjoiNjUzN2UwNjQ1YzJlNTgzNmU2MmJjZTZhMTA2NjNhY2Q0ODJjZmRlYThkMzFmYjk0NjMyZjJjN2NjNmJiODMxNiIsIm1vZGUiOiJ0ZXh0Iiwib2Zmc2V0IjowLCJ2IjoxfQ"
  },
  "gaps": [],
  "observed_at": "2026-09-12T12:00:00Z",
  "coverage": {
    "capture_id": "secdoc_9cc130407524a5b67004d4f45465b302a16dacd2065513067c5c7830f476ee28",
    "receipt_id": 1,
    "mode": "index",
    "catalog_complete": true,
    "complete": true,
    "index_total": 3,
    "index_offset": 0
  },
  "next_cursor": null
}
```

Following that index's text_start_cursor returns this complete passage (within
the same six-key envelope):

```json
{
  "text": "Item 1. Business\nneedle one needle two",
  "citation": {
    "filing_id": "0000320193:0000950170-26-000001",
    "document_id": "file:actual.htm",
    "capture_id": "secdoc_9cc130407524a5b67004d4f45465b302a16dacd2065513067c5c7830f476ee28",
    "accession": "0000950170-26-000001",
    "source_url": "https://www.sec.gov/Archives/edgar/data/320193/000095017026000001/actual.htm",
    "original_sha256": "63aaffb1419acfc38f5a8cb09b65cacf721ed773db812bdc259542b9b2e9206c",
    "text_sha256": "122d4716b6849e5891cbfe148581a437dbc1c11c4da64f09f33c9b6f2c3d3a38",
    "extraction_version": "sec-document-text-v3",
    "start_byte": 0,
    "end_byte": 38,
    "match_start_byte": null,
    "match_end_byte": null
  }
}
```
## Fix Round1 Delta: I1 And I2

DONE. Commit `1f964efe305816641439926b4ede4473563056b2`, based on eeffb971.
Both Important findings were read in full and reproduced before source edits.
Only these four files changed: src/sec_research/document_service.py,
src/sec_research/document_store.py, tests/test_sec_research_document_service.py,
tests/test_sec_research_document_queries.py. No Task3/4, worker thread, schema
repair/change, Task1 interface/version change, provider/network/install or reviewer.

### Interface Delta

- Attempt output/immutable details add nullable `invalidation_primary_document`.
  DocumentStore.record_attempt adds that optional keyword; the new
  DocumentStore.invalidation_primary_document(filing_id, document_id) returns the
  latest established alias only for invalidation. It is captured before the first
  marker; fresh resolved_document_id/primary_document remain null on resolution
  failure. Stale catalog metadata never authorizes dispatch. Both spellings and
  markers block stale current reads; pinned reads are unchanged. Old attempt JSON
  reads the missing field as null without migration or writes.
- Exact request-record shape, used by attempt.requests, capture metadata.requests
  and the directory's request provenance (the call signatures/envelope are unchanged):

```text
{
  operation: "directory" | "document",
  url: str,
  request_count: int | null,
  dispatch_state: "dispatched" | "not_dispatched" | "unknown",
  report: {requests: int, observations: list[dict]} | null,
  gaps: list[{code: str}]
}
```

Count is independently snapshotted before report validation/cleanup: exact integer
0 <= count < 2**53, or null when unreadable/invalid. Positive/zero/null map to
dispatched/not_dispatched/unknown. A failed attempt with any known dispatch is
failed; unknown-only is interrupted; known zero/no operation is no_dispatch.
report is the actual validated reader report or null, never fabricated. Reporting
and cleanup failures add sanitized source_read_report_invalid and/or
source_read_cleanup_failed, preserving the original read error. A valid complete
read report can remain even when later cleanup prevents capture publication.

The original reviewer probe and checkpoint-specific hash assertion are untouched.
Its old I2 sum(report.requests) assertion is historical; the shipped actual-reader
owner instead requires independent count/state plus report=null for status600.
No full example is repeated; existing index/envelope examples are structurally
unchanged, while request records use the shape above.

### Evidence Delta

Runner: `/home/hyl/.virtualenvs/llm_app/bin/python .superpowers/sdd/2026-09-12-sec-document-reading/run_checks.py task2-fix-r1-<suffix> backend -q <selection>`.
Each named directory retains the exact selection in command.json and results/logs.
Hash prefixes below are service mutant -> restored; full nine-file snapshots,
exact named inverse owners/selections and restoration checks are in
`task-2/fix-r1-inverse-hashes.json`.

| Owner / Check | Command suffix | Result | Hash |
| --- | --- | --- | --- |
| Original reviewer behavioral RED | red-review-01 | 5 failed, 1 deselected | pre-fix source |
| New behavioral RED | red-owners-01 | 16 failed, 2 passed, 65 deselected | pre-fix source |
| Unknown/count snapshot RED | red-count-01 | 3 failed, 36 deselected | intermediate RED |
| Amended owners GREEN | green-owners-01 | 20 passed, 65 deselected | 4e1b311d4b54 |
| All Task2 + original I1 probes | green-core-01 | 111 passed, 2 deselected | 4e1b311d4b54 |
| Task2/store/captures/lock/public reader/wire regression | regression-01 | 338 passed (21.53s) | 4e1b311d4b54 |
| I1 both alias directions + first marker | inverse-alias-01 | 6 failed | 2c66ed565260 -> 4e1b311d4b54 |
| I2 invalid reports, directory + document | inverse-report-01 | 2 failed | abbc706e60f4 -> 4e1b311d4b54 |
| I2 cleanup + counter preservation | inverse-cleanup-01 | 7 failed | 1b55c255c0f5 -> 4e1b311d4b54 |
| I2 unknown is not zero | inverse-unknown-01 | 1 failed | 0e646bc458b1 -> 4e1b311d4b54 |
| Receipt-bound primary absence | inverse-primary-01 | 1 failed | 8acefd2b23f5 -> 4e1b311d4b54 |
| Truncated read cannot be complete | inverse-truncated-01 | 1 failed | 78f037355e7a -> 4e1b311d4b54 |
| Restored affected owners | restored-01 | 20 passed, 65 deselected | 4e1b311d4b54 |

All six inverses failed on their intended assertions and all nine hashes matched
after every restoration and after commit. Query source remains 71e00e4d4fc1,
so its two original inverses were not duplicated; the manifest links that evidence.
GREEN's two deselections are only the old checkpoint hash and obsolete I2 shape
assertion. The 107 shipped Task2 tests and four original I1 probes all pass.

Self-review covered the complete four-file diff, current/pinned alias semantics,
dispatch/cleanup ordering, sanitized gaps and backward read-only attempt JSON.
No remaining blocking finding identified. git diff --check and staged check passed;
only the four owned files were committed, post-commit status is empty, and no
source mutation remains. Reports/evidence are unstaged. Parent scoped rereview
and eventual full integration/browser acceptance remain parent-owned.
